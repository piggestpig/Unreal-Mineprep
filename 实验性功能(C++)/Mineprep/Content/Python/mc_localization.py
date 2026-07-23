import unreal
from contextlib import contextmanager

KernelLanguage = None
LocalizationCache = None

@contextmanager
def language(lang=None):
    """切换内部语言"""
    global KernelLanguage
    map = {['zh-Hans','zh-CN','zh',1]: 1,
           ['en','English',2]: 2,
           ['zh-Hant','zh-TW','zh-HK',3]: 3}
    for key, value in map.items():
        if lang.lower() in key.lower():
            KernelLanguage = value
            break

    yield
    KernelLanguage = None



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
    global LocalizationCache
    try:
        lang = lang or int(LocalizationCache[0][0].split(',')[0])
        col_index = int(LocalizationCache[0][0].split(',')[block])
        return LocalizationCache[lang+col_index]
    except:
        return []


def bilingual(chinese, english):
    """双语文本"""
    text = unreal.TextLibrary.find_text_in_live_table_advanced('UObjectDisplayNames', chinese, chinese)
    if not text:
        polyglot = unreal.PolyglotTextData(category = unreal.LocalizedTextSourceCategory.EDITOR,
                                   namespace = 'UObjectDisplayNames',
                                   key = chinese,
                                   native_string = chinese,
                                   localized_strings = {'zh-Hans': chinese, 'en': english},
                                   is_minimal_patch = False)
        text = unreal.TextLibrary.polyglot_data_to_text(polyglot)

    return loctext(chinese)


class tooltip(str):
    """双语工具提示预设"""
    def __new__(cls, key, name=None):
        return super().__new__(cls, cls.tooltips[key](name))

    tooltips = {
        'help': lambda x: bilingual(
            '查看输出日志或前往https://github.com/piggestpig/Unreal-Mineprep/wiki/Mineprep-Python-API获取更多信息',
            'Check Output Log or go to https://github.com/piggestpig/Unreal-Mineprep/wiki/Mineprep-Python-API for more information'),
        '所有插件面板': lambda x: bilingual(
            '【unreal.mineprep.panel() 可用的对象->类别】',
            'Available objects -> classes for unreal.mineprep.panel()'),
        '未找到面板': lambda x: bilingual(
            f'未找到"{x}", 运行 unreal.mineprep.panel() 在日志中打印所有控件',
            f'No widget found for "{x}", run unreal.mineprep.panel() to print all available widgets'),
        '你可能在寻找': lambda x: bilingual('你可能在寻找:', 'You may be looking for:')
    }