try:
    import unreal
except ModuleNotFoundError:
    from mc_utils import Lazy as unreal

import os
import ast
import shutil
import mcvars
import json
import sys
from pathlib import Path
from functools import lru_cache
from copy import copy, deepcopy
from mc_utils import prints, debug, warn, send2trash
from contextlib import contextmanager


def loctext(key='', source_string=''):
    """获取本地化文本"""
    source_string = source_string or key
    return unreal.NSLOCTEXT('UObjectDisplayNames', key, source_string)

def nsloctext(namespace='UObjectDisplayNames', key='', source_string=''):
    """按命名空间获取本地化文本"""
    source_string = source_string or key
    return unreal.NSLOCTEXT(namespace, key, source_string)


def loctable_col(block=1, lang=None):
    """获取本地化缓存中的列"""
    try:
        lang = lang or int(mcvars.LocalizationCache[0][0].split(',')[0])
        col_index = int(mcvars.LocalizationCache[0][0].split(',')[block])
        return mcvars.LocalizationCache[lang+col_index]
    except:
        return []


def bilingual(chinese: str, english: str=''):
    """双语文本，已废弃，建议升级为i18n"""
    text = unreal.TextLibrary.find_text_in_live_table_advanced('UObjectDisplayNames', chinese, chinese)
    if not text or mcvars.DebugMode:
        english = english or chinese
        lang = unreal.InternationalizationLibrary.get_current_language()
        if unreal.InternationalizationLibrary.get_suitable_culture(['zh'], lang, ''):
            lang = 'zh'
        polyglot = unreal.PolyglotTextData(category = unreal.LocalizedTextSourceCategory.EDITOR,
                                   namespace = 'UObjectDisplayNames',
                                   key = chinese,
                                   native_string = chinese,
                                   localized_strings = {'en': english, lang:english, 'zh': chinese},
                                   is_minimal_patch = False)
        text = unreal.TextLibrary.polyglot_data_to_text(polyglot)

    return loctext(chinese)


def localize(source: str, *args, **kwargs):
    """立刻注入本地化翻译, args对应mcvars.Languages的各语言翻译, kwargs可以指定namespace, key和自定义语言  
    如mineprep.localize(原名, 中文, 英文, 繁体中文，... , namespace='UObjectDisplayNames', key=原名)
    """
    namespace = kwargs.get('namespace', 'UObjectDisplayNames')
    key = kwargs.get('key', source)
    localizations = {lang: arg for lang, arg in zip(mcvars.Languages, args)}
    localizations.update({k: v for k, v in kwargs.items() if k not in ['namespace', 'key']})
    polyglot = unreal.PolyglotTextData(category = unreal.LocalizedTextSourceCategory.EDITOR,
                    namespace = namespace,
                    key = key,
                    native_string = source,
                    localized_strings = localizations,
                    is_minimal_patch = False)
    if int(mcvars.DebugMode) >= 2:
        unreal.log(f'本地化: namespace={namespace}, key={key}, source_string={source} -> {args}')
    return unreal.TextLibrary.polyglot_data_to_text(polyglot)


class tooltip(str):
    """多语言工具提示预设"""
    def __new__(cls, key, name=None):
        return super().__new__(cls, cls.tooltips[key](name))

    tooltips = {
        'help': lambda x: i18n.help.overview(
            '查看输出日志或前往https://github.com/piggestpig/Unreal-Mineprep/wiki/Mineprep-Python-API获取更多信息',
            'Check Output Log or go to https://github.com/piggestpig/Unreal-Mineprep/wiki/Mineprep-Python-API for more information'),
        '所有插件面板': lambda x: i18n.help.panels(
            '【mineprep.panel() 可用的对象->类别】',
            'Available objects -> classes for mineprep.panel()'),
        '所有快捷键': lambda x: i18n.help.hotkeys(
            '【mineprep.hotkey() 全部快捷键】',
            'All shortcuts for mineprep.hotkey()'),
        '未找到面板': lambda x: i18n.help.panel_missing(
            '未找到"{name}", 运行 mineprep.panel() 在日志中打印所有控件',
            'No widget found for "{name}", run mineprep.panel() to print all available widgets').format(name=str(x)),
        '你可能在寻找': lambda x: i18n.help.suggestions('你可能在寻找:', 'You may be looking for:')
    }


