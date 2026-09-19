# Mineprep 命令行安装脚本（不依赖 Blender）
# 与 Mineprep_installer.blend 放在同一目录，用系统 Python 即可运行。
#
# 用法:
#   python Mineprep_installer.py new [目录] [--name 工程名]
#   python Mineprep_installer.py existing <已有工程目录>
#   python Mineprep_installer.py -h
#
# 参数:
#   --lite 1|2
#       安装精简版。1 会跳过源码、运动匹配、音效等少用资源；
#       2 只保留核心素材（插件贴图、Render，以及名称含 core 的目录）。
#       省略则装完整内容。若安装包路径带 Lite 且未写本参数，视为 1。
#   --crossplatform
#       同时拷贝 Windows / Mac / Linux 的平台文件。省略则只拷当前系统。
#   --experimental DIGITS
#       实验性功能，数字可连写：1 是 C++ 模块，2 是材质参数面板，3 是 VR3D渲染。
#       例如 12、123。默认关闭。
#   --ffmpeg <exe>
#       使用指定的 ffmpeg 可执行文件。省略则用安装包解压出来的版本。
#   --gbuffer 0|1
#       Substrate GBuffer。1 为 Adaptive（默认，画质更好），0 为有限 Blendable（兼容性更好，性能更快）。
#   --preload
#       启动时在后台预加载资源，运行时更流畅。默认关闭。
#   --optimize
#       降低默认画质，换取更好性能。默认关闭。
#   --name NAME
#       仅用于 new，指定 .uproject 文件名，默认为 MC_Startup。
#   --lang zh_CN|en_US|zh_TW
#       提示文本语言。省略则跟随系统。
#   --dry-run
#       只打印将要安装的内容和估算体积，不写入磁盘。
#   --open
#       安装完成后打开工程文件。
#
# 示例:
#   完整版（功能全开）:
#     python Mineprep_installer.py new --experimental 123 --crossplatform --preload --open
#   精简版（省空间）:
#     python Mineprep_installer.py new --experimental 12 --lite 1 --optimize --gbuffer 0 --open
#
# new 若不写目录，默认装到「本仓库上一级 / MC_Startup」。
# existing 必须指向包含 .uproject 的工程根目录。
# 不带参数直接运行时，会打印本说明，按任意键退出。

import argparse
import json
import locale
import os
import re
import shutil
import subprocess
import sys
import traceback
import zipfile
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
STARTUP_DIR = PACKAGE_ROOT / 'MC_Startup'
STARTUP_PLUGIN = STARTUP_DIR / 'Plugins' / 'Mineprep'
MINEPREP_DIR = PACKAGE_ROOT / 'Mineprep'
EXP_DIR = PACKAGE_ROOT / '实验性功能(C++)' / 'Mineprep'
MATERIAL_DIR = PACKAGE_ROOT / '实验性功能(C++)' / 'InlineMaterialInstance'
VR3D_DIR = PACKAGE_ROOT / '实验性功能(C++)' / 'MoviePipelineMaskRenderPass'
RESOURCE_PACK = PACKAGE_ROOT / 'Blender扩展资源' / 'mc_default'
FFMPEG_ZIP = MINEPREP_DIR / 'Render' / 'ffmpeg.zip'
CORE_LIST = ('插件贴图', 'Render')
HOST = {'win32': 'Win64', 'darwin': 'Mac', 'linux': 'Linux'}.get(sys.platform)

_UE_INI_COMMANDS = '+-!.@*^'
_UE_INI_SECTION = re.compile(r'^\s*\[(.+)\]\s*$')
_UE_INI_KV = re.compile(rf'^(\s*)([{re.escape(_UE_INI_COMMANDS)}])?(.+?)(\s*=\s*)(.*)$')

