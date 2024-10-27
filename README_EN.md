# Unreal-Mineprep

English | [**中文**](./README.md) | [**繁體中文**](./README_ZH-Hant.md)

✨This is a UE5 plugin that inherits the practical features of [Blender MCprep](https://theduckcow.com/dev/blender/mcprep/), and adds some new assets to facilitate the creation of MC animations.

![image](Readme素材/0.4-pre2封面图.jpg)

![image](Readme素材/插件展示_EN.jpg)

*This plugin is not affiliated with Minecraft or MCprep. Upon their suggestion, we changed the name from Unreal MCprep to Unreal Mineprep to avoid confusion (versions 0.3 and earlier have been archived so they remain unchanged).

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
- PhysicsControl
- Procedural Content Generation Framework (PCG)
- Mover(not necessary for now)
- Take Recorder (not necessary for now)
- Chaos Flesh (not necessary for now)
- Motion Design (not necessary for now)

Restart Unreal Engine, right-click on the Mineprep blueprint, and click "Run Editor Utility Widget". Most of the plugin's functions should now be available!

3. Download and install [TApython](https://github.com/cgerchenhp/UE_TAPython_Plugin_Release) and [DLSS](https://developer.nvidia.com/rtx/dlss/get-started) to use additional features like auto sway. These need to be installed manually, which can be a bit tricky for beginners (Remember the first time you installed mods for MC? Forge, Fabric, pre-request... It was truly a bit difficult. ~~Oh you say play the Bedrock Edition, never mind then~~). The installation process will be simplified in the future!

4. Download [Blender](https://www.blender.org/download/) and install [MCprep](https://theduckcow.com/dev/blender/mcprep/), then configure the Blender path in the Mineprep panel to use the block and item spawner.

5. If you want to render videos, remember to click "Init Video Render" in the plugin panel and then restart. Note that we use [ffmpeg](https://ffmpeg.org/download.html) for video encoding, and its storage path, which is your project file path, cannot contain non-ascii characters. (Besides, click "Experimental Features" and restart to unlock VR stereoscopic rendering. If you don't use it, you needn't click it.)

## Mobs
- Mineprep provides MC mobs that can be placed through the spawner panel; there are two types: skeletal mesh and automated NPC.
- 0.4-pre2 supports Pig, Cow, Sheep, Horse (Donkey, Mule, Zombie Horse, Skeleton Horse), Zombie, Husk, Drowned, Skeleton, Wither Skeleton, Stray, Bogged, Piglin, Piglin Brute, Pillager, Vindicator, and Iron Golem.
- "Steve" and "Alex" represent generic player models that can change skins.
- More content is WIP.

## Localization
- Mineprep offers extensible multi-language support. Currently, the plugin panel is the most complete one, with support for Simplified Chinese, English, and Traditional Chinese. They are translated according to the standardized names in MC Java Edition.
- More content is WIP.

## License
- When creating the plugin, I first used the GPL-3.0 license, but then discovered that UE's source code EULA is incompatible with open-source licenses (*´･д･)? So for now there is no License file here. In short:
- In most cases, you can use this plugin for free.
> UE5.4 charges film makers with annual revenue over $1 million per seat. Apparently we won't reach that threshold hhh (UE5.3 and earlier versions even didn't  charge the film industry, but engine content is not backward compatible, so the latest Mineprep can only be used in higher versions).
- Without an open-source license on GitHub, it is private by default, so you can't modify the plugin and sell it. Given the inclusion of engine source code and official assets, UE5's EULA is incompatible with open-source licenses. You should edit it for personal use only.
> Interesting fact: open-source ≠ public ≠ free. For example, you can find Unreal Engine source code on GitHub, but it uses Epic Games' own EULA. Open-source is related to the License file.
- Thanks to all the software and plugins referenced, including Unreal Engine, Minecraft, Blender, MCprep, FFmpeg, TApython, DLSS, etc. When using relevant content, you can also check their requirements — for example, MCprep requires you to own a legitimate copy of Minecraft, and UE's official assets can only be used within Unreal Engine.
- In the future, we may consider making a Mineprep Lite, which only includes core features like prep scene and swap texture, without official assets and engine source code. This will make installation much simpler and I can put a GPL-3.0 license there.

## Version Updates

#### 0.4-pre2
![image](Readme素材/0.4-pre2封面图.jpg)
- A new milestone! We have put the results of the past few months into actual production, creating the video "Epic Animations 2" and bringing many detailed optimizations and bug fixes.
- Added `MC Director Station`, generated together with Mineprep post-processing volume as the basic module of the scene.
  - In the detail panel, you can separately control preview quality, preview FPS limit and rendering quality to optimize performance (all rendering presets no longer use cinematic quality settings, but are controlled by the MC Director Station). The default preview quality is "3+ Ultra High", and the default rendering quality is "4 Cinematic". If your computer performance is weak, it is recommended to change the preview quality to "2 High (Fast Lumen)"; if you want to reduce flickering and ghosting during rendering and further improve quality, you can change the rendering quality to "4+ Cinematic (Enhanced Lumen)".
  - The MC Director's Desk can add event keyframes on the timeline to broadcast commands to the entire scene, such as batch switching lights, switching NPC actions, starting running and jumping, etc. It can reload signal source positions (specified coordinates < specified actor < search actor by tag), adjust the maximum signal propagation distance (a negative value will shrink from the outside in), set the propagation speed to simulate delay, and modify the parameters of different commands. Enabling debug will display the sphere shape of the maximum distance.
  - In the future, we will add functions such as switching player cameras and dynamically modifying post-processing effects.
- "Motion matching player" and NPCs  have more control methods now.
  - Added custom keyboard animations to replace the old version of switching ficial expressions. It has extended to all NPCs. In the detail panel, you can choose up to 3 actions and 3 expressions, switch actions with keyboard keys 1-3, and switch expressions with keys 4-6. You can also set "blend time", "disable movement input while playing action", and "NPC loop play action 1". If you want movement offset, please ensure that the animation strip has root motion; specifically, the third-person motion matching character needs to add the prefix UE_ or UEFN_ to use the action for the official human model before retargeting, otherwise it will be directly applied to the MC model (no offset).
  - Now you can call events such as jumping, running, switching animations, dismemberment, paralysis, etc. from the timeline. (The latter belongs to the "numpad physical events", triggered by specifying the key name. The default value is 0, which means paralysis).
- The spawner panel adds `Pile up Blocks` and `Background Animal Scatter`, using the PCG plugin to procedurally place a large number of models.
  - Pile up Blocks by default generates  5x5x1 grass blocks, which can be set to be placed in mid-air or in a custom curved area. It can automatically snap to the ground based on the collision box. You can modify the block mesh, such as covering the ground with top layer snow. You can also set a second block and adjust the ratio between the two; add offsets or random rotations. Note that Pile up Blocks do not have face culling, so the performance is not good for very large scenes.
  - Background Animal Scatter will place pig, cow, sheep, and horse NPCs in a curved area. You can modify parameters such as species and density. To improve performance, all simple animal NPCs have turned off physical interactions  by default.
- "Attach" function in the spawner panel are no longer limited to the last selected actor. Some functions will be applied to all eligible objects. We added `Light Remote Controller`, which can attach remote control components to all selected light sources (excluding sunlight and sky atmosphere) with one click, allowing them to be batch controlled by the MC Director Station.
> This feature is prepared for UE5.5. With the help of "Megalights", it can greatly improve performance, supporting hundreds or thousands of lights. The shots lighting up the entire scene in the trailer look super cool \~\\(≥▽≤)/\~
- The "Crane Camera" also has smooth motion now.
- Optimized the collision boxes of mobs, especially their hands.
- Added `Small Explosion Shake`, `Large Explosion Shake`, `Slow Camera Shake`.
- Added `Fluid-style Collision Particles`.
- The "Glow" section of Other Tools panel adds `Convolution Bloom` and `Conv-dispersion`, making the bloom softer; the "Motion Blur" section adds `FPS` (the lower the frame rate, the longer the shutter time, and the greater the blur effect); the "Light Path" section adds `Ray Tracing Translucency (Unoptimized)`, which can improve light and shadows of water and clouds. But it sometimes leads to noise and bugs, which will be optimized later.
- Fixed the UV mapping of horse skins.
- Uploaded the FBX models of new mobs in the "Blender扩展资源" folder.
- 0.4-pre2 does not have demo scenes. The final release of 0.4 version is coming during the winter vacation.
- *Story: The theme of this version is called "Trails and Tails". According to our original plan, there are two major updates - "Trails" refers to motion matching (0.4-pre1), and "Tails" refers to camera language (0.4). So what about 0.4-pre2? It's actually a overhaul of the plugin during the summer vacation. Besides, we are glad to see many new features added to the plugin too. In the next few months, we will focus on updating camera and movements~*

#### 0.4-pre1
![image](Readme素材/0.4-pre1封面图.jpg)
- New milestone (*・ω・)ﾉ We fixed a lot of bugs and added several new features this week. The packaged demo exe containing all the content from 0.3 and 0.4-pre1 will be uploaded later as a formal Release.
- mcprep_data.json has been updated to version 1.21, synchronized with the newly released MCprep 3.6. The default resource pack has not been updated yet.
- Added a `Complex` option next to the "Collision" option in the plugin panel, enabled by default. Previous prepared scenes also used complex collision; if you want to perform physical simulations, please disable this option and then use the prepared scene on the selected items. Additionally, three new functions have been added:
- **Replace Material**  
  `Modifies`: Viewport Selected   
  `Effect`: Searches for a single static mesh or a blueprint containing skeletal mesh components and replaces all materials with the specified material. If no material is specified, no replacement will occur.  
  `Options`: Material, Overlay, Physics
- **Process Recording**  
  `Modifies`: Opened sequencer  
  `Effect`: Searches for "Motion Matching Player" on the timeline, finds recorded animations, and attempts to fix rotation issues. (I finally found this bug. Since the MC rigs are redirected to the official motion matching character at runtime, it records keyframe animations twice. Resetting the MC rigs' rotation to zero can partially solve the issue of idle camera rotation).
> The following is the first experimental feature and the first one to include C++ code.  
> We discovered the hidden VR+3D rendering function last week and couldn't wait to bring it out this week -- please use experimental features with caution. A detailed introduction and warning will pop up before running, requiring confirmation to proceed.
- **Experimental**  
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
- Added "Idle-Follow AI Controller"
- Try fixing the bug where the Take Recorder can not record character camera rotation.
  - The FPV flying camera can always record rotation.
  - The MC first-person camera can now record rotation except for camera shake.
  - The motion matching player is more complicated. You need to place a `Sync Player Camera` through the spawner panel, then add it to the recording panel. It will sync and record the player's camera rotation. If the recorded animation has a few stutters, delete those keyframes and smooth the transition. Remember to switch the camera bound to the timeline before render.
- "MC Sky" can now set the direction and speed of cloud movement, and the cascade shadow distance of lighting has been increased for smoother transitions
- "Prep Scene" now adds sound effect physical materials based on block names. Currently, there are six types: grass, gravel (dirt), sand, snow, stone, and wood. Unmatched ones are considered stone. The "Motion Matching Player" will play corresponding footstep sound effects when walking on them. Note that the entire audio rendering module is still in early development, and currently, you can only hear the sound.
- Added `Smooth Physical Material`, `Elastic Physical Material`, and the previously existing "High Friction Physical Material" to affect objects with enabled physical simulation.
- Removed the material interface of "Interactive 2D Water Surface" because water materials require a dedicated module to render waves, and randomly changing one doesn't work. Also, changed its collision target from Actor to component, fixing the collision failure bug.
- Fixed the bug where "Light Linking" was ineffective for internal components
- The "2x Distance Field" and "Enable Nanite" options in the "LOD&Nanite" function are disabled by default, as they run very slowly. The first button to disable shadows seems more practical.
- The plugin panel pop-up now supports English, and part of the GitHub Readme has also been translated into English -- Yes, clicking the English button at the top won't lead to a 404 page anymore. The oldest bug has finally been fixed!

> [!NOTE]
> The remaining English translation is WIP
