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
    text = unreal.TextLibrary.find_text_in_live_table_advanced('UObjectDisplayNames', key, source_string)
    return str(text) or key

def nsloctext(namespace='UObjectDisplayNames', key='', source_string=''):
    """按命名空间获取本地化文本"""
    source_string = source_string or key
    text = unreal.TextLibrary.find_text_in_live_table_advanced(namespace, key, source_string)
    return str(text) or key


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
    if 'zh-' in unreal.InternationalizationLibrary.get_current_language():
        return text or chinese
    else:
        return text or english


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