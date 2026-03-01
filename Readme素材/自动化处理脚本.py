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

for modules_path in plugin_dir.rglob("*.modules"):
    modules_path.unlink()
    print("已删除 .modules 文件：", modules_path)

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

#############################################################
# 创建 Mineprep-Lite

LITE_SKIP_NAMES = {"第三人称运动匹配", "音效", "whisper", "Source", "ffmpeg"}

def lite_ignore(src, names):
    ignored = {n for n in names if n in LITE_SKIP_NAMES}
    for n in ignored:
        print(f"[lite] 跳过: {src}\\{n}")
    return ignored

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

mc_default_src = plugin_dir / "Blender扩展资源" / "mc_default"
mc_default_dst = lite_dir / "Blender扩展资源" / "mc_default"
if mc_default_src.exists():
    shutil.copytree(mc_default_src, mc_default_dst, dirs_exist_ok=True)
    print(f"已复制: {mc_default_src} -> {mc_default_dst}")
else:
    print(f"跳过（不存在）: {mc_default_src}")

lite_ffmpeg_dir = lite_dir / "Mineprep" / "Render" / "ffmpeg"
if lite_ffmpeg_dir.exists():
    shutil.rmtree(lite_ffmpeg_dir)
    print("已删除 ffmpeg 文件夹：", lite_ffmpeg_dir)

lite_ffmpeg_zip = lite_dir / "Mineprep" / "Render" / "ffmpeg.zip"
if lite_ffmpeg_zip.exists():
    lite_ffmpeg_zip.unlink()
    print("已删除 ffmpeg.zip：", lite_ffmpeg_zip)

print("Mineprep-Lite 创建完成：", lite_dir)




