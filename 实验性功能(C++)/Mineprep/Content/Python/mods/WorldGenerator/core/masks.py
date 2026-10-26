"""Request-local distribution images and exact horizontal scenery clearance.

Reuse heightmap file snapshots/decoding; masks never enter terrain planning.
"""
from dataclasses import dataclass, replace
import numpy as np

from .heightmap import capture, decoded, input_key

KINDS = ('vegetation', 'clearance')


@dataclass(frozen=True)
class Mask:
    config: object
    source: object
    values: np.ndarray
    kind: str

    def sample(self, x, z):
        x, z = np.broadcast_arrays(x, z)
        r, a = self.config.region, self.values
        inside = (x >= r.x0) & (x < r.x0+r.width) & (z >= r.z0) & (z < r.z0+r.depth)
        u = np.clip((x+.5-r.x0)*a.shape[1]/r.width-.5, 0, a.shape[1]-1)
        v = np.clip((z+.5-r.z0)*a.shape[0]/r.depth-.5, 0, a.shape[0]-1)
        if self.kind == 'clearance':
            value = a[np.floor(v+.5).astype(np.intp), np.floor(u+.5).astype(np.intp)]
        else:
            ix, iz = u.astype(np.intp), v.astype(np.intp)
            fx, fz = u-ix, v-iz
            right, bottom = np.minimum(ix+1, a.shape[1]-1), np.minimum(iz+1, a.shape[0]-1)
            value = ((a[iz, ix]*(1-fx)+a[iz, right]*fx)*(1-fz)
                     + (a[bottom, ix]*(1-fx)+a[bottom, right]*fx)*fz)
        return np.where(inside, value, 1. if self.kind == 'vegetation' else 0.)


def sources(spec, *, cancel_event=None):
    return {kind: capture(getattr(spec, kind+'_mask'), cancel_event=cancel_event)
            for kind in KINDS if getattr(spec, kind+'_mask') is not None}


def keys(spec, inputs):
    return {kind: input_key(getattr(spec, kind+'_mask'), source) for kind, source in inputs.items()}


def bind(pack, spec, inputs):
    masks = {}
    for kind, source in inputs.items():
        image = decoded(source)
        if np.any((image.values < 0) | (image.values > 1)):
            raise ValueError(f'{kind} mask pixels must be in [0,1]')
        masks[kind] = Mask(getattr(spec, kind+'_mask'), source, image.values, kind)
    return replace(pack, masks=masks)


def active(pack, kind, category):
    return kind in (pack.masks or {}) and category in (pack.mask_categories or {}).get(kind, ())


def blocked(pack, category, x, z):
    return pack.masks['clearance'].sample(x, z) >= .5 if active(pack, 'clearance', category) else False


def weight(pack, category, x, z):
    value = pack.masks['vegetation'].sample(x, z) if active(pack, 'vegetation', category) else 1.
    return value * np.logical_not(blocked(pack, category, x, z))


def rejected(pack, category, batch, roots):
    """Reject whole owners by occupied columns, never their bounding rectangles."""
    if not active(pack, 'clearance', category):
        return np.empty(0, np.intp)
    from .templates import TemplateBatch
    if isinstance(batch, TemplateBatch):
        bad = []
        for template, rotation, owner in zip(batch.template_ids, batch.rotations, batch.owners):
            xz = batch.templates[int(template)].orientations[int(rotation)][1] + roots[owner, [0, 2]]
            if blocked(pack, category, xz[:, 0], xz[:, 1]).any():
                bad.append(owner)
        return np.asarray(bad, np.intp)
    p = roots[batch.owners] + batch.offsets
    return np.unique(batch.owners[blocked(pack, category, p[:, 0], p[:, 2])])


def check_sources(pack, *, full=False):
    for mask in (pack.masks or {}).values():
        mask.source.checked(full=full)
