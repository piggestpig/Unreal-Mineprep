"""Explicit one-time JSON upgrade. Runtime loaders never interpret legacy features."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import shutil
import uuid
import tempfile

from .storage import write_json

PLACEMENT_KEYS = ('surface', 'density', 'patch_scale', 'max_slope', 'enabled_param')


def upgrade_content(data):
    """Convert an effective rules snapshot, preserving explicit values and biome order."""
    result = deepcopy(data)
    biomes = result.get('biomes', [])
    if isinstance(biomes, dict):
        biomes = list(biomes.values())
    for biome in biomes:
        biome.setdefault('features', {})
    for name, feature in result.get('features', {}).items():
        if 'biomes' not in feature:
            continue
        targets = feature.pop('biomes')
        if not isinstance(targets, list) or any(not isinstance(n, str) for n in targets):
            raise ValueError(f'feature {name}: cannot migrate invalid biomes')
        if set(targets) - {b['id'] for b in biomes}:
            raise ValueError(f'feature {name}: cannot migrate unknown biomes')
        placement = {k: feature.pop(k) for k in PLACEMENT_KEYS if k in feature}
        if not {'surface', 'density', 'patch_scale', 'max_slope'} <= placement.keys():
            raise ValueError(f'feature {name}: incomplete legacy placement')
        if feature['type'] == 'surface_scatter':
            placement.setdefault('enabled_param', 'vegetation.enabled')
        feature.setdefault('category', (placement.get('enabled_param') or 'features').split('.')[0])
        for biome in biomes:
            biome['features'].pop(name, None)
            if biome['id'] in targets:
                biome['features'][name] = deepcopy(placement)
    result['biomes'] = biomes
    if result.get('water'):
        result['water'].setdefault('generate_param', 'water.generate')
        result['water'].setdefault('enabled_param', 'water.enabled')
    result['format_version'] = 2
    return result


def _publish(changes, backup_root):
    """Back up before publishing; restore all originals if any write fails."""
    originals = {path: path.read_bytes() if path.exists() else None for path in changes}
    backup = Path(backup_root) / (datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    backup.mkdir(parents=True)
    manifest = []
    for i, (path, content) in enumerate(originals.items()):
        name = f'{i:04d}.json'
        if content is not None:
            (backup/name).write_bytes(content)
        manifest.append(dict(path=str(path.resolve()), backup=name if content is not None else None))
    write_json(backup/'files.json', manifest)
    staging = backup/'staging'
    staging.mkdir()
    for i, (path, value) in enumerate(changes.items()):
        write_json(staging/f'{i:04d}.json', value)
    published = []
    try:
        for i, path in enumerate(changes):
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(staging/f'{i:04d}.json', path.with_suffix('.upgrade.tmp'))
            path.with_suffix('.upgrade.tmp').replace(path)
            published.append(path)
    except BaseException:
        for path in reversed(published):
            if originals[path] is None:
                path.unlink()
            else:
                path.write_bytes(originals[path])
        raise
    return str(backup)


def upgrade_pack(directory, *, roots, backup_root):
    """Resolve legacy inheritance as raw JSON, then publish only changed own files."""
    directory = Path(directory)
    def read(path):
        return json.loads(path.read_text(encoding='utf8'))
    own = read(directory/'pack.json')
    if own.get('format_version') == 2:
        return None
    def effective(folder, seen=()):
        manifest = read(folder/'pack.json')
        name = manifest['id']
        if name in seen:
            raise ValueError('pack extends cycle during migration')
        result = dict(biomes={}, features={}, params={})
        base = manifest.get('extends')
        if base:
            candidates = [Path(root)/base for root in roots if (Path(root)/base/'pack.json').is_file()]
            if not candidates:
                raise ValueError(f'missing migration base {base}')
            result = effective(candidates[0], (*seen, name))
        for p in (folder/'biomes').glob('*.json'):
            biome = read(p)
            if 'features' not in biome and manifest.get('format_version') != 2:
                biome['features'] = deepcopy(result['biomes'].get(p.stem, {}).get('features', {}))
            result['biomes'][p.stem] = biome
        if (folder/'features.json').is_file():
            result['features'].update(read(folder/'features.json'))
        result['params'].update(manifest.get('params', {}))
        return result
    raw = effective(directory)
    for name, f in raw['features'].items():
        unknown = set(f.get('biomes', ())) - raw['biomes'].keys()
        if unknown:
            raise ValueError(f'feature {name}: unknown legacy biomes {sorted(unknown)}')
    converted = upgrade_content(raw)
    own['format_version'] = 2
    if own.get('water'):
        for key, param in (('generate_param','water.generate'),('enabled_param','water.enabled')):
            if param in raw['params']:
                own['water'].setdefault(key,param)
    changes = {directory/'pack.json': own}
    feature_path = directory/'features.json'
    own_features = read(feature_path) if feature_path.exists() else {}
    affected = {n for n, f in own_features.items() if 'biomes' in f}
    for b in converted['biomes']:
        old = raw['biomes'][b['id']]
        path = directory/'biomes'/(b['id']+'.json')
        if (path.exists() and b != read(path) or affected and
                any(n in old.get('features', {}) or b['id'] in own_features[n]['biomes'] for n in affected)):
            changes[directory/'biomes'/(b['id']+'.json')] = b
    if feature_path.exists():
        names = read(feature_path)
        changes[feature_path] = {n: converted['features'][n] for n in names}
    from .core.pack import load_pack
    Path(backup_root).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=backup_root, prefix='validate-') as temporary:
        staged = Path(temporary)/directory.name
        shutil.copytree(directory, staged, ignore=shutil.ignore_patterns('__pycache__'))
        for path, value in changes.items():
            write_json(staged/path.relative_to(directory), value)
        load_pack(own['id'], roots=(temporary, *roots))
    return _publish(changes, backup_root)


def upgrade_workspace(workspace, *, roots):
    """Only active user packs, drafts and session; no historical Saved traversal."""
    workspace = Path(workspace)
    report = dict(upgraded=[], errors=[])
    all_roots = (workspace/'packs', workspace/'drafts', *map(Path, roots))
    pending = [p for root in all_roots[:2] for p in sorted(root.glob('*/pack.json'))]
    visited = set()
    def upgrade(manifest, visiting=()):
        if manifest in visited:
            return
        if manifest in visiting:
            raise ValueError('pack extends cycle during migration')
        value = json.loads(manifest.read_text(encoding='utf8'))
        base = value.get('extends')
        if base:
            parent = next((Path(r)/base/'pack.json' for r in all_roots
                           if (Path(r)/base/'pack.json').is_file()), None)
            if parent in pending:
                upgrade(parent, (*visiting, manifest))
        backup = upgrade_pack(manifest.parent, roots=all_roots, backup_root=workspace/'migrations')
        visited.add(manifest)
        if backup:
            report['upgraded'].append(dict(pack=manifest.parent.name, backup=backup))
    for manifest in pending:
        try:
            upgrade(manifest)
        except Exception as exc:
            report['errors'].append(dict(path=str(manifest), error=str(exc)))
    path = workspace/'session.json'
    if path.exists():
        try:
            session = json.loads(path.read_text(encoding='utf8'))
            if session.get('format_version') != 2:
                session['data'] = upgrade_content(session['data'])
                session['data'].pop('format_version', None)
                session['format_version'] = 2
                from .core.pack import load_pack
                session['fingerprint'] = load_pack(session['pack'], roots=all_roots).fingerprint
                report['upgraded'].append(dict(session=str(path), backup=_publish({path: session}, workspace/'migrations')))
        except Exception as exc:
            report['errors'].append(dict(path=str(path), error=str(exc)))
    # Convert display-page aliases and library schemas once, using each pack's
    # metadata. Parameter values and local preset membership remain unchanged.
    from .core.pack import load_pack
    from .core.ui_metadata import section_id
    candidates = [(workspace/'preferences.json', 'preferences')]
    candidates += [(p, 'preset') for p in sorted((workspace/'presets').glob('*.json'))]
    for path, kind in candidates:
        if not path.exists():
            continue
        try:
            value = json.loads(path.read_text(encoding='utf8'))
            if value.get('content_format') == 2:
                continue
            pack = load_pack(value.get('pack', 'vanilla'), roots=all_roots)
            if kind == 'preferences':
                value['page'] = section_id(value.get('page', 'world'), pack.ui_sections)
                if value['page'] == 'seabed_water':
                    value['page'] = 'water'
            else:
                if value.get('section'):
                    value['section'] = section_id(value['section'], pack.ui_sections)
                for definition in value.get('definitions', {}).values():
                    definition['page'] = section_id(definition['page'], pack.ui_sections)
            # Library validation is intentionally strict; keep its public keys.
            if kind == 'preferences':
                value['content_format'] = 2
            original = json.loads(path.read_text(encoding='utf8'))
            if value != original:
                report['upgraded'].append(dict(path=str(path), backup=_publish({path:value}, workspace/'migrations')))
        except Exception as exc:
            report['errors'].append(dict(path=str(path), error=str(exc)))
    return report