TEXTS = {
    'zh_CN': {
        'empty': '安装路径为空',
        'no_uproject': '未找到 .uproject，请选择工程根目录',
        'non_ascii': '警告: 路径含非 ASCII 字符，部分功能可能失效',
        'done': '安装完成',
        'keep_pkg': '请勿移动或删除安装包，插件可能会引用其中资源',
        'upscale': '建议按需安装超分辨率插件（每个引擎版本装一次）:',
        'pause': '看完后按任意键退出。',
        'dry': '预演（不写盘）',
        'size': '估算体积',
        'merge_zip': '正在合并 ffmpeg 分卷…',
        'merged': 'ffmpeg 分卷合并完成',
    },
    'en_US': {
        'empty': 'Install path is empty',
        'no_uproject': '.uproject not found; pick the project root',
        'non_ascii': 'Warning: path contains non-ASCII characters; some features may break',
        'done': 'Installation completed',
        'keep_pkg': 'Do not move or delete the installer package; assets may be referenced.',
        'upscale': 'Optional upscaling plugins (install once per engine version):',
        'pause': 'Press any key to exit.',
        'dry': 'Dry run (no files written)',
        'size': 'Estimated size',
        'merge_zip': 'Merging ffmpeg zip parts…',
        'merged': 'ffmpeg zip merge finished',
    },
    'zh_TW': {
        'empty': '安裝路徑為空',
        'no_uproject': '未找到 .uproject，請選擇工程根目錄',
        'non_ascii': '警告: 路徑含非 ASCII 字元，部分功能可能失效',
        'done': '安裝完成',
        'keep_pkg': '請勿移動或刪除安裝包，插件可能會引用其中資源',
        'upscale': '建議按需安裝超解析度插件（每個引擎版本裝一次）:',
        'pause': '看完後按任意鍵結束。',
        'dry': '預演（不寫盤）',
        'size': '估算體積',
        'merge_zip': '正在合併 ffmpeg 分卷…',
        'merged': 'ffmpeg 分卷合併完成',
    },
}
TEXTS['zh_HANS'] = TEXTS['zh_CN']
TEXTS['zh_HANT'] = TEXTS['zh_TW']


class Options:
    def __init__(self):
        self.command = ''
        self.dest = ''
        self.name = 'MC_Startup'
        self.lite = 0
        self.crossplatform = False
        self.experimental = set()
        self.ffmpeg = ''
        self.gbuffer = 1
        self.preload = False
        self.optimize = False
        self.lang = 'en_US'
        self.dry_run = False
        self.open_project = False

    @property
    def lite_on(self):
        return self.lite >= 1

    @property
    def core_only(self):
        return self.lite >= 2

    @property
    def exp_cpp(self):
        return '1' in self.experimental

    @property
    def exp_material(self):
        return '2' in self.experimental

    @property
    def exp_vr3d(self):
        return '3' in self.experimental


def detect_lang():
    raw = (os.environ.get('LANG') or os.environ.get('LANGUAGE') or '')
    try:
        loc = locale.getlocale()[0] or ''
        raw = raw or loc
    except Exception:
        pass
    if not raw and sys.platform == 'win32':
        try:
            import ctypes
            langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            if (langid & 0xFF) == 0x04:
                return 'zh_TW' if langid in (0x0404, 0x0C04, 0x1404) else 'zh_CN'
        except Exception:
            pass
    raw = raw.replace('-', '_')
    low = raw.lower()
    if low.startswith('zh_cn') or low.startswith('zh_hans') or low == 'zh':
        return 'zh_CN'
    if low.startswith('zh_tw') or low.startswith('zh_hk') or low.startswith('zh_hant'):
        return 'zh_TW'
    return 'en_US'


def tr(opt, key):
    table = TEXTS.get(opt.lang) or TEXTS['en_US']
    return table.get(key) or TEXTS['en_US'][key]


def ffmpeg_bundled():
    if HOST == 'Win64':
        return MINEPREP_DIR / 'Render' / 'ffmpeg' / 'Win64' / 'ffmpeg.exe'
    if HOST == 'Mac':
        return MINEPREP_DIR / 'Render' / 'ffmpeg' / 'Mac' / 'ffmpeg'
    if HOST == 'Linux':
        return MINEPREP_DIR / 'Render' / 'ffmpeg' / 'Linux' / 'ffmpeg'
    return None


def parse_experimental(value):
    text = str(value or '0').strip()
    if text in ('', '0'):
        return set()
    digits = set(text)
    bad = digits - set('123')
    if bad:
        raise argparse.ArgumentTypeError('use digits 1, 2, 3 (e.g. 12 or 123)')
    return digits


def parse_lite(value):
    n = int(value)
    if n not in (1, 2):
        raise argparse.ArgumentTypeError('use 1 (lite) or 2 (core-only)')
    return n


def parse_gbuffer(value):
    n = int(value)
    if n not in (0, 1):
        raise argparse.ArgumentTypeError('use 0 (blendable) or 1 (adaptive)')
    return n


