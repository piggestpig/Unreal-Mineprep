# 点击上方的 ▶️ 按钮开始安装
# Click the ▶️ button above to start installation

把等号右边的数改为1可以强制显示简体中文 = 0

import bpy
import os
from os.path import join
import re
import shutil
import zipfile
import configparser
import json
import subprocess
from sys import platform
from pathlib import Path

class MineprepProperties(bpy.types.PropertyGroup):
    install_path: bpy.props.StringProperty(subtype='DIR_PATH')
    ffmpeg_path: bpy.props.StringProperty(subtype='FILE_PATH')
    page: bpy.props.IntProperty()
    exp_basic: bpy.props.BoolProperty(default=True)
    exp_material: bpy.props.BoolProperty(default=True)
    exp_vr3d: bpy.props.BoolProperty()
    exp_template_seq: bpy.props.BoolProperty()
    ini_ffmpeg: bpy.props.BoolProperty()
    ini_memory: bpy.props.BoolProperty(default=True)
    install_mode: bpy.props.IntProperty()
    lite_version: bpy.props.BoolProperty()
    skip_other_platform: bpy.props.BoolProperty(default=True)

bpy.utils.register_class(MineprepProperties)
bpy.types.Scene.mineprep = bpy.props.PointerProperty(type=MineprepProperties)

mc = bpy.context.scene.mineprep
lang = bpy.context.preferences.view.language
system = {'win32': 'Win64', 'win64': 'Win64', 'darwin': 'Mac', 'linux': 'Linux'}.get(platform)
lite_only = "Lite" in bpy.path.basename(bpy.data.filepath)

file_dir = os.path.dirname(bpy.data.filepath)
outer_dir = os.path.dirname(file_dir)
ffmpeg_zipfile = join(file_dir, 'Mineprep', 'Render', 'ffmpeg.zip')
ffmpeg_default = {'Win64': join(file_dir, 'Mineprep', 'Render', 'ffmpeg', 'Win64', 'ffmpeg.exe'),
                  'Mac': join(file_dir, 'Mineprep', 'Render', 'ffmpeg', 'Mac', 'ffmpeg'),
                  'Linux': join(file_dir, 'Mineprep', 'Render', 'ffmpeg', 'Linux', 'ffmpeg')}.get(system)
startup_dir = join(file_dir, 'MC_Startup')
startup_plugin = join(file_dir, 'MC_Startup', 'Plugins', 'Mineprep')
mineprep_dir = join(file_dir, 'Mineprep')
exp_dir = join(file_dir, '实验性功能(C++)', 'Mineprep')
material_dir = join(file_dir, '实验性功能(C++)', 'InlineMaterialInstance')
vr3d_dir = join(file_dir, '实验性功能(C++)', 'MoviePipelineMaskRenderPass')
template_sequence_dir = join(file_dir, '实验性功能(C++)', 'TemplateSequence')
blender_path = bpy.app.binary_path
resource_pack_path = join(file_dir, 'Blender扩展资源', 'mc_default')

