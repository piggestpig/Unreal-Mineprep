"""Low-poly recipes: UE XYZ, Z up, one length unit = 100 cm.

Recipes hold shared geometry sources, local group poses and numeric instance
arrays. No Unreal objects are created until spawn/update. Polygon geometry can
join the source resolver later without changing the group or output contracts.
"""
from dataclasses import dataclass
from hashlib import sha256
from uuid import uuid4
import re

import numpy as np

try:
    import unreal
except ModuleNotFoundError:
    unreal = None


COLOR_MATERIAL = '/Game/Mineprep/材质/Core/纯色实例材质'
_CACHE_ROOT = '/Game/mc/LowPoly'
_OWNER = 'Mineprep.LowPoly.Owner:'
_GROUP = 'Mineprep.LowPoly.Group:'
_ROOT = 'Mineprep.LowPoly.Root.v2:'
_RECIPE = 'Mineprep.LowPoly.Geometry'
_DEFAULTS = np.array([1, 1, 1, 1, 0, .5, .65, 0], dtype=np.float32)


def _numbers(value, label):
    result = np.asarray(value, dtype=np.float64)
    if not np.isfinite(result).all():
        raise ValueError(f'{label} must contain finite numbers')
    return result


def _xyz(value, label, *, positive=False):
    result = np.broadcast_to(_numbers(value, label), (3,)).copy()
    if positive and np.any(result <= 0):
        raise ValueError(f'{label} must be positive')
    return result


def _array(value, shape, label, *, positive=False):
    result = np.broadcast_to(_numbers(value, label), shape).copy()
    if positive and np.any(result <= 0):
        raise ValueError(f'{label} must be positive')
    return result


def _appearance(count, color, metallic, specular, roughness, emissive):
    values = np.broadcast_to(_DEFAULTS, (count, 8)).copy()
    if color is not None:
        if isinstance(color, str):
            text = color.removeprefix('#')
            if len(text) not in (6, 8):
                raise ValueError('color requires #RRGGBB or #RRGGBBAA')
            color = [int(text[i:i+2], 16) / 255 for i in range(0, len(text), 2)]
        rgb = _numbers(color, 'color')
        if rgb.ndim == 0 or rgb.shape[-1] not in (3, 4) or np.any((rgb < 0) | (rgb > 1)):
            raise ValueError('color requires sRGB(A) values in 0..1')
        width = rgb.shape[-1]
        values[:, :width] = np.broadcast_to(rgb, (count, width))
        srgb = values[:, :3]
        values[:, :3] = np.where(srgb <= .04045, srgb / 12.92, ((srgb + .055) / 1.055) ** 2.4)
    for index, label, value in ((4, 'metallic', metallic), (5, 'specular', specular),
                                (6, 'roughness', roughness), (7, 'emissive', emissive)):
        if value is not None:
            data = _array(value, (count,), label)
            if np.any(data < 0) or (index != 7 and np.any(data > 1)):
                raise ValueError(f'{label} is outside its supported range')
            values[:, index] = data
    if not np.isfinite(values).all():
        raise ValueError('appearance exceeds float32 range')
    return values


@dataclass(frozen=True)
class _Source:
    kind: str
    value: object


@dataclass
class _Part:
    source: _Source
    positions: np.ndarray
    angles: np.ndarray                 # pitch, yaw, roll; degrees
    scales: np.ndarray
    values: np.ndarray                 # linear RGBA, metallic, specular, roughness, emissive
    material: object
    colored: bool


