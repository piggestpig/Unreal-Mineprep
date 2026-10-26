"""Continuous cover and rock signals; no terrain or physical water changes."""
import numpy as np
from ...core.fields import field
from ...core.reference import slope as height_slope
from .terrain import _coast_blend,_smooth


@field('slope',deps=('height',),halo=1)
def slope(ctx,height):
    """Standalone fallback; reference evaluation primes the same exact gradient."""
    return height_slope(np.clip(height,ctx.param('world.y_min'),ctx.param('world.y_max')))


@field('shore_cover_weight',deps=('height','water_level','water_presence'),halo=9)
def shore_cover(ctx,height,levels,presence):
    if not ctx.param('water.generate'): return 0.
    height=np.clip(height,ctx.param('world.y_min'),ctx.param('world.y_max'))
    wet=(presence>0)&(np.ceil(height)<=levels)
    return _coast_blend(wet)*_smooth(1-np.abs(height-levels)/8)


@field('surface_rock',deps=('slope','shore_cover_weight'))
def rock(ctx,slope,shore):
    """Shared land/underwater cliff signal, with bounded cover on shore shoulders."""
    excess=slope-ctx.param('surface.steep_slope')
    shift=.4*ctx.noise('surface/jitter/slope',ctx.param('surface.boundary_scale'),octaves=2)
    return np.maximum(excess-shift-shore,excess-1.2)


@field('foothill_temperature',deps=('temperature','altitude'))
def foothill_temperature(ctx,temperature,altitude):
    return temperature+ctx.param('climate.cooling')*np.maximum(altitude-ctx.param('climate.mountain_height'),0)/128


@field('shore_cover_depth',deps=('shore_cover_weight','surface_rock'))
def cover_depth(ctx,shore,rock):
    base=ctx.param('surface.soil_depth');extra=ctx.param('surface.shore_cover_extra')
    if not base or not extra: return base
    noise=np.clip(3*ctx.noise('surface/shore_cover',ctx.param('surface.boundary_scale'),octaves=2),-1,1)
    extra=np.rint(extra*shore*(.75+.25*noise))
    return np.minimum(32,base+np.where(rock<0,extra,0))
