"""从 README.md 生成台、港两份繁体文档；运行位置不限，沿用现有 OpenCC 依赖。

普通用词由 s2twp / s2hk 转换，MC 专名和少量技术用语在 TERMS 中维护。
链接地址、HTML 标签、代码块及行内代码保持原样；页内锚点随标题转换。
"""

import re
from pathlib import Path

import opencc


ROOT = Path(__file__).resolve().parent.parent
LANGUAGES = {
    "zh": ("简体中文", "README.md"),
    "en": ("English", "README_English.md"),
    "zh-Hant": ("繁體中文(台灣)", "README_繁體中文(台灣).md"),
    "zh-Hant-HK": ("繁體中文(香港)", "README_繁體中文(香港).md"),
}
CONVERTERS = {
    "zh-Hant": opencc.OpenCC("s2twp.json"),
    "zh-Hant-HK": opencc.OpenCC("s2hk.json"),
}

# 简中原词: (台湾, 香港)。一次匹配最长词，译文不再次参与替换。
# MC 名称参考游戏 zh_tw / zh_hk 语言资源；不再把两个地区的译名并列。
TERMS = {
    "僵尸马": ("殭屍馬", "喪屍馬"),
    "僵尸": ("殭屍", "喪屍"),
    "尸壳": ("屍殼", "屍殼"),
    "溺尸": ("沉屍", "沉屍"),
    "猪灵蛮兵": ("豬布林蠻兵", "殘暴豬人"),
    "猪灵": ("豬布林", "豬人"),
    "卫道士": ("衛道士", "衞道士"),
    "掠夺者": ("掠奪者", "掠奪者"),
    "凋灵骷髅": ("凋零骷髏", "凋零骷髏骨"),
    "骷髅马": ("骷髏馬", "骷髏骨馬"),
    "骷髅": ("骷髏", "骷髏骨"),
    "凋灵": ("凋零怪", "凋零怪"),
    "流浪者": ("流髑", "流浪者"),
    "沼骸": ("沼骸", "沼骨"),
    "焦骸": ("枯骸", "旱骨"),
    "铁傀儡": ("鐵魔像", "鐵人"),
    "蠹虫": ("蠹魚", "蠹魚"),
    "末影螨": ("終界蟎", "終界蟎"),
    "烈焰人": ("烈焰使者", "烈焰使者"),
    "疣猪兽": ("豬布獸", "野豬獸"),
    "雪傀儡": ("雪人", "雪人"),
    "悦灵": ("悅靈", "悦靈"),
    "快乐恶魂": ("快樂幽靈", "快樂幽靈"),
    "小恶魂": ("小幽靈", "幽靈仔"),
    "恶魂": ("地獄幽靈", "地獄幽靈"),
    "豹猫": ("山貓", "豹貓"),
    "苦力怕": ("苦力怕", "Creeper"),
    "鲑鱼": ("鮭魚", "三文魚"),
    "生物群系": ("生態域", "生物羣落"),
    "群系": ("生態域", "羣落"),
    "洞穴与山崖": ("洞穴與山崖", "洞穴與山崖"),
    "灵魂沙峡谷": ("靈魂砂谷", "靈魂砂谷"),
    "灵魂沙": ("靈魂砂", "靈魂砂"),
    "绯红森林": ("緋紅森林", "猩紅森林"),
    "诡异森林": ("扭曲森林", "迷離森林"),
    "热带草原": ("莽原", "熱帶稀樹草原"),
    "覆雪针叶林": ("冰雪針葉林", "冰雪針葉林"),
    "下界荒地": ("地獄荒原", "地獄荒原"),
    "下界": ("地獄", "地獄"),
    "末地": ("終界", "終界"),
    "冰刺之地": ("冰刺", "冰刺之地"),
    "冻洋": ("寒凍海洋", "冰洋"),
    "玄武岩三角洲": ("玄武岩三角洲", "玄武岩三角洲"),
    "系统要求": ("系統需求", "系統要求"),
    "工程文件": ("專案檔", "工程檔案"),
    "工程": ("專案", "工程"),
    "项目": ("專案", "項目"),
    "文件夹": ("資料夾", "資料夾"),
    "文件": ("檔案", "檔案"),
    "插件": ("外掛", "插件"),
    "用户": ("使用者", "用戶"),
    "视频": ("影片", "影片"),
    "摄像机": ("攝影機", "攝影機"),
    "组件": ("元件", "組件"),
    "实例": ("實例", "實例"),
    "参数": ("參數", "參數"),
    "自定义": ("自訂", "自定義"),
    "示例": ("範例", "示例"),
    "函数": ("函式", "函數"),
    "帧": ("影格", "幀"),
    "分辨率": ("解析度", "解像度"),
    "显存": ("顯示記憶體", "顯存"),
    "命令行": ("命令列", "命令列"),
    "兼容": ("相容", "兼容"),
    "教程": ("教學", "教學"),
    "默认画质预设": ("預設畫質配置", "預設畫質配置"),
    "默认": ("預設", "預設"),
    "支持": ("支援", "支援"),
    "导入": ("匯入", "匯入"),
    "导出": ("匯出", "匯出"),
    "绑定": ("綁定", "綁定"),
    "重载": ("重載", "重載"),
    "像素": ("像素", "像素"),
    "消息": ("消息", "消息"),
    "进程": ("進程", "進程"),
    "飞行模式": ("飛行模式", "飛行模式"),
    "高级选项": ("進階選項", "高級選項"),
    "高级设置": ("進階設定", "高級設置"),
    "高级元数据": ("進階元資料", "高級元數據"),
    "高级水体": ("進階水體", "高級水體"),
    # 修正 OpenCC 的断词或漏转：合并为、并发布、复刻、复现等。
    "合并为": ("合併為", "合併為"),
    "并发布": ("並發布", "並發佈"),
    "并为": ("並為", "並為"),
    "制作": ("製作", "製作"),
    "只有": ("只有", "只有"),
    "复刻": ("復刻", "復刻"),
    "复现": ("復現", "復現"),
    "挡位": ("檔位", "檔位"),
}
_TERMS = re.compile("|".join(map(re.escape, sorted(TERMS, key=len, reverse=True))))

