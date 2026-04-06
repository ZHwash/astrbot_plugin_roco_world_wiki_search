import sys
sys.path.insert(0, '/home/inmain/AstrBot/data/plugins/astrbot_plugin_roco_world_wiki_search/src')

from color_extractor import ColorExtractor
import sqlite3

# 连接数据库
db_path = '/home/inmain/AstrBot/data/plugins/astrbot_plugin_roco_world_wiki_search/wiki-local.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 查询需要重新识别的家具
cursor.execute("SELECT name, image_local FROM items WHERE name='草喵·床头小柜'")
row = cursor.fetchone()

if row:
    name, image_local = row
    print(f"正在重新识别: {name}")
    
    # 构建完整路径
    import os
    if image_local and not os.path.isabs(image_local):
        full_path = os.path.join('/home/inmain/AstrBot/data/plugins/astrbot_plugin_roco_world_wiki_search', image_local)
    else:
        full_path = image_local
    
    print(f"图片路径: {full_path}")
    
    # 重新识别颜色
    result = ColorExtractor.extract_main_colors(full_path)
    
    if result and result['main_color']:
        old_color = '粉'  # 已知的旧值
        new_color = result['main_color']
        
        print(f"旧颜色: {old_color}")
        print(f"新颜色: {new_color}")
        print(f"所有颜色: {result['colors']}")
        
        # 更新数据库
        cursor.execute("UPDATE items SET main_color = ? WHERE name = ?", (new_color, name))
        conn.commit()
        
        print(f"✅ 已更新数据库")
    else:
        print("❌ 颜色识别失败")
else:
    print("❌ 未找到记录")

conn.close()
