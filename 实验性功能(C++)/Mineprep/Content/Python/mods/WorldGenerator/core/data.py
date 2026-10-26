"""Generation data uses MC block coordinates: x/z horizontal, y up; arrays are field[z, x].

UE scenes use centimetres with z up. The only conversion is to_ue/from_ue:
UE horizontal X/Y are MC X/Z, UE Z is MC Y, with no sign changes.
"""

from dataclasses import dataclass

import numpy as np


# A deliberate float64 sampling limit, not a claim of arbitrary int64 precision.
MAX_COORD = 2**40
BLOCK_CM = 100


def to_ue(xyz, scale=BLOCK_CM):
    """MC (x, y, z) in blocks to UE (x, y, z): reorder to (x, z, y), then scale."""
    return np.asarray(xyz, np.float64)[..., [0, 2, 1]] * scale


def from_ue(xyz, scale=BLOCK_CM):
    """UE (x, y, z) to MC blocks; the inverse of to_ue."""
    return np.asarray(xyz, np.float64)[..., [0, 2, 1]] / scale


def require_int(name, value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")


class GenerationCancelled(Exception):
    """A pure-data task was cancelled before it entered the editor."""


def check_cancel(event):
    if event is not None and event.is_set():
        raise GenerationCancelled()


@dataclass(frozen=True)
class Region:
    """World integer cells [x0,x0+width) x [z0,z0+depth), sampled at integers."""

    x0: int = 0
    z0: int = 0
    width: int = 256
    depth: int = 256

    def __post_init__(self):
        require_int("x0", self.x0, -MAX_COORD, MAX_COORD)
        require_int("z0", self.z0, -MAX_COORD, MAX_COORD)
        require_int("width", self.width, 1, 2 * MAX_COORD)
        require_int("depth", self.depth, 1, 2 * MAX_COORD)
        if self.x0 + self.width > MAX_COORD or self.z0 + self.depth > MAX_COORD:
            raise ValueError("region end exceeds supported world coordinates")

    @property
    def shape(self):
        return (self.depth, self.width)

    @property
    def cells(self):
        return self.width * self.depth

    def coordinates(self):
        """Broadcastable int64 x[1,X], z[Z,1]; negative coordinates stay signed."""
        x = np.arange(self.x0, self.x0 + self.width, dtype=np.int64)[None, :]
        z = np.arange(self.z0, self.z0 + self.depth, dtype=np.int64)[:, None]
        return x, z

    def tiles(self, tile_size, *, reverse=False):
        require_int("tile_size", tile_size, 1, 4096)
        nx = (self.width + tile_size - 1) // tile_size
        nz = (self.depth + tile_size - 1) // tile_size
        indices = range(nx * nz - 1, -1, -1) if reverse else range(nx * nz)
        for index in indices:
            iz, ix = divmod(index, nx)
            dx, dz = ix * tile_size, iz * tile_size
            yield Region(self.x0 + dx, self.z0 + dz,
                         min(tile_size, self.width - dx), min(tile_size, self.depth - dz))

    def expanded(self, halo=1):
        require_int("halo", halo, 0, 4096)
        return Region(self.x0 - halo, self.z0 - halo,
                      self.width + 2 * halo, self.depth + 2 * halo)

    def slices(self, inner):
        """Index `inner` (fully contained) inside arrays shaped like this region."""
        dz, dx = inner.z0 - self.z0, inner.x0 - self.x0
        if dx < 0 or dz < 0 or dx + inner.width > self.width or dz + inner.depth > self.depth:
            raise ValueError("inner region is not contained")
        return slice(dz, dz + inner.depth), slice(dx, dx + inner.width)

    def to_list(self):
        return [self.x0, self.z0, self.width, self.depth]
