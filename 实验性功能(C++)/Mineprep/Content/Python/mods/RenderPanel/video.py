"""后台视频编码与图片转码：沿用现有异步任务，渲染与进程占用分别管理。"""
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from uuid import uuid4

import unreal

from . import encoding, ops


def prepare(state, config, backend, output_dir):
    s = state['settings']
    folder = 'RenderPanelStill' if s.get('single_frame') else 'RenderPanelImages' if s['video'] == 0 else 'RenderPanelVideo'
    cache = Path(s['project_dir']) / 'cache' / folder / uuid4().hex
    state.update(cache_dir=str(cache), output_dir=output_dir,
                 output_key=tuple(part.casefold() for part in encoding.output_name(s['name'])),
                 background_still=bool(s.get('single_frame')))
    ops._background[id(state)] = state
    if backend == 'MRG':
        output = config.get_nodes_for_branch(unreal.MovieGraphGlobalOutputSettingNode, 'Globals')[0]
        ops._set(output, bOverride_OutputDirectory=True, OutputDirectory=unreal.DirectoryPath(str(cache)))
    else:
        output = config.find_setting_by_class(unreal.MoviePipelineOutputSetting)
        ops._set(output, OutputDirectory=unreal.DirectoryPath(str(cache)))


def ffmpeg_path(settings):
    from . import hdr
    return str(settings.get('ffmpeg_path', '')).strip().strip('"') or hdr._context(None)['ffmpeg']


def acquire(state, notice):
    """视频和图片转码共用后台进程名额。"""
    from . import batch
    state.update(phase='等待后台编码', encoding_started=False)
    while sum(job.get('encoding_started', False) for job in ops._background.values()) >= ops.MAX_BACKGROUND_ENCODERS:
        notice.stage('等待后台编码')
        yield 0.1
    state.update(phase='后台编码中', encoding_started=True)
    batch._changed()


def run(state, jobs):
    """jobs 为 (argv, output_file)；最多两个 FFmpeg，同时仍允许一项 MRQ 渲染。"""
    from . import batch, hdr
    title = 'Filmic HDR 视频编码' if state.get('filmic') else '后台图片转码' if state.get('settings', {}).get('video') == 0 else '后台视频编码'
    if state.get('settings', {}).get('name'):
        title += ' · ' + state['settings']['name']
    notice = hdr._ProcessingNotice(title)
    success = False
    try:
        yield from acquire(state, notice)
        cache = Path(state['cache_dir'])
        cache.mkdir(parents=True, exist_ok=True)
        cache.joinpath('encode_commands.json').write_text(json.dumps(
            [args for args, _ in jobs], ensure_ascii=False, indent=2), encoding='utf-8')
        encoded = []
        for index, (args, output) in enumerate(jobs):
            output = Path(output)
            output.parent.mkdir(parents=True, exist_ok=True)
            unreal.log(subprocess.list2cmdline(args))
            log = cache / ('encode.log' if state.get('filmic') else f'encode_{index}.log')
            yield from hdr._run_process(args, log, title, notice=notice)
            outputs = [output]
            if '%04d' in str(output):
                start_at = [i for i, arg in enumerate(args) if arg == '-start_number'][-1]
                start = int(args[start_at + 1])
                count = int(args[args.index('-frames:v') + 1])
                outputs = [Path(str(output).replace('%04d', f'{frame:04d}')) for frame in range(start, start + count)]
            if not all(path.is_file() and path.stat().st_size for path in outputs):
                raise RuntimeError(f'编码未生成有效输出：{output}')
            encoded.extend(str(path) for path in outputs)
        state['encoded_files'] = encoded
        success = state['success']
        return True
    except hdr._ProcessingCancelled:
        state.update(success=False, cancelled=True)
        return False
    finally:
        state['encoding_started'] = False
        notice.finish(success)
        batch._changed()