localization = {
    'zh_CN': {
        1: "\n\n⚠ ⚠ ⚠ ⚠ ⚠\n\n安装路径为空！\n\n⚠ ⚠ ⚠ ⚠ ⚠",
        2: "---Mineprep v0.5 安装向导---".replace("Mineprep", "Mineprep Lite" if lite_only else "Mineprep"),
        3: "欢迎使用Mineprep！",
        4: "· 实验性功能适用于 Windows + UE5.7",
        5: "· 非实验性功能也许能兼容Mac和高版本UE",
        6: "· 重复安装会直接覆盖原文件",
        7: "· 安装前建议关闭虚幻引擎",
        8: "请点击下方按钮选择安装模式，并根据提示执行操作",
        9: "新建UE工程文件",
        10: "安装至现有工程",
        11: "选择安装路径",
        12: "警告: 文件夹路径包含中文或非ASCII字符！可能会导致部分功能失效",
        13: "实验性功能 (仅支持Windows+UE5.7):",
        14: "Mineprep C++ 拓展模块",
        15: "解锁双目立体全景渲染",
        16: "扩展模板序列以支持双精度浮点和向量属性乘数",
        17: "插件设置:",
        18: "手动指定FFmpeg路径 (如ffmpeg.exe)",
        19: "路径",
        20: "内存预加载",
        21: "     · 启动时在后台异步加载所有资源，减少运行时卡顿",
        22: "选择工程目录 (包含.uproject的文件夹)",
        23: "警告: 未找到.uproject文件！请确认当前文件夹为UE工程根目录",
        24: "安装完成！",
        25: "Mineprep已经可以使用了",
        26: "打开工程文件",
        27: "另外，我们推荐您安装超分辨率插件",
        28: "它可以提升画质和帧率，甚至节约显存",
        29: "您需要手动下载安装，一个虚幻引擎版本只需要安装一次：",
        30: "不建议移动或删除安装包，插件可能会引用其中资源",
        31: "为材质参数面板添加关键帧按钮和本地化翻译",
        32: "安装精简版 (无源代码/运动匹配/音效/不常用功能)",
        33: "当前所需空间：",
        34: "跳过为其他平台编译的文件"
    },
    'en_US': {
        1: "\n\n⚠ ⚠ ⚠ ⚠ ⚠\n\nInstall path is empty!\n\n⚠ ⚠ ⚠ ⚠ ⚠",
        2: "---Mineprep v0.5 Installer---".replace("Mineprep", "Mineprep Lite" if lite_only else "Mineprep"),
        3: "Welcome to Mineprep!",
        4: "· The experimental features are designed for Windows + UE5.7",
        5: "· Non-experimental features may be compatible with Mac and higher engine version",
        6: "· Reinstalling will overwrite the original files",
        7: "· It is recommended to close Unreal Engine before installation",
        8: "Click one button below to select an installation mode",
        9: "Create a new UE project",
        10: "Install to an existing project",
        11: "Installation directory",
        12: "The path contains non-ASCII characters! Some functions may be broken",
        13: "Experimental features (only for Windows+UE5.7):",
        14: "Mineprep C++ extensions",
        15: "Unlock VR stereoscopic rendering",
        16: "Extend Template Sequence with float64 & vector property multiplier",
        17: "Plugin settings:",
        18: "Manually specify FFmpeg path (such as ffmpeg.exe)",
        19: "Path",
        20: "Memory preload",
        21: "     · Async load all assets at start, reducing runtime stut",
        22: "Select project directory (folder containing .uproject)",
        23: ".uproject file not found! Please make sure it's the correct directory",
        24: "Installation completed!",
        25: "Mineprep is ready to use",
        26: "Open project file",
        27: "By the way, we recommend installing upscaling plugins",
        28: "It can improve image quality and frame rate, even saving VRAM",
        29: "You need to download it manually, only once for each UE version:",
        30: "You may not move or delete the installer, resources may be referenced.",
        31: "Add keyframe buttons and localization for material parameter panel",
        32: "Lite version (No source code / motion matching / sound / rare assets)",
        33: "Estimated size: ",
        34: "Skip files compiled for other platforms"
    },
    'zh_TW': {
        1: "\n\n⚠ ⚠ ⚠ ⚠ ⚠\n\n安裝路徑為空！\n\n⚠ ⚠ ⚠ ⚠ ⚠",
        2: "---Mineprep v0.5 安裝嚮導---".replace("Mineprep", "Mineprep Lite" if lite_only else "Mineprep"),
        3: "歡迎使用Mineprep！",
        4: "· 實驗性功能適用於 Windows + UE5.7",
        5: "· 非實驗性功能也許能兼容Mac和高版本UE",
        6: "· 重複安裝會直接覆蓋原文件",
        7: "· 安裝前建議關閉虛幻引擎",
        8: "請點擊下方按鈕選擇安裝模式，並根據提示執行操作",
        9: "新建UE工程文件",
        10: "安裝至現有工程",
        11: "選擇安裝路徑",
        12: "警告: 文件夾路徑包含中文或非ASCII字符！可能會導致部分功能失效",
        13: "實驗性功能 (僅支持Windows+UE5.7):",
        14: "Mineprep C++ 擴展模組",
        15: "解鎖雙目立體全景渲染",
        16: "擴展模板序列以支援雙精度浮點與向量屬性乘數",
        17: "插件設置:",
        18: "手動指定FFmpeg路徑 (如ffmpeg.exe)",
        19: "路徑",
        20: "內存預加載",
        21: "     · 啓動時在後臺異步加載所有資源，減少運行時卡頓",
        22: "選擇工程目錄 (包含.uproject的文件夾)",
        23: "警告: 未找到.uproject文件！請確認當前文件夾為UE工程根目錄",
        24: "安裝完成！",
        25: "Mineprep已經可以使用了",
        26: "打開工程文件",
        27: "另外，我們推薦您安裝超分辨率插件",
        28: "它可以提升畫質和幀率，甚至節約顯存",
        29: "您需要手動下載安裝，一個虛幻引擎版本只需要安裝一次：",
        30: "不建議移動或刪除安裝包，插件可能會引用其中資源",
        31: "為材質參數面板添加關鍵幀按鈕和本地化翻譯",
        32: "安裝精簡版 (無源代碼/運動匹配/音效/不常用功能)",
        33: "當前所需空間：",
        34: "跳過為其他平台編譯的文件"
    },
}

