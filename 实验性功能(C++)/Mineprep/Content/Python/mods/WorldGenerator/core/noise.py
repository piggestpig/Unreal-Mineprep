"""2D gradient (Perlin) noise on world coordinates with an explicit integer hash.

No process hash(), RNG state or per-tile normalization: a value depends only on
seed, salt and coordinates. Grid inputs x[1,X], z[Z,1] take a fast path that
hashes each lattice corner once instead of once per sample.
"""

from functools import lru_cache
import hashlib

import numpy as np

NOISE_VERSION = "perlin2-splitmix64-1"

_ANGLES = (np.arange(16) + 0.5) * (2 * np.pi / 16)
_GX, _GZ = np.cos(_ANGLES), np.sin(_ANGLES)
_SCALE = np.sqrt(2.0)  # unit gradients bound 2D Perlin by sqrt(1/2)


@lru_cache(maxsize=4096)
def seed_key(seed, salt):
    """uint64 key and a per-salt lattice offset in [0,256)², so octaves never align."""
    raw = hashlib.sha256(salt.encode("utf-8")).digest()
    key = np.uint64((seed & (2**64 - 1)) ^ int.from_bytes(raw[:8], "little"))
    offset = (int.from_bytes(raw[8:12], "little") / 2**24, int.from_bytes(raw[12:16], "little") / 2**24)
    return key, offset


def _hash64(ix, iz, key):
    # uint64 arithmetic intentionally wraps; signed coordinates keep their bits.
    with np.errstate(over="ignore"):
        h = (ix.astype(np.uint64) * np.uint64(0x9E3779B185EBCA87)
             ^ iz.astype(np.uint64) * np.uint64(0xC2B2AE3D27D4EB4F) ^ key)
        h = (h ^ (h >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        h = (h ^ (h >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        h = h ^ (h >> np.uint64(31))
    return h


def _hash(ix, iz, key):
    return (_hash64(ix, iz, key) >> np.uint64(60)).astype(np.intp)


def _fade(t):
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def perlin2(x, z, *, seed=42, salt="terrain"):
    """Broadcast x,z in lattice units; float64 in [-1,1], 0 mean, C2 continuous."""
    key, (ox, oz) = seed_key(seed, salt)
    x = np.asarray(x, dtype=np.float64) + ox
    z = np.asarray(z, dtype=np.float64) + oz
    ix, iz = np.floor(x), np.floor(z)
    fx, fz = x - ix, z - iz
    ix, iz = ix.astype(np.int64), iz.astype(np.int64)
    if x.ndim == 2 and z.ndim == 2 and x.shape[0] == 1 and z.shape[1] == 1:
        # Separable grid: hash the small lattice once, then gather per sample.
        bx, bz = int(ix.min()), int(iz.min())
        lx = np.arange(bx, int(ix.max()) + 2, dtype=np.int64)[None, :]
        lz = np.arange(bz, int(iz.max()) + 2, dtype=np.int64)[:, None]
        g = _hash(lx, lz, key)
        gx, gz = _GX[g], _GZ[g]
        ux, uz = (ix - bx)[0], (iz - bz)[:, 0]
        rows = [(gx[uz + k], gz[uz + k]) for k in (0, 1)]
        corner = lambda r, c: (rows[r][0][:, ux + c], rows[r][1][:, ux + c])
    else:
        ix, iz, fx, fz = np.broadcast_arrays(ix, iz, fx, fz)

        def corner(r, c):
            g = _hash(ix + c, iz + r, key)
            return _GX[g], _GZ[g]
    (ax, az), (bx_, bz_) = corner(0, 0), corner(0, 1)
    (cx, cz), (dx, dz) = corner(1, 0), corner(1, 1)
    fx1, fz1 = fx - 1.0, fz - 1.0
    tx, tz = _fade(fx), _fade(fz)
    a = ax * fx + az * fz
    b = bx_ * fx1 + bz_ * fz
    c = cx * fx + cz * fz1
    d = dx * fx1 + dz * fz1
    low = a + (b - a) * tx
    high = c + (d - c) * tx
    return (low + (high - low) * tz) * _SCALE


def fbm2(x, z, *, seed, salt, octaves=4, lacunarity=2.0, persistence=0.5):
    """Amplitude-normalized fBm; each octave has its own salt and lattice offset."""
    total, frequency, amplitude, weight = 0.0, 1.0, 1.0, 0.0
    for octave in range(octaves):
        total = total + amplitude * perlin2(x * frequency, z * frequency, seed=seed,
                                            salt=f"{salt}/{octave}")
        weight += amplitude
        frequency *= lacunarity
        amplitude *= persistence
    return total / weight


def ridged2(x, z, **kwargs):
    """1 - |fbm|: sharp crests at the zero set of the fBm, in [0,1]."""
    return 1.0 - np.abs(fbm2(x, z, **kwargs))
