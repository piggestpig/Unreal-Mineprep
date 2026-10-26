"""Warped archipelagos and asymmetric floating density in world coordinates."""
import numpy as np

from ...core.fields import field
from ...core.density import density
from ...core.noise import fbm2


def pillars(params, seed):
    if params['end.layout'] != 'full' or not params['monuments.pillars']:
        return ()
    rng = np.random.default_rng(seed & (2**64-1))
    heights = rng.permutation(np.arange(24, 64, 4))
    return tuple((int(round(params['end.center_x'] + 42*np.cos(i*2*np.pi/10))),
                  int(round(params['end.center_z'] + 42*np.sin(i*2*np.pi/10))),
                  3+i%3, int(round(params['end.height']))+int(heights[i]))
                 for i in range(10))


def altar(params):
    return params['end.layout'] == 'full' and params['monuments.portal']


def islands(x, z, params, seed):
    """Continuous island potential; shared by reference maps and the volume."""
    mode = params['end.layout']
    if mode not in ('outer','full'):
        raise ValueError('end.layout must be outer or full')
    x,z = np.broadcast_arrays(x,z)
    scale = params['end.scale']
    wx = x + .24*scale*fbm2(x/scale,z/scale,seed=seed,salt='end/warp_x',octaves=2)
    wz = z + .24*scale*fbm2(x/scale,z/scale,seed=seed,salt='end/warp_z',octaves=2)
    broad = fbm2(wx/(scale*.8),wz/(scale*.8),seed=seed,salt='end/outer',octaves=3)
    fragments = fbm2(wx/(scale*.25),wz/(scale*.25),seed=seed,salt='end/fragments',octaves=2)
    body = 2.2*broad + .3*fragments - (1.1-1.13*params['end.density'])
    if params['end.density'] == 0:
        body = np.full(x.shape,-3.)
    central = np.zeros(x.shape,bool)
    if mode == 'full':
        dx,dz = x-params['end.center_x'],z-params['end.center_z']
        distance = np.hypot(dx,dz)
        fade = np.clip((distance-params['end.outer_start'])/(scale*.35),0,1)
        body -= 3*(1-fade)
        radius = params['end.main_radius']
        mx = dx + .3*radius*fbm2(dx/radius,dz/radius,seed=seed,salt='end/main_x',octaves=2)
        mz = dz + .3*radius*fbm2(dx/radius,dz/radius,seed=seed,salt='end/main_z',octaves=2)
        main = 1.25*(1-np.hypot(mx,mz)/radius)
        main += .38*fbm2(dx/32,dz/32,seed=seed,salt='end/main_edge',octaves=2)
        central = (main > body) & (main > -.4)
        body = np.maximum(body,main)
    return np.clip(body,-3,1.1),central


def elevation(x, z, params, seed):
    scale = params['end.scale']*1.8
    noise = fbm2(x/scale,z/scale,seed=seed,salt='end/elevation',octaves=2)
    main = 0
    if params['end.layout'] == 'full':
        distance = np.hypot(x-params['end.center_x'],z-params['end.center_z'])
        radius = params['end.main_radius']
        main = np.clip((radius*1.5-distance)/(radius*.5),0,1)
    return params['end.height']-4*main + (params['end.relief']*(1-main)+3*main)*noise


def layout(x, z, params, seed):
    body,central = islands(x,z,params,seed)
    level = elevation(x,z,params,seed)
    top = level + 8*np.clip(body,0,.45)
    bottom = level - params['end.thickness']*np.maximum(body,0)**(1/.85)
    if altar(params):
        distance = np.hypot(x-params['end.center_x'],z-params['end.center_z'])
        pad = np.clip((14-distance)/8,0,1)
        top -= pad*np.maximum(top-params['end.height'],0)
    biome = np.where(body>.32,1,np.where(body>.12,2,np.where(body>0,3,4)))
    biome = np.where(central,0,biome).astype(np.uint16)
    return top,bottom,body,biome


def _layout(ctx):
    cached = getattr(ctx,'_end_layout',None)
    if cached is None:
        cached = layout(ctx.x,ctx.z,ctx.params,ctx.seed)
        ctx._end_layout = cached
    return cached


@field('height')
def height(ctx):
    top,_,body,_ = _layout(ctx)
    return np.where(body>0,top,0.)


@field('island_presence')
def presence(ctx):
    return (_layout(ctx)[2]>0).astype(float)


@field('end_biome')
def biome(ctx):
    return _layout(ctx)[3].astype(float)


@density('end_level',res=8,axes='xz')
def level(ctx):
    return elevation(ctx.x,ctx.z,ctx.params,ctx.seed).astype(np.float32)


@density('end_body',res=4,axes='xz')
def body(ctx):
    return islands(ctx.x,ctx.z,ctx.params,ctx.seed)[0].astype(np.float32)


@density('end_rock',res=4)
def rock(ctx):
    return (.8*ctx.noise('end/rock',(48,24,48),octaves=2)
            + .22*ctx.noise('end/detail',(18,10,18),octaves=1))


@density('end_solid',deps=('end_level','end_body','end_rock'))
def solid(ctx, level, body, rock):
    y = ctx.y+.5
    p = ctx.params
    offset = y-level
    # Strong cores deepen the island rather than turning every top into a dome.
    shoulder = np.maximum(body-.35,0)*np.clip((offset+2)/6,0,1)
    result = body+rock-shoulder-np.maximum(offset,0)/8-(np.maximum(-offset,0)/p['end.thickness'])**.85
    if altar(p):
        distance = np.hypot(ctx.x-p['end.center_x'],ctx.z-p['end.center_z'])
        pad = np.clip((14-distance)/8,0,1)
        result -= pad*np.maximum(result-(p['end.height']-y)/8,0)
    for cx,cz,radius,high in pillars(p,ctx.seed):
        radial = radius+.25-np.hypot(ctx.x-cx,ctx.z-cz)
        if (radial > 0).any():
            column = np.minimum(radial,np.minimum(y-(p['end.height']-12),high-y))
            result = np.maximum(result,column)
    if altar(p):
        radius = np.hypot(ctx.x-p['end.center_x'],ctx.z-p['end.center_z'])
        floor = np.minimum(3.5-radius,np.minimum(y-(p['end.height']-3),p['end.height']-y))
        rim = np.minimum(np.minimum(3.5-radius,radius-2.3),np.minimum(y-p['end.height'],p['end.height']+1-y))
        stem = np.minimum(.8-radius,np.minimum(y-p['end.height'],p['end.height']+4-y))
        result = np.maximum(result,np.maximum(floor,np.maximum(rim,stem)))
    return result.astype(np.float32)


def materials(ctx):
    result = ctx.materials.copy()
    p = ctx.params
    for cx,cz,radius,high in pillars(p,ctx.seed):
        r = np.hypot(ctx.x-cx,ctx.z-cz)
        selected = (r < radius+.25) & (ctx.y >= p['end.height']-12) & (ctx.y < high)
        result[selected] = ctx.block_index['obsidian']
        result[selected & (ctx.x==cx) & (ctx.z==cz) & (ctx.y==high-1)] = ctx.block_index['bedrock']
    if altar(p):
        selected = ((np.hypot(ctx.x-p['end.center_x'],ctx.z-p['end.center_z']) < 3.5)
                    & (ctx.y >= p['end.height']-3) & (ctx.y < p['end.height']+4))
        result[selected] = ctx.block_index['bedrock']
    return result
