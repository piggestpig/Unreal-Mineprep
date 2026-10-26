"""Editor-only heightmap ownership and import notifications; no UE in specs."""
from pathlib import Path

from .core.pack import PackChangedError


class HeightmapSource:
    def __init__(self, label='高度图 / Heightmap'):
        self.label = label
        self.texture = None
        self.asset_path = ''
        self.identity = None
        self._file_identity = None
        self.path = ''
        self._bindings = []
        self._pending = None
        self._closed = False

    def resolve(self, asset_path):
        import unreal
        import mineprep
        self.asset_path = asset_path
        texture = self.texture
        if texture is None or not unreal.SystemLibrary.is_valid(texture) or texture.get_path_name() != asset_path:
            texture = unreal.load_asset(asset_path)
        if not isinstance(texture, unreal.Texture2D):
            raise ValueError(f'{self.label}: 纹理不存在或不是Texture2D / Missing Texture2D')
        if texture.get_editor_property('virtual_texture_streaming'):
            raise ValueError(f'{self.label}: 不支持虚拟纹理 / Virtual textures are unsupported')
        source_id = texture.blueprint_get_texture_source_id_string()
        if not source_id:
            raise ValueError(f'{self.label}: 纹理没有有效Source / Texture has no Source')
        identity = (asset_path, source_id)
        if identity != self.identity or not self.path or not Path(self.path).is_file():
            path = str(mineprep.export_tex_cache(texture))
        else:
            path = self.path
        self.texture, self.identity, self.path = texture, identity, path
        self.guard()()
        return path

    def guard(self):
        """Capture this request's UObject and identity; call only at main-thread boundaries."""
        if self.identity is None:
            return None
        texture, identity = self.texture, self.identity
        def check():
            import unreal
            if (not unreal.SystemLibrary.is_valid(texture)
                    or texture.get_path_name() != identity[0]
                    or texture.blueprint_get_texture_source_id_string() != identity[1]
                    or texture.get_editor_property('virtual_texture_streaming')):
                raise PackChangedError()
        return check

    def import_file(self, path, source):
        import mineprep
        source.checked()
        identity = (str(path), source.digest, source.stamp)
        if self.texture is not None and identity == self._file_identity:
            return self.texture  # Mapping edits do not rebuild the unchanged input texture.
        texture = mineprep.import_data_tex(path)
        source.checked()
        self.texture = texture
        self._file_identity = identity
        return texture

    def listen(self, invalidate, refresh):
        import unreal
        import mineprep
        self._invalidate, self._refresh = invalidate, refresh
        try:
            subsystem = unreal.get_editor_subsystem(unreal.ImportSubsystem)
            for name, handler in (('on_asset_reimport', self._reimport),
                                  ('on_asset_post_import', self._post_import)):
                delegate = getattr(subsystem, name)
                delegate.add_callable(handler)
                self._bindings.append((delegate, handler))
        except Exception as exc:
            self._unbind()
            mineprep.warn(f'{self.label}: 自动刷新不可用；操作时仍检查来源 / Import notifications unavailable: {exc}')

    def _post_import(self, factory, created_object):
        self._reimport(created_object)

    def _reimport(self, created_object):
        if (self._closed or not self.asset_path or created_object is None
                or created_object.get_path_name() != self.asset_path or self._pending is not None):
            return
        if self._invalidate() is False:
            return
        import mineprep
        self._pending = mineprep.delay(self._dispatch)()

    def _dispatch(self):
        self._pending = None
        if not self._closed:
            self._refresh()

    def clear(self):
        if self._pending is not None:
            self._pending.destroy()
            self._pending = None
        self.texture, self.identity = None, None
        self._file_identity = None
        self.asset_path = self.path = ''

    def _unbind(self):
        for delegate, handler in self._bindings:
            try:
                delegate.remove_callable(handler)
            except Exception as exc:
                import mineprep
                mineprep.warn(f'Heightmap import callback cleanup: {exc}')
        self._bindings.clear()

    def close(self):
        self._closed = True
        try:
            self._unbind()
        finally:
            self.clear()