def usage_comment_block():
    lines = []
    for line in Path(__file__).read_text(encoding='utf-8').splitlines():
        if not line.startswith('#'):
            break
        lines.append(line[2:] if line.startswith('# ') else line[1:])
    return '\n'.join(lines).strip()


def ran_without_args(argv):
    return len(argv) < 2


def wait_any_key():
    try:
        if sys.platform == 'win32':
            import msvcrt
            msvcrt.getwch()
            return
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except Exception:
        try:
            input()
        except EOFError:
            pass


def pause_console(opt=None):
    if not sys.stdin.isatty():
        return
    msg = tr(opt, 'pause') if opt else TEXTS[detect_lang()]['pause']
    print()
    print(msg)
    wait_any_key()
    print()


def _ue_ini_map(sections):
    out = {}
    for section, opts in (sections or {}).items():
        bucket = out.setdefault(section.casefold(), {'name': section, 'keys': {}})
        items = opts.items() if isinstance(opts, dict) else ((key, None) for key in opts)
        for key, value in items:
            bucket['keys'][key.casefold()] = (key, value)
    return out


def patch_ue_ini_text(text, sets=None, removes=None):
    want, drop = _ue_ini_map(sets), _ue_ini_map(removes)
    nl = '\r\n' if '\r\n' in text else '\n'
    ended = text.endswith('\n') or text.endswith('\r\n')
    lines, out, i, seen = text.splitlines(), [], 0, set()

    def append_remaining(sec_cf):
        bucket = want.get(sec_cf)
        if not bucket:
            return
        for orig_key, value in bucket['keys'].values():
            if value is not None:
                out.append(f'{orig_key}={value}')
        bucket['keys'].clear()

    while i < len(lines):
        line = lines[i]
        header = _UE_INI_SECTION.match(line)
        if not header:
            out.append(line)
            i += 1
            continue
        name = header.group(1)
        sec_cf = name.casefold()
        seen.add(sec_cf)
        out.append(line)
        i += 1
        while i < len(lines) and not _UE_INI_SECTION.match(lines[i]):
            line = lines[i]
            parsed = None
            if line.strip() and not line.lstrip().startswith(';'):
                parsed = _UE_INI_KV.match(line)
            if parsed is None:
                out.append(line)
                i += 1
                continue
            indent, cmd, key, eq, value = parsed.groups()
            cmd, key = cmd or '', key.rstrip()
            key_cf = key.casefold()
            if key_cf in drop.get(sec_cf, {}).get('keys', {}):
                i += 1
                continue
            bucket = want.get(sec_cf)
            if bucket and not cmd and key_cf in bucket['keys']:
                _, new_value = bucket['keys'].pop(key_cf)
                out.append(f'{indent}{cmd}{key}{eq}{new_value}')
                i += 1
                continue
            out.append(line)
            i += 1
        append_remaining(sec_cf)

    missing = [want[k] for k in want if k not in seen and want[k]['keys']]
    if missing:
        if out and out[-1].strip():
            out.append('')
        for bucket in missing:
            out.append(f'[{bucket["name"]}]')
            append_remaining(bucket['name'].casefold())
    body = nl.join(out)
    if ended or text == '' or missing:
        return body + nl
    return body


def patch_ue_ini(path, sets=None, removes=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding='utf-8') if path.exists() else ''
    path.write_text(patch_ue_ini_text(text, sets, removes), encoding='utf-8')
    return path


def merge_ffmpeg_zip():
    part1 = Path(str(FFMPEG_ZIP) + '.001')
    if not part1.is_file() or FFMPEG_ZIP.is_file():
        return
    print(TEXTS[detect_lang()]['merge_zip'])
    with FFMPEG_ZIP.open('wb') as output:
        i = 1
        while True:
            part = Path(str(FFMPEG_ZIP) + f'.{i:03d}')
            if not part.is_file():
                break
            output.write(part.read_bytes())
            i += 1
    print(TEXTS[detect_lang()]['merged'])


def extract_ffmpeg_zip():
    extracted = FFMPEG_ZIP.with_suffix('')
    if extracted.exists() or not FFMPEG_ZIP.is_file():
        return
    with zipfile.ZipFile(FFMPEG_ZIP, 'r') as zf:
        zf.extractall(FFMPEG_ZIP.parent)


