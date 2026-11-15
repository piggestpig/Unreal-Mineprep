"""Pure-Python shared rig layout tables, bone aliases, and Bedrock<->UE unit conversions."""
from __future__ import annotations

import re

PIXELS_TO_CM = 6.25

BIPED_PARENTS = {
    'root': None,
    'waist': 'root',
    'body': 'waist',
    'head': 'body',
    'leftarm': 'body',
    'rightarm': 'body',
    'leftleg': 'root',
    'rightleg': 'root',
}

# Bedrock player source reference positions in cm. Wide and slim share these joint transforms.
BIPED_SOURCE_POSITIONS = {
    'root': (0.0, 0.0, 0.0),
    'waist': (0.0, 0.0, 75.0),
    'body': (0.0, 0.0, 75.0),
    'head': (0.0, 0.0, 0.0),
    'leftarm': (0.0, -31.25, -12.5),
    'rightarm': (0.0, 31.25, -12.5),
    'leftleg': (0.0, -12.5, 75.0),
    'rightleg': (0.0, 12.5, 75.0),
}

BIPED_TARGET_BONES = {
    'root': (None, 'root'),
    'pelvis': ('root', None),
    'body': ('pelvis', 'body'),
    'head': ('body', 'head'),
    'left_arm': ('body', 'leftarm'),
    'right_arm': ('body', 'rightarm'),
    'left_leg': ('pelvis', 'leftleg'),
    'right_leg': ('pelvis', 'rightleg'),
}

BIPED_TARGETS = {tgt: src for tgt, (_, src) in BIPED_TARGET_BONES.items() if src is not None}

GENERIC_ALIASES = {
    'leftbackleg': 'left_hind_leg',
    'left_back_leg': 'left_hind_leg',
    'rightbackleg': 'right_hind_leg',
    'right_back_leg': 'right_hind_leg',
    'leftrearleg': 'left_hind_leg',
    'left_rear_leg': 'left_hind_leg',
    'rightrearleg': 'right_hind_leg',
    'right_rear_leg': 'right_hind_leg',
    'leg0': 'right_hind_leg',
    'leg1': 'left_hind_leg',
    'leg2': 'right_front_leg',
    'leg3': 'left_front_leg',
    'torso': 'body',
    'upperbody': 'upper_body',
}

QUADRUPED_EDIT_BONES = {
    'root': None,
    'pelvis': 'root',
    'body': 'pelvis',
    'head': ('body', 'head_parts', 'neck'),
    'left_front_leg': 'body',
    'right_front_leg': 'body',
    'left_hind_leg': 'pelvis',
    'right_hind_leg': 'pelvis',
}

QUADRUPED_EDIT_OPTIONAL = {
    'upper_body': ('body',),
    'left_chest': ('body',),
    'right_chest': ('body',),
    'egg_belly': ('body',),
    'hump': ('body',),
    'head_parts': ('body',),
    'neck': ('body',),
    'tail': ('pelvis', 'body'),
    'tail1': ('pelvis',),
    'tail2': ('tail1', 'pelvis'),
}

QUADRUPED_EDIT_REPARENTED = {
    'upper_body': 'body',
    'left_chest': 'body',
    'right_chest': 'body',
    'egg_belly': 'body',
    'hump': 'body',
    'head_parts': 'body',
    'neck': 'body',
    'tail': 'pelvis',
    'tail1': 'pelvis',
    'tail2': 'tail1',
}

QUADRUPED_BODY_CHILDREN = frozenset({'head', 'left_front_leg', 'right_front_leg'})

QUADRUPED_REQUIRED = (
    'root', 'body', 'head',
    'left_front_leg', 'right_front_leg', 'left_hind_leg', 'right_hind_leg',
)


def bedrock_pos_to_ue_cm(pos, scale: float = 1.0) -> tuple[float, float, float]:
    """Convert Bedrock position in pixels to UE cm with optional retarget scale."""
    factor = PIXELS_TO_CM * float(scale)
    return (-float(pos[2]) * factor, -float(pos[0]) * factor, float(pos[1]) * factor)


def ue_cm_to_bedrock_pos(vec, scale: float = 1.0) -> list[float]:
    """Inverse of `bedrock_pos_to_ue_cm`: convert UE cm back to Bedrock pixels."""
    factor = PIXELS_TO_CM * float(scale)
    if factor <= 0.0:
        raise ValueError(f'无效位移缩放倍率: {scale}')
    return [-float(vec[1]) / factor, float(vec[2]) / factor, -float(vec[0]) / factor]


