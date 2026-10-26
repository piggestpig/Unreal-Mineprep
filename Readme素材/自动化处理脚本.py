import json
import shutil
import sys
from pathlib import Path

#查找或创建文件
def find_or_create(file_path):
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path

self_dir = Path(__file__).resolve().parent
plugin_dir = self_dir.parent

uplugin_src = plugin_dir / "实验性功能(C++)" / "Mineprep" / "Mineprep.uplugin"
uplugin_dst = plugin_dir / "MC_Startup" / "Plugins" / "Mineprep" / "Mineprep.uplugin"

with open(uplugin_src, "r", encoding="utf-8") as f:
    src_obj = json.load(f)

plugins = src_obj.get("Plugins")
if uplugin_dst.exists():
    with open(uplugin_dst, "r", encoding="utf-8") as f:
        dst_obj = json.load(f)

if dst_obj["Plugins"] != plugins:
    dst_obj["Plugins"] = plugins
    with open(uplugin_dst, "w", encoding="utf-8") as f:
        json.dump(dst_obj, f, ensure_ascii=False, indent=4)
    print("已将 'Plugins' 从源复制到目标：", uplugin_dst)

############################################################

ffmpeg_dir = plugin_dir / "Mineprep" / "Render" / "ffmpeg"
if ffmpeg_dir.exists():
    shutil.rmtree(ffmpeg_dir)
    print("已删除 ffmpeg 文件夹：", ffmpeg_dir)

ffmpeg_zip = plugin_dir / "Mineprep" / "Render" / "ffmpeg.zip"
if ffmpeg_zip.exists():
    ffmpeg_zip.unlink()
    print("已删除 ffmpeg.zip：", ffmpeg_zip)

ffmpeg_multipart = plugin_dir / "Mineprep" / "Render" / "ffmpeg.zip.001"
assert ffmpeg_multipart.exists(), "ffmpeg.zip.001 分卷压缩文件不存在"

############################################################

#搜索plugin_dir下所有.pdb文件，打印并删除
for pdb_path in plugin_dir.rglob("*.pdb"):
    pdb_path.unlink()
    print("已删除 .pdb 文件：", pdb_path)

#删除 Linux 编译产生的调试和符号文件
for debug_path in plugin_dir.rglob("*.debug"):
    debug_path.unlink()
    print("已删除 .debug 文件：", debug_path)

for sym_path in plugin_dir.rglob("*.sym"):
    sym_path.unlink()
    print("已删除 .sym 文件：", sym_path)

#删除所有.patch_*.exe .patch_*.exp .patch_*.lib，*为数字
for patch_path in plugin_dir.rglob("*.patch_*.exe"):
    patch_path.unlink()
    print("已删除 .patch_*.exe 文件：", patch_path)

for patch_path in plugin_dir.rglob("*.patch_*.exp"):
    patch_path.unlink()
    print("已删除 .patch_*.exp 文件：", patch_path)

for patch_path in plugin_dir.rglob("*.patch_*.lib"):
    patch_path.unlink()
    print("已删除 .patch_*.lib 文件：", patch_path)

#删除所有Intermediate文件夹
for intermediate_dir in plugin_dir.rglob("Intermediate"):
    if intermediate_dir.is_dir():
        shutil.rmtree(intermediate_dir)
        print("已删除 Intermediate 文件夹：", intermediate_dir)

#删除__pycache__文件夹
for pycache_dir in plugin_dir.rglob("__pycache__"):
    if pycache_dir.is_dir():
        shutil.rmtree(pycache_dir)
        print("已删除 __pycache__ 文件夹：", pycache_dir)

#删除cache文件夹
for cache_dir in plugin_dir.rglob("cache"):
    if cache_dir.is_dir():
        shutil.rmtree(cache_dir)
        print("已删除 cache 文件夹：", cache_dir)

#删除.vscode文件夹
for vscode_dir in plugin_dir.rglob(".vscode"):
    if vscode_dir.is_dir():
        shutil.rmtree(vscode_dir)
        print("已删除 .vscode 文件夹：", vscode_dir)

def remove_empty_dirs(root):
    """删除不含任何文件的文件夹，并删除子目录中的 .git。保留 root 自己的 .git。"""
    root_git = root / ".git"
    nested_gits = [p for p in root.rglob(".git") if p.is_dir() and p != root_git]
    for path in sorted(nested_gits, key=lambda p: len(p.parts)):
        if path.is_dir():
            shutil.rmtree(path)
            print("已删除子目录 .git：", path)
    dirs = [p for p in root.rglob("*") if p.is_dir() and p != root_git and root_git not in p.parents]
    for path in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
            print("已删除空文件夹：", path)