def commands(s, files, ffmpeg, output_dir):
    """根据本次回调的实际帧序列生成各通道命令，不扫描上一次的图片。"""
    groups = {}
    audio = [str(Path(path)) for path in files if Path(path).suffix.lower() == '.wav']
    for value in files:
        path = Path(value)
        match = re.match(r'^(.*\.)(-?\d+)((?:_[^.]*)?\.(exr|png|jpe?g))$', path.name, re.I)
        if not match:
            continue
        prefix, frame, suffix, extension = match.groups()
        key = str(path.parent / (prefix + '%04d' + suffix))
        groups.setdefault(key, dict(prefix=prefix, suffix=suffix, extension=extension.lower(), frames=[]))['frames'].append(int(frame))
    # 同一通道多格式时优先 EXR，其次 PNG/JPEG，与旧命令一致。
    selected = {}
    for pattern, group in sorted(groups.items(), key=lambda pair: ({'exr': 0, 'png': 1}.get(pair[1]['extension'], 2), pair[0])):
        selected.setdefault(str(Path(pattern).with_suffix('')), (pattern, group))
    jobs = []
    for _, (pattern, group) in selected.items():
        flat = s['stereo'] == 1 and s['vr'] == 0 and s['platform'] in ('Windows', 'Linux')
        merge = flat and s['stereo_format'] != 0 and '_nDisplayLit_' in pattern
        if merge and '_nDisplayLit_R' in pattern:
            continue
        frames = sorted(set(group['frames']))
        if frames != list(range(frames[0], frames[-1] + 1)):
            raise RuntimeError(f'图片帧不连续：{pattern}')
        stem = group['prefix'].rstrip('.') + group['suffix'].rsplit('.', 1)[0]
        if flat:
            stem = stem.replace('_nDisplayLit_L', '' if merge else '_L').replace('_nDisplayLit_R', '_R')
        image = s['video'] != 1
        include_audio = not image and s['audio'] == 1
        extension = s['image_transcode'].lower() if image else 'mov' if s['codec'] == 3 else s['container'].lower()
        output = Path(output_dir) / (stem + ('.%04d' if image and extension == 'png' else '') + '.' + extension)
        values = dict(s, stereo=0, background_encode=1, container=extension,
                      image_formats={'exr': 4, 'png': 1}.get(group['extension'], 2))
        args = shlex.split(encoding.build_command(values, s['project_dir']))
        args[args.index('-r')] = '-framerate'
        index = args.index('-i')
        args[index:index] = ['-start_number', str(frames[0])]
        index = args.index('-i')
        args[index + 1] = pattern
        if include_audio:
            if not audio:
                raise RuntimeError('本次渲染没有生成请求的视频音频输入')
            audio_index = args.index('-i', index + 2)
            args[audio_index + 1] = audio[0]
        if merge:
            right = pattern.replace('_nDisplayLit_L', '_nDisplayLit_R')
            if right not in groups or sorted(set(groups[right]['frames'])) != frames:
                raise RuntimeError('左右眼图片缺失或帧范围不一致')
            args[index + 2:index + 2] = ['-framerate', str(s['fps']), '-start_number', str(frames[0]), '-i', right]
            combine = {1: 'hstack', 2: 'vstack', 3: 'hstack,stereo3d=sbsl:arcd'}[s['stereo_format']]
            filters = ''
            if '-vf' in args:
                at = args.index('-vf')
                filters = ',' + args[at + 1]
                del args[at:at + 2]
            args[-1:-1] = ['-filter_complex', '[0:v][1:v]' + combine + filters + '[out]', '-map', '[out]']
            if include_audio:
                args[-1:-1] = ['-map', '2:a:0']
        args[-1] = str(output)
        args[-1:-1] = ['-frames:v', str(len(frames))]
        if image and extension == 'png':
            args[-1:-1] = ['-start_number', str(frames[0])]
        jobs.append(([ffmpeg, *args], output))
    return jobs


def encode(state):
    s = state['settings']
    files = state.get('output_files', [])
    jobs = commands(s, files, ffmpeg_path(s), state['output_dir'])
    if not jobs:
        if state['success']:
            raise RuntimeError('本次渲染没有生成可编码的图片')
        return
    if not (yield from run(state, jobs)):
        return
    # 只有整个编码成功后才发布／删除本次原图。取消后的部分视频保留缓存。
    if state['success']:
        cache = Path(state['cache_dir'])
        publish_sources(state)
        shutil.rmtree(cache)


def publish_sources(state):
    """保留原图时搬回原目录，但不能覆盖刚完成的同名转码结果。"""
    if state['settings']['delete_source'] == 1:
        return
    cache = Path(state['cache_dir'])
    converted = {Path(path) for path in state.get('converted_files', []) + state.get('encoded_files', [])}
    for value in state.get('output_files', []):
        source = Path(value)
        target = Path(state['output_dir']) / source.relative_to(cache)
        if target not in converted:
            target.parent.mkdir(parents=True, exist_ok=True)
            source.replace(target)
