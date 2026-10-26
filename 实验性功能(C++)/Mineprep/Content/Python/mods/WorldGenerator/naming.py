"""Readable leaf names; full identities remain separate from display paths."""
import re
import unicodedata


def safe_name(value, fallback='preset'):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', unicodedata.normalize('NFC',value))
    name = name.strip().rstrip('. ')[:80].rstrip('. ')
    reserved = {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}
    return fallback if not name or name.split('.')[0].upper() in reserved else name


def short_names(name, digest, suffix=''):
    if not re.fullmatch(r'[0-9a-f]{8,64}',digest):
        raise ValueError('readable names require a full hexadecimal identity')
    for length in range(8,len(digest)+1,4):
        yield f'{safe_name(name)}_{digest[:length]}{suffix}'


def validate_output_name(name):
    if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,32}',name):
        raise ValueError('输出名称须为 1–32 位英文字母、数字、下划线或短横线')
    return name