class _Group:
    def __init__(self, name='Model', pivot=(0, 0, 0), *, pitch=0, yaw=0, roll=0, scale=1):
        self.name = str(name)
        if not self.name or '/' in self.name:
            raise ValueError('group names must be nonempty and cannot contain /')
        self.pivot = tuple(_xyz(pivot, 'pivot'))
        self.pitch, self.yaw, self.roll = map(float, _numbers((pitch, yaw, roll), 'rotation'))
        self.scale = tuple(_xyz(scale, 'scale', positive=True))
        self.groups = {}
        self._parts = []

    def group(self, name, pivot=(0, 0, 0), *, pitch=0, yaw=0, roll=0, scale=1):
        """Create a named child; its pivot is in this group's local coordinates."""
        name = str(name)
        if name in self.groups:
            raise ValueError(f'duplicate group: {name}')
        child = _Group(name, pivot, pitch=pitch, yaw=yaw, roll=roll, scale=scale)
        self.groups[child.name] = child
        return child

    def clear(self):
        """Clear this group's recipe, without touching any placed output."""
        self._parts.clear()
        self.groups.clear()
        return self

    def add(self, source, position=(0, 0, 0), *, scale=1, pitch=0, yaw=0, roll=0,
            color=None, material=None, metallic=None, specular=None, roughness=None, emissive=None, pivot=None):
        """Add an asset or MC model at its original pivot. Scale is dimensionless."""
        return self.add_many(source, [_xyz(position, 'position')], scale=scale,
                             pitch=pitch, yaw=yaw, roll=roll, color=color, material=material,
                             metallic=metallic, specular=specular, roughness=roughness, emissive=emissive, pivot=pivot)

    def add_many(self, source, positions, *, scale=1, pitch=0, yaw=0, roll=0,
                 color=None, material=None, metallic=None, specular=None, roughness=None, emissive=None, pivot=None):
        """Append numeric arrays; positions [N,3], scale scalar/XYZ/[N,3], angles scalar/[N]."""
        points = _numbers(positions, 'positions')
        if points.ndim != 2 or points.shape[1] != 3:
            raise ValueError('positions requires [N,3], including for empty input')
        count = len(points)
        scales = _array(scale, (count, 3), 'scale', positive=True)
        angles = np.column_stack([_array(v, (count,), k) for k, v in
                                  (('pitch', pitch), ('yaw', yaw), ('roll', roll))])
        if pivot is not None:
            origin = _array(pivot, (count, 3), 'pivot')
            # UE Rotator quaternion, vectorized; scaling stays about each mesh's origin.
            sp, sy, sr = np.sin(np.radians(angles / 2)).T
            cp, cy, cr = np.cos(np.radians(angles / 2)).T
            q = np.column_stack((cr*sp*sy-sr*cp*cy, -cr*sp*cy-sr*cp*sy,
                                 cr*cp*sy-sr*sp*cy))
            w = cr*cp*cy+sr*sp*sy
            delta = points-origin
            cross = 2*np.cross(q, delta)
            points = origin+delta+w[:, None]*cross+np.cross(q, cross)
        colored = any(v is not None for v in (color, metallic, specular, roughness, emissive))
        if material is not None and colored:
            raise ValueError('material and color/surface overrides are mutually exclusive')
        values = _appearance(count, color, metallic, specular, roughness, emissive)
        source = source if isinstance(source, _Source) else _Source('asset', source)
        if count:
            self._parts.append(_Part(source, points.copy(), angles, scales, values, material, colored))
        return self

    def box(self, position=None, size=None, *, bounds=None, **options):
        """Centered solid box; size is a length or XYZ lengths in model units."""
        if bounds is not None:
            if position is not None or size is not None:
                raise ValueError('bounds is exclusive with position/size')
            low, high = _array(bounds, (2, 3), 'bounds')
            position, size = (low+high)/2, high-low
        else:
            position = (0, 0, 0) if position is None else position
            size = 1 if size is None else size
        options.setdefault('color', '#ffffff' if options.get('material') is None else None)
        return self.add(_Source('box', 0), position, scale=_xyz(size, 'size', positive=True), **options)

    def cylinder(self, position=(0, 0, 0), radius=.5, height=1, segments=8, **options):
        return self._round('cylinder', position, radius, height, segments, options)

    def cone(self, position=(0, 0, 0), radius=.5, height=1, segments=8, **options):
        return self._round('cone', position, radius, height, segments, options)

    def frustum(self, position=(0, 0, 0), radius=.5, top_radius=.25, height=1, segments=8, **options):
        """Centered capped frustum; radius is the bottom radius, top may be zero."""
        top = float(_numbers(top_radius, 'top_radius'))
        if top < 0:
            raise ValueError('top_radius must be nonnegative')
        return self._round('frustum', position, radius, height, segments, options, top)

    def _round(self, kind, position, radius, height, segments, options, top=None):
        if type(segments) is not int or not 3 <= segments <= 256:
            raise ValueError('segments must be an integer in 3..256')
        size = _xyz((2 * radius, 2 * radius, height), 'dimensions', positive=True)
        options.setdefault('color', '#ffffff' if options.get('material') is None else None)
        value = segments if top is None else (segments, float(top / radius).hex())
        return self.add(_Source(kind, value), position, scale=size, **options)

    def _walk(self, path=''):
        yield path, self
        for name, child in self.groups.items():
            yield from child._walk(f'{path}/{name}' if path else name)


def _ue():
    if unreal is None:
        raise RuntimeError('LowPolyModel placement requires Unreal Editor')
    return unreal


