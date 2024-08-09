# Unreal-Mineprep

[**中文**](./README.md) | [**English**](./README_EN.md)

✨This is a UE5 plugin that inherits the practical features of [Blender MCprep](https://theduckcow.com/dev/blender/mcprep/), and adds some new assets to facilitate the creation of MC animations.

![image](Readme素材/0.4封面图.jpg)

<img src="/Readme素材/插件展示_EN.jpg" alt="Example Image">

*This plugin is not affiliated with Minecraft or MCprep. Upon their suggestion, we changed the name from Unreal MCprep to Unreal Mineprep to avoid confusion (versions 0.3 and earlier have been archived so they remain unchanged). It's easy to rename the GitHub page, but renaming the plugin folder can cause a lot of bugs, so I'll try that later if possible.

*We are planning a overhaul of the plugin, and 0.4-pre2 gonna rename the root directory to Mineprep!

> Currently there is no user tutorial •ࡇ• — Before the official release of v1.0, the plugin is mainly for internal use, and we haven't planned to deal with compatibility and potential ~~bugs~~ features. If you don't have Unreal Engine, you can download the packed demo from the Release section to experience this plugin's demonstration.

## Installation (for version 0.3+)
1. Download the MCprep folder and place it in the "content" directory of your UE project (do not place it in other paths).

2. Enable the following built-in plugins:
- Python Editor Script Plugin
- Movie Render Queue
- Movie Render Queue Additional Render Passes
- OpenColorlO (OCIO)
- Apple Prores Media
- NiagaraFluids
- Motion Trajectory
- Motion Warping
- Pose Search
- Animation Warping
- Animation Locomotion Library
- Chooser
- Deformer Graph
- Text 3D
- Metasound
- Take Recorder (not necessary in the current version)
- Chaos Flesh (not necessary in the current version)
- Motion Design (not necessary in the current version)

Restart Unreal Engine, right-click on the Mineprep blueprint, and click "Run Editor Utility Widget". Most of the plugin's functions should now be available!

3. Download and install [TApython](https://github.com/cgerchenhp/UE_TAPython_Plugin_Release) and [DLSS](https://developer.nvidia.com/rtx/dlss/get-started) to use additional features like auto sway. These need to be installed manually, which can be a bit tricky for beginners (Remember the first time you installed mods for MC? Forge, Fabric, pre-request... It was truly a bit difficult. ~~Oh you say play the Bedrock Edition, never mind then~~). The installation process will be simplified in the future!

4. Download [Blender](https://www.blender.org/download/) and install [MCprep](https://theduckcow.com/dev/blender/mcprep/), then configure the Blender path in the Mineprep panel to use the block and item spawner.

5. If you want to render videos, remember to click "Init Video Render" in the plugin panel and then restart. Note that we use [ffmpeg](https://ffmpeg.org/download.html) for video encoding, and its storage path, which is your project file path, cannot contain non-ascii characters. (Besides, click "Experimental Features" and restart to unlock VR stereoscopic rendering. If you don't use it, you needn't click it.)

## License
- This plugin is open-source under the GPL-3.0 license, which is also inherited from MCprep.
- Thanks to all the software and plugins referenced, including Unreal Engine, Minecraft, Blender, MCprep, FFmpeg, TApython, DLSS, etc. You may also check their requirements — for example, MCprep requires you to own a legitimate copy of Minecraft, and the official assets of Unreal Engine  can only be used within UE.

## Version Updates

#### 0.4-pre1
![image](Readme素材/0.4封面图.jpg)
- New milestone (*・ω・)ﾉ We fixed a lot of bugs and added several new features this week. The packaged demo exe containing all the content from 0.3 and 0.4-pre1 will be uploaded later as a formal Release.
- mcprep_data.json has been updated to version 1.21, synchronized with the newly released MCprep 3.6. The default resource pack has not been updated yet.
- Added a `Complex` option next to the "Collision" option in the plugin panel, enabled by default. Previous prepared scenes also used complex collision; if you want to perform physical simulations, please disable this option and then use the prepared scene on the selected items. Additionally, three new functions have been added:
- **Replace Material**  
  `Modifies`: Viewport Selected   
  `Effect`: Searches for a single static mesh or a blueprint containing skeletal mesh components and replaces all materials with the specified material. If no material is specified, no replacement will occur.  
  `Options`: Material, Overlay, Physics
- **Process Recorded Animation**  
  `Modifies`: Opened sequencer  
  `Effect`: Searches for "Motion Matching Player" on the timeline, finds recorded animations, and attempts to fix rotation issues. (I finally found this bug. Since the MC rigs are redirected to the official motion matching character at runtime, it records keyframe animations twice. Resetting the MC rigs' rotation to zero can partially solve the issue of idle camera rotation).
> The following is the first experimental feature and the first one to include C++ code.  
> We discovered the hidden VR+3D rendering function last week and couldn't wait to bring it out this week -- please use experimental features with caution. A detailed introduction and warning will pop up before running, requiring confirmation to proceed.
- **Experimental Feature**  
  `Requires`: UE version 5.4 + Windows system (Otherwise, it will try to recompile the plugin from source code when opening the project file, and it's currently unclear if Visual Studio is needed)  
  `Modifies`: Movie Render Queue Additional Render Passes plugin  
  `Effect`: Extracts the modified new plugin and moves it to the Plugins folder in the root directory of the project file. It will prioritize loading the plugin from here upon restart. The Stereo, Eye Separation, and Eye Convergence Distance options in panoramic rendering have been unlocked, allowing output of stereoscopic panoramic rendering. Other rendering presets are unaffected. It has not yet been added to the custom rendering configuration in the plugin panel.  
  `Options`: Yes/No
- New rendering preset `【实验性】VR_3D-FTB_8K_HDR_exr`, requires enabling experimental features  
  - Uses 8640*8640 resolution, outputs a Full-Top-Bottom panoramic sequence, adopts Rec2100 PQ color transformation, and DWAA compressed exr encoding. Since we're doing such high-spec rendering, let's max out all parameters.
  - Each frame is about 35MB, requiring about 40G of VRAM + shared memory... This is really not something an ordinary computer can handle qwq (exr is already much smaller than png).
- Continued fixing rendering preset and character collision bugs
- Added `Diffuse` slider to the "Light Path" panel, which can increase the intensity of indirect lighting
- Now you can place multiple "Soft Body Steve" in the scene
- The shortcut key for inverting the mouse Y-axis in "FPV Flight Mode" has been changed to Tab
- Added an option for automatic wall climbing (i.e., two-block high) to the "Motion Matching Player", enabled by default; can be disabled at runtime by pressing Tab
- Both "Motion Matching Player" and "Simple NPC" now have item slots and can enable physical simulation through the num pad.  
  "0" - Paralysis   "." - Toggle gravity   "2" - Drop item  
  "4" - Break left arm   "1" - Break left leg  
  "6" - Break right arm   "3" - Break right leg  
  "8" - Break head   "5" - Break Full body   
  - When recording animations using the camera recorder, if you want to throw the held item, add "Nearby Spawned Actors", and then manually specify the model of the thrown item on the timeline. This is currently the best method, as directly dropping the original item causes jitter, while spawning a new item is more stable.
> The above shortcuts may require enabling Num Lock on the num pad
- Added "NPC跑步跟随目标" (Run to Follow Target) option and several original running animations to the creature detail panel.
- "MC Sky" can now set the direction and speed of cloud movement, and the cascade shadow distance of lighting has been increased for smoother transitions
- "Prepared Scene" now adds sound effect physical materials based on block names. Currently, there are six types: grass, gravel (dirt), sand, snow, stone, and wood. Unmatched ones are considered stone. The "Motion Matching Player" will play corresponding footstep sound effects when walking on them. Note that the entire audio rendering module is still in early development, and currently, you can only hear the sound.
- Added `Smooth Physical Material`, `Elastic Physical Material`, and the previously existing "High Friction Physical Material" to affect objects with enabled physical simulation.
- Removed the material interface of "Interactive 2D Water Surface" because water materials require a dedicated module to render waves, and randomly changing one doesn't work. Also, changed its collision target from Actor to component, fixing the collision failure bug.
- Fixed the bug where "Light Linking" was ineffective for internal components
- The "2x Distance Field" and "Enable Nanite" options in the "LOD&Nanite" function are disabled by default, as they run very slowly. The first button to disable shadows seems more practical.
- The plugin panel pop-up now supports English, and part of the GitHub Readme has also been translated into English -- Yes, clicking the English button at the top won't lead to a 404 page anymore. The oldest bug has finally been fixed!

> [!NOTE]
> The remaining translation is WIP
