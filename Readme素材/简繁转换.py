import opencc

# 定义字符串替换规则
replacements = {
    "僵尸": "喪屍/殭屍",
    "尸壳": "屍殼",
    "溺尸": "溺屍/沉屍",
    "猪灵": "豬人/豬布林",
    "猪灵蛮兵": "殘暴豬人/豬布林蠻兵",
    "卫道士": "衛道士",
    "掠夺者": "掠奪者",
    "骷髅": "骷髏",
    "凋灵": "凋零",
    "流浪者": "流浪者/流髑",
    "沼骸": "沼骨/沼骸",
    "猪": "豬",
    "马": "馬",
    "铁傀儡": "鐵魔像/鐵巨人"
}

# 定义简转繁转换器
converter = opencc.OpenCC('s2t.json')

def translate_readme(content):
    # 应用替换规则
    for key, value in replacements.items():
        content = content.replace(key, value)
    
    # 进行简转繁转换
    content = converter.convert(content)
    
    return content

# 读取并翻译README文件
with open("README.md", "r", encoding="utf-8") as f:
    content = f.read()

translated_content = translate_readme(content)

# 将翻译结果写入新文件
with open("README_ZH-Hant.md", "w", encoding="utf-8") as f:
    f.write(translated_content)

print("README 文件已成功转换为繁体中文并保存。")