localization['zh_HANS'] = localization['zh_CN']
localization['zh_HANT'] = localization['zh_TW']

def loc(index=0, preview="-------本地化文本-------"):
    if 把等号右边的数改为1可以强制显示简体中文 and index in localization['zh_CN'] :
        return localization['zh_CN'][index]
    elif lang in localization and index in localization[lang]:
        return localization[lang][index]
    elif index in localization['en_US'] :
        return localization['en_US'][index]
    else:
        return preview

def gather_loctext():
    matches_array = []
    for text in bpy.data.texts:
        pattern = r'loc\((\d+)\s*,\s*"([^"]*)"'
        matches = re.finditer(pattern, text.as_string())
        for i in matches:
            matches_array.append(f"{i.group(1)}: \"{i.group(2)}\"")
    
    text_nums = {}
    for item in matches_array:
        num, text = item.split(':', 1)
        if text not in text_nums:
            text_nums[text] = set()
        text_nums[text].add(num.strip())
    
    # 重复编号
    result = []
    for item in sorted(matches_array, key=lambda x: int(x.split(':')[0])):
        num, text = item.split(':', 1)
        nums = text_nums[text]
        if len(nums) > 1:
            other_nums = sorted([n for n in nums if n != num.strip()])
            item = f"{item.rstrip()} 【{','.join(other_nums)}】"
        result.append(item)
    
    return ',\n'.join(result) + '\n'

print(f"\n{lang}\n{gather_loctext()}\n")

#############################################################################

#查找或创建文件
def find_or_create(file_path):
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path

def get_abs_path(path):
    #转换为绝对路径，同时处理Windows路径分隔符
    if path.startswith("//"):
        abs_path = bpy.path.abspath(path)
    else:
        abs_path = path
    return os.path.normpath(abs_path)

def extract_zip(zip_path, extract_to):
    # 检查是否已解压（去掉.zip后缀的路径）
    if os.path.exists(zip_path.replace('.zip', '')):
        return
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

def get_lite_skip():
    skip = {"ffmpeg.zip.001", "ffmpeg.zip.002"}
    if mc.skip_other_platform:
        all_platforms = {'Win64', 'Mac', 'Linux'}
        if system:
            skip.update(all_platforms - {system})
    if mc.lite_version:
        skip.update({"第三人称运动匹配", "音效", "ffmpeg.zip", "whisper", "Source"})
    return skip

def get_dir_size(path, skip):
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.name in skip:
                print(f"[lite] 跳过: {entry.path}")
                continue
            if entry.is_dir(follow_symlinks=False):
                total += get_dir_size(entry.path, skip)
            else:
                total += entry.stat(follow_symlinks=False).st_size
    except (PermissionError, FileNotFoundError):
        pass
    return total