def skip_names(opt):
    skip = {'ffmpeg.zip.001', 'ffmpeg.zip.002'}
    if not opt.crossplatform and HOST:
        skip.update({'Win64', 'Mac', 'Linux'} - {HOST})
    if opt.lite_on:
        skip.update({'第三人称运动匹配', '音效', 'ffmpeg.zip', 'whisper', 'Source'})
    if HOST and HOST != 'Win64':
        skip.add('MC_物理交互绑定.uasset')
    return skip


def skip_bundled_ffmpeg(opt, path):
    bundled = ffmpeg_bundled()
    if not opt.ffmpeg or not bundled:
        return False
    return os.path.normcase(os.path.normpath(path)) == os.path.normcase(str(bundled))


def contains_core_folder(path):
    try:
        for entry in os.scandir(path):
            if entry.is_dir(follow_symlinks=False):
                if 'core' in entry.name.lower() or contains_core_folder(entry.path):
                    return True
    except (PermissionError, FileNotFoundError):
        pass
    return False


def mineprep_policy(path):
    rel = os.path.relpath(path, str(MINEPREP_DIR))
    if rel == '.':
        return 'root'
    parts = rel.split(os.sep)
    if parts[0] in CORE_LIST:
        return 'keep'
    if any('core' in part.lower() for part in parts):
        return 'keep'
    if contains_core_folder(path):
        return 'traverse'
    return 'skip'


def ignore_general(opt):
    skip = skip_names(opt)

    def _ignore(directory, contents):
        ignored = {item for item in contents if item in skip}
        for item in ignored:
            print(f'[skip] {os.path.join(directory, item)}')
        return ignored

    return _ignore


def ignore_mineprep(opt):
    base = ignore_general(opt)

    def _ignore(directory, contents):
        ignored = set(base(directory, contents))
        for item in contents:
            item_path = os.path.join(directory, item)
            if skip_bundled_ffmpeg(opt, item_path):
                ignored.add(item)
                print(f'[ffmpeg] {item_path}')
        if not opt.core_only:
            return ignored
        policy = mineprep_policy(directory)
        for item in contents:
            if item in ignored:
                continue
            item_path = os.path.join(directory, item)
            if policy == 'root':
                keep = os.path.isfile(item_path) or item in CORE_LIST
                if not keep and os.path.isdir(item_path):
                    keep = contains_core_folder(item_path)
            elif policy == 'keep':
                keep = True
            elif policy == 'traverse':
                keep = os.path.isdir(item_path) and mineprep_policy(item_path) != 'skip'
            else:
                keep = False
            if not keep:
                ignored.add(item)
                print(f'[core_only] {item_path}')
        return ignored

    return _ignore


def dir_size(path, skip):
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.name in skip:
                continue
            if entry.is_dir(follow_symlinks=False):
                total += dir_size(entry.path, skip)
            else:
                total += entry.stat(follow_symlinks=False).st_size
    except (PermissionError, FileNotFoundError):
        pass
    return total


def mineprep_dir_size(path, opt, skip):
    total = 0
    policy = mineprep_policy(path) if opt.core_only else 'keep'
    try:
        for entry in os.scandir(path):
            if entry.name in skip or skip_bundled_ffmpeg(opt, entry.path):
                continue
            if policy == 'root':
                keep = entry.is_file(follow_symlinks=False) or entry.name in CORE_LIST
                if not keep and entry.is_dir(follow_symlinks=False):
                    keep = contains_core_folder(entry.path)
                if not keep:
                    continue
            elif policy == 'traverse':
                if entry.is_file(follow_symlinks=False):
                    continue
                if mineprep_policy(entry.path) == 'skip':
                    continue
            if entry.is_dir(follow_symlinks=False):
                total += mineprep_dir_size(entry.path, opt, skip)
            else:
                total += entry.stat(follow_symlinks=False).st_size
    except (PermissionError, FileNotFoundError):
        pass
    return total


def format_size(total):
    if total >= 1024 ** 3:
        return f'{total / 1024 ** 3:.2f} GB'
    if total >= 1024 ** 2:
        return f'{total / 1024 ** 2:.0f} MB'
    return f'{total / 1024:.0f} KB'


def estimate_size(opt):
    skip = skip_names(opt)
    total = 0
    if opt.command == 'new':
        total += dir_size(str(STARTUP_DIR), skip)
    else:
        total += dir_size(str(STARTUP_PLUGIN), skip)
    total += mineprep_dir_size(str(MINEPREP_DIR), opt, skip)
    if opt.exp_cpp:
        total += dir_size(str(EXP_DIR), skip)
    else:
        total += dir_size(str(EXP_DIR / 'Content'), skip)
    if opt.exp_material:
        total += dir_size(str(MATERIAL_DIR), skip)
    if opt.exp_vr3d:
        total += dir_size(str(VR3D_DIR), skip)
    return format_size(total)


