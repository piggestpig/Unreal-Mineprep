"""Fine terrain shaping and water semantics over replaceable planning geometry."""
import numpy as np

from ...core.fields import field
from .terrain import _smooth

@field('river_bed_noise', res=2)
def river_bed_noise(ctx):
    sea = np.floor(ctx.param('world.sea_level'))
    active = (ctx.param('water.generate') and ctx.param('river.enabled') and not ctx.param('terrain.flat')
              and ctx.param('river.max_cut') > 0 and ctx.param('world.y_min') <= sea < ctx.param('world.y_max'))
    if not active or not ctx.param('river.bed_strength') or not ctx.param('river.depth'):
        return 0.
    return np.clip(2.5 * ctx.noise('river/bed', ctx.param('river.bed_scale'), octaves=2), -1, 1)


@field('river_distance', resources=('water',))
def river_distance(ctx):
    """Continuous planned distance; no river influence with hydrology disabled."""
    if not ctx.param('water.generate'):
        return 0.
    return _sample(ctx)['river_distance'] if _enabled(ctx) else 1e6


@field('river_bank_span', deps=('height_before_rivers',), resources=('water',))
def river_bank_span(ctx, original):
    """Shared shaped bank span, including the near-water band."""
    if not ctx.param('water.generate'):
        return 0.
    return _sample(ctx)['river_bank_span'] if _enabled(ctx) else 0.


def _enabled(ctx):
    return ctx.param('water.generate') and ctx.param('hydrology.enabled') and not ctx.param('terrain.flat')


def _sample(ctx):
    cached = ctx._cache.get('water/shape')
    if cached is not None:
        return cached
    plan = ctx.resource('water')
    original = ctx.get('height_before_rivers')
    sea = ctx.param('world.sea_level')
    anchor = np.floor(sea)
    old_wet = np.ceil(np.clip(original, ctx.param('world.y_min'), ctx.param('world.y_max'))) <= sea
    distance, half, mouth, sid = plan.query(ctx.x, ctx.z, wet_mask=old_wet)
    variation = np.clip(ctx.noise('water/banks', 48, octaves=2) * 2, -1, 1)
    half = half * (1 + .17 * variation)
    above = np.maximum(original - anchor, 0)
    bank = np.minimum(64, ctx.param('river.bank_width') + ctx.param('river.bank_height_scale')
                      * above * (1 + .35 * variation))
    near = ctx.param('river.near_bank') * (1 + .2 * variation)
    edge = np.maximum(distance - half, 0)
    inner = _smooth(edge / near)
    outer = _smooth(np.maximum(edge - near, 0) / np.maximum(bank, 1))
    # Two transitions: the water's edge climbs only a few blocks first;
    # the broad valley retains original detail through a variable outer blend.
    shore = anchor + 1.5 + .5 * variation
    depth = ctx.param('river.depth')
    u = np.clip(distance / np.maximum(half, .01), 0, 1)
    amplitude = min(ctx.param('river.bed_strength'), depth / 4)
    bed_noise = np.clip(ctx.get('river_bed_noise'), -1, 1)
    edge_depth = min(depth, ctx.param('river.edge_depth'))
    bed = anchor - depth + (depth - edge_depth) * u * u + amplitude * (1 - u * u) * bed_noise
    if plan.mouth_profiles is not None and len(plan.segments) and depth > 0:
        # One vector projection of the already-selected segment; no additional
        # terrain sampling. Missing profiles retain custom planner behavior.
        s = plan.segments[np.maximum(sid, 0)]
        dx, dz = s[..., 2] - s[..., 0], s[..., 3] - s[..., 1]
        t = np.clip(((ctx.x - s[..., 0]) * dx + (ctx.z - s[..., 1]) * dz)
                    / np.maximum(dx * dx + dz * dz, 1e-12), 0, 1)
        profile = plan.mouth_profiles[np.maximum(sid, 0)]
        remaining = profile[..., 0] * (1 - t) + profile[..., 1] * t
        join = (sid >= 0) * (1 - _smooth(np.maximum(remaining, 0) / ctx.param('river.mouth_length')))
        bed += (np.minimum(bed, profile[..., 2]) - bed) * join
    target = (bed * (1 - inner) + shore * inner) * (1 - outer) + original * outer
    budget = ctx.param('river.max_cut') + ctx.param('river.pass_cut_extra')
    support = (sid >= 0) & (distance < half + near + bank)
    # The last extension beyond an outlet is for underwater joining only.
    extension = (sid >= 0) & (plan.segments[np.maximum(sid, 0), 7] < 0) if len(plan.segments) else np.zeros(ctx.shape, bool)
    dry_support = support & ~old_wet & ~extension
    final = np.where(dry_support, np.minimum(original, np.maximum(target, original - budget)), original)
    # Blend existing wet floor across the complete mouth/lake join. Far ocean
    # stays exact. The lateral blend reaches zero smoothly outside the channel.
    join_length = np.minimum(96, np.maximum(ctx.param('river.mouth_length'), np.abs(original - bed) * 4))
    axial = np.where(extension, _smooth(np.clip((mouth + 1) * .5 * 96 / join_length, 0, 1)), 1.)
    lateral = 1 - _smooth(np.maximum(distance - half, 0) / np.maximum(near + bank, 1))
    joined = old_wet & support
    final = np.where(joined, original + (np.minimum(original, np.minimum(bed, anchor - .05))
                     - original) * lateral * axial, final)
    levels = np.full(ctx.shape, sea)
    kind = np.where(old_wet, 1, 0).astype(np.uint8)
    river_wet = dry_support & (np.ceil(final) <= sea)
    kind[river_wet] = 2
    body_id = np.zeros(ctx.shape, np.int32)
    for body in plan.nearby_bodies(ctx.x, ctx.z):
        d = body.distance(ctx.x, ctx.z)
        support |= d < 6
        inside = d < 0
        rim = 1 - _smooth(np.maximum(d, 0) / 6)
        # Basin interior is bowl-shaped, with small continuous bed variation.
        deep = _smooth(np.maximum(-d, 0) / max(body.depth * 2, 6))
        floor = np.floor(body.level) - body.depth * deep
        floor += min(.4, body.depth / 4) * bed_noise * deep
        floor = np.minimum(floor, np.floor(body.level) - .05)
        outside_target = body.level + 1 + np.maximum(original - body.level - 1, 0) * (1 - rim)
        shaped = np.where(inside, floor, outside_target)
        final = np.where(d < 6, np.minimum(final, shaped), final)
        levels[inside] = body.level
        body_id[inside] = body.id
        kind[inside] = body.kind
        # Same-level river/lake floors share the lake target across the junction.
        if body.level == sea:
            # Join the actual wet river corridor, not the entire lake footprint:
            # the latter would overwrite its bowl and steepen every shoreline.
            join = (d < ctx.param('river.mouth_length')) & (river_wet | joined) & (np.ceil(final) <= sea)
            blend = 1 - _smooth(np.maximum(d, 0) / ctx.param('river.mouth_length'))
            lake_bed = np.floor(sea) - body.depth
            final = np.where(join, final + (lake_bed - final) * blend, final)
    # Same-level lake joins may adjust their bowl, but cannot raise an ocean
    # floor outside the actual lake footprint.
    final = np.where(old_wet & (kind == 1), np.minimum(final, original), final)
    wet = np.ceil(np.clip(final, ctx.param('world.y_min'), ctx.param('world.y_max'))) <= levels
    kind = np.where(wet, np.where(kind > 0, kind, 1), 0)
    result = dict(height=final, water_level=levels, water_presence=wet, water_kind=kind,
                  river_distance=distance, river_bank_span=bank + near, water_body_id=body_id,
                  water_influence=support | (body_id > 0))
    ctx._cache['water/shape'] = result
    return result


