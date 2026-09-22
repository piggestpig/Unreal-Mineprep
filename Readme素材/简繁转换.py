import re
from pathlib import Path

import opencc

# 生物等专有译名。按词条从长到短替换，避免“猪”先改掉“疣猪兽”
replacements = {
    "僵尸马": "殭屍馬",
    "僵尸": "喪屍(殭屍)",
    "尸壳": "屍殼",
    "溺尸": "溺屍(沉屍)",
    "猪灵蛮兵": "殘暴豬人(豬布林蠻兵)",
    "猪灵": "豬人(豬布林)",
    "卫道士": "衛道士",
    "掠夺者": "掠奪者",
    "骷髅": "骷髏",
    "凋灵": "凋零",
    "流浪者": "流浪者(流髑)",
    "沼骸": "沼骸",
    "焦骸": "旱骨(枯骸)",
    "猪": "豬",
    "马": "馬",
    "铁傀儡": "鐵魔像(鐵巨人)",
    "蠹虫": "蠹魚",
    "末影螨": "終界蟎",
    "烈焰人": "烈焰使者",
    "疣猪兽": "野豬獸(豬布獸)",
    "雪傀儡": "雪人",
    "悦灵": "悅靈",
    "快乐恶魂": "快樂幽靈",
    "小恶魂": "小幽靈",
    "恶魂": "地獄幽靈",
    "豹猫": "豹貓(山貓)",
    "中文 | [**English**](./README_English.md) | [**繁體中文**](./README_繁體中文.md)": "繁體中文 | [**English**](./README_English.md) | [**中文**](./README.md)",
}

# 仓库路径和图片地址保持原样；#锚点要随标题一起转换
_LINK = re.compile(r"(\]\()(<[^>]+>|[^)\s]+)(\))|(src=\")([^\"]+)(\")")
converter = opencc.OpenCC("s2t.json")
ROOT = Path(__file__).resolve().parent.parent


def apply_replacements(content):
    for key, value in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        content = content.replace(key, value)
    return content


def mask_urls(content):
    slots = []

    def repl(match):
        if match.group(1):
            url = match.group(2)
            raw = url[1:-1] if url.startswith("<") and url.endswith(">") else url
            if raw.startswith("#"):
                return match.group(0)
            token = f"@@URL{len(slots):04d}@@"
            slots.append(url)
            return match.group(1) + token + match.group(3)
        token = f"@@URL{len(slots):04d}@@"
        slots.append(match.group(5))
        return match.group(4) + token + match.group(6)

    return _LINK.sub(repl, content), slots


def unmask_urls(content, slots):
    for index, url in enumerate(slots):
        content = content.replace(f"@@URL{index:04d}@@", url)
    return content


def translate_readme(content):
    content = apply_replacements(content)
    content, slots = mask_urls(content)
    content = converter.convert(content)
    return unmask_urls(content, slots)


def main():
    source = ROOT / "README.md"
    target = ROOT / "README_繁體中文.md"
    content = source.read_text(encoding="utf-8")
    target.write_text(translate_readme(content), encoding="utf-8")
    print(f"已写入 {target.name}")


if __name__ == "__main__":
    main()