def has_uproject(folder):
    try:
        return any(name.endswith('.uproject') for name in os.listdir(folder))
    except OSError:
        return False


def first_uproject(folder):
    for name in os.listdir(folder):
        if name.endswith('.uproject'):
            return os.path.join(folder, name)
    return ''


def warn_non_ascii(opt, path):
    if not all(ord(ch) < 128 for ch in path):
        print(tr(opt, 'non_ascii'))


def write_plugin_config(opt, dest):
    config_path = Path(dest) / 'Content' / 'Mineprep' / 'Mineprep_config.txt'
    with config_path.open(encoding='utf-8') as fh:
        config = json.load(fh)
    settings = config.setdefault('Settings', {})
    settings['memory_preload'] = opt.preload
    settings['installer_dir'] = os.path.normpath(str(PACKAGE_ROOT))
    settings['blender_path'] = ''
    settings['texture_pack_path'] = os.path.normpath(str(RESOURCE_PACK))
    settings['init'] = 'true'
    settings['optimize_default'] = opt.optimize
    if opt.ffmpeg:
        settings['ffmpeg_path'] = os.path.normpath(opt.ffmpeg)
    with config_path.open('w', encoding='utf-8') as fh:
        json.dump(config, fh, ensure_ascii=False, indent=4)


def write_project_ini(opt, dest):
    cfg = Path(dest) / 'Config'
    bundled = ffmpeg_bundled()
    ffmpeg_path = opt.ffmpeg or (str(bundled) if bundled else '')
    executable = f'"{os.path.normpath(ffmpeg_path)}"' if ffmpeg_path else '""'
    patch_ue_ini(cfg / 'DefaultEngine.ini', {
        '/Script/MovieRenderPipelineCore.MoviePipelineCommandLineEncoderSettings': {
            'ExecutablePath': executable,
            'VideoCodec': 'libx265',
            'AudioCodec': 'aac',
            'OutputFileExtension': 'mp4',
            'CommandLineFormat': r'"-hide_banner -y -loglevel error {AdditionalLocalArgs}"',
        },
        '/Script/Engine.RendererSettings': {
            'r.DefaultFeature.AutoExposure': 'False',
            'r.RayTracing': 'True',
            'r.RayTracing.Shadows': 'True',
            'r.Lumen.HardwareRayTracing': 'True',
            'r.AllowStaticLighting': 'False',
            'r.CustomDepth': '3',
            'r.PostProcessing.PropagateAlpha': 'True',
            'r.Deferred.SupportPrimitiveAlphaHoldout': 'True',
            'r.SkinCache.SceneMemoryLimitInMB': '1024.0',
            'rhi.Bindless.Resources': 'Enabled',
            'rhi.Bindless.Samplers': 'Enabled',
            'rhi.Bindless': 'Enabled',
            'r.Translucency.HeterogeneousVolumes': 'True',
            'r.Substrate': 'True',
            'r.Substrate.ProjectGBufferFormat': '0' if opt.gbuffer == 0 else '1',
            'r.Substrate.OpaqueMaterialRoughRefraction': 'True',
            'r.GenerateMeshDistanceFields': 'True',
        },
        '/Script/Engine.GarbageCollectionSettings': {
            'gc.AssetClustreringEnabled': 'True',
            'gc.ActorClusteringEnabled': 'True',
        },
        '/Script/Engine.Engine': {
            'GenerateDefaultTimecodeFrameRate': '(Numerator=60,Denominator=1)',
        },
        '/Script/WaterAdvanced.ShallowWaterSettings': {
            'UseDefaultShallowWaterSubsystem': 'True',
            'ShallowWaterSimParameters': '(WorldGridSize=5000,ResolutionMaxAxis=768)',
        },
        '/Script/DLSS.DLSSSettings': {
            'bEnableDLSSInEditorViewports': 'True',
            'bEnableDLSSInPlayInEditorViewports': 'True',
        },
        '/Script/PythonScriptPlugin.PythonScriptPluginSettings': {
            'bRemoteExecution': 'True',
        },
    }, removes={
        '/Script/DLSS.DLSSSettings': ['bEnableDLSSInEditorViewport'],
    })
    patch_ue_ini(cfg / 'DefaultInput.ini', {
        '/Script/EnhancedInput.EnhancedInputDeveloperSettings': {
            'bEnableUserSettings': 'True',
        },
    })
    patch_ue_ini(cfg / 'DefaultEditor.ini', {
        '/Script/UnrealEd.BlueprintEditorProjectSettings': {
            'bAllowImpureToPureNodeConversion': 'True',
        },
    })
    patch_ue_ini(cfg / 'DefaultEditorSettings.ini', {
        '/Script/UnrealEd.EditorPerformanceSettings': {
            'bShowFrameRateAndMemory': 'True',
        },
    })
    patch_ue_ini(cfg / 'DefaultEditorPerProjectUserSettings.ini', {
        '/Script/UnrealEd.EditorLoadingSavingSettings': {
            'LoadLevelAtStartup': 'LastOpened',
        },
        '/Script/AvalancheEditor.AvaEditorSettings': {
            'bAutoActivateMotionDesignViewport': 'False',
        },
    })
    patch_ue_ini(cfg / 'Windows' / 'WindowsEngine.ini', {
        'ShaderPlatformConfig PCD3D_SM6': {
            'BindlessConfiguration': 'Minimal',
        },
    })