class Internationalization:
    """运行时收集并缓存本地化文本；下标指定 namespace，属性链组成 key。

    推荐用法：i18n('中文', 'English')，i18n('中文')，I18N('English')  
    可直接替代旧的bilingual。高级用法如下  
    i18n.queue.start('开始', 'Start', '開始', ja='スタート')  
    i18n['Shared'].done('已完成 {count} 项', 'Completed {count} jobs').format(count=3)  
    i18n('取消', 'Cancel', namespace='Shared', key='cancel')  
    I18N.queue.start('Start', '开始')  

    位置文本按 langs 映射，语言关键字覆盖本次调用的对应文本。  
    langs 默认复制 mcvars.Languages；I18N 将英语移到首位。  
    新语言自动补入词典，已有译文（包括空译文）以 JSON 为准。  
    check=True 默认检查源文差异并记日志，DebugMode 下同时警告。  
    check=False 平时跳过源文差异检查，DebugMode 下仅写普通日志。  
    JSON 格式为 {namespace: {key: {语言代码: 文本, '_native': 源语言}}}。  
    _native 省略时为 zh，其他下划线字段也视为元数据；语言排列不影响源语言。  
    zh 提供通用中文回退；zh-Hans / zh-Hant 可作为更具体的译文覆盖。  
    缺少译文时回退到原文，不自动填充译文。  
    首次访问词典时统一注册已有文本；新词条立即合并写回，已有译文以 JSON 为准。  
    PropertyGroup.localize 共用批量收集入口，一次合并写回其属性文本。  
    检测到 unreal.mineprep.register_polyglot_texts 时使用 C++ 批量注册，否则逐条注册。  
    file 指定 JSON 路径（相对当前工作目录），构造时规范化，首次补词时创建文件及父目录。  
    显式文件默认以所在文件夹名为 namespace；公共 Python 目录仍用 Core。  
    属性链、下标及 PropertyGroup.localize 继承文件配置；建议同时指定稳定的 namespace。  
    不传 file 时仍根据调用来源自动定位；临时脚本默认仅在内存中使用 UObjectDisplayNames。  
    数据读写失败时保留原文件，本次运行只在内存中收集和翻译。  
    from_data(data, namespace=...) 装载 {key: 词条记录}，不读写文件或收集文本。  
    同 namespace 再次装载会替换快照，旧实例和节点也查询新快照。  
    内存模式的首参数仅作缺词 fallback；命中时不比较原文，缺词不注册。  
    刷新后再次调用 Class.localize(instance) 更新属性绑定。  
    修改 JSON 后使用 mineprep.reload() 重新加载。UE 文本操作应在主线程执行。  
    """

    _catalogs = {}
    _texts = {}
    _readonly = set()
    _reported = set()
    _memory = object()  # 与文件路径及临时脚本的 None 缓存分开

    def __init__(self, namespace=None, key='', file=None, *, langs=None):
        self._namespace = namespace
        self._key = key
        self._file = Path(file).resolve() if file is not None else None
        if self._file is not None and self._file.suffix.lower() != '.json':
            raise ValueError('file 须为 JSON 文件路径')
        self._source = None
        self._memory_mode = False
        self._langs = tuple(mcvars.Languages if langs is None else langs)

    @classmethod
    def from_data(cls, data, *, namespace):
        """复制并批量装载只读内存词典；无效数据警告并保留该 namespace 的旧快照。"""
        if not isinstance(namespace, str) or not namespace:
            raise ValueError('from_data 需要非空字符串 namespace')
        instance = cls(namespace=namespace)
        instance._memory_mode = True
        try:
            cls._validate(data)
            data = deepcopy(data)
        except (ValueError, TypeError) as exc:
            warn(f'i18n {namespace}: 内存词典无效，保留旧快照', exc)
            return instance
        cls._sync(cls._memory, {**cls._catalogs.get(cls._memory, {}), namespace: data})
        return instance

    def __getattr__(self, key):
        if key.startswith('_'):
            raise AttributeError(key)
        node = copy(self)
        node._source = self._source or sys._getframe(1).f_code.co_filename
        node._key = f'{self._key}.{key}' if self._key else key
        return node

    def __getitem__(self, namespace):
        node = copy(self)
        node._source = self._source or sys._getframe(1).f_code.co_filename
        node._namespace = namespace
        return node

    @staticmethod
    @lru_cache(maxsize=None)
    def _location(filename):
        file = Path(filename)
        if file.suffix != '.py':
            return None, 'UObjectDisplayNames'
        file = file.resolve()
        root = next((p for p in reversed(file.parents)
                     if (p / '__init__.py').is_file()), None)
        if root is not None:
            return root / 'i18n.json', root.name
        namespace = 'Core' if file.parent == Path(__file__).resolve().parent else file.stem
        return file.parent / 'i18n.json', namespace

    @staticmethod
    def _validate(entries):
        """文件及内存词典共用的词条输入校验。"""
        if not isinstance(entries, dict):
            raise ValueError('词典需要 {key: 词条记录}')
        for key, translations in entries.items():
            if not isinstance(key, str) or not key or not isinstance(translations, dict):
                raise ValueError('词条需要非空字符串 key 和语言字典')
            native = translations.get('_native', 'zh')
            if (not isinstance(native, str) or not native or native.startswith('_')
                    or not translations.get(native)
                    or not all(isinstance(lang, str) and (lang.startswith('_') or isinstance(text, str))
                               for lang, text in translations.items())):
                raise ValueError('词条需要源语言对应的非空原文和字符串译文')

    @classmethod
    def _read(cls, path):
        if path is None or path in cls._readonly:
            return cls._catalogs.get(path, {})
        try:
            data = json.loads(path.read_text(encoding='utf-8-sig'))
            # 在文件输入边界校验，后续注册直接使用词典内容。
            for entries in data.values():
                cls._validate(entries)
            return data
        except FileNotFoundError:
            return cls._catalogs.get(path, {})
        except (OSError, ValueError, AttributeError, TypeError) as exc:
            cls._readonly.add(path)
            warn(f'{path}: i18n 读取失败，本次仅在内存中收集', exc)
            return cls._catalogs.get(path, {})

    @classmethod
    def _register_polyglots(cls, data):
        """普通词条与属性桥接共用批量接口；兼容未编译新函数的插件。"""
        register = getattr(getattr(unreal, 'mineprep', None), 'register_polyglot_texts', None)
        return (register(data) if callable(register) else
                [unreal.TextLibrary.polyglot_data_to_text(item) for item in data])

    @classmethod
    def _register(cls, path, entries):
        data = []
        for namespace, key, translations in entries:
            native = translations.get('_native', 'zh')
            data.append(unreal.PolyglotTextData(
                category=unreal.LocalizedTextSourceCategory.EDITOR,
                native_culture=native, namespace=namespace, key=key,
                native_string=translations[native],
                localized_strings={lang: text for lang, text in translations.items()
                                   if not lang.startswith('_') and text},
                is_minimal_patch=False,
            ))
        texts = cls._register_polyglots(data)
        cls._texts.update(((path, namespace, key), text)
                          for (namespace, key, _), text in zip(entries, texts, strict=True))

    @classmethod
    def _sync(cls, path, data):
        previous = cls._catalogs.get(path, {})
        changed = []
        for namespace, entries in previous.items():
            for key in entries.keys() - data.get(namespace, {}).keys():
                cls._texts.pop((path, namespace, key), None)
        for namespace, entries in data.items():
            for key, translations in entries.items():
                if ((path, namespace, key) not in cls._texts
                        or translations != previous.get(namespace, {}).get(key)):
                    changed.append((namespace, key, translations))
        if changed:
            cls._register(path, changed)
        cls._catalogs[path] = data

    @classmethod
    def _load(cls, path):
        if path not in cls._catalogs:
            cls._sync(path, cls._read(path))
        return cls._catalogs[path]

    @classmethod
    def _save(cls, path, data):
        if path is None or path in cls._readonly:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix('.json.tmp')
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n',
                                 encoding='utf-8')
            temporary.replace(path)
        except OSError as exc:
            cls._readonly.add(path)
            warn(f'{path}: i18n 保存失败，本次仅在内存中收集', exc)

    def _collect(self, file, supplied_entries, namespace=None, *, native_cultures=None, check=True):
        """批量合并，一次写回；native_cultures 可覆盖各个新词条的源语言。"""
        native = self._langs[0]
        if self._memory_mode:
            namespace = self._namespace if namespace is None else namespace
            entries = self._catalogs.get(self._memory, {}).get(namespace, {})
            records = {}
            for key, supplied in supplied_entries.items():
                culture = (native_cultures or {}).get(key, native)
                records[key] = entries[key] if key in entries else {
                    '_native': culture, culture: supplied.get(culture) or key,
                }
            return self._memory, namespace, records
        if self._file is None:
            path, default_namespace = self._location(self._source or file)
        else:
            path = self._file
            default_namespace = 'Core' if path.parent == Path(__file__).resolve().parent else path.parent.name
        if namespace is None:
            namespace = self._namespace if self._namespace is not None else default_namespace

        data = self._load(path)
        entries = data.get(namespace, {})
        if any(key not in entries or any(lang not in entries[key] for lang in supplied)
               for key, supplied in supplied_entries.items()):
            # 写入前重读；复制修改的层级，让内存／只读模式也能比较新旧词条。
            data = self._read(path).copy()
            entries = data[namespace] = data.get(namespace, {}).copy()
            changed = False
            for key, supplied in supplied_entries.items():
                translations = entries.get(key)
                if translations is None:
                    entry_native = native_cultures.get(key, native) if native_cultures else native
                    source = supplied.get(entry_native)
                    if source is None:
                        warn(f'i18n {namespace}.{key} 缺少原文，暂用 key 显示')
                    translations = {} if entry_native == 'zh' else {'_native': entry_native}
                    translations[entry_native] = source or key
                merged = {**supplied, **translations}
                if entries.get(key) != merged:
                    entries[key] = merged
                    changed = True
            if changed:
                self._save(path, data)
            self._sync(path, data)

        if check or mcvars.DebugMode:
            for key, supplied in supplied_entries.items():
                translations = entries[key]
                native = translations.get('_native', 'zh')
                original = supplied.get(native)
                if original and translations[native] != original:
                    report = (path, namespace, key, native, original, translations[native],
                              bool(mcvars.DebugMode), check)
                    if report not in self._reported:
                        debug(f'i18n {namespace}.{key} 使用词典原文 '
                              f'{translations[native]!r} ({native})，代码原文为 {original!r}',
                              autolog=check, warning=check)
                        self._reported.add(report)
        return path, namespace, {key: entries[key] for key in supplied_entries}

    def __call__(self, source=None, *texts, namespace=None, key=None, check=True, **languages):
        if len(texts) + 1 > len(self._langs):
            raise TypeError('位置文本数量超过 langs 配置，请使用语言关键字或扩展 langs')
        if any(lang.startswith('_') for lang in languages):
            raise TypeError('下划线开头的字段是词典元数据，不能作为语言参数')
        if self._memory_mode:
            key = key if key is not None else self._key or source
            namespace = self._namespace if namespace is None else namespace
            text = self._texts.get((self._memory, namespace, key))
            return text if text is not None else unreal.Text(source or key or '')
        supplied = dict(zip(self._langs, (source, *texts)))
        supplied.update(languages)
        supplied = {lang: text for lang, text in supplied.items() if text}
        source = supplied.get(self._langs[0])
        key = key if key is not None else self._key or source
        if not key:
            return unreal.Text(source or '')
        file = self._source or sys._getframe(1).f_code.co_filename
        path, namespace, _ = self._collect(file, {key: supplied}, namespace, check=check)
        return self._texts[path, namespace, key]


