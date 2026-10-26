# 公共纹理 API：契约与边界

用于高度图（[HEIGHTMAP](HEIGHTMAP.md)）与遮罩（[MASKS](MASKS.md)）的 UE 纹理导出及瞬态数据纹理导入。

## 三个公开入口

以下函数在编辑器主线程调用，使用`mineprep.*`；文件解码、摘要、NumPy映射与采样仍放工作线程。

```python
import unreal
import mineprep

texture = unreal.load_asset('/Game/Path/T_Texture')
originals = mineprep.tex_source_files(texture)  # tuple[Path, ...]
cached = mineprep.export_tex_cache(texture)   # Path，工程/cache/
cached = mineprep.export_tex_cache(texture, path='cache/heightmaps')
preview_texture = mineprep.import_data_tex(cached)  # Texture2D，保留强引用
```

| 入口 | 契约 |
| --- | --- |
| `tex_source_files(texture)` | 只接受Texture2D；查询asset_import_data的全部文件，转为绝对Path、稳定去重；无导入数据返回空元组，缺失文件仍保留记录，不导出、不判断能否解码 |
| `export_tex_cache(texture, path='')` | path是缓存目录；空值使用工程/cache，非空相对目录相对工程根解析，也接受绝对目录。创建目录，导出TextureSource像素并返回绝对Path |
| `import_data_tex(path)` | 接受已存在的PNG／EXR文件，创建瞬态Texture2D；设置sRGB=False、Nearest、X/Y Clamp，仅刷新本次新对象。调用方持有强引用，不保存内容浏览器资产 |

## 导出与缓存

先检查有效Source ID，再拒绝虚拟纹理；无Source时在创建导出任务之前报错。通过当前对象的AssetData查询SourceFormat，不依据CompressionSettings猜测数值类型。

| TextureSource格式 | 文件 |
| --- | --- |
| G8、G16、BGRA8、RGBA16 | PNG |
| BGRE8、R16F、R32F、RGBA16F、RGBA32F | EXR |

未知格式报错。不显式指定Exporter，由引擎选择兼容导出器。文件名为纹理名前32字符、SHA256身份前8位及扩展名；身份包含编码版本v1、资产对象路径、Source ID和扩展名。旁置`.png.key`／`.exr.key`保存完整64位身份，仅在记录完全匹配且图片非空时复用。短名冲突、缺失／损坏记录或未知占用时每次延长4位，不覆盖其他内容。相同身份的空文件可修复；旧长名缓存原样保留，首次使用新规则重新导出。

首次导出写同目录临时文件，检查导出结果、Source ID及非空文件后原子发布图片，最后原子发布完整身份记录；失败清理本次临时文件。中断留下的未配对图片不会命中或被覆盖。命中缓存时也复查Source ID。该接口不计算缓存文件内容摘要，不会检测任意外部篡改的非空缓存；WorldGenerator仍须捕获文件内容、保留数值快照并校验生成来源。

## 精度与安全边界

- 选引擎资产时，Source导出代表该纹理当前的源数据；`tex_source_files`只是原图线索，原图可能缺失或与重导入前后的资产不同步，不能静默替换当前Source。
- 导出文件保留Source格式的数值用途；PNG整数归一化、EXR格数及彩色图R通道提取由WorldGenerator解码层解释。Alpha不作为高度；EXR导出可能补Alpha通道。
- 瞬态纹理用于预览，不取代文件／解码数组作为生成数据。`import_data_tex`不承诺所有输入保留FP32精度，已知彩色FP32 EXR导入可能转换为FP16；需要精确高度时使用原文件数组。
- 文件导入创建的瞬态Texture2D通常没有有效TextureSource。不得再次用资产导出器导出；本地文件来源应直接复用已捕获的文件／数组。
- 此前对无Source瞬态纹理直接调用TextureExporterEXR，触发TSF_Invalid原生断言并导致编辑器退出；Python异常处理无法兜住。不得为验证重新走该路径。
- 不修改用户纹理的sRGB、压缩、导入配置或构建状态；不增加GPU读回兜底、RenderTarget支持、C++接口或缓存自动清理。旧`tex_to_color`／`color_to_tex`行为保持，仍不适合高精度高度输入。
