"""Deterministic 3D gradient noise; independent of the unchanged 2D kernel."""
import hashlib
from functools import lru_cache
import numpy as np
from .noise import _fade

VERSION = 'perlin3-splitmix64-1'
_GRAD = np.array([(a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1)
                  for c in (-1, 0, 1) if abs(a) + abs(b) + abs(c) == 2], np.float64) / np.sqrt(2)


def hash01(x,y,z,seed,salt):
    """World-coordinate draws; extracted unchanged from the Overworld ore recipe."""
    key = np.uint64((seed & (2**64-1)) ^ int.from_bytes(hashlib.sha256(salt.encode()).digest()[:8],'little'))
    with np.errstate(over='ignore'):
        h = (x.astype(np.uint64)*np.uint64(0x9E3779B185EBCA87)
             ^ y.astype(np.uint64)*np.uint64(0x165667B19E3779F9)
             ^ z.astype(np.uint64)*np.uint64(0xC2B2AE3D27D4EB4F) ^ key)
        h = (h ^ (h >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        h = (h ^ (h >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        h ^= h >> np.uint64(31)
    return (h >> np.uint64(11)).astype(np.float64) / 2**53


def _hash(x, y, z, key):
    with np.errstate(over='ignore'):
        h = (x.astype(np.uint64) * np.uint64(0x9E3779B185EBCA87)
             ^ y.astype(np.uint64) * np.uint64(0x165667B19E3779F9)
             ^ z.astype(np.uint64) * np.uint64(0xC2B2AE3D27D4EB4F) ^ key)
        h = (h ^ (h >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        h = (h ^ (h >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        h ^= h >> np.uint64(31)
    return (h % np.uint64(12)).astype(np.intp)


@lru_cache(maxsize=4096)
def _key(seed, salt):
    raw = hashlib.sha256(salt.encode()).digest()
    return np.uint64((seed & (2**64 - 1)) ^ int.from_bytes(raw[:8], 'little')), tuple(
        int.from_bytes(raw[i:i + 4], 'little') / 2**24 for i in (8, 12, 16))


def perlin3(x, y, z, *, seed=42, salt='density'):
    key, offset = _key(seed, salt)
    values = [np.asarray(v, np.float64) + o for v, o in zip((x, y, z), offset)]
    lattice = [np.floor(v).astype(np.int64) for v in values]
    fraction = [v - i for v, i in zip(values, lattice)]
    fades = [_fade(v) for v in fraction]
    result = np.zeros(np.broadcast_shapes(*(v.shape for v in values)), np.float64)
    low = [int(v.min()) for v in lattice]
    sizes = [int(v.max()) - lo + 2 for v, lo in zip(lattice, low)]
    # Rotated/scattered inputs still occupy a very small gradient lattice.
    # Hash its corners once instead of hashing eight dense arrays per sample.
    gradients = None
    if np.prod(sizes, dtype=np.float64) <= min(262144, result.size * 8):
        axes = [np.arange(lo, lo + n, dtype=np.int64) for lo, n in zip(low, sizes)]
        gradients = _GRAD[_hash(axes[0][None,None,:], axes[1][None,:,None], axes[2][:,None,None], key)]
        index = [v - lo for v, lo in zip(lattice, low)]
    for dz in (0, 1):
        for dy in (0, 1):
            for dx in (0, 1):
                g = (gradients[index[2]+dz,index[1]+dy,index[0]+dx] if gradients is not None
                     else _GRAD[_hash(lattice[0]+dx,lattice[1]+dy,lattice[2]+dz,key)])
                dot = sum(g[..., i] * (fraction[i] - d) for i, d in enumerate((dx, dy, dz)))
                weight = (fades[0] if dx else 1 - fades[0]) * (fades[1] if dy else 1 - fades[1]) * (fades[2] if dz else 1 - fades[2])
                result += dot * weight
    return np.clip(result * 1.15, -1, 1)


def fbm3(x, y, z, *, seed=42, salt='density', octaves=2, lacunarity=2., persistence=.5):
    result, weight, amplitude, frequency = 0., 0., 1., 1.
    for i in range(octaves):
        result = result + amplitude * perlin3(x * frequency, y * frequency, z * frequency, seed=seed, salt=f'{salt}/{i}')
        weight += amplitude
        amplitude *= persistence
        frequency *= lacunarity
    return result / weight
