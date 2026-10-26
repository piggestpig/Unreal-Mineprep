"""World-aligned frozen-ocean bodies; geometry remains package content."""
import numpy as np
from ...core.fields import field
from ...core.multi_features import _hash


@field('iceberg_surface',res=4)
def surface(ctx):
    return np.clip(ctx.noise('iceberg/body_surface',ctx.param('frozen_ocean.body_scale'),octaves=2)*2.5,-1,1)


@field('iceberg_pillar',res=4)
def pillar(ctx):
    return np.clip(ctx.noise('iceberg/body_pillar',ctx.param('frozen_ocean.body_scale')/1.28,octaves=2)*2.5,-1,1)


@field('iceberg_roof',res=4)
def roof(ctx):
    return ctx.noise('iceberg/body_roof',ctx.param('frozen_ocean.body_scale')/2,octaves=2)*2.5


@field('iceberg_base_roof',res=4,deps=('iceberg_roof',))
def base_roof(ctx,roof):
    """The submerged footprint keeps its bounded roof independently of top polish."""
    return np.clip(roof,-1,1)


def _region_values(ctx,salt,classify):
    x,z=ctx.x/64,ctx.z/64
    ix,iz=np.floor(x).astype(np.int64),np.floor(z).astype(np.int64)
    tx,tz=x-ix,z-iz;tx=tx*tx*(3-2*tx);tz=tz*tz*(3-2*tz)
    values=[classify((_hash(ix+dx,iz+dz,ctx.seed,salt)>>np.uint64(11)).astype(np.float64)/2**53)
            for dz,dx in ((0,0),(0,1),(1,0),(1,1))]
    return (values[0]*(1-tx)+values[1]*tx)*(1-tz)+(values[2]*(1-tx)+values[3]*tx)*tz


def region_weight(ctx,param,salt):
    return _region_values(ctx,salt,lambda u:(u<ctx.param(param)).astype(float))


@field('iceberg_top_style',res=4)
def top_style(ctx):
    return _region_values(ctx,'iceberg/top_regions',lambda u:np.where(u<.25,0.,np.where(u<.75,1.,2.)))


@field('iceberg_large_weight',res=4)
def large(ctx): return region_weight(ctx,'frozen_ocean.large_chance','iceberg/large_regions')


@field('iceberg_snow_weight',res=4)
def snow(ctx): return region_weight(ctx,'frozen_ocean.snow_cap_chance','iceberg/snow_regions')
