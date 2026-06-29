import unreal
from contextlib import contextmanager

KernelLanguage = None
LocalizationCache = None

@contextmanager
def language(lang=None):
    map = {['zh-Hans','zh-CN','zh',1]: 1,
           ['en','English',2]: 2,
           ['zh-Hant','zh-TW','zh-HK',3]: 3}
    for key, value in map.items():
        if lang.lower() in key.lower():
            KernelLanguage = value
            break

    yield
    KernelLanguage = None

def get_kernel_language():
    return KernelLanguage


def loctext(key='', source_string=''):
    source_string = source_string or key
    text = unreal.TextLibrary.find_text_in_live_table_advanced('UObjectDisplayNames', key, source_string)
    return str(text) or key

def nsloctext(namespace='UObjectDisplayNames', key='', source_string=''):
    source_string = source_string or key
    text = unreal.TextLibrary.find_text_in_live_table_advanced(namespace, key, source_string)
    return str(text) or key

def loctable_col(block=1, lang=None):
    global LocalizationCache
    try:
        lang = lang or int(LocalizationCache[0][0].split(',')[0])
        col_index = int(LocalizationCache[0][0].split(',')[block])
        return LocalizationCache[lang+col_index]
    except:
        return []