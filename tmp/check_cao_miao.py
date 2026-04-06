import sqlite3

conn = sqlite3.connect('/home/inmain/AstrBot/data/plugins/astrbot_plugin_roco_world_wiki_search/wiki-local.db')
cursor = conn.cursor()

# 查询草喵相关家具
cursor.execute("SELECT name, main_color, rarity FROM items WHERE name LIKE '%草喵%' AND category='家具'")
rows = cursor.fetchall()

print("草喵家具颜色信息:")
for row in rows:
    print(f"  名称: {row[0]}")
    print(f"  主色: {row[1]}")
    print(f"  稀有度: {row[2]}")
    print()

conn.close()
