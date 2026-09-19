"""Dockable Mineprep browser. All Unreal calls stay on the Slate thread."""
import time
import weakref
from concurrent.futures import wait, FIRST_COMPLETED
from functools import partial

import unreal
import mineprep
from .assets import AssetStore, load_settings, save_settings
from .props import LoaderOptions
from . import composition

_instances = weakref.WeakSet()
CATEGORIES = {'ALL': ('全部', 'All'), 'Regular': ('常规', 'Regular'),
              'Babies': ('幼体', 'Babies'), 'Custom': ('自定义', 'Custom'),
              'Legacy': ('历史版本', 'Legacy'), 'Unsupported': ('未支持', 'Unsupported')}


def tr(zh, en):
    return mineprep.bilingual(zh, en)


def label(category):
    return tr(*CATEGORIES[category]) if category in CATEGORIES else category


def picture(parent, size):
    node = parent.image(size=size, color=unreal.LinearColor(1, 1, 1, 0), padding=1, align=(2, 2))
    node.hide(unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE)
    return node


def close_all():
    for instance in list(_instances):
        instance.destruct()


class VanillaMobLoader(mineprep.Mod):
    _unique_ = True
    _label_ = tr('MC原版生物加载器', 'Vanilla Mob Loader')

    def __init__(self, context=None):
        self.options = LoaderOptions()
        self.store = AssetStore()
        self.catalog = self.store.cached_catalog()
        settings = load_settings()

        self.category = settings.get('category', 'Regular') if self.catalog else 'Regular'
        if self.catalog and self.category not in ['ALL'] + self.catalog.categories:
            self.category = 'Regular' if 'Regular' in self.catalog.categories else self.catalog.categories[0]
        previous = settings.get('selected', []) if self.catalog else []
        if isinstance(previous, str):
            previous = [previous] if previous else []
        self.selected_keys = list(dict.fromkeys(k for k in previous if self.catalog and k in self.catalog.by_key))
        self.options.SavePath = str(settings.get('save_path', '/Game/mc/mob/')) if self.catalog else '/Game/mc/mob/'
        self.options.SaveName = str(settings.get('save_name', composition.automatic_name(self.selected_entries()))) if self.catalog else ''
        self.query = ''

        self.rows = []
        self.textures = {}
        self.attempted = set()
        self.refreshing = False
        self.closed = False
        self.tick_handle = None
        self._search_due = 0
        self._elapsed = 0
        self._size = (0, 0)
        self._grid_images = {}
        self._buttons = {}
        self._detail_image = None
        self._details_key = None
        self._missing = 0
        self._status = ''

        selected_entry = self.catalog.by_key.get(self.selected) if self.catalog else None
        self.expanded = {selected_entry.parent_key} if selected_entry and selected_entry.parent_key else set()
        self._cells = {}
        self._groups = {}
        self._badges = {}
        self._highlighted = {}
        self._visible_keys = set()
        _instances.add(self)

        try:
            super().__init__(context)
            self.tick_handle = unreal.register_slate_post_tick_callback(self._tick)
        except Exception:
            self.destruct()
            raise

    @property
    def selected(self):
        return self.selected_keys[0] if self.selected_keys else ''

    @selected.setter
    def selected(self, key):
        self.selected_keys = [key] if key else []

    def selected_entries(self):
        return [self.catalog.by_key[k] for k in self.selected_keys if k in self.catalog.by_key] if self.catalog else []

    def draw(self: mineprep.Mod, context=None):
        self.frame = self.layout.sizebox(1080, 660, padding=0)
        root = self.frame.col(align=(0, 0), padding=8)

        header = root.row(padding=(0, 4))
        header.text(tr('*需要联网下载资源，模型来自 Blockbench CEM Template Loader\n 按住Shift进行多选，按顺序组合模型',
                       '*Internet required to download resources from Blockbench CEM Template Loader'
                       '\n Hold Shift to select multiple mobs and combine them in order'),
                    size=10, wrap=True, align=(1, 2), fill=1)
        self.refresh_button = header.button(tr('刷新资源', 'Refresh assets'), size=12, on_clicked=self.refresh)

        searchrow = root.row(padding=(0, 5))
        self.search = searchrow.textbox(
            hint=tr('搜索名称或 ID…', 'Search name or ID…'),
            fill=1, align=(0, 2), on_text_changed=self._search_changed)
        self.clear_button = searchrow.button(tr('清除', 'Clear'), size=12, on_clicked=lambda: self.search.set_text(''))

        body = root.row(fill=1, align=(0, 0), padding=0)
        self.categories = body.sizebox(150, align=(0, 0), padding=(0, 4)).scrollbox(align=(0, 0)).col()

        middle = body.col(fill=1, align=(0, 0), padding=(8, 4))
        self.heading = middle.text('', size=15)
        self.grid_scroll = middle.scrollbox(fill=1, align=(0, 0), padding=0, clip=True)
        self.grid = self.grid_scroll.col(padding=0)

        right = body.sizebox(260, align=(0, 0), padding=(4, 4)).col(align=(0, 0))
        self.details_scroll = right.scrollbox(fill=1, align=(0, 0), clip=True)
        self.details = self.details_scroll.col()
        self._create_detail_widgets()
        right.prop(self.options, on_property_changed=self._options_changed)
        self.load_button = right.button(tr('放置生物', 'Place entity'), size=12, on_clicked=self.load_entity)
        self.load_button.set_is_enabled(False)
        self.reload_button = right.button(tr('重新加载生物', 'Reload entity'), size=12,
                                          on_clicked=self.reload_entity)
        self.reload_button.set_is_enabled(False)

        self.status = root.text('', size=11, wrap=True)

        self._build_categories()
        self._build_grid(rebuild=True)

    def _build_categories(self):
        self.categories.clear_children()
        self.category_buttons = {}

        for name in ['ALL'] + (self.catalog.categories if self.catalog else list(CATEGORIES)[1:]):
            button = self.categories.button(label(name), size=12, on_clicked=partial(self.set_category, name), padding=(2, 5))
            button.set_is_enabled(self.catalog is not None)
            button.set_background_color(unreal.LinearColor(0.3, 0.7, 1, 1) if name == self.category else unreal.LinearColor(1, 1, 1, 1))
            self.category_buttons[name] = button

        self.search.set_is_enabled(self.catalog is not None)
        self.clear_button.set_is_enabled(self.catalog is not None)

    def _search_changed(self, text):
        self.query = str(text)
        self._search_due = time.monotonic() + 0.15

    def set_category(self, name):
        self.category = name
        self._build_categories()
        self._build_grid()

    def _build_grid(self, rebuild=False):
        if rebuild:
            self.grid.clear_children()
            self._grid_images.clear()
            self._buttons.clear()
            self._cells.clear()
            self._groups.clear()
            self._badges.clear()
            self._highlighted.clear()
            self._visible_keys.clear()
            self.empty = self.grid.text('', size=14, wrap=True)

            for entry in self.catalog.entries if self.catalog else []:
                group = (entry.category, entry.group)
                if group not in self._groups:
                    section = self.grid.col(padding=0)
                    title = section.text(f'{label(entry.category)} {entry.group}', size=12, padding=(2, 8))
                    wrap = section.wrapbox(inner_padding=6, padding=0)
                    self._groups[group] = (section, title, wrap)

                wrap: mineprep.Layout = self._groups[group][2]
                cell = wrap.sizebox(124, 150, padding=0)
                button = cell.button(on_clicked=partial(self.select, entry.key), padding=0, align=(0, 0))
                content = button.col(padding=5, align=(0, 0))
                image = picture(content, 88)
                self._grid_images.setdefault(entry.id, []).append(image)

                title = content.text(entry.name, size=11, wrap=True, align=(2, 1), padding=(-5, 1))

                count = len(self.catalog.variants.get(entry.key, []))
                if entry.parent_key:
                    content.text(tr('变体', 'Variant'), size=9, align=(2, 1), padding=(0, 1))
                elif count:
                    self._badges[entry.key] = content.text('', size=9, align=(2, 1), padding=(0, 1))

                button.set_tool_tip_text(entry.name + (' · ' + entry.parent_name if entry.parent_name else ''))
                self._buttons[entry.key] = button
                self._cells[entry.key] = cell
                if entry.id in self.textures:
                    image.set_brush_resource_object(self.textures[entry.id])
                    self._fit_image(image, self.textures[entry.id], 88)

        self.rows = self.catalog.browse(self.category, self.query, self.expanded) if self.catalog else []
        visible = {e.key for e in self.rows}
        changed = set(self._cells) if rebuild else self._visible_keys ^ visible
        for key in changed:
            self._cells[key].hide(key not in visible)
        self._visible_keys = visible

        groups = {(e.category, e.group) for e in self.rows}
        for group, (section, title, wrap) in self._groups.items():
            section.hide(group not in groups)
            title.hide(not group[1] and self.category != 'ALL')

        for key, badge in self._badges.items():
            badge.set_text(('−' if key in self.expanded else '+') + str(len(self.catalog.variants[key])) + ' ' + str(tr('变体', 'variants')))

        valid = [k for k in self.selected_keys if self.catalog and k in self.catalog.by_key]
        if valid != self.selected_keys:
            self.selected_keys = valid
            self.options.SaveName = composition.automatic_name(self.selected_entries())
        count = sum(self.category == 'ALL' or e.category == self.category
                    for e in self.catalog.entries) if self.catalog else 0
        self.heading.set_text(f'{label(self.category)} · {count}')
        self.empty.hide(bool(self.rows))
        self.empty.set_text(tr('没有匹配的模板', 'No matching templates') if self.catalog else
                            tr('尚未下载模板目录，请点击「刷新资源」获取最新信息。', 'No template catalog. Click Refresh assets to download the latest information.'))

        if rebuild or self._details_key != tuple(self.selected_keys):
            self._build_details()
        self._highlight()
        self._save()
        self._update_status()

    def _save(self):
        if self.catalog and not save_settings(self.category, self.selected_keys, save_path=self.options.SavePath,
                                              save_name=self.options.SaveName, expansion=self.options.LayerExpansion,
                                              random_scale=self.options.RandomScale):
            self._status = str(tr('设置未保存：缓存目录不可写', 'Settings not saved: cache is not writable'))

    def select(self, key):
        state = unreal.InputLibrary.get_modifier_keys_state()
        self._select(key, unreal.InputLibrary.modifier_keys_state_is_shift_down(state))

    def _select(self, key, additive=False):
        if not self.catalog or key not in self.catalog.by_key:
            return
        old = list(self.selected_keys)
        if additive:
            if key in self.selected_keys:
                self.selected_keys.remove(key)
            else:
                self.selected_keys.append(key)
        else:
            self.selected_keys = [key]
        if old != self.selected_keys:
            self.options.SaveName = composition.automatic_name(self.selected_entries())
        if self.catalog.variants.get(key):
            if not additive and key in self.expanded:
                self.expanded.remove(key)
            elif key in self.selected_keys:
                self.expanded.add(key)
            self._build_grid()
        else:
            self._build_details()
            self._highlight()
            self._save()
            self._update_status()

    def _highlight(self):
        active = {key: min(i,1) for i,key in enumerate(self.selected_keys)}
        for key in self._highlighted.keys() | active.keys():
            if self._highlighted.get(key) == active.get(key):
                continue
            if key in self._buttons:
                color = ((.3,.7,1,1) if active[key] == 0 else (.35,1,.4,1)) if key in active else (1,1,1,1)
                self._buttons[key].set_background_color(unreal.LinearColor(*color))
        self._highlighted = active

    def _create_detail_widgets(self):
        # One widget tree per panel, reused across every selection and refresh.
        self._detail_empty = self.details.text(tr('选择模板查看详情', 'Select a template to view details'), size=13, wrap=True)
        self._detail_body = self.details.col()
        self._detail_image = picture(self._detail_body, 170)
        self._detail_name = self._detail_body.text('', size=17, wrap=True, align=(2, 1), padding=(0, 2))
        self._detail_info = info = self._detail_body.col()
        self._detail_fields = {}
        for key in ('id', 'category', 'textures', 'parent', 'description', 'model', 'filename'):
            text = info.text('', size=10 if key in ('textures', 'model', 'filename') else 11, wrap=True)
            self._detail_fields[key] = text

    def _build_details(self):
        self._details_key = tuple(self.selected_keys)
        entry = self.catalog.by_key.get(self.selected) if self.catalog else None
        enabled = bool(entry) and not self.refreshing
        self.load_button.set_is_enabled(enabled)
        self.reload_button.set_is_enabled(enabled)
        self.details_scroll.set_scroll_offset(0)
        self._detail_empty.hide(bool(entry))
        self._detail_body.hide(not entry)
        self._detail_info.hide(not self.options.ShowDetails)
        # Clear the old brush even if the new entry's thumbnail is unavailable.
        tex = self.textures.get(entry.id) if entry else None
        self._detail_image.set_brush_resource_object(tex)
        self._detail_image.set_color_and_opacity(unreal.LinearColor(1, 1, 1, 0))
        if not entry:
            return
        if tex:
            self._fit_image(self._detail_image, tex, 170)
        entries = self.selected_entries()
        self._detail_name.set_text(" + ".join(e.name for e in entries))
        values = {
            'id': entry.id,
            'category': label(entry.category),
            'textures': tr('仅使用主皮肤；额外贴图暂未应用', 'Primary skin only; additional textures are not applied')
                        if self.catalog.texture_count(entry) > 1 else '',
            'parent': tr('父模板：' + entry.parent_name, 'Parent: ' + entry.parent_name) if entry.parent_name else '',
            'description': entry.description,
            'model': 'Model: ' + entry.model,
            'filename': 'JEM: ' + entry.filename + '.jem',
        }
        if len(entries) > 1:
            values = dict.fromkeys(values, '')
            values['description'] = '\n+\n'.join(
                '\n'.join(filter(None, (e.name, e.id, str(label(e.category)), e.description,
                                          'Model: '+e.model, 'JEM: '+e.filename+'.jem',
                                          str(tr('仅使用主皮肤', 'Primary skin only')) if self.catalog.texture_count(e)>1 else '')))
                for e in entries)
        for key, value in values.items():
            self._detail_fields[key].set_text(value)
            self._detail_fields[key].hide(not bool(value))

    def _options_changed(self, name):
        if str(name) == 'ShowDetails' and getattr(self, '_detail_info', None):
            self._detail_info.hide(not self.options.ShowDetails)
        self._save()

    def reload_entity(self):
        self._load_entity(reload=True)

    def load_entity(self):
        self._load_entity()

    def _load_entity(self, reload=False):
        if self.refreshing or self.closed or not self.selected or not self.catalog:
            return

        from . import importer, skeletal
        self.refreshing = True
        self.refresh_button.set_is_enabled(False)
        self.load_button.set_is_enabled(False)
        self.reload_button.set_is_enabled(False)
        self.store.close()
        self.store = AssetStore()

        try:
            entries = self.selected_entries()
            folder, name = composition.destination(self.options.SavePath, self.options.SaveName)
            self.options.SaveName = name
            self._save()
            entry = composition.aggregate_entry(entries, name, self.options.LayerExpansion, self.options.RandomScale)
            placement = None if reload else importer.placement_target()
            target = importer.composition_target(entry, folder, name, reload)
            mesh = target[2]
            warnings = []
            if mesh is None or reload:
                skeletal.prerequisites()
                models = [self.catalog.model_data(e) for e in entries]
                skins = [None]*len(entries)
                with unreal.ScopedSlowTask(len(entries)+2, tr('正在加载模型', 'Loading model')) as progress:
                    progress.make_dialog(False)
                    futures = {self.store.submit(self.store.skin,e.id): i for i,e in enumerate(entries) if not e.textureless}
                    for i,result in self._wait_batch(futures,progress):
                        try:
                            skins[i] = result.result()
                        except Exception as exc:
                            warnings.append(entries[i].name+': '+str(tr('皮肤不可用', 'Skin unavailable'))+' '+str(exc)[:80])
                    future = self.store.submit(composition.combine, entries, models, skins,
                                               self.options.LayerExpansion, self.options.RandomScale)
                    for _,result in self._wait_batch({future:None},progress):
                        geo, conflicts = result.result()
                    if conflicts:
                        mineprep.panic(tr('组合骨骼冲突', 'Conflicting bones'),
                                       str(tr('继续运行将使用主模型的骨骼，忽略后续多选模型的冲突骨骼。',
                                          'Continue to keep the first selected bone definitions and ignore later conflicting bones.'))
                                       + '\n' + '\n'.join(conflicts))
                    from dataclasses import replace
                    from types import SimpleNamespace
                    sources = []
                    reserved = set()
                    for slot in geo.materials:
                        e = entries[slot['source']]
                        digest = slot['digest']
                        single = len(entries) == 1
                        owner = e if single else replace(e, key='skin:'+digest)
                        material_name = importer.skin_name(owner, target[0], composition.clean_name(e.id), reserved)
                        reserved.add(material_name.casefold())
                        path = self.store.skin_path(e.id) if not e.textureless else None
                        sources.append((owner, material_name, path, SimpleNamespace(single_sided=slot['single_sided'])))
                    mesh, build_warnings = skeletal.create_assets(entry, self.catalog.version, target, geo,
                                                                  reload=reload, material_sources=sources)
                    warnings += build_warnings
                    progress.enter_progress_frame(1)
                if any(self.catalog.texture_count(e)>1 for e in entries):
                    warnings.append(str(tr('每个模板仅使用主皮肤', 'Primary skin only for each template')))
                if self.store.unsaved:
                    warnings.append(str(tr('部分缓存未保存', 'Some cache was not saved')))

            if not reload:
                importer.place(mesh, self.options.ModelScale, placement)
            self._status = str(tr('已更新：', 'Updated: ') if reload else tr('已放置：', 'Placed: ')) + entry.name
            if warnings:
                self._status += ' · ' + '; '.join(warnings)
        except Exception as exc:
            self._status = str(tr('加载失败：', 'Import failed: ')) + str(exc)[:220]
            mineprep.warn('VanillaMobLoader', exc)
        finally:
            self.store.close()
            self.refreshing = False
            self.refresh_button.set_is_enabled(True)
            self.load_button.set_is_enabled(bool(self.selected))
            self.reload_button.set_is_enabled(bool(self.selected))
            self._update_status()

    def _wait_batch(self, futures, progress):
        pending = set(futures)
        while pending:
            done, pending = wait(pending, timeout=10, return_when=FIRST_COMPLETED)
            if not done:
                mineprep.panic(tr('资源下载停滞', 'Download stalled'),
                               tr('连续 10 秒没有资源下载完成。可继续等待，或停止本次刷新。',
                                  'No resource completed for 10 seconds. Continue waiting or stop this refresh.'))
            for future in done:
                self.store.futures.discard(future)
                progress.enter_progress_frame(1)
                yield futures[future], future

    def refresh(self):
        if self.refreshing or self.closed:
            return

        self.refreshing = True
        self.store.close()
        self.store = AssetStore()
        self.attempted.clear()
        self._missing = 0
        self.refresh_button.set_is_enabled(False)

        try:
            with unreal.ScopedSlowTask(1, tr('正在下载模板目录', 'Downloading catalog')) as progress:
                progress.make_dialog(False)
                future = self.store.submit(self.store.refresh_catalog)
                for _, result in self._wait_batch({future: None}, progress):
                    data, saved = result.result()

            self.catalog = data
            self.expanded.clear()
            if self.category not in ['ALL'] + data.categories:
                self.category = data.categories[0]
            self._build_categories()
            self._build_grid(rebuild=True)

            ids = list(dict.fromkeys(e.id for e in data.entries))
            with unreal.ScopedSlowTask(len(ids), tr('正在读取缓存并补齐缩略图', 'Loading cached thumbnails and downloading missing ones')) as progress:
                progress.make_dialog(False)
                futures = {self.store.submit(self.store.thumbnail, ident): ident for ident in ids}
                for ident, result in self._wait_batch(futures, progress):
                    try:
                        raw = result.result()
                    except Exception:
                        raw = None
                    if not self._apply_png(ident, raw or self.store.cached_png(ident)) and ident not in self.textures:
                        self._missing += 1
                    self.attempted.add(ident)

            self._status = str(tr('全部资源刷新完成', 'Asset refresh complete') if saved and not self.store.unsaved else
                               tr('刷新完成，但部分缓存未保存', 'Refresh complete; some cache was not saved'))
        except Exception as exc:
            self._status = str(tr('刷新停止，请重试', 'Refresh stopped; please retry')) + ': ' + str(exc)[:120]
            mineprep.warn('VanillaMobLoader', exc)
        finally:
            self.store.close()
            self.refreshing = False
            self.refresh_button.set_is_enabled(True)
            self.load_button.set_is_enabled(bool(self.selected))
            self.reload_button.set_is_enabled(bool(self.selected))
            self._update_status()

    def _update_status(self):
        messages = [self._status] if self._status else []
        if self._missing:
            messages.append(str(tr('部分缩略图不可用', 'Some thumbnails unavailable')))
        self.status.set_text(' · '.join(messages))
        self.status.hide(not messages)

    def _apply_png(self, ident, raw):
        if not raw:
            return False
        try:
            tex = unreal.RenderingLibrary.import_buffer_as_texture2d(mineprep.world(), raw)
            if tex is None:
                return False
            tex.set_editor_property('filter', unreal.TextureFilter.TF_NEAREST)
            self.textures[ident] = tex

            for image in self._grid_images.get(ident, []):
                image.set_brush_resource_object(tex)
                self._fit_image(image, tex, 88)

            entry = self.catalog.by_key.get(self.selected) if self.catalog else None
            if entry and entry.id == ident and self._detail_image:
                self._detail_image.set_brush_resource_object(tex)
                self._fit_image(self._detail_image, tex, 170)
            return True
        except Exception:
            return False

    @staticmethod
    def _fit_image(image, tex, size):
        image.set_color_and_opacity(unreal.LinearColor(1, 1, 1, 1))
        width, height = tex.blueprint_get_size_x(), tex.blueprint_get_size_y()
        scale = size / max(width, height, 1)
        image.set_desired_size_override(unreal.Vector2D(width * scale, height * scale))

    def _images_tick(self):
        # Prioritize selection and the approximate visible rows, then progress forward.
        columns = max(1, int(max(124, self._size[0] - 460) / 130))
        start = max(0, int(self.grid_scroll.get_scroll_offset() / 156) * columns - columns)
        candidates = self.rows[start:start + columns * 8]
        chosen = self.catalog.by_key.get(self.selected) if self.catalog else None
        if chosen:
            candidates = [chosen] + candidates

        budget = 4
        for entry in candidates:
            ident = entry.id
            if ident in self.attempted or ident in self.textures:
                continue
            if not budget:
                break
            budget -= 1
            self.attempted.add(ident)
            if self._apply_png(ident, self.store.cached_png(ident)):
                continue
        self._update_status()

    def _tick(self, delta):
        if self.closed or self.refreshing:
            return
        self._elapsed += delta
        if self._elapsed < 0.1:
            return
        self._elapsed = 0

        try:
            size = self.layout.get_local_size()
            desired = (max(780, int(size.x) - 8), max(480, int(size.y) - 8))
            if desired != self._size:
                self._size = desired
                self.frame.set_width_override(desired[0])
                self.frame.set_height_override(desired[1])

            if self._search_due and time.monotonic() >= self._search_due:
                self._search_due = 0
                self._build_grid()
            self._images_tick()
        except Exception as exc:
            mineprep.warn('VanillaMobLoader UI', exc)
            self.destruct()

    def destruct(self):
        if self.closed:
            return
        self.closed = True
        if self.tick_handle is not None:
            unreal.unregister_slate_post_tick_callback(self.tick_handle)
            self.tick_handle = None
        self.store.close()
        self.textures.clear()
        _instances.discard(self)