i18n = Internationalization()
I18N = Internationalization(langs=('en', *(lang for lang in mcvars.Languages if lang != 'en')))


def _i18n_node(node, namespace):
    """只认标准名称及其属性／下标链，不追踪变量。"""
    name = ast.unparse(node)
    if name in ('i18n', 'I18N', 'mineprep.i18n', 'mineprep.I18N'):
        langs = list(mcvars.Languages)
        if name.endswith('I18N'):
            langs = ['en', *(lang for lang in langs if lang != 'en')]
        return namespace, '', langs
    if isinstance(node, (ast.Attribute, ast.Subscript)):
        parent = _i18n_node(node.value, namespace)
        if parent:
            namespace, key, langs = parent
            if isinstance(node, ast.Subscript):
                namespace = ast.literal_eval(node.slice)
            else:
                key = f'{key}.{node.attr}' if key else node.attr
            return namespace, key, langs


def _i18n_arguments(node):
    args, options = [], {}
    for arg in node.args:
        if isinstance(arg, ast.Starred):
            args.extend(ast.literal_eval(arg.value))
        else:
            args.append(ast.literal_eval(arg))
    for kw in node.keywords:
        value = ast.literal_eval(kw.value)
        options.update(value if kw.arg is None else {kw.arg: value})
    return args, options


