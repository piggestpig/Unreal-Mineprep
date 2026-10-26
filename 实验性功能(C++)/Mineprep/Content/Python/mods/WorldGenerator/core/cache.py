"""Build-once dictionaries for pure, world-anchored records."""
import threading

_MISSING = object()


class Memo:
    """Thread-safe memo, optionally keeping only the `limit` most recently used entries.

    Concurrent misses may build the same pure value twice; the first stored
    value wins, so every caller sees one result.
    """
    def __init__(self, limit=None):
        self.limit = limit
        self._values = {}
        self._lock = threading.Lock()

    def get(self, key, build):
        value = self._values.get(key, _MISSING)
        if value is _MISSING:
            return self.put(key, build())
        if self.limit is not None:
            with self._lock:
                if key in self._values:
                    self._values[key] = self._values.pop(key)
        return value

    def put(self, key, value):
        """Store value unless key is already present; return the stored value."""
        with self._lock:
            value = self._values.setdefault(key, value)
            while self.limit is not None and len(self._values) > self.limit:
                del self._values[next(iter(self._values))]
        return value

    def clear(self):
        with self._lock:
            self._values.clear()

    def __contains__(self, key):
        return key in self._values

    def __len__(self):
        return len(self._values)

    def items(self):
        return tuple(self._values.items())