# 常见 Markdown 链接（含一层圆括号路径）、引用链接、HTML 和代码。
_PROTECTED = re.compile(
    r"(?P<langbar>^简体中文 \| [^\n]*README[^\n]*$)"
    r"|(?P<fence>^[ \t]*(?P<marker>`{3,}|~{3,})[^\n]*\n.*?^[ \t]*(?P=marker)[ \t]*(?=\n|$))"
    r"|(?P<code>(?P<ticks>`+)[^`\n]+(?P=ticks))"
    r"|(?P<link>\]\((?:<[^>\n]+>|(?:[^()\n]|\([^()\n]*\))+)\))"
    r"|(?P<html><[A-Za-z/!][^>\n]*>)"
    r"|(?P<reference>^[ \t]{0,3}\[[^\]\n]+\]:[ \t]*\S+)"
    r"|(?P<url>https?://[^\s<>]+)",
    re.MULTILINE | re.DOTALL,
)


def language_bar(culture):
    return " | ".join(
        label if code == culture else f"[**{label}**](<./{filename}>)"
        for code, (label, filename) in LANGUAGES.items()
    )


def translate_readme(content, culture):
    """按 zh-Hant 或 zh-Hant-HK 转换；不读取或改写文件。"""
    converter = CONVERTERS[culture]
    region = 0 if culture == "zh-Hant" else 1

    def translate_words(text):
        # 专名先占位，避免被 OpenCC 或后续的短词再次转换。
        slots = []

        def replace(match):
            slots.append(TERMS[match.group()][region])
            return f"\ue000{len(slots) - 1}\ue001"

        text = converter.convert(_TERMS.sub(replace, text))
        return re.sub(r"\ue000(\d+)\ue001", lambda m: slots[int(m[1])], text)

    result = []
    start = 0
    for match in _PROTECTED.finditer(content):
        result.append(translate_words(content[start:match.start()]))
        literal = match.group()
        # 顶部语言栏按目标语言生成；页内锚点及非路径的行内反引号文本跟随转换。
        if match.lastgroup == "langbar":
            literal = language_bar(culture)
        elif match.lastgroup == "link" and literal.startswith(("](#", "](<#")):
            literal = translate_words(literal)
        elif match.lastgroup == "code" and not ("/" in literal or "\\" in literal):
            literal = translate_words(literal)
        result.append(literal)
        start = match.end()
    result.append(translate_words(content[start:]))
    return "".join(result)


def main():
    content = (ROOT / "README.md").read_text(encoding="utf-8")
    for culture in CONVERTERS:
        target = ROOT / LANGUAGES[culture][1]
        target.write_text(translate_readme(content, culture), encoding="utf-8")
        print(f"已写入 {target.name}")


if __name__ == "__main__":
    main()
