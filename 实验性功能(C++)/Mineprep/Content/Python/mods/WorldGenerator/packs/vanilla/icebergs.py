"""Continuous bodies plus sparse independent shoulders, combined as columns."""
import numpy as np
from ...core.features import ColumnBatch, FeatureBatch
from ...core.multi_features import _hash
from ...core.noise import fbm2


def shape(ctx,key):
    """Shared bounded shape for column recipes and legacy FeatureBatch callers."""
    base=ctx.param('frozen_ocean.iceberg_height')
    large=(key>>32)/2**32 < ctx.param('frozen_ocean.large_chance')
    height=int(2*base if large else .75*base)+((key>>8)%9)-4
    radius=8+((key>>12)%3)
    angle=((key>>20)%256)*np.pi/128
    x,z=np.meshgrid(np.arange(-radius,radius+1),np.arange(-radius,radius+1))
    x,z=x.ravel(),z.ravel()
    u=x*np.cos(angle)+z*np.sin(angle);v=-x*np.sin(angle)+z*np.cos(angle)
    ridge=((key>>28)%5)<2
    width=radius*(.4 if ridge else .8)
    d=(u/radius)**2+(v/width)**2
    use=d<=1
    x,z,u,v,d=x[use],z[use],u[use],v[use],d[use]
    profile=(np.maximum(0,1-(v/width)**2)*np.maximum(0,1-.5*(u/radius)**2)
             if ridge else np.maximum(0,1-d)**.45)
    profile*=np.clip(1+.15*u/radius,.8,1.2)
    top=np.maximum(1,np.floor(height*np.minimum(1,profile)).astype(np.int64))
    cut=((u-radius*.65)**2+(v+width*.7)**2)<(width*.5)**2
    keep=~cut
    return x[keep],z[keep],top[keep],np.clip(np.ceil(top[keep]/6).astype(np.int64)+2,2,6)


def build(ctx,anchors,keys):
    """Keep the existing multi-block callable contract using the shared shape."""
    parts,types,owners=[],[],[]
    for i,value in enumerate(keys):
        if int(ctx.water_depths[i])<2: continue
        key=int(value);x,z,top,depth=shape(ctx,key);depth=np.minimum(depth,int(ctx.water_depths[i]))
        lengths=top+depth;columns=np.repeat(np.arange(len(x)),lengths)
        y=np.arange(len(columns))-np.repeat(np.cumsum(lengths)-lengths,lengths)-depth[columns]
        points=np.column_stack((x[columns],y,z[columns])).astype(np.int32)
        capped=(key&65535)/2**16<ctx.param('frozen_ocean.snow_cap_chance')
        cap=capped & (top[columns]>=top.max()*.6)&(y>=top[columns]-(1+((key>>4)%3)))&(y>=0)
        parts.append(points);types.append(np.where(cap,ctx.block_ids['snow_block'],ctx.block_ids['packed_ice']).astype(np.uint16))
        owners.append(np.full(len(points),i,np.int32))
    return FeatureBatch(np.concatenate(parts) if parts else np.empty((0,3),np.int32),
        np.concatenate(types) if types else np.empty(0,np.uint16),np.concatenate(owners) if owners else np.empty(0,np.int32))


def _ceiling(base,large,roof,style):
    """Blend broad mesas, rolling roofs and shoulders around regional ridges."""
    n=np.tanh(roof)
    style=np.clip(style,0,2)
    flat=np.maximum(0,1-style);peak=np.maximum(0,style-1);wavy=1-flat-peak
    limit=base*(1.25+1.25*np.clip(large,0,1))
    detail=flat*.75*n+wavy*2*n-peak*(base*.25)*((1-n)/2)**2
    return np.minimum(2.5*base,limit+detail)


def _bevel(heights,solid):
    """Two eight-neighbour rings; neither the footprint nor submerged base moves."""
    inner=solid
    result=heights.copy()
    for scale in (1/3,2/3):
        padded=np.pad(inner,1)
        eroded=inner.copy()
        for dz in range(3):
            for dx in range(3): eroded&=padded[dz:dz+inner.shape[0],dx:dx+inner.shape[1]]
        ring=inner&~eroded
        result[ring]=np.maximum(1,heights[ring]*scale)
        inner=eroded
    return np.floor(result).astype(np.int64)