def _transform(position, angles=(0, 0, 0), scale=1):
    ue = _ue()
    point = _xyz(position, 'position') * 100
    pitch, yaw, roll = _numbers(angles, 'rotation')
    return ue.Transform(location=ue.Vector(*map(float, point)),
                        rotation=ue.Rotator(pitch=float(pitch), yaw=float(yaw), roll=float(roll)),
                        scale=ue.Vector(*map(float, _xyz(scale, 'scale', positive=True))))


def _primitive(source):
    ue = _ue()
    if source.kind == 'box':
        return ue.load_asset('/Engine/BasicShapes/Cube')
    recipe = f'lowpoly-1:{source.kind}:{source.value}:center:facet:uniform-uv'
    path = f'{_CACHE_ROOT}/SM_{source.kind}_{sha256(recipe.encode()).hexdigest()[:8]}'
    if ue.EditorAssetLibrary.does_asset_exist(path):
        mesh = ue.load_asset(path)
        if not isinstance(mesh, ue.StaticMesh) or ue.EditorAssetLibrary.get_metadata_tag(mesh, _RECIPE) != recipe:
            raise ValueError(f'Unowned or incompatible geometry asset: {path}')
        return mesh
    mesh = ue.DynamicMesh()
    options = ue.GeometryScriptPrimitiveOptions()
    segments = source.value[0] if source.kind == 'frustum' else source.value
    common = dict(radial_steps=segments, height_steps=0,
                  origin=ue.GeometryScriptPrimitiveOriginMode.CENTER, capped=True)
    if source.kind == 'cylinder':
        ue.GeometryScript_Primitives.append_cylinder(mesh, options, ue.Transform(), radius=50, height=100, **common)
    else:
        top = 50 * float.fromhex(source.value[1]) if source.kind == 'frustum' else 0
        ue.GeometryScript_Primitives.append_cone(mesh, options, ue.Transform(), base_radius=50, top_radius=top, height=100, **common)
    ue.GeometryScript_Normals.set_per_face_normals(mesh)
    result, outcome = ue.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(
        mesh, path, ue.GeometryScriptCreateNewStaticMeshAssetOptions())
    if result is None or outcome != ue.GeometryScriptOutcomePins.SUCCESS:
        raise RuntimeError(f'Cannot build geometry: {path}')
    ue.EditorAssetLibrary.set_metadata_tag(result, _RECIPE, recipe)
    if not ue.EditorAssetLibrary.save_loaded_asset(result):
        raise RuntimeError(f'Cannot save geometry: {path}')
    return result


def _asset(source, expected):
    ue = _ue()
    if isinstance(source, str):
        if source.startswith('/') and not source.endswith('.json'):
            source = ue.load_asset(source)
        elif expected == ue.StaticMesh:
            from mc_importer import import_block
            source = import_block(source)
    if not isinstance(source, expected):
        raise ValueError(f'Expected {expected.__name__}, got {source}')
    return source


@dataclass
class _Draw:
    mesh: object
    materials: tuple
    colored: bool
    parts: list

    def transforms(self):
        for part in self.parts:
            for point, angles, scale in zip(part.positions, part.angles, part.scales):
                yield _transform(point, angles, scale)


def _prepare(model):
    ue = _ue()
    sources, materials, prepared = {}, {}, {}
    for path, group in model._walk():
        draws = prepared[path] = {}
        for part in group._parts:
            if part.source not in sources:
                sources[part.source] = (_asset(part.source.value, ue.StaticMesh) if part.source.kind == 'asset'
                                        else _primitive(part.source))
            mesh = sources[part.source]
            slots = max(1, len(mesh.get_editor_property('static_materials')))
            if part.colored:
                if 'color' not in materials:
                    materials['color'] = _asset(COLOR_MATERIAL, ue.MaterialInterface)
                overrides = (materials['color'],) * slots
            elif part.material is not None:
                refs = part.material if isinstance(part.material, (list, tuple)) else [part.material] * slots
                if len(refs) != slots:
                    raise ValueError('material list must match the mesh material slot count')
                overrides = tuple(_asset(ref, ue.MaterialInterface) for ref in refs)
            else:
                overrides = ()
            key = mesh.get_path_name(), tuple(m.get_path_name() for m in overrides), part.colored
            if key not in draws:
                draws[key] = _Draw(mesh, overrides, part.colored, [])
            draws[key].parts.append(part)
    return prepared


def _write_custom_data(component, values):
    """Prefer the optional bulk bridge; official UE Python is a complete fallback."""
    ue = _ue()
    bulk = getattr(getattr(ue, 'mineprep', None), 'set_ism_custom_data', None)
    if bulk is not None:
        if not bulk(component, values.ravel().tolist(), 8):
            raise RuntimeError('Cannot write LowPoly instance data')
        return
    _write_custom_data_python(component, values)