_size_cache = {}

def est_size():
    cache_key = (mc.lite_version, mc.skip_other_platform, mc.install_mode, mc.exp_basic, mc.exp_material, mc.exp_vr3d, mc.exp_template_seq)
    if cache_key in _size_cache:
        return _size_cache[cache_key]

    skip = get_lite_skip()
    total = 0
    if mc.install_mode == 1:
        total += get_dir_size(startup_dir, skip)
    else:
        total += get_dir_size(startup_plugin, skip)
    total += get_dir_size(mineprep_dir, skip)
    if mc.exp_basic:
        total += get_dir_size(exp_dir, skip)
    if mc.exp_material:
        total += get_dir_size(material_dir, skip)
    if mc.exp_vr3d:
        total += get_dir_size(vr3d_dir, skip)
    if mc.exp_template_seq:
        total += get_dir_size(template_sequence_dir, skip)

    if total >= 1024 ** 3:
        result = f"{total / 1024 ** 3:.2f} GB"
    elif total >= 1024 ** 2:
        result = f"{total / 1024 ** 2:.0f} MB"
    else:
        result = f"{total / 1024:.0f} KB"

    _size_cache[cache_key] = result
    return result

def lite_ignore(dir, contents):
    skip = get_lite_skip()
    ignored = {item for item in contents if item in skip}
    for item in ignored:
        print(f"[lite] 跳过: {os.path.join(dir, item)}")
    return ignored

###############################################################################

