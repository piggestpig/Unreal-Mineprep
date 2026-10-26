"""Private, source-snapshotted import namespaces for a pack and its bases.

Committed snapshots stay importable for the session (they are small), so an
older Pack keeps working after its files change; uninstall() drops them all.
"""
import hashlib
import importlib
import importlib.abc
import importlib.util
import json
from pathlib import Path
import sys


class _Context(importlib.abc.Loader):
    def __init__(self, root_package, roots, directories, files, versions):
        digest = hashlib.sha256(json.dumps((roots, directories, versions)).encode())
        for pack_id, path, source in files:
            digest.update(pack_id.encode() + str(path).encode() + source)
        self.prefix = f'{root_package}._pack_{digest.hexdigest()}'
        self.sources = {}
        self.packages = {self.prefix}
        self.committed = False
        for pack_id, directory in directories:
            parent = f'{self.prefix}.{pack_id}'
            self.packages.add(parent)
            for owner, path, source in files:
                if owner != pack_id:
                    continue
                parts = Path(path).relative_to(directory).with_suffix('').parts
                package = parts[-1] == '__init__'
                parts = parts[:-1] if package else parts
                name = '.'.join((parent, *parts))
                self.sources[name] = (path, source)
                self.packages.update('.'.join((parent, *parts[:i])) for i in range(len(parts)))
                if package:
                    self.packages.add(name)

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        source = self.sources.get(module.__name__)
        if source:
            path, code = source
            module.__file__ = path
            exec(compile(code, path, 'exec'), module.__dict__)

    def module(self, pack_id, name):
        return importlib.import_module(f'{self.prefix}.{pack_id}.{name}')


class _Finder(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.contexts = {}

    def find_spec(self, fullname, path=None, target=None):
        # Only intercept our private namespaces; normal core/third-party imports
        # retain Python's normal behaviour. Empty package paths prevent fallback
        # to live files when a snapshot does not contain the requested helper.
        parent = fullname
        while parent not in self.contexts and '.' in parent:
            parent = parent.rpartition('.')[0]
        context = self.contexts.get(parent)
        if context and (fullname in context.sources or fullname in context.packages):
            return importlib.util.spec_from_loader(
                fullname, context, is_package=fullname in context.packages)
        return None


_finder = _Finder()


def context(root_package, roots, directories, files, versions):
    candidate = _Context(root_package, roots, directories, files, versions)
    existing = _finder.contexts.get(candidate.prefix)
    if existing is not None:
        return existing
    if _finder not in sys.meta_path:
        sys.meta_path.insert(0, _finder)
    _finder.contexts[candidate.prefix] = candidate
    return candidate


def discard_uncommitted():
    for prefix, item in list(_finder.contexts.items()):
        if not item.committed:
            _drop(prefix)


def _drop(prefix):
    _finder.contexts.pop(prefix, None)
    for name in list(sys.modules):
        if name == prefix or name.startswith(prefix + '.'):
            sys.modules.pop(name, None)
    parent, _, attribute = prefix.rpartition('.')
    module = sys.modules.get(parent)
    if module is not None and hasattr(module, attribute):
        delattr(module, attribute)


def uninstall():
    """Unregister the finder before Mineprep unloads the package modules."""
    from . import pack
    with pack._lock:
        # Disable/re-enable can reuse the package without a full Python reload.
        # Cached Packs must not refer to namespaces which have been removed.
        pack._cache.clear()
        for prefix in list(_finder.contexts):
            _drop(prefix)
        if _finder in sys.meta_path:
            sys.meta_path.remove(_finder)
