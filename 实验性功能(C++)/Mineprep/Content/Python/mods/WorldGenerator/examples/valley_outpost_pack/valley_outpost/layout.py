"""The outpost's sites, paths and heightmap, in MC blocks (Y up)."""
import numpy as np
from mods.WorldGenerator.core.noise import perlin2


def sites(size):
    return {
        'inn': (round(-.24*size), max(27, round(.12*size)), 14, 15, 45),
        'shed': (round(-.30*size), -max(22, round(.12*size)), 8, 9, 42),
        'rest': (max(31, round(.16*size)), -max(22, round(.09*size)), 9, 8, 36),
    }


def paths(size):
    inn, shed, rest = (sites(size)[k] for k in ('inn', 'shed', 'rest'))
    return (
        ((inn[0], inn[1]-12, inn[4]), (-36, 0, 36), (-30, 0, 36)),
        ((shed[0], shed[1]-7, shed[4]), (shed[0]+9, shed[1]-11, 36), (-30, 0, 36)),
        ((rest[0], rest[1]-6, 36), (rest[0]+5, 0, 36), (30, 0, 36)),
    )


def smooth(value):
    t = np.clip(value, 0, 1)
    return t*t*(3-2*t)


def river_x(z, size):
    return .115*size*np.sin(z/(.23*size)) + .018*size*np.sin(z/(.065*size))


def road_distance(x, z, size):
    distance = np.full(np.broadcast_shapes(x.shape, z.shape), np.inf)
    for path in paths(size):
        for a, b in zip(path, path[1:]):
            dx, dz = b[0]-a[0], b[1]-a[1]
            t = np.clip(((x-a[0])*dx+(z-a[1])*dz)/max(1, dx*dx+dz*dz), 0, 1)
            distance = np.minimum(distance, np.hypot(x-a[0]-t*dx, z-a[1]-t*dz))
    return np.minimum(distance, np.where(np.abs(x) <= 31, np.abs(z), np.inf))


def support_pads(size):
    """Small level areas beneath the buildings, steps and three cargo stacks."""
    inn, shed, rest = (sites(size)[k] for k in ('inn', 'shed', 'rest'))
    ix, iz, _, _, iy = inn
    sx, sz, _, _, sy = shed
    return ((ix, iz-2, 11, 11, iy), (ix+11, iz+11, 3, 3, iy),
            (ix+5, iz+11, 3, 3, iy), (sx, sz, 7, 6, sy),
            (sx+3, sz-8, 3, 3, sy), (rest[0], rest[1]-1, 8, 7, rest[4]))


def pad_distance(x, z, cx, cz, rx, rz):
    return np.hypot(np.maximum(np.abs(x-cx)-rx, 0),
                    np.maximum(np.abs(z-cz)-rz, 0))


def support_distance(x, z, size):
    return np.minimum.reduce([pad_distance(x, z, *p[:4]) for p in support_pads(size)])


def clearings(x, z, size, seed):
    d = np.minimum(support_distance(x, z, size), road_distance(x, z, size)+1)
    warp = 3*perlin2(x/17, z/17, seed=seed, salt='outpost/woodland-edge')
    weight = 1-smooth((d-6+warp)/12)
    patches = np.clip(.5+1.4*perlin2(x/3, z/3, seed=seed, salt='outpost/tree-gaps'), 0, 1)
    return (d <= 5) | (patches < weight)


def worn_ground(x, z, size, seed):
    d = road_distance(x, z, size)
    wear = 2.1-d
    for name, offset, radius in (('inn', -12, 5), ('shed', -7, 4), ('rest', -7, 3)):
        cx, cz, *_ = sites(size)[name]
        wear = np.maximum(wear, radius-np.hypot(x-cx, z-cz-offset))
    edge = perlin2(x/3, z/3, seed=seed, salt='outpost/worn-edge')
    return (d < 1.5) | (wear+1.8*edge > .2)


def heights(size, seed):
    z, x = np.indices((size, size), dtype=float)
    x -= size//2
    z -= size//2
    phase = np.random.default_rng(seed).uniform(-np.pi, np.pi, 3)
    distance = np.abs(x-river_x(z, size))
    upland = smooth((distance-18)/(size*.24))
    h = 36 + upland*(9 + 3*np.sin(x/17+phase[0])*np.cos(z/23+phase[1]))
    for cx, cz, amplitude, wx, wz in ((-.32, .43, 63, .14, .15), (.27, .40, 52, .18, .19)):
        hill = np.exp(-((x/size-cx)/wx)**2-((z/size-cz)/wz)**2)
        detail = 4*np.sin(x/9+phase[0])*np.sin(z/11)+2*np.sin((x+z)/5)
        h += (amplitude+detail)*hill*smooth((distance-18)/15)
    h += upland*(1.1*np.sin(x/5+phase[2])*np.sin(z/7))
    half = max(3.2, size*.026)
    bed = 28 + 2*np.minimum(distance/half, 1)**2
    banks = smooth((distance-half)/5)
    h = bed*(1-banks) + h*banks
    # A low bank beneath the bridge; ramps meet its six-block-high deck.
    bridge = (1-smooth((np.abs(x)-20)/3))*(1-smooth((np.abs(z)-5)/4))
    h = h*(1-bridge) + np.where(distance < half+5, h, 36)*bridge
    for path in paths(size):
        for a, b in zip(path, path[1:]):
            dx, dz = b[0]-a[0], b[1]-a[1]
            t = np.clip(((x-a[0])*dx+(z-a[1])*dz)/max(1, dx*dx+dz*dz), 0, 1)
            d = np.hypot(x-a[0]-t*dx, z-a[1]-t*dz)
            weight = 1-smooth((d-2)/4)
            weight *= distance > half+6
            target = a[2]+t*(b[2]-a[2])
            h = h*(1-weight)+target*weight
    # The yard follows the approach and hillside; only the supports need levelling.
    warp = perlin2(x/18, z/18, seed=seed, salt='outpost/yard-slope')
    for cx, cz, rx, rz, level in support_pads(size):
        d = pad_distance(x, z, cx, cz, rx, rz)
        edge = d*(1+.22*warp+.15*np.tanh((z-cz)/12))
        h = np.minimum(h, level + .08*edge + .008*edge**2)
        shoulder = 1-smooth(d/10)
        h = h*(1-shoulder)+level*shoulder
    for cx, cz, rx, rz, level in support_pads(size):
        h = np.where(pad_distance(x, z, cx, cz, rx, rz) == 0, level, h)
    ramp = (np.abs(x) >= 21) & (np.abs(x) <= 31)
    weight = ramp*(1-smooth((np.abs(z)-4)/2))
    level = np.maximum(36, 42-np.floor((np.abs(x)-21)*.65))
    return h*(1-weight)+level*weight
