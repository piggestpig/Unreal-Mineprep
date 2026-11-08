# Unreal-Mineprep

[**简体中文**](<./README.md>) | [**English**](<./README_English.md>) | 繁體中文(台灣) | [**繁體中文(香港)**](<./README_繁體中文(香港).md>)

✨這是一個正在開發中的UE5外掛，繼承了 [Blender MCprep](https://theduckcow.com/dev/blender/mcprep/) 的實用功能，並加入一些新的資產，為製作MC動畫帶來便利

![image](https://raw.githubusercontent.com/wiki/piggestpig/Unreal-Mineprep/image/0.7-pre1%E5%B0%81%E9%9D%A2%E5%9B%BE.jpg)

![image](https://raw.githubusercontent.com/wiki/piggestpig/Unreal-Mineprep/image/%E6%8F%92%E4%BB%B6%E5%B1%95%E7%A4%BA.jpg)

· 本外掛與Minecraft、MCprep官方沒有直接聯絡，在其建議下外掛名稱由Unreal MCprep更改為Unreal Mineprep，以避免混淆（0.3及之前的版本已經歸檔，就不做修改了）

Mineprep 1.0 預計在2027年釋出。我們正透過Python進行大型底層重構，同時為最新版編寫[使用教學](https://github.com/piggestpig/Unreal-Mineprep/wiki)。當前，外掛主要供內部使用，可能存在相容性問題和潛在的 ~~bug~~ 特性，之後會逐步修復。

[Mineprep Lite](https://github.com/piggestpig/Mineprep-Lite)是此外掛的精簡版。它的體積更小，下載更快，以GPLv3協議開源，保留了95%的核心功能。

## 下載與安裝

> 使用Mineprep前，你需要安裝 [虛幻引擎](https://www.unrealengine.com/zh-CN/download)，MacOS使用者還需安裝 [Xcode](https://developer.apple.com/xcode/) 才能啟動引擎

① 下載Mineprep，建議儲存在純英文路徑下
- 你可以前往 [Releases](https://github.com/piggestpig/Unreal-Mineprep/releases) -> Assets -> Source code
(zip) 下載較為穩定的大版本
- 或者點選上面的綠色 Code 按鈕 -> Download ZIP，下載最新快照版本
- 新手入門/網速較慢時，可下載[Mineprep Lite](https://github.com/piggestpig/Mineprep-Lite)精簡版，壓縮包僅250MB左右

② 選擇任意一種安裝方法；根據你所啟用的功能，安裝所需空間在80MB~2GB之間：

<details>
<summary> 1. 使用Blender安裝包 (適用於0.4+版本) </summary>

- 前提條件：你已經擁有[Blender](https://www.blender.org/download/)
- 解壓外掛安裝包後，使用Blender開啟裡面的[Mineprep_installer.blend檔案](./Mineprep_installer.blend)
- 點選▶️執行指令碼，會彈出選單和安裝引導，目前支援“建立新的專案檔”或“安裝至現有專案”
- 你可以在UI介面中選擇實驗性功能、修改外掛設定

</details>

<details>
<summary> 2. 使用Python安裝指令碼 (適用於0.6+版本) </summary>

- 前提條件：你已經擁有[Python](https://www.python.org/downloads/)執行環境
- 在命令列中執行[Mineprep_installer.py](./Mineprep_installer.py)指令碼
- 以下是推薦範例，這會安裝效能最佳化後的精簡版外掛：  
```
Mineprep_installer.py new [目标文件夹] [--name 工程文件名] --experimental 12 --lite 1 --optimize --gbuffer 0 --open
```
- 使用`--dry-run`列印將要安裝的內容並估算所需空間；各種參數的用法都寫在指令碼開頭了

</details>

<details>
<summary> 3. 從現有專案遷移外掛 (適用於0.6+版本) </summary>

- 前提條件：你已經有了一個裝好Mineprep的專案檔
- 開啟 頂部選單欄 → MC → 模組管理器，勾選左下角的“顯示進階選項”，啟用`外掛更新與遷移工具`模組
- 你可以在UI介面中選擇目標路徑、挑選要遷移的內容
> 遷移外掛能保留你自己修改或新增的檔案，還可遷移模組偏好設定

</details>


<details>
<summary> 4. 手動安裝 </summary>

需要複製Mineprep內容資料夾+修改專案設定，稍後會更新詳細步驟

</details>
<br>

如果你經常更新快照版本，建議使用git克隆倉庫，這樣只需拉取最新的提交，不必反覆下載整個壓縮包！喜歡UI介面的使用者可以用[Github Desktop](https://desktop.github.com/download/)代替git

<details>
<summary> 檢視安裝時修改的檔案 </summary>

```
工程文件目录
    ├── Config
    │     ├── Windows
    │     │     └── WindowsEngine.ini
    │     ├── DefaultEditor.ini
    │     ├── DefaultEngine.ini
    │     └── DefaultInput.ini
    ├── Content
    │     └── Mineprep
    ├── Plugins
    │     ├── Mineprep (*)
    │     ├── InlineMaterialInstance*
    │     └── MoviePipelineMaskRenderPass*


*表示可选的实验性功能
(*)表示有普通/实验性两个版本
```

</details>

<details>
<summary> [推薦] 安裝DLSS等第三方超解析度外掛 </summary>

非常建議N卡使用者安裝DLSS，能提升效能、提高畫質、節約顯示記憶體

1、前往[https://developer.nvidia.com/rtx/dlss](https://developer.nvidia.com/rtx/dlss)，在“DLSS 4.5 Plugin for Unreal Engine”板塊下載對應的外掛版本

2、解壓後，複製Plugins資料夾裡的子資料夾 到虛幻引擎外掛目錄的Marketplace資料夾中，如下所示:

**從解壓後的DLSS外掛資料夾**
```
Plugins
  ├── DLSS
  ├── DLSSMoviePipelineSupport
  └── ...
```
**到虛幻引擎外掛資料夾**

```
Engine
  ├── Plugins
  │     ├── Marketplace
  │     │     ├── DLSS ⬅
  │     │     ├── DLSSMoviePipelineSupport ⬅
  │     │     └── ...
  │     └── ...
  └── ...
```
沒有Marketplace資料夾的話自己新建一個

3、開啟專案檔，在左上角-編輯-外掛 裡搜尋DLSS，啟用`NVIDIA
DLSS
Super Resolution/Ray Reconstruction/DLAA`和`Movie Render Queue DLSS/DLAA Support`，重啟引擎

安裝成功後，你可以在MC導播臺中調整DLSS檔位。

> 渲染動畫時只能使用DLSS和光線重構，用不了影格生成，所以啟用上面兩個外掛就夠了

</details>



## 系統需求
Mineprep 0.7-pre1 使用 Windows + UE5.8 開發，建議在此環境下使用。其他平臺或引擎版本將會有一些功能不可用。

除了[虛幻引擎官方文件](https://dev.epicgames.com/documentation/zh-cn/unreal-engine/hardware-and-software-specifications-for-unreal-engine)中的最低要求之外，渲染動畫還需要更高的配置和更多的顯示記憶體：

| 推薦配置 | 參考配置<sup>[1]</sup> |
| :--- | :--- |
| - 支援硬體光線追蹤的顯示卡<sup>[2]</sup> <br>- 32G以上記憶體和12G以上顯示記憶體<br>- SSD固態硬碟 | - CPU：i7-13700K<br>- 記憶體：32G*2 DDR5-6400MHz<br>- 顯示卡：RTX 4080 (16G)<br>- 硬碟：2TB + 4TB PCIe 4.0 SSD |

<sup> [1] 我們開發外掛和製作動畫所用的電腦  
[2] NVIDIA 20系，AMD 6000系，Intel Arc 或 Apple M3 及以上 </sup>


### 歷史版本與平臺相容性

Mineprep的絕大部分功能都用藍圖和Python編寫，旨在支援不同的平臺和更高的引擎版本。實驗性功能是C++程式碼，通常只為Windows編譯。

| Mineprep<br>版本 | Python<br>API 版本 | 引擎版本 | Windows<br>實驗性功能 | Mac/Linux<br>實驗性功能 |
| :---: | :---: | :---: | :---: | :---: |
| 最新快照 | 3.0 | 5.8 | ✅ | - |
| 0.7-pre1 | 2.0 | 5.8 | ✅ | - |
| 0.6-pre1 | 1.0 | 5.7 | ✅ | ℹ️ |
| 0.5 | 0.1 | 5.7 | ✅ | ✅ |
|  |  |  |  |  |
| 0.5-pre3 | - | 5.6 | ✅ | - |
| 0.5-pre2 | - | 5.6 | ✅ | - |
| 0.5-pre1 | - | 5.5 | ✅ | - |
| 0.4 | - | 5.4 | ✅ | - |
| 0.4-pre2 | - | 5.4 | ✅ | - |
| 0.4-pre1 | - | 5.4 | ✅ | - |
| 0.3 | - | 5.4 | - | - |
| 0.3-pre1 | - | 5.4 | - | - |
| 0.2 | - | 5.3 | - | - |
| 0.1 | - | - | - | - |

> [!WARNING]  
> 請勿在不相容的環境（比如高版本引擎）勾選實驗性功能，否則專案檔打都打不開，一上來就報錯！！


<details>
<summary> *展開細節 </summary>

Mineprep 0.6-pre1 只在 Windows 上編譯了最新的實驗性功能。我們保留了來自0.5版本的二進位制檔案，Mac和Linux使用者可以嘗試安裝，但不保證能正常執行

<img src="https://raw.githubusercontent.com/wiki/piggestpig/Unreal-Mineprep/image/Mac%26Linux%E5%90%88%E5%BD%B1%E7%95%99%E5%BF%B5.jpg" alt="Mac&Linux合影留念">
<sup><i> ↑ Mineprep 0.5 在 MacOS 和 Linux 執行的紀念照 </i></sup>

- 安裝包是寫在Blender裡的python指令碼，理論上是跨平臺的，但是有一些細節比如os.startfile()只在Windows上可用，我們嘗試用命令列替代這些功能
- 外掛的非實驗性功能是UE5藍圖資產，高版本引擎可以向下相容舊資產，但低版本引擎無法開啟新資產。如果你不得不使用低版本引擎，請下載Mineprep的早期版本
- 實驗性功能是C++程式碼，必須針對特定平臺和特定引擎版本編譯。Windows會隨每次快照更新，Mac和Linux只會在大版本更新
- 目前物理互動綁定會在Mac和Linux上閃退，安裝時將跳過這個素材
- 另外，外掛附帶了FFmpeg用於影片編碼。你也可以手動下載ffmpeg並在安裝時指定路徑。官方建議下載最新版的master build

> ⚠️  
> MacOS使用過 M4 Max (36G)和 M2 Max (32G)進行測試，目前存在的問題如下：  
> · 儘管能用硬體光追和Megalights，但似乎不支援Alpha遮罩。預設啟用VSM虛擬陰影貼圖  
> · 遠景地形生成器效能差，比預期慢好幾倍  
> · 可互動3D水池非常不穩定，產生劇烈的自碰撞  
> · 沒有DLSS等超解析度外掛，預設使用引擎自帶的TSR，拖影嚴重且效能差，空場景佔用6ms比光追還慢  
> · 缺少nDisplay，不支援3D立體渲染，安裝實驗性功能才有初步的3D渲染功能  
> · Mac的資料夾可以隨意擺放檔案位置，渲染後好像要向下滾動才能在底部看到影片  
> · 生成器子面板的排序和Windows不一樣，好像是python sort的問題，反正中文名都沒啥順序，就當特性好了  
> · 快捷鍵的Ctrl似乎會變成Cmd，遠端連線時一個快捷鍵也沒按出來，本地使用應該沒問題

> ⚠️  
> Linux使用E5+64G+3090的伺服器測試，只簡短地測過一次，沒發現什麼大問題  
> · E5實在是太太太慢了，別看有18個核心，編譯著色器竟然花了半小時，進編輯器只有四五十影格qwq （我第一次直觀感受到單核效能的重要性）  
> · 真的有人用linux做動畫嗎？

> ⚠️  
> 使用NvRTX等非官方引擎版本，實驗性功能不可用，其他功能應該可用  
> 非官方版本一般需要自己編譯，假如你已經配好了環境，其實可以安裝實驗性功能，在開啟專案檔時根據提示重新編譯  
> 我之前使用NvRTX 5.7，發現它僅支援Blendable Gbuffer，安裝外掛時請勾選“使用相容性更好的有限Blendable GBuffer材質”

· 充足的顯示記憶體是流暢執行的基礎，渲染動畫會額外佔用更多顯示記憶體。Windows(DX12)和MacOS在爆顯示記憶體後能使用記憶體/硬碟繼續渲染，但速度會慢10倍左右。Vulkan爆顯示記憶體則會直接崩潰。

· 使用推薦配置中的RTX4080主機製作動畫，編輯器中的影格率通常在60~120fps之間

· 我們常用的渲染預設是 `2K_120.mp4` 和 `2K_120_HDR.mp4`，使用 `4 影視級（特調畫質）`，開啟DLAA，輸出影格率在5~30fps左右


</details>




## 生物
- Mineprep提供了MC原版生物模型，可以透過生成器面板放置
- 目前主要有骨骼網格體和自動化NPC兩種型別，部分生物製作了頂點動畫實例模型，用於大型群體粒子。所有生物都可以更換材質，兩腳生物可以嘗試新增IK綁定
- 當前版本支援：Steve/Alex玩家、豬、牛、羊、馬（驢、騾、殭屍馬、骷髏馬）、殭屍、屍殼、沉屍、骷髏、凋零骷髏、流髑、沼骸、豬布林、豬布林蠻兵、掠奪者、衛道士、鐵魔像、蠹魚、終界蟎、蜘蛛（洞穴蜘蛛）、村民、烈焰使者、凋零怪、豬布獸、雪人、狼、貓、悅靈、流浪商人、山貓、地獄幽靈、小幽靈、快樂幽靈、苦力怕、鸚鵡、駱駝、駱駝屍殼、枯骸、鱈魚、鮭魚、熱帶魚
- 透過`MC原版生物載入器`模組，可以從Blockbench的CEM Template Loader下載最新的生物模型，匯入為骨骼網格體
- 更多內容正在更新中

## 語言本地化
Mineprep提供了可拓展的多語言翻譯，目前支援中文/英文/繁體中文(臺灣/香港)
- **安裝包**會根據Blender的偏好設定選擇語言。本地化內容以字典的形式寫在程式碼中，參見[Mineprep_installer.blend](./Mineprep_installer.blend)或[Mineprep_installer.py](./Mineprep_installer.py)
- **外掛面板**上方有選擇語言的按鈕，在啟動時會根據UE的偏好設定選擇語言。本地化內容儲存在[語言本地化_language_localization.csv](./Mineprep/插件贴图/语言本地化_language_localization.csv) 和 [變數顯示名_VariableDisplayNames.csv](./Mineprep/插件贴图/变量显示名_VariableDisplayNames.csv)中。
- **模組**的本地化內容儲存在各自的`i18n.json`檔案中。
- 只有安裝了第一個實驗性功能 `(Mineprep C++ 拓展模組)` 才能翻譯粒子參數。  
- 只有安裝了第二個實驗性功能 `(為材質參數面板新增關鍵影格按鈕和本地化翻譯)` 才能翻譯材質參數
- 第一個實驗性功能還提供了自訂快捷鍵，可以按`insert`嘗試翻譯滑鼠下的文字；如果在變數顯示名的csv檔案中找到匹配條目，就替換文字。有了實驗性功能後，還能透過`本地化翻譯控制板`模組收集最新的變數顯示名

更多內容正在更新中


## 模組
模組是透過 [Mineprep Python API](https://github.com/piggestpig/Unreal-Mineprep/wiki/Mineprep-Python-API) 編寫的指令碼檔案，支援像Blender一樣快速建立UI介面，執行自訂程式

- 可隨時安裝和解除安裝
- 體積小，通常只有幾十KB
- 跨平臺，易於擴充套件
- 能自動儲存屬性集
- 適合Agent迭代開發

使用方法：在 `頂部選單欄 → MC → 模組管理器` 中安裝、解除安裝、啟用、停用、打包模組。  
Mineprep 0.7-pre1有以下內建模組（目前仍處於早期開發階段，可能存在bug）：

| 模組名稱 | 版本 | 簡介 | 原始碼參考 |
| :--- | :---: | :--- | :--- |
| [模組管理器](<./实验性功能(C++)/Mineprep/Content/Python/mods/ModManager>) | 2.0 | 啟用、停用、安裝、解除安裝、打包模組 | [Blender](https://github.com/blender/blender/blob/main/scripts/addons_core/bl_pkg/cli/blender_ext.py) |
| [自訂快捷鍵](<./实验性功能(C++)/Mineprep/Content/Python/mods/EditorShortcuts>) | 2.0 | 編輯自訂快捷鍵 | |
| | | | |
| [VAT頂點動畫工具](<./实验性功能(C++)/Mineprep/Content/Python/mods/VAT_Tools>) | 2.0 | 烘焙頂點動畫紋理，用於大型群體粒子 | [Anim To Texture Helpers](https://github.com/kromond/AnimToTextureHelpers) |
| [皮膚&表情編輯器](<./实验性功能(C++)/Mineprep/Content/Python/mods/Skin_Editor>) | 2.0 | 編輯選中Actor的皮膚與頭部材質；繪製紋理 | [MC Skin Converter](https://util.gflash.eu/mcskinconverter/) |
| [MC原版生物載入器](<./实验性功能(C++)/Mineprep/Content/Python/mods/VanillaMobLoader>) | 2.0 | 瀏覽、匯入並放置MC生物模型（下載資源需聯網） | [CEM Template Loader](https://ewanhowell.com/plugins/cem-template-loader/) |
| [基岩版動畫轉換器](<./实验性功能(C++)/Mineprep/Content/Python/mods/BedrockAnimator>) | 2.0 | 把基岩版 animation.json 轉換為動畫序列 | |
| [像素標題生成器](<./实验性功能(C++)/Mineprep/Content/Python/mods/TitleGenerator>) | 2.0 | 生成大標題（下載資源需聯網） | [Minecraft Title Generator](https://github.com/ewanhowell5195/MinecraftTitleGenerator) |
| [MC世界生成器](<./实验性功能(C++)/Mineprep/Content/Python/mods/WorldGenerator>) | 0.64.7 | 高效能的世界生成器，支援多種地形和生態域 | [Minecraft](https://www.minecraft.net/en-us/article/removing-obfuscation-in-java-edition), [Mineways](https://github.com/erich666/Mineways) |
| | | | |
| [外掛更新與遷移工具](<./实验性功能(C++)/Mineprep/Content/Python/mods/VersionControl>) | 2.0 | 遷移Mineprep外掛至其他專案檔或安裝包倉庫 | |
| [本地化翻譯控制板](<./实验性功能(C++)/Mineprep/Content/Python/mods/LocalizationBoard>) | 2.0 | 掃描資產並整理變數顯示名 CSV（需要實驗性功能）| |
| [自動化測試](<./实验性功能(C++)/Mineprep/Content/Python/mods/AutomationTest>) | 2.0 | 執行編輯器自動化測試專案 | |
| [Mod模板](<./实验性功能(C++)/Mineprep/Content/Python/mods/template.py>) | 2.0 | 面向開發者的普通mod模板 | |
| [minimal](<./实验性功能(C++)/Mineprep/Content/Python/mods/minimal.py>) | - | 最小範例 | |


## 開源協議
- 由於完整版Mineprep包含了虛幻引擎官方範例和原始碼，它們和開源許可證不相容，這裡就先不放License檔案了。[Mineprep Lite](https://github.com/piggestpig/Mineprep-Lite) 是此外掛的精簡版，它以GPLv3協議開源
- 在大部分情況下，你可以免費使用本外掛。(UE5.3及更早的版本不向影視創作者收費，UE5.4開始對年收入超過100萬美元的使用者按席位收費，顯然我們不會達到收費門檻hhh)  
具體參見[Epic Games的使用者協議](https://www.unrealengine.com/zh-CN/eula)
- 同時，Mineprep引用了許多第三方外掛和資源，在此向他們表示感謝。我們在[ResourceLicenses](./Readme素材/ResourceLicenses)資料夾中收錄了一些許可證和作者留言。如有遺漏可以拉一個Pull Request進行補充


## 版本更新

#### 26w44a

- 重構了本地化系統，改進了大量翻譯；繁體中文現在區分臺譯和港譯；Python API的版本也升級至3.0，各個模組的文字會收錄到自己的`i18n.json`檔案中
  - 在外掛面板中切換語言時，如果遇到UE編輯器本身未翻譯的語言（比如繁體中文），會彈出提示框：是否複製當前語言包（比如簡體中文）作為回退。這能避免直接退到英文
  - Mineprep的簡體中文代號從`zh-Hans`改為`zh`，使得繁體中文能沿著“zh ← zh-Hant ← zh-Hant-HK”這條鏈回退。
  - 舊的 bilingual('中文', 'English') 函式可以無縫升級為`i18n('中文', 'English')`。更簡潔的寫法是`i18n('中文')`或`I18N('English')`
  - i18n能在執行時自動檢測模組位置並收集文字，每個模組有獨立的名稱空間
  - i18n返回unreal.Text，可以使用.format()方法進行格式化。[官方文件](https://dev.epicgames.com/documentation/unreal-engine/text-localization-in-unreal-engine?lang=zh-CN)介紹了高階用法，例如"There {NumCats}|plural(one=is,other=are) {NumCats} {NumCats}|plural(one=cat,other=cats)"
  - 修改i18n.json後，需要使用頂部選單欄的“重新載入 Python API”或mineprep.reload()來重新整理快取
  - 直接呼叫`PropertyGroup.localize()`能收集整個屬性集的文字，它相當於以英文變數名作為主語言的PropertyGroup.localize(I18N)
  - 關於自訂檔案路徑、namespace和key的更多用法見[Mineprep Wiki](https://github.com/piggestpig/Unreal-Mineprep/wiki/Mineprep-Python-API)
  - 安裝最新的實驗性功能後，註冊本地化文字的速度更快

> 如果要找出Mineprep裡最大的屎山，非本地化系統莫屬。現在所做的工作都是在給它打補丁，已經搞出3套不同的系統了qwq

> UE自帶的本地化控制板非常難用，總是收集不到文字，甚至還要編譯，我至今沒搞明白 為什麼給人看的文字需要編譯 (⊙ˍ⊙)？相比之下，Polyglot真是神中神，不僅能動態注入翻譯，還可以修復引擎自帶的機翻。只可惜，前兩年我從未聽說過它，在手搓翻譯的道路上一去難反

> 除了錯誤的開端，平時偷懶的迴旋鏢也打自己頭上了 (ﾟДﾟ≡ﾟдﾟ)!? 以前手寫程式碼的時候為了省事，在藍圖裡搞“簡單中英文選擇器”，在Python裡搞bilingual函式，把程式和翻譯寫在一起。現在有了AI，一下子寫出幾十個檔案，上萬行程式碼，我要去裡面找文字，哇，眩暈癱坐！

> 這次新增的i18n解決了兩大難題，一是自動收集文字，二是快速增加新語言。可惜的是，藍圖裡的舊本地化系統耦合太深，目前動不了，希望Mineprep 1.0的時候能徹底重構藍圖吧

- 更新了MC世界生成器模組
  - 新增類似於MiEX的LOD功能，可以用2x2或4x4的較低精度生成世界。左鍵畫方框挖空區域，右鍵畫方框設定核心區域；核心內採用1x1高精度，核心外採用2x2或4x4低精度。啟用LOD將小幅加快生成速度，大幅減少實例數、提高渲染效能
  - 新增繪製自訂紋理的功能，包括高度圖、植被分佈、留空區域、生態域分佈圖
- 修復了一些舊方塊模型，將原點居中，塗上頂點色
- Mover Pawn NPC現已支援攀爬和可變重力方向
- 修復了匯入MC結構時，若生成的紋理尺寸為2的冪，會使GPU場景損壞的bug。我直接關閉了稀疏結構紋理的Mipmap和紋理流送。


### 0.7-pre1

![image](https://raw.githubusercontent.com/wiki/piggestpig/Unreal-Mineprep/image/0.7-pre1%E5%B0%81%E9%9D%A2%E5%9B%BE.jpg)

Mineprep 0.7-pre1現已釋出！這是首個支援UE5.8的版本，主題為“洞穴與山崖”

從這個版本開始，我們改變了更新策略：預覽版不必嚴格按照版本號遞增，會以更高的頻率釋出，其穩定性介於大版本和快照之間。快來看看最新的內容吧：

<details>
<summary> MC世界生成器 </summary>

MC世界生成器是迄今為止最大的模組，旨在高效能地生成地形和生態域。得益於Python的簡潔性，模組分發大小僅為1.6MB

![image](<https://raw.githubusercontent.com/wiki/piggestpig/Unreal-Mineprep/image/MC世界生成器.jpg>)

模組依賴一部分藍圖資源，至少需要安裝Mineprep精簡版才能正常執行。

當前有3個資源包和24個全域性預設：
- **主世界**：預設 | 預設+洞穴 | 草原 | 混合林 | 白樺林 | 針葉林 | 冰雪針葉林 | 莽原 | 山地 | 沙漠 | 惡地 | 雪地 | 冰刺 | 海洋 | 寒凍海洋
- **地獄**：預設 | 所有生態域 | 地獄荒原 | 靈魂砂谷 | 緋紅森林 | 扭曲森林 | 玄武岩三角洲
- **終界**：預設 | 主島-虛空-外島

推薦用法是“生成預覽” → “準備資源” → “放置到場景”，也可以一鍵點選放置到場景

預設生成方式是4進程+PCG實例化方塊，渲染前建議設定CPU暖場影格。首次“準備資源”會花一段時間匯入方塊，之後能複用快取

0.7-pre1的封面圖就是用它製作的2048x2048場景，使用預設種子42，你可以快速復刻這個世界！

第一代模組由GPT 6 Astra、6.1 Sol，Claude Opus 5.5和Gemini 4 Argon開發。我們將持續使用前沿模型改進和重構內容

下一階段將圍繞動畫渲染製作更多實用功能，包括自訂地形、LOD、更好的UI介面與提示文字

</details>

<details>
<summary> 生態域顏色紋理 </summary>

MC世界生成器能夠繪製生態域顏色，並儲存為紋理貼圖(BCT)。

我們改進了方塊材質，使PCG實例化方塊/動態結構粒子能使用獨立的生態域紋理，在平移、旋轉、縮放時保持整體著色。

生態域紋理目前有兩種模式：正數表示RGB倍率，負數絕對值表示HSV偏移。預設用於染色的樹葉和草，可以透過“重載生態域ID”變數的小數部分疊加到整個材質。你甚至可以將渲染目標或影片紋理用於生態域著色！

</details>

<details>
<summary> 效能與記憶體最佳化 </summary>

匯入大型結構的速度快至6倍，同時新增`分組`參數，解決了單個PCG actor最多支援256種方塊的限制，還能減少Niagara粒子的實例總數，大幅提高渲染效能

</details>

<details>
<summary> 新一代Mover Pawn NPC </summary>

所有NPC生物已升級為Mover Pawn，並更新了來自UE5.8的運動匹配官方範例。未來將提供更多新功能！

</details>

<details>
<summary> 像素標題生成器 </summary>

這個新模組能從Blockbench的Minecraft Title Generator外掛下載資源，生成大標題模型，將整個流程整合在虛幻引擎裡！我們用其製作了0.7-pre1的封面圖

</details>

<details>
<summary> 新版自訂快捷鍵 </summary>

自訂快捷鍵系統經過重構，已經變成模組，支援Python程式碼和藍圖函式這兩種程式設計方式，並修復了在UE5.8中產生衝突的快捷鍵

</details>

<details>
<summary> 📜展開快照 </summary>

#### 26w42a
- Mineprep 0.7-pre1即將釋出，這裡記錄了最後的更新內容
- `MC世界生成器`模組已合併進主分支！
- 匯入MC結構時新增`分組`參數，解決了單個PCG actor最多支援256種方塊的限制，還能減少Niagara粒子的實例總數，大幅提高渲染效能
- 優化了匯入大型結構的效能和記憶體佔用，實測速度快至6倍
- 新增`生態域顏色紋理`(BCT)，目前由“MC世界生成器”模組繪製，推薦用於PCG實例化方塊與動態結構粒子
  - 每個Actor能使用獨立的生態域紋理，在平移、旋轉、縮放時保持整體著色
  - 生態域紋理目前有兩種模式：正數表示RGB倍率，負數絕對值表示HSV偏移
  - 預設用於染色的樹葉和草，可以透過“重載生態域ID”變數的小數部分疊加到整個材質
  - 實際上，你可以手繪生態域貼圖，甚至換成影片紋理/可變的渲染目標！
- 所有NPC生物已升級為mover pawn，並更新了來自UE5.8的運動匹配官方範例
  - 新一代mover pawn相容以前的絕大多數功能，但是尚未經過充分測試，暫時沒適配可變重力方向。
  - 只有安裝了實驗性功能後，才能把骨骼網格體參數顯示在整個actor的細節面板中。這一功能早在UE5.7就做好了，目的是讓模型保持一致，並且能直接調整頭部的動畫和材質
  - 未來會改進NPC參數，並嘗試利用官方提供的行為樹、智慧物件、Ragdoll等範例內容
- 新增`像素標題生成器`模組，從Blockbench的Minecraft Title Generator外掛下載資源，用於生成大標題。0.7-pre1的封面圖完全在虛幻引擎中製作！
- 改進了安裝程式，現在會寫入DDCVar和GameplayTag，能設定自訂資源包路徑（勾選後預設把素材複製到專案檔裡），並關閉後臺CPU節能
- 改進了Mineprep Python API，最大的亮點之一是能離線呼叫函式，在沒有unreal模組的情況下進行測試了
- 改進了模組管理器，現在能打包模組了
- 模仿Blender製作了`mod_manifest.toml`，可配置paths_exclude_pattern等進階元資料，便於打包和遷移
- 更新了本地化翻譯；接下來會重構整個Python API的本地化系統
- 修復了自訂快捷鍵在垃圾回收後失效的bug
- 修復了鏡頭試拍錄製器啟動後立即中止的bug

#### 26w41a
- 本週在兩方面取得了巨大進展，雖然內容尚未推送至github，但有望在下週釋出0.7-pre1了！
  - 0.7版本的主題是洞穴與山崖，核心功能為`MC世界生成器`模組
  - 成功遷移出UE5.8的運動匹配官方範例，功能更強大，刪除無關內容後，檔案體積也和現在相近
- 改進了layout.prop，皮膚&表情編輯器不再依賴藍圖資產了
- 所有方塊的原點改為中心，便於旋轉和numpy向量化操作。現有模型可能尚未更新，匯入新方塊時會檢查元資料並列印警告
- 匯入結構現已支援水平面上的任意角度旋轉+基岩版拼圖方塊的24種旋轉
- 改進了LabPBR材質，現在能正確顯示各自旋轉後的方塊實例了
- 修復了匯入紋理時 藍色圖片被錯誤當成法線貼圖的bug。編輯器仍會彈出提示，但mineprep會自動修正
- 【實驗性功能】修復了準備紋理時，因打斷首次編譯造成影像失效的bug。目前僅在“MC世界生成器”模組中復現過此現象，並為其設計了備用解決方案

#### 26w40a
- `自訂快捷鍵`系統經過重構，已經變成模組，支援Python程式碼和藍圖函式這兩種程式設計方式，並修復了一部分有衝突的快捷鍵。
- 頂部工具欄的MC選單中新增`核心模組`，存放比較重要的模組。
- 清理了舊的藍圖和C++函式
- 更新了MC_Startup專案的滑鼠旋轉靈敏度。之前一直有非常奇怪的問題，把官方運動匹配角色遷移到另一個專案後，旋轉視角特別快。最近才發現，專案設定裡有個0.07的輸入倍率
- 第三人稱運動匹配角色已損壞。我們即將移植UE5.8的全新模板，並嘗試把NPC升級為Mover Pawn
- 改進了Mineprep Python API
  - 模組會在啟動時儲存tab_id，隨後能透過self.close()關閉面板。重新載入Python API終於能自動關閉所有舊模組了。
  - 新增`layout.splitter()`，用於建立可拖動的分割條。例如
  ```py
  mineprep.ui('''
  split = layout.splitter()
  split.first.border(color=(1,0,0,0.2), padding=3).title("1")
  split.second.border(color=(0,1,0,0.2), padding=3).title("2")
  ''')
  ```
  splitter在Layout類的基礎上提供了first, second, divider, get_ratio, set_ratio, solo這些成員，是新一代複合控制元件的典範。我們已經改進了幾個模組的UI介面。

#### 26w39a
引擎版本已升級至UE5.8，我們為Windows編譯了實驗性功能。先前設計的Lumen中等質量照明和霧螢幕空間散射也已可用

- 改進匯入結構的程式，最佳化記憶體和速度，支援新版nbt格式與基岩版的狀態資訊，修復床、樓梯、火把、柵欄門、壓力板、柵欄、玻璃板等許多方塊的異常
- 改進方塊實例材質，單個實例縮放時UV在一定範圍內能保持不變
- 修復了UE5.8放置Niagara粒子後渲染png/exr序列影格在最後一影格閃退的bug
> UE5.8.3已經徹底修復了這個bug，我們保留了相容舊版本的cvar

- 修復了實驗性功能朗讀滑鼠下文字閃退的bug
- 上傳了[Mineprep Skills](./实验性功能(C++)/Mineprep/Content/Python/mineprep-skills)，這是集開發和使用於一體的agent技能，需要配置Unreal MCP才能發揮全部功能
- Mineprep Python API和模組更新至2.0版本，根據新的設計理念進行重構和解耦，無需UI介面就能呼叫模組功能，並改善了許多細節
- Mineprep Wiki的教學序章已經更新，甚至有一鍵執行指令碼
- UE5.8大幅改進了HDR渲染管線！我們做了初步適配
  - 省流：在顏色子面板勾選“HDR”，依舊能所見即所得，甚至比以前更準確了
  - 後期處理體積中現在有Filmic和Standard ACES兩種模式。引擎預設的Filmic支援HDR了，各種小參和lut都能用於HDR畫面，但是不支援SceneColorMultiplier。Standard ACES則是渲染輸出使用的管線，和以前一樣接著用SceneColorMultiplier，雖然畫面一致，但是怎麼看都沒有Filmic好看
  - OCIO裡面的ACES更新至2.0版本了，加入了Rec.2100 HLG等更多色彩模式，等重構渲染輸出子面板的時候考慮加進來
  - 以前編輯器視口的亮度上限會隨顯示器變化，導致它和渲染輸出的亮度有所不同。現在能用 r.HDR.Display.OverrideOSMaxLuminance 1 重載亮度上限為1000nits，完美對齊輸出結果，即使顯示器本身的亮度上限不高，也能用筆記本/手機遠端連線電腦 監看高質量HDR畫面
  - 編輯器亮度等其他參數也變得不同了，總之顏色子面板已經適配了新版引擎，調色示波器也直接用自帶功能，舊的刪了

</details>


### 0.6-pre1
![image](https://raw.githubusercontent.com/wiki/piggestpig/Unreal-Mineprep/image/0.6-pre1%E5%B0%81%E9%9D%A2%E5%9B%BE.jpg)

Mineprep 0.6-pre1 是最後一個支援UE5.7的版本，主題為水域更新，我們用其製作了新的動畫影片《選一扇門，開啟你的MC之旅》

先來看看和大版本主題相關的更新吧：

<details>
<summary> 進階水體 </summary>

- 進階水體包含專用水面材質和水下後期處理效果，提供浮力、水波互動、自訂曲線區域等多種功能

</details>

<details>
<summary> 水坑貼花與LabPBR孔隙率 </summary>

- 使用水坑貼花在任意位置生成水坑和漣漪
- LabPBR的孔隙率參數現已實裝，它在此處被解釋為“吸水程度”，會減弱材質對貼花金屬度、高光度、粗糙度和法線的響應效果

</details>

<details>
<summary> 更多MC原版生物 </summary>

- 新增鱈魚、鮭魚、熱帶魚及其NPC生物。熱帶魚有不同的體型、花紋和顏色
- 全新的`MC原版生物載入器`模組能從Blockbench的CEM Template Loader下載所有生物模型，並綁定簡易的單層骨骼

</details>

<details>
<summary> 魚群粒子與大型群體 </summary>

- 魚群和鳥群粒子已加入生成器面板，它們在3D空間中運動，能檢測進階水體和環境碰撞
- 大幅改進了粒子群體和材質，支援新的力場效果、手持物品、眨眼等功能
- 使用`VAT頂點動畫工具`模組快速烘焙頂點動畫模型，可用於粒子群體、實例化靜態網格體、植被繪製或PCG散佈器

</details>

隨著UE5系列接近尾聲，我們開啟了迄今為止最大、時間跨度最長的底層重構。Mineprep 1.0 也提上日程了！

<details>
<summary> Python正如閃電般歸來 </summary>

- [Mineprep Python API](https://github.com/piggestpig/Unreal-Mineprep/wiki/Mineprep-Python-API) 經過完整重寫，不再是實驗性功能，並推動了外掛的現代化和模組化。下列功能都是基於Python實現的：

</details>

<details>
<summary> 原生的放置方塊/物品功能 </summary>

- 不需要Blender了！點選按鈕立即匯入模型

</details>

<details>
<summary> 匯入MC結構 </summary>

- 初步支援解析和匯入 .nbt / .mcstructure / .schem 檔案

</details>

<details>
<summary> 自動化 </summary>

- Mineprep Python API能夠執行大型程式構建場景
- 使用mineprep.panel()訪問外掛面板
- 使用@mineprep.asynctask建立非同步延遲任務
- 使用mineprep-skills讓AI操作編輯器

</details>

<details>
<summary> 模組 </summary>

- 模組是使用Python編寫的輕量級指令碼，體積小、功能強大、易於擴充套件。我們模仿Blender提供了建立UI介面的API，方便開發者和Agent快速迭代、製作新功能。[點選檢視內建模組](#模組)

</details>

除此之外，還有大量效能最佳化和bug修復。Mineprep 0.6、0.7、0.8都在同步開發中，接下來的版本號和更新節奏可能有所調整

<details>
<summary> 📜展開快照 </summary>

#### 26w35a
- Mineprep 0.6-pre1即將釋出，這裡記錄了最後的更新內容
- 新增鱈魚、鮭魚、熱帶魚的NPC生物。馬、鸚鵡、熱帶魚現在統一採用從陣列中隨機挑選皮膚的方法
- 新增[Python安裝指令碼](./Mineprep_installer.py)和`外掛更新與遷移`模組。重寫了configparser，支援虛幻引擎特有的帶“+”的條目。安裝時會自動啟用RemoteControl等更多編輯器設定
- 新增`MC原版生物載入器`模組，需要聯網使用，從Blockbench的CEM Template Loader下載最新的生物模型，匯入為骨骼網格體。從某種程度上來說，Mineprep已經支援所有原版生物了！
- 更新了本地化翻譯，新增`本地化翻譯控制板`模組
- 改進了“堆放方塊”素材，現在能設定任意方塊型別和權重，調整間距，隨機修改位置、旋轉、縮放，剔除重疊模型，極大拓展了功能。不僅適用於方塊，還能放置觀眾人群
- MC導播臺新增`後期處理體積框作遮罩場`參數，勾選後將高精度長方體區域作為遮罩場
- 半透明水材質支援遮罩層了
- 大幅改進了粒子群體和頂點動畫材質，適配手持物品、眨眼效果，並能用於實例化靜態網格體、植被繪製和PCG散佈器。
- 粒子系統現在會重新解釋“線性速度”和“角扭矩”這兩個力場，增強了實用性：
  - 將自身速度插值到目標線性速度
  - 將自身旋轉插值到角扭矩向量所指方向
- 更新了粒子互動場的用法，用整數部分表示粒子事件
  - 個位：互動動畫
  - 十位：生成一次子粒子
  - 百位：持續生成子粒子
  - 負數：殺死粒子
- 基於方形、曲線和影像的全域性粒子生成區域能投射到地面上了
- 頭身分離綁定基礎生物模型在烘焙骨骼網格體時會自動合併相同模型的材質插槽了
- 預設畫質配置關閉了DLSS光線重構。之前製作貓meme時，必須藉助光線重構得到清晰的半透明陰影；但在一般情況下，光線重構反而會降低效能，有時還會產生噪點與拖影
- 禮花粒子改用長方形飄帶
- 豬布林頭部使用和身體一致的皮膚
- 略微移動了村民的腿，避免在烘焙VAT模型時共用頂點
- 修復了部分四足NPC生物的頭身朝向問題
- 修復了烈焰使者動畫迴圈首尾影格不一致的問題
- 修復了中鍵點選放置生物按鈕，未能新增烈焰使者粒子的bug
- 修復了粒子群體渲染偏移的座標系相關問題
- 修復了藍圖在python初始化前呼叫函式的問題
- 由於現在啟用了Lumen命中光照，陰影處不再死黑一片，我們關閉了粒子群體材質的次表面散射，這能顯著提高效能

#### 26w34a
- 更新了`皮膚&表情編輯器`，在第二頁添加了繪製紋理貼圖的功能，提供寬手臂、細手臂、內層、外層等快捷按鈕，支援儲存紋理和匯出為png
- 更新了細節面板的本地化翻譯
- 更新了Mineprep Python API
- 改進了半透明水材質，使方塊側面也能產生水波
- 清理了表情動畫序列的多餘骨骼
- 修復了粒子群體的預設動畫速率


#### 26w33a
- 製作了首個`表情綁定`，適用於MC_Head_FaceX和MC_Head_Eyes，提供眼睛、眉毛、嘴巴的多功能控制點。可點選“頭身分離綁定基礎生物模型”細節面板中的按鈕新增分層綁定
- 製作了`皮膚&表情編輯器`模組，目前能顯示選中actor的身體材質和表情材質，便於修改


#### 26w32a
- 改進了匯入方塊模型的程式和材質，縮放實例時能像全域性座標那樣延展紋理
- 匯入結構新增`合併方塊`選項，可減少實例數，提升大場景效能
- 更新了生物模型的手部骨骼，手持物品現在綁定在hand_r和hand_l上
- 新增`通用物品`，可以透過更改紋理貼圖變成任意32x32的立體模型
- 製作了左/右手持有通用物品的獨立生物模型，用於烘焙頂點動畫，用於粒子群體
- 改進了“VAT頂點動畫工具”模組，烘焙動畫時能自動處理影格率和Rate Scale。頂點動畫材質能切換至通用物品模式
- 修復了匯入結構時方塊倒轉插入地面的問題
- 修復了“頭身分離綁定基礎生物模型”無法清空頭部和還原材質的bug，以及烘焙骨骼網格體時錯誤轉換手持物品頂點色的bug


#### 26w31a
- 大幅改進了匯入MC結構相關功能
  - 支援新舊兩種schematics格式，根據字尾名區分新的.schem和舊的.schematic
  - 修復了門、柵欄、半磚、床、玻璃板等方塊的匯入問題
  - 移除了草方塊側邊的重疊面
  - 改進材質，使用實例化方塊、PCG和粒子時，能對齊全域性的木板紋理。單個方塊依舊會使用本地旋轉
  - 加強內部剔除效果，等級3能剔除底面和側面方塊
  - 顯著提升匯入速度
- 生成器子面板新增`強制重新匯入模型`勾選框，適用於方塊、物品和結構
- 修改了所有頭部模型的朝向，單獨放置時面向X軸。新增`MC_Head_Simple`，頂點數最少，將用於VAT實例模型
- 調整了PCG生成的CPU模型，修復了UE5.8的效能問題
  - 我們發現UE5.8會每影格重建mesh card導致影格數大幅下降。注意到，r.LumenScene.SurfaceCache.CardMinResolution的預設值從4變成2。改回去後，攝影機靜止時影格數提升，但移動時仍然很卡
  - 目前的解決辦法是關閉動態間接光照。這一改動和GPU模型同步，因為GPU模型本身不支援動態間接光照。好消息是，它對畫質的影響很小，因為現在預設使用Lumen命中光照，始終會計算第一次間接光照。
- 其他功能子面板的“雙面”勾選框改為“動態間接光照”，支援雙擊文字執行。使用Lumen命中光照時，甚至可以關閉全場的動態間接光照，畫質幾乎不變，效能有所提升


#### 26w30a
- 本週製作了第一個可用的模組：`VAT頂點動畫工具`，提供了當前迫切需要的功能，它即將投入實際生產，用於最新的動畫影片！
  - 支援從骨骼網格體建立資料資產、烘焙動畫紋理、複製資料資產
  - 整個流程高度自動化，切換資產時會自動載入已有動畫序列，十分便捷
  - 我們更新了所有粒子群體的動畫資料集
> 這個模組採用了全新的開發流程，由Agent使用UE5.8 MCP伺服器讀取藍圖程式，再透過Mineprep Python API編寫指令碼，最後遷移回UE5.7。整個流程非常高效，我甚至建立了Mineprep Skill和MCP擴充套件工具，等升級引擎後納入外掛中

> 該模組的前身分為兩部分：首先是[AnimToTextureHelpers](https://github.com/kromond/AnimToTextureHelpers)，這個外掛能烘焙標準的頂點動畫紋理，之前未包含在Mineprep中；然後是我們自己做的“烘焙VAT資料資產”面板，它能調整紋理貼圖用於統一粒子群體，必須配合AnimToTextureHelpers使用。現在，兩個板塊合二為一，完全python化了！舊面板已從頂部選單欄移除
- “頭身分離綁定基礎生物模型”添加了烘焙骨骼網格體功能，可以把頭身+手持物品烘焙到一起。我們即將為所有生物提供一體化模型。
- 之前更新的實驗性功能 已支援在骨骼網格體Actor的細節面板中顯示頭部模型和材質。因此，單獨的“頭部模型”變數已被移除，同時修復了手持物品方向相反的bug。
- 修復了植物搖擺錯誤使用單面材質的bug
- 修復了UE5.8右鍵藍圖資產看不到“指令碼化資產行為”的bug
- 修復了快捷鍵面板，上週由於Mineprep Python API更新而損壞。現在mineprep.PropertyGroup必須先實例化再使用，每個Mod可以在__init__中生成獨立的屬性集，支援同時開啟多個面板

#### 26w29a
- 本週更新了MC資源包，支援26.2版本的最新方塊和物品，並重新校對了中文名。開發外掛所用的Blender版本提升至5.2，MCprep版本提升至3.6.3
- 繼續開發Mineprep Python API，製作了`模組管理器`，實際上，它本身就是一個模組！目前支援啟用、停用、安裝和解除安裝其他模組。
- 修復了放置物品時法線翻轉的問題
- 修復了方塊體積雲材質，避免在UE5.8啟動時閃退
- 修復了在GPU上匯入MC結構時，因為跳過失敗的方塊而發生型別錯亂的問題。
> 這場轟轟烈烈的Python大開發暫時告一段落，接下來我們將回歸動畫，回到Mineprep 0.6-pre1的主線上來

> 很長一段時間裡，我都在使用vscode copilot寫程式碼，它的按次計費和學生優惠特別划算，是實驗性功能的大功臣。可惜到今年6月被徹底砍廢了，用不了一點 o(TヘTo)   
> (為copilot默哀3秒鐘)

> 但是完全不必擔心，接下來將要登場的是cursor！我天呢 它這個20刀的pro會員怎麼那麼多額度，還會重置，還有半價優惠，尤其是自家的Composer2.5和Grok4.5，根本用不完（⊙ｏ⊙）過去一個月越用越上頭，光是Mineprep這邊就寫了匯入方塊、匯入物品、匯入結構、開發模組、本地化翻譯等諸多內容，還有好幾個專案齊頭並進，最後花了90%的額度，也算是物盡其用了~


#### 26w28a
- 本週為Mineprep Python API添加了許多功能，支援像Blender一樣建立UI介面，同時為“模組”打下基礎。展望未來，我們將以模組的形式提供擴充套件功能，這不需要重新安裝外掛，而且體積小、開發快
- 由於Mineprep Wiki一直沒更新，這裡將直接展示幾個python範例。在命令列中執行mineprep.ui函式，即可快速建立ui介面：  
  `mineprep.ui("""`
  ```py
  layout.text("第1行文字")
  layout.text("第2行文字")
  row = layout.row()
  row.text("并排文字1")
  row.text("并排文字2")
  """)
  ```
- 用PropertyGroup定義參數集，它會自動註冊，隨後能在別處使用：  
  `mineprep.ui("""`
  ```py
  class MyProps(mineprep.PropertyGroup):
    a: int
    b: int = 1
    c = 1
    d: float = (0, {'UIMin': 0, 'UIMax': 10})
    e: str = "Hello, Mineprep!"
    f: unreal.Object
	
  my_props = MyProps()
  layout.prop(my_props, "a", "整数")
  layout.prop(my_props, "b", "整数，带默认值")
  layout.prop(my_props, "c", "整数，从默认值推断类型")
  layout.prop(my_props, "d", "小数，通过 (值,meta字典) 定义元数据")
  layout.prop(my_props, "e", "字符串")
  layout.prop(my_props, "f", "对象")

  layout.button("点击打印字符串", align=(1,1),
    on_clicked=lambda: mineprep.prints(my_props.e)
  )

  #显示所有属性
  layout.prop(my_props)
  """)
  ```
- 編寫大型程式時，可以使用mineprep.Mod類和其中的self.layout，在建立實例時自動註冊UI介面：
  ```py
  class MyMod(mineprep.Mod):
    def draw(self, context):
        layout = self.layout
        layout.text("在类中编程能看到IDE提示")

  MyMod()
  ```  
  如果模組不需要UI介面，可以重載__new__方法，此時self.layout的預設值為None
- 快捷鍵提示面板現已改用Mineprep Python API編寫，不再依賴tkinter，理論上能在Mac和Linux上顯示。點選第一列的按鈕可直接觸發快捷鍵，即使未安裝實驗性功能也能這樣“使用”它了。整個視窗可停靠在任意位置，底部的滑塊能調整UI介面縮放
- 由於UE5.7缺少關鍵的編輯器函式，現在無法保證UI介面唯一存在，我們將在UE5.8完善整個模組系統。


#### 26w27a
- 改進了匯入世界功能，現在始終會自動準備場景，此選項已隱藏。匯入nbt/mcstructure/schematics時，能選擇內部剔除和匯入方式（CPU實例化方塊 / GPU PCG / GPU粒子）
- 新增`動態結構粒子`，由動態地形粒子簡化而來，從MC結構紋理中讀取方塊的位置和旋轉，非常高效，並且能和效應器一起使用。
- 繼續開發Mineprep Python API，加入了sequencer/關鍵影格等功能
- 修復了單面材質啟用植物搖擺時的陰影問題
- 修復了外掛啟動時未註冊快捷鍵的bug
- 修復了爆炸粒子和營火煙霧粒子無法錄製快取的bug。烈焰使者粒子仍然保留輕量級發射器


#### 26w26a
- 在匯入世界的選項中新增了實驗性的`nbt`，`mcstructure`和`schematics`選項。本週重點改進了匯入程式，但是仍然有一些問題
  - 匯入單個方塊會使用特製的單面材質。這解決了花草有重疊面的問題，但是植物搖擺仍會向自身投射陰影
  - 能自動識別動畫紋理，使用二級動態材質了
  - 初步支援匯入水方塊，目前使用不透明材質
  - 自動跳過無法匯入的方塊，不再中斷整個程式
- 改進了統一粒子群體，包括更好的動畫系統和基於HLSL的材質。目前最直觀的新功能是增加了`裝備`參數，可以疊加第二個動畫模型
- 修復了MC天空在啟動時異常載入其他資源的bug
- 修復了對染色玻璃替換半透明材質時錯誤設定不透明度的bug
- 將在下週修復另一個新發現的bug：爆炸粒子等使用輕量級發射器的系統無法錄製快取


#### 26w25a
- UE5.8釋出了！據說這是UE6之前的最後一次大版本更新。我們預計在兩週後釋出動畫影片和Mineprep 0.6-pre1，然後更新至5.8版本
> UE6要等2027年底才出預覽版，中間有這麼長的空窗期，我們吃什麼？  
> 是啊，吃什麼？  
> 是時候把Mineprep 1.0提上日程了！
- 繼續基於Mineprep Python API開發新功能，並最佳化外掛效能
- 選中多個方塊 使用“更換模型（實例化）”，會把每種型別合併為“實例化方塊”。如果勾選了“分割為獨立的Actors”，則會拆分回去
- 修復了匯入火把等方塊時模型破損、UV顛倒的問題。不過，門和床這些特殊模型暫時無法正確匯入
- 正在編寫匯入MC結構的程式，有望支援nbt，mcstructure和schematics
  - 當前僅能透過python呼叫：`mineprep.spawn_structure(filepath='', loc=(0,0,0), rot=(0,0,0), gpu=False)`，下週會加入外掛面板
  - 預設情況下，會把每一類方塊匯入為“實例化方塊”
  - 如果使用gpu=True，會把方塊的位置和旋轉烘焙到兩張貼圖中，生成一整個“PCG實例化方塊”。這由遠景地形生成器改造而來，效能極好，但是無碰撞箱且容易消失，渲染開始時會重新生成

#### 26w24a
- 本週在虛幻引擎中編寫了放置方塊和放置物品的程式，點選後立刻生效，速度和穩定性大幅提升。至此，Mineprep的所有功能都可獨立執行，不再需要Blender了！
- Mineprep Python API 轉正了！儘管部分函式仍然需要實驗性功能才會生效，但是整個框架已不再依賴C++，支援精簡版和極簡版在內的所有版本
  - 使用方法：直接`import mineprep`，更多資訊見Mineprep Wiki
  - 除了原有的模擬點選功能，現在添加了許多專屬函式，並特地優化了效能，比如`mineprep.spawn_mob('Steve')`
  - 使用`@mineprep.asynctask`和`yield (秒數)`編寫非同步延遲函式，例如  
    ```py
    import mineprep

    @mineprep.asynctask
    def spawn_grid():
	    for i in range(10):
		    for j in range(10):
		      mineprep.spawn_mob('Steve', (i*100,j*100,0))
		      yield

    spawn_grid()
    ```
    這為複雜任務和自動化測試打下基礎。
  - 還有很多的語法糖！開發和使用效率空前提高
- “Mineprep自訂快捷鍵”物件下放到非實驗性版本
- 新增`實例化方塊`，下週將製作更多功能

#### 26w23a
- 本週大幅改進了畫質預設，提升全域性光照明並平衡效能。最直觀的感受是，日光可以照亮室內了!
  - MC導播臺的“畫質預設”改為從選項到等級的對映，可以自由組合各種選項
  - 選項分總畫質和重載預覽畫質兩類，小參會覆蓋大參。等級減少至5級 + 自訂（不重載）。
  - | 畫質選項 | -> | 畫質等級 |
    | :---: | :---: | :---: |
    | 【全域性預設】<sup>#佔位符</sup> |  | 0 低 |
    | ★總畫質 |  | 1 中 |
    | 引擎畫質級別 |  | 2 高 |
    | GI間接光照 |  | 3 極高 |
    | ★細節參數集 |  | 4 影視級 |
    | Lumen質量 |  | （自訂） |
    | Lumen距離 |  |  |
    | Lumen更新速度 |  |  |
    | Megalights質量 |  |  |
    | - |  |  |
    | 【重載預覽設定】<sup>#佔位符</sup> |  |  |
    | ⇛ 預覽畫質 |  |  |
    | → 引擎畫質級別 |  |  |
    | → GI間接光照 |  |  |
    | ⇛ 預覽細節參數集 |  |  |
    | → Lumen質量 |  |  |
    | → Lumen距離 |  |  |
    | → Lumen更新速度 |  |  |
    | → Megalights質量 |  |  |
  - 現在預設啟用Lumen命中光照，可透過GI間接光照控制，各等級如下所示：  
    0低：表面快取 + UE5.8的Lumen輻照場探針  
    1中：反射的命中光照 + UE5.8的Lumen輻照場探針  
    2高：反射的命中光照  
    3極高：命中光照  
    4影視級：命中光照
  > 還記得UE5.5的時候效能很差，現在好起來了，我再微調一下其他參數，影格數幾乎不變或略有下降。  
  > 之前過的什麼苦日子啊😭有了命中光照，逆光/室內照明/Mojang宣傳片風格都好做多了，淚目
  - 預設畫質為 ★總畫質：4影視級，⇛預覽畫質：3極高  
    在安裝包中勾選最佳化效能後，預設畫質為 ★總畫質：3極高，⇛預覽畫質：2高，→GI間接光照：1中  
    Lumen輻照場探針讓影格數在UE5.8直接起飛，不過它會造成大塊光影突變，只適合編輯器預覽，不適合渲染動畫
- 從底層重構了Mineprep Python API，繞過C++直接由Python注入Unreal模組。這一革命性改進有望從實驗性功能轉正，在相容舊語法的同時帶來更豐富的介面、泛型、熱重載。好東西就要來了！
- 修復了導播臺重載重力方向在XY軸超過1000時失效報錯的bug
    

#### 26w22a
- 改進了方塊雲和方塊體積雲，新增MC 1.21.9的新版雲朵紋理
  - 方塊雲改為實例化靜態網格體，透過2x2拼接擴大了面積，預設使用舊模型
  - 方塊體積雲現在能從紋理貼圖生成圓角雲朵，預設使用新版紋理，調整了密度和顏色使之更加好看，而且效能顯著提升
  - 節約儲存空間
- 製作了大量實驗性功能
  - 調色面板也有關鍵影格按鈕了
  - 能在日誌中列印全域性快捷鍵衝突
  - 新增一個捕獲後期處理階段到渲染目標的函式
  - 擴充套件Mineprep Python API介面
  - 擴充套件細節面板，自動檢測含mover元件的pawn型別角色，將骨骼網格體和材質參數顯示在整個Actor的細節面板中。我們預計在UE5.8升級NPC和第三人稱運動匹配角色，採用全新的mover移動器（也許還會上UAF動畫框架）
- 修復了統一粒子群體在靜止或保持直立時方向突變的bug
- 修復了觀眾人群散佈器的朝向
- 修復了LabPBR材質的貼花法線問題
- 修復了幾個極簡版安裝時缺少的素材

#### 26w21a
- 本週對生物、安裝包和實驗性功能進行大改造
- 開發了全新的放置生物寶寶功能，先嚐試放置新版幼年生物，沒有則按照老方法縮放成年生物
- 新增`熱帶魚`，有兩種不同模型，小的算作生物寶寶
- 修改了多層皮膚材質，“紋理顏色”參數只會影響內層，中間層和外層則由“覆層顏色”控制。目前用於村民和熱帶魚
- 重新整理了外掛結構，在安裝包中新增`僅安裝核心功能（跳過90%預設素材）`選項，勾選後進行極簡安裝，最小隻需85MB左右！
  - 修復了手動指定FFmpeg路徑在渲染時遇到的bug，此時也不再複製FFmpeg到外掛目錄，節約空間。預設路徑指向安裝包。
  - 極簡版僅包含外掛面板中的功能性按鈕+Steve/Alex基礎模型，剔除了絕大部分預設素材
  - 實驗性功能依舊可選，包含快捷鍵、關鍵影格等實用功能，非常適合其他非MC專案
  - 整理外掛結構可能產生bug，需要更多測試
- 改進了實驗性功能
  - 使用新的關鍵影格按鈕圖示，預設為空心，打關鍵影格變實心，操作時間線的程式從藍圖遷移至C++。不過，材質的紋理參數關鍵影格依舊使用老圖示，新圖示目前無法在移開播放頭時變成同心菱形
  - 添加了捕獲視口畫面的函式，之後會開發更多功能
  - 改進Mineprep Python API，詳見Mineprep Wiki

#### 26w20a
- UE5.8預覽版釋出了！非實驗性功能已適配UE5.8
  - UAF觀眾人群暫時固定為迴圈播放動畫，避免升級引擎後報錯
  - MC天空新增`霧螢幕空間散射`相關參數，能產生朦朧的背景模糊，且支援正交攝影機。需要UE5.8才能生效，目前不能打關鍵影格
- 繼續進行生物模型底層重構
  - 統一了頭部骨骼朝向，所有生物都能正確地使用面向目標功能
  - 修復了鸚鵡的縮放
  - 修復了MC_Bent和MC_Segment的模型
- 準備場景的“啟用碰撞”選項能同時調整GPU距離場碰撞箱了。修復了nDisplay3D攝影機組的預覽視窗帶有距離場碰撞箱的bug
- 鳥群粒子預設使用白色鸚鵡皮膚
> 我們已經為UE5.8編譯了DLSS外掛，做好了升級準備！Mineprep 0.6-pre1預計在一個月內釋出，這將是最後一個支援UE5.7的版本  
> 今年的AI終於變聰明瞭，它能自動搜尋引擎安裝位置並讀取原始碼，不再憑感覺瞎改程式。我只需要說一聲編譯DLSS，它就會自主迭代直至編譯成功。看來以後能做更多實驗性功能了呢！

#### 26w19a
- 大多數生物模型已完成重構，統一面向X軸，接下來需要檢查動畫片段和NPC是否正常
  - 保留了一個_MC_Retarget_模型面向Y軸，用於動作重定向。更好的方法是在匯入動作捕捉片段時直接旋轉90°面向X軸，這樣就能重定向到任意MC模型了
  - 生成器子面板的生物寶寶也需要重構，適配 MC 26.1 新增的幼年生物模型；同時，熱帶魚有兩種不同的模型，小的那個也將算作生物寶寶
- 新增`鱈魚`，`鮭魚`和`魚群粒子`。將魚群粒子放在“進階水體”之下，可以限制它們的活動區域
- 新增MC人模的頂點動畫實例模型和`觀眾人群粒子`。實際上，我們已經有能力為所有生物製作頂點動畫和粒子群體了！

#### 26w18a
本週開始對生物模型進行新一輪底層重構：
- 主要任務是把大部分生物從面向y軸改為面向x軸。在此之前，朝向問題已經出現過很多次，像粒子群體、mover移動器、騎乘等功能經常需要打補丁或手動調整。不如從源頭上搞定吧
- 同時，修復部分生物的頭頸旋轉和動畫錯位問題
- 後續會為頭身分離模型補充一體化模型，用於觀眾人群和粒子群體
- 頭部模型暫時不做調整，等未來製作更好的表情功能
> 從Y軸改到X軸，聽起來簡單，做起來麻煩qwq  
> 現有的動畫片段和重定向器不會自動旋轉，必須一個個手動調整...  
> 直接回Blender從源頭重新匯出模型吧

#### 26w17a
本週製作了`進階水體`，功能全方位超越之前的`可互動2D水面`
- 進階水體包含水面材質和水下後期處理材質，放置在普通水面上會直接覆蓋它
- 透過調整“波源”參數製造波浪
- 支援在攝影機附近與物體互動，具體範圍和精度位於專案設定的“淺水模擬參數”中
- 預設情況下，NPC和玩家在水中移動會自動產生水波；基礎生物模型需要透過“附加元件”功能新增碰撞tag；部分粒子系統添加了`與水體碰撞互動`選項，勾選後能產生水波；方塊則有單獨的互動設定
- 方塊添加了`水體互動&漂浮`參數，裡面可以設定啟用浮力、互動水波、漂浮點位等參數
> 由於水面材質和互動範圍不同，“可互動2D水面”依然保留

> 我們的開發重點將轉移至具有MC特色的像素水。如果需要高階流體模擬，可以搜尋第三方水外掛，UE5有很多超棒的外掛
- 進一步優化了MC天空的效能
- 【實驗性功能】按快捷鍵 Shift+` 將視口攝影機吸附到前方表面

#### 26w16a
Mineprep 0.6的主題已確定為“水域更新”！
- 新增`水坑貼花`，用於在特定區域生成地面的積水
  - 透過材質參數控制水面反射（金屬度/高光度/粗糙度）、噪聲、水波、漣漪等效果
  - 增大範圍至整個世界，可用於下雨天的地面積水
- MC材質現已支援`孔隙率`參數，實現了LabPBR標準的所有功能！
  - 孔隙率表示吸水程度，目前需要配合水坑貼花使用
  - 這個參數實際上會減弱材質對貼花的金屬度、高光度、粗糙度和法線的響應程度
  - 半透明材質不支援貼花，因此孔隙率沒有效果。其他材質正在改造中
> 孔隙率（Porosity）並非常見的PBR參數，官方文件也沒講清楚，應該是MC特有的東西。  
> 它竟然和次表面散射打包在一個通道里，還區分金屬和非金屬，真是絞盡腦汁也想不明白啊()  
> 忽然，我有了一個絕妙的點子，如果用貼花來製作積水效果，就能控制吸水程度了嘛 ✧٩(ˊᗜˋ*)و✧
- 優化了一級動態材質的效能
- 優化了MC天空在編輯器視口拖拽和旋轉的效能
- 為Lumen啟用了螢幕空間反射，否則水坑反射已遮罩材質時會顯示為藍色的天空。（之前好像發現螢幕空間反射有些問題，把它關掉了，現在需要更多測試）
- 修改了2K_120.mp4渲染預設，使用exr作為中間圖片格式。之後的動畫影片都會用16bit原圖來編碼10bit影片
- 每週快照都會更新一部分Mineprep Wiki的內容

</details>

### 0.5 : 荒野更新
![image](https://raw.githubusercontent.com/wiki/piggestpig/Unreal-Mineprep/image/0.5%E5%B0%81%E9%9D%A2%E5%9B%BE.jpg)

Mineprep 0.5 正式釋出了！這是首個支援Windows、MacOS和Linux的跨平臺版本，實驗性功能適用於UE5.7

經過一年多的開發，外掛在各個方面都有了重大更新，我們製作了4段動畫影片，工作室賬號也取得了萬粉的成就

你可以前往[Mineprep Wiki](https://github.com/piggestpig/Unreal-Mineprep/wiki)檢視新手教學，或者在[討論區](https://github.com/piggestpig/Unreal-Mineprep/discussions)進行交流。我們已經根據5個社群反饋改進了許多功能，在此表示感謝！

快來看看有哪些新內容吧：

<details>
<summary> 所有核心功能都得到了初步實現 </summary>

- Mineprep 0.5 終於有了
`匯入世界`和`更換模型（實例化）`按鈕，分別對應MCprep的“OBJ world import”和“Mesh Swap”功能
- 同時，我們正在參考Blender製作Mineprep Python API。安裝實驗性功能後可以使用Python訪問外掛面板的每個按鈕

</details>

<details>
<summary> 支援LabPBR標準的MC材質 </summary>

- 近幾年的MC紋理包大多采用[LabPBR](https://shaderlabs.org/wiki/LabPBR_Material_Standard)標準，Mineprep現已支援除了孔隙率之外的所有特性！
- 新版材質還有更多實用功能，比如半透明、遮罩層、ping-pong動畫和多層生物皮膚等

<sup>*孔隙率用於下雨積水時的潮溼效果，這將在Mineprep 0.6（水域更新）中得到支援</sup>

</details>

<details>
<summary> 程式化生成MC地形 </summary>

- `遠景地形生成器`和`動態地形粒子`能在GPU上高效地生成MC地形！它們的效能和開發進度都遠遠超出預期，是本次更新的最大亮點之一
- Mineprep 0.5的封面圖就是用遠景地形生成器製作的
- 新的動畫影片《？！Bad Apple！？》使用動態地形粒子，可以即時播放

</details>

</details>

<details>
<summary> 更多MC原版生物 </summary>

- 新增*蠹魚、終界蟎、蜘蛛、洞穴蜘蛛、村民、烈焰使者、凋零怪、豬布獸、雪人、狼、貓、悅靈、流浪商人、山貓、地獄幽靈、小幽靈、快樂幽靈、苦力怕、鸚鵡、駱駝、駱駝屍殼、枯骸*
- 使用控制綁定、物理互動、批次播片等多種方式製作動畫
- 重新設計了NPC生物，支援隨機重新整理皮膚和更多運動模式
- 部分生物具有騎乘槽位，並且能夠疊高高


</details>

<details>
<summary> 大統一粒子 </summary>

- 我們設計了MC粒子模板，更新了大量現有的粒子系統，提供統一的基礎參數和實用功能
- 使用`全域性粒子生成區域`在任意位置生成粒子
- 使用`全域性力場`及其衍生的“粒子互動場”、“動畫偏移場”控制粒子系統
- 使用`全域性區分ID`召喚子粒子，把多個系統聯絡起來
> 目前採用這一模板的粒子系統有：*下雨粒子、下雪粒子、噴濺藥水粒子、灰塵粒子、爆炸粒子、爆裝備粒子、愛心粒子、落葉粒子、禮花粒子、粒子自碰撞、統一粒子群體（蟲群粒子、蜘蛛群粒子、鳥群粒子、螢火蟲粒子、媒體摳像粒子）*



</details>

<details>
<summary> 更多渲染輸出格式 </summary>

> 由於引擎自帶的H.264和ProRes編碼器只在Windows上可用，我們大幅改進了ffmpeg編碼配置，支援MacOS、Linux和高階輸出格式

- 影片編碼：H.264、H.265、AV1、ProRes
- 圖片編碼：jpg、png、exr、gif、webp、avif、jxl
- 正確的HDR色彩管理流程，渲染所見即所得的畫面
- 更多3D輸出格式
- 分層渲染

</details>

<details>
<summary> 改進使用者體驗 </summary>

- 修復了許多bug並最佳化效能；同時UE5.7的材質參數面板不再閃退，這是近期最穩定的一代外掛
- 安裝包提供更多選項，可以選擇精簡版，顯示所需空間，降低預設畫質等
- 外掛面板和預設素材有更多本地化翻譯
- 正在編寫新手教學，詳見[Mineprep Wiki](https://github.com/piggestpig/Unreal-Mineprep/wiki)

</details>

<details>
<summary> 📜展開快照 </summary>

#### 0.5-RC4

- 這是Mineprep 0.5最後一次計劃外的更新，主要根據[社群討論](https://github.com/piggestpig/Unreal-Mineprep/discussions)中的反饋修復了一些bug並改善使用者體驗
- 放置方塊和放置物品現在有中文翻譯了，選中物品旁邊還能顯示縮圖
- 為“匯入世界”添加了`匯入到世界原點`選項，修復了放置模型錯位的bug
- 匯入世界後將在大綱中建立同名資料夾，收納匯入的模型
- 準備場景現在能保護特殊名稱的材質，比如背景天空等非LabPBR材質：若材質名以“-”開頭，則跳過它；若材質名以“+”開頭且是材質實例，則用它建立新的動態材質實例
- 外掛面板的材質參數現在能用於實例化網格體
- 遠景地形生成器取消勾選在GPU上生成，能自動停用草的CPU碰撞箱
- 為許多生物添加了騎乘槽位
- 新增`鳥群粒子`和鸚鵡的頂點動畫實例模型。實際上我們還做了魚群粒子，但是現在沒有魚的模型，要等到Mineprep 0.6（暫定為水域更新）才會加入生成器面板
- 渲染SDR影片也可以使用exr作為中間圖片格式了，這將充分利用16bit高色深，比8bit png更好。我們將在Mineprep 0.6的第一個快照更新渲染預設
- MacOS預設使用VSM虛擬陰影貼圖。光追陰影在測試時始終不支援Alpha遮罩
- 【實驗性功能】為MacOS初步適配了3D渲染，不需要nDisplay 3D攝影機組，但是當前不支援分層渲染等功能，也可能存在bug。Windows/Linux使用者可以雙擊“3D”文字來使用這個實驗性功能，此時VR前面的勾選框會打上橫槓
- 【實驗性功能】VR+3D渲染支援全部四種立體格式了，但是目前使用多層exr和引擎內建的影片編碼器會有bug
- 【實驗性功能】製作了第一代Mineprep Python API，旨在像Blender一樣為每個可互動按鈕提供python介面，便於編寫指令碼和自動化測試。更多內容詳見Mineprep Wiki
- 使用安裝包“新建UE專案檔”，能輸入專案檔名稱了
- 安裝時可以選擇`最佳化效能，降低預設畫質`
- 安裝外掛時會在專案配置中顯式啟用網格體距離場
- 外掛初始化時將開啟編輯器偏好設定選單，載入一些配置
- 修復了NPC生物在待機機率為0時一直不動的bug。這背後修復了與狀態樹過渡有關的更多機率問題
- 修復了“處理錄製的動畫”未能生成場景中現有方塊被破壞後的粒子軌道的bug。此功能現在會自動執行，已經從外掛面板中移除
> 小故事：
> 檢視[社群討論](https://github.com/piggestpig/Unreal-Mineprep/discussions)，獲取和本次更新有關的更多資訊！

> 在生成器子面板中，方塊和物品的名稱是從資源包裡讀出來的，總共有三千多個英文名，很長一段時間都沒有翻譯。但是，現在已經是2026年了，我忽然意識到，可以開幾個agent去找譯名嘛！

> 正好上個月的copilot額度還有剩餘，我把各種模型都試了一遍，發現最貴的Claude Opus 4.5質量最好。它先從網上找標準譯名，再寫python指令碼，最後自己校對，把翻譯率提高到90%以上。雖然有一些問題，但是總算能用了

> 翻譯完成後，copilot額度還有剩餘，那就再幹點什麼吧！  
> 如今AI快速發展，命令列強勢迴歸，CLI正在變得比GUI更有效率。要是能像Blender那樣，給外掛的每個按鈕提供Python介面，就能讓AI寫指令碼進行操作了。  
> 於是我又設計了鏈式呼叫語法，第一代Mineprep Python API誕生了 \\^o^/

> 做完這個工作後，copilot額度還有剩餘，這麼好的機會不能浪費，不如...讓AI修一下MacOS的3D渲染吧。  
> 一開始我想編譯nDisplay外掛，但是改到後面發現缺少Nvidia之類的依賴項，看起來沒辦法解決。然後我又讓它改VR渲染外掛，把其中的3D渲染拆出來，這個明顯簡單多了。  
> 當時已是半夜，我提完要求，掛上autopilot自動審批，直接睡了一覺，第二天一看，MacOS的3D渲染在一夜之間建成了！

#### 0.5-RC3
- 0.5-RC3按原計劃是最後一次快照更新，包含對粒子系統的重大改進
- 製作了`MC粒子模板`，提供統一的基礎參數和實用功能，並用其重置了大量粒子系統
  - 目前有三類基礎參數，所有采用MC粒子模板的系統都繼承了以下功能：  
    **① 粒子生成**：  
    生成速率/生命週期  
    粒子大小  
    全域性區分ID  
    生成區域大小  
    生成位置偏移  
    初始化批次生成  
    批次生成數/間隔時間  
    批次生成陣列  
    陣列XYZ數量  
    **② 力場**：  
    重載重力XYZ-權重W  
    全域性力場權重  
    全域性力場取樣型別  
    **③ 子粒子**：  
    召喚全域性子粒子  
    子粒子全域性ID  
    出生/死亡/碰撞/互動子粒子數  
    生命週期->每粒子每秒生成  
    數量曲線倍率-單次上限  
  - `全域性區分ID`更新為多選框，可以為一個粒子系統分配多個ID，具體內容詳見工具提示
  - `初始化批次生成`是一個布林參數，可以打關鍵影格，它會在每次從關到開的時候批次生成粒子。如果要多次觸發同一粒子系統，這個功能比“觸發器軌道”更好用
  - 勾選`批次生成陣列`，會根據陣列數量填充粒子網格，如果批次生成數太少則填不滿，生成數太多則會反覆填充
  - `子粒子`可以把整個世界中的粒子系統聯絡起來，製作互動事件。例如，場景中有下雨粒子和爆炸粒子，想讓雨滴落地時產生爆炸效果，只需要  
  ① 勾選下雨粒子的“召喚全域性子粒子”  
  ② 然後分配一個“子粒子全域性ID”（比如1）  
  ③ 接著調整“出生/死亡/碰撞/互動子粒子數”中的碰撞數量（>0）  
  ④ 最後在爆炸粒子中設定對應的“全域性區分ID”（包含1即可），它就能在雨滴落地時感受到召喚了！
> 分配ID時一定要注意，自己召喚自己可能使粒子數量指數級增長，幾秒內卡死引擎！！
- 新增`全域性粒子生成區域`，可以使用全域性區分ID在特定地點召喚粒子。預設是方形區域，更改粒子系統後，還有球形、影像、曲線、靜態網格體、骨骼網格體這些區域
- 新增`粒子互動場`，當前負數表示殺死粒子，正數表示在粒子進入該場的時候觸發子粒子互動事件，≥256會在場中持續觸發互動事件
- 新增`禮花粒子`，這是落葉粒子的改版，兩者都用上了MC粒子模板
- 更新了MC材質總類，一些粒子系統能對方塊染色了
- 新增`動態地形粒子`，由動態設計克隆器和遠景地形生成器改造而來
  - 每一影格都能更新地形，可以使用影片紋理作為地形貼圖，或者對生成參數打關鍵影格
  - 相容動態設計效應器，並提供了“建立連結效應器”按鈕
  - 比遠景地形生成器多一個“生態域貼圖”，目前是根據圖片對方塊染色，之後會更新更多功能
- 修復了導播臺的DLSS選項修改後無法儲存的bug
- 修復了統一粒子群體在攝影機遠離又靠近時重新生成的bug
- 修復了全域性力場啟用休眠物件時導致靜態碰撞失效的bug
- 可能是我更新了顯示卡驅動，ffmpeg的hevc_vulkan和prores_ks_vulkan影片編碼修好了，只剩下av1_vulkan卡住無法播放

#### 0.5-RC2
![image](https://raw.githubusercontent.com/wiki/piggestpig/Unreal-Mineprep/image/Mac%26Linux%E5%90%88%E5%BD%B1%E7%95%99%E5%BF%B5.jpg)
<sup><i> 歷史性時刻：Mineprep在 MacOS 和 Linux 上執行！ </i></sup>

- 本週我們租用雲電腦，在Mac和Linux實機測試安裝包與外掛，編譯了所有實驗性功能，並修復大量相容性問題。正巧這周破萬粉了，或許可以把Mineprep 0.5作為萬粉禮物釋出呢ヾ(≧▽≦*)o
- FFmpeg已更新至最新版master build，添加了prores_ks_vulkan編碼器。不過，所有vulkan編碼在測試時都有閃爍/破圖問題，暫時無法修復
- 新增12bit 4:2:0、12bit 4:2:2、12bit 4:4:4三種色度抽樣選項。CPU H.265編碼支援所有9種選項，其他GPU編碼可選的條目如下所示：

|   | 8bit 4:2:0 | 10bit 4:2:0 | 10bit 4:2:2 | 10bit 4:4:4 | 12bit 4:2:0 |
| :---: | :---: | :---: | :---: | :---: | :---: |
| Nvidia | ✅ <br> nv12 | ✅ <br> p010le | ℹ️僅50系 <br> p210le | ✅ <br> yuv444p10msble | - |
| Intel | ✅ <br> nv12 | ✅ <br> p010le | ✅ <br> y210le | - | ✅ <br> p012le |
| AMD | ✅ <br> nv12 | ✅ <br> p010le | - | - | - |
| Apple | ✅ <br> nv12 | ✅ <br> p010le | ✅ <br> p210le | - | - |
| Vulkan | ✅ <br> nv12 | ✅ <br> p010le | - | - | - |

- 新增`分層渲染`，能夠把場景中的物件分成多個層，渲染多張背景透明的圖片。目前，僅單個層支援ffmpeg影片編碼，且光影顏色可能有所不同，未來考慮使用MRG影片渲染圖改進分層渲染。
- 使用ProRes時勾選HDR或3D渲染，會主動改用ffmpeg編碼，現在能匯出透明的HDR影片了！需要注意的是，只有Apple GPU和Vulkan支援ProRes硬體加速，選中Nvidia/Intel/AMD GPU會退回基於CPU的prores_ks編碼
- Apple GPU確實不支援av1編碼，退回基於CPU的libsvtav1編碼
- “渲染帶HDR增益圖的jpg”即將轉正，已經移至頂部選單欄的“除錯與開發”主機板塊。修復了渲染不在第0影格時的報錯問題，改進了HDR色彩管理流程。目前，僅剩下UI介面編輯器等少數功能尚不支援HDR增益圖
- 移除了實驗性功能`擴充套件模板序列以支援雙精度浮點和向量屬性乘數`。此功能在製作動畫時從未使用，而且難以編譯，在linux上安裝會報錯，不如直接移除
- 添加了本地化條目，能夠翻譯變數類別了
- 修復了“遠景地形生成器”在mac上因為中文變數名而失效的bug。雖然內部重新命名為英文，但是本地化系統能把它翻譯成原模原樣的中文
- 修復了反斜槓路徑名在mac和linux上引發的錯誤
- 修復了mac和linux不能使用tkinter開啟檔案的問題，轉而使用系統自帶的檔案瀏覽器
- 修復了mac和linux上可執行檔案缺少許可權的問題。使用安裝包或重新初始化外掛時，都會為ffmpeg和ultrahdr_app注入rwx許可權
- 修復了mac和linux缺少內建的H.264與ProRes編碼器的問題，改用ffmpeg編碼。可惜的是，mac還缺少nDisplay外掛，目前沒有替代方案，因此不能進行3D立體渲染
> 虛幻引擎震撼首發：[Apple ProRes Movie ...... 只在Windows構建中可用！](https://dev.epicgames.com/documentation/zh-cn/unreal-engine/movie-render-graph-nodes-in-unreal-engine#outputfiletype%E8%8A%82%E7%82%B9)  
> 不是哥們 這什麼NTR行為啊喂🤣
- 更多mac和linux的相容性問題見[系統需求](#系統需求)部分



#### 0.5-RC1
- Mineprep 0.5進入最後的收尾階段，預計在兩週內釋出
- 改進了安裝包，現在會顯示安裝所需的空間，能夠安裝精簡版，以及跳過為其他平臺編譯的檔案。
- 新建了一個倉庫 [Mineprep Lite](https://github.com/piggestpig/Mineprep-Lite)，專門存放精簡版外掛。目前移除了原始碼、音效、whisper、運動匹配相關資源，體積縮小1個G以上，同時保留了95%的核心功能，以GPLv3協議開源
- 調整了多個程式，修復一些在Mac/Linux上可能出現的bug
- 為Linux編譯了實驗性功能。由於wsl2缺少Vulkan，暫時不能啟動虛幻引擎進行測試
- 開始編寫 [Minecraft Wiki](https://github.com/piggestpig/Unreal-Mineprep/wiki)，製作新手入門教學
- 【實驗性功能】增強了本地化系統，可以翻譯粒子參數了！至此，我們終於有能力翻譯所有的常見資訊
- 【實驗性功能】新增快捷鍵，按insert嘗試翻譯滑鼠下的文字。如果在[變數顯示名_VariableDisplayNames.csv](./Mineprep/插件贴图/变量显示名_VariableDisplayNames.csv)找到匹配條目，就替換文字
- 【實驗性功能】新增自訂快捷鍵時，能檢測按鍵衝突，並在右下角彈窗提示

#### 26w08a
- 新的動畫作品《撿到一隻快樂小幽靈2》現已釋出！第三集正在製作中，小幽靈的故事就要完結啦
  - 在製作動畫的過程中，我們檢驗了現有功能並修復了許多bug。新功能直接在專案檔中開發，注重參數化和拓展性
  - DLSS光線重構首次投入使用，極大提升了水面反射和半透明陰影的質量
  - 這是第一個使用正確的HDR色彩管理流程渲染的影片，配合LabPBR材質，畫面相較於第一集有了質的飛躍
  - UE5.7本身就是一個很好的版本。一方面，材質參數面板十分穩定，大幅減少了閃退次數；另一方面，緩動曲線預設從動態設計序列下放到普通關卡序列，用起來非常方便
- 新增`鸚鵡`，`駱駝`，`駱駝屍殼`，`枯骸`及其NPC生物。鸚鵡NPC能根據隨機種子重新整理皮膚，駱駝會自動扇耳朵
- 修改和添加了幾個攝影機晃動預設
- 修改和添加了一些粒子系統，還沒有放入生成器子面板中
- 添加了一些生物的動畫片段
- 添加了一些方塊模型
- 修復了飛行NPC在原地不動的bug。之後會進一步修改狀態樹
- 修復了外掛面板在初始化時未能注入本地化材質參數名的bug
- 拓展了本地化系統，原先零零散散分佈在藍圖中的“簡單中英文選擇器”，也能被收錄在[變數顯示名_VariableDisplayNames.csv](./Mineprep/插件贴图/变量显示名_VariableDisplayNames.csv)裡面了。多行文字有一些問題，因為換行符可能是\r\n而不是\n

#### 26w07a
- 要過年啦！！在這辭舊迎新之際，我們修復了近期最重大的bug，調整了一部分動畫相關功能
- 引擎自帶的Anim Mixer外掛已被停用。它會強制使用自訂動畫模式，使動畫藍圖失效。更多資訊參見 [https://forums.unrealengine.com/t/ue5-7-preview-sequencer-forces-custom-mode-overrides-animation-blueprint/2663672](https://forums.unrealengine.com/t/ue5-7-preview-sequencer-forces-custom-mode-overrides-animation-blueprint/2663672)
- 沒有Anim Mixer外掛，暫時無法在時間線上使用動畫序列控制新版觀眾人群（UAF動畫框架）。“切換動作”事件仍然有效
- 為媒體摳像播放器製作了動畫藍圖，用於混合預設動畫和時間線上的動畫序列
- 基礎生物模型和NPC生物新增`面向玩家/目标`、`面向角度/速度/始末距离`參數，可以自動轉頭面向最近的目標。部分舊的生物模型由於骨架不同，旋轉方向可能不對
- 騎乘者現在會自動對齊旋轉
- 村民NPC能根據隨機種子自動重新整理皮膚了
- 遠景地形生成器新增`地形邊界衰減`參數，用於降低邊界高度
- 導播臺新增`优化/还原`按鈕，點選可以最佳化簡單MC場景的效能
> Mineprep 0.5已經不知不覺做了快一年了，下週一定要釋出新的動畫，然後速速結束這個版本呀！！或許我選擇“荒野更新”這個大版本主題就是註定要拖更的 (´。＿。｀)  
> 荒野更新（x）  洞穴與山崖part3（√）

#### 26w06a
- 本週大幅改進了遠景地形生成器，添加了水面，公開了許多參數，能夠使用自訂`地形紋理`來控制地形的高度、植被密度和水域了
  - 平原、山脈和水面的高度會根據邊界框自動縮放，透過`平原/山脉/水面高度偏移`這個參數調整相對值，勾選`低窪處填充水面`或者使用地形紋理來生成水
  - 地形紋理的RGB通道分別對應高度/植被密度/水域，通常在0~1之間，也支援小於0或大於1的值  
  · R>0升高地面，R<0降低地面  
  · G>0增加植被，G<0減少植被  
  · B=1時直接轉換為水域，0<B<1時對地形高度進行插值，如果最後的地表高度低於河面，才會生成水
  - 提供了4組參數用於調整地形紋理：`高度/植被/河流偏移` `高度/植被/河流缩放` `高度/植被/河流乘方` `高度/植被/河流模糊`，每一個都是4D向量，分別對應RGBA通道
  - 預設在GPU上生成地形，速度非常快，便於調整參數。但是GPU地形經常會從編輯器中消失，渲染開始時需要花幾影格時間重新生成地形。取消勾選“在GPU上生成”，則會傳回穩定的CPU模型，不過生成速度很慢。
> 如果用普通的圖片作為地形紋理，說不定有意想不到的驚喜！試試虛幻引擎自帶的各種貼圖吧，比如 3DMotionGraphicsThumbnail 這張圖片生成的效果還挺好看的

> 我目前沒找到什麼比較好的畫圖工具，虛幻引擎雖然有一個網格體繪製模式，裡面能畫紋理貼圖，但它真的好難用 ╯︿╰
- 新增`苦力怕`及其NPC生物
- 改進了LabPBR材質，現在會從高光貼圖中讀取次表面散射，植物搖擺不會自動新增次表面散射了
- 修復了一些動畫序列造成頭部異常旋轉的bug
- 將MC攝影機的根元件替換為骨骼網格體，也就是說可以像生物一樣製作骨骼動畫了
- UE 5.7 的關卡序列似乎有bug，對內部元件打關鍵影格會因中文名而閃退，目前把生物的頭部重新命名為Head
- 媒體摳像播放器已更新Substrate材質
- 清理了一些舊資產
- 【實驗性功能】材質參數面板新增📄按鈕，點選複製一份新的材質
- 【實驗性功能】按Ctrl+Alt+9 交換選中項的位置


#### 26w05a
- 本週我們將MCprep的Mesh Swap功能帶入虛幻引擎，這是盼望已久的最後一個核心功能！
- `更換模型（實例化）`
  - 位於匯入世界的按鈕下面，目前有`分割不相鄰方塊的距離`、`分割為獨立的Actors`、`自發光光源`、`生成輔助燈光`四個參數
  - 點選後把大模型（燈籠、火把等離散的方塊）拆成小塊，每一塊都能單獨移動或刪除，同時支援還原為大模型
  - 拆分後顯著提升了自發光照明效果，還有一鍵生成輔助燈光的功能
  - 實際上，拆出來的是動態網格體，不是實例化網格體。暫時不支援GPU距離場碰撞箱，也不能對它使用準備場景
- 導播臺新增`自訂控制檯變數`，公開了許多調整畫質的參數。比如，最新的r.MegaLights.ScreenTraces.MaxDistance 15減少了螢幕空間追蹤距離，緩解陰影閃爍問題
- MC天空現在會把時間儲存到本地檔案裡，重啟後自動讀取，比之前更可靠
- 優化了方塊體積雲，增大了視野範圍，遠處有淡出效果
- 4級動態材質和外掛面板新增`覆層貼圖`，`覆層顏色`，`Stencil覆層貼圖遮罩`參數
- 拓展了材質系統，正在製作新的生物皮膚材質，用於多層貼圖和更好的2D表情動畫
- 修復了準備場景有時因空紋理而閃退的bug

#### 26w04a
- 本週材質大更新基本完成~ 清理了舊程式和舊參數
- 外掛面板新增兩行自訂材質參數，可以手動輸入參數名
- 應用材質參數時有三個目標型別：`方塊（靜態網格體）`、`生物（骨骼網格體）`、`覆層材質`，預設勾選前兩個。覆層材質是新新增的型別，暫時不支援關鍵影格
- 準備場景時，會自動判斷黑白貼圖再應用顏色，始終對單個小方塊使用“簡單與複雜”碰撞
- 修復了低解析度貼圖在一定距離處變模糊的問題
- 安裝外掛時，會把引擎時間碼修改為60fps。這將用於鏡頭試拍錄製器和新的防掉影格保護功能
- 方塊、基礎生物模型和NPC生物新增`騎乘者`參數，可以快速讓一個物件騎在另一個物件上
  - 每次新增新的乘客，會在`騎乘骨骼位`中尋找空位，然後把乘客附加到該骨骼上，使用指定的動畫
  - 勾選`分離(取消騎乘)`會解綁該乘客。再次點選取消勾選會重新綁定，相當於重新整理乘客狀態
  - 附加乘客時，會自動停用兩者之間的碰撞，防止穿模後抽搐
  - 癱瘓會向上傳遞，也就是坐騎和乘客全部摔倒。斷肢不會傳遞，最好不要讓騎的骨骼斷開
  - 目前，不支援讓NPC騎在別的物件上
- 為方塊添加了“癱瘓”事件，相當於開始物理模擬
- 點選兩次基礎生物模型的“物理Ⅰ”、“物理Ⅱ”、“物理Ⅲ”、“物理Ⅴ”按鈕，會切換到癱瘓狀態
- 新增`拴繩`，包含繩子、拴繩結和物理約束
  - 繩子是視覺效果，會和場景碰撞，但不會影響場景中的其他物件
  - 物理約束則是實際的連結，可以懸掛或牽引正在物理模擬中的物件。它會以牽引端為圓心進行約束（相當於懸掛），如果要牽引，建議把牽引端先放在物件身上，執行時再拉出來。
  - 可以把繩子和物理約束綁定到不同的骨骼上
  - 目前製作了`彈簧`、`硬約束`、`軟約束`三個快捷按鈕
- 附加元件新增`拴繩`和`騎乘上一個選中項`功能
  - 選中多個物件時，使用“拴繩”會把其他物件栓到最後一個選中項上
  - 選中多個物件時，使用“騎乘上一個選中項”會疊高高，從後往前依次騎乘上一項
- 【實驗性功能】右鍵細節面板中的材質參數，可以複製黏貼參數值和變數名了
- 【實驗性功能】增強了本地化系統，能夠修改引擎內建的文字了！在[變數顯示名_VariableDisplayNames.csv](./Mineprep/插件贴图/变量显示名_VariableDisplayNames.csv)的第一列添加了Namespace，用於區分不同板塊。勾選外掛面板中的“朗讀滑鼠下文字”後，會在日誌中列印讀取到的本地化資訊，然後把Namespace、Key和Source String複製到csv檔案的前三列，就能自訂翻譯文字了
- 【實驗性功能】右鍵點選MC場景編輯器子面板的圖示，可以直接進入此編輯器模式了
- 更新了MC場景編輯器的操作方式，更符合原版MC的樣子了：
  - 移動滑鼠將自動旋轉視角。按住左Alt鍵停止自動旋轉
  - 按TAB鍵切換為不自動旋轉，此時需要按住滑鼠中鍵才能旋轉視角（類似於Blender）
  - 由於虛幻引擎的限制，十字準星也會隨滑鼠移動。按右Shift鍵在螢幕中間生成另一個十字準星
  - 按下滑鼠左鍵/右鍵，能立即破壞/放置方塊，而不是在鬆開滑鼠時才生效
  - 長按或拖動滑鼠左鍵/右鍵，可以連續破壞/放置方塊
  - 修復了點選物品欄時並未切換對應方塊的bug

#### 26w03a
- 重新設計了外掛面板的材質參數，添加了大量新功能和參數行，每一行採用`🔲參數名【參數值】🔒🔗🔷`的格式，最頂上有`應用參數按鈕📥`和`按等級過濾參數🔍`
  - **🔲**：勾選框，是否用於準備場景、更換材質和`應用參數按鈕📥`。按住滑鼠左鍵能批次刷選
  - **參數名**：點選後應用此參數至選中項。雙擊時應用參數並儲存更改
  - **參數值**：有數值滑條和顏色這兩種型別，右邊有返回預設值的小箭頭
  - **🔒**：點選後解鎖數值滑條的滑動範圍限制。另外，無論有沒有解鎖，都可以用鍵盤輸入任意值。按住滑鼠左鍵能批次刷選
  - **🔗**：即時同步，啟用後修改參數值能即時應用於選中項。按住滑鼠左鍵能批次刷選
  - **🔷**：關鍵影格按鈕，左鍵對所有選中項新增關鍵影格，若參數名不存在則跳過。右鍵/中鍵會先應用參數值，再新增關鍵影格。
  - 右鍵“準備場景”等大按鈕能過濾相關參數。摺疊“進階設定”面板再展開會顯示全部參數
  - “附魔”、“植物搖擺”、“半透明”、“自發光”始終會應用相關參數
  - 更多功能正在開發中，暫不考慮靜態準備場景，未來會移除舊參數和相關程式
- 外掛面板新增`半透明`按鈕，點選後能把模型的材質轉換為真正的半透明材質，適合染色玻璃、淡出消失等效果
  - 半透明材質基於原有的動態材質，也分1~4級，新增了`模糊`和`折射率`參數
  > Substrate材質讓非光追半透明也有了模糊效果，但是它受粗糙度控制，直接使用會造成大部分方塊變糊。因此，我們使用獨立的“模糊”參數來控制模糊程度；粗糙度則是影響高光
  - 1級：接受漫反射光照，粗糙度直接減少高光度。不透明度被連線至Substrate覆蓋權重，因此越透明的材質模糊上限越低。其他功能和普通的1級動態材質相同
  - 2級：在1級的基礎上，接受鏡面高光光照。沒有“次表面顏色RGB+透射A”參數。其他功能和普通的2級動態材質相同
  - 3級：粗糙度被連線至Substrate第二粗糙度，用於模糊高光效果。其他功能和普通的3級動態材質相同
  - 4級：這一等級不再使用Substrate覆蓋權重，而是添加了“次表面顏色RGB+透射A”參數，由SSS MFP（次表面散射平均自由程）控制透明度。不透明度則用於縮放SSS MFP，值為0不一定能讓物體隱形。實際上，SSS MFP才是Substrate半透明的正確用法，能夠充分體現模糊效果；假如未來Lumen能投射彩色半透明陰影，SSS MFP還會被用來控制陰影顏色。
  - 一般來說，方塊的折射效果很差，不需要動折射率。開了光線追蹤半透明後，效果會好一點，此時折射率>1才會有模糊效果。
  - 普通的方塊或生物不需要半透明材質。用的多了會出現半透明排序問題，也就是各種奇怪的穿模。光線追蹤半透明是最簡單的解決方法，但是整個光影效果就變了，我通常很少使用
  - 目前，半透明材質都是單面的，不適合植物（雙面的排序問題實在太多了⊙﹏⊙）
  - 對半透明材質使用“準備場景”就能變回普通材質了
- 4級動態材質新增`間接光照貼圖`和`陰影貼圖`，前者可以修改反射/折射/自發光照明的顯示內容，後者可以修改陰影蒙板。比如說，讓生物在鏡子裡顯示另一種皮膚。預設不重載，也就是使用紋理貼圖。
- 新增`淡出消失`模板序列，適合半透明材質
- 修復了DLSS選項失效的bug。現在預設啟用光線重構，能大幅提升半透明陰影清晰度。修復了半透明陰影在遠處消失的問題
- 修復了畫質預設因為本地化翻譯而損壞的bug。同時修改了畫質預設選項，移除了4*和“反射為極高”，改為
  - 3- 極高（快速Lumen）
  - 3  極高
  - 3+ 極高（特調畫質）
  - 4- 影視級
  - 4  影視級（特調畫質）
  - 4+ 影視級（增強lumen）
> 有了DLSS光線重構後，反射更加清晰，我們決定始終使用高質量半透明反射。預設渲染畫質變回 4 影視級（特調畫質）。如果需要節約顯示記憶體，3+ 極高（特調畫質）也是不錯的選擇


#### 26w02a
- 所有實驗性功能已升級至UE5.7！
  - 虛幻引擎製作了新的新手入門外掛，不再需要舊版GuidedTutorials，已經將其從安裝包中移除
  - 添加了新的實驗性功能`擴充套件模板序列以支援雙精度浮點和向量屬性乘數`。這個早就做好了，在UE5.7中啟用
  - 添加了新的實驗性功能`為材質參數面板新增關鍵影格按鈕和本地化翻譯`。引擎內建的InlineMaterialInstance外掛經過大改，材質參數面板不再閃退了，但是無法透過之前的方法新增關鍵影格按鈕，於是我直接修改外掛，並把它和本地化系統整合在一起
- 材質系統正在升級至Substrate！
  - 大部分材質的預設效果和以前保持一致，我們仍然沿用之前的“金屬度”、“高光度”等參數，便於調整
  - Substrate帶來了新的特性：現已支援LabPBR高光貼圖的8種特殊金屬F0；將高光度提高至>1可以進一步讓材質變成鏡子；次表面散射的透射A能更好地表示透光程度了
  - 然而，Substrate大幅增加了次表面散射的指令數，造成效能下降。於是，我們調整了1級動態材質，移除次表面散射，新增法線貼圖，適用於大部分方塊。現在，匯入世界將使用1級動態材質來準備場景，生物也依舊使用1級動態材質。
- 觀眾人群已升級至UAF動畫框架，大幅提高了在編輯器中的效能！
  - 使用方法和以前一樣，繼承了大部分功能，在必要時退回舊版動畫藍圖
  - UAF目前不支援物理互動。使用衝擊和斷肢會自動癱瘓，然後退回動畫藍圖
  - 切換動作暫不支援播放速率和初始位置，支援播放次數和自訂鍵控動畫組
  - 額外旋轉目前支援z軸的0~180°，和以前一樣，設定為90表示面向x軸
  - 暫不支援在時間線上使用控制綁定，FK綁定也不行
- 改進了媒體摳像散佈器，和觀眾人群散佈器一樣，可以重載動畫，自適應面向目標
- UE 5.7 不能對許多陣列變數打關鍵影格了。修復了受傷變紅模板失效的問題。添加了破壞方塊的模板序列
- “遠景地形生成器”能投射光線追蹤陰影了，而且效能提升了幾十倍，在達到1800萬方塊上限前都能瞬間生成，極其震撼！！同時優化了內部的點生成器，現在完全執行在GPU上
- 修復了“簡單跟隨路徑移動控制器”失效的bug
- 修復了無綁定渲染和DLSS衝突造成閃退的bug。另外，經過測試，UE5.7的DLSS光線重構沒有渲染問題了

</details>

### 0.5-pre3
![image](https://raw.githubusercontent.com/wiki/piggestpig/Unreal-Mineprep/image/0.5-pre3%E5%B0%81%E9%9D%A2%E5%9B%BE.jpg)
<sup><i> 這是一張帶 HDR增益圖的 jpg封面！使用 HDR顯示器或下載到手機上即可檢視高動態範圍效果 <br>
地圖來自https://www.curseforge.com/minecraft/worlds/rtx-aio-map </i></sup>

Mineprep 0.5-pre3 是最後一個支援UE5.6的版本，帶來了許多革命性的改進：
- 首次支援MC的LabPBR材質標準
- 首次使用正確的HDR渲染流程，提供更多圖片/影片輸出格式
- 首次使用UE原生的本地化系統，高效且動態地注入變數名
- 全新的NPC生物和統一粒子群體
- 全面適配Chaos場系統，用於全域性力場、材質遮罩、動畫偏移

需要注意的是，這個版本處於UE5.6和5.7的過渡階段，許多新功能尚未在實際生產中進行測試。我們計劃使用UE5.7製作新的動畫影片。以下是最後兩週的更新日誌：

<details>
<summary> 檢視細節 </summary>

- 新增`全域性力場`、`力場探測器`、`動畫偏移場`、`材質遮罩場`、`角速度旋轉場`。
  - 以上內容都使用Chaos場系統，只能在執行時生效，編輯器中沒有效果。
  - 虛幻引擎提供了12種力場型別，包含整數場、小數場和向量場。向量場預設指向中心，可以勾選重設方向
  - 邊界範圍有球形、方形、平面一側、全場四種類型
  - 可以設定力場強度、衰減並新增噪聲
  - 可以分別啟用“世界場”（影響粒子、材質）或“Chaos場”（影響物理模擬）
- 舊版徑向力場仍然保留，它是唯一能在編輯器中生效的力場。優化了統計方法，提高效能並修復垃圾回收報錯
- 粒子能在多影格輪流取樣不同的向量場了。預設勾選了“線性力”，“線性速度”，“角速度”三個選項
- 為統一粒子群體製作了切換動畫功能。
  - 目前，只有蜘蛛有靜止和爬行兩種動畫，會根據速度自動切換，也可以使用“指定動畫索引”參數來設定。
  - “動畫偏移場”能控制一片區域的動畫時刻。使用負數可以把粒子的隨機動畫偏移全部減到0，也就是整齊劃一的動作
- “動態體積霧”可以取樣材質遮罩場了，預設沒有啟用，需要修改材質參數
- 導播臺新增`批次播片`事件，能對任意物件播放關卡序列或模板序列；基礎生物模型和NPC生物也添加了各自的`播片`事件
  - 在“新增MC關卡序列”後面新增了`新增批次播片模板`選單項，這是只有一個物件的關卡序列
  - 批次播片預設每0.05秒播放一批動畫，且對關卡序列有特殊的最佳化，建議對大規模人群使用關卡序列而不是模板序列
  - 在模板中製作動畫時，建議使用Additive相對偏移作為關鍵影格軌道
  - 播片不支援事件關鍵影格
- 製作了生物`受傷變紅`的模板序列，可以在時間線上右鍵新增，也可以用於播片事件。
- 改進了“觀眾人群散佈器”，添加了重載動畫和皮膚的參數。預設狀態不建立旋轉元件，設定面向目標後請點選重新整理按鈕，即可正確面向目標
- 改進了“遠景地形生成器”，現在會根據尺寸框的z軸縮放自動生成山脈，公開了“方塊”、“在GPU上生成”、“啟用植物搖擺”三個參數。注意，UE5.6無法投射光追陰影，等到UE5.7才有實用性
- “注入本地化變數名”轉正了！相關按鈕已經從頂部選單欄移除，不再是實驗性功能，而是在切換語言時自動執行。我們第一次使用了UE內建的polyglot本地化系統，且第一次翻譯了列舉值。這能在25ms內注入1000條變數名，速度極快，無需編譯。變數名儲存在[變數顯示名_VariableDisplayNames.csv](./Mineprep/插件贴图/变量显示名_VariableDisplayNames.csv)中
- 【實驗性功能】按 Ctrl+Alt+? 可以檢視當前所有自訂快捷鍵
- 改進了Megalights在渲染時的陰影質量和體積質量
- 使用純函式和批次陣列處理優化了許多藍圖程式的效能
- 為蜘蛛製作了首個Locomotor運動綁定
- 調整了初始的日光強度、環境光遮蔽和對比度參數
- 點選UI介面編輯器的“重新整理”按鈕，能自動更新編輯器中的SDR/HDR顯示狀態
- 修復了“從圖片合成HDR增益圖jpg”因為臨時檔案而報錯的bug。注意，前兩個檔案名似乎需要純英文。“渲染帶HDR增益圖的jpg”要等UE5.7才能解決色彩管理問題
- 修復了VR+3D渲染錯誤啟用nDisplay輸出的bug
- 修復了方塊破碎模板的材質消失問題

</details>

<details>
<summary> 📜展開快照 </summary>

#### 25w51a
- 進一步完善統一粒子群體，利用紋理集合支援任意數量的皮膚和動畫，打通不同生物模型之間的壁壘，新增了`螢火蟲粒子`
  - 每一種用於粒子群體的生物都有專屬資料集，裡面包含模型、皮膚、動畫、碰撞箱等參數。
  - 當前，一個粒子群體支援4個不同的資料集，也就是說，可以把蠹魚蜘蛛終界蟎什麼的全部混在一起，做一個大蟲群了！
  - 細節面板中有多個模組，其中一部分是不同的運動模式，按需啟用。當前有“粒子生成”，“模型”，“材質(模型/Sprite)”，“動畫”，“碰撞檢測”
，“行走”，“爬行”，“Boid模擬(鳥群/魚群)”，“子粒子”和一些力場參數
  - 螢火蟲粒子和媒體摳像粒子使用Sprite材質，而非普通的模型。可以勾選始終面向攝影機
  - 最佳化效能並修復了跳躍和碰撞箱的一些bug
> 紋理集合需要無綁定渲染，這個功能必須透過修改專案配置檔案來啟用，而且UE5.7的啟用方法和UE5.6不一樣。我試試把它們都放進安裝包裡
- 媒體摳像粒子集成了摳像快取和粒子群體兩個系統，現在需要手動指定`缓存帧数/更新帧率`和`快取解析度`，修復了快取影格數超過30會失效的bug。新增`抖動遮罩模擬半透明`參數，預設勾選，能大幅提升效能，但會降低半透明部分的質量。
- 更改了生成器子面板按型別過濾的多選策略：左鍵點選多個類別（比如A、B），將同時檢查A與B，而非之前的A或B

#### 25w50a
- 本週初步製作了`統一粒子群體`，之前的蟲群粒子（蠹魚/終界蟎）和蜘蛛群粒子已經合併到一起
  - 新一代粒子群體集成了各種運動方式，可以按需啟用，也支援透過關鍵影格在執行時切換狀態
  - 目前有行走、爬行和Boid模擬（將用於鳥群和魚群）三種運動方式
  - 接下來的任務是改造動畫系統，然後把媒體摳像粒子合併進來
- 材質新增`不透明R~G+B*A`參數，能夠正確渲染染色玻璃了，也能製作模型的淡入淡出動畫
  - 計算順序從後往前，先把紋理貼圖的不透明度乘以A，然後+B，最後判斷是否在R~G範圍內，小於R直接設定為透明，大於G直接設定為不透明
  - 目前使用抖動遮罩的方式模擬半透明效果，會產生噪點，而且在運動時有明顯重影。UE5.7提供了一個拒絕TAA的材質節點，能大幅緩解重影問題。等更新UE5.7之後，還會使用Substrate材質製作真正的半透明玻璃
- 新增材質遮罩場，將“Stencil遮罩層”設為9可以取樣全域性力場作為遮罩。導播臺新增`GPU力場精度`、`GPU力場距離`、`材質遮罩場型別`參數。預設精度32比較低，但提升精度會顯著增加顯示記憶體佔用。
- 修復了IK綁定導致手部異常旋轉的bug。現在，FK和IK都使用分層綁定，而且能疊加使用。做完動畫後，可以點選細節面板面板中的`烘焙關鍵影格`按鈕，一鍵烘焙動畫
- 無時間線 直接從編輯器視角渲染動畫時，添加了攝影機晃動效果
- 舊版隨機種子已全部升級為新的“隨機種子Seed”參數
- 優化了MC場景編輯器中基礎方塊的GPU距離場碰撞箱。雙面材質似乎會破壞距離場，因此使用了一個專門的單面方塊作為距離場替換網格體

#### 25w49a
MC即將迎來新的版本編號方法，下一次大更新不是1.22，不是2.0，而是... 26.1!（⊙ｏ⊙）  
至於Mineprep嘛，現在這個版本編號挺好的，那就繼續用吧

- 本週NPC大改基本完成，新一代NPC不僅翻新了底層架構，而且繼承了之前的所有功能，顯著提升效能和互動體驗。新增了 `蠹魚、終界蟎、蜘蛛、洞穴蜘蛛、地獄幽靈、快樂幽靈、小幽靈、烈焰使者、凋零怪、豬布獸、雪人、狼、貓、山貓、悅靈` 對應的NPC生物，並帶來了以下新功能：
  - 絕大多數參數都顯示在細節面板的`NPC行為`部分，可以整體複製黏貼，比如把地獄幽靈的行為複製給殭屍，讓它飛起來。每個參數都有詳細的工具提示
  - 新的`隨機種子Seed`變數會自動設定初始值，點選右邊的↩按鈕能隨機設定新的值，它和移動速度和單獨列出，不包含在NPC行為中
  - NPC行為的第一個參數是`運動模式`，當前支援“無”、“行走”、“尋路網格體行走”（沒有導航網格會自動退回行走）、“正在飛行”，未來會支援游泳。
  - `自動跳躍,攀爬,避障模式`進一步定義了行走模式，當前有“無”（撞牆會換方向走）、“跳躍”（大部分陸地生物的預設模式）、“攀爬”（蜘蛛的預設模式）、“上牆行走”（更真實的蜘蛛爬行/飛簷走壁，相當於自動改變重力方向）
  - 考慮到大規模人群的效能最佳化，NPC生物移動時會首先逐影格平滑移動旋轉，然後呼叫自動化移動函式。`平滑移動旋轉閾值`決定了切換到自動化移動函式的方向夾角，預設為0.1（弧度）。設定為0表示始終平滑移動旋轉，這是飛行生物和高階NPC的預設設定
  - `旋轉速度`有三個值，分別對本地XYZ軸的旋轉速度。將前兩個值設為0表示只能水平旋轉，例如直立飛行
  - 目前NPC有待機、遊蕩、跟隨、躲避四種基本狀態；按目標點巡邏屬於跟隨狀態。可以使用事件關鍵影格或導播臺廣播強制切換特定狀態
  - 待機和到達跟隨目標後支援隨機播放動畫，根據`待機隨機播放動畫索引`和`攻擊隨機播放動畫索引`在自訂鍵控動畫組中挑選
  - 要讓NPC根據tag自動跟隨/躲避目標，目前必須勾選`视觉/听觉/触觉感知`的視覺感知，感知半徑暫時鎖定在15m。然後，配置`跟隨目標類->tag`和`躲避目標類->tag`（tag留空表示任意值），讓NPC識別進入視野的目標
  - 物理互動動畫和輔助碰撞箱現在預設關閉，按需啟用
  - 更多參數資訊請檢視工具提示
> 高階NPC暫未支援全部功能，等UE5.7換了新的運動匹配官方範例再說。下週會檢查各種舊功能以及基礎生物模型的相容性，最後開發一下統一粒子群體，Mineprep 0.5-pre3就能釋出了
- `自訂鍵控動畫組`是新一代用於遊戲模式、NPC行為和事件關鍵影格的動畫系統
  - 繼承了先前的互動模式，依然可以按數字鍵播放動畫，或者使用事件關鍵影格/導播臺廣播來播放
  - 每個索引代表一個動畫組，支援多個動畫
  - 預設情況是按順序播放身體動作。透過重載特定動畫索引的參數，可以配置表情動畫、播放速度、緩入緩出等資訊。手動輸入`播放順序`則能進行連播、隨機播放、迴圈播放等行為。具體參見工具提示（待更新）：
  - <播放順序> 留空表示按照0123...的正常順序一個接一個播放；(012)表示從中隨機挑選動畫；[012]表示同時播放所有動畫，通常用於身體和表情等不同部位的組合，將最後一個動畫的結束時間作為整組時間。在兩個動畫之間新增"."表示間隔0.1秒，":" 表示間隔0.2秒，"/" 表示間隔0.5秒
- MC天空支援自訂背景貼圖了！預設是Celestial Vault外掛的銀河系全景圖。雙擊天空找到背景材質，調整裡面的`背景天空亮度`就能看到了。
- 繼續改進匯入方塊/匯入物品相關程式
  - 把等待時間延長至5秒，解決第一次匯入時 可能因初始化時間較長而失敗的問題
  - 5秒後，強制關閉Blender後臺進程
- 修復了遠處透明材質因各向異性過濾出現異常條紋的問題
- 修復了MC場景編輯器不能按delete刪除選中物件的問題


#### 25w48a
- 本週對NPC生物進行大改，這一改造已經陸陸續續持續了幾周，預計能在25w49a基本完成。新一代NPC的底層架構從行為樹轉換為狀態樹，並添加了以下功能：
  -  支援飛行、攀爬等多種運動方式
  -  將更多的參數暴露在細節面板中，支援整體複製黏貼
  -  事件驅動的狀態轉換，可以透過關鍵影格和導播臺廣播來控制NPC行為
  -  提升效能
- 重新設計了新的“自訂鍵控動畫組”，支援把多個動畫組合在一起播放，透過簡單的指令重載播放順序，後續將與NPC整合到一起

#### 25w47a
- 透過混合最近點取樣和各向異性過濾取樣，大幅提升了遠景材質的質量，減少模糊、閃爍和消失的問題
- 從3級動態材質開始，可以使用“單面”參數的小數部分略微擠出面，解決兩個模型重疊時的閃爍問題；植物互動現在能用於大場景模型
- 改善MC天空重啟後可能回到6:00的問題。現在應該能記錄時間並重新整理待儲存狀態。優化了方塊雲在夜晚的亮度
- 改進放置物品和放置方塊的工作流程，當檢測到錯誤時（未安裝Blender、未安裝MCprep、匯入模型失敗等）會彈出提示框，並修復了連點產生的bug
- 【實驗性功能】更新快捷鍵Ctrl+Alt+5為顯示選中物件的輪廓；按小鍵盤0切換攝影機視角時，若沒有開啟時間線，會自動檢測選中的攝影機或場景中的攝影機
- 【實驗性功能，將在UE5.7啟用】擴充套件模板序列以支援雙精度浮點和向量屬性乘數。同時，UE5.7有了新的官方入門教學外掛，舊版GuidedTutorials將被廢棄

#### 25w46a
- UE5.7正式版釋出了！我們計劃在幾周後升級引擎，目前為非實驗性功能修復了一個新的選單欄bug
- MCprep更新了3.6.2版本，我們同步了新的MC資源包(支援到1.21.10版本)，並修復了在Mineprep中呼叫放置方塊/放置物品時的一些bug。新版MCprep適配了Blender5.0，放置方塊時不會給每個面生成多餘的材質了，更換紋理能也對放置的大部分方塊生效。
- 準備場景的進階設定中新增`平直著色(重置法線)`選項
- 在MC場景編輯器子面板新增`匯入世界`按鈕，目前有OBJ(Mineways)，OBJ(jmc2obj)和FBX三個選項。這是第一次適配jmc2obj，之後還將逐步適配MiEx的usd模型
- 優化了匯入模型的預設參數，OBJ模型會使用100倍縮放和90°旋轉，從MC座標系轉換到UE座標系；匯入jmc2obj模型還會自動應用平直著色(重置法線)。右鍵按鈕可以開啟詳細參數面板。
- MC天空新增`日/月光束遮挡+过渡`，`太陽泛光RGB+亮度A`和`月亮泛光RGB+亮度A`參數。太陽預設使用光束遮擋，月亮預設使用泛光，增強了體積光效應和氛圍感。修復了月相在半夜變化的bug
- 使用影片編碼或影像轉碼時新增`刪除原圖`參數。當前3D渲染有點問題，需要關閉刪除原圖，否則會報錯

#### 25w45a
- 這幾周的渲染流程大更新基本結束了。最後為3D渲染適配了影片編碼和影像轉碼，新增以下四種格式
  - 兩組獨立輸出
  - 左右並排 FSBS
  - 上下並列 FTB
  - 紅藍濾色
- 輸出檔案名可以新增子資料夾路徑了，例如"MC/xxx"會先建立名為MC的資料夾，把輸出結果儲存到裡面
- 外掛設定子面板新增`渲染結束開啟資料夾`（預設勾選）和 `渲染結束提示音`（預設為空）
- 在頂部選單欄-MC-開發板塊新增`渲染帶HDR增益圖的jpg`和`從圖片合成HDR增益圖jpg`按鈕<sup>[僅支援Windows]</sup>，使用新版Movie Render Graph同時渲染SDR和HDR畫面，然後使用libultrahdr合成帶增益圖的jpg圖片。
> 目前能保證SDR畫面和編輯器視口保持一致，但是無法應用HDR渲染亮度倍率，因此沿用之前的色彩校正方法，HDR增益圖效果大約和r.HDR.Aces.SceneColorMultiplier=1.5差不多

> Movie Render Graph的暖場很慢，並且會運行遊戲邏輯，我們在渲染開始時加快了自動曝光調整速度

> 暫不支援3D渲染、全景渲染和DLSS等功能。
- MC攝影機、搖臂攝影機、導軌攝影機新增`旋焦`參數，>0表示繞中心旋轉的背景模糊，<0表示指向中心的徑向模糊
- 準備場景現在會強制重新整理紋理貼圖，修復以往的模糊問題
- 改進了媒體摳像播放器和媒體摳像散佈器，切換影片不再閃爍
- 修復了方塊體積雲與半透明材質之間的排序問題，在安裝外掛時啟用bCompositeHeterogeneousVolumesWithTranslucency專案設定

#### 25w44a
- 改進渲染流程和預設檔案，統一為"Mineprep自訂渲染配置"，移除了舊的配置和Mineprep3D攝影機組
- 渲染時會建立一個新的臨時配置檔案，向其中新增所需模組，這可以避免未安裝DLSS彈出警告的問題
- H.264編碼現在使用UE內建的影片編碼器
- 整理了渲染輸出子面板，新增`圖片轉碼`功能，在不輸出影片時也可以進一步處理圖片。當前有以下選項：
  - 無
  - 動圖.gif
  - 動圖.webp
  - HDR/序列影格.png
  - HDR/動圖.avif
  - HDR/動圖.jxl
- 重置了渲染預設，預設為1080p+時間線影格率+高質量H.264編碼，用於快速渲染。當前有以下選項：
  - 2K_120.mp4
  - 2K_120_HDR.mp4
  - 2K_透明_Prores.mov
  - 2K_3D.mp4
  - 4K_VR全景.mp4
  - 2K_HDR.png
  - 2K_HDR.exr
  - 512x512_動圖.gif
  - 512x512_動圖.webp
  - 預設
- 3D渲染支援景深了！渲染時會把當前攝影機的景深同步到Mineprep後期處理體積，透過全域性景深影響nDisplay3D攝影機組，模糊程度可能略有不同。
- UI介面編輯器支援3D渲染了！nDisplay3D攝影機組新增`UI介面3D效果`參數，預設為1，調大可以增強左右眼偏移
- 驗證了libultrahdr合成jpeg圖片的可行性。我們使用達芬奇的Nvidia RTX Video HDR把往期封面圖轉換為Rec2100 PQ並匯出為16-bit HDR png，然後用ultrahdr_app.exe把原圖和新圖合成為帶HDR增益圖的jpg，在各個平臺上都有不錯的觀看效果。接下來考慮將其整合到渲染流程中
> 除了libultrahdr，我還嘗試製作空間影片和實況照片，結果一個也沒弄成，Windows一敗塗地啊，安卓的標準又參差不齊，真就是Only Apple Can Do ｡ﾟヽ(ﾟ´Д`)ﾉﾟ。  
> 為了彌補遺憾，在圖片轉碼那邊添加了gif/webp/avif/jxl格式，後面兩個算是戰未來吧，目前不能用於剪輯，只能在有限的平臺觀看



#### 25w43a
- 所有生物已更換新版材質。方塊材質新增`單面`參數，預設為0，表示雙面渲染；設為1僅渲染正面（適合簡單玻璃），設為-1僅渲染背面。
- 繼續改進渲染輸出流程，現在無需實驗性功能或重啟引擎就能更改輸出的字尾名格式了
- H.265/AV1全面支援新的HDR編碼方式，同時針對不同硬體編碼器調整了色度抽樣和質量參數
- 新增`Vulkan`硬體加速選項，支援H.264/H.265/AV1編碼
- 安裝外掛或重新初始化時會透過OpenCV的OpenCL模組更加智慧地識別顯示卡
- 第三版png標準支援HDR了，測試發現FFmpeg也能正確寫入元資料！我們改進了啟用HDR後的圖片渲染功能，若勾選png，則會渲染exr並重新編碼至16-bit Rec2100 PQ png。話說png序列影格能顯示縮圖、能被達芬奇直接識別輸入色彩空間，這不比exr好多了(～￣▽￣)～
- 【實驗性功能】我們編譯了[libultrahdr](https://github.com/google/libultrahdr)，用於製作帶HDR增益圖的jpg圖片。ultrahdr_app.exe儲存在ffmpeg.exe旁邊。
  - 這是目前相容性最好的格式，包含SDR和HDR兩份資料，若顯示器不支援HDR也能當成普通的jpg開啟。
  - 初步測試，同時注入ISO和XMP元資料的HDR圖片能被Windows、蘋果和安卓成功識別
  - 我們參考[這個指令碼](https://github.com/albertz/playground/blob/master/ultrahdr.py)把Readme中的圖片轉換成了帶HDR增益圖的jpg，看看有沒有效果👀
  - 下一步計劃是把它整合到Mineprep的渲染流程中。為了同時渲染SDR和HDR底圖並應用各自的色調對映，需要新版Movie Render Graph，還要在渲染結束後單獨呼叫ultrahdr_app.exe。這將是一個長期目標

#### 25w42a
- 本週大幅改進了PBR材質和HDR渲染流程，從根源上解決長期存在的問題，為後續版本更新以及UE5.7的Substrate材質打下堅實基礎
- 重新設計材質參數和紋理貼圖的解讀方式，適配MC專用的LabPBR標準，並添加了4級動態材質用於視差凹凸效果
  - 近幾年的MC紋理包普遍採用[LabPBR](https://shaderlabs.org/wiki/LabPBR_Material_Standard)標準，它把自發光蒙版、次表面散射、環境光遮蔽、高度圖等諸多資訊打包在高光貼圖(_s)和法線貼圖(_n)的不同通道中。現在，Mineprep能正確解讀這些附加資訊了！
  - 新版材質分1~4級，如下所示。（未來還會增加兩種半透明材質，1-2級用於簡單染色玻璃，3-4級用於模糊的磨砂玻璃，這需要新一代Substrate材質系統）
  - ① 用於生物皮膚的材質。包含以下參數：  
    Stencil遮罩層  
    發光亮度  
    照明強度  
    紋理顏色  
    次表面顏色RGB+透射A   
    金屬/高光/粗糙/孔隙率   
    紋理貼圖  
    高光貼圖  
  - ② 用於方塊的材質。添加了以下的額外參數：  
    法線強度  
    破碎程度  
    頂點顏色   
    單面  
    動畫速度/步長/列數/漸變    
    法線貼圖  
  - ③ 用於附魔和植物搖擺的材質。添加了以下的額外參數：  
    搖擺幅度  
    搖擺速度  
    互動強度  
    附魔縮放/速度/對比度/底色  
    附魔顏色  
  - ④ 用於視差凹凸的材質，需要法線貼圖的Alpha通道包含高度資訊+Megalights光追陰影，添加了以下的額外參數：  
    視差凹凸強度   
    視差精度
  - 新版材質減少了貼圖數量，並透過強有力的if else跳轉分支，在功能更多的同時 效能保持不變或更好。（不過虛幻引擎會統計所有分支的指令數，直接看著色器複雜度似乎較高，實測沒有問題）
  - 現在可以在參數中設定是否啟用漸變動畫了，預設為漸變，“準備場景”會對火焰等特殊方塊設定不漸變；動畫播放速度已經統一，預設為1秒1張圖；步長設定為負數表示往返迴圈，可以解決**靜態岩漿**的突變問題；而**流動岩漿**把每一張圖儲存為2x2的重複塊，設定步長4 列數2即可正常播放
  - 金屬/高光/粗糙 設定為正數表示相乘，負數直接指定為絕對值。孔隙率將在Mineprep 0.6得到支援，用於積水溼度，目前沒有效果
  - 發光亮度現在表示整體偏移量，預設是0。高光貼圖的Alpha通道存放了自發光蒙版，若含有資訊會自動發光。降低發光亮度至<0可以使它減弱，提升至>0則使整體變亮。新材質發光時會自動從“次表面”著色模型切換至預設光照
  - 各向異性和切線貼圖已被移除（之前從未用過，在Substrate中還會增加材質複雜度）
  - 新材質專為MC設計，不建議對非MC模型使用“準備場景”！當前需要取樣法線貼圖的四個通道，會改變紋理取樣器型別，和原材質不相容。另外，MiEx會把LabPBR轉換為常規PBR匯出，這反而需要特殊處理了，未來會製作自動識別與匯入模型的功能
  - 更多功能正在更新中，生物和方塊即將更換新版材質。
- 徹底解決了HDR渲染顏色和編輯器視口不一致的問題，不再需要色彩校正。顏色子面板新增`HDR渲染亮度倍率`滑塊，可以理解為HDR專用的曝光參數，初始值為2，比UE預設的1.5略高，使HDR畫面變得明亮
> 終於，我解決了這個困擾一年的問題，淚目 ｡ﾟ(ﾟ´ω`ﾟ)ﾟ｡
>   
> [論壇中的這個討論](https://forums.unrealengine.com/t/fixing-hdr-tonemapping-errors-darkened-image-and-wrong-colors/2544973)點出了問題的根源：UE5有一個控制檯變數 r.HDR.Aces.SceneColorMultiplier，預設值是1.5，它會把編輯器視口的亮度x1.5，但是不影響渲染輸出！！！難怪以前顏色不一致
>   
> 最簡單的解決辦法是把它改成1，但是這導致場景昏暗，上面那個帖子也說增加到3.25才比較好看。進一步研究發現，它的效果和後期處理體積的全域性增益相同——因此，我們在導播臺中添加了一個優先順序更高的後期處理元件，渲染時檢測到HDR就會自動啟用，把Mineprep後期處理體積的全域性增益和SceneColorMultiplier相乘。
- 調整了Mineprep後期處理體積的初始參數，現在會啟用環境光遮蔽(強度0.5 距離50)和全域性對比度1.05
- 發現了頂點動畫的陰影問題所在：光線追蹤目前無法投射正確的次表面陰影！把“次表面散射RGB+透射A”參數改為0，可以暫時解決Lumen光追在蟲群粒子和PCG植物上投射錯誤陰影的問題。而Megalights有HZB螢幕空間追蹤，這很大程度上緩解了錯誤的陰影，還能投射正確的視差凹凸陰影
    
#### 25w41a
- 雙擊MC天空的背景（即選中天空球元件），能夠看到背景天空/方塊雲/方塊體積雲/體積雲的材質，現在可以很方便地調整參數和製作關鍵影格動畫了
- 繼續改進渲染畫質，增強反射和視野距離等參數；正式啟用了Megalights的定向光源功能，顯著提高了大場景的效能，在“光程”板塊新增一個使用虛擬陰影貼圖或退回lumen的按鈕
> 儘管UE5.7的更新日誌才提到Megalights支援定向光源，UE5.6已經有相關控制檯變量了。當前，Lumen光追無法在實例化網格體（如蟲群粒子）上投射正確的WPO陰影，Megalights是最直接、效能最好的解決方案。另外，遠景地形生成器問題比較大，目前停用了WPO頂點動畫，需要使用虛擬陰影貼圖或更新至UE5.7
- 新增`光照探測器`，能夠探測空間中或表面上的光照強度，在檢視中顯示亮度和RGB分量。可以使用數學表示式把亮度值設定到其他物件上，預設參數是控制燈光亮度，在夜晚亮起。*注意亮度是一個不穩定的參數，不建議用於精確值
- 修復了Chaos破碎模板的方塊材質問題

#### 25w40a
- 改進NPC生物的狀態機動畫，製作了 常規運動-潛行-游泳-飛行 的模板，為更多種類的運動方式打下基礎
- 修復了一些自動跳躍和麵向目標的bug
- 更新了“MC第一人稱攝影機”，使用UE5.6的新版第一人稱渲染模式，加入手持物品、身體模型和更多功能
  - 預設情況下顯示右手，點選或長按滑鼠左鍵可以揮動右手；身體在反射中可見，能夠投射陰影。
  - 錄製動畫會記錄第一人稱視角和全身運動的所有關鍵影格。修改“身體部位可見性”可以決定要顯示的部分
  - 優化了走路和跑步的攝影機晃動，更符合MC原版的樣子
  - 未來，我們計劃把MC場景編輯器和第一人稱角色結合起來，實現動態放置、破壞、獲取、切換方塊
- 方塊的物理破碎板塊添加了`自訂切割位置+法向量`功能，能程式化切割**任意方塊**，還支援直接錄製動畫！
  - 我們提供了幾個“PM”開頭的切割模板。切割次數根據模板名稱變化，比如“PM切割小方塊_2x2x2”可以改成3x3x3，隨機切割則由隨機種子決定
  - 效能不如原先的Chaos破碎預設，不要切太碎。如果使用了Chaos破碎預設，將忽略自訂切割
  - 停用物理破碎需要清空破碎模板和自訂切割參數
- 在導播臺的畫質預設中加入了`4* 影視級（反射為極高+增強降噪）`選項，優化了lumen光線追蹤相關參數，現已成為預設渲染畫質。
- 其他功能子面板的“光程”和“環境光遮蔽”板塊添加了`室內天空光照`參數，可以調節顏色和強度

#### 25w39a
- UE5.7預覽版釋出了，Mineprep 0.5-pre3將是最後一個支援UE5.6的版本！外掛的非實驗性功能已經為5.7做好適配，透過延遲初始化修復了python指令碼執行失敗的新問題。
- UI介面編輯器基本製作完成
  - 點選細節面板的按鈕，可以新增文字或影像，上移或下移圖層。*刪除圖層後需要手動點選重新整理
  - 預設情況下使用相對縮放，修改渲染解析度也能保持相近的圖層大小。取消勾選“隨解析度自動縮放”，將使用絕對的像素大小
  - 在3D場景中雙擊圖層，可以快速選中並移動、旋轉、縮放它
  - 能夠調整全域性顏色/不透明度以及每個圖層的參數，製作關鍵影格動畫
  - 支援僅在邊界框內顯示，調整PostProcess元件的混合半徑還可實現淡入淡出
> 暫不支援全景和3D渲染，未來估計也不會支援！話說，在後期剪輯時給全景/3D影片上字幕，好像也不簡單啊 Σ(;ﾟдﾟ)  
> **0.5-pre3 (25w44a) 已支援3D渲染！**
- UI文字具有`匯入字幕`按鈕，可以匯入srt檔案為關鍵影格，或者從音影片中識別字幕
  - 通常來說，我們更推薦在剪輯軟體中加字幕，直接在UE裡做算是多了一種選擇
  - 識別字幕使用FFmpeg 8.0呼叫whisper生成srt檔案，儲存在專案檔目錄的cache資料夾下。
  - Mineprep附帶了ggml-base-q8_0.bin作為預設的小模型，如果想要更好的效果，可以在[whisper倉庫](https://huggingface.co/ggerganov/whisper.cpp/tree/main)下載ggml-large-v3-turbo-q8_0.bin等更大的模型，放至/Content/Mineprep/Render/models/whisper目錄下
- 使用UE5.6的官方範例重做了第三人稱運動匹配角色，同時重新設計模組化的NPC
  - 修復了物理互動造成閃退的bug。現在可以為骨骼配置任意數量的不同物理參數集了
  - 增強了跳躍檢測功能，可以在空中抓住牆壁爬上去了！錄製關鍵影格動畫時，也不再會生成一堆臨時碰撞箱了
  - 官方提供了新的衝刺模式，目前分配給按鍵"Z"
  - 更多功能正在製作中，預計會下放給普通NPC生物

#### 25w38a
- 為方塊模型添加了`物理破碎`功能
  - 預設情況下破碎模板為空，設定為有效的模板即可啟用Chaos物理破碎，可以碎成小方塊或不規則形狀
  - 效能 2x2小方塊 > 碎石塊 > 4x4小方塊 > 6x6小方塊 > 8x8小方塊
  - 勾選初始模擬會隨重力下落，否則受到撞擊才破碎
  - 修改分級破碎閾值，可先碎成大塊，再碎成小塊（目前只分兩級）
  - 當前僅支援六個面的標準方塊，以及頂面/側面/底面三種材質
  - 暫時無法錄製關鍵影格動畫，需要專用的Chaos快取
- FFmpeg已經升級至8.0版本！新版注入HDR元資料的方式有變，我深入研究了色彩管理的細節，正在開發新一代渲染流程
  - 使用全新的命令編碼H.265影片，其他格式也將陸陸續續改進
  - UE5_HDR.cube已經廢棄，不再需要lut進行影片編碼時的調色，而是通過後期處理材質在色調對映後power 0.85，直接模擬這一調色過程。現在，只匯出exr序列影格不編碼影片，也可以在達芬奇中手動指定輸入顏色空間為Rec.2100 PQ來還原編輯器中的顏色。
- 初步製作了`UI介面編輯器`
  - 終於，我們有了相容HDR的UI渲染器！UE內建的渲染管線是把sRGB UI直接疊加到最終影像上，繞過Filmic色調對映，但未考慮HDR輸出。在普通的SDR渲染時，我們仍然遵循這一流程。
  - 而在HDR渲染時，沒有色調對映，只有色彩空間轉換。因此，我們通過後期處理材質將Linear Rec.709 UI直接注入色調對映前的場景顏色，隨場景一起轉換到HDR顏色空間，得到了正確的顯示效果。需要注意的是，當前最晚只能在泛光前注入，也就是UI會受到輝光的影響。
  - UI介面編輯器旨在提供動態新增文字和影像的功能，可以在3D場景中預覽和編輯、製作關鍵影格動畫，未來還將支援匯入字幕
  - UI介面的縮放取決於渲染解析度，需要在攝影機視口中檢視，否則會拉伸


#### 25w37a
- 本次更新對整個外掛的檔案層級進行了大調整。由於PCG HLSL節點在中文路徑下會報錯，不得不做出以下更改：
  - “MC藍圖資源”資料夾改名為“MC_Blueprint"
  - 各大類從“依賴”資料夾中提取出來
  
  最終，“/Mineprep/MC藍圖資源/依賴/PCG/” 變為 “/Mineprep/MC_Blueprint/PCG/”。未來將會進一步整理檔案，使資源路徑簡潔清晰。同時又要debug了...
- 初步製作`遠景地形生成器`，在GPU上高效生成MC地形。目前實現了基本的石頭-泥土-草方塊-草的生成+內部方塊剔除，未來將和場景互動，擴充套件現有模型的邊界。目前侷限性較多，不支援光線追蹤陰影，更多功能要等UE5.7更新
- 粒子現已支援Chaos力場。這是虛幻引擎官方提供的全域性力場，有更豐富的功能，但是不能在編輯器內預覽，只能在執行時使用。舊版徑向力場仍然保留
- MC攝影機、搖臂攝影機、導軌攝影機添加了`交叉疊化`轉場功能。這是首個混合兩邊畫面的轉場，先從原攝影機過渡到快取，再從快取過渡到新攝影機，在編輯器內以低解析度預覽（需要進入攝影機檢視檢視轉場過程）。可以調整緩動曲線和時長。中間的空當需要與鏡頭切換對齊
- 遙控燈光不再需要提前新增元件了，導播臺廣播時會自動識別燈光
- 優化了導播臺批次廣播參數，可以在時間線上方便地修改訊號源和目標類了。勾選debug後，能更好地顯示訊號傳播過程
> 事件關鍵影格的參數：陣列，不行。結構體包裝的陣列，行。Actor陣列，不能改。軟引用陣列，能改。這什麼抽象用法啊喂(ﾟДﾟ≡ﾟдﾟ)!?

</details>

### 0.5-pre2
![image](https://raw.githubusercontent.com/wiki/piggestpig/Unreal-Mineprep/image/0.5-pre2%E5%B0%81%E9%9D%A2%E5%9B%BE.jpg)

Mineprep 0.5-pre2帶來了生物模型大改的階段性成果，同時也新增了許多媒體播放和後期合成的素材，我們用其製作了貓meme《撿到一隻快樂小幽靈》
> 需要注意的是，這個版本由於升級到UE5.6的產生了新的bug（例如MC像素文字損壞、第三人稱運動匹配角色開啟物理互動後閃退），目前透過停用部分設定來避免問題，最終的修復需要等Mineprep 0.5正式版釋出

<details>
<summary> 檢視細節 </summary>

- 新增 `村民`、`烈焰使者`、`凋零怪`、`豬布獸`、`雪人`、`狼`、`貓`、`悅靈`、`流浪商人`、`山貓` 、`地獄幽靈`、`小幽靈`、`快樂幽靈` 的模型
  - 其中，村民和流浪商人包含NPC版本
  - 村民有特製的材質，透過更改紋理貼圖來切換職業和生態域
- 所有生物模型配置了骨骼級別的重定向設定。人與動物可以共用動畫片段，效果比之前更好。清理了許多舊的動畫片段，製作了新的動畫片段
- 觀眾人群散佈器完成第一階段開發工作，可以設定隨機皮膚和隨機動作
- 新增 `營火`、`營火煙霧粒子`、`爆裝備粒子`、`愛心粒子`、`噴濺藥水粒子`
- 新增 `監控攝影機`，能捕獲畫面並寫入渲染目標紋理貼圖，顯示在別處。目前有三種模式：“預設(可遞迴)”，“後處理(帶景深)”，“背景透明”。
- 修改了材質參數，新增`頂點顏色`，在準備場景時自動識別，值設為1會讀取不同生態域的植物顏色，適用於從MiEx匯出的usd模型。"[著色模型] 1預設/2次表面"已棄用，改為原來的`照明強度`, ≥0使用次表面，<0取絕對值然後使用預設光照
> 虛幻引擎的自發光很迷 (╯°口°)╯ 有的模型用次表面能發光，有的僅支援預設光照。有的模型只能在次表面下調節照明強度，換預設光照又不行了。總之發光亮度和照明強度的各種組合都可以試試
- "放置物品"旁邊新增了`選擇透明圖片，匯入為3D模型`的按鈕，同樣是遠端呼叫Blender的MCprep外掛功能
- "MC攝影機"，"搖臂攝影機"，"導軌攝影機"新增了`初始化跳過緩動`選項，在編輯器檢視和渲染剛開始時停用緩動，立即移至所需位置。新增`硬切`按鈕，用於在時間線上切換攝影機，這是第一個轉場功能。
- "記憶體預載入"和"注入本地化變數名"現在會在後臺非同步載入資源，提升流暢度
- 更新了“搖晃振動彈跳軌道”，能根據起始影格計算當前時刻，並添加了更多預設
- "媒體摳像播放器"在切換不同素材時會保持高度一致，將"拉伸影像"設為0可自訂縮放。新增`是像素貼圖`選項和一些動畫片段預設
- `錄製子面板`新增許多參數：使用當前時間線、建立副本、直接錄製動畫到物件上、每個物件建立子序列、錄製影格率、錄製前倒計時、遊戲模式。錄製後會自動處理動畫片段，修復了破壞方塊時錄製粒子的bug
- 頂部MC選單欄新增一套渲染模式：  
①儲存渲染設定並切換空關卡  
②從空關卡渲染動畫(節約顯示記憶體)
- 更新了其他功能子面板的輝光參數，普通模式和卷積模式分別設定閾值和倍率
- 【實驗性功能】新增更多編輯器快捷鍵，例如Ctrl+Alt+7顯示物件並打關鍵影格，Ctrl+Alt+Shift+7隱藏物件並打關鍵影格。具體可在自訂按鍵子面板中檢視
- 導播臺添加了沿-Z軸吸附的按鈕，修復了碰撞檢測bug
- 降低了Mineprep後期處理體積的預設暗角強度，加快了曝光調節速度
- 修復了骷髏皮膚的UV問題
- 修復了"遮罩層"顯示框未能正確縮放的bug
- 修復了"丁達爾體積光"光束不發散的問題
- 修復了"VFX地獄傳送門"從傾斜角度觀看時出現的問題
- 修復了材質和攝影機晃動未正確載入的bug
- 修復了靜態模型綁定父級失敗的bug，現在會修改為可移動
- 修復了準備場景的碰撞箱bug，現在能正確停用碰撞

</details>

<details>
<summary> 📜展開快照 </summary>

#### 25w29a
- 媒體摳像播放器（以及散佈器、粒子）新增“匯入影片”快捷按鈕，匯入的影片儲存在/mc/media資料夾下，會自動建立時間線軌道和媒體紋理
- 生成器面板新增兩個過濾器類別，分別表示力場和工具
- 修復了放置生物錯誤的bug，之前的名稱搜尋演算法會把豬當作豬布林
- 材質遮罩參數的小數位有了三個新功能
  - x.25 表示僅在遮罩後方顯示
  - x.5 表示在遮罩前方（或無遮罩時）顯示。可以用來製作走出傳送門的效果
  - x.75 表示模型在任意遮罩層後面的部分都會投射陰影

#### 25w28a
- 新增`媒體摳像散佈器`和`媒體摳像粒子`，用於高效能、大批次播放影片素材
  - 二者都有三個材質槽位，第一個用於摳像快取，第二個用於描邊陰影等後期效果快取，第三個是共享的最終顯示材質
  - 媒體摳像散佈器會整齊劃一地播放影片。每個實例可以單獨編輯
  - 媒體摳像粒子支援快取先前影格，讓不同的粒子有不同的時間差量，陸陸續續播放影片。注意，快取影格過多會佔用大量顯示記憶體
  - 更多功能正在開發中
- 新增`簡單跟隨路徑控制器`，用於快速、高效能地移動方塊或普通生物模型（不能用於NPC或物理模擬）
  - 選中場景中的物件，使用附加元件綁定一個“簡單跟隨路徑控制器”。之後可以在控制器中新增或刪除受控物件。附加元件時如果有選中的控制器，會直接更新它，不再建立新控制器
  - 移動路徑是預先計算的。目前可以各自跟隨曲線運動，整體沿曲線方向運動，或者自己設定目標點
  - 移動時可以保持旋轉或面向移動方向。由於生物模型的初始旋轉角偏了90°，在細節面板新增了“執行時額外旋轉”變數，設定為(0,-90)可修正偏差
- 改進了部分撤銷提示，內容更詳細
- 馬_NPC現在根據隨機種子選擇皮膚

#### 25w27a
- 基礎生物模型新增`FK綁定`、`IK綁定`、`物理綁定`、`運動綁定`的快捷按鈕
  - FK綁定：所有生物都能使用的通用綁定，可操控每個骨骼，製作關鍵影格動畫。點選按鈕會新增分層綁定，疊加到現有動畫片段上，和其他控制綁定相容
  - IK綁定：使用UE5的模組化綁定，例如移動手可以帶動肘和肩的旋轉，目前適用於兩腳生物，不能疊加，會重載現有動畫
  - 物理綁定：UE5.6的新功能，在編輯器中也能生效的物理互動動畫，能與自身骨骼碰撞，不與環境碰撞。理論上適用於所有生物，無需分層疊加到現有動畫片段上
  - 運動綁定：正在開發中，使用UE5.6的locomotor，為多足生物自動生成行走動畫
- 在搖晃彈跳振動軌道中製作了更多預設
- 右鍵外掛面板底部的“MC場景編輯器按鈕”，會先判斷當前模式，如果是預設選擇模式，才會切換到自訂工具模式，否則返回預設選擇模式

#### 25w26a
- 新增`地獄幽靈`，`快樂幽靈`，`小幽靈`的模型和待機動畫。三者可以共用動畫，快樂幽靈和小幽靈可以共享材質（這兩個是雙層皮膚，地獄幽靈是單層）
- 生物模型添加了“物理Ⅰ”、“物理Ⅱ”、“物理Ⅲ”、“物理Ⅴ”、“停用物理互動”的快捷按鈕，用於調整物理互動強度，在執行時生效
- 媒體摳像播放器新增許多快捷按鈕，例如“綠幕”、“藍幕”、“陰影”、“自發光”等
- 大部分方塊和生物材質都支援讀取遮罩了
- 專用的“遮罩層”actor現在可分別設定正面和背面的遮罩，多個遮罩層疊加時預設使用最前方的遮罩，新增“用作可疊加遮罩”，“未設定遮罩時清除後方遮罩”選項框。
- 右鍵場景中的物件，在“指令碼化Actor行為”新增了`用作遮罩層`功能

#### 25w25a
- 新增`媒體摳像播放器`及後期合成相關素材（MC 1.21.6 釋出了，最近很有靈感，來做個快樂幽靈的貓meme！）
  - 媒體摳像播放器是骨骼網格體平面，可以拉伸變形，像生物一樣製作動畫片段
  - 有兩個材質槽位，第一個包含綠幕摳像和調色參數，第二個包含描邊、陰影、邊緣高光等參數
  - 預設情況下接受場景光照，勾選“保持原色”後將顯示原圖
  - 在普通的lumen光追下效果最好，啟用Megalights後無法投射陰影，啟用光線追蹤半透明會失去邊緣高光
- 新增`遮罩層`，可以讓物體僅顯示在特定遮罩中（後期剪輯的實用功能get，配合燈光排除能做出更棒的“4D場景”！），後續會改進所有方塊和生物的材質
  - 總共有8個遮罩層，支援同時寫入多個遮罩。預設為單面，可以在材質參數中啟用雙面
  - 對於應用遮罩的物體，在材質參數中調整“遮罩層”，逐位過濾遮罩。0為不啟用，正數在遮罩內顯示（例如12表示遮罩層1和2的重疊區域），負數在遮罩外顯示（比如-1表示排除遮罩1），如果要同時接受和排除遮罩，用0分割（比如1203表示在遮罩層1、2內+3的外面才顯示）
  - 實際上，任意物體都可以作為遮罩層，在細節面板裡開啟自訂深度後調整自訂模板的數值即可。不過這裡涉及位掩碼運算，之後會在外掛面板的生成器板塊做點更簡單的預設
- 新增`簡單倒角覆層材質`，使用附加元件新增到模型上，使邊緣變得圓滑。目前是螢幕空間效果，對摺到背後的面無效。
- 使用鏡頭試拍錄製器，結束後能自動開啟關卡序列並執行“處理錄製的動畫”了！點選外掛面板下方新增的錄製按鈕，可以快速錄製場景中選中的物件。新功能有許多bug，正在慢慢修復中


#### 25w24a
- 所有實驗性功能已更新至UE5.6！修復了雙目立體全景渲染拼接錯誤的bug
- 清理了許多舊的生物模型，優化了不同尺寸骨架的相容性，修復動畫素材，為兩足生物製作了新的模組化IK綁定
- 優化了動畫藍圖，NPC支援在時間線上使用動作片段，基礎生物模型也能像NPC一樣使用事件關鍵影格切換動作。
  - 動畫優先順序為：基礎動畫（迴圈播放/NPC運動）< 時間線動作片段 < 切換動作的事件 < 癱瘓起身
  - 基礎生物模型會迴圈播放預設動作片段，可設定速度和時間偏移，能與時間線的其他動作混入混出。另外，物理模擬前不會啟用Tick，提升了效能
- 新增`觀眾人群散佈器`，使用從基礎生物模型派生出的專用觀眾模型，可以根據種子隨機挑選皮膚和動作，面向特定目標。效能經過最佳化，在預設狀態下能以60fps帶動1000個人；支援各類事件，能用導播臺批次控制
- 修復了UE5.6更新帶來的部分問題：最佳化方塊體積雲的顏色，啟用新版光線追蹤半透明
- 緩解了MC天空在午夜月亮位置會瞬移的問題。
- 加快了預設情況下自動曝光的調整速度，在明暗場景中快速切換更流暢
- 外掛面板底部新增兩個圖示
  - `MC場景編輯器按鈕`：【實驗性功能】左鍵顯示資訊，右鍵切換至自訂工具模式
  - `錄製按鈕`：正在開發中，左鍵顯示資訊，右鍵使用鏡頭試拍錄製器記錄關鍵影格動畫
- 虛幻引擎似乎不會在編輯器中進行垃圾回收，時間久了一運行遊戲就會卡幾秒。因此我們在外掛的部分功能中手動觸發垃圾回收，如放置模型和方塊，開啟輸出資料夾，彈出提示框後等等。這些功能受到卡頓的影響較少
- 【實驗性功能】按Ctrl+Alt+3隱藏/顯示工具欄圖示的文字名稱，按Ctrl+Alt+4隱藏/顯示藍圖建立的元件
- 新增`動態設計效應器`，選中場景中的模型，點選附加元件或Ctrl+Alt+5即可快速綁定Free Placement克隆器和效應器，預設效果是讓範圍外的方塊逐漸縮小下移消失（實驗性功能的自訂快捷鍵經常有所變動，之後會單獨開一個板塊來記錄）

#### 25w23a
- UE5.6正式釋出了，這是最後一個老版本快照更新！
- 修改了各種生物的骨骼，在UE5.6中可直接使用新的模組化綁定。不過原先的動畫素材和物理資產出了問題，需要慢慢修復
- 簡單NPC和基礎生物模型經過修改，提供頭身一體、無手持物品的簡化版本
- 簡單NPC的狀態機動畫投入使用了（實際上，目前只用了混合空間，沒有狀態機）
  - 首先按照風格分為三類：預設動畫、官方宣傳片、動作捕捉。可以在細節面板中快速更改動畫風格
  - 每一種風格都可填充所需動畫，設定相關屬性。有四檔移動型別可供選擇
  - 在曲線中配置移動速度和移動型別的對應關係
  - 如果同一移動型別有多個動畫，會根據它們的隨機挑選權重和生物的隨機種子進行挑選。此功能為之後的人群模擬而設計
- 自訂鍵控動畫經過修改，可以新增任意數量的動畫，然後配置按鍵序號、動作/表情、緩入緩出等屬性，適用於簡單NPC和高階NPC。原先的 1 2 3 4 5 6 切換動畫快捷鍵依然生效
- 清理了一部分老舊的模型和動畫

#### 25w22a
- 繼續製作狀態機動畫。目前發現舊的動畫片段有首尾迴圈等諸多問題，即將和生物模型一起大改
> 我們，馬上，就能，升級引擎版本了！！

> 近日瀏覽UE5.6的更新路線圖，發現nDisplay支援DLSS了 (話說以前不支援的嗎∑(￣□￣;)...誒不對，DLSS通常要晚幾個月釋出，怎麼已經用上了，難道有內鬼？！）於是自己嘗試編譯了一下，還真成功了！現在萬事具備，只待正式版釋出，UE5.6帶來了大量新功能、新介面和效能最佳化，非常適合製作動畫

#### 25w21a
- 初步製作了`MC狀態機動畫藍圖`，將用於簡單NPC，適合蟲子、鳥、魚等非兩腳生物；同時這是一個輕量級的程式，在大型人群中比運動匹配有著更好的效能。
- 初步製作了`搖晃彈跳振動軌道`，這是一個通用的時間線軌道，附帶多種快捷預設，能為所有物件新增位移、旋轉或縮放動畫
- 初步製作了`粒子環境碰撞箱`，提供最高精度的GPU碰撞，旨在解決距離場精度低、遠處會消失的問題， 為新的大型人群粒子做好準備
- 緩解了蟲群粒子（蠹魚）由於距離場碰撞精度低而平地起跳的bug

</details>

### 0.5-pre1
![image](https://raw.githubusercontent.com/wiki/piggestpig/Unreal-Mineprep/image/0.5-pre1%E5%B0%81%E9%9D%A2%E5%9B%BE.jpg)
Mineprep 0.5的第一個預覽版來了，全新動畫《捅了銀魚窩了》現已釋出！
> 這可能是最後一個支援UE5.5的版本——我們將在不久後升級引擎，非實驗性功能已適配UE5.6。

<details>
<summary> 檢視細節 </summary>

- 蟲群粒子新增全域性粒子間碰撞功能，有“寫入”和“讀取”兩個選項，會消耗更多的顯示卡效能和顯示記憶體
- 蠹魚、終界蟎、蜘蛛（洞穴蜘蛛）的普通模型已加入放置生物功能中，NPC需要等未來進一步修改
- 改進了語言本地化模組，現在會在開啟外掛面板或切換語言時從csv檔案生成pickle快取，刪除空格，提升讀取速度。各板塊前面都添加了屬性列，比如用於放置生物/預設素材/附加元件板塊的型別過濾器
- 生成器面板新增10種`型別過濾器`，左鍵選擇此類，中鍵僅選擇此類，右鍵排除此類。放置生物選項右邊還添加了`嘗試放置生物寶寶`按鈕
- 【實驗性功能】快捷鍵面板增加了`編輯器快捷鍵`綁定條目，可以自由新增或修改快捷鍵，更加方便了！
- 修改了NPC的輔助碰撞箱，根據細節面板中的參數動態生成，還可以使用head.ear_l等語句為其他部位綁定碰撞箱，詳情參見工具提示。輔助碰撞箱已經下放至普通模型。“背景生物散佈器”預設情況下會停用碰撞箱以提高效能。
- 第三人稱運動匹配角色（高階運動匹配NPC）現在自帶用於粒子和材質的全域性力場
- 新增`灰塵粒子`
- 新增`MC_Head_Face2D`和2D表情皮膚材質，完全由材質參數控制表情動畫。更多功能正在開發中，未來將適用於所有生物
- 預設MC資源包現在放在安裝包中，安裝時不再複製，而是提供檔案地址連結，大幅提升安裝速度
- 修復了放置方塊和物品時由於資產命名衝突而失敗的bug

</details>

<details>
<summary> 📜展開快照 </summary>

#### 25w17a
- 改進和完善了MC場景編輯器：
  - 用滑鼠中鍵獲取方塊時，會先在物品欄中查詢已有方塊，如果沒有的話就在空格子裡建立方塊，如果沒有空格子才會替換當前方塊。更符合MC的操作邏輯了
  - 獲取大地圖模型方塊時會根據面朝向解析植物，斜面（如草、花、甘蔗等）將使用草的模型，新增對應材質，自帶植物搖擺
- “植物搖擺”新增`互動強度`選項，可與生物或力場互動，被排斥開來。當前只能用於單個草的模型，不適用於匯入的大地圖模型
- 重新設計了全域性力場，能夠與粒子和材質互動，當前最多支援64個力場，可以透過調整“Niagara全域性變數渲染目標”的尺寸來增大上限。（注意：數量過多效能較差）
- 使用“附加元件”功能可向任意物件新增`粒子/材质力场`元件，寫入全域性力場
- 新增`距離場碰撞箱包裹器`，為GPU粒子生成精度較高的環境碰撞箱。使用時需要拖動它與場景中的方塊對齊。
- 新增`超彈性物理材質`，擁有1.5倍彈力，在物理模擬時會越彈越高，可以當粘液塊用
- 修復了“曲線引導粒子”附加到其他物件上時粒子消失的bug。在粒子參數中可以指定其他曲線了

#### 25w16a
- 本週製作了里程碑式的新功能：MC場景編輯器！並且對粒子系統等功能進行了重大更新
- `MC場景編輯器`
  - 像玩MC一樣在虛幻引擎中放置、破壞、獲取方塊，四處移動，編輯場景！
  - 點選左上角的：“選擇模式”->指令碼化工具模式，即可看到MC場景編輯器按鈕
  - 進入場景編輯器後，用WASD移動，Shift/Q下降，空格/E上升，Ctrl加速。按住右鍵拖動滑鼠以旋轉視角
  - 滾動滑鼠滾輪/按1~9/左鍵點選切換物品欄。長按物品欄可以拖動。在細節面板中，可以設定方塊陣列、物品欄縮放、格子數量等參數
  - 左鍵破壞方塊（或選中非方塊模型，按delete刪除）
  - 右鍵放置方塊，自動根據視角在水平方向上旋轉
  - 中鍵獲取方塊，會嘗試解析模型、把動態材質儲存為材質實例。對於單個方塊的小模型，直接獲取它；對於匯入地圖後的大模型或者非MC模型，獲取滑鼠下的材質，用它新建一個方塊。
  - 方塊的座標和大小使用相對於導播臺的變換，可以為小數。MC導播臺現在有一個黃色的方塊模型，在渲染時會自動隱藏。匯入地圖後，把MC導播臺拖到上方，先按END鍵吸附到地面，再去細節面板裡點選按鈕沿X軸和y軸吸附到邊上，使參考方塊與場景對齊。這樣放置的方塊也會與場景對齊。縮放導播臺後，新放置的方塊會隨之縮放。
  - 可以撤銷和恢復操作
  - 可以使用鏡頭試拍錄製器錄製放置和破壞方塊的操作（需要新增方塊和附近生成的actor作為錄製物件）模擬執行編輯器場景時，破壞方塊有破碎動畫和粒子特效，時長可在細節面板中修改，錄製後需要點選“處理錄製的動畫”
- 在時間線工具欄中添加了“🛠️”按鈕，點選處理錄製的動畫
- 錄製動畫時，第三人稱運動匹配角色扔出的手持物品也能自動記錄模型了！
- 所有粒子系統在細節面板中添加了三個按鈕：建立`生命週期軌道`、`快取軌道`、`觸發器軌道`。
  - 第一個功能最常用，開啟時間線後，點選按鈕，會在當前影格新增Niagara系統生命週期軌道，粒子會從這一影格開始播放，根據影格數進行確定性渲染。
  - 對於下雪粒子等需要一段時間才能飄落的粒子，可以把生命週期軌道向前拖，計算一段時間後的狀態。
  - 如果需要倒放粒子動畫，建議烘焙快取。如果需要多次觸發，可使用觸發器軌道打關鍵影格。
- 在MC導播臺中，可以設定`重載材質時間`  
  值為0時不重載，材質動畫自動播放  
  值>0，使用此作為全域性材質時間  
  值<0，將絕對值和材質自動播放的時間相加
- 右鍵場景中的物件，在“指令碼化Actor行為”欄目下添加了`簡單描邊`功能。
- 優化了導播臺廣播事件的效能，最大傳播範圍作為參數下放到每個物件上。
- 修復了基礎方塊模型的一些材質bug

#### 25w15a
- 本週對核心功能進行了大更新：準備場景、更換材質、附魔、植物搖擺、自發光可以使用全新的動態材質了！執行速度大幅提升！你可以在細節面板中快速修改參數，破壞方塊，以及使用實驗性功能一鍵打關鍵影格。這些操作可以撤銷，不影響原有材質
- 在外掛面板的進階設定中，有動態級別滑條，0為原來的靜態材質，1、2、3為動態材質。預設值設為2
  - ① 用於生物皮膚的材質。包含以下參數：  
    [著色模型] 1預設/2次表面  
    發光亮度  
    次表面顏色RGB+不透明度A  
    紋理顏色  
    金屬/高光/粗糙/各向異性  
    紋理貼圖  
    自發光蒙版  
  - ② 用於方塊的材質。添加了以下的額外參數：  
    法線強度  
    破碎程度  
    動畫速度/U縮放/V縮放  
    反轉:紋理/金屬/高光/粗糙  
    法線貼圖  
    粗糙貼圖   
    金屬貼圖  
    高光貼圖
  - ③ 用於附魔和植物搖擺的材質（是的，兩者可以相容了！），效能開銷最大。添加了以下的額外參數：  
    搖擺幅度  
    搖擺速度  
    附魔縮放/速度/對比度/底色  
    附魔顏色  
    切線貼圖  
- 使用準備場景等功能時，會自動應用單面/雙面材質、漸變動畫紋理等選項。
- 使用更換材質功能時，可以從材質包中自動讀取自發光蒙版了（僅限動態準備材質）
- 雙擊某個具體參數，會自動判斷靜態和動態材質進行處理。雙擊“靜態材質”，可以退回模型的預設材質。
- 我還嘗試給細節面板的參數和關鍵影格按鈕新增工具提示，但是目前有些bug，需要摺疊面板再展開才能刷新出來，滑鼠懸停時顯示提示。
> 材質參數面板是虛幻引擎的實驗性功能，好像挺容易閃退的，希望官方速速修復bug
- 新增`可破壞方塊`，擁有“破壞”事件，觸發時播放破壞方塊的動畫和粒子效果，可以在導播臺批次觸發。之後會新增更多功能。
- 改進了頂點動畫材質，慢放時可以平滑插值。

#### 25w14a
> MC大電影上映了，老玩家第一時間就去觀影~ 還記得最早聽說電影的消息是在初中，經過好幾次跳票，轉眼間我都成大學生了。雖然劇情比較老套，但整體是挺歡樂的，Mojang憋了這麼多年終於把電影拍完了！下週我大概能做完新的動畫影片，希望之後能月更 (ﾉ>ω<)ﾉ  
> 至於Mineprep後續的更新嘛，大機率不會做電影這種寫實風格，還是原版&材質包更合適
- 新增蜘蛛的頂點動畫實例模型+洞穴蜘蛛的皮膚材質。
- 新增`蜘蛛群粒子`，將“模型二佔比”參數設為1就是洞穴蜘蛛
- 修復了後期景深模糊和調色示波器。由於後期處理鏈圖在UE5.5中壞掉了，不得不使用後期處理元件重做。目前加入了一個新功能，可以更改用於散景光斑的貼圖，根據alpha通道確定背景虛化的光斑形狀
- MC天空的普通方塊雲現已改為不透明材質，從根源上解決光線追蹤半透明的問題
- 修改了準備材質等功能的處理物件——不再需要輸入資產資料夾路徑，而是獲取內容瀏覽器中的選中項（包括單個資產和資料夾）

#### 25w13a
- 新增蠹魚的頂點動畫實例模型。蟲群粒子總體分為兩類，一類是無視重力四處爬牆，一類是正常移動跳上方塊
- 【實驗性功能】“MC導播臺”的全域性重力已更改為三維向量。若沒有安裝實驗性功能，會忽略xy軸，只調整z軸重力大小
- 新增`徑向力場`，給範圍內的物件持續施加引力和斥力，可選擇線性衰減或常量力。透過“衝擊”事件能施加瞬時衝量，可同時癱瘓生物。調整作用於粒子系統的倍率，可以把自身註冊到全域性力場，影響粒子系統。目前最多支援8個全域性力場
- 大改粒子系統，建立了“MC粒子總類”和“MC粒子元件總類”。未來，所有粒子可以透過導播臺修改全域性重力，也可以被徑向力場影響。
- 【實驗性功能】粒子參數旁邊有關鍵影格按鈕了！點選即可在時間線上新增關鍵影格

#### 25w12a
- 新版`MC天空`基本製作完成，在保留原先功能的基礎上帶來了更好的畫質
  - 視口頂部有一個`時刻`按鈕，點進去可以快速調整當前時間
  - 在細節面板中可的分別調整天數和小時，然後點選“總時間-用於關鍵影格”右邊的按鈕製作關鍵影格動畫
  - 現在有3種雲可供選擇：①方塊雲 ②方塊體積雲 ③體積雲（UE5.5新版體積雲明顯好看多了）
  - 優化了方塊太陽和方塊月亮在雲霧後面和光線追蹤半透明下的顯示效果
  - 自動曝光大幅改進，預設的EV100參數同時適用於白天和夜晚，HDR渲染也更好看了
- 繼續製作幾個月前的蜘蛛群粒子，目前實現了爬牆功能，並製作了首個頂點動畫實例模型（終界蟎）

#### 25w11a
- Mineprep 0.5的主題暫定為“荒野更新”，主要目標是製作更多的生物和高效能NPC群體
- 實驗性功能已全部更新至UE5.5
- MC天空即將大改，使用虛幻引擎新提供的Day Sequence外掛作為模板

</details>

### 0.4 : 足跡與故事
![image](https://raw.githubusercontent.com/wiki/piggestpig/Unreal-Mineprep/image/0.4%E5%B0%81%E9%9D%A2%E5%9B%BE.jpg)
0.4版本正式釋出了！這是一個重大更新，包含了許多新功能和改進，也是最後一個支援UE5.4的版本。
快來看看有哪些新功能吧

![image](https://raw.githubusercontent.com/wiki/piggestpig/Unreal-Mineprep/image/0.4%E6%9B%B4%E6%96%B0%E6%B1%87%E6%80%BB1.jpg)
![image](https://raw.githubusercontent.com/wiki/piggestpig/Unreal-Mineprep/image/0.4%E6%9B%B4%E6%96%B0%E6%B1%87%E6%80%BB2.jpg)
- 以上是精彩集錦，更多內容參見下方的快照。
- 從這個版本起，我們不在Releases中釋出內容範例場景，而是打包當前庫，下載解壓後能看到安裝包和各種資源。（之後考慮在其他地方釋出內容範例和精簡版外掛）

<details>
<summary> 📜展開快照 </summary>

#### 0.4-RC1
- 這是0.4版本的最後一次內容更新！安裝包已經準備就緒
- 新增`腳步粒子`,在生物跑步或落地時根據地面材質產生粒子效果。第三人稱運動匹配角色（高階運動匹配NPC）自帶腳步粒子，你也可以使用“附加元件”按鈕把它新增到其他物件上。
- 新增四肢硬直的`MC_Straight_Body`、`MC_Straight_Slim_Body`，和胳膊與腿分成兩截的`MC_Segment_Body`、`MC_Segment_Slim_Body`四種基礎生物模型。
- 為所有生物添加了根碰撞箱，修復了開啟物理模擬後彈出警告的bug
- 所有生物與NPC都有了在倒地後起身的功能。點選小鍵盤0能夠在癱瘓和起身之間切換。你也可以使用事件關鍵影格進行控制、重載起身動畫。
- 所有生物都有了動態材質，可以調整顏色等屬性，開啟實驗性功能後還能一鍵新增材質關鍵影格。
- 表情動畫預設使用統一的形態鍵動畫，可以相容不同模型了
- 修復了一部分因改變重力方向產生的bug。簡單NPC能正確地在牆上隨機移動和跟隨目標了。第三人稱運動匹配角色的bug仍然比較多
- 現在每個生物都有了自己的隨機種子，實現更精細的控制。你可以在MC導播臺修改或重新整理全域性隨機種子。
- 準備材質的“次表面散射”精簡為一個RGBA顏色參數，其中RGB決定顏色，A決定次表面不透明度。同時修復了一些bug
- 大改並統一了攝影機的功能和參數。“MC攝影機”、“搖臂攝影機”和“導軌攝影機”現在可以設定平滑移動/旋轉、視野、光圈、畫面尺寸和遮幅、追蹤目標、聚焦目標/正交/自動希區柯克變焦、後期移軸模糊和區域性模糊。
- 修復了大量錄製動畫的bug和閃退問題。“MC第一人稱攝影機”能錄製攝影機晃動了，結束後需要點選外掛面板“處理錄製的動畫”按鈕。“第三人稱運動匹配玩家”能直接記錄攝影機運動了，無需同步玩家攝影機
- MC導播臺新增DLSS/FSR選項，安裝相關外掛後，可以設定超解析度、光線重構（目前檢視預覽和渲染似乎不一致）和影格生成（僅限獨立視窗遊戲模式，不支援渲染）
- MC導播臺批次呼叫事件的參數有所變更，現在訊號源是Actor陣列，目標是Actor類陣列，有利於過濾物件、提升效能
- 改進了渲染輸出面板
  - 可以同時輸出一影格畫面的多種格式jpg/png/exr（含DWAA壓縮和不壓縮兩種格式）
  - 畫面解析度可以動態從語言本地化表格中載入，並且應用於場景中的攝影機。目前有以下預設：  
  1080p #1920x1080  
  2K #2560x1440  
  4K #3840x2160  
  VR_4K (2:1) #4096x2048  
  VR_8K (2:1) #8192x4096  
  DCI_2K (1.89:1) #2048x1080  
  DCI_4K (1.89:1) #4096x2160  
  老電影 4:3 #1920x1440  
  寬屏 2.39:1 #3440x1440  
  豎屏 9:16 #1080x1920
  - 新增Prores影片編碼選項，使用虛幻引擎自帶外掛，跳過序列影格直接輸出影片。極高畫質（Prores4444）支援透明度；但是不支援HDR
  - Mineprep 3D攝影機組即將棄用，現在點選渲染輸出面板的`3D`勾選框，會自動生成nDisplay 3D攝影機組。可以一鍵渲染3D動畫，分別輸出左右眼的Prores影片或序列影格
  - 初步添加了`渲染音訊`選項（但是虛幻引擎自帶功能非常簡陋，沒什麼可選的，有時還會產生bug）
  - 可以自動應用MC導播臺的DLSS/FSR預設
- 頂部選單欄新增一些除錯和開發功能。安裝實驗性功能後，點選**頂部選單欄-MC-開發-注入本地化變數名**，可以翻譯細節面板中的變數和函式名稱！
- 新增多種MC字型，包括Minecraft-Five，Minecraft-Seven，Minecraft-Ten，Unifont，Standard Galactic Alphabet，illageralt，可以在“MC像素文字(3D)”中使用
- 優化了光追半透明下的水材質
- 放置方塊和物品時會自動把“移動性”設為“可移動”
- 預設素材新增`區域性調色蒙版(2D)`、`區域性調色區域(3D)`、`空物體(路標)`。安裝實驗性功能後，可以使用Ctrl+Alt+0快速放置空物體；附加元件新增綁定父級至最後選中項，即之前的Ctrl+Alt+P快捷鍵
- 好消息：UE5.5.4終於修復了中文資料夾層級錯亂的bug！淚目！！！DLSS也支援UE5.5了，總算可以更新了！Mineprep 0.4 將會是最後一個支援UE5.4的版本

#### 25w05a
- 外掛安裝包製作完成！Mineprep 0.4很快就能釋出了
> 0.5版本很可能會繼續使用UE5.4開發，因為UE5.5出現了中文資料夾層級錯亂的bug，一直到現在也沒修好 qwq
- 添加了幾個快捷鍵（實驗性功能），與Blender非常相似：
  - F12  渲染圖片
  - Ctrl+F12  渲染影片
  - 小鍵盤0  進入攝影機檢視
  - Ctrl+Alt+小鍵盤0  將攝影機移動到當前位置並進入攝影機視角
  - 快速綁定父級的快捷鍵從Ctrl+Alt+0更改為Ctrl+Alt+P（Ctrl+P已被虛幻引擎佔用）
- “一鍵渲染”功能在未開啟時間線時，會在視口位置使用`臨時攝影機`進行渲染；渲染圖片和影片能自動適配SDR/HDR了
- 頂部選單欄回來了，在`MC`選單下有渲染圖片、渲染影片、開啟輸出資料夾和重啟外掛面板的按鈕
- 透過新增“DoNotRecord”標籤，可以讓鏡頭試拍錄製器跳過特定元件。現在NPC生物不會錄製額外的碰撞箱了，能提高效能並精簡軌道

#### 25w04a
- 外掛安裝包來了！用Blender開啟`Mineprep_installer.blend`檔案，執行指令碼，即可根據指引快速建立專案檔，或者把Mineprep安裝到已有的專案檔中。安裝時可以挑選實驗性功能、修改外掛設定、指定ffmpeg路徑。更多內容正在開發中。
- 【實驗性功能】可以選擇mp4或mov作為影片輸出格式
- 初步添加了和macOS相關的模組，例如影片編碼的Apple GPU選項、yuva420p色度抽樣選項（用於帶Alpha通道的透明H.265影片）
> 由於我沒有mac，暫時無法測試這些功能是否有效（¯﹃¯）
- 底部工具欄新增`自訂按鍵選單`，可以修改按鍵對映並儲存到本地
- 修復了快捷鍵Ctrl+Alt+0 切換新舊Gizmo小工具失效的bug。第一次使用時可能會彈出編輯器偏好設定視窗
- 改進了語言本地化的載入方式，這次應該是最簡潔的形態了

#### 25w03a
- 外掛面板底部新增工具欄，把滑鼠移至圖示上即可彈出新的選單；點選圖示可以鎖定/隱藏選單
- `外掛設定選單`
  - 點選`重新初始化外掛`按鈕，可以載入偏好設定、初始化影片渲染（部分操作需要實驗性功能或重啟）。
  - 這裡記錄了全域性設定，比如`UI介面縮放`（實驗性功能），`朗讀滑鼠下文字`（實驗性功能），`記憶體預載入`（開啟外掛時把所有資源載入到記憶體中，啟動慢但執行更流暢）
- `顏色設定選單`
  - 這裡可以開啟HDR顯示輸出，調整編輯器HDR亮度，開啟調色示波器，調整波形圖的取樣步長和亮度
- 方塊體積雲現已整合到“MC天空”中
- 新增兩個快捷鍵（實驗性功能）：
  - Ctrl+Alt+0 切換新舊Gizmo小工具
  - Cltl+Alt+1 切換預覽選中攝影機的視窗
- 生成器面板現已支援全語言搜尋內容
- 外掛面板選項框和事件關鍵影格軌道支援多語言翻譯了

#### 25w02a
- 填坑了填坑了，外掛面板底層改造終於完成了。準備場景等核心功能變得更加高效
- 右鍵點選大按鈕，可以在進階設定中單獨顯示它的參數
- 雙擊特定的文字可以直接執行此項（將滑鼠放在文字上，如果能雙擊，會彈出提示）
- 現在能在外掛面板中直接控制“MC天空”的時間和太陽角度
- 更新了附魔材質的參數，取值範圍更合理
- 【實驗性功能】 在處理材質後會刪除未使用的節點並重新整理材質
- 現在可以像Blender一樣用快捷鍵綁定父級了：
- **綁定父級**  
  `前提`：啟用實驗性功能   
  `物件`：綁定其它視口選中項 ——> 最後選中的Actor  
  `效果`：在視口中選擇多個物件，觸發此功能後會彈出一個面板，顯示最後選中的Actor+所有元件+骨骼名稱，你可以把其他選中的物件綁定到具體的元件或骨骼上。  
  `可選項`：綁定目標  
  `快捷鍵`：預設為Ctrl+Alt+0。可在偏好設定中更改。
- 修復了半透明材質無法投射陰影的bug

#### 25w01a
- 新的一年，來一次實用的大更新~
- 【實驗性功能】材質關鍵影格按鈕  
  - 點選材質參數右邊的按鈕即可在時間線上新增關鍵影格！極大簡化了操作流程
  - 需要開啟Virtual Production Utilities外掛。參數面板會展示材質實例中所有打勾的參數
  - 目前支援靜態網格體、骨骼網格體的基礎材質，以及浮點、向量和紋理貼圖三種參數型別
- 更新了附魔元件，能在編輯器中即時顯示自訂附魔了，還可以新增材質關鍵影格
- “準備場景”新增次表面散射參數
- FPV飛行攝影機現已支援手柄，但是手感一般，按鍵可能會大改。
  - 左搖桿↑↓:前進/後退，←→:橫滾
  - 右搖桿↑↓:俯仰，←→:左右偏航
  - 左扳機下降，右扳機上升
  - 按下左右搖桿急剎

#### 24w52a
- 今年的最後一次快照更新！
- 新增了大量實驗性功能，很快就會整合到外掛面板中。
  - 用python非侵入式呼叫C++函式，即使實驗性功能損壞，也不會影響原有功能
  - 包括調整編輯器UI縮放，設定預覽攝影機視窗，獲取滑鼠下的文字，啟用Tick多執行緒等內容
  - 在/Plugins/Mineprep內容 資料夾中新增`Mineprep自訂快捷鍵`藍圖，其中有多個自訂事件。第一個會在後臺每隔一段時間（預設0.5s）自動觸發，時間間隔可以用控制檯命令 Mineprep.TickInterval 設定
  - 新增10個可自訂的快捷鍵。按鍵綁定儲存在偏好設定的Mineprep條目下，執行的操作儲存在“Mineprep自訂快捷鍵”藍圖中
  - UE4有一個官方的新手教學外掛，很可惜它停止更新了。這是個好東西，我把其中一部分功能修好了，以後說不定能新增一些MC動畫教學（嗯，應該是1.0版本之後的事了）
- 修復了“nDisplay3D攝影機組”的左右眼視角問題
- 重寫了大部分“準備場景”的功能。未來會對常見的實心方塊使用單面材質，修復距離場碰撞箱問題，避免粒子穿模。
- 優化了第三人稱運動匹配角色（高階運動匹配NPC）的腳步聲音效，當沒有物理材質時，會嘗試從普通材質名判斷方塊種類。
- 再次優化了編輯器Tick和構造函式相關問題，搖臂攝影機、導軌攝影機等預設素材能在編輯器中正常緩動和追蹤目標了。藉助Livelink元件，這次是真正實現了編輯器內Tick
- 使用“執行緒安全更新動畫”優化了動畫藍圖的效能

#### 24w51a
- 最新發現，方塊體積雲在場景捕獲中顏色異常，需要改進3D攝影機組。為此，我使用UE官方的外掛，初步製作了`nDisplay3D攝影機組`,`nDisplay3D渲染配置`。
  - 新方法的顯示記憶體佔用受畫質影響較大，推薦使用極高畫質，節約顯示記憶體
  - 分別輸出左眼和右眼的影像序列影格，這正好符合達芬奇的3D影片同步模式。
  - 理論上，它能使用兩張顯示卡同時渲染

#### 24w50a
- 修改了所有隨機數生成方法，使多次渲染的結果一致
  - 可以在MC導播臺設定隨機種子
  - NPC生物會從導播臺拿隨機數
  - 粒子系統在生成時會指定一個隨機種子
- 把mineprep_config.ini修改為Mineprep_config.txt，使用json儲存更多資料型別，並優化了讀取語言翻譯的方法
- 我們成功在虛幻引擎編輯器內開啟了HDR顯示模式！很快會整合到外掛面板中。目前優化了HDR渲染輸出的lut（軸心0 對比度1.22），使其更符合編輯器內顯示效果。
- 優化了調色示波器，在HDR顯示模式下會取樣指數增長的座標軸（0，1，10，100，1000，10000），與達芬奇的示波器類似。由於Rec 2100 PQ 的最大亮度為1000nit，示波器會在3/4處截斷。
- 修復了放置模型、生物時位置經常不在檢視中心的bug。如果放置多個同名模型，會自動新增1、2、3等字尾名以示區分
- 可以在MC導播臺初步設定自訂按鍵映射了
> 小故事：我很快會買一個沒有小鍵盤的輕薄本，自訂按鍵對映就是為它設計的(～￣▽￣)～ 新筆記本的螢幕很好，這周成功測試了用moonlight串流HDR畫面，透過ipv6連上家裡的電腦，以後就可以遠端製作HDR影片了！不過嘛，寒假裡會把它帶到國外用，大概是不能遠端聯機了，那麼輕薄本能否帶動虛幻引擎的光線追蹤呢...

#### 24w49a
- 這兩週在多個方面有了重大發現，從安裝到使用再到渲染，每一環節都會變得更加方便！
- 用後期處理鏈圖重做了移軸模糊，提升預覽質量，支援HDR渲染，還有光圈散景效果。現在所有攝影機的後期模糊由MC導播臺統一控制。
- MC導播臺可以設定“全域性重力”，支援關鍵影格動畫
- 軟引用改造基本完成，外掛啟動速度加快至1~2秒
- 新增方塊體積雲，源自Nostalgia光影，蓬鬆柔軟又不失方塊本色（我最喜歡的體積雲！）
- 優化了渲染時的顯示記憶體佔用，普通情況下減少2-3G，雙目立體全景渲染能減少8G
> 那麼究竟優化了什麼地方呢...不知道 (*´･д･)?! UE5似乎會檢測MoviePipelineGameMode這個字串，我從它繼承了一個子類，不改功能只改名字，顯示記憶體佔用就明顯減少了。目前看來沒啥問題
- 好消息！有辦法在藍圖中訪問更多變量了，很快就能支援在外掛面板設定雙目立體全景渲染（仍然是實驗性功能），之後也不需要把UE5_HDR.cude複製到D盤了。更重要的是，不需要TApython就能使用植物搖擺功能，0.4正式版有望減少前置外掛
- 新增`調色示波器`，在編輯器中即時顯示直方圖、分量圖、波形圖。很快會修改外掛面板，新增更多模組。
- 初步製作了自訂按鍵對映

#### 24w47a
- 新增了一鍵渲染按鈕——匯出影片最簡單的一集！
- **一鍵渲染**  
  `前提`：初始化影片渲染  
  `物件`：當前關卡+開啟的根級序列+Mineprep自訂渲染預設  
  `效果`：更新渲染配置，然後直接開始渲染
> 小故事：我一開始用藍圖做這個功能，怎麼做都會閃退 X﹏X 上網一查，有人說用python可以解決問題。於是，我重新寫了幾乎一樣的程式......你猜怎麼著，它真的不閃退了！
- 繼續使用軟引用最佳化外掛啟動速度，目前已經節約了超過500MB記憶體。
- 摺疊了Readme的快照部分，預設展示大版本更新

#### 24w46a
- 完善了“MC攝影機”的移軸模糊功能
  - 使用後期模糊替代原有景深，可用於正交渲染
  - 能夠在水平和豎直方向旋轉聚焦平面，沿斜線模糊
  - 將“衰減”設為負數，可以讓中間模糊、兩邊清晰
  - 最終渲染質量比檢視預覽更高。目前適配了3D渲染，但不支援HDR和全景。
- 修復了軟引用未能起到最佳化作用的bug（還需額外新增非同步載入節點），底層重構繼續進行中
- “準備場景”功能即將大改——首先，我們會檢測選中的模型、材質、紋理有沒有重複，在某些情況下大幅提升效能；其次，每個參數都可以透過雙擊文字來單獨執行（比如啟用碰撞、重載粗糙度等），具有更高的可控性；最後，修復骨骼網格體和資料夾中網格體一直被忽略的bug

#### 24w45a
- 新增`MC攝影機`，在細節面板可以設定視野、光圈、聚焦距離等參數，之後會以此為模板更新其他的攝影機。進階設定裡還可更改透視模式為正交，啟用移軸模糊（正在開發中）
- 我們正在給自訂變數新增工具提示，將滑鼠放在變數名上即可顯示詳細資訊；同時添加了英語版本作為語言本地化更新的一部分
- 新增一個適用於光線追蹤半透明的水材質
- UE5.5就要釋出了，Mineprep 0.4將是最後一個支援5.4的版本！在此之前，我們將繼續推進底層重構，首先是透過軟引用最佳化外掛的啟動速度
> 外掛面板當前的所有依賴性都是硬引用，會在啟動時全部載入到記憶體中。如果使用軟引用，就只會在呼叫時載入了！

#### 24w44a
- 修復了一些攝影機預設以非16:9解析度渲染時產生黑框的問題。在編輯器中，它們開啟了“約束寬高比”，便於預覽可視區域。此次更新後會在渲染時自動解除。
- 為基礎人模新增根骨骼碰撞箱，修復了移動“拖拽布偶史蒂夫”時產生大量警告的問題
- 修復了“堆放方塊”丟失預設貼圖的問題
- 嘗試最佳化方塊雲、太陽和月亮的材質，用於光線追蹤半透明
- 初步製作了起身功能，在後續更新中，當生物癱瘓倒地後，它們能站起來恢復動畫
- 初步製作了名為`Mineprep`的uplugin外掛，上傳到`MC_Startup/Plugins`路徑中。把它放到專案檔根目錄/Plugins資料夾下，可以自動開啟前置外掛，簡化安裝流程

#### 24w43a
- 修復了“緩動導軌攝影機”無法在時間線上預覽緩動效果的bug
- 修復了“第三人稱運動匹配角色”（高階運動匹配NPC）對手持物品打關鍵影格無法更換模型的bug
> 是的，UE的變數不會自動與屬性關聯，這在很長一段時間裡只能靠強制重新整理構造函式來解決。但是，我剛剛得知，建立一個名為 *Set變數名* 的函式，就能被時間線自動呼叫了！更多相關bug即將被修復
- 修復了“MC導播臺”在同時發出多個命令（按tag搜尋actor時），延遲並非最短時間的bug
- 修復了重啟虛幻引擎，“MC導播臺”沒有應用預覽畫質和影格數上限的bug
- “MC天空”新增“散射分佈（各向異性）”屬性，數值越大，光源附近的霧越濃，需要開啟體積霧才能生效
- 重新製作了`同步玩家攝影機`，可以修改緩動程度，並為之後動態切換角色做好準備
- 初步製作了蜘蛛群粒子模板

</details>

### 0.4-pre2
![image](https://raw.githubusercontent.com/wiki/piggestpig/Unreal-Mineprep/image/0.4-pre2%E5%B0%81%E9%9D%A2%E5%9B%BE.jpg)
- 新的里程碑！我們將這幾個月的成果投入實際生產，製作了動畫影片《史詩級動作最佳化2》，並帶來了許多細節最佳化和bug修復

<details>
<summary> 檢視細節 </summary>

- 新增`MC導播臺`，與Mineprep後期處理體積一起生成，作為場景的基礎模組
  - 在細節面板中，可以分別控制預覽畫質、預覽影格率上限和渲染畫質，最佳化效能或提升質量（所有渲染預設已不再使用過場動畫質量設定，轉而由MC導播臺控制）。預覽畫質預設為“3+ 極高”，渲染畫質預設為“4 影視級”。如果電腦效能較弱，建議把預覽畫質改為“2 高（快速lumen）”；如果想要減少渲染時的閃爍和殘影，進一步提高質量，可以把渲染畫質改為“4+ 影視級（增強lumen）”
  - MC導播臺可以在時間線上新增事件關鍵影格，向全場廣播命令，例如批次開關燈光、切換NPC動作、開始跑步跳躍等。它能重載訊號源位置（指定座標<指定actor<按tag搜尋actor）、調整訊號最大傳播距離（值為負數則從外向內收縮）、設定傳播速度來模擬延遲，還能修改不同命令的專有參數。啟用debug後會顯示最大傳播距離的球體形狀
  - 未來，還將新增切換玩家攝影機、動態修改後期處理效果等功能。
- “第三人稱運動匹配角色”和NPC生物添加了更多控制方式
  - 新增自訂鍵控動畫，取代了舊版切換表情的功能，並下放至所有NPC。在細節面板指定至多3段動作和3段表情，用鍵盤1-3切換動作，4-6切換表情。動作還能設定“混合時間”、“播放動作時停用移動輸入”和“NPC迴圈播放動作1”。如果要產生位移，請確保動作片段具有根運動；特別地，第三人稱運動匹配角色需要新增UE_或UEFN_字首，將動作用於重定向前的官方人模，否則將直接應用於MC人模（沒有位移）。
  - 現在能從時間線上呼叫跳躍、跑步、切換動畫、斷肢、癱瘓等事件了！（後者屬於“小鍵盤物理事件”，透過指定按鍵名來觸發，預設為0，即癱瘓）
- 生成器面板新增`堆放方塊`、`背景生物散佈器`，使用PCG外掛來程式化生成大量模型
  - 堆放方塊預設生成5x5x1的草方塊，可以設定懸空放置或自訂曲線區域。預設情況下，它將根據碰撞箱自動吸附到地面上。你可以修改方塊模型，例如在地上鋪滿頂層雪。還可以設定第二種方塊和兩者的比例，新增偏移或隨機旋轉。注意，堆放方塊沒有面剔除，它的效能不適合超大場景。
  - 背景生物散佈器將在自訂曲線區域內生成豬、牛、羊、馬NPC，可以修改種類、密度等參數。為提高效能，所有簡單動物NPC在預設情況下關閉了物理動畫互動。
- “附加元件”不再侷限於最後選中的actor，一部分功能會應用於所有符合條件的物件了！新增`燈光遙控`，一鍵新增遙控元件至所有選中的光源（不含日光和天空大氣），使其能夠被MC導播臺批次控制。
> 這個功能是為UE5.5而準備的，新的Megalights大幅提高了效能，能承載成百上千的燈光，宣傳片裡點亮整個場景的鏡頭看起來超帥 \~\\(≥▽≤)/\~
- “搖臂攝影機”也有緩動功能了
- 優化了生物模型尤其是手部的碰撞箱
- 新增`小爆炸晃動`、`大爆炸晃動`、`鏡頭緩慢晃動`
- 新增`流體化自碰撞粒子`
- 其他功能子面板的“輝光”板塊新增`卷積輝光`、`卷積散射`，效果更加柔和；“動態模糊”板塊新增`FPS`（此影格率越低，快門時間越長，模糊效果越大）；“光程”板塊新增`光線追蹤半透明（未最佳化）`，此功能可以改善水和雲的光影效果，但有時會帶來噪點和bug，之後慢慢最佳化
- 修復了馬的皮膚UV對映問題
- 在“Blender擴充套件資源”資料夾中上傳了新增生物的FBX模型
- 0.4-pre2沒有內容範例，預計在寒假更新0.4正式版
- *小故事：這個版本的主題叫“足跡與故事”，按照最初的計劃有兩次大更新 —— “足跡”指運動匹配，“故事”指鏡頭語言，分別對應0.4-pre1和0.4正式版。至於0.4-pre2，是趁著暑假給外掛來了個底層重構，現在看看，新東西倒也不少。接下來一段時間，會重點更新攝影機和運鏡方面的內容啦~*

</details>

<details>
<summary> 📜展開快照 </summary>
  
#### 24w39a
- “第三人稱運動匹配角色”和NPC生物現已支援切換重力方向，可以飛簷走壁，在牆和天花板上移動了！
  - 細節面板的進階設定中有初始重力方向，預設為(0,0,-1)
  - 使用鍵鼠操控角色時，可以按小鍵盤的“+”改變重力，新方向垂直於面前的平面向內
  - 新功能產生了許多~~bug~~特性，先不列出來了，等下慢慢修......倒掛在天花板上還好一點，牆上的問題比較多，目前嘗試鎖定頭部旋轉並關閉生物之間的RVO避障
- 新增官方宣傳片風格的走路和跑步動畫
- 豬、牛、羊預設關閉物理互動，因為跑步時碰撞箱有點問題
- “第三人稱運動匹配角色”新增頭髮選項，有身前和身後兩種樣式，支援自訂皮膚（需要內層皮膚有頭髮紋理）。同時，派生出“第三人稱運動匹配玩家”和“Alex長髮大眼睛高階NPC”兩個子類，前者用於遊戲模式，不在父類調整參數了；後者用於生成器，使用MC_Head_Eyes及其眨眼表情動畫
- 新增`動態體積霧`，可調整濃度、縮放、顏色、運動速度和方向。現在，放置“MC天空”和體積霧/體積光時會檢測對方是否存在，自動開啟體積設定並將霧濃度保持在0.015以上。
- 新增`緩動導軌攝影機`，預先將攝影機綁定到導軌上，透過拉曲線編輯移動路徑。運動時還會有緩動跟隨效果，使鏡頭平滑、穩定。這個和搖臂攝影機不一樣，只有在遊戲/渲染中才能使攝影機追蹤目標，在時間線上重新整理構造函式會丟失緩動效果。***0.4正式版（24w43a）已修復此問題！***
- 開放了“HDR靜影格_2K_avif”的部分參數，在UE渲染面板的右下角可以看到它們，重載解析度、暖場影格和渲染的影格數。

#### 24w38a
- 本週帶來了HDR渲染、語言本地化以及多個方面的重大更新
- 新增`牛`、`羊`兩種生物
- 物理互動動畫使用Physical Animation元件重做，現在“物理互動時鎖定雙腳”選項已更新為`區域性停用物理模擬`,可以自己新增所需骨骼；人形生物預設鎖定兩腳，豬羊牛馬鎖定四腳。
- 其他功能子面板的“色彩管理”選項下新增`EV100`，可設定自動曝光的上下限，對手動曝光沒有影響
  - 這個好像是攝影那邊的術語，操作邏輯有點怪，在暗處減小最小值可以提高亮度，在亮處減小最大值也是提高亮度。
  - 範例1：在夜晚增大最小值，可降低環境亮度，防止自動曝光變得像白天一樣亮
  - 範例2：在洞穴和峽谷中，可減小最小值，提高亮度，光影質感會很不錯，先是山有小口，彷彿若有光...復行數十步，豁然開朗
- “MC天空”有了白天、清晨、夜晚、濃霧四個預設，可以多次點選“生成MC天空”按鈕來切換，優化了日夜交替時的天空顏色
  - 前二者EV100 Min=-3，後二者EV100 Min=0，清晨和濃霧預設啟用了`體積霧（丁達爾光）`選項，對效能消耗比較大
- 新增`丁達爾體積光`預設，可透過生成器放置到場景中，有聚光燈/面光/點光三個選項，可設定亮度、顏色、光束變化速度等參數。需要環境中有體積霧
> 在詳細閱讀了虛幻引擎官方文件後，我發現HDR渲染（啟用OCIO後）會自動停用色調曲線，結果相當於相機拍攝的RAW素材...難怪色彩比檢視中差了很多！終於，在歷經了半年的探索後，新一代HDR渲染方案來了
- 透過一級調色還原lut極大改進了HDR渲染的色彩；渲染輸出模組新增AV1影片編碼、線性顏色選項和`HDR靜影格_2K_avif`影片圖渲染預設。
  - AV1需要很新的顯示卡（比如40系）才支援硬體加速，一般用H265就行，我看ffmpeg支援AV1就順便把它加進來了(ノ´・ω・`)ノ
  - 在影片編碼階段，會透過`UE5_HDR.cube`檔案對HDR畫面進行調色。這是一個3D lut，用達芬奇製作，旨在還原色彩，參數也比較簡單：第一個節點對比度1.25 軸心0.05；第二個節點對比度1.05 HDR色輪highlight 0.05
- `HDR靜影格_2K_avif`採用了UE5.4新的影片圖渲染功能，需要在渲染佇列點選“替換為圖（實驗性）”找到它。
  - 只渲染時間線最開始的1影格（之前會有30影格暖場），使用2560*1440解析度，輸出avif圖片，採用Rec2100 PQ色彩變換和還原lut
  - 出於技術原因，目前不能從Mineprep外掛面板修改其中的參數，必須寫死檔案路徑和檔案名。因此在初始化影片渲染時會把“UE5_HDR.cube”複製到D盤根目錄。
  - avif可以看作單影格av1，這裡使用通用的cpu編碼，不過貌似會把輸出日誌當報錯資訊彈出...總之在資料夾裡能看到成功渲染的圖片
> Windows建議使用chrome瀏覽器檢視avif，記得要開啟HDR顯示；蘋果原生支援avif（但是不支援av1影片），亮度會隨螢幕亮度而明顯變化
- HDR_2K_exr渲染預設更改為`【線性】2K_exr`，雙目立體全景渲染從exr更改為`【實驗性】VR_3D-FTB_8K_jpg`
  - 帶著Rec2100 PQ的“Raw” exr太少見了，通常用的是線性和ACES；另外單獨渲染序列影格是沒有調色的，所以雙目立體全景渲染退回jpg了（雙擊點進去也能改回exr輸出）。
- 新增`HDRI全景貼圖_8K_exr`渲染預設，使用8640*4320解析度，輸出單影格全景圖（沒有暖場），採用線性色彩變換和DWAA壓縮的exr編碼。
- 完善了語言本地化系統，新增對繁體中文的支援，為更多語言預留了擴充套件空間，詳見Readme的“語言本地化”板塊（正在編寫中）

#### 24w37a
- `骷髏`，`凋零骷髏`，`流髑`，`沼骸`，`豬`，`馬`，`鐵魔像`現已加入Mineprep！
  - 這些生物有專用皮膚，與普通玩家皮膚不相容。它們依然使用的是同一套骨骼，但是身體尺寸不一樣，因此有單獨的動畫庫。如果要在不同生物之間遷移動畫，建議使用自動重定向。
  - 從“簡單運動匹配NPC”派生出`簡單動物NPC`作為四腳生物的父類
  - 骷髏、流髑和沼骸的NPC手持弓，凋零骷髏手持石劍
  - 馬包括多種顏色和`驢`、`騾`、`殭屍馬`、`骷髏馬`的皮膚。
- 新增`MC_Head_Eyes`頭部模型，有著兩格大眼睛，可以新增表情動畫
- 第三人稱運動匹配角色（高階運動匹配NPC）添加了`披風貼圖`和`披风/鞘翅`選項，0表示停用，1是MC原版披風，2是布料模擬披風，3是鞘翅（暫未實裝）。預設的貼圖是MC15週年苦力怕披風，其中包含了鞘翅的紋理，更換時應該使用同樣規格的貼圖。
> 由於虛幻引擎的特性，布料模擬只能與具有簡單碰撞的Worldstatic物體進行互動
- 所有NPC都能設定潛行/走路/跑步速度了，並添加了`面向玩家/目标`選項，可以自動轉頭面向附近的角色
- 優化了“MC天空”的效能和方塊雲夜晚閃爍問題，現在可以在時間線上製作關鍵影格動畫，新增光照強度、柔和陰影、體積光、霧氣等控制參數
- 初步製作了自訂眼睛材質和邊緣高光材質

#### 24w36a
- 本週對生物和NPC系統進行了大翻新，使用繼承父類的方法整合了許多資源，引入物理互動動畫。
- 在頭身分離綁定的基礎上，重做了第三人稱運動匹配角色，派生出`高階運動匹配NPC`；重做了簡單運動匹配NPC，派生出各種生物子類。
- 所有生物在細節面板可開啟`物理互動（糾正穿模）`和`物理互動時鎖定雙腳`選項，運動時身體能與環境和其他生物碰撞互動。
  - 只有在遊戲/渲染時能進行物理互動，編輯器檢視不可見
  - 目前有一個~~bug~~特性，區域性斷肢會導致上半身全部萎掉 (ﾟД ﾟ;) 因此玩家控制的第三人稱運動匹配角色預設關閉物理互動，NPC預設開啟。
- 新增`豬布林`，`豬布林蠻兵`，`衛道士`，`掠奪者`及相關動作庫。
  - 在放置NPC時，豬布林預設手持金劍，豬布林蠻兵手持金斧，衛道士手持鐵斧，掠奪者手持弩。
  - 豬布林的耳朵會自動擺動，災厄村民多了一個控制鼻子的骨骼，但各種生物的表情動畫有待更新
- 新增路標引導NPC功能：在細節面板新增場景中的物體作為路標，NPC會依次前往這些路標；勾選“迴圈”後，會從最後一個路標返回第一個路標，重新開始
- 又修復了模組化綁定的腿部朝向bug...平時我沒動它來著，好像是UE版本更新出的問題
- 徹底修復了“搖臂攝影機”和“3D攝影機組”無法在編輯器視口更新關鍵影格動畫的bug。外掛面板的“強制重新整理構造函式”按鈕現已棄用。

#### 24w35a
- 0.4-pre2將對外掛進行大翻新，本週已經開始底層重構了！注意新版本與舊版本不相容，而且無法透過替換單個檔案的方式來更新特定資產
- 外掛根目錄資料夾由MCprep改名為Mineprep（已經修了很多損壞的依賴項了，希望不要出bug qwq）
- 外掛面板的按鈕增加了撤銷功能，可以按Ctrl+Z撤銷，Ctrl+Y恢復。準備場景、更換材質等部分按鈕暫時還無法撤銷
- 外掛子面板被拆分為單獨的控制元件，再整合到Mineprep面板中（主要是提升開發時的流暢度，對使用者沒有影響......希望不要出bug qwq）
- 整個生物模型和角色系統將大改。目前添加了`頭身分離綁定基礎生物模型`，可以自由搭配身體和頭顱，例如MC_Body+MC_Head就相當於MocapCarrier。在時間線上製作動畫時，能夠分離控制動作和表情，不需要把表情的插槽名稱改為“f”了。
- 新的模型修復了權重繪製的bug，斷頭之後繼續向前跑，身體不會被拉伸

</details>

### 0.4-pre1
![image](https://raw.githubusercontent.com/wiki/piggestpig/Unreal-Mineprep/image/0.4-pre1%E5%B0%81%E9%9D%A2%E5%9B%BE.jpg)
- 新的里程碑(*・ω・)ﾉ 我們在這一週修復了大量bug並帶來幾個新功能，稍後將上傳打包的exe範例檔案，包含0.3和0.4-pre1的所有內容，作為正式的Release釋出

<details>
<summary> 檢視細節 </summary>

- mcprep_data.json已更新至1.21版本，與剛剛釋出的MCprep 3.6同步。預設資源包尚未更新
- 外掛面板的“啟用碰撞”選項旁邊添加了`複雜碰撞`選項，預設開啟，之前的準備場景也都在用複雜碰撞；如果要進行物理模擬，請關閉此選項，再對選中物品使用準備場景。此外還增加了三個新功能：
- **重載材質**  
  `物件`：視口選中項  
  `效果`：搜尋單個靜態網格體或包含骨骼網格體元件的藍圖，把所有材質替換為你指定的材質。若沒有指定材質，則不會替換。  
  `可選項`：材質、覆層材質、物理材質
- **處理錄製的動畫**  
  `物件`：開啟的關卡序列  
  `效果`：搜尋時間線上的“第三人稱運動匹配角色”，尋找錄製的動畫，嘗試修復旋轉問題。（這個bug終於被我找到了，由於MC人模是在執行時重定向到官方運動匹配角色，所以會記錄兩次關鍵影格動畫，把MC人模的旋轉清零能在一定程度上解決空轉鏡頭的問題）。
> 以下是第一個實驗性功能，也是第一個包含C++程式碼的內容。  
> 上週剛發現官方隱藏的VR+3D渲染功能，這周就迫不及待地想要端上來力 -- 請謹慎使用實驗性功能，按下按鈕後會先彈出一個詳細的介紹與警告，需要確認才能執行
- **實驗性功能**  
  `前提`：UE版本5.4，作業系統Windows（否則需要在開啟專案檔時從原始碼編譯外掛，尚不清楚是否需要Visual Studio）  
  `物件`：Movie Render Queue Additional Render Passes外掛  
  `效果`：將改寫後的新外掛解壓並移動至專案檔根目錄的Plugins資料夾下，重新啟動時會優先從這裡載入外掛。全景渲染中的Stereo、Eye Separation和Eye Convergence Distance選項已經解鎖，可以輸出雙目立體全景渲染，其他渲染預設不受影響。暫未將其加入外掛面板的自訂渲染配置。  
  `可選項`：是/否
- 新的渲染預設`【實驗性】VR_3D-FTB_8K_HDR_exr`，需要開啟實驗性功能  
  - 使用8640*8640解析度，輸出上下並列的Full Top-Bottom全景序列影格，採用Rec2100 PQ色彩變換和DWAA壓縮的exr編碼。既然要做這麼高規格的渲染，那各項參數都拉滿吧
  - 一影格約35MB，需要約40G的顯示記憶體+共享記憶體......這真不是普通電腦能帶的動的qwq（exr已經比png小很多了）
- 繼續修復渲染預設和人物碰撞bug
- “光程”面板新增了`漫反射增強`滑條，可以增加間接光照明強度
- 現在可以場景中放置多個“軟體史蒂夫”了
- “FPV飛行模式”的反轉滑鼠Y軸快捷鍵改為Tab
- “第三人稱運動匹配角色” 添加了自動爬牆的選項（即兩格高方塊），預設開啟；可以在執行時按Tab關閉
- “第三人稱運動匹配角色”和“簡單運動匹配NPC”都有了手持物品槽，還可以透過小鍵盤按鍵開啟物理模擬。  
  “0”-全身癱瘓  “.”-開/關重力  “2”-物品脫手   
  “4”-斷左臂  “1”-斷左腿  
  “6”-斷右臂  “3”-斷右腿  
  “8”-斷頭  “5”-全身斷開  
  - 使用鏡頭試拍錄製器記錄動畫時，如果要扔出手持物品，請新增“Nearby Spawned Actors”，之後需要在時間線中手動指定扔出物品的模型。這是目前最好的辦法，因為直接讓原物品脫手會發生抖動，生成新物品反而比較穩定。***【自0.5-pre1（25w16a）起，不需要手動指定模型了，會自動記錄】***
> 以上快捷鍵可能需要開啟小鍵盤的Num Lock
- 生物的細節面板新增了“NPC跑步跟隨目標”選項和幾個原版跑步動畫。
- 新增“待機-跟隨AI控制器”
- 嘗試修復鏡頭試拍錄製器無法錄製角色攝影機旋轉的bug。
  - FPV飛行攝影機一直都能錄製旋轉
  - MC第一人稱攝影機現在能錄製除了鏡頭晃動以外的旋轉【0.4正式版已有錄製攝影機晃動的方法！】
  - 而第三人稱運動匹配角色比較麻煩，要用生成器放置一個`同步角色攝影機`，再新增到錄製面板裡，它會同步並記錄玩家攝影機的旋轉。如果錄製的動畫有幾影格卡頓，那麼就把這幾個關鍵影格刪掉，平滑過渡。渲染器記得切換時間線綁定的攝影機。【0.4正式版已修復此bug！】
- “MC天空”現在可以設定雲的移動方向和速度，同時增大了光照的級聯陰影距離，使過渡更平滑
- “準備場景”會根據方塊名稱來新增音效物理材質了。現在有grass，gravel(dirt)，sand，snow，stone，wood六類，沒有匹配成功都視作石頭。“第三人稱運動匹配角色”在上面行走時會播放對應的腳步聲音效。注意，整個音訊渲染模組還在早期開發階段，目前只能聽個響
- 新增`光滑物理材質`，`彈性物理材質`，和之前的“高摩擦力物理材質”一起影響開啟了模擬物理的物件。
- 取消了“可互動2D水面”的材質介面，因為水材質需要專門的模組才能繪製波浪，隨便換一個不管用。同時將它的碰撞物件從Actor改為元件，修復了碰撞失效的bug
- 修復“燈光排除”對內部元件無效的bug
- “LOD&Nanite”功能的“2x增強網格體距離場”和“啟用Nanite”選項在預設狀態下停用，這倆執行起來特別卡，感覺第一個關閉陰影更實用一些
- 外掛面板彈出框現已支援英語，Github Readme也翻譯了一部分英語 —— 是的，你點最頂上那個English按鈕不會跳到404頁面了，最古老的bug終於被修復了!

</details>

<details>
<summary> 📜展開快照 </summary>

#### 24w30a
- Mineprep 0.4-pre1就要釋出了，這是最後一次快照更新，加入新功能並修復bug~
- **強制重新整理構造函式**  
  `物件`：最後一個視口選中項  
  `效果`：每隔一段時間重新整理選中的物體，使其在編輯器中不斷更新狀態。如果影格數下降，可以勾選“中止”打斷程式執行。例如，之前搖臂攝影機的關鍵影格動畫不能觸發追蹤模組，現在可以使用此功能強制重新整理了。  
  `可選項`：時長(s)，間隔(s)，中止(勾選框)
- 修改了所有骨骼的碰撞設定，修復穿模和麵部扭曲的bug
- 新增`軟體史蒂夫`，使用骨骼模擬物理+Niagara變形製作而成，目前只能在場景中放置一個實例，之後會繼續更新。
> 我們還嘗試用Chaos Flesh做軟體模擬，但是bug更多了，暫時不會加入外掛面板
- 新增`下雪粒子`
- 新增`MC文字`，需要開啟Text 3D外掛，放置到場景中可以修改文字、顏色等屬性。
- 在影片渲染模組中添加了“-tag:v hvc1”。H.265分為hev1和hvc1兩種模式，蘋果不支援之前預設的hev1，現在指定為hvc1。
- 全景渲染預設的DLSS Quality已更改為DLAA，能顯著提升質量，同時將橫向取樣數改為4、橫向視野設定為120°，渲染前採用10影格顯式暖場影格，以節約顯示記憶體並加快速度。
> 好消息：官方為全景渲染外掛做了3D輸出功能；壞消息：不知為何它被隱藏起來了，需要修改外掛原始碼才能啟用。目前Mineprep不包含C++模組，我們考慮在0.4pre-1之後加入新功能，也許就能輸出VR+3D+HDR的超高規格影片了！
- “MCprep自訂渲染配置”改名為“Mineprep自訂渲染配置”，同時修改預設解析度，“VR全景_4K”改為4320x2160（因為4K又叫2160p，通常以短邊為基準），“VR全景_8K”改為8640x4320
- 修復了暖場影格、HDR影片編碼等bug

#### 24w29a
- 本週更新了放置生物功能和NPC運動系統，舊版運動匹配角色也重生啦。在背景中放幾個生物，無需編輯動畫，它們就能動起來，給場景增添幾分生機 ╰ \*°▽°\* ╯
- “放置生物”現已實裝，具體參見24w28a介紹。目前支援的生物包括之前的所有人模 + 殭屍、屍殼、沉屍
- 修復了“MC_UE模組化綁定”的左臂凸起和腿部旋轉問題
- 新增了AI控制器和相關的黑板、任務模組，可以讓NPC生物自行遊蕩或跟隨目標。若在場景中放置了導航網格體，它們會跟著導航走。
- 舊版運動匹配角色重新啟用，更名為`簡單運動匹配NPC`。它具有AI控制器，運行遊戲或渲染時會自己走動。新增了MC原版玩家和殭屍的動作庫
- 新增`下雨粒子`，執行在GPU上，可以即時生成大範圍降雨，模擬MC原版風格的雨滴和水花。
- “附加元件”新增新增標籤功能。`“collider” tag`會對物體及其所有元件新增碰撞標籤，可以與水互動。`“通用跟蹤目標” tag`會新增標籤與AI感知刺激源元件，使該物體成為NPC跟隨的目標

#### 24w28a
- 本週更新了“生成MC天空”，“放置生物”，“預設素材”和多個新功能！可以在生成器面板放置生物（暫未實裝）、粒子、攝影機、傳送門等各種素材了
- **生成MC天空**  
  `物件`：MC天空  
  `效果`：清除場景中的預設光照和大氣，新增“MC天空”藍圖。它具有方塊形狀的雲、太陽和月亮，可以更改時間、角度等設定。之後會繼續更新  
- **放置生物**  
  `物件`：選定的生物  
  `效果`：嘗試在螢幕中心15m內檢測地面，如果檢測到了就把生物放到地面上，沒有就放在前方的空中。放置的生物是從基本骨骼或藍圖角色衍生而來，更換其皮膚、動畫庫、AI控制器等屬性。對於骨骼網格體，會把縮放設定為0.95並新增“collider” tag；對於NPC生物，會隨機設定旋轉。  
  `可選項`：生物名稱(支援多語言)，過濾名稱  
- **預設素材**  
  `物件`：選定的藍圖  
  `效果`：嘗試在螢幕中心15m內檢測地面，如果檢測到了就把預設素材放到地面上，沒有就放在前方的空中。  
  `可選項`：藍圖名稱(支援多語言)，過濾名稱  
- 新增了`末影粒子`，`爆炸粒子`。末影粒子必須要透過“附加元件”綁定到生物或模型上，向外持續散發紫色粒子。爆炸粒子則是在一瞬間產生TNT爆炸效果，可以單獨放置或綁定
- 點選語言選項前面的圖示，可以直接開啟“語言本地化_language_localization.csv”檔案
- 渲染輸出名稱前面有了重置按鈕。點一下會自動更新為“{時間線名稱}\_{解析度}\_{影格率}\_[是否HDR]\_[是否VR]\_[3D({瞳距}mm,{視場}°,[是否FSBS])]”。若未開啟時間線則不會更新
- 綁定3D攝影機組會自動新增到時間線

#### 24w27a
- 本週對外掛的多個方面進行了更新，包括人物模型、3D渲染、生成器、語言本地化等內容
- 修復了所有人物模型（除模組化綁定外）左臂彎曲會略微凸起的問題
- 最近發現Blender的形態鍵可以匯出到虛幻引擎！由此可以製作直角彎曲的四肢以及表情變形動畫。除模組化綁定外，所有人模都已經添加了變形目標(即形態鍵)，稍後會製作動畫藍圖。
- 新人模 `MC_Bent`  
  - 骨架與MocapCarrier相同，四肢具有形態鍵，透過動畫藍圖的驅動器即時變形，實現直角彎曲。
  - 小臂和小腿鎖定了Y軸和Z軸的旋轉，小腿X軸旋轉限制在75°以內
  - *形態鍵可能導致材質法向出現問題，目前沒有完美的修復方法，有時會出現異常的光滑/陰影。更換材質時建議新增微弱的自發光
- 以上模型的FBX檔案已更新到“Blender擴充套件資源”資料夾中
- 語言本地化更新：藉助python指令碼，現在能從csv檔案中即時讀取文字，不需要匯入為表格了
- 生成器面板新增 `附加元件` 按鈕，之後還會製作 `放置生物` 和 `預設素材`。它們的選項框具有多語言支援，放置的東西也會重新命名
- **附加元件**  
  `物件`：最後一個視口選中項  
  `效果`：把選定的物品綁定到物件上。可能是直接新增為元件，也可能是在場景中生成新物品，比如最新的“3D攝影機組”  
  `可選項`：物品名(支援多語言)，過濾名稱
- 修復了渲染輸出面板和渲染預設的一些bug。現在渲染前會有30影格暖場影格，中途取消不會跳過影片編碼了
- 新增 `3D（FSBS）自訂渲染配置` ，`3D攝影機組` 藍圖，外掛面板的 `紅藍3D疊加輸出` 選項
  - 當你按照普通的流程製作了一個鏡頭後，可以快速輸出3D影片：首先選中當前攝影機，然後在生成器面板使用“附加元件”綁定3D攝影機組，接著在渲染輸出面板設定參數，最後使用“3D（FSBS）自訂渲染配置”匯出影片，這樣就搞定了
  - 預設輸出是左右眼畫面並排的Full Side By Side格式，橫向解析度變為2倍，適合後期調色、合成蘋果的空間影片。勾選“紅藍3D疊加輸出”後，會生成目標解析度的濾色影片，適合帶上3D眼睛觀看。
  - 支援HDR，不支援全景渲染和Alpha通道，取樣數恆為1，渲染壓力為普通影片的2~3倍。**始終建議在外掛面板修改渲染參數，最終畫面的色彩可能會有些許不同**
  - 3D攝影機組可以設定“目標攝影機”，“用tag獲取攝影機”，“瞳距（mm）”，“預覽時捕獲每影格”，“預覽解析度（預設540p）”。放置到場景中後，會展示左右眼分別看到的畫面和紅藍3D疊加畫面。它會自動綁定到選中的攝影機，修改焦距、後期處理配置等參數。綁定函式首先在場景中搜索具有tag的物品（預設tag為“3D”），把它設定為目標攝影機。如果沒有，讀取你選定的目標攝影機（值為空則在場景中尋找攝影機）。目標攝影機如果是普通攝影機/電影攝影機/包含攝影機的藍圖，就會與之同步；如果目標攝影機是個模型，就只會綁定旋轉和位移。
> 時間軸攝影機和鏡頭試拍錄製器記錄的動畫會在關卡開始時重新整理，因此只綁定目標攝影機會丟失物件。建議新增tag“3D”，或者使用“附加元件”功能，一鍵配置目標攝影機和tag

> 3D渲染需要記錄左右眼畫面，效能消耗大。檢視卡頓的話可以關閉“預覽時捕獲每影格”

#### 24w26a
- 我們重新設計了外掛面板並添加了許多新功能
  - 外掛面板從MCprep改名為Mineprep，包含`進階設定`，`渲染輸出`，`生成器`，`其他功能`四個子版塊
  - “進階設定”裡會顯示`材質包路徑`，預設為MC原版材質，已經包含在“外掛貼圖”資料夾中。當點選“更換材質”功能時，會寫入你所選擇的材質包資料夾；如果中途取消，會終止程式並回到預設材質。你也可以手動輸入材質包路徑。
  - 當你配置了Blender路徑並安裝MCprep外掛後，可以使用“生成器”的`放置方塊`、`放置物品`功能，遠端呼叫Blender獲取模型然後擺放到場景中。名稱從材質包中載入，所以會顯示英文名。
  - “其他功能”包含原來的燈光排除、LOD&Nanite功能；新增了`輝光`、`動態模糊`、`光程`、`色彩管理`選項，能夠像Blender一樣快速調整畫面效果。它會首先在場景中生成一個“Mineprep後期處理體積”（如果已經有了，就讀取其中的值），範圍是無限，優先順序是9（高於普通的後期處理體積），然後設定裡面的參數。
- **放置方塊**  
  `前提`：安裝Blender和其中的MCprep外掛，配置Blender與材質包路徑  
  `物件`：選定的方塊（來自材質包）  
  `效果`：匯入並放置選定的方塊。首先會在專案檔根目錄建立一個空的cache資料夾，然後在後臺啟動Blender，傳送一串命令，遠端呼叫MCprep生成方塊，匯出FBX模型到cache資料夾中，最後匯入虛幻引擎。若4秒內沒有檢測到模型，程式會終止。匯入後先嚐試在螢幕中心15m內檢測地面，如果檢測到了就把方塊放到地面上，沒有就放在前方的空中。  
  `可選項`：方塊名，材質包路徑，過濾名稱  

- **放置物品**  
  `前提`：安裝Blender和其中的MCprep外掛，配置Blender與材質包路徑  
  `物件`：選定的物品（來自材質包）  
  `效果`：匯入並放置選定的物品。大致流程同上，在Blender中生成模型時會把厚度設定為0.075然後應用實體化修改器  
  `可選項`：物品名，材質包路徑，過濾名稱

- **過濾名稱**  
  `前提`：材質包路徑有效  
  `物件`：生成器的所有選項框  
  `效果`：根據你輸入的名稱，篩選出包含這些字元的選項。儘管“放置方塊”的單詞之間有下劃線，過濾名稱時請使用空格隔開

- **輝光**  
  `物件`：Mineprep後期處理體積  
  `效果`：即時更新輝光強度和閾值。當取消勾選時退回到UE5預設輝光設定，同時也會保留修改後的值  
  `可選項`：強度、閾值

- **動態模糊**  
  `物件`：Mineprep後期處理體積  
  `效果`：即時更新動態模糊強度和最大值。當取消勾選時退回到UE5預設設定，同時也會保留修改後的值  
  `可選項`：強度、最大值
> 注意，動態模糊僅在遊戲和渲染模式下可見，檢視編輯器好像沒效果

- **光程**  
  `前提`：在專案設定裡開啟lumen硬體光線追蹤  
  `物件`：Mineprep後期處理體積  
  `效果`：把光線光照模式改為“反射的命中光照”，即時更新反射次數和折射次數。這可以用於鏡子的多重反射。當取消勾選時退回到UE5預設設定，同時也會保留修改後的值  
  `可選項`：反射次數、折射次數

- **色彩管理**  
  `物件`：Mineprep後期處理體積  
  `效果`：啟用自動曝光時把曝光補償設定為1，關閉自動曝光時把曝光補償設定為11；即時更新曝光補償、陰影對比度、高光對比度。當取消勾選時退回到UE5預設設定，同時也會保留修改後的值  
  `可選項`：自動曝光（勾選框）、曝光補償、陰影對比度、高光對比度

#### 24w25a
- 0.4版本的第一個快照！虛幻引擎官方釋出了運動匹配範例場景，我們很快移植到了MC角色上
- 舊版運動匹配藍圖已棄用，暫時保留在依賴資料夾裡。取而代之的是新版`第三人稱運動匹配角色`。
  - 可以像MC一樣用WASD移動角色、shift潛行、ctrl加速、空格跳躍等等。
  - 角色具有運動匹配功能，會自動從動畫庫中挑選合適的動畫播放，透過執行時重定向把動畫應用於MC人模。
  - 預設皮膚是官方宣傳片材質的史蒂夫
  - 新增：正面自動跨上1格高方塊，側面自動跳上1格高方塊，自動翻越1格高柵欄，按空格還可攀爬1.5~2.5格高方塊
  - 新增：用鍵盤“1”，“2”，“3”切換表情，預設播放眨眼動畫。這些動畫片段可以在類預設值裡更改。
  - 新增：滑鼠右鍵聚焦，中鍵居中人物。這是官方運動匹配附帶的功能，以後可能會更改。
> 注意，鏡頭試拍錄製器似乎無法單獨錄製鏡頭旋轉。不建議在人物靜止時旋轉視角。
- 根據MCprep官方的建議，外掛名稱由Unreal MCprep更改為Unreal Mineprep，以避免混淆。Github主頁很好改名，但是動外掛資料夾會出一堆bug，之後再試試qwq

</details>

### 0.3 : 多彩世界
![image](https://raw.githubusercontent.com/wiki/piggestpig/Unreal-Mineprep/image/0.3%E5%B0%81%E9%9D%A2%E5%9B%BE.jpg)

- 0.3正式版現已釋出！本次更新的主題為“多彩世界”，和0.2版本相比，加入了大量新功能與資源素材，我們用其製作了動畫短片《史蒂夫之夢》。來看一看最後更新的內容吧：

<details>
<summary> 檢視細節 </summary>

- **最佳化安裝流程，減少對其他外掛的依賴**。之前的版本必須藉助TApython才能執行，否則整個藍圖都會報錯。現在只有“植物搖擺”功能依賴TApython，而且它不影響其他功能。具體來說，我們用python自帶的filedialog替代了“更換材質”的選擇資料夾彈窗，用UE自帶的“顯示消息對話”節點替代了右下角提示彈窗。
- **修復大量bug，提高穩定性**。 “準備場景”在搜尋材質中的紋理貼圖時，會判斷物件是否為空來避免閃退，最多向前查詢三層。“更換材質”會先刪除原來的材質節點（刪的更乾淨了），再連線新材質。動畫紋理能對粗糙度和法線貼圖進行處理了。
- “準備場景”新增`漸變動畫紋理`選項，可以使動畫材質平滑過渡。
- “LOD & Nanite”新增`投射陰影`選項，可以批次關閉選中項的陰影。在匯入超過1000萬面的特大場景後，陰影渲染會使影格數明顯下降。不妨在編輯場景時關閉一部分模型的陰影，渲染前再開啟。
- 新增`滾動方塊`，把它拖放到場景中，設定方向、重力、速度，可以在執行時滾起來
- 整理了外掛結構，現在有一個“材質”資料夾。更新了Github頁面對外掛的介紹。
- 我們計劃跳過0.3 Demo內容範例，等下次0.4-pre1一起釋出。下個版本的主題暫定為“足跡與故事”，將會製作生物、動畫這方面的內容。

</details>

<details>
<summary> 📜展開快照 </summary>

#### 24w22a
- 本週沒有更新，因為我們正在全力製作新的動畫影片《史蒂夫之夢》！過幾天就能釋出啦，祝MC15週年生日快樂（託更了好久hh）

#### 24w21a
- 新增`搖臂攝影機`，預先把電影攝影機綁定到搖臂上，拖入場景即可使用。開啟“希區柯克變焦”功能後，攝影機將自動追蹤搖臂底座，根據搖臂長度縮放焦距。
> 和單獨的攝影機相比，電影攝影機元件缺少追蹤模組，因此用藍圖實現了類似功能。遺憾的是和追蹤相關的關鍵影格動畫不會在檢視中更新，需要進入遊戲模式或者渲染才能看到。***0.4版本（24w36a）已徹底解決此問題！***
- 優化了傳送門材質，可以調整紋理和色相，增加了傳送門的整體縮放變數

#### 24w20a
- 新增`曲線引導粒子`，由樣條線和粒子系統組成，粒子會沿著曲線運動。拖放到場景中之後，選中一個控制點並按住Alt移動，即可擠出新的控制點。
- 修改了所有粒子系統，開放材質或網格體介面，現在可以在細節面板裡編輯這些參數了。
- 新增表情動畫藍圖，目前處於測試階段，附帶了兩個表情。直接把動畫藍圖拖放到場景中，在兩個軌道中新增身體和表情的動畫，然後右鍵把表情的插槽名稱改為“f”，即可分離控制。
- Nvidia宣佈將在一個月內更新DLSS外掛！這意味這我們可以遷移到UE5.4了，Unreal MCprep 0.3正式版即將推出~

#### 24w19a
- 新增`Demo`分支，存放打包的exe檔案，並發布到release裡。Git LFS傳大檔案有好多坑啊啊啊，我最後選擇了分卷壓縮(doge
- 優化了飛行模式的手感，現在轉向回正後不會漂移，按"\\"可以反轉滑鼠Y軸
- 調整了所有遊戲模式的攝影機光圈，可以在更大範圍內設定景深了
- 優化了可互動3D水面的渲染，減少顆粒感
- 修改了MC_FaceX和MC_Slim_FaceX的臉部骨骼，為接下來的高階表情控制功能做準備

</details>

### 0.3-pre1
- 第一個預覽版本，進行了大量最佳化並修復了不少bug！稍後將上傳打包的exe檔案，供沒有虛幻引擎的使用者體驗外掛。以下是新功能

<details>
<summary> 檢視細節 </summary>

- **自發光**  
  `物件`：視口選中項/資產資料夾  
  `效果`：使選中的材質發光，可以分別控制照亮場景的強度和自身亮度  
  `可選項`：照明強度，自身亮度
- **燈光排除**  
  `物件`：視口選中項  
  `效果`：批次分配選中物件的燈光組。只有同一組的燈光才能照亮同一組的物體。預設燈光組是1  
  `可選項`：燈光組 [1，2，3]
- **LOD&Nanite**  
  `物件`：視口選中項/資產資料夾  
  `效果`：開啟對應選項後，可提高網格體距離場解析度至2倍（有利於GPU碰撞檢測），開啟Nanite並將回退目標的三角形百分比設定為100%（保持原先碰撞箱）  
  `可選項`：2x增強網格體距離場，啟用Nanite
> 不清楚這是什麼功能？那就最好不要動它哦。MC的Distant Horizon模組特別棒，我也試了試UE5的Nanite最佳化 —— 雖然影格率顯著提升，但方塊變成多邊形了，一言難盡。2x增強網格體距離場會逐步加重負擔，導致影格率下降，建議不要給整個場景使用，應該搭建小的輔助碰撞模型。哦對了，這倆玩意兒載入時間特別長，一不小心還會閃退TAT
- 改進了自訂附魔的實現方法，現在可以在物體面板看到附魔元件了
- 大改影片渲染模組：虛幻引擎預設的ffmpeg編碼模式是concat，會導致重複影格和卡頓，拖慢編碼速度。現在採用預設的input，極大加快N卡處理png序列影格的速度，影片也變流暢了！
  - 兩個mp4渲染配置檔案的預設硬體選項從Intel GPU改為Nvidia GPU
  - 外掛面板增加了影格率和影片名稱的選項
  - 新增以下兩個渲染預設，需要開啟UE自帶的*Apple Prores Media* 外掛，無需外掛的初始化功能。這個格式編解碼速度快，但windows自帶播放器是不認的，而且體積很大。
  - `Prores_2K_mov（UE內建外掛）`使用2560x1440解析度，直接輸出Prores422LT編碼的mov影片，無需渲染結束後的等待。
  - `Prores4444_2K_透明mov（內建外掛）`使用2560x1440解析度，直接輸出Prores4444編碼的mov影片，還能包含Alpha通道，生成透明免摳影片。    
- 更新了飛行模式，手感大大提升。現在按滑鼠左/右/中鍵都可以急剎，並且效果會疊加。按滑鼠側鍵可以加速俯仰。我們收集了許多內測建議，將陸陸續續改進。
- 準備場景增加了“啟用碰撞”選項
- 更換材質能自動處理動畫貼圖了
- 新增了UE“建築視覺化”範例裡的高質量水材質
- 優化了傳送門和落葉粒子。“VFX傳送門”可以使用立方體渲染目標的全景貼圖，保持高效能的同時帶來透視效果，目前還不能傳送。
- 新增`可互動2D水面`，`可互動3D水池`，`粒子自碰撞`，都是使用Niagara GPU的高效能粒子系統。
- 新增`場景初始化`藍圖，拖放到場景中設定畫質和最高影格率
- 正在製作一個範例檔案，展示Unreal MCprep的各種功能，打包後供沒有虛幻引擎的使用者體驗。

</details>

<details>
<summary> 📜展開快照 </summary>

#### 24w17b
- 新增了`第三人稱運動匹配模式`
  - 可以像MC一樣用WASD移動角色、shift潛行、ctrl加速、空格跳躍等等。
  - 角色具有運動匹配功能，會自動從動畫庫中挑選合適的動畫播放
  - 目前從Mixamo中下載了幾個動作，包含前後左右的行走和跑步，僅供測試使用。再過幾個月，UE5.4會發佈一個官方範例檔案，裡面包含上百個高質量動畫。我們已經做好了準備，到時候可以快速遷移到這個角色上——然後就能即時錄製動畫了！
> *此功能需要UE5.4的Motion trajectory外掛
- 新增了從UE5和Mixamo人模到MocapCarrier的重定向器。推薦用這個功能替代自動重定向，因為原來的運動速度不一樣，經過除錯之後將根骨骼的位移x1.5就好多了。
> 注意，Mixamo下載的動畫不帶根骨骼，啟用根運動會出錯。我透過[Mixamo Converter](https://terribilisstudio.fr/?section=MC)對其進行轉換，然後重定向。另外Mixamo Converter只認Mixamo網站的標準模型。
- 重新命名：`MC玩家攝影機 & MC玩家模式`已更名為`MC第一人稱攝影機 & MC第一人稱模式`，`飛行模式`已更名為`FPV飛行模式`
- 改進了飛行模式，現在按滑鼠左右鍵可以急剎，上升/下降的速度會隨飛行速度而變化。

#### 24w17a
- 一大批MC人模正在接近 —— 藉助動作捕捉和遊戲模式，減輕k影格的工作量，加快動畫製作流程！先來看看目前做好的通用模型吧
- 更新了外掛結構，*Blender_export.py* 和新的FBX人模放在*Blender擴充套件資源* 資料夾下。這些FBX模型具有廣泛的相容性，可以匯入Blender、UE、Mixamo（線上動作捕捉素材庫）、Cascadeur（AI輔助動畫軟體，可用於影片動捕）等各種軟體。MCprep的*生物模型rigs* 資料夾裡已經包含了匯入UE5.4並經過最佳化的模型。
- `MocapCarrier`（簡稱MC）
  - 最基礎的模型，自帶Steve的粗胳膊皮膚。
  - 下面的高階人模都設定了骨骼相容，可以直接使用MocapCarrier的動畫，無需重定向。如果要用其他動作捕捉軟體，推薦用它作為載體，這就是MocapCarrier名字的由來
- `MC_Slim`  
  - 骨架與MocapCarrier相同，自帶Alex的細胳膊皮膚。
- `MC_FaceX`  
  - 在MocapCarrier基礎上，添加了臉部骨骼，可單獨設定嘴巴、眉毛、左眼、右眼、眼白的材質。
  - 臉部不打算做動捕或者高階綁定了，稍後會製作動畫庫，準備一些常用素材；也可以自己k影格。
- `MC_Slim_FaceX`  
  - 在MC_Slim基礎上，添加了臉部骨骼，可單獨設定嘴巴、眉毛、左眼、右眼、眼白的材質。
- `MC_模組化綁定`  
  - 在MocapCarrier基礎上，調整了腿部骨骼軸向，配置了UE5.4的模組化綁定功能。
  - 把它拖放到場景中，你會直接進入動畫模式，能對各個關節進行k影格，腿部和身體有IK綁定。  
  > 不過...應該沒人會在虛幻引擎中手搓動畫吧（づ￣3￣）づ 以上人模主打一個動作捕捉工作流程，要k影格也可以去Blender或者Cascadeur，所以就只給MocapCarrier做了模組化綁定，其他的不搞了，展示一下新功能就行。模組化綁定的IK控制器需要很奇特的骨骼朝向，不然會變成小短腿，這個bug修了好久【0.4正式版起使用自制IK綁定，將會適配更多生物】

#### 24w16a
- 更新了兩個遊戲模式，現在可以像玩MC一樣用鍵盤移動/飛行啦。開啟UE5自帶的 *Take Recorder* 外掛後，還能透過 *鏡頭試拍錄製器* 記錄運動軌跡，即時運鏡。最簡單的使用方法是修改 *世界場景設定* 裡的 *遊戲模式重載* ，不需要拖放藍圖，直接運行遊戲就行。
- `MC第一人稱攝影機 & MC第一人稱模式`  
  - WASD移動，shift潛行，ctrl加速，空格跳躍
  - 包含自動跳躍、潛行防掉、視野縮放等特性
- `飛行攝影機（Do_a_barrel_roll）& 飛行模式`
  - MC有一個超棒的鞘翅模組叫Do a barrel roll，可以像FPV無人機一樣做空中機動，我參考他的按鍵設定製作了飛行模式（目前是初稿，以後可能有修改）
  - WS前進/後退，AD左右偏航，滑鼠左右移動橫滾，前後移動俯仰
  - 空格上升，shift下降，ctrl加速前進，z加速後退
- *小故事：我本來沒有做炸機的程式，但是撞上東西后自帶奇妙效果，還特別好玩 (ﾉ･ω･)ﾉ 應該是彈簧臂元件的特性*

#### 24w15b
- 添加了落葉粒子（niagara）和傳送門（立方體渲染目標）的基礎模板
- 整理了外掛結構，可以拖放到場景中的素材都儲存在`MC藍圖資源`資料夾下

#### 24w15a
- 更新了一鍵附魔功能
- **附魔**  
  `物件`：視口選中項  
  `效果`：將附魔材質新增到選中物體的覆層材質  
  `可選項`：祛魔 - 清除覆層材質  
  - 自訂附魔 [顏色，速度，縮放，透明度] - 新增一個元件，在執行時建立動態材質實例，修改以上參數  
  > · 由於動態材質實例的特性，只有開始遊戲和渲染時才能看到效果【0.4正式版（25w01a）已修復此問題！】  
  > · 與植物搖擺一起使用會有穿模bug【0.5-pre1（25w15a）新增的動態準備材質功能可解決此問題！】  
  

#### 24w14b
- 更新了外掛面板的UI文字綁定，為後續更新和多語言支援帶來便利。現在所有名稱記錄在`語言本地化_language_localization.csv`檔案中，可以很方便地編輯，然後匯入虛幻引擎變成表格，在外掛執行時載入。

#### 24w14a
- 重新整理了外掛結構，所有虛幻引擎相關內容都在MCprep資料夾裡，丟到專案檔的Content目錄下就可以使用了
- 從這個版本起，不需要安裝Easy File Dialog作為前置外掛了，選擇資料夾的功能由TApython提供
- 製作了2個影片渲染預設和1個自訂配置檔案，可以透過外掛面板修改。我們終於實現了在虛幻引擎中快速匯出影片的方法——甚至還能匯出HDR影片！先來看看全新的“自訂渲染配置”功能吧
- **預設**（選項框）  
  `物件`：MCprep自訂渲染配置/外掛面板細節參數  
  `效果`：選擇一個渲染預設，載入到“MCprep自訂渲染配置”和外掛面板細節參數  
  `可選項`：(Intel)2K.mp4, (Intel)HDR_2K.mp4, 2K.png, ACES_2K.exr, HDR_2K.exr, VR全景_8K.png
- **初始化影片渲染**  
  `物件`：DefaultEngine.ini  
  `效果`：如果要匯出影片，需要進行初始化並重啟專案檔（一個專案只需一次初始化）。它會解壓ffmpeg壓縮包，把ffmpeg.exe的路徑新增到專案設定中，並修改一些編碼參數
- **開啟輸出資料夾**  
  `物件`：/Saved/MovieRenders  
  `效果`：開啟預設輸出資料夾。如果路徑名稱包含中文等特殊字元，會彈出一個警告。此時你可以渲染圖片序列影格，但不能用ffmpeg匯出影片！建議使用純英文路徑
- **更新渲染配置**  
  `物件`：MCprep自訂渲染配置  
  `效果`：將細節面板的參數載入到“MCprep自訂渲染配置”中，你可以在渲染時呼叫它。  
  `可選項`：（可以使用預設或手動修改）
  - 輸出圖片序列影格格式 [png, jpg, exr]  
  - 解析度 [1080p, 2K, 4K, VR全景_4K, VR全景_8K]
  - 空間取樣數、時間取樣數
  - 色彩管理 [普通(sRGB), HDR(Rec2100 PQ), ACEScg]
  - 全景渲染（勾選框）
  - 輸出影片（勾選框）
  - 影片編碼 [H.264, H.265]
  - 硬體加速 [CPU(慢), Nvidia GPU, Intel GPU, AMD GPU]
  - 色度抽樣 [yuv420p, yuv422p, yuv444p, yuv420p10le, yuv422p10le, yuv444p10le]
  - 質量 [低, 中, 高, 極高]
  - 是HDR影片（勾選框）
> 如果不清楚某個選項最好不要動它！錯誤的搭配會導致影片顏色怪異甚至無法播放，不過windows自帶的播放器比較差，yuv444都放不出來(*￣︿￣)。顯示卡編碼比cpu快得多，這兩年的intel核顯就已經很強了，強烈推薦用顯示卡。另外把png編碼成影片的速度遠慢於jpg和exr。

  下面是兩個新的影片編碼預設
- `Nvidia_2K_mp4`使用2560x1440解析度，輸出png序列影格，透過ffmpeg編碼為10bit H265的mp4影片。預設編碼器是Nvidia的hevc_nvenc  
  注：把8bit素材編碼為10bit影片，實測下來真的能減少色彩斷層！
- `Nvidia_HDR_2K_mp4`使用 *HDR_2K_exr* 的預設，透過ffmpeg編碼為10bit H265的mp4影片，帶Rec2100 PQ靜態元資料。預設編碼器是Nvidia的hevc_nvenc
- *小故事：我測試外掛時使用最高質量影片編碼，匯出後仍然有色彩斷層，這是怎麼回事呢...？哦原來我在用筆記本遠端連線桌上型電腦，網路傳輸壓畫質了hhh*

#### 24w13b
- 製作了4個渲染預設和1個OCIO色彩管理檔案。（沒有渲染預設前，我會優先選擇錄屏，畢竟UE5比起blender最大的優勢就是速度快嘛。以下渲染配置都是1個取樣，不使用路徑追蹤，有N卡的使用者強烈推薦安裝DLSS！）  
- `2K_png`是之前常用的渲染設定，使用2560x1440解析度並輸出png序列影格。若安裝了DLSS外掛，還會使用DLAA。  
- `ACES_2K_exr`使用2560x1440解析度和ACEScg色彩變換，輸出DWAA壓縮的exr序列影格。若安裝了DLSS外掛，還會使用DLAA。這個需要在達芬奇等專業後期軟體裡剪輯，可以轉換成其他色彩空間。  
- `HDR_2K_exr`使用2560x1440解析度和Rec2100PQ色彩變換，輸出DWAA壓縮的exr序列影格。若安裝了DLSS外掛，還會使用DLAA。這個需要在支援HDR和exr的後期軟體裡剪輯，比如PR和達芬奇。  
- `VR全景_8K_png`使用7680x3840解析度，輸出png序列影格。必須開啟虛幻引擎自帶的Movie Render Queue Additional Render Passes外掛並關閉專案設定裡的自動曝光。若安裝了DLSS外掛，還會使用DLSS Quality。注意全景圖需要很高的解析度才會看起來清晰，而且尺寸要是2:1。預設設定使用橫8縱3的拼接模式，速度超慢還佔顯示記憶體（目測24G都不夠用），我試驗後改成橫5縱3，配合DLSS 16G勉強夠用。如果電腦帶不動可以降解析度，但是4K會比8K糊得多。

#### 24w13a
- 在弄壞了兩次外掛後，我準備定期更新github，既能作為備份也能推進開發。不如...就學mojang一週發一個快照吧
- 添加了Readme簡介，記錄了0.1 0.2兩個分支版本
- 製作了用於附魔的覆層材質和用於動畫序列影格的材質函式

</details>

### 0.2
- 小外掛有圖形化介面啦~透過右鍵執行編輯器工具控制元件即可調出外掛面板。下面是已實現的功能和可選參數  
*自0.5-pre1(25w14a)起，資產資料夾路徑已更改為內容瀏覽器選中項*
- **準備場景**  
  `物件`：視口選中項/資產資料夾  
  `效果`：批次最佳化材質、貼圖和碰撞箱。修改模型碰撞複雜度為“將複雜碰撞用作簡單碰撞”；修改材質混合模式為“已遮罩”，啟用“雙面”，連線Alpha通道，將高光貼圖反轉後連線到粗糙度；修改紋理貼圖的過濾器為“最近”，如果不是法線貼圖再把壓縮設定改為“使用者介面2D（RGBA）”  
  `可選項`：重載材質屬性（金屬度，高光度，粗糙度）
  
- **更換材質**  
  `前提`：安裝UE5的Easy File Dialog外掛。*0.3版本已不再需要前置外掛*  
  `物件`：視口選中項/資產資料夾  
  `效果`：批次更換貼圖（支援PBR材質包，但不支援CTM連線紋理），同時呼叫“準備場景”中的最佳化材質功能。執行時會彈出資源管理器，讓你選擇一個MC材質包解壓後的資料夾。  
  `可選項`：重載材質屬性（金屬度，高光度，粗糙度） 

- **植物搖擺**  
  `前提`：安裝UE5的TApython外掛。 *0.4版本已不再需要前置外掛，可能需要開啟實驗性功能重新整理材質*  
  `物件`：視口選中項/資產資料夾  
  `效果`：讓選中的物件隨風搖擺。在材質中建立simple grass wind節點並連線到全域性位置偏移  
  `可選項`：搖擺幅度，搖擺速度

- **啟動Blender**  
  `效果`：把你的Blender.exe檔案路徑複製到框中（建議直接複製到外掛的預設值），點一下圖示即可開啟blender。以後還會新增更多功能

- *小故事：~~怎麼會有人把自己的外掛搞壞了兩次啊qwq~~ 我想把外掛複製到另一個專案檔裡，一不小心按了ctrl+x剪貼，又一不小心按了ctrl+z撤銷，然後它 ...原地消失了！  
  嘗試恢復檔案無果後，我只好從頭再做一遍，不過這次有了更好看的UI介面和更整齊的藍圖節點，為後續更新打下了基礎*


### 0.1
- 最早的版本，寫了兩個python檔案，`Blender_export.py`可以在blender中批次處理mcprep最佳化過的材質，使貼圖能夠匯出到OBJ/FBX中。`unreal_mcprep.py`則是在虛幻引擎裡批次最佳化材質、貼圖和碰撞箱。
- *小故事：當時我隨便給檔案起了個名字，好像叫test.py，結果一不小心把它覆寫掉了，痛失外掛qwq。後來我重寫了程式碼，把它傳到github上做備份，Unreal MCprep從此誕生了！*