def chmod_ffmpeg(dest):
    exe_dir = Path(dest) / 'Content' / 'Mineprep' / 'Render' / 'ffmpeg'
    if HOST not in ('Mac', 'Linux') or not exe_dir.exists():
        return
    for root, _dirs, files in os.walk(exe_dir):
        for name in files:
            os.chmod(os.path.join(root, name), 0o777)


def open_project(dest):
    uproject = first_uproject(dest)
    if HOST == 'Win64' and uproject:
        os.startfile(uproject)
    elif HOST == 'Mac' and uproject:
        subprocess.Popen(['open', uproject])
    elif HOST == 'Linux':
        subprocess.Popen(['xdg-open', dest if not uproject else uproject])


def copytree(src, dst, ignore):
    shutil.copytree(str(src), str(dst), dirs_exist_ok=True, ignore=ignore)


def install(opt):
    dest = os.path.normpath(opt.dest)
    if not dest:
        raise FileNotFoundError(tr(opt, 'empty'))
    warn_non_ascii(opt, dest)
    if opt.command == 'existing' and not has_uproject(dest):
        raise FileNotFoundError(tr(opt, 'no_uproject'))

    merge_ffmpeg_zip()
    extract_ffmpeg_zip()

    os.makedirs(dest, exist_ok=True)
    general = ignore_general(opt)
    if opt.command == 'new':
        for item in os.listdir(STARTUP_DIR):
            src = STARTUP_DIR / item
            target = Path(dest) / item
            if src.is_dir():
                copytree(src, target, general)
            elif src.is_file():
                shutil.copy2(src, target)
        if opt.name and opt.name != 'MC_Startup':
            for file in os.listdir(dest):
                if file.endswith('.uproject'):
                    os.rename(os.path.join(dest, file), os.path.join(dest, f'{opt.name}.uproject'))
                    break
    else:
        copytree(STARTUP_PLUGIN, Path(dest) / 'Plugins' / 'Mineprep', general)

    copytree(MINEPREP_DIR, Path(dest) / 'Content' / 'Mineprep', ignore_mineprep(opt))
    chmod_ffmpeg(dest)

    if opt.exp_cpp:
        copytree(EXP_DIR, Path(dest) / 'Plugins' / 'Mineprep', general)
    else:
        copytree(EXP_DIR / 'Content', Path(dest) / 'Plugins' / 'Mineprep' / 'Content', general)
    if opt.exp_material:
        copytree(MATERIAL_DIR, Path(dest) / 'Plugins' / 'InlineMaterialInstance', general)
    if opt.exp_vr3d:
        copytree(VR3D_DIR, Path(dest) / 'Plugins' / 'MoviePipelineMaskRenderPass', general)

    write_plugin_config(opt, dest)
    write_project_ini(opt, dest)
    print(tr(opt, 'done'))
    print(tr(opt, 'keep_pkg'))
    print(tr(opt, 'upscale'))
    print('  DLSS  https://developer.nvidia.com/rtx/dlss#getstarted')
    print('  FSR   https://gpuopen.com/learn/ue-fsr/')
    print('  XeSS  https://github.com/GameTechDev/XeSSUnrealPlugin/releases')
    if opt.open_project:
        open_project(dest)


