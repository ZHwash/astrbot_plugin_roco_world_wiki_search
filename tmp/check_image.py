import sqlite3

conn = sqlite3.connect('/home/inmain/AstrBot/data/plugins/astrbot_plugin_roco_world_wiki_search/wiki-local.db')
cursor = conn.cursor()

# 查询草喵床头小柜的图片路径
cursor.execute("SELECT name, image_local, main_color FROM items WHERE name='草喵·床头小柜'")
row = cursor.fetchone()

if row:
    print(f"名称: {row[0]}")
    print(f"图片路径: {row[1]}")
    print(f"主色: {row[2]}")
else:
    print("未找到记录")

conn.close()