def columns(ctx):
    ref=ctx.reference;c=ref.ctx;r=ctx.region
    x,z=np.broadcast_arrays(c.x,c.z);level=np.floor(ref.levels).astype(np.int64)
    top=level.astype(float);bottom=level.copy();caps=np.zeros(c.shape,np.int64)
    base=ctx.param('frozen_ocean.iceberg_height')
    continuous=0
    if ctx.param('frozen_ocean.continuous_ice'):
        signal=np.minimum(np.abs(c.get('iceberg_surface'))*8.25,c.get('iceberg_pillar')*15)
        roof_field=c.get('iceberg_roof')
        roof=(np.abs(roof_field)*40+14)*base/16
        large=c.get('iceberg_large_weight')
        limit=_ceiling(base,large,roof_field,c.get('iceberg_top_style'))
        raw_height=signal**2*1.2*base/16
        h=np.minimum(np.minimum(raw_height,roof),limit)
        use=ctx.allowed & (signal>max(.25,1.8+4*(.65-ctx.density))) & (h>=2)
        top[use]=level[use]+h[use]
        base_roof=(np.ceil(np.abs(c.get('iceberg_base_roof'))*40)+14)*base/16
        base_height=np.minimum(np.minimum(raw_height,base_roof),base*(1.25+1.25*np.clip(large,0,1)))
        bottom[use]=level[use]-np.clip(base_height[use]//6+2,2,6)
        snow=use & (c.get('iceberg_snow_weight')>=.5) & (h>=max(4,base*.5))
        cap_key=_hash(np.floor(x/64).astype(np.int64),np.floor(z/64).astype(np.int64),ctx.seed,'iceberg/cap_depth')
        caps[snow]=(1+(cap_key%np.uint64(3)).astype(np.int64))[snow]
        inside=(x>=r.x0)&(x<r.x0+r.width)&(z>=r.z0)&(z<r.z0+r.depth)
        continuous=int((use&inside).sum())
    independent=0
    if ctx.param('frozen_ocean.isolated_fraction'):
        independent=_isolated(ctx,c,level,top,bottom,caps)
    solid=ctx.allowed & (top>level)
    top=level+_bevel(top-level,solid)
    caps=np.minimum(caps,top-level)
    use=ctx.allowed & (top>level)&(x>=r.x0)&(x<r.x0+r.width)&(z>=r.z0)&(z<r.z0+r.depth)
    xz=np.column_stack((x[use],z[use])).astype(np.int64)
    lo,hi,cap=bottom[use],top[use],caps[use]
    cut=hi-cap;has_cap=cap>0
    return ColumnBatch(np.r_[xz,xz[has_cap]],np.r_[lo,cut[has_cap]],np.r_[cut,hi[has_cap]],
        np.r_[np.full(len(lo),ctx.block_ids['packed_ice'],np.uint16),np.full(int(has_cap.sum()),ctx.block_ids['snow_block'],np.uint16)],
        dict(continuous_columns=continuous,independent_candidates=independent))


def _isolated(ctx,c,level,top,bottom,caps):
    r=ctx.region
    cx,cz=np.meshgrid(np.arange(int(c.x.min())//32-1,int(c.x.max())//32+2),
                     np.arange(int(c.z.min())//32-1,int(c.z.max())//32+2))
    cx,cz=cx.ravel(),cz.ravel()
    px=cx*32+(_hash(cx,cz,ctx.seed,'features/iceberg/x')%np.uint64(32)).astype(np.int64)
    pz=cz*32+(_hash(cx,cz,ctx.seed,'features/iceberg/z')%np.uint64(32)).astype(np.int64)
    usable=(px>=c.x.min())&(px<=c.x.max())&(pz>=c.z.min())&(pz<=c.z.max())
    cx,cz,px,pz=cx[usable],cz[usable],px[usable],pz[usable]
    xx,zz=px-int(c.x.min()),pz-int(c.z.min())
    patch=fbm2(px/ctx.patch_scale,pz/ctx.patch_scale,seed=ctx.seed,salt='features/iceberg/patch',octaves=2)
    candidate=(_hash(cx,cz,ctx.seed,'features/iceberg/candidate')>>np.uint64(11)).astype(float)/2**53
    keys=_hash(cx,cz,ctx.seed,'features/iceberg/shape')
    fraction=(_hash(cx,cz,ctx.seed,'iceberg/isolated')>>np.uint64(11)).astype(float)/2**53
    proposed=ctx.allowed[zz,xx]&(candidate<ctx.density*np.clip(1+2*patch,0,2))&(fraction<ctx.param('frozen_ocean.isolated_fraction'))
    independent=int((proposed&(px>=r.x0)&(px<r.x0+r.width)&(pz>=r.z0)&(pz<r.z0+r.depth)).sum())
    for i in np.flatnonzero(proposed):
        key=int(keys[i]);sx,sz,st,sd=shape(ctx,key)
        ax,az=px[i]+sx,pz[i]+sz
        use=(ax>=c.x.min())&(ax<=c.x.max())&(az>=c.z.min())&(az<=c.z.max())
        ax,az,st,sd=ax[use],az[use],st[use],sd[use]
        ix,iz=ax-int(c.x.min()),az-int(c.z.min())
        use=ctx.allowed[iz,ix];ix,iz,st,sd=ix[use],iz[use],st[use],sd[use]
        hi=level[iz,ix]+st;higher=hi>top[iz,ix]
        capped=(key&65535)/2**16<ctx.param('frozen_ocean.snow_cap_chance')
        caps[iz[higher],ix[higher]]=np.where(capped&(st[higher]>=st.max(initial=0)*.6),1+((key>>4)%3),0)
        top[iz,ix]=np.maximum(top[iz,ix],hi)
        bottom[iz,ix]=np.minimum(bottom[iz,ix],level[iz,ix]-sd)
    return independent