def _write_custom_data_python(component, values):
    """Official Python fallback; upload all channels and refresh only at the end."""
    component.modify()
    component.set_num_custom_data_floats(8)
    last = len(values) - 1
    for index, row in enumerate(values):
        for channel, value in enumerate(row):
            if not component.set_custom_data_value(index, channel, float(value), index == last and channel == 7):
                raise RuntimeError('Cannot write LowPoly instance data')


def _tag(actor, prefix):
    tags = actor.tags if isinstance(actor, _ue().Actor) else actor.component_tags
    return next((str(t)[len(prefix):] for t in tags if str(t).startswith(prefix)), None)


def _mark(actor, owner, path=None):
    actor.component_tags = [*actor.component_tags, _OWNER + owner] + ([] if path is None else [_GROUP + path])


def _attach(component, parent, *, keep_world=False):
    ue = _ue()
    rule = ue.AttachmentRule.KEEP_WORLD if keep_world else ue.AttachmentRule.KEEP_RELATIVE
    if not component.attach_to_component(parent, '', rule, rule, rule, False):
        raise RuntimeError('Cannot attach LowPoly component')


def _rename_component(component, label):
    """Names share the Actor's namespace, including pending-destruction objects."""
    base = re.sub(r'\W', '_', label) or 'Part'
    name, suffix = base, 1
    while (existing := _ue().find_object(component.get_outer(), name)) is not None and existing != component:
        name, suffix = f'{base}_{suffix}', suffix+1
    component.modify()
    if not component.rename(name):
        raise RuntimeError(f'Cannot name LowPoly component: {name}')


def _component(root, parent, cls, label):
    """Official editor component creation: registered, transactional and serialized."""
    ue = _ue()
    subsystem = ue.get_engine_subsystem(ue.SubobjectDataSubsystem)
    library = ue.SubobjectDataBlueprintFunctionLibrary
    handles = subsystem.k2_gather_subobject_data_for_instance(root)
    handle = next(h for h in handles if library.get_associated_object(library.get_data(h)) == parent)
    root.modify()
    added, reason = subsystem.add_new_subobject(ue.AddNewSubobjectParams(parent_handle=handle, new_class=cls))
    component = library.get_associated_object(library.get_data(added))
    if not isinstance(component, cls):
        raise RuntimeError(f'Cannot create LowPoly component: {reason}')
    component.modify()
    component.set_mobility(ue.ComponentMobility.MOVABLE)
    _rename_component(component, label)
    return component


def _owned(root, owner):
    return [a for a in root.get_components_by_class(_ue().SceneComponent)
            if _tag(a, _OWNER) == owner]