def install():
    install_path = get_abs_path(mc.install_path)
    if mc.install_path == "":
        raise FileNotFoundError(loc(1, "⚠ ⚠ ⚠ ⚠ ⚠\n\n安装路径为空！\n\n⚠ ⚠ ⚠ ⚠ ⚠"))
    if not os.path.exists(install_path):
        os.makedirs(install_path)
    
    #创建工程
    if mc.install_mode == 1:
        for item in os.listdir(startup_dir):
            files = join(startup_dir, item)
            if os.path.isdir(files):
                shutil.copytree(files, join(install_path, item), dirs_exist_ok=True, ignore=lite_ignore)
            elif os.path.isfile(files):
                shutil.copy(files, join(install_path, item))
    elif mc.install_mode == 2:
        shutil.copytree(startup_plugin, join(install_path, 'Plugins', 'Mineprep'), dirs_exist_ok=True, ignore=lite_ignore)

    shutil.copytree(mineprep_dir, join(install_path, 'Content', 'Mineprep'), dirs_exist_ok=True, ignore=lite_ignore)
    #实验性功能
    if mc.exp_basic:
        shutil.copytree(exp_dir, join(install_path, 'Plugins', 'Mineprep'), dirs_exist_ok=True, ignore=lite_ignore)
    if mc.exp_material:
        shutil.copytree(material_dir, join(install_path, 'Plugins', 'InlineMaterialInstance'), dirs_exist_ok=True, ignore=lite_ignore)
    if mc.exp_vr3d:
        shutil.copytree(vr3d_dir, join(install_path, 'Plugins', 'MoviePipelineMaskRenderPass'), dirs_exist_ok=True, ignore=lite_ignore)
    if mc.exp_template_seq:
        shutil.copytree(template_sequence_dir, join(install_path, 'Plugins', 'TemplateSequence'), dirs_exist_ok=True, ignore=lite_ignore)
    
    #修改插件配置文件
    mineprep_ini = join(install_path, 'Content', 'Mineprep', 'Mineprep_config.txt')
    with open(mineprep_ini, 'r', encoding='utf-8') as file:
        config = json.load(file)
    
    config['Settings']['memory_preload'] = mc.ini_memory
    config['Settings']['installer_dir'] = file_dir.replace("\\\\", "\\").replace("/", "\\")
    config['Settings']['blender_path'] = blender_path.replace("\\\\", "\\").replace("/", "\\")
    config['Settings']['texture_pack_path'] = resource_pack_path.replace("\\\\", "\\").replace("/", "\\")
    config['Settings']['init'] = "true"
    if mc.ini_ffmpeg:
        config['Settings']['ffmpeg_path'] = mc.ffmpeg_path.replace("\\\\", "\\").replace("/", "\\")

    with open(mineprep_ini, 'w', encoding='utf-8') as file:
        json.dump(config, file, ensure_ascii=False, indent=4)

    #修改项目配置文件
    DefaultEngine_ini = find_or_create(join(install_path, 'Config', 'DefaultEngine.ini'))
    config = configparser.ConfigParser(allow_no_value=True, strict=False)
    config.read(DefaultEngine_ini, encoding='utf-8')

    CLI = '/Script/MovieRenderPipelineCore.MoviePipelineCommandLineEncoderSettings'
    if not config.has_section(CLI):
        config.add_section(CLI)
    ExecutablePath = mc.ffmpeg_path.replace("\\\\", "\\").replace("/", "\\") if mc.ini_ffmpeg else ffmpeg_default
    config.set(CLI, 'ExecutablePath', ExecutablePath)
    config.set(CLI, 'VideoCodec', 'libx265')
    config.set(CLI, 'AudioCodec', 'aac')
    config.set(CLI, 'OutputFileExtension', 'mp4')
    config.set(CLI, 'CommandLineFormat', r'"-hide_banner -y -loglevel error {AdditionalLocalArgs}"')

    RENDER = '/Script/Engine.RendererSettings'
    if not config.has_section(RENDER):
        config.add_section(RENDER)
    config.set(RENDER, 'r.DefaultFeature.AutoExposure', 'False')
    config.set(RENDER, 'r.RayTracing', 'True')
    config.set(RENDER, 'r.RayTracing.Shadows', 'True')
    config.set(RENDER, 'r.Lumen.HardwareRayTracing', 'True')
    config.set(RENDER, 'r.AllowStaticLighting', 'False')
    config.set(RENDER, 'r.CustomDepth', '3')
    config.set(RENDER, 'r.PostProcessing.PropagateAlpha', 'True')
    config.set(RENDER, 'r.Deferred.SupportPrimitiveAlphaHoldout', 'True')
    config.set(RENDER, 'r.SkinCache.SceneMemoryLimitInMB', '1024.0')
    config.set(RENDER, 'rhi.Bindless.Resources', 'Enabled')
    config.set(RENDER, 'rhi.Bindless.Samplers', 'Enabled')
    config.set(RENDER, 'rhi.Bindless', 'Enabled')
    config.set(RENDER, 'r.Translucency.HeterogeneousVolumes', 'True')
    config.set(RENDER, 'r.Substrate', 'True')
    config.set(RENDER, 'r.Substrate.ProjectGBufferFormat', '1')
    config.set(RENDER, 'r.Substrate.OpaqueMaterialRoughRefraction', 'True')

    GC = '/Script/Engine.GarbageCollectionSettings'
    if not config.has_section(GC):
        config.add_section(GC)
    config.set(GC, 'gc.AssetClustreringEnabled', 'True')
    config.set(GC, 'gc.ActorClusteringEnabled', 'True')

    ENGINE = '/Script/Engine.Engine'
    if not config.has_section(ENGINE):
        config.add_section(ENGINE)
    config.set(ENGINE, 'GenerateDefaultTimecodeFrameRate', '(Numerator=60,Denominator=1)')

    with open(DefaultEngine_ini, 'w', encoding='utf-8') as f:
        config.write(f)

    #修改输入配置文件
    DefaultInput_ini = find_or_create(join(install_path, 'Config', 'DefaultInput.ini'))
    config = configparser.ConfigParser(allow_no_value=True, strict=False)
    config.read(DefaultInput_ini, encoding='utf-8')

    INPUT = '/Script/EnhancedInput.EnhancedInputDeveloperSettings'
    if not config.has_section(INPUT):
        config.add_section(INPUT)
    config.set(INPUT, 'bEnableUserSettings', 'True')

    with open(DefaultInput_ini, 'w', encoding='utf-8') as f:
        config.write(f)

    # 修改编辑器配置文件
    DefaultEditor_ini = find_or_create(join(install_path, 'Config', 'DefaultEditor.ini'))
    config = configparser.ConfigParser(allow_no_value=True, strict=False)
    config.read(DefaultEditor_ini, encoding='utf-8')

    EDITOR = '/Script/UnrealEd.BlueprintEditorProjectSettings'
    if not config.has_section(EDITOR):
        config.add_section(EDITOR)
    config.set(EDITOR, 'bAllowImpureToPureNodeConversion', 'True')

    with open(DefaultEditor_ini, 'w', encoding='utf-8') as f:
        config.write(f)

    #为UE5.7启用无绑定渲染，目前All会导致DLSS闪退
    WindowsEngine_ini = find_or_create(join(install_path, 'Config', 'Windows', 'WindowsEngine.ini'))
    config = configparser.ConfigParser(allow_no_value=True, strict=False)
    config.read(WindowsEngine_ini, encoding='utf-8')

    BINDLESS = 'ShaderPlatformConfig PCD3D_SM6'
    if not config.has_section(BINDLESS):
        config.add_section(BINDLESS)

    config.set(BINDLESS, 'BindlessConfiguration', 'Minimal')
    with open(WindowsEngine_ini, 'w', encoding='utf-8') as f:
        config.write(f)

