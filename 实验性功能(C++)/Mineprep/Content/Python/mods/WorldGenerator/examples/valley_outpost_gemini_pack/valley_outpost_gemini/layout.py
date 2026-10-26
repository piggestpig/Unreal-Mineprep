"""Organic ridged-FBM valley, winding roads, and gently graded building terraces in MC blocks (Y up)."""
import numpy as np
from mods.WorldGenerator.core.noise import fbm2, perlin2


def sites(size):
    return {
        'inn': (round(-.22*size), max(28, round(.11*size)), 15, 15, 45),
        'shed': (round(-.29*size), -max(22, round(.11*size)), 9, 9, 41),
        'rest': (max(31, round(.16*size)), -max(21, round(.09*size)), 10, 9, 36),
    }


def paths(size):
    inn, shed, rest = (sites(size)[k] for k in ('inn', 'shed', 'rest'))
    return (
        ((inn[0], inn[1]-12, inn[4]), (inn[0]+8, inn[1]-20, 41), (-38, 4, 37), (-28, 0, 36)),
        ((shed[0], shed[1]-7, shed[4]), (shed[0]+10, shed[1]-11, 39), (-36, -6, 37), (-28, 0, 36)),
        ((28, 0, 36), (rest[0]-6, -6, 36), (rest[0], rest[1]-7, rest[4]), (rest[0]+14, rest[1]-14, 35)),
    )


def smooth(value):
    t = np.clip(value, 0, 1)
    return t*t*(3-2*t)


def river_x(z, size):
    return .11*size*np.sin(z/(.24*size)) + .022*size*np.cos(z/(.08*size) + .4)


def road_distance(x, z, size, seed=42):
    wx = x + 1.4*perlin2(x/11, z/11, seed=seed, salt='outpost/road-wx')
    wz = z + 1.4*perlin2(x/11, z/11, seed=seed, salt='outpost/road-wz')
    distance = np.full(np.broadcast_shapes(x.shape, z.shape), np.inf)
    for path in paths(size):
        for a, b in zip(path, path[1:]):
            dx, dz = b[0]-a[0], b[1]-a[1]
            t = np.clip(((wx-a[0])*dx+(wz-a[1])*dz)/max(1, dx*dx+dz*dz), 0, 1)
            distance = np.minimum(distance, np.hypot(wx-a[0]-t*dx, wz-a[1]-t*dz))
    return np.minimum(distance, np.where(np.abs(x) <= 29, np.abs(z), np.inf))


def support_pads(size):
    """Terrace footprints beneath buildings, steps and cargo stacks."""
    inn, shed, rest = (sites(size)[k] for k in ('inn', 'shed', 'rest'))
    ix, iz, _, _, iy = inn
    sx, sz, _, _, sy = shed
    return ((ix, iz-2, 12, 12, iy), (ix+12, iz+10, 3, 3, iy),
            (ix+6, iz+11, 3, 3, iy), (sx, sz, 8, 7, sy),
            (sx+4, sz-8, 3, 3, sy), (rest[0], rest[1]-1, 9, 8, rest[4]))


def pad_distance(x, z, cx, cz, rx, rz):
    return np.hypot(np.maximum(np.abs(x-cx)-rx, 0),
                    np.maximum(np.abs(z-cz)-rz, 0))


def support_distance(x, z, size):
    return np.minimum.reduce([pad_distance(x, z, *p[:4]) for p in support_pads(size)])


def clearings(x, z, size, seed):
    d = np.minimum(support_distance(x, z, size), road_distance(x, z, size, seed))
    warp = 3.5*perlin2(x/16, z/16, seed=seed, salt='outpost/woodland-edge')
    weight = 1-smooth((d-7+warp)/13)
    patches = np.clip(.5+1.35*perlin2(x/3.5, z/3.5, seed=seed, salt='outpost/tree-gaps'), 0, 1)
    return (d <= 6) | (patches < weight)


def worn_ground(x, z, size, seed):
    d = road_distance(x, z, size, seed)
    wear = 2.8 - d
    for name, offset, radius in (('inn', -12, 6.5), ('shed', -7, 5.0), ('rest', -7, 4.5)):
        cx, cz, *_ = sites(size)[name]
        wear = np.maximum(wear, radius-np.hypot(x-cx, z-cz-offset))
    edge = perlin2(x/3.5, z/3.5, seed=seed, salt='outpost/worn-edge')
    core = (d < 2.2) | (wear + 1.4*edge > .55)
    fringe = (~core) & ((d < 3.4) | (wear + 1.8*edge > -.35))
    return core, fringe