remove_empty_dirs(plugin_dir)

#############################################################
# 创建 Mineprep-Lite

LITE_SKIP_NAMES = {"Mover", "音效", "whisper", "Source", "ffmpeg"}

def lite_ignore(src, names):
    ignored = {n for n in names if n in LITE_SKIP_NAMES}
    for n in ignored:
        print(f"[lite] 跳过: {src}\\{n}")
    return ignored

def files_under(root):
    if not root.exists():
        return set()
    return {p.relative_to(root).as_posix() for p in root.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(root).parts}

def print_lite_extras():
    """打印精简版里有、完整包对应位置已经没有的文件。"""
    pairs = [
        (plugin_dir / "Mineprep", lite_dir / "Mineprep"),
        (plugin_dir / "MC_Startup", lite_dir / "MC_Startup"),
        (plugin_dir / "实验性功能(C++)", lite_dir / "实验性功能(C++)"),
        (plugin_dir / "Blender扩展资源" / "mc_default", lite_dir / "Blender扩展资源" / "mc_default"),
        (self_dir / "ResourceLicenses", lite_dir / "Readme素材" / "ResourceLicenses"),
    ]
    extras = []
    for src, dst in pairs:
        extras.extend(dst / rel for rel in sorted(files_under(dst) - files_under(src)))
    print(f"Lite 多余文件：{len(extras)}")
    for path in extras:
        print(" ", path)

lite_dir = plugin_dir.parent / "Mineprep-Lite"
lite_dir.mkdir(exist_ok=True)

copy_targets = ["Mineprep", "MC_Startup", "实验性功能(C++)"]
for target in copy_targets:
    src = plugin_dir / target
    dst = lite_dir / target
    if src.exists():
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=lite_ignore)
        print(f"已复制: {src} -> {dst}")
    else:
        print(f"跳过（不存在）: {src}")

installer_blend = plugin_dir / "Mineprep_installer.blend"
if installer_blend.exists():
    dst_blend = lite_dir / "Mineprep_Lite_installer.blend"
    dst_blend.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(installer_blend, dst_blend)
    print(f"已复制: {installer_blend} -> {dst_blend}")
else:
    print(f"跳过（不存在）: {installer_blend}")

installer_py = plugin_dir / "Mineprep_installer.py"
if installer_py.exists():
    dst_py = lite_dir / "Mineprep_Lite_installer.py"
    dst_py.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(installer_py, dst_py)
    print(f"已复制: {installer_py} -> {dst_py}")
else:
    print(f"跳过（不存在）: {installer_py}")

mc_default_src = plugin_dir / "Blender扩展资源" / "mc_default"
mc_default_dst = lite_dir / "Blender扩展资源" / "mc_default"
if mc_default_src.exists():
    shutil.copytree(mc_default_src, mc_default_dst, dirs_exist_ok=True)
    print(f"已复制: {mc_default_src} -> {mc_default_dst}")
else:
    print(f"跳过（不存在）: {mc_default_src}")

licenses_src = self_dir / "ResourceLicenses"
licenses_dst = lite_dir / "Readme素材" / "ResourceLicenses"
if licenses_src.exists():
    shutil.copytree(licenses_src, licenses_dst, dirs_exist_ok=True)
    print(f"已复制: {licenses_src} -> {licenses_dst}")
else:
    print(f"跳过（不存在）: {licenses_src}")

lite_ffmpeg_dir = lite_dir / "Mineprep" / "Render" / "ffmpeg"
if lite_ffmpeg_dir.exists():
    shutil.rmtree(lite_ffmpeg_dir)
    print("已删除 ffmpeg 文件夹：", lite_ffmpeg_dir)

lite_ffmpeg_zip = lite_dir / "Mineprep" / "Render" / "ffmpeg.zip"
if lite_ffmpeg_zip.exists():
    lite_ffmpeg_zip.unlink()
    print("已删除 ffmpeg.zip：", lite_ffmpeg_zip)

remove_empty_dirs(lite_dir)
print_lite_extras()

print("Mineprep-Lite 创建完成：", lite_dir)