def _i18n_properties(call, classes, namespace):
    """简单的同文件 PropertyGroup；复杂声明交给 agent 查看。"""
    cls = classes[ast.unparse(call.func.value)]
    if len(call.args) > 1 or len(cls.bases) != 1:
        raise ValueError('旧式 localize 或复杂继承')
    config = _i18n_node(call.args[0] if call.args else ast.Name(id='I18N', ctx=ast.Load()), namespace)
    if config is None:
        raise ValueError('动态或旧式 localize')
    namespace, prefix, langs = config
    _, options = _i18n_arguments(ast.Call(func=call.func, args=[], keywords=call.keywords))
    if options.keys() - {'tooltip'}:
        raise ValueError('不支持的 localize 参数')
    tooltip = options.get('tooltip', False)
    language = 'en' if tooltip is True else tooltip
    if tooltip is not False and (not isinstance(language, str) or not language or language.startswith('_')):
        raise ValueError('无效的 tooltip 语言')
    prefix, result = prefix or cls.name, []
    for field in cls.body:
        target = field.target if isinstance(field, ast.AnnAssign) else (
            field.targets[0] if isinstance(field, ast.Assign) and len(field.targets) == 1 else None)
        if not isinstance(target, ast.Name) or target.id.startswith('_') or isinstance(field.value, ast.Lambda):
            continue
        meta = {}
        if isinstance(field.value, ast.Tuple):
            metadata = field.value.elts[1]
            for key, value in zip(metadata.keys, metadata.values):
                key = ast.literal_eval(key).lower()
                if key in ('displayname', 'category', 'tooltip', 'shorttooltip'):
                    meta[key] = ast.literal_eval(value)
        result.append((namespace, f'{prefix}.{target.id}', {langs[0]: meta.get('displayname', target.id)}, langs[0]))
        for segment in meta.get('category', cls.name).split('|'):
            if segment:
                result.append((namespace, f'{prefix}.category.{segment}', {langs[0]: segment}, langs[0]))
        if tooltip is not False:
            for name, suffix in (('tooltip', 'tooltip'), ('shorttooltip', 'short_tooltip')):
                if meta.get(name):
                    result.append((namespace, f'{prefix}.{target.id}.{suffix}', {language: meta[name]}, language))
    return result


