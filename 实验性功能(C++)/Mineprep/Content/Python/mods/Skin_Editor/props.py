"""Skin Editor: skin/head slot-name → material maps."""
import unreal
import mineprep


class Mats(mineprep.PropertyGroup):
    _unique_ = True
    Skin: dict[str, unreal.MaterialInterface] = {}
    Head: dict[str, unreal.MaterialInterface] = {}

Mats.localize('Mats', '材质', 'Material', '材質')
Mats.localize('Skin', '皮肤材质', 'Skin Materials', '皮膚材質')
Mats.localize('Head', '头部材质', 'Head Materials', '頭部材質')
