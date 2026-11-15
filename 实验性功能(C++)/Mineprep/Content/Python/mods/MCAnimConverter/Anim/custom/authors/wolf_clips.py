"""Procedural wolf-specific clip authored on the articulated quadruped_edit skeleton."""
from __future__ import annotations

import math

from .common import TAU, bake_clip, smooth_plateau


def build_wolf_play_bow() -> dict:
    """Expressive wolf play-bow (`1.6s`, 97 keys) using pelvis, body, upper_body, head, tail & real_tail."""
    duration = 1.6
    steps = 96

    def pose_at(p: float, u: float) -> dict:
        # Torso dips after front legs begin reaching forward, and rises slightly before front legs recover,
        # preventing paw ground clipping without requiring artificial shoulder translation.
        body_env = smooth_plateau(u, 0.08, 0.28, 0.65, 0.86)
        reach_env = smooth_plateau(u, 0.01, 0.21, 0.72, 0.94)
        wag_hold = smooth_plateau(u, 0.03, 0.16, 0.82, 0.96)
        bounce = body_env * 0.5 * (1.0 - math.cos(2.0 * TAU * max(0.0, min(1.0, (u - 0.22) / 0.48))))

        # Three complete tail-wag cycles per loop with trailing tip lag on `real_tail`.
        wag_phase = 3.0 * p
        wag = math.sin(wag_phase)
        wag_tip = math.sin(wag_phase - 0.55)

        hind_brace = 15.0 * body_env - 1.2 * bounce
        rad_h = math.radians(hind_brace)
        # Keep hind paws planted on ground (pelvis shifts forward & settles cleanly as hind legs brace).
        pelvis_drop_cm = 50.0 * (1.0 - math.cos(rad_h)) - 6.25 * math.sin(rad_h)
        pelvis_fwd_cm = 50.0 * math.sin(rad_h)
        pelvis_y_px = -pelvis_drop_cm / 6.25
        pelvis_z_px = -pelvis_fwd_cm / 6.25  # Bedrock -Z maps to UE +X (forward).

        body_pitch = 16.0 * body_env + 1.4 * bounce
        body_roll = 0.6 * body_env * math.sin(wag_phase * 0.5)

        front_world = -61.8 * reach_env - 1.0 * bounce
        front_local = front_world - body_pitch
        alt_paw = 1.2 * wag_hold * math.sin(wag_phase * 0.5)

        mane_pitch = -3.5 * body_env + 2.5 * bounce
        head_pitch = -(body_pitch + 6.0 * body_env - 2.0 * bounce)
        head_yaw = 11.0 * wag_hold * math.sin(TAU * u)
        head_roll = 10.5 * body_env

        return {
            'pelvis': {
                'position': [0.0, pelvis_y_px, pelvis_z_px],
            },
            'body': {
                'rotation': [body_pitch, 0.0, body_roll],
            },
            'upper_body': {
                'rotation': [mane_pitch, 2.8 * body_env * math.sin(wag_phase * 0.5), 0.0],
            },
            'head': {
                'rotation': [head_pitch, head_yaw, head_roll],
            },
            'tail': {
                'rotation': [22.0 + 50.0 * body_env + 4.0 * bounce, 24.0 * wag, 0.0],
            },
            'real_tail': {
                'rotation': [10.0 * body_env, 14.0 * wag_tip, 0.0],
            },
            'left_front_leg': {
                'rotation': [front_local + alt_paw, 0.0, -3.5 * reach_env],
            },
            'right_front_leg': {
                'rotation': [front_local - alt_paw, 0.0, 3.5 * reach_env],
            },
            'left_hind_leg': {
                'rotation': [hind_brace, 0.0, 0.0],
            },
            'right_hind_leg': {
                'rotation': [hind_brace, 0.0, 0.0],
            },
        }

    return bake_clip('animation.mineprep.wolf.play_bow', duration, steps, pose_at)