def print_plan(opt):
    print(tr(opt, 'dry'))
    print(f'  command       {opt.command}')
    print(f'  dest          {opt.dest}')
    if opt.command == 'new':
        print(f'  name          {opt.name}')
    print(f'  lite          {opt.lite or 0}')
    print(f'  crossplatform {opt.crossplatform}')
    print(f'  experimental  {"".join(sorted(opt.experimental)) or 0}')
    print(f'  gbuffer       {opt.gbuffer}')
    print(f'  preload       {opt.preload}')
    print(f'  optimize      {opt.optimize}')
    print(f'  ffmpeg        {opt.ffmpeg or ffmpeg_bundled()}')
    print(f'  {tr(opt, "size")}: {estimate_size(opt)}')


def add_shared_flags(parser):
    parser.add_argument('--lite', type=parse_lite, metavar='1|2',
                        help='1=lite, 2=core-only')
    parser.add_argument('--crossplatform', action='store_true',
                        help='copy Win64/Mac/Linux binaries')
    parser.add_argument('--experimental', type=parse_experimental, default='0',
                        metavar='DIGITS', help='1=C++ 2=material 3=VR, e.g. 123 (default off)')
    parser.add_argument('--ffmpeg', default='', metavar='EXE',
                        help='external ffmpeg executable')
    parser.add_argument('--gbuffer', type=parse_gbuffer, default=1, metavar='0|1',
                        help='0=blendable, 1=adaptive (default 1)')
    parser.add_argument('--preload', action='store_true', help='enable memory preload')
    parser.add_argument('--optimize', action='store_true', help='lower default quality')
    parser.add_argument('--lang', choices=('zh_CN', 'en_US', 'zh_TW'), default='',
                        help='UI language')
    parser.add_argument('--dry-run', action='store_true', dest='dry_run',
                        help='print plan only')
    parser.add_argument('--open', action='store_true', dest='open_project',
                        help='open .uproject when done')


def build_parser():
    parser = argparse.ArgumentParser(
        prog='Mineprep_installer.py',
        description='Mineprep command-line installer (no Blender).',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=usage_comment_block(),
    )
    sub = parser.add_subparsers(dest='command')

    p_new = sub.add_parser('new', help='create a new UE project')
    p_new.add_argument('dest', nargs='?', default='', help='project directory')
    p_new.add_argument('--name', default='MC_Startup', help='.uproject name')
    add_shared_flags(p_new)

    p_old = sub.add_parser('existing', help='install into an existing project')
    p_old.add_argument('dest', help='project root that contains .uproject')
    add_shared_flags(p_old)
    return parser


def options_from_args(args):
    opt = Options()
    opt.command = args.command
    opt.dest = os.path.abspath(args.dest) if args.dest else ''
    opt.name = getattr(args, 'name', 'MC_Startup')
    opt.crossplatform = args.crossplatform
    raw_exp = args.experimental
    opt.experimental = raw_exp if isinstance(raw_exp, set) else parse_experimental(raw_exp)
    opt.ffmpeg = args.ffmpeg or ''
    opt.gbuffer = args.gbuffer
    opt.preload = args.preload
    opt.optimize = args.optimize
    opt.lang = args.lang or detect_lang()
    opt.dry_run = args.dry_run
    opt.open_project = args.open_project
    if args.lite:
        opt.lite = args.lite
    elif 'Lite' in PACKAGE_ROOT.name:
        opt.lite = 1
    if opt.command == 'new' and not opt.dest:
        opt.dest = str((PACKAGE_ROOT.parent / 'MC_Startup').resolve())
    return opt


def run(argv):
    parser = build_parser()
    if ran_without_args(argv):
        print(usage_comment_block())
        return 0
    args = parser.parse_args(argv[1:])
    if not args.command:
        parser.print_help()
        return 2
    opt = options_from_args(args)
    if opt.dry_run:
        print_plan(opt)
        return 0
    install(opt)
    return 0


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    argv = sys.argv
    pause = ran_without_args(argv)
    code = 1
    try:
        code = run(argv)
    except Exception:
        traceback.print_exc()
        code = 1
    if pause:
        opt = Options()
        opt.lang = detect_lang()
        pause_console(opt)
    sys.exit(code)


if __name__ == '__main__':
    main()
