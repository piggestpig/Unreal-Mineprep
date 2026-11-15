"""Pure-stdlib Bedrock keyframe authoring utilities."""
from __future__ import annotations

import json
import math
from pathlib import Path

TAU = 2.0 * math.pi


def time_key(step: int, duration: float, steps: int) -> str:
    """Format uniform keyframe timestamp cleanly without trailing noise."""
    t = duration if step == steps else (step * duration / steps)
    text = f'{t:.5f}'.rstrip('0').rstrip('.')
    return text if '.' in text else f'{text}.0'


def rnd(value: float, digits: int = 4) -> float:
    rounded = round(float(value), digits)
    return 0.0 if abs(rounded) < 1e-9 else rounded


def smootherstep(edge0: float, edge1: float, x: float) -> float:
    if edge1 <= edge0:
        return 1.0 if x >= edge1 else 0.0
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def smooth_plateau(u: float, rise0: float, rise1: float, fall0: float, fall1: float) -> float:
    """Smooth C2 envelope rising from 0->1 over [rise0, rise1] and falling 1->0 over [fall0, fall1]."""
    if u <= rise0 or u >= fall1:
        return 0.0
    if u < rise1:
        return smootherstep(rise0, rise1, u)
    if u <= fall0:
        return 1.0
    return 1.0 - smootherstep(fall0, fall1, u)


def bake_clip(clip_id: str, duration: float, steps: int, pose_fn, *, loop: bool = True) -> dict:
    """Sample `pose_fn(phase_rad, u)` at `steps + 1` points with exact `0` / `duration` closure."""
    bones: dict[str, dict[str, dict[str, list[float]]]] = {}
    for step in range(steps):
        u = step / steps
        phase = TAU * u
        tk = time_key(step, duration, steps)
        frame = pose_fn(phase, u)
        for bone_name, channels in frame.items():
            target = bones.setdefault(bone_name, {})
            for ch_name, vec in channels.items():
                target.setdefault(ch_name, {})[tk] = [rnd(v) for v in vec]

    end_tk = time_key(steps, duration, steps)
    start_tk = time_key(0, duration, steps)
    for channels in bones.values():
        for timeline in channels.values():
            timeline[end_tk] = list(timeline[start_tk])

    return {
        'format_version': '1.8.0',
        'animations': {
            clip_id: {
                'loop': bool(loop),
                'animation_length': rnd(duration, 4),
                'bones': bones,
            }
        },
    }


def write_bedrock_clip(path: Path | str, payload: dict) -> Path:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return dest