def heights(size, seed):
    z, x = np.indices((size, size), dtype=float)
    x -= size//2
    z -= size//2
    wx = x + 14*perlin2(x/44, z/44, seed=seed, salt='outpost/warp-x')
    wz = z + 14*perlin2(x/44, z/44, seed=seed, salt='outpost/warp-z')

    distance = np.abs(x - river_x(z, size))
    upland = smooth((distance-16)/(size*.22))
    rolling = fbm2(wx/36, wz/36, seed=seed, salt='outpost/rolling', octaves=4)
    h = 35.5 + upland*(7.5 + 6.5*rolling)

    # Organic ridged-FBM mountain amphitheater with smooth map-border tapering (no sliced cones).
    border = smooth((.48 - np.maximum(np.abs(x), np.abs(z))/size) / .13)
    r1 = 1.0 - np.abs(perlin2(wx/38, wz/38, seed=seed, salt='outpost/ridge-major'))
    r2 = 1.0 - np.abs(perlin2(wx/18, wz/18, seed=seed, salt='outpost/ridge-minor'))
    crags = .64*(r1**1.55) + .36*(r2**1.75)
    strata = fbm2(wx/14, wz/14, seed=seed, salt='outpost/crag-detail', octaves=3)

    north_arc = np.exp(-((wx/size+.14)/.26)**2 - ((wz/size-.34)/.17)**2)
    east_spur = np.exp(-((wx/size-.25)/.22)**2 - ((wz/size-.29)/.19)**2)
    west_spur = np.exp(-((wx/size+.34)/.16)**2 - ((wz/size-.18)/.20)**2) * border
    envelope = np.clip(north_arc + .82*east_spur + .48*west_spur, 0, 1.15)
    mountain = (42*envelope + 34*envelope*crags + 5*strata*envelope) * smooth((distance-19)/16)
    h += mountain * (0.35 + 0.65*border)

    half = max(4.2, size*.030)
    bed = 26.5 + 3.5*np.minimum(distance/half, 1)**1.8
    banks = smooth((distance-half)/6.5)
    h = bed*(1-banks) + h*banks

    bridge = (1-smooth((np.abs(x)-22)/3.5))*(1-smooth((np.abs(z)-5)/4.5))
    h = h*(1-bridge) + np.where(distance < half+5.5, h, 36)*bridge

    for path in paths(size):
        for a, b in zip(path, path[1:]):
            dx, dz = b[0]-a[0], b[1]-a[1]
            t = np.clip(((x-a[0])*dx+(z-a[1])*dz)/max(1, dx*dx+dz*dz), 0, 1)
            d = np.hypot(x-a[0]-t*dx, z-a[1]-t*dz)
            weight = (1-smooth((d-2.5)/4.5)) * (distance > half+6)
            target = a[2]+t*(b[2]-a[2])
            h = h*(1-weight) + target*weight

    warp = perlin2(x/18, z/18, seed=seed, salt='outpost/yard-slope')
    for cx, cz, rx, rz, level in support_pads(size):
        d = pad_distance(x, z, cx, cz, rx, rz)
        edge = d*(1+.20*warp+.14*np.tanh((z-cz)/12))
        h = np.minimum(h, level + .07*edge + .007*edge**2)
        shoulder = 1-smooth(d/11)
        h = h*(1-shoulder) + level*shoulder

    # Gentle downhill edge relief so api.foundation() builds real stone masonry footings.
    for cx, cz, rx, rz, level in support_pads(size):
        in_pad = pad_distance(x, z, cx, cz, rx, rz) == 0
        front_lip = in_pad & (z < cz - rz + 2) & (np.abs(x - cx) > 3)
        pad_h = np.where(front_lip, level - 1.0, level)
        h = np.where(in_pad, pad_h, h)

    # House grading must not lift the abutments; keep the wet riverbed intact.
    h = h*(1-bridge) + np.minimum(h, 36)*bridge
    ramp = (np.abs(x) >= 21) & (np.abs(x) <= 34)
    weight = ramp*(1-smooth((np.abs(z)-4.5)/2.5))
    level = np.maximum(36, 43-np.floor((np.abs(x)-21)*.55))
    return h*(1-weight) + level*weight
