import unreal
import mcvars
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


def bilingual(chinese: str, english: str):
    """双语文本"""
    text = unreal.TextLibrary.find_text_in_live_table_advanced('UObjectDisplayNames', chinese, chinese)
    if not text or mcvars.DebugMode:
        lang = unreal.InternationalizationLibrary.get_current_language()
        polyglot = unreal.PolyglotTextData(category = unreal.LocalizedTextSourceCategory.EDITOR,
                                   namespace = 'UObjectDisplayNames',
                                   key = chinese,
                                   native_string = chinese,
                                   localized_strings = {'en': english, lang:english, 'zh-Hans': chinese},
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
    """双语工具提示预设"""
    def __new__(cls, key, name=None):
        return super().__new__(cls, cls.tooltips[key](name))

    tooltips = {
        'help': lambda x: bilingual(
            '查看输出日志或前往https://github.com/piggestpig/Unreal-Mineprep/wiki/Mineprep-Python-API获取更多信息',
            'Check Output Log or go to https://github.com/piggestpig/Unreal-Mineprep/wiki/Mineprep-Python-API for more information'),
        '所有插件面板': lambda x: bilingual(
            '【mineprep.panel() 可用的对象->类别】',
            'Available objects -> classes for mineprep.panel()'),
        '未找到面板': lambda x: bilingual(
            f'未找到"{x}", 运行 mineprep.panel() 在日志中打印所有控件',
            f'No widget found for "{x}", run mineprep.panel() to print all available widgets'),
        '你可能在寻找': lambda x: bilingual('你可能在寻找:', 'You may be looking for:')
    }