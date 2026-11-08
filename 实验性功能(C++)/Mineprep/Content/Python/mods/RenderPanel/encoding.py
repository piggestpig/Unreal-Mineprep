"""根据渲染设置拼接 FFmpeg 视频编码与图片转码命令（纯字符串构建，不依赖 Unreal）。"""
import json
import re
import shlex
import sys
from pathlib import Path

# 保留独立 Python 的编码命令构建能力；只有引擎内需要本地化 Text。
if 'unreal' in sys.modules:
    from mineprep import i18n
else:
    def i18n(source, *texts, **languages):
        return source

TABLES = json.loads(Path(__file__).with_name('encoding_tables.json').read_text(encoding='utf-8'))
CODECS = ('H.264', 'H.265', 'AV1', 'ProRes')
HARDWARE = ('CPU', 'Nvidia', 'Intel', 'AMD', 'Apple', 'Vulkan')


def quote(value):
    value = str(value)
    if any(c in value for c in ('"', '\r', '\n', '\0')):
        raise ValueError(i18n('输出名称／路径不能包含双引号或控制字符'))
    return '"' + value + '"'


def output_name(text):
    """拆分相对子目录与文件主干名（行为与蓝图“解析文本框路径”一致）。"""
    text = str(text).replace('\\', '/').strip()
    quote(text)
    folder, separator, leaf = text.rpartition('/')
    stem, dot, extension = leaf.rpartition('.')
    if not dot or extension.lower() not in ('mp4', 'mov', 'mkv', 'avi', 'webm', 'png', 'jpg', 'jpeg', 'exr', 'avif', 'webp', 'gif', 'jxl'):
        stem = leaf
    if not stem or text.startswith('/') or re.match(r'^[A-Za-z]:', text) or '..' in text.split('/'):
        raise ValueError(i18n('输出名称须为非空的相对文件名，可包含子目录'))
    return (folder if separator else ''), stem


def uses_background(s):
    return s.get('background_encode') == 1 and (s.get('video') == 1 or s.get('image_transcode', 'No') != 'No')


def routing(s):
    video = s['video'] == 1
    background = video and s.get('background_encode') == 1
    stereo = s['stereo'] == 1
    vr = s['vr']
    codec = s['codec']
    windows = s['platform'] == 'Windows'
    # 平面立体走宏的 Unchecked 分支，全景立体走 Undetermined 分支
    transcode = codec in (0, 3) and video and (
        s['hdr'] == 1 or not windows or
        stereo and (s['stereo_format'] in (1, 2) or s['stereo_format'] == 3 and vr == 0 and windows))
    # 原生 MP4 编码器不支持 MOV 容器，选 MOV 时改走 FFmpeg
    if video and codec == 0 and s['container'].lower() != 'mp4':
        transcode = True
    native = video and codec in (0, 3) and not transcode and not background
    ffmpeg = background or video and (transcode or codec not in (0, 3)) or not video and s['image_transcode'] != 'No'
    return {'native': native, 'ffmpeg': ffmpeg, 'transcode': transcode}


def merge_filters(command):
    """将命令中的多个 -vf 滤镜参数合并为一个，保留首次出现的位置与其余参数。"""
    pattern = re.compile(r'-vf\s+"([^"\n]*)"')
    matches = list(pattern.finditer(command))
    if len(matches) < 2:
        return command
    filters = ','.join(m[1] for m in matches)
    first = matches[0]
    tail = pattern.sub('', command[first.end():])
    return command[:first.start()] + '-vf ' + quote(filters) + tail


