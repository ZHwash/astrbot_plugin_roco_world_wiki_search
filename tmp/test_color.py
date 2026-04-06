import sys
sys.path.insert(0, '/home/inmain/AstrBot/data/plugins/astrbot_plugin_roco_world_wiki_search/src')

from color_extractor import ColorExtractor

image_path = '/home/inmain/AstrBot/data/plugins/astrbot_plugin_roco_world_wiki_search/output/images/items/家具/草喵·床头小柜.png'

result = ColorExtractor.extract_main_colors(image_path, top_n=5)

if result:
    print(f"主要颜色: {result['main_color']}")
    print(f"所有颜色: {result['colors']}")
    print(f"RGB值: {result['rgb_values']}")
else:
    print("颜色提取失败")
