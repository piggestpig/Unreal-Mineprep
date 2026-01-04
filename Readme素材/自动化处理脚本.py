import json
import shutil
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

with open(uplugin_src, "r", encoding="utf-16") as f:
    src_obj = json.load(f)

plugins = src_obj.get("Plugins")
if uplugin_dst.exists():
    with open(uplugin_dst, "r", encoding="utf-16") as f:
        dst_obj = json.load(f)

if dst_obj["Plugins"] != plugins:
    dst_obj["Plugins"] = plugins
    with open(uplugin_dst, "w", encoding="utf-16") as f:
        json.dump(dst_obj, f, ensure_ascii=False, indent=4)
    print("已将 'Plugins' 从源复制到目标：", uplugin_dst)

############################################################

ffmpeg_dir = plugin_dir / "Mineprep" / "Render" / "ffmpeg"
if ffmpeg_dir.exists():
    shutil.rmtree(ffmpeg_dir)
    print("已删除 ffmpeg 文件夹：", ffmpeg_dir)

############################################################

#搜索plugin_dir下所有.pdb文件，打印并删除
for pdb_path in plugin_dir.rglob("*.pdb"):
    pdb_path.unlink()
    print("已删除 .pdb 文件：", pdb_path)

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