def _offline_i18n(path, languages=None, write=False):
    path = Path(path).resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    if not path.is_dir() and path.suffix != '.py':
        raise ValueError('path 须为 Python 文件或 mod 文件夹')
    if isinstance(languages, str):
        raise TypeError('languages 须为语言代码序列')
    languages = list(('zh', 'en') if languages is None else languages)
    report = {name: [] for name in ('added', 'untranslated', 'unused', 'dynamic', 'errors')}
    files, catalogs, scopes, entries, conflicts = [], set(), {}, {}, set()
    if path.is_file():
        files = [path]
    else:
        for folder, dirs, names in os.walk(path):
            dirs[:] = sorted(d for d in dirs if d not in {'.git', '__pycache__', '.venv', 'venv', 'node_modules', 'Intermediate', 'Saved'})
            files.extend(Path(folder) / name for name in sorted(names)
                         if name.endswith('.py') or name in ('i18n.json', 'mod_manifest.toml'))

    def add(namespace, key, texts, native, source):
        if not key:
            return
        if (not isinstance(namespace, str) or not isinstance(key, str)
                or any(not isinstance(lang, str) or lang.startswith('_') or not isinstance(text, str)
                       for lang, text in texts.items())):
            raise ValueError('namespace、key 和语言文本须为字符串')
        identity = catalog, namespace, key
        scopes.setdefault(catalog, set()).add(namespace)
        entry = entries.setdefault(identity, {'native': native, 'texts': {}, 'source': source})
        if texts and not entry['texts']:
            entry['native'] = native
        if any(lang in entry['texts'] and entry['texts'][lang] != text for lang, text in texts.items()):
            if identity not in conflicts:
                report['errors'].append({'file': source, 'message': f'{namespace}.{key} 源码文本冲突，跳过补写'})
            conflicts.add(identity)
        entry['texts'].update(texts)

    for file in files:
        if file.name == 'i18n.json':
            catalogs.add(file)
            continue
        catalog, namespace = Internationalization._location(str(file.with_name('__init__.py') if file.suffix == '.toml' else file))
        catalogs.add(catalog)
        scopes.setdefault(catalog, set()).add(namespace)
        try:
            source = file.read_text(encoding='utf-8-sig')
            if file.suffix == '.toml':
                import tomllib
                data = tomllib.loads(source)
                if data.get('schema_version') != 2 or not file.with_name('__init__.py').is_file():
                    raise ValueError('仅支持 schema_version=2 的文件夹 mod 清单')
                for key in ('Name', 'Description'):
                    value = data.get(key, '')
                    if isinstance(value, str):
                        continue
                    texts = dict(zip(mcvars.Languages, value)) if isinstance(value, list) else value
                    if not isinstance(texts, dict) or not texts.get(mcvars.Languages[0]):
                        raise ValueError(f'{key} 缺少清单原文')
                    add(namespace, f'mod_info.{key}', {lang: text for lang, text in texts.items() if text},
                        mcvars.Languages[0], str(file))
                continue
            tree = ast.parse(source, filename=str(file))
        except (OSError, ValueError, SyntaxError) as exc:
            report['errors'].append({'file': str(file), 'message': str(exc)})
            continue
        classes = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
                   and any(ast.unparse(base) in ('PropertyGroup', 'mineprep.PropertyGroup') for base in node.bases)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            location = f'{file}:{node.lineno}'
            try:
                config = _i18n_node(node.func, namespace)
                if config:
                    ns, prefix, langs = config
                    args, options = _i18n_arguments(node)
                    if len(args) > len(langs):
                        raise ValueError('位置文本超出默认语言数量')
                    if 'source' in options:
                        args = [options.pop('source')]
                    override = options.pop('namespace', None)
                    ns = ns if override is None else override
                    key = options.pop('key', None)
                    options.pop('check', None)
                    texts = {lang: text for lang, text in {**dict(zip(langs, args)), **options}.items() if text}
                    key = key if key is not None else prefix or texts.get(langs[0], '')
                    add(ns, key, texts, langs[0], location)
                elif isinstance(node.func, ast.Attribute) and node.func.attr == 'localize':
                    for ns, key, texts, native in _i18n_properties(node, classes, namespace):
                        add(ns, key, texts, native, location)
                elif ast.unparse(node.func) in ('Internationalization', 'mineprep.Internationalization'):
                    raise ValueError('自定义实例不静态展开')
            except (ValueError, TypeError, KeyError, AttributeError, IndexError):
                report['dynamic'].append({'file': str(file), 'line': node.lineno,
                                          'source': ast.get_source_segment(source, node)})

    for catalog in sorted(catalogs):
        try:
            data = json.loads(catalog.read_text(encoding='utf-8-sig')) if catalog.exists() else {}
            for rows in data.values():
                for key, record in rows.items():
                    native = record.get('_native', 'zh')
                    if (not key or not isinstance(native, str) or not native or native.startswith('_')
                            or not isinstance(record.get(native), str) or not record[native]
                            or any(not isinstance(text, str) for lang, text in record.items() if not lang.startswith('_'))):
                        raise ValueError('词典需要非空原文和字符串译文')
        except (OSError, ValueError, AttributeError, TypeError) as exc:
            report['errors'].append({'file': str(catalog), 'message': str(exc)})
            continue
        updated = {ns: rows.copy() for ns, rows in data.items()}
        for (owner, ns, key), entry in entries.items():
            if owner != catalog or (owner, ns, key) in conflicts:
                continue
            existing = data.get(ns, {}).get(key)
            if existing is None:
                native = entry['native']
                existing = {} if native == 'zh' else {'_native': native}
                existing[native] = entry['texts'].get(native) or key
            merged = {**entry['texts'], **existing}
            if merged != data.get(ns, {}).get(key):
                updated.setdefault(ns, {})[key] = merged
                report['added'].append({'file': str(catalog), 'namespace': ns, 'key': key,
                                        'texts': merged, 'source': entry['source']})
        for ns, rows in data.items():
            if (path.is_file() or not catalog.is_relative_to(path)) and ns not in scopes.get(catalog, ()):
                continue  # 共享词典只比较本次涉及的 namespace。
            for key, record in rows.items():
                item = {'file': str(catalog), 'namespace': ns, 'key': key}
                if (catalog, ns, key) not in entries:
                    report['unused'].append(item)
                missing = [lang for lang in languages if not record.get(lang)]
                if missing:
                    report['untranslated'].append({**item, 'languages': missing})
        if write and updated != data:
            temporary = catalog.with_suffix('.json.tmp')
            try:
                temporary.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                temporary.replace(catalog)
            except OSError as exc:
                report['errors'].append({'file': str(catalog), 'message': str(exc)})
    return report


