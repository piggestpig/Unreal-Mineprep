"""Monotone cubic curves: JSON points in, vectorized lookup out.

A curve is a list of [x, y] points with strictly increasing x. Evaluation uses
Fritsch-Carlson slopes (no overshoot between keys) and clamps outside the range,
UE's editor keys use these same computed slopes as cubic user tangents.
"""

import math
import re

import numpy as np


def normalize_points(points):
    """Validate and return a canonical tuple of (x, y) float pairs."""
    try:
        points = list(points)
        if any(len(p) != 2 for p in points):
            raise ValueError
        pairs = tuple((float(p[0]), float(p[1])) for p in points)
    except (TypeError, ValueError):
        raise ValueError("curve must be a list of [x, y] pairs") from None
    if len(pairs) < 2:
        raise ValueError("curve needs at least two [x, y] pairs")
    if not all(math.isfinite(v) for p in pairs for v in p):
        raise ValueError("curve points must be finite")
    if any(b[0] <= a[0] for a, b in zip(pairs, pairs[1:])):
        raise ValueError("curve x values must strictly increase")
    return pairs


class Spline:
    __slots__ = ("points", "_x", "_y", "_m")

    def __init__(self, points):
        self.points = normalize_points(points)
        x = np.array([p[0] for p in self.points])
        y = np.array([p[1] for p in self.points])
        delta = np.diff(y) / np.diff(x)
        m = np.empty_like(x)
        m[0], m[-1] = delta[0], delta[-1]
        m[1:-1] = np.where(delta[:-1] * delta[1:] > 0, (delta[:-1] + delta[1:]) / 2, 0.0)
        for i in range(len(delta)):
            if delta[i] == 0:
                m[i] = m[i + 1] = 0.0
                continue
            a, b = m[i] / delta[i], m[i + 1] / delta[i]
            if a * a + b * b > 9:
                t = 3 / math.sqrt(a * a + b * b)
                m[i], m[i + 1] = t * a * delta[i], t * b * delta[i]
        self._x, self._y, self._m = x, y, m

    def __call__(self, value):
        v = np.clip(np.asarray(value, dtype=np.float64), self._x[0], self._x[-1])
        i = np.clip(np.searchsorted(self._x, v, side="right") - 1, 0, len(self._x) - 2)
        x0, h = self._x[i], self._x[i + 1] - self._x[i]
        t = (v - x0) / h
        t2, t3 = t * t, t * t * t
        return ((2 * t3 - 3 * t2 + 1) * self._y[i] + (t3 - 2 * t2 + t) * h * self._m[i]
                + (-2 * t3 + 3 * t2) * self._y[i + 1] + (t3 - t2) * h * self._m[i + 1])

    def to_json(self):
        return [list(p) for p in self.points]

    def __eq__(self, other):
        return isinstance(other, Spline) and other.points == self.points

    def __hash__(self):
        return hash(self.points)

    def __repr__(self):
        return f"Spline({self.to_json()})"


_KEYS = re.compile(r"Keys=\(((?:\([^()]*\),?)+)\)")
_NUMBER = re.compile(r"(?:^|,)(Time|Value)=([^,()]+)")


def points_from_ue_text(text):
    """Parse `RuntimeFloatCurve.export_text()` output into [x, y] points."""
    external = re.search(r'ExternalCurve=([^,)]+)', text or '')
    if external and external[1].strip() != 'None':
        raise ValueError('只支持内嵌曲线节点，请清除外部 CurveFloat 引用')
    # Unreal omits fields equal to their struct defaults, including Time/Value=0.
    match = _KEYS.search(text or "")
    points = []
    if match:
        for key in re.findall(r"\(([^()]*)\)", match[1]):
            values = {n: float(v) for n, v in _NUMBER.findall(key)}
            points.append([values.get('Time', 0.), values.get('Value', 0.)])
    return [list(p) for p in normalize_points(points)]


def ue_text_from_points(points):
    """UE cubic keys with the exact generating Spline's automatically computed slopes."""
    spline = Spline(points)
    keys = ",".join(f"(InterpMode=RCIM_Cubic,TangentMode=RCTM_User,Time={x:.9g},Value={y:.9g},"
                    f"ArriveTangent={m:.9g},LeaveTangent={m:.9g})"
                    for (x, y), m in zip(spline.points, spline._m))
    return (f"(EditorCurveData=(Keys=({keys}),PreInfinityExtrap=RCCE_Constant,"
            'PostInfinityExtrap=RCCE_Constant),ExternalCurve=None)')