class CustomButton(bpy.types.Operator):
    bl_idname = "custom.button"
    bl_label = "Custom Button"
    
    press: bpy.props.StringProperty(default="")
    
    def execute(self, context):
        if self.press:
            exec(self.press)
        return {'FINISHED'}

class Welcome(bpy.types.Operator):
    bl_idname = "dialog.welcome"
    bl_label = "Mineprep Installer"

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=444)

    def draw(self, context):
        box = self.layout.box()
        layout = box.column(align=True)

        layout.label(text=loc(2,"---Mineprep v0.4 安装向导---"))
        layout.label(text=loc(3,"欢迎使用Mineprep！"))
        layout.label(text=loc(4,"· 此安装包适用于 Windows + UE5.4"))
        layout.label(text=loc(5,"· 非实验性功能也许能兼容Mac和高版本UE"))
        layout.label(text=loc(6,"· 重复安装会直接覆盖原文件"))
        layout.label(text=loc(7,"· 安装前建议关闭虚幻引擎"))
        layout.separator(factor=3, type='LINE')
        layout.label(text=loc(8,"请点击下方按钮选择安装模式，并根据提示执行操作"))
        layout.separator()

        row = layout.row(align=True)
        row.scale_y = 1.5

        # 修改按钮动作以打开新对话框
        button = row.operator(CustomButton.bl_idname, text=loc(9,"新建UE工程文件"))
        button.press = "mc.install_mode = 1; bpy.ops.dialog.installer1('INVOKE_DEFAULT')"

        button = row.operator(CustomButton.bl_idname, text=loc(10,"安装至现有工程"))
        button.press = "mc.install_mode = 2; bpy.ops.dialog.installer2('INVOKE_DEFAULT')"