def collect_i18n(path, *, write=False):
    """离线收集标准写法；默认预览，write=True 只补充词条／语言，已有 JSON 优先。

    返回 added、untranslated、unused、dynamic、errors 列表。
    不执行源码或注册 Text；补写后按正常流程 reload。unused 仅供检索，不自动删除。
    """
    return _offline_i18n(path, write=write)


def check_i18n(path, *, languages=None):
    """只读检查，返回结构同 collect_i18n；默认检查 zh、en，可显式指定其他语言。"""
    return _offline_i18n(path, languages)


_ENGINE_CULTURES = frozenset({
    'ar', 'de', 'en', 'es', 'es-419', 'fr', 'it', 'ja', 'ko',
    'pl', 'pt-br', 'ru', 'tr', 'zh-hans',
})


def copy_engine_culture(source, target, dry_run=False):
    """把引擎里已有的 source 文化目录复制为 target。dry_run 只打印将写入的路径。

    引擎自带的 14 种语言不会写入。其他语言的目标目录若已存在，先移到回收站再复制。
    """
    import mineprep

    if not source or not target or source == target:
        mineprep.prints(i18n.culture.same_source_target('源语言和目标语言必须不同', 'Source and target languages must differ'))
        return []
    if target.casefold() in _ENGINE_CULTURES:
        mineprep.prints(i18n.culture.builtin_target(
            '{target} 是引擎自带语言，不会覆盖',
            '{target} is built into the engine and will not be overwritten').format(target=str(target)))
        return []

    engine = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.engine_dir()))
    destinations = []
    seen = set()
    skip_dirs = {'Binaries', 'Intermediate', 'Source', 'DerivedDataCache', 'Saved', '.git'}
    for root in (engine / 'Content' / 'Localization', engine / 'Plugins'):
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if name not in skip_dirs]
            if Path(dirpath).name != source or not any(name.endswith('.locres') for name in filenames):
                continue
            folder = Path(dirpath).resolve()
            if folder in seen:
                continue
            seen.add(folder)
            destination = folder.parent / target
            if destination.exists() and destination.resolve().name.casefold() in _ENGINE_CULTURES:
                continue
            if not dry_run and destination.exists():
                send2trash(destination)
            if not dry_run:
                shutil.copytree(folder, destination)
            destinations.append(str(destination))

    message = (i18n.culture.will_copy(
        '将复制 {count} 个目录：{source} → {target}', 'Will copy {count} directories: {source} → {target}')
        if dry_run else i18n.culture.copied(
            '已复制 {count} 个目录：{source} → {target}', 'Copied {count} directories: {source} → {target}'))
    mineprep.prints(message.format(count=str(len(destinations)), source=str(source), target=str(target)),
                    *destinations, duration=10)
    return destinations


def editor_has_culture(culture):
    """编辑器是否有该语言的翻译。精准匹配返回 True，父文化返回其名字，都没有返回 False。"""
    engine = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.engine_dir()))
    cultures, skip = [], {'Binaries', 'Intermediate', 'Source', 'DerivedDataCache', 'Saved', '.git'}
    for root in (engine / 'Content' / 'Localization', engine / 'Plugins'):
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if name not in skip]
            if any(name.endswith('.locres') for name in filenames):
                cultures.append(Path(dirpath).name)
    match = unreal.InternationalizationLibrary.get_suitable_culture(cultures, culture, '')
    language = culture.split('-', 1)[0].casefold()
    if not match or match.split('-', 1)[0].casefold() != language:
        return False
    return True if match.casefold() == culture.casefold() else match

