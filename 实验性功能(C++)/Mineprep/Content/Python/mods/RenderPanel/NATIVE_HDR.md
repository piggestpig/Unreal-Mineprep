# Filmic HDR：原生 PQ / scRGB

原生 MRQ 添加 **Mineprep Filmic HDR**。默认峰值 1000 nit、参考白 203 nit、Rec.2020/D65 限制色域。保留类名及 Core Redirect，不批量改写资产。

## 参数与用户设置

- **Output PQ**：C++ `bOutputPQ=true`，Python `output_pq`。开启输出 Rec.2020/D65 ST2084 PQ，关闭输出线性 scRGB（sRGB/D65 原色，1.0＝80 nit）。旧配置没有该字段时采用默认 PQ。
- **Peak Luminance**：`100 < PeakNits <= 10000`，须为有限数值。
- **Paper White**：`0 < PaperWhiteNits <= PeakNits`，须为有限数值。

任务只临时选择 `r.LUT.TonemappingMethod=0`（Filmic），结束后恢复原值。ACES 版本、SceneColorMultiplier、Gamma、LUT 等沿用用户值，不改写场景、相机或工程 ini。

不修改 `r.HDR.Display.OverrideOSMaxLuminance`。该全局开关开启时，引擎可能优先使用全局峰值，组件 PeakNits 不保证强制生效。不要求采集视口或开启 Windows HDR，但全局参数仍遵循引擎规则。

只校验两个亮度参数，不拦截 CLI、OCIO、Color Output、采样、分块、分层、工作色域及其他输出组合。启用本设置会选择 Filmic HDR ViewFamily 输出；后续 OCIO 等按引擎顺序组合，不自动禁用。旧 ACES 显示变换会再次改变已经调色的图像，解除拦截不代表任意组合都获得相同颜色。

代理仍转发 MRQ 自己的纹理、RDG、UAV、尺寸与资源，不捕获视口。每个镜头及任务收尾时等待渲染命令完成，释放代理、恢复 Filmic 选择；保留失败、取消和销毁清理。

## Python 单帧入口

```python
from mods.RenderPanel import native_hdr

# 只生成配置，不改队列、资产、输出目录或 CVar。
config, sequence = native_hdr.build_test_config(resolution=(1920, 1080))

# 可选线性 scRGB。
config, sequence = native_hdr.build_test_config(output_pq=False)

# 只向空 MRQ 队列加入一项，由用户提交。
job = native_hdr.prepare_test_job(
    resolution=(3840, 2160), peak_nits=1000.0,
    paper_white_nits=203.0, output_pq=True)
```

两个入口保留 sequence、frame、resolution、peak_nits、paper_white_nits，新增关键字参数 output_pq=True。默认当前序列与光标帧，要求相机切换轨道；显式其他序列默认播放起点。帧范围为 [frame, frame+1)。

默认普通 Deferred、1×1 采样、40 次渲染暖场、2 帧引擎暖场、单层半浮点 ZIP EXR、Tone Curve 开启、OCIO 关闭，无音频或视频。输出使用独立的 Saved/MovieRenders/FilmicHDR_Test/<唯一目录>/。预览不创建目录，准备任务保留空队列与活动任务保护。

## 临时视频按钮

**Filmic HDR（临时）** 明确使用 PQ，沿用当前任务的序列、输出名、分辨率、帧率、采样和暖场：

```text
场景 → UE Filmic HDR → Rec.2020 PQ EXR → BT.2020 YUV → H.265 MP4
```

FFmpeg 明确按 PQ / Rec.2020 读取，只做 RGB→limited-range BT.2020 non-constant YUV。不再使用线性输入、npl=80 或第二次 PQ 变换，不接入 OpenCV/NumPy 逐帧管道。PQ EXR 是显示编码图像，不是普通场景线性 EXR。

保持 HEVC Main10 4:2:0、hvc1、PQ/BT.2020 标记，无音频，不虚构 MaxCLL/MaxFALL。硬件与质量从旧面板采集：CPU/libx265、Nvidia/NVENC、Intel/QSV、AMD/AMF、Apple/VideoToolbox、Vulkan；不会因不可用而静默换成其他硬件。CPU 写入 1000 nit mastering SEI；硬件路径保留 PQ/BT.2020 VUI 与容器标记，容器中的 `master-display` 不保证等同于 x265 的 mastering SEI。FFmpeg 使用偏好路径或插件附带版本。临时按钮仍只组装普通 MRQ 动画，要求正偶数宽高；不扩展 MRG、预设或批量。

输出在 Saved/MovieRenders/<原子目录>/<名称>_FilmicHDR/<唯一目录>/，保留 EXR、encode_command.json、encode.log。原生队列和旧配置资产不变；通过新 job 的 SetConfiguration 清除 preset origin，避免重新加载旧 OCIO。

render_video(settings=None, *, on_done=None, notify=True) 返回现有异步句柄（done/result/error）；显式设置不读旧控件。旧面板的 `🔲后台编码` 开启时，渲染结束释放渲染占用，编码进入最多两个并发的 Python 后台进程，允许下一份渲染开始；关闭时通过 MRQ CLI 编码，MRQ 会等待它完成。句柄始终等到编码结束才完成，关闭面板不取消任务。UE 取消后若已有连续帧，允许编码部分视频但返回 success=False。无输入正常返回未完成；编码错误保留材料。完整成功才播放提示，目录沿用原偏好。

## 验收

完整编译后由用户重开编辑器，以同一帧对比原生 PQ 与正确的 scRGB 重编码参考，检查灰阶、高光、饱和色和尺寸。检查 bool 的配置复制、CLI/OCIO 组合不再被拦截、成功及取消后的 CVar 恢复。

编码命令显式声明输入约定，不依赖 EXR 写入器自动推断传递函数。scRGB 的负值及超过 1 的值仍需要保真的浮点处理通路，当前视频按钮只编码 PQ。
