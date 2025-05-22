import opencc

# 定义字符串替换规则
replacements = {
    "僵尸": "殭屍",
    "尸壳": "屍殼",
    "溺尸": "溺屍",
    "猪灵": "豬布林",
    "猪灵蛮兵": "豬布林蠻兵",
    "卫道士": "衛道士",
    "掠夺者": "掠奪者",
    "骷髅": "骷髏",
    "凋灵": "凋零",
    "流浪者": "流髑",
    "沼骸": "沼骸",
    "猪": "豬",
    "马": "馬",
    "铁傀儡": "鐵巨人",
    "蠹虫": "蠹魚",
    "末影螨": "終界蟎",
}

# 定义简转繁转换器
converter = opencc.OpenCC('s2t.json')

def translate_readme(content):
    # 应用替换规则
    for key, value in replacements.items():
        content = content.replace(key, value)
    
    # 进行简转繁转换
    content = converter.convert(content)

    content = content.replace("封面圖","封面图")
    content = content.replace("更新彙總","更新汇总")
    content = content.replace("Blender擴展資源/","Blender扩展资源/")
    content = content.replace("插件貼圖/語言本地化","插件贴图/语言本地化")
    content = content.replace("/實驗性功能(C++)/Mineprep/Content/變量顯示名","/实验性功能(C++)/Mineprep/Content/变量显示名")
    
    return content

# 读取并翻译README文件
with open("README.md", "r", encoding="utf-8") as f:
    content = f.read()

translated_content = translate_readme(content)

# 将翻译结果写入新文件
with open("README_ZH-Hant.md", "w", encoding="utf-8") as f:
    f.write(translated_content)

print("README 文件已成功转换为繁体中文并保存。")