class Installer1(bpy.types.Operator):
    bl_idname = "dialog.installer1"
    bl_label = loc(9,"新建UE工程文件")
    
    def execute(self, context):
        mc.install_mode = 1
        install()
        bpy.ops.dialog.finish('INVOKE_DEFAULT')
        return {'FINISHED'}
    
    def invoke(self, context, event):
        mc.install_path = join(outer_dir, "MC_Startup")
        extract_zip(ffmpeg_zipfile, join(file_dir, 'Mineprep', 'Render'))
        return context.window_manager.invoke_props_dialog(self, width=420)
    
    def draw(self, context):
        layout = self.layout.column(align=True)
        layout.label(text=loc(11,"选择安装路径"))

        # 选择文件夹
        layout.prop(mc, "install_path", text="")

        if mc.install_path and not all(ord(char) < 128 for char in mc.install_path):
            box = layout.box()
            box.alert = True
            box.label(text=loc(12,"警告: 文件夹路径包含中文或非ASCII字符！可能会导致部分功能失效"), icon='ERROR')

        layout.separator(type='LINE')
        layout.label(text=loc(33,"当前所需空间") + est_size())
        if lite_only:
            layout.label(text=loc(32,"安装精简版"))
        else:
            layout.prop(mc, "lite_version", text=loc(32,"安装精简版"))
        layout.prop(mc, "skip_other_platform", text=loc(34,"跳过为其他平台编译的文件"))
        layout.separator(type='LINE')
        layout.label(text=loc(13,"实验性功能:"))
        layout.prop(mc, "exp_basic", text=loc(14,"Mineprep C++ 拓展模块"))
        layout.prop(mc, "exp_material", text=loc(31,"为材质参数面板添加关键帧按钮和本地化翻译"))
        layout.prop(mc, "exp_vr3d", text=loc(15,"解锁双目立体全景渲染"))
        layout.prop(mc, "exp_template_seq", text=loc(16,"扩展模板序列以支持双精度浮点和向量属性乘数"))

        layout.separator(type='LINE')
        layout.label(text=loc(17,"插件设置:"))
        layout.prop(mc, "ini_ffmpeg", text=loc(18,"手动指定FFmpeg路径 (如ffmpeg.exe)"))
        if mc.ini_ffmpeg:
            layout.prop(mc, "ffmpeg_path", text=loc(19,"路径"))
        layout.prop(mc, "ini_memory", text=loc(20,"内存预加载"))
        layout.label(text=loc(21,"     · 打开插件时加载所有资源，启动速度较慢，但运行更流畅"))
        



class Installer2(bpy.types.Operator):
    bl_idname = "dialog.installer2"
    bl_label = loc(10,"安装至现有工程")

    def execute(self, context):
        mc.install_mode = 2
        install()
        bpy.ops.dialog.finish('INVOKE_DEFAULT')
        return {'FINISHED'}
    
    def invoke(self, context, event):
        mc.install_path = ""
        extract_zip(ffmpeg_zipfile, join(file_dir, 'Mineprep', 'Render'))
        return context.window_manager.invoke_props_dialog(self, width=420)
    
    def draw(self, context):
        layout = self.layout.column(align=True)
        layout.label(text=loc(22,"选择工程目录 (包含.uproject的文件夹)"))
        
        # 选择文件夹
        layout.prop(mc, "install_path", text="")
        
        # 获取绝对路径进行检查
        if mc.install_path:
            abs_path = get_abs_path(mc.install_path)
            
            # 警告信息
            if not all(ord(char) < 128 for char in abs_path):
                box = layout.box()
                box.alert = True
                box.label(text=loc(12,"警告: 文件夹路径包含中文或非ASCII字符！可能会导致部分功能失效"), icon='ERROR')
            if not os.path.exists(abs_path) or not any(file.endswith('.uproject') for file in os.listdir(abs_path)):
                box = layout.box()
                box.alert = True
                box.label(text=loc(23,"警告: 未找到.uproject文件！请确认当前文件夹为UE工程根目录"), icon='ERROR')

        layout.separator(type='LINE')
        layout.label(text=loc(33,"当前所需空间") + est_size())
        if lite_only:
            layout.label(text=loc(32,"安装精简版"))
        else:
            layout.prop(mc, "lite_version", text=loc(32,"安装精简版"))
        layout.prop(mc, "skip_other_platform", text=loc(34,"跳过为其他平台编译的文件"))
        layout.separator(type='LINE')
        layout.label(text=loc(13,"实验性功能(仅适用于Windows+UE5.7):"))
        layout.prop(mc, "exp_basic", text=loc(14,"Mineprep C++ 拓展模块"))
        layout.prop(mc, "exp_material", text=loc(31,"为材质参数面板添加关键帧按钮和本地化翻译"))
        layout.prop(mc, "exp_vr3d", text=loc(15,"解锁双目立体全景渲染"))
        layout.prop(mc, "exp_template_seq", text=loc(16,"扩展模板序列以支持双精度浮点和向量属性乘数"))

        layout.separator(type='LINE')
        layout.label(text=loc(17,"插件设置:"))
        layout.prop(mc, "ini_ffmpeg", text=loc(18,"手动指定FFmpeg路径 (如ffmpeg.exe)"))
        if mc.ini_ffmpeg:
            layout.prop(mc, "ffmpeg_path", text=loc(19,"路径"))
        layout.prop(mc, "ini_memory", text=loc(20,"内存预加载"))
        layout.label(text=loc(21,"     · 打开插件时加载所有资源，启动速度较慢，但运行更流畅"))
        

