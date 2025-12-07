import json
import shutil
import os
import sys

self_dir = os.path.dirname(os.path.abspath(__file__))
plugin_dir = os.path.dirname(self_dir)

uplugin_src = os.path.join(plugin_dir, "实验性功能(C++)", "Mineprep", "Mineprep.uplugin")
uplugin_dst = os.path.join(plugin_dir, "MC_Startup", "Plugins", "Mineprep", "Mineprep.uplugin")

with open(uplugin_src, "r", encoding="utf-16") as f:
    src_obj = json.load(f)

plugins = src_obj.get("Plugins")
if os.path.exists(uplugin_dst):
    with open(uplugin_dst, "r", encoding="utf-16") as f:
        dst_obj = json.load(f)

if dst_obj["Plugins"] != plugins:
    dst_obj["Plugins"] = plugins
    with open(uplugin_dst, "w", encoding="utf-16") as f:
        json.dump(dst_obj, f, ensure_ascii=False, indent=4)
    print("已将 'Plugins' 从源复制到目标：", uplugin_dst)

############################################################

ffmpeg_dir = os.path.join(plugin_dir, "Mineprep", "Render", "ffmpeg")
if os.path.exists(ffmpeg_dir):
    shutil.rmtree(ffmpeg_dir)
    print("已删除 ffmpeg 文件夹：", ffmpeg_dir)