"""Small offline author tools built on the pack loader and reference snapshots."""
import math
import os
import re
from pathlib import Path
import tempfile
from time import perf_counter
from collections.abc import Mapping

import numpy as np

from .core import pack as packs
from .core.data import GenerationCancelled
from .core.features import enabled
from .core.spec import WorldSpec
from .core.world import Overview, World
from .storage import SAVED_DIR, write_json


def biome_order(pack_id='vanilla', *, insert=(), before=None, after=None):
    """Copy the resolved order without writing files or activating new IDs."""
    order = [b.id for b in packs.load_pack(pack_id).biomes]
    if not isinstance(insert, (str, list, tuple)):
        raise TypeError('insert must be a biome ID or a list/tuple of IDs')
    additions = [insert] if isinstance(insert, str) else list(insert)
    if any(not isinstance(n, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', n) for n in additions):
        raise ValueError('insert must contain valid biome IDs')
    if len(set(additions)) != len(additions) or set(additions) & set(order):
        raise ValueError('insert contains duplicate or already active biome IDs')
    if not additions:
        if before is not None or after is not None:
            raise ValueError('an anchor requires nonempty insert')
        return order
    if (before is None) == (after is None):
        raise ValueError('insert requires exactly one of before or after')
    anchor = before if before is not None else after
    if not isinstance(anchor, str) or anchor not in order:
        raise ValueError(f'unknown biome anchor: {anchor!r}')
    index = order.index(anchor) + (after is not None)
    order[index:index] = additions
    return order


def create_pack(pack_id, *, extends='vanilla', root=None, name=None):
    # WorldSpec enforces the same ID grammar as the loader (including no paths).
    request = WorldSpec(pack_id)
    WorldSpec(extends)
    if name is not None and (not isinstance(name, str) or not name.strip()):
        raise ValueError('name must be a nonempty string')
    root = (SAVED_DIR / 'packs' if root is None else Path(root)).resolve()
    target = root / pack_id
    roots = packs.pack_roots()
    parent = packs.load_pack(extends, roots=roots)
    with packs._lock:
        if any((Path(r) / pack_id / 'pack.json').is_file() for r in roots) or target.exists():
            raise FileExistsError(f'pack already exists: {pack_id}')
    # Registration puts this root first. Validate the actual future parent too.
    future_roots = (str(root), *roots)
    if packs.load_pack(extends, roots=future_roots).fingerprint != parent.fingerprint:
        raise ValueError('root would shadow the selected parent pack')
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.create-', dir=root) as staging:
        draft = Path(staging) / pack_id
        draft.mkdir()
        write_json(draft / 'pack.json', dict(format_version=2, id=pack_id,
                   name=name or pack_id, extends=extends, modules=['landscape']))
        (draft / 'landscape.py').write_text('', encoding='utf-8')
        (draft / 'README.md').write_text(
            f'# {name or pack_id}\n\nInherits `{extends}` without changing its output.\n\n'
            'This interpreter has registered the parent directory. In a new interpreter:\n\n'
            '```python\nfrom mods.WorldGenerator import api\n'
            f'api.register_pack_root({str(root)!r})\n'
            f'spec = api.spec({pack_id!r})\n'
            'data = api.overview(spec)\nprint(api.check(data))\n```\n\n'
            'Use Python 3.11 with NumPy; image output also needs OpenCV (cv2). '
            'Add the plugin Python directory and project Intermediate/PipInstall/Lib/site-packages '
            'to PYTHONPATH; verify imports before generating.\n\n'
            'Add Python fields to landscape.py (already in modules). Add biomes/ID.json, '
            'features.json and blocks.json only when the content needs them. New biome files '
            'must enter the explicit pack.json.biomes list:\n\n'
            '```python\n'
            f'order = api.biome_order({extends!r}, insert="my_biome", before={parent.biomes[-1].id!r})\n'
            '# Write order to pack.json.biomes and create biomes/my_biome.json.\n'
            'print(api.describe(spec.pack)["inactive_biomes"])\n'
            'data = api.overview(spec)\nprint(api.check(data))\n'
            '# api.locate(data, biome="my_biome") reuses this snapshot.\n'
            '# Generate a small World only when checking actual trees/grass.\n```\n\n'
            'Choose an anchor whose priority fits your climate rules. '
            'Pack.blocks is a name tuple; block_defs is the definition mapping. Prefer api.describe(). '
            'Climate intervals are closed; surface and locate upper bounds are exclusive. '
            'Keep reports outside the pack directory: Python/JSON files affect its fingerprint. '
            'Do not copy planning_params: inherited packs invalidate conservatively.\n\n'
            'Full instructions: WorldGenerator/README.md and docs/CONTENT_PACK_GUIDE.md.\n',
            encoding='utf-8')
        packs.load_pack(pack_id, roots=(staging, *future_roots)).resolve(request)
        # Serialize publication with registrations. Recheck after staging work.
        with packs._lock:
            current_roots = packs.pack_roots()
            if any((Path(r) / pack_id / 'pack.json').is_file() for r in current_roots) or target.exists():
                raise FileExistsError(f'pack already exists: {pack_id}')
            if packs.load_pack(extends, roots=(str(root), *current_roots)).fingerprint != parent.fingerprint:
                raise packs.PackChangedError()
            os.rename(draft, target)
            packs.register_pack_root(root)
    return target


def _source(source, options, *, full=False):
    if isinstance(source, WorldSpec):
        from . import api
        return api.generate(source, **options) if full else api.overview(source, **options)
    if not isinstance(source, (World, Overview)):
        raise TypeError('source must be a WorldSpec, Overview or World')
    if options:
        raise TypeError('generation options are only accepted with a WorldSpec')
    if full and isinstance(source, Overview):
        raise ValueError('full checking requires a World or WorldSpec; use the original Spec')
    return source


def _ids(values):
    values = (values,) if isinstance(values, str) else tuple(values)
    if any(not isinstance(value, str) for value in values):
        raise TypeError('expected IDs must be strings')
    return tuple(dict.fromkeys(values))


def check(source, *, full=False, expect_biomes=(), expect_features=(), **options):
    if type(full) is not bool:
        raise TypeError('full must be a bool')
    if not isinstance(source, (WorldSpec, World, Overview)):
        raise TypeError('source must be a WorldSpec, Overview or World')
    if not isinstance(source, WorldSpec):
        _source(source, options, full=full)  # Invalid reuse requests are caller errors.
    wanted_biomes, wanted_features = _ids(expect_biomes), _ids(expect_features)
    spec = source if isinstance(source, WorldSpec) else source.spec
    start = perf_counter()
    report = dict(ok=False, scope='full' if full or isinstance(source, World) else 'reference',
                  pack=spec.pack, fingerprint=None, seed=spec.seed,
                  region=spec.region.to_list(), terrain={}, biomes={}, features={},
                  inactive_biomes=[], errors=[], warnings=[])
    try:
        data = _source(source, options, full=full)
        p = data.pack
        report['fingerprint'] = p.fingerprint
        report['inactive_biomes'] = list(p.inactive_biomes)
        for key in p.inactive_biomes:
            report['warnings'].append(f'biome {key}: local file excluded from pack.json.biomes')
        heights = data.heights
        report['terrain'] = dict(min=float(heights.min()), max=float(heights.max()),
                                 mean=float(heights.mean()), cells=int(heights.size),
                                 wet_cells=int(np.count_nonzero(data.wet_mask)))
        report['biomes'] = {key: float(value) for key, value in data.biome_fractions().items()}
        counts = data.stats.get('feature_counts', {})
        unsupported = data.stats.get('feature_unsupported', ())
        for definition in p.feature_defs:
            bindings = [f for f in p.features if f.id == definition.id]
            active = any(enabled(f, data.params) and
                         (data.params[f.density[1:]] if isinstance(f.density, str) else f.density) > 0
                         for f in bindings)
            actual = isinstance(data, World)
            count = counts.get(definition.id, {})
            cells = int(count.get('cells', 0)) if actual else None
            instances = int(count.get('instances', 0)) if actual else None
            status = ('disabled' if not active else 'not_sampled' if not actual else
                      'present' if cells or instances else 'not_observed')
            report['features'][definition.id] = dict(status=status, enabled=active,
                cells=cells, instances=instances, unsupported=definition.id in unsupported)
        for kind, wanted in (('biomes', wanted_biomes), ('features', wanted_features)):
            for key in wanted:
                if key not in report[kind]:
                    if kind == 'biomes' and key in p.inactive_biomes:
                        report['errors'].append(f'biome {key}: defined locally but missing from pack.json.biomes')
                    else:
                        report['errors'].append(f'unknown {kind} ID: {key}')
                elif kind == 'biomes' and not report[kind][key]:
                    report['warnings'].append(f'biome {key}: not observed in this region')
                elif kind == 'features' and report[kind][key]['status'] != 'present':
                    report['warnings'].append(f"feature {key}: {report[kind][key]['status']} in this region")
        report['ok'] = not report['errors']
    except (GenerationCancelled, packs.PackChangedError):
        raise
    except Exception as exc:
        report['errors'].append(f'{type(exc).__name__}: {exc}')
    report['seconds'] = perf_counter() - start
    return report


def _number(value, label):
    if (isinstance(value, (bool, np.bool_)) or np.iscomplexobj(value) or
            not isinstance(value, (int, float, np.number))):
        raise ValueError(f'{label} must be a finite real number')
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{label} must be a finite real number') from exc
    if not math.isfinite(result):
        raise ValueError(f'{label} must be a finite real number')
    return result


def locate(source, *, biome=None, where=None, origin=None, **options):
    if biome is None and not where:
        raise ValueError('specify biome or where')
    if biome is not None and not isinstance(biome, str):
        raise ValueError('biome must be one biome ID')
    if where is None:
        where = {}
    if not isinstance(where, Mapping):
        raise ValueError('where must map field names to min/max conditions')
    conditions = {}
    for name, bounds in where.items():
        if not isinstance(name, str) or not isinstance(bounds, Mapping) or not bounds or set(bounds) - {'min', 'max'}:
            raise ValueError('where requires field: {min: number, max: number}; bounds are optional')
        conditions[name] = {key: _number(value, f'{name}.{key}') for key, value in bounds.items()}
        if 'min' in bounds and 'max' in bounds and conditions[name]['min'] >= conditions[name]['max']:
            raise ValueError(f'{name}: min must be less than max')
    if not isinstance(source, (WorldSpec, Overview, World)):
        raise TypeError('source must be a WorldSpec, Overview or World')
    p = packs.load_pack(source.pack) if isinstance(source, WorldSpec) else source.pack
    biome_names = [b.id for b in p.biomes]
    if biome is not None and biome not in biome_names:
        raise ValueError(f'unknown biome ID: {biome}')
    required = tuple(name for name in conditions if name != 'height')
    for name in required:
        if name not in p.fields:
            raise ValueError(f'unknown field: {name}')
    region = source.region
    if origin is None:
        origin = (region.x0 + (region.width - 1) / 2, region.z0 + (region.depth - 1) / 2)
    if not isinstance(origin, (tuple, list)) or len(origin) != 2:
        raise ValueError('origin must be an MC (X, Z) pair')
    ox, oz = (_number(v, 'origin') for v in origin)
    if isinstance(source, WorldSpec):
        from .api import _field_names
        retained = tuple(_field_names(options.get('keep_fields', ())))
        options['keep_fields'] = tuple(dict.fromkeys((*retained, *required)))
    data = _source(source, options)
    # A source edit during generation must not mix the preflight and result IDs.
    if isinstance(source, WorldSpec) and data.pack.fingerprint != p.fingerprint:
        raise packs.PackChangedError()
    mask = np.ones(region.shape, dtype=bool)
    if biome is not None:
        mask &= data.biome_ids == biome_names.index(biome)
    for name, bounds in conditions.items():
        if name != 'height' and name not in data.fields:
            raise ValueError(f'field {name!r} was not retained; request keep_fields={required!r} with the original Spec')
        values = data.heights if name == 'height' else data.fields[name]
        if not np.issubdtype(values.dtype, np.number) or np.iscomplexobj(values):
            raise ValueError(f'field {name!r} must be numeric')
        mask &= np.isfinite(values)
        if 'min' in bounds:
            mask &= values >= bounds['min']
        if 'max' in bounds:
            mask &= values < bounds['max']
    iz, ix = np.nonzero(mask)
    if not len(ix):
        return None
    x, z = ix + region.x0, iz + region.z0
    distances = (x.astype(np.float64) - ox) ** 2 + (z.astype(np.float64) - oz) ** 2
    tied = np.flatnonzero(distances == distances.min())
    winner = tied[np.lexsort((z[tied], x[tied]))[0]]
    row, col = iz[winner], ix[winner]
    return dict(x=int(x[winner]), z=int(z[winner]), height=float(data.heights[row, col]),
                biome=data.pack.biomes[int(data.biome_ids[row, col])].id,
                distance=float(math.sqrt(distances[winner])), reference=True)