def bedrock_scale_to_ue(scale) -> tuple[float, float, float]:
    """Reorder Bedrock XYZ scale axes into UE coordinates."""
    return (float(scale[2]), float(scale[0]), float(scale[1]))


def biped_control_name(bone: str) -> str | None:
    """Normalize a Bedrock biped bone key to one of `BIPED_PARENTS`, or None."""
    low = bone.casefold()
    if low == 'hip':
        return 'waist'
    if low in BIPED_PARENTS:
        return low
    compact = low.replace('_', '')
    return compact if compact in ('leftarm', 'rightarm', 'leftleg', 'rightleg') else None


def canonical_snake_name(bone: str) -> str:
    """Convert camelCase / kebab-case bone names to folded snake_case."""
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', bone).replace('-', '_').casefold()


def resolve_aliased_bone(bone: str, exact, lookup_fn) -> str | None:
    """Resolve a Bedrock bone name via exact, case-folded, snake_case, and alias matches."""
    if bone in exact:
        return bone
    low = bone.casefold()
    hit = lookup_fn(low)
    if hit is not None:
        return hit
    snake = canonical_snake_name(bone)
    hit = lookup_fn(snake)
    if hit is not None:
        return hit
    alias = GENERIC_ALIASES.get(low) or GENERIC_ALIASES.get(snake)
    return lookup_fn(alias.casefold()) if alias is not None else None


def biped_source_layout(
    root_p: tuple[float, float, float],
    pelvis_p: tuple[float, float, float],
    head_p: tuple[float, float, float] | None,
    target_positions: dict[str, tuple[float, float, float]],
) -> tuple[dict[str, tuple[float, float, float]], float]:
    """Match Bedrock player sockets and translation scale to target skeleton proportions."""
    torso_h = (head_p[2] - pelvis_p[2]) if head_p is not None else 0.0
    leg_h = pelvis_p[2] - root_p[2]
    if torso_h > 1e-3:
        scale = torso_h / 75.0
    elif leg_h > 1e-3:
        scale = leg_h / 75.0
    else:
        scale = 1.0
    body_p = (pelvis_p[0], pelvis_p[1], pelvis_p[2] + 75.0 * scale)

    def _offset(target_name: str, parent_p: tuple[float, float, float], default_xyz: tuple[float, float, float]):
        if target_name in target_positions:
            tp = target_positions[target_name]
            return (tp[0] - parent_p[0], tp[1] - parent_p[1], tp[2] - parent_p[2])
        return tuple(v * scale for v in default_xyz)

    positions = {
        'root': root_p,
        'waist': (pelvis_p[0] - root_p[0], pelvis_p[1] - root_p[1], pelvis_p[2] - root_p[2]),
        'body': (body_p[0] - pelvis_p[0], body_p[1] - pelvis_p[1], body_p[2] - pelvis_p[2]),
        'head': _offset('head', body_p, BIPED_SOURCE_POSITIONS['head']),
        'leftarm': _offset('left_arm', body_p, BIPED_SOURCE_POSITIONS['leftarm']),
        'rightarm': _offset('right_arm', body_p, BIPED_SOURCE_POSITIONS['rightarm']),
        'leftleg': _offset('left_leg', root_p, BIPED_SOURCE_POSITIONS['leftleg']),
        'rightleg': _offset('right_leg', root_p, BIPED_SOURCE_POSITIONS['rightleg']),
    }
    return positions, float(scale)


def quadruped_source_parents(
    bone_parents: dict[str, str | None],
    mapped_bones,
    *,
    edit_rig: bool,
) -> dict[str, str | None]:
    """Build flat-source parent mapping for quadruped raw and edit skeletons."""
    head_parent = bone_parents['head'] if edit_rig else None
    head_follows_neck = head_parent in ('head_parts', 'neck') and head_parent in mapped_bones
    flat_required = set(QUADRUPED_REQUIRED[1:]) - ({'head'} if head_follows_neck else set())
    reparented_optional = {
        name for name, parent in QUADRUPED_EDIT_REPARENTED.items()
        if bone_parents.get(name) == parent and name in mapped_bones
    }
    flat_root = flat_required | reparented_optional
    return {
        name: ('root' if (edit_rig and (name in flat_root or bone_parents[name] == 'pelvis'))
               else bone_parents[name])
        for name in bone_parents
        if name != 'pelvis'
    }
