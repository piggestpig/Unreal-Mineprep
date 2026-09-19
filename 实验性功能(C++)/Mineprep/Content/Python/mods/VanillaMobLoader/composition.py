"""Pure template composition, naming, identities and rigid bone remapping."""
from collections import Counter
from dataclasses import replace
import hashlib
import json
import math
import re
from .geometry import MeshData, build_geometry
from .skin import alpha_reader


def clean_name(value):
    return re.sub(r'[^a-zA-Z0-9_]', '_', str(value)).strip('_')[:96]


def automatic_name(entries):
    seen, words = set(), []
    for entry in entries:
        for word in clean_name(entry.id).split('_'):
            words.append('' if word in seen else word)
            seen.add(word)
    return '_'.join(words).strip('_')[:96]


def destination(path, name):
    path = str(path).strip().rstrip('/')
    if not re.fullmatch(r'/Game(?:/[a-zA-Z0-9_]+)*', path):
        raise ValueError('保存路径必须为合法 /Game/... 路径 / Invalid /Game path')
    name = clean_name(name)
    if not name:
        raise ValueError('保存名称不能为空 / Save name is empty')
    return path+'/'+name, name


def recipe(entries, expansion, random_scale=0.):
    if not math.isfinite(expansion) or expansion < 0:
        raise ValueError('Invalid expansion')
    if not math.isfinite(random_scale) or random_scale < 0:
        raise ValueError('Invalid random scale')
    if len(entries) == 1 and random_scale == 0:
        return entries[0].key
    payload = {'entries':[e.key for e in entries], 'expansion':round(expansion,8)}
    if random_scale:
        payload['random'] = round(random_scale, 8)
    return json.dumps(payload, separators=(',',':'))


def aggregate_entry(entries, name, expansion, random_scale=0.):
    return replace(entries[0], id=name, name=' + '.join(e.name for e in entries),
                   key=recipe(entries, expansion, random_scale), model=' + '.join(e.model for e in entries))


def combine(entries, models, skins, expansion, random_scale=0.):
    """First occurrence owns each bone. Caller must approve returned conflicts."""
    recipe(entries, expansion, random_scale)
    if not entries or len(entries) != len(models) or len(entries) != len(skins):
        raise ValueError('Composition requires one model and skin per selection')
    out, conflicts, bones, slots = MeshData(), [], {}, {}
    for source, (entry,model,raw) in enumerate(zip(entries,models,skins)):
        geo = build_geometry(model, alpha_reader(raw) if raw else None, source*expansion, random_scale)
        counts = Counter(p['name'].casefold() for p in geo.parts)
        paths, occurrences, remap = {}, {}, {}
        for i,part in enumerate(geo.parts):
            parent = remap.get(part['parent'], -1)
            leaf = part['name'].casefold()
            path = paths.get(part['parent'], ()) + (leaf,)
            paths[i] = path
            # A duplicated name inside one source must never collapse.
            identity = ('name',leaf) if counts[leaf] == 1 else ('path',path)
            occurrence = occurrences.get(identity, 0)
            occurrences[identity] = occurrence+1
            identity = (identity,occurrence)
            if identity in bones:
                target = bones[identity]
                canonical = out.parts[target]
                same_matrix = all(abs(a-b)<1e-5 for ar,br in zip(canonical['matrix'],part['matrix']) for a,b in zip(ar,br))
                if parent != canonical['parent'] or not same_matrix:
                    conflicts.append(entry.name+': '+part['name'])
            else:
                target = len(out.parts)
                bones[identity] = target
                out.parts.append(dict(part, parent=parent))
            remap[i] = target
        digest = hashlib.sha256(raw).hexdigest() if raw else 'neutral'
        material_key = digest
        if material_key not in slots:
            slots[material_key] = len(out.materials)
            out.materials.append(dict(source=source, digest=digest, single_sided=False))
        slot = slots[material_key]
        base = len(out.vertices)
        out.vertices.extend(geo.vertices)
        out.uv.extend(geo.uv)
        out.normals.extend(geo.normals)
        out.vertex_parts.extend(remap[p] for p in geo.vertex_parts)
        out.triangles.extend(tuple(base+i for i in tri) for tri in geo.triangles)
        out.groups.extend(remap[p] for p in geo.groups)
        out.triangle_materials.extend([slot]*len(geo.triangles))
        out.warnings.extend(geo.warnings)
    out.warnings = list(dict.fromkeys(out.warnings))
    return out, list(dict.fromkeys(conflicts))