def stereo_command(command, mode):
    """将单视角序列帧编码命令转换为左右眼 (_L / _R) 立体视频编码命令。"""
    inputs = list(re.finditer(r'-i\s+"([^"]+)"', command))
    output = re.search(r'"([^"]+)"\s*$', command)
    if not inputs or not output:
        raise ValueError(i18n('立体编码命令缺少输入或输出路径'))
    if '-filter_complex' in command:
        raise ValueError(i18n('无法自动组合已有 filter_complex 与立体输出'))
    rate_match = re.search(r'-r\s+([\d./]+)', command)
    rate = rate_match[1] if rate_match else '24'
    base, ext = inputs[0][1].rsplit('.', 1)
    prefix = command[:rate_match.start()] if rate_match else ''
    head = f'{prefix}-r {rate} -i {quote(base + "_nDisplayLit_L." + ext)} -r {rate} -i {quote(base + "_nDisplayLit_R." + ext)}'
    audio = len(inputs) > 1
    if audio:
        audio_base, audio_ext = inputs[1][1].rsplit('.', 1)
        head += ' -i ' + quote(audio_base + '._Audio_main_camera.' + audio_ext)
    params = command[inputs[-1].end():output.start()].strip()
    filters = re.findall(r'-vf\s+"([^"]*)"', params)
    if mode == 0:
        # 独立双眼输出时为左右眼同时保留 -vf 滤镜参数
        base, ext = output[1].rsplit('.', 1)
        amap = ' -map 2:a' if audio else ''
        return (f'{head} -map 0:v{amap} {params} {quote(base + "_L." + ext)} '
                f'-map 1:v{amap} {params} {quote(base + "_R." + ext)}')
    params = re.sub(r'-vf\s+"[^"]*"', '', params).strip()
    graph = {1: '[0:v][1:v]hstack[out]', 2: '[0:v][1:v]vstack[out]',
             3: '[0:v][1:v]hstack[sbs];[sbs]stereo3d=sbsl:arcd[out]'}[mode]
    label = '[out]'
    if filters:
        graph += ';[out]' + ','.join(filters) + '[final]'
        label = '[final]'
    amap = ' -map 2:a' if audio else ''
    return f'{head} -filter_complex {quote(graph)} -map {quote(label)}{amap} {params} {quote(output[1])}'


def build_command(s, project_dir):
    route = routing(s)
    if not route['ffmpeg']:
        return ''
    folder, name = output_name(s['name'])
    base = str(Path(project_dir) / 'Saved' / 'MovieRenders' / folder / name).replace('\\', '/')
    formats = s['image_formats']
    source = 'exr' if formats & 12 else 'png' if formats & 1 else 'jpeg'
    if not formats & 15:
        raise ValueError(i18n('ffmpeg 编码需要至少一种图片序列格式'))
    fps = format(s['fps'], '.12g')
    source_args = f'-r {fps} -i {quote(base + ".%04d." + source)}'
    linear = ''
    if formats & 12 and s['hdr'] != 1 and s['color'] == 0:
        linear = '-vf "zscale=tin=linear:pin=bt709:t=iec61966-2-1:p=bt709,format=rgba"'
    quality = s['quality']
    if s['video'] == 1:
        hardware = HARDWARE[s['hardware']]
        codec = CODECS[s['codec']]
        # Nvidia / Intel / AMD 显卡无硬件 ProRes 编码器，回退至 CPU 编码
        if codec == 'ProRes' and hardware in ('Nvidia', 'Intel', 'AMD'):
            hardware = 'CPU'
        encoder = TABLES['硬件到编码'][hardware + codec]
        # 修正旧编码表中无法被 FFmpeg 识别的 '- qp_i' 多余空格
        speed = TABLES['硬件到质量'][hardware + str(quality)].replace('- qp_i', '-qp_i')
        if codec == 'AV1' and hardware == 'CPU':
            speed = f'-preset {(8, 6, 5, 4)[quality]} -crf {(40, 32, 24, 18)[quality]}'
        if hardware == 'AMD':
            speed = f'-quality {("speed", "balanced", "quality", "quality")[quality]} -rc cqp -qp_i {(28, 23, 19, 16)[quality]} -qp_p {(28, 23, 19, 16)[quality]}'
        if codec == 'ProRes':
            speed = '-profile:v ' + str(quality + 1)
        depth = s['chroma']
        if codec == 'H.264':
            depth = depth.replace('10bit', '8bit').replace('12bit', '8bit')
        pixel = TABLES['硬件到pix_fmt'].get(hardware + depth)
        if codec == 'ProRes':
            pixel = '-vf "format=yuva444p10le,hwupload"' if hardware == 'Vulkan' else ''
        if pixel is None:
            raise ValueError(i18n('旧编码映射不支持 {hardware} / {depth}，请调整硬件或色度抽样').format(hardware=str(hardware), depth=str(depth)))
        hdr = TABLES['硬件到HDR'].get(hardware + codec, '') if s['hdr'] == 1 else linear
        audio = f' -i {quote(base + ".wav")} -acodec aac -b:a 320k' if s['audio'] == 1 else ''
        init = '-init_hw_device vulkan=vk:0 ' if hardware == 'Vulkan' else ''
        cmd = f'-hide_banner -y {init}{source_args}{audio} -vcodec {encoder} {speed} {hdr} {pixel} {quote(base + "." + s["container"])}'
    else:
        kind = s['image_transcode'].lower()
        hdr = ('-vf "zscale=primariesin=bt2020:primaries=bt2020:matrixin=bt2020nc:matrix=bt2020nc:'
               'transferin=smpte2084:transfer=smpte2084" -color_primaries bt2020 -color_trc smpte2084 -colorspace bt2020nc') if s['hdr'] == 1 else linear
        if kind == 'png':
            if s['hdr'] == 1:
                hdr = hdr.replace('transfer=smpte2084"', 'transfer=smpte2084,unpremultiply=inplace=1,format=rgba64be"')
            cmd = f'{source_args} {hdr} -pix_fmt rgba64be -y {quote(base + ".%04d.png")}'
        elif kind == 'avif':
            crf = (50, 35, 20, 1)[quality]
            color_range = '-color_range tv' if s['hdr'] == 1 else ''
            cmd = f'{source_args} {hdr} {color_range} -c:v libsvtav1 -crf {crf} -pix_fmt yuv420p10le -y {quote(base + ".avif")}'
        elif kind == 'webp':
            cmd = f'{source_args} {linear} -c:v libwebp -pix_fmt yuva420p -quality {(40,60,80,100)[quality]} -loop 0 -y {quote(base + ".webp")}'
        elif kind == 'jxl':
            color_range = '-color_range tv' if s['hdr'] == 1 else ''
            cmd = f'{source_args} {hdr} {color_range} -c:v libjxl_anim -effort 5 -distance {(5,3,1.5,.5)[quality]} -f image2pipe -y {quote(base + ".jxl")}'
        elif kind == 'gif':
            palettes = ('=max_colors=32', '=max_colors=64', '=max_colors=96', '')
            dither = ('=dither=bayer:bayer_scale=4', '=dither=bayer:bayer_scale=3', '=dither=bayer:bayer_scale=3', '')
            vf = f'fps={fps},split[s0][s1];[s0]palettegen{palettes[quality]}[p];[s1][p]paletteuse{dither[quality]}'
            cmd = f'{source_args} -vf {quote(vf)} -loop 0 -y {quote(base + ".gif")}'
        else:
            raise ValueError(i18n('未知图片转码格式：{image_transcode}').format(image_transcode=str(s["image_transcode"])))
    cmd = merge_filters(cmd)
    if s['stereo'] == 1 and s['vr'] == 0 and s['platform'] in ('Windows', 'Linux'):
        cmd = stereo_command(cmd, s['stereo_format'])
    return cmd