@field('height', deps=('height_before_rivers',), resources=('water',))
def height(ctx, original):
    if not ctx.param('water.generate'):
        return ctx.get('height_badlands')
    if _enabled(ctx):
        return _sample(ctx)['height']
    return original


@field('water_level', resources=('water',))
def water_level(ctx):
    return _sample(ctx)['water_level'] if _enabled(ctx) else ctx.param('world.sea_level')


@field('water_presence', deps=('height', 'water_level'))
def water_presence(ctx, height, levels):
    if not ctx.param('water.generate'):
        return 0.
    return np.ceil(np.clip(height, ctx.param('world.y_min'), ctx.param('world.y_max'))) <= levels


@field('water_kind', deps=('height', 'water_presence'), resources=('water',))
def water_kind(ctx, final, presence):
    if not ctx.param('water.generate'):
        return 0.
    if _enabled(ctx):
        return np.where(presence > 0, _sample(ctx)['water_kind'], 0)
    return np.where(presence > 0, 1, 0)


@field('water_body_id', resources=('water',))
def water_body_id(ctx):
    return _sample(ctx)['water_body_id'] if _enabled(ctx) else 0.


@field('water_influence', resources=('water',))
def water_influence(ctx):
    return _sample(ctx)['water_influence'] if _enabled(ctx) else 0.


@field('channel_distance', resources=('water',))
def channel_distance(ctx):
    return _sample(ctx)['river_distance'] if _enabled(ctx) else ctx.get('river_distance')


@field('channel_bank_span', resources=('water',))
def channel_bank_span(ctx):
    return _sample(ctx)['river_bank_span'] if _enabled(ctx) else ctx.get('river_bank_span')