class LowPolyModel(_Group):
    """Static low-poly recipe. Asset size/pivot is preserved; group pivots are local origins.

    Pure color data: linear RGBA, metallic, specular, roughness, emissive (8 floats).
    Color input is sRGB(A); material overrides and color/surface overrides are exclusive.
    Geometry sources and shared material assets are prepared before editing the level.
    """
    def __init__(self, name='Model'):
        super().__init__(name)

    @classmethod
    def from_blocks(cls, blocks, *, cell_size=1, cull=2, merge=3):
        from mc_structure import Blocks, _apply_cull, convert_to_packed_arrays
        from mc_math import decode_rotation
        if not isinstance(blocks, Blocks):
            raise TypeError('from_blocks requires Blocks')
        unit = float(_xyz(cell_size, 'cell_size', positive=True)[0])
        if np.asarray(cell_size).ndim != 0 or cull not in (0, 1, 2, 3) or merge not in (0, 1, 2, 3):
            raise ValueError('cell_size must be scalar; cull and merge must be in 0..3')
        result = cls(blocks.name)
        for name, data in convert_to_packed_arrays(_apply_cull(blocks.copy_cells(), cull), merge=merge).items():
            angles = np.asarray([decode_rotation(float(code)) for code in data['rot']])
            result.add_many(name, data['pos'] * (unit / 100), scale=data['scale'] * unit,
                            pitch=angles[:, 0], yaw=angles[:, 1], roll=angles[:, 2])
        return result

    def spawn(self, *, position=(0, 0, 0), pitch=0, yaw=0, roll=0, scale=1, collision=False):
        ue = _ue()
        pose = _transform(position, (pitch, yaw, roll), scale)
        prepared = _prepare(self)
        if not any(prepared.values()):
            return None
        subsystem = ue.get_editor_subsystem(ue.EditorActorSubsystem)
        with ue.ScopedEditorTransaction('Create LowPoly model'):
            root = subsystem.spawn_actor_from_class(ue.Actor, ue.Vector())
            if root is None:
                raise RuntimeError('Cannot create LowPoly Actor')
            root.tags = [*root.tags, _ROOT + uuid4().hex]
            try:
                if root.root_component is None:
                    _component(root, root, ue.SceneComponent, 'Root')
                root.root_component.set_mobility(ue.ComponentMobility.MOVABLE)
                from mc_utils import set_actor_label
                set_actor_label(root, self.name)
                root.set_actor_transform(pose, False, False)
                root.set_folder_path(self.name)
                self._replace(root, prepared, collision)
            except Exception:
                subsystem.destroy_actor(root)
                raise
        return root

    def update(self, root, *, collision=False):
        """Keep the root pose and group identities; replace only owned render batches."""
        ue = _ue()
        if not isinstance(root, ue.Actor) or not ue.SystemLibrary.is_valid(root) or _tag(root, _ROOT) is None:
            raise ValueError('update requires a live LowPolyModel root Actor')
        if root.get_world() != ue.get_editor_subsystem(ue.UnrealEditorSubsystem).get_editor_world():
            raise ValueError('root must belong to the current editor world')
        prepared = _prepare(self)
        with ue.ScopedEditorTransaction('Update LowPoly model'):
            self._replace(root, prepared, collision)
        return root

    @staticmethod
    def component(root, path=''):
        """按持久化分组路径取组件句柄；空路径为根，不依赖组件对象名。"""
        owner = _tag(root, _ROOT)
        if owner is None:
            raise ValueError('component requires a LowPolyModel root Actor')
        from mc_handle import component
        if not path:
            return component(root.root_component)
        for group in _owned(root, owner):
            if _tag(group, _GROUP) == path:
                return component(group)
        raise KeyError(path)

    def _replace(self, root, prepared, collision):
        ue = _ue()
        from mc_structure import _add_transform_instances
        owner = _tag(root, _ROOT)
        old = _owned(root, owner)
        anchors = {_tag(a, _GROUP): a for a in old if _tag(a, _GROUP) is not None}
        anchors[''] = root.root_component
        created, snapshots, names = [], [], []
        try:
            for path, group in self._walk():
                if path and path not in anchors:
                    actor = _component(root, anchors[path.rpartition('/')[0]], ue.SceneComponent, path.replace('/', '_'))
                    created.append(actor)
                    _mark(actor, owner, path)
                    anchors[path] = actor
                for index, draw in enumerate(prepared[path].values()):
                    actor = _component(root, anchors[path], ue.InstancedStaticMeshComponent, f'LowPolyBuild_{uuid4().hex}')
                    created.append(actor)
                    names.append((actor, f'{path.replace("/", "_") or group.name}_{draw.mesh.get_name()}_{index}'))
                    _mark(actor, owner)
                    actor.set_visibility(False)
                    actor.set_static_mesh(draw.mesh)
                    actor.set_collision_profile_name('BlockAll' if collision else 'NoCollision')
                    actor.set_editor_property('can_ever_affect_navigation', bool(collision))
                    _add_transform_instances(actor, draw.transforms(), update_navigation=collision)
                    for slot, material in enumerate(draw.materials):
                        actor.set_material(slot, material)
                    if draw.colored:
                        _write_custom_data(actor, np.concatenate([p.values for p in draw.parts]))
                    _attach(actor, anchors[path])
            # Commit poses only after all render batches have been populated.
            active = dict(self._walk())
            for path, group in active.items():
                if path:
                    actor = anchors[path]
                    snapshots.append((actor, actor.get_attach_parent(), actor.get_relative_transform()))
                    actor.modify()
                    _attach(actor, anchors[path.rpartition('/')[0]])
                    actor.set_relative_transform(
                        _transform(group.pivot, (group.pitch, group.yaw, group.roll), group.scale), False, False)
        except Exception:
            for actor, parent, pose in reversed(snapshots):
                if parent is not None:
                    _attach(actor, parent)
                actor.set_relative_transform(pose, False, False)
            for actor in reversed(created):
                actor.destroy_component(root)
            raise
        retained = {a for path, a in anchors.items() if path in active}
        obsolete = [a for a in old if a not in retained]
        # User attachments survive even when their generated parent is removed.
        for actor in obsolete:
            for child in actor.get_children_components(False):
                if _tag(child, _OWNER) != owner:
                    child.modify()
                    _attach(child, root.root_component, keep_world=True)
        for actor in reversed(obsolete):
            actor.modify()
            _rename_component(actor, f'LowPolyOld_{uuid4().hex}')
            actor.destroy_component(root)
        for actor, label in names:
            _rename_component(actor, label)
        for actor in created:
            actor.set_visibility(True)
