# Unreal-MCprep

[**English**](./README_EN.md) | [**中文**](./README.md)

✨这是一个正在开发中的UE5插件，继承了 [Blender MCprep](https://theduckcow.com/dev/blender/mcprep/) 的实用功能，并加入一些新的资产，为制作MC动画带来便利~ 

> 目前还没写安装和使用教程 •ࡇ• —— 在v1.0正式发布前，插件主要供内部使用，不考虑兼容性和潜在的 ~~bug~~ 特性。需要[TApython](https://github.com/cgerchenhp/UE_TAPython_Plugin_Release) 和 [Easy File Dialog](https://www.unrealengine.com/marketplace/en-US/product/easy-file-dialog) 作为前置插件。

## 版本更新

### 0.1
- 最早的版本，写了两个python文件，`Blender_export.py`可以在blender中批量处理mcprep优化过的材质，使贴图能够导出到OBJ/FBX中。`unreal_mcprep.py`则是在虚幻引擎里批量优化材质、贴图和碰撞箱。
- *当时我随便给文件起了个名字，好像叫test.py，某天一不小心就覆写掉了，痛失插件qwq。重新写了一份后，正好把它传到github上做备份，然后Unreal MCprep就诞生了！*