class Finish(bpy.types.Operator):
    bl_idname = "dialog.finish"
    bl_label = loc(24,"安装完成！")

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):

        box = self.layout.box()
        box.label(text=loc(25,"Mineprep已经可以使用了"))
        box.label(text=loc(30,"请勿移动或删除安装包，插件可能会引用其中资源"))
        button = box.operator(CustomButton.bl_idname, text=loc(26,"打开工程文件"))
        abs_path = get_abs_path(mc.install_path)
        uproject_files = [f for f in os.listdir(abs_path) if f.endswith('.uproject')]
        newproj_path = join(abs_path, uproject_files[0]) if uproject_files else ""
        button.press = f"os.startfile(r\"{newproj_path}\")"

        box.separator(type='LINE')

        layout = box.column(align=True)
        layout.label(text=loc(27,"另外，我们推荐您安装超分辨率插件"))
        layout.label(text=loc(28,"它可以提升画质和帧率，甚至节约显存"))
        layout.label(text=loc(29,"您需要手动下载安装，一个虚幻引擎版本只需要安装一次："))
        row = box.row(align=True)
        button_dlss = row.operator(CustomButton.bl_idname, text="DLSS")
        button_dlss.press = "bpy.ops.wm.url_open(url='https://developer.nvidia.com/rtx/dlss#getstarted')"
        button_fsr = row.operator(CustomButton.bl_idname, text="FSR")
        button_fsr.press = "bpy.ops.wm.url_open(url='https://gpuopen.com/learn/ue-fsr/')"
        button_xess = row.operator(CustomButton.bl_idname, text="XeSS")
        button_xess.press = "bpy.ops.wm.url_open(url='https://github.com/GameTechDev/XeSSUnrealPlugin/releases')"


# 启动时将分卷压缩合并为完整 ffmpeg.zip
def merge_ffmpeg_zip():
    part1 = ffmpeg_zipfile + '.001'
    if not os.path.exists(part1) or os.path.exists(ffmpeg_zipfile):
        return
    print("正在合并 ffmpeg 分卷压缩文件...")
    with open(ffmpeg_zipfile, 'wb') as output:
        i = 1
        while os.path.exists(f"{ffmpeg_zipfile}.{i:03d}"):
            with open(f"{ffmpeg_zipfile}.{i:03d}", 'rb') as part:
                output.write(part.read())
            i += 1
    print("合并完成：", ffmpeg_zipfile)

def register():
    bpy.utils.register_class(CustomButton)
    bpy.utils.register_class(Welcome)
    bpy.utils.register_class(Installer1)
    bpy.utils.register_class(Installer2)
    bpy.utils.register_class(Finish)

def unregister():
    bpy.utils.unregister_class(CustomButton)
    bpy.utils.unregister_class(Welcome)
    bpy.utils.unregister_class(Installer1)
    bpy.utils.unregister_class(Installer2)
    bpy.utils.unregister_class(Finish)
    del bpy.types.Scene.mineprep

if __name__ == "__main__":
    register()
    merge_ffmpeg_zip()
    if hasattr(bpy.context.scene, "mineprep"):
        mc.page = 0
    if lite_only:
        mc.lite_version = True
    bpy.ops.dialog.welcome('INVOKE_DEFAULT')