def still_args(s, inputs, output):
    """复用图片转码滤镜与质量；明确输入文件和单帧输出，支持合并左右眼。"""
    source = Path(inputs[0]).suffix.lower()
    values = dict(s, video=0, audio=0, stereo=0,
                  image_formats={'.exr': 4, '.png': 1, '.jpg': 2, '.jpeg': 2}[source])
    args = shlex.split(build_command(values, s['project_dir']))
    if args[:1] == ['-r']:
        del args[:2]
    index = args.index('-i')
    args[index + 1] = Path(inputs[0]).as_posix()
    args[-1] = Path(output).as_posix()
    if s['image_transcode'].lower() == 'gif' and '-vf' in args:
        index = args.index('-vf')
        args[index + 1] = re.sub(r'^fps=[^,]+,', '', args[index + 1])
    if len(inputs) == 2:
        args[index + 2:index + 2] = ['-i', Path(inputs[1]).as_posix()]
        mode = s['stereo_format']
        combine = {1: 'hstack', 2: 'vstack', 3: 'hstack,stereo3d=sbsl:arcd'}[mode]
        filters = ''
        if '-vf' in args:
            index = args.index('-vf')
            filters = ',' + args[index + 1]
            del args[index:index + 2]
        args[-1:-1] = ['-filter_complex', '[0:v][1:v]' + combine + filters + '[out]', '-map', '[out]']
    args[-1:-1] = ['-frames:v', '1']
    if s['image_transcode'].lower() == 'png':
        args[-1:-1] = ['-update', '1']
    return args
