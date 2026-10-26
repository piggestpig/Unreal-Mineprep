"""Explicit numeric diagnostics shared by geometry stages and pack samplers."""
from dataclasses import dataclass, field


@dataclass
class StageReport:
    values: dict = field(default_factory=dict)

    def add(self, name, value):
        self.values[name] = self.values.get(name, 0) + value

    def peak(self, name, value):
        self.values[name] = max(self.values.get(name, 0), value)

    def get(self, name, default=0):
        return self.values.get(name, default)
