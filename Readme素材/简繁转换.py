import opencc

# 定义字符串替换规则
replacements = {
    "僵尸马": "殭屍馬",
    "僵尸": "喪屍(殭屍)",
    "尸壳": "屍殼",
    "溺尸": "溺屍(沉屍)",
    "猪灵": "豬人(豬布林)",
    "猪灵蛮兵": "殘暴豬人(豬布林蠻兵)",
    "卫道士": "衛道士",
    "掠夺者": "掠奪者",
    "骷髅": "骷髏",
    "凋灵": "凋零",
    "流浪者": "流浪者(流髑)",
    "沼骸": "沼骸",
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
    "中文 | [**English**](./README_English.md) | [**繁體中文**](./README_繁體中文.md)" : "繁體中文 | [**English**](./README_English.md) | [**中文**](./README.md)",
}

replace_back = {
    "封面圖": "封面图",
    "更新彙總": "更新汇总",
    "Blender擴展資源/": "Blender扩展资源/",
    "插件貼圖/語言本地化": "插件贴图/语言本地化",
    "/實驗性功能(C++)/Mineprep/Content/變量顯示名": "/实验性功能(C++)/Mineprep/Content/变量显示名",

}

# 定义简转繁转换器
converter = opencc.OpenCC('s2t.json')

def translate_readme(content):
    # 应用替换规则
    for key, value in replacements.items():
        content = content.replace(key, value)
    
    # 进行简转繁转换
    content = converter.convert(content)

    # 替换回特殊名称
    for key, value in replace_back.items():
        content = content.replace(key, value)

    return content

# 读取并翻译README文件
with open("README.md", "r", encoding="utf-8") as f:
    content = f.read()

translated_content = translate_readme(content)

# 将翻译结果写入新文件
with open("README_繁體中文.md", "w", encoding="utf-8") as f:
    f.write(translated_content)

print("README 文件已成功转换为繁体中文并保存。")
