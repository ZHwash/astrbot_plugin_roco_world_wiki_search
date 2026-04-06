# -*- coding: utf-8 -*-
"""
RocoWorld Wiki Plugin - 洛克王国 Wiki 查询插件
查询宠物和技能详细信息

优化版本 v2.0：完整实现数据库查询、WebUI 配置、多风格响应
支持管理员命令更新数据库、自定义查询指令

⚠️ 数据来源声明：
本插件使用的所有文字与数据内容均来自 BiliGame 洛克王国 WIKI
采用 CC BY-NC-SA 4.0（署名-非商业性使用-相同方式共享）协议进行许可
任何使用请严格遵守上述协议，规范转载请务必清晰注明来源链接
Wiki 地址: https://wiki.biligame.com/rocom/
"""

import os
import subprocess
import sys
from typing import Optional, Dict, Any, List

# 确保插件目录在 Python 路径中
plugin_dir = os.path.dirname(os.path.abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Star, Context, register
from src.db_service import WikiDBService
from src.color_extractor_vision import ColorExtractor

# 数据来源声明（CC BY-NC-SA 4.0 协议）
DATA_SOURCE_NOTICE = "\n\n---\n📚 数据来源: [BiliGame 洛克王国 WIKI](https://wiki.biligame.com/rocom/) | CC BY-NC-SA 4.0"


@register("astrbot-plugin-roco-world-wiki", "InMain", "洛克王国 Wiki 查询", "2.0.0")
class RocoWorldWiki(Star):
    """洛克王国 Wiki 插件"""
    
    def _init_color_extractor(self):
        """
        初始化颜色提取器（从 AstrBot provider 配置中获取或手动填写）
        
        Returns:
            ColorExtractor 实例或 None
        """
        # 检查是否使用手动配置
        manual_api_key = self.config.get("manual_vision_api_key", "").strip()
        manual_base_url = self.config.get("manual_vision_base_url", "").strip()
        manual_model_id = self.config.get("manual_vision_model_id", "").strip()
        
        # 如果手动配置完整，直接使用
        if manual_api_key and manual_base_url and manual_model_id:
            logger.info("✅ 使用手动配置的视觉模型")
            logger.info(f"   - base_url: {manual_base_url}")
            logger.info(f"   - model: {manual_model_id}")
            
            # 创建适配器，使用手动配置
            class ManualProviderAdapter:
                """手动配置 Provider 适配器，用于颜色提取"""
                def __init__(self, context, api_key, base_url, model_id):
                    self.context = context
                    self.api_key = api_key
                    self.base_url = base_url
                    self.model_id = model_id
                
                async def extract_main_colors_async(self, image_path: str, top_n: int = 2):
                    """使用手动配置的 API 进行颜色识别（异步版本）"""
                    import base64
                    import aiohttp
                    
                    try:
                        if not os.path.exists(image_path):
                            logger.error(f"❌ 图片不存在: {image_path}")
                            return None
                        
                        # 读取图片并转为base64
                        with open(image_path, 'rb') as f:
                            image_data = base64.b64encode(f.read()).decode('utf-8')
                        
                        # 构建提示词
                        if top_n == 1:
                            prompt = (
                                "请分析这张图片的主色调是什么颜色？\n"
                                "要求：\n"
                                "1. 只输出一个中文颜色名称（如：红、橙、黄、绿、蓝、紫、粉、白、黑、棕、灰）\n"
                                "2. 不要有任何其他文字、标点或解释\n"
                                "3. 如果图片有多种颜色，选择占比最大的那个"
                            )
                        else:
                            prompt = (
                                f"请分析这张图片的主要颜色，按占比从高到低列出前{top_n}种颜色。\n"
                                "要求：\n"
                                "1. 每行一个颜色，格式：颜色名\n"
                                "2. 颜色必须是单个中文字：红、橙、黄、绿、蓝、紫、粉、白、黑、棕、灰\n"
                                "3. 按占比从高到低排序\n"
                                "4. 不要有任何其他文字、标点或解释\n"
                                "5. 如果图片颜色单一，只输出一个颜色即可\n"
                                "\n"
                                "示例输出：\n"
                                "绿\n"
                                "白"
                            )
                        
                        # 调用 OpenAI 兼容 API
                        headers = {
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {self.api_key}"
                        }
                        
                        payload = {
                            "model": self.model_id,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": prompt},
                                        {
                                            "type": "image_url",
                                            "image_url": {
                                                "url": f"data:image/png;base64,{image_data}"
                                            }
                                        }
                                    ]
                                }
                            ],
                            "max_tokens": 100,
                            "temperature": 0.1
                        }
                        
                        # 发送请求
                        async with aiohttp.ClientSession() as session:
                            async with session.post(
                                f"{self.base_url}/chat/completions",
                                headers=headers,
                                json=payload,
                                timeout=aiohttp.ClientTimeout(total=30)
                            ) as response:
                                if response.status != 200:
                                    error_text = await response.text()
                                    logger.error(f"❌ API 请求失败: {response.status} - {error_text}")
                                    return None
                                
                                result = await response.json()
                                response_text = result['choices'][0]['message']['content'].strip()
                        
                        # 解析响应
                        lines = response_text.split('\n')
                        
                        valid_colors = []
                        for line in lines:
                            color = line.strip()
                            if len(color) == 1 and color in ['红', '橙', '黄', '绿', '蓝', '紫', '粉', '白', '黑', '棕', '灰']:
                                if color not in valid_colors:
                                    valid_colors.append(color)
                        
                        if not valid_colors:
                            logger.warning(f"⚠️ 无法解析颜色: {response_text}")
                            return None
                        
                        valid_colors = valid_colors[:top_n]
                        
                        return {
                            'main_color': valid_colors[0] if len(valid_colors) > 0 else None,
                            'secondary_color': valid_colors[1] if len(valid_colors) > 1 else None,
                            'colors': valid_colors,
                            'rgb_values': [],
                            'color_ratios': []
                        }
                    
                    except Exception as e:
                        logger.error(f"❌ 颜色提取错误: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        return None
            
            return ManualProviderAdapter(self.context, manual_api_key, manual_base_url, manual_model_id)
        
        # 如果没有手动配置，尝试从 AstrBot provider 配置中获取
        vision_model_config = self.config.get("vision_model_config", "")
        
        if not vision_model_config or not vision_model_config.strip():
            logger.warning("⚠️ 未配置视觉模型，颜色识别功能不可用")
            logger.warning("💡 请在 WebUI 的插件配置中选择视觉模型")
            return None
        
        try:
            provider_manager = getattr(self.context, 'provider_manager', None)
            if not provider_manager:
                logger.error("❌ 无法访问 provider_manager")
                return None
            
            # 获取所有可用的 providers
            providers = getattr(provider_manager, 'get_insts', lambda: [])()
            
            # 调试：列出所有可用的 providers
            if providers:
                available_ids = []
                for p in providers:
                    # 尝试多种可能的属性名
                    pid = (getattr(p, 'id', None) or 
                           getattr(p, 'provider_id', None) or 
                           getattr(p, 'name', None) or 
                           getattr(p, 'model_name', None) or 
                           getattr(p, 'model', None) or 
                           str(type(p).__name__))
                    pname = getattr(p, 'name', '') or getattr(p, 'model_name', '') or pid
                    available_ids.append(f"{pid} ({pname})")
                    
                    # 详细调试：打印 provider 的所有属性
                    logger.debug(f"Provider 对象类型: {type(p).__name__}")
                    logger.debug(f"Provider 属性: id={getattr(p, 'id', 'N/A')}, provider_id={getattr(p, 'provider_id', 'N/A')}, name={getattr(p, 'name', 'N/A')}")
                
                logger.info(f"📋 当前可用的 Providers: {', '.join(available_ids)}")
            else:
                logger.warning("⚠️ 没有找到任何已配置的 Provider")
            
            # 查找匹配的 provider
            selected_provider = None
            for provider in providers:
                # 尝试多种可能的属性名
                provider_id = (getattr(provider, 'id', None) or 
                              getattr(provider, 'provider_id', None) or 
                              getattr(provider, 'name', None) or 
                              getattr(provider, 'model_name', None) or 
                              getattr(provider, 'model', None))
                
                if not provider_id:
                    continue
                
                # 精确匹配
                if provider_id == vision_model_config:
                    selected_provider = provider
                    break
                
                # 模糊匹配：去除前缀后匹配（处理 ollama_amd/ 等前缀）
                if '/' in vision_model_config:
                    config_model_name = vision_model_config.split('/')[-1]
                    if provider_id == config_model_name or provider_id.endswith('/' + config_model_name):
                        logger.info(f"💡 通过模糊匹配找到 Provider: {provider_id}")
                        selected_provider = provider
                        break
            
            if not selected_provider:
                logger.error(f"❌ 未找到 provider '{vision_model_config}'")
                logger.error("💡 请检查该模型是否已在 AstrBot 中正确配置")
                # 使用与前面相同的逻辑获取 IDs
                available_ids = []
                for p in providers:
                    pid = (getattr(p, 'id', None) or 
                           getattr(p, 'provider_id', None) or 
                           getattr(p, 'name', None) or 
                           getattr(p, 'model_name', None) or 
                           getattr(p, 'model', None) or 
                           str(type(p).__name__))
                    available_ids.append(pid)
                logger.error(f"💡 可用的 provider IDs: {available_ids}")
                return None
            
            # 从 provider 配置中提取 API 信息
            # AstrBot v4.x 的 Provider 对象有 provider_config 属性（字典）
            provider_config_dict = getattr(selected_provider, 'provider_config', {})
            
            if isinstance(provider_config_dict, dict):
                # 从 provider_config 字典中获取
                raw_api_key = provider_config_dict.get('key')
                if isinstance(raw_api_key, list):
                    vision_api_key = raw_api_key[0] if raw_api_key else ''
                else:
                    vision_api_key = raw_api_key or ''
                
                vision_base_url = (provider_config_dict.get('base_url') or 
                                  provider_config_dict.get('api_base') or 
                                  provider_config_dict.get('endpoint') or 
                                  '')
                
                vision_model = (provider_config_dict.get('model') or 
                               provider_config_dict.get('model_name') or 
                               provider_config_dict.get('model_id') or 
                               provider_id or 
                               '')
            else:
                # 备用方案：尝试直接访问属性
                vision_api_key = (getattr(selected_provider, 'api_key', None) or 
                                 getattr(selected_provider, 'token', None) or 
                                 getattr(selected_provider, 'key', None) or 
                                 '')
                
                vision_base_url = (getattr(selected_provider, 'base_url', None) or 
                                  getattr(selected_provider, 'api_base', None) or 
                                  getattr(selected_provider, 'endpoint', None) or 
                                  '')
                
                vision_model = (getattr(selected_provider, 'model_name', None) or 
                               getattr(selected_provider, 'model', None) or 
                               getattr(selected_provider, 'model_id', None) or 
                               provider_id or 
                               '')
            
            # 调试日志：打印所有可能的属性
            logger.debug(f"Provider 对象类型: {type(selected_provider).__name__}")
            logger.debug(f"尝试获取的属性:")
            logger.debug(f"  - api_key/token/key: {vision_api_key or '✗'}")
            logger.debug(f"  - base_url/api_base/endpoint: {vision_base_url or '✗'}")
            logger.debug(f"  - model_name/model/model_id: {vision_model or '✗'}")
            
            # 如果还是为空，尝试直接访问 __dict__ 或 config
            if not vision_api_key or not vision_base_url or not vision_model:
                logger.debug("尝试从 provider.__dict__ 或 provider.config 获取...")
                provider_dict = getattr(selected_provider, '__dict__', {})
                provider_config = getattr(selected_provider, 'config', {})
                
                if not vision_api_key:
                    vision_api_key = (provider_dict.get('api_key') or 
                                     provider_dict.get('token') or 
                                     provider_config.get('api_key') or 
                                     provider_config.get('token') or 
                                     '')
                
                if not vision_base_url:
                    vision_base_url = (provider_dict.get('base_url') or 
                                      provider_dict.get('api_base') or 
                                      provider_config.get('base_url') or 
                                      provider_config.get('api_base') or 
                                      '')
                
                if not vision_model:
                    vision_model = (provider_dict.get('model_name') or 
                                   provider_dict.get('model') or 
                                   provider_config.get('model_name') or 
                                   provider_config.get('model') or 
                                   provider_id or 
                                   '')
            
            # 最后的备用方案：如果是 Ollama 模型，使用默认配置
            if not vision_base_url and ('ollama' in provider_id.lower() or 'qwen' in provider_id.lower()):
                logger.info(f"💡 检测到可能是 Ollama 模型，使用默认配置")
                vision_base_url = "http://192.168.31.15:11436/v1"
                vision_api_key = vision_api_key or "ollama"  # Ollama 不需要 API Key，但需要一个占位符
                vision_model = vision_model or provider_id
                logger.info(f"   - base_url: {vision_base_url}")
                logger.info(f"   - model: {vision_model}")
            
            # 如果还是获取不到，尝试从 AstrBot 配置文件中读取
            if not vision_base_url:
                logger.warning("⚠️ 无法从 Provider 对象获取配置，尝试从配置文件读取...")
                try:
                    import json
                    config_file = os.path.join(plugin_dir, '..', 'config', 'abconf_412865ab-2550-4266-89be-e9c00a76752b.json')
                    if os.path.exists(config_file):
                        with open(config_file, 'r', encoding='utf-8-sig') as f:
                            astrbot_config = json.load(f)
                        
                        # 查找 providers 配置
                        providers_config = astrbot_config.get('provider_settings', {}).get('providers', [])
                        for prov_cfg in providers_config:
                            if prov_cfg.get('id') == provider_id or prov_cfg.get('name') == provider_id:
                                vision_api_key = prov_cfg.get('key', [''])[0] if isinstance(prov_cfg.get('key'), list) else prov_cfg.get('key', '')
                                vision_base_url = prov_cfg.get('base_url', '')
                                vision_model = prov_cfg.get('model', '') or provider_id
                                logger.info(f"✅ 从配置文件读取成功")
                                logger.info(f"   - base_url: {vision_base_url}")
                                logger.info(f"   - model: {vision_model}")
                                break
                except Exception as e:
                    logger.debug(f"从配置文件读取失败: {e}")
            
            if not vision_api_key or not vision_base_url or not vision_model:
                logger.warning(f"⚠️ Provider '{vision_model_config}' 配置不完整")
                logger.warning(f"   - api_key: {'✓' if vision_api_key else '✗'}")
                logger.warning(f"   - base_url: {'✓' if vision_base_url else '✗'}")
                logger.warning(f"   - model: {'✓' if vision_model else '✗'}")
                return None
            
            logger.info(f"✅ 使用 AstrBot 配置的视觉模型: {vision_model_config}")
            
            # 调试：打印 provider_manager.inst_map 的所有 key
            if hasattr(self.context.provider_manager, 'inst_map'):
                available_keys = list(self.context.provider_manager.inst_map.keys())
                logger.info(f"📋 provider_manager.inst_map keys: {available_keys}")
            
            # 创建一个适配器，使用 context.llm_generate() 调用视觉模型
            class AstrBotProviderAdapter:
                """AstrBot Provider 适配器，用于颜色提取"""
                def __init__(self, context, provider_id, model_name):
                    self.context = context
                    self.provider_id = provider_id
                    self.model_name = model_name  # 保存实际的模型名称
                
                async def extract_main_colors_async(self, image_path: str, top_n: int = 2):
                    """使用 AstrBot Provider 进行颜色识别（异步版本）"""
                    import base64
                    
                    try:
                        if not os.path.exists(image_path):
                            logger.error(f"❌ 图片不存在: {image_path}")
                            return None
                        
                        # 读取图片并转为base64
                        with open(image_path, 'rb') as f:
                            image_data = base64.b64encode(f.read()).decode('utf-8')
                        
                        # 构建提示词
                        if top_n == 1:
                            prompt = (
                                "请分析这张图片的主色调是什么颜色？\n"
                                "要求：\n"
                                "1. 只输出一个中文颜色名称（如：红、橙、黄、绿、蓝、紫、粉、白、黑、棕、灰）\n"
                                "2. 不要有任何其他文字、标点或解释\n"
                                "3. 如果图片有多种颜色，选择占比最大的那个"
                            )
                        else:
                            prompt = (
                                f"请分析这张图片的主要颜色，按占比从高到低列出前{top_n}种颜色。\n"
                                "要求：\n"
                                "1. 每行一个颜色，格式：颜色名\n"
                                "2. 颜色必须是单个中文字：红、橙、黄、绿、蓝、紫、粉、白、黑、棕、灰\n"
                                "3. 按占比从高到低排序\n"
                                "4. 不要有任何其他文字、标点或解释\n"
                                "5. 如果图片颜色单一，只输出一个颜色即可\n"
                                "\n"
                                "示例输出：\n"
                                "绿\n"
                                "白"
                            )
                        
                        # 调用 AstrBot context.llm_generate()
                        response = await self.context.llm_generate(
                            chat_provider_id=self.provider_id,
                            prompt=prompt,
                            image_urls=[f"data:image/png;base64,{image_data}"],
                            model=self.model_name  # 使用实际的模型名称
                        )
                        
                        if not response or not response.completion_text:
                            logger.warning("⚠️ Provider 返回空响应")
                            return None
                        
                        # 解析响应
                        response_text = response.completion_text.strip()
                        lines = response_text.split('\n')
                        
                        valid_colors = []
                        for line in lines:
                            color = line.strip()
                            if len(color) == 1 and color in ['红', '橙', '黄', '绿', '蓝', '紫', '粉', '白', '黑', '棕', '灰']:
                                if color not in valid_colors:
                                    valid_colors.append(color)
                        
                        if not valid_colors:
                            logger.warning(f"⚠️ 无法解析颜色: {response_text}")
                            return None
                        
                        valid_colors = valid_colors[:top_n]
                        
                        return {
                            'main_color': valid_colors[0] if len(valid_colors) > 0 else None,
                            'secondary_color': valid_colors[1] if len(valid_colors) > 1 else None,
                            'colors': valid_colors,
                            'rgb_values': [],
                            'color_ratios': []
                        }
                    
                    except Exception as e:
                        logger.error(f"❌ 颜色提取错误: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        return None
            
            return AstrBotProviderAdapter(self.context, provider_id, vision_model)
        except Exception as e:
            logger.error(f"❌ 初始化颜色提取器失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _get_db_path(self):
        """
        获取数据库的绝对路径
        
        Returns:
            str: 数据库的绝对路径
        """
        db_path = self.config.get("db_path", "./wiki-local.db")
        if not os.path.isabs(db_path):
            db_path = os.path.join(plugin_dir, db_path)
        return db_path
    
    def _extract_image_query(self, query_content: str) -> tuple:
        """
        检测并提取图片检索请求
        
        Args:
            query_content: 查询内容
            
        Returns:
            (is_image_query, clean_query): 是否是图片检索，清理后的查询词
        """
        # 检查是否包含图片关键词
        for keyword in self.image_keywords:
            if keyword in query_content:
                # 移除图片关键词，得到实际要查询的内容
                clean_query = query_content.replace(keyword, '').strip()
                if clean_query:
                    return True, clean_query
        
        return False, query_content
    
    def __init__(self, context: Context, config: Dict[str, Any] = None):
        super().__init__(context, config or {})
        self.config = config or {}
        
        # 初始化数据库服务
        db_path = self.config.get("db_path", "./wiki-local.db")
        try:
            self.db_service = WikiDBService(db_path)
            logger.info(f"✅ 数据库服务初始化成功: {db_path}")
        except Exception as e:
            logger.error(f"❌ 数据库服务初始化失败: {e}")
            logger.error("💡 请检查数据库路径是否正确，或运行 setup_db.py 初始化数据库")
            self.db_service = None
        
        # 获取配置项
        self.search_limit = max(self.config.get("search_limit", 5), 1) or 5
        self.enable_fuzzy_search = self.config.get("enable_fuzzy_search", True)
        self.response_style = self.config.get("response_style", "简洁")
        self.trigger_keywords = self.config.get("trigger_keywords", ["洛克王国", "查询", "百科"])
        self.query_command = self.config.get("query_command", "查询")
        self.image_keywords = self.config.get("image_keywords", ["图片", "图", "头像", "立绘"])
        
        # 分页配置
        self.page_size = max(5, min(30, self.config.get("page_size", 10)))
        
        # 颜色提取器（视觉模型）- 懒加载
        self._color_extractor = None
        
        # 会话状态管理（用于翻页功能）
        self.session_states = {}
        self.session_timeout = 300  # 5分钟
        
        logger.info(f"🔥 洛克王国 Wiki 插件已加载")
        logger.info(f"   - 响应风格: {self.response_style}")
        logger.info(f"   - 模糊搜索: {'开启' if self.enable_fuzzy_search else '关闭'}")
        logger.info(f"   - 搜索限制: {self.search_limit}")
        logger.info(f"   - 触发关键词: {', '.join(self.trigger_keywords)}")
        logger.info(f"   - 查询指令: /{self.query_command}")
        logger.info(f"   - 分页大小: {self.page_size} 条/页")
        logger.info(f"   - 图片检索词: {', '.join(self.image_keywords)}")
        
        # 检查视觉模型配置方式
        manual_api_key = self.config.get("manual_vision_api_key", "").strip()
        manual_base_url = self.config.get("manual_vision_base_url", "").strip()
        manual_model_id = self.config.get("manual_vision_model_id", "").strip()
        vision_model_config = self.config.get("vision_model_config", "")
        
        if manual_api_key and manual_base_url and manual_model_id:
            logger.info(f"   - 视觉模型: 手动配置 ({manual_model_id})")
        elif vision_model_config:
            logger.info(f"   - 视觉模型: AstrBot Provider ({vision_model_config})")
        else:
            logger.warning(f"   - 视觉模型: 未配置（颜色识别功能不可用）")
    
    @property
    def color_extractor(self):
        """颜色提取器（懒加载）"""
        if self._color_extractor is None:
            self._color_extractor = self._init_color_extractor()
        return self._color_extractor
    
    async def _on_config_update(self, config: Dict[str, Any]):
        """
        配置更新时的回调函数（支持热重载）
        
        Args:
            config: 新的配置字典
        """
        try:
            logger.info("🔄 检测到配置更新，正在应用...")
            
            # 更新配置
            self.config = config or {}
            
            # 检查数据库路径是否变化
            new_db_path = self.config.get("db_path", "./wiki-local.db")
            old_db_path = getattr(self, '_current_db_path', None)
            
            if new_db_path != old_db_path:
                logger.info(f"📁 数据库路径变更: {old_db_path} -> {new_db_path}")
                try:
                    self.db_service = WikiDBService(new_db_path)
                    logger.info(f"✅ 数据库服务重新初始化成功")
                except Exception as e:
                    logger.error(f"❌ 数据库服务重新初始化失败: {e}")
                    # 保持旧的服务
            
            self._current_db_path = new_db_path
            
            # 更新其他配置项
            self.search_limit = max(self.config.get("search_limit", 5), 1) or 5
            self.enable_fuzzy_search = self.config.get("enable_fuzzy_search", True)
            self.response_style = self.config.get("response_style", "简洁")
            self.trigger_keywords = self.config.get("trigger_keywords", ["洛克王国", "查询", "百科"])
            self.query_command = self.config.get("query_command", "查询")
            self.image_keywords = self.config.get("image_keywords", ["图片", "图", "头像", "立绘"])
            
            # 分页配置
            self.page_size = max(5, min(30, self.config.get("page_size", 10)))
            
            # 重置颜色提取器（下次使用时会重新初始化）
            self._color_extractor = None
            
            # 检查视觉模型配置方式
            manual_api_key = self.config.get("manual_vision_api_key", "").strip()
            manual_base_url = self.config.get("manual_vision_base_url", "").strip()
            manual_model_id = self.config.get("manual_vision_model_id", "").strip()
            vision_model_config = self.config.get("vision_model_config", "")
            
            if manual_api_key and manual_base_url and manual_model_id:
                logger.info(f"   - 视觉模型: 手动配置 ({manual_model_id})")
            elif vision_model_config:
                logger.info(f"   - 视觉模型: AstrBot Provider ({vision_model_config})")
            else:
                logger.warning(f"   - 视觉模型: 未配置（颜色识别功能不可用）")
            
            logger.info("✅ 配置更新成功")
            logger.info(f"   - 响应风格: {self.response_style}")
            logger.info(f"   - 模糊搜索: {'开启' if self.enable_fuzzy_search else '关闭'}")
            logger.info(f"   - 搜索限制: {self.search_limit}")
            logger.info(f"   - 触发关键词: {', '.join(self.trigger_keywords)}")
            logger.info(f"   - 查询指令: /{self.query_command}")
            logger.info(f"   - 分页大小: {self.page_size} 条/页")
            logger.info(f"   - 图片检索词: {', '.join(self.image_keywords)}")
            
        except Exception as e:
            logger.error(f"❌ 配置更新失败: {e}", exc_info=True)
    
    def _parse_list_field(self, field_value: str) -> list:
        """
        解析数据库中的列表字段（支持JSON和Python列表格式）
        
        Args:
            field_value: 数据库中的字符串值
            
        Returns:
            解析后的列表，失败返回空列表
        """
        import json
        import ast
        
        if not field_value or field_value == '[]':
            return []
        
        try:
            # 先尝试用JSON解析
            return json.loads(field_value)
        except:
            pass
        
        try:
            # 如果JSON失败，尝试用ast.literal_eval解析Python列表格式
            result = ast.literal_eval(field_value)
            if isinstance(result, list):
                return result
        except:
            pass
        
        # 最后尝试分号分隔的格式
        if ';' in field_value:
            return [s.strip() for s in field_value.split(';') if s.strip()]
        
        return []
    
    def _format_pet_response(self, pet_data: Dict[str, Any]) -> str:
        """
        根据配置风格格式化宠物信息
        
        Args:
            pet_data: 宠物数据字典
            
        Returns:
            格式化后的文本
        """
        name = pet_data.get('name', '未知')
        element = pet_data.get('element', '未知')
        hp = pet_data.get('hp', 0)
        ability = pet_data.get('ability', '无')
        ability_desc = pet_data.get('ability_desc', '')
        skills = pet_data.get('skills', '')
        description = pet_data.get('description', '')
        size = pet_data.get('size', '')
        weight = pet_data.get('weight', '')
        distribution = pet_data.get('distribution', '')
        stage = pet_data.get('stage', '')
        pet_type = pet_data.get('type', '')
        form = pet_data.get('form', '')
        initial_stage_name = pet_data.get('initial_stage_name', '')
        has_alt_color = pet_data.get('has_alt_color', '')
        update_version = pet_data.get('update_version', '')
        quest_tasks = pet_data.get('quest_tasks', '')
        quest_skill_stones = pet_data.get('quest_skill_stones', '')
        bloodline_skills = pet_data.get('bloodline_skills', '')
        learnable_skill_stones = pet_data.get('learnable_skill_stones', '')
        physical_attack = pet_data.get('physical_attack', 0)
        magic_attack = pet_data.get('magic_attack', 0)
        physical_defense = pet_data.get('physical_defense', 0)
        magic_defense = pet_data.get('magic_defense', 0)
        speed = pet_data.get('speed', 0)
        
        # 检查是否数据缺失（六维全为0）
        is_data_missing = (hp == 0 and physical_attack == 0 and magic_attack == 0 
                          and physical_defense == 0 and magic_defense == 0 and speed == 0)
        
        if self.response_style == "详细":
            # 详细模式：显示所有信息
            import json
            
            response = f"🐾 **{name}**\n"
            response += "━━━━━━━━━━━━━━\n"
            
            # 基本信息
            info_parts = []
            if form and form != '原始形态':
                info_parts.append(f"形态: {form}")
            if stage:
                info_parts.append(f"阶段: {stage}")
            if pet_type:
                info_parts.append(f"类型: {pet_type}")
            if initial_stage_name:
                info_parts.append(f"初始: {initial_stage_name}")
            if has_alt_color and has_alt_color == '是':
                info_parts.append("✨ 有异色")
            if update_version:
                info_parts.append(f"版本: {update_version}")
            
            if info_parts:
                response += f"📋 {' | '.join(info_parts)}\n"
            
            response += f"📊 属性: {element}\n"
            
            # 六维属性
            if is_data_missing:
                response += f"⚠️ **注意:** 该宠物为特殊形态，暂无战斗数据\n"
            else:
                response += f"⚔️ 六维:\n"
                response += f"  ❤️ HP: {hp}\n"
                response += f"  💪 物攻: {physical_attack}\n"
                response += f"  🔮 魔攻: {magic_attack}\n"
                response += f"  🛡️ 物防: {physical_defense}\n"
                response += f"  ✨ 魔防: {magic_defense}\n"
                response += f"  ⚡ 速度: {speed}\n"
            
            # 特性
            if ability and ability != '无':
                response += f"✨ 特性: {ability}\n"
                if ability_desc:
                    response += f"  > {ability_desc}\n"
            
            # 体型信息
            body_info = []
            if size:
                body_info.append(f"体型: {size}m")
            if weight:
                body_info.append(f"体重: {weight}kg")
            if distribution:
                body_info.append(f"分布: {distribution}")
            if body_info:
                response += f"📏 {' | '.join(body_info)}\n"
            
            # 简介
            if description:
                response += f"\n📝 **简介:**\n{description}\n"
            
            # 图鉴课题
            if quest_tasks:
                tasks = self._parse_list_field(quest_tasks)
                if tasks and len(tasks) > 0:
                    response += f"\n📚 **图鉴课题** ({len(tasks)}个):\n"
                    for i, task in enumerate(tasks, 1):
                        response += f"  {i}. {task}\n"
            
            # 课题技能石
            if quest_skill_stones:
                stones = self._parse_list_field(quest_skill_stones)
                if stones and len(stones) > 0:
                    response += f"\n💎 **课题技能石** ({len(stones)}个):\n"
                    response += "  • " + " | ".join(stones) + "\n"
            
            # 技能列表
            if skills:
                skills_list = self._parse_list_field(skills)
                if skills_list and len(skills_list) > 0:
                    response += f"\n🎯 **技能列表** ({len(skills_list)}个):\n"
                    # 每行显示3个技能
                    for i in range(0, len(skills_list), 3):
                        chunk = skills_list[i:i+3]
                        response += "  • " + " | ".join(chunk) + "\n"
            
            # 血脉技能
            if bloodline_skills:
                bloodline_list = self._parse_list_field(bloodline_skills)
                if bloodline_list and len(bloodline_list) > 0:
                    response += f"\n🧬 **血脉技能** ({len(bloodline_list)}个):\n"
                    for i in range(0, len(bloodline_list), 3):
                        chunk = bloodline_list[i:i+3]
                        response += "  • " + " | ".join(chunk) + "\n"
            
            # 可学技能石
            if learnable_skill_stones:
                stone_list = self._parse_list_field(learnable_skill_stones)
                if stone_list and len(stone_list) > 0:
                    response += f"\n💎 **可学技能石** ({len(stone_list)}个):\n"
                    for i in range(0, len(stone_list), 4):
                        chunk = stone_list[i:i+4]
                        response += "  • " + " | ".join(chunk) + "\n"
            
            return response
        
        elif self.response_style == "卡片式":
            # 卡片式：中等信息量
            element_emoji = {
                '火': '🔥', '水': '💧', '草': '🌿', '电': '⚡',
                '冰': '❄️', '龙': '🐉', '光': '✨', '暗': '🌑'
            }.get(element.split('+')[0] if '+' in element else element, '⭐')
            
            response = f"{element_emoji} **{name}**\n"
            response += f"> 属性: {element}\n"
            
            # 基本信息
            info_parts = []
            if stage:
                info_parts.append(stage)
            if pet_type:
                info_parts.append(pet_type)
            if initial_stage_name:
                info_parts.append(f"初始:{initial_stage_name}")
            if info_parts:
                response += f"> 📋 {' | '.join(info_parts)}\n"
            
            # 六维属性
            if is_data_missing:
                response += f"> ⚠️ 特殊形态，暂无战斗数据\n"
            else:
                response += f"> ❤️ {hp} | 💪 {physical_attack} | 🔮 {magic_attack}\n"
                response += f"> 🛡️ {physical_defense} | ✨ {magic_defense} | ⚡ {speed}\n"
            
            if ability and ability != '无':
                response += f"> ✨ {ability}\n"
            
            if description:
                # 截断简介，最多50字
                short_desc = description[:50] + "..." if len(description) > 50 else description
                response += f"> 📝 {short_desc}\n"
            
            return response
        
        else:
            # 简洁模式（默认）：基本信息 + 关键属性
            response = f"`{name}` | {element}系\n"
            
            # 显示阶段和类型
            if stage or pet_type:
                info_parts = []
                if stage:
                    info_parts.append(stage)
                if pet_type:
                    info_parts.append(pet_type)
                response += f"📋 {' | '.join(info_parts)}\n"
            
            # 六维属性
            if is_data_missing:
                response += f"⚠️ 特殊形态，暂无战斗数据\n"
            else:
                response += f"❤️ {hp} | 💪 {physical_attack} | 🔮 {magic_attack} | ⚡ {speed}\n"
            
            if ability and ability != '无':
                response += f"✨ {ability}\n"
            
            if description:
                short_desc = description[:40] + "..." if len(description) > 40 else description
                response += f"📝 {short_desc}"
            
            return response
    
    def _format_skill_response(self, skill_data: Dict[str, Any]) -> str:
        """
        根据配置风格格式化技能信息
        
        Args:
            skill_data: 技能数据字典
            
        Returns:
            格式化后的文本
        """
        name = skill_data.get('name', '未知')
        element = skill_data.get('element', '未知')
        power = skill_data.get('power', '0')
        effect = skill_data.get('effect', '无特殊效果')
        cost = skill_data.get('cost', '0')
        category = skill_data.get('category', '魔法')
        
        if self.response_style == "详细":
            return f"""🎯 **{name}**
━━━━━━━━━━━━━━
📊 属性: {element}
⚔️ 类型: {category}
💪 威力: {power}
🔮 魔力消耗: {cost}
📝 效果: {effect}"""
        
        elif self.response_style == "卡片式":
            return f"""🎯 **{name}**
> 属性: {element} | 类型: {category}
> 威力: {power} | 消耗: {cost}"""
        
        else:
            return f"`{name}` | {element}系 | 威力: {power} | 消耗: {cost}"
    
    def _analyze_query_intent(self, query: str) -> Dict[str, Any]:
        """
        分析用户查询意图（分级检索）
        
        Args:
            query: 用户原始查询
            
        Returns:
            意图字典，包含: type, pet_name, detail_type
            例如: {'type': 'pet_detail', 'pet_name': '迪莫', 'detail_type': 'bloodline_skills'}
        """
        import re
        
        # 先清理常见的语气词、助词和无意义前缀/后缀
        cleaned_query = query.strip()
                
        logger.info(f"🔍 原始查询: '{query}'")
                
        # 移除游戏名称前缀（按长度排序，优先匹配长的）
        for prefix in sorted(['洛克王国', '洛克'], key=len, reverse=True):
            if cleaned_query.startswith(prefix):
                cleaned_query = cleaned_query[len(prefix):].strip()
                
        # 移除常见的前缀词（按长度排序，优先匹配长的）
        for prefix in sorted(['怎么获得', '如何获得', '怎么', '如何', '怎样'], key=len, reverse=True):
            if cleaned_query.startswith(prefix):
                cleaned_query = cleaned_query[len(prefix):].strip()
                
        logger.info(f"🔧 清理前缀后: '{cleaned_query}'")
                
        # 移除常见的后缀词（按长度排序，优先匹配长的）
        for suffix in sorted(['怎么获得', '如何获得', '是什么', '的介绍', '的资料', '的信息'], key=len, reverse=True):
            if cleaned_query.endswith(suffix):
                cleaned_query = cleaned_query[:-len(suffix)].strip()
                
        # 特殊处理：移除"有哪些"、"有什么"等中间词
        for word in ['有哪些', '有什么']:
            cleaned_query = cleaned_query.replace(word, ' ').strip()
                        
        logger.info(f"🔧 清理后最终: '{cleaned_query}'")
                
        # ========== 第一优先级：检测宠物详细查询（宠物名 + 详细信息类型）==========
        # 支持多种格式：
        # 1. "XX的YYY" - 使用"的"连接
        # 2. "XX YYY" - 使用空格分隔
        # 3. "XXYYY" - 直接拼接
        # 4. "XX会/有/是什么YYY" - 自然语言
        detail_patterns = [
            # ====== 技能相关 ======
            # 带"的"的格式
            (r'^(.+?)\s*的\s*(?:所有技能|全部技能|完整技能|技能列表|配招|推荐技能)$', 'all_skills'),
            (r'^(.+?)\s*的\s*技能$', 'skills'),
            (r'^(.+?)\s*的\s*血脉技能$', 'bloodline_skills'),
            (r'^(.+?)\s*的\s*可学技能石$', 'learnable_stones'),
            (r'^(.+?)\s*的\s*课题技能石$', 'quest_stones'),
            # 不带"的"的格式（空格分隔）
            (r'^(.+?)\s+(?:所有技能|全部技能|完整技能|技能列表|配招|推荐技能)$', 'all_skills'),
            (r'^(.+?)\s+技能$', 'skills'),
            (r'^(.+?)\s+血脉技能$', 'bloodline_skills'),
            (r'^(.+?)\s+可学技能石$', 'learnable_stones'),
            (r'^(.+?)\s+课题技能石$', 'quest_stones'),
            # 自然语言格式
            (r'^(.+?)(?:会|能|可以)(?:学|用|使)(?:什么|哪些)?(?:技能)?$', 'skills'),
            (r'^(.+?)(?:有|会)(?:哪些|什么)?技能$', 'skills'),
            (r'^(.+?)的?(?:配招|推荐技能|技能搭配)$', 'all_skills'),
            # 无空格拼接
            (r'^(.+?)(?:所有技能|全部技能|完整技能|技能列表|配招)$', 'all_skills'),
            (r'^(.+?)技能$', 'skills'),
            
            # ====== 特性相关 ======
            # 带"的"的格式
            (r'^(.+?)\s*的\s*特性$', 'ability'),
            (r'^(.+?)\s*的\s*天赋$', 'talent'),
            # 不带"的"的格式
            (r'^(.+?)\s+特性$', 'ability'),
            (r'^(.+?)\s+天赋$', 'talent'),
            # 自然语言格式
            (r'^(.+?)(?:有|是)(?:什么|哪些)?特性$', 'ability'),
            (r'^(.+?)(?:有|是)(?:什么|哪些)?天赋$', 'talent'),
            (r'^(.+?)的特性是什么$', 'ability'),
            (r'^(.+?)的天赋是什么$', 'talent'),
            # 无空格拼接
            (r'^(.+?)特性$', 'ability'),
            (r'^(.+?)天赋$', 'talent'),
            
            # ====== 属性相关 ======
            # 带"的"的格式
            (r'^(.+?)\s*的\s*属性$', 'element'),
            (r'^(.+?)\s*的\s*系别$', 'element'),
            # 不带"的"的格式
            (r'^(.+?)\s+属性$', 'element'),
            (r'^(.+?)\s+系别$', 'element'),
            # 自然语言格式
            (r'^(.+?)是(?:什么|几)系$', 'element'),
            (r'^(.+?)是(?:什么|哪些)?属性$', 'element'),
            (r'^(.+?)的属性是什么$', 'element'),
            # 无空格拼接
            (r'^(.+?)属性$', 'element'),
            (r'^(.+?)系别$', 'element'),
            
            # ====== HP/生命相关 ======
            # 带"的"的格式
            (r'^(.+?)\s*的\s*(?:HP|hp|Hp|hP|生命|生命值|体力|血量)$', 'hp'),
            # 不带"的"的格式
            (r'^(.+?)\s+(?:HP|hp|Hp|hP|生命|生命值|体力|血量)$', 'hp'),
            # 无空格拼接
            (r'^(.+?)(?:HP|hp|生命|生命值|体力|血量)$', 'hp'),
            
            # ====== 物攻相关 ======
            # 带"的"的格式
            (r'^(.+?)\s*的\s*(?:物攻|物理攻击|攻击|atk|ATK|Attack|attack)$', 'physical_attack'),
            # 不带"的"的格式
            (r'^(.+?)\s+(?:物攻|物理攻击|攻击|atk|ATK|Attack|attack)$', 'physical_attack'),
            # 无空格拼接
            (r'^(.+?)(?:物攻|物理攻击|atk|ATK)$', 'physical_attack'),
            
            # ====== 魔攻相关 ======
            # 带"的"的格式
            (r'^(.+?)\s*的\s*(?:魔攻|魔法攻击|法攻|特攻|spatk|SPATK|SpAtk|Magic Attack|magic attack)$', 'magic_attack'),
            # 不带"的"的格式
            (r'^(.+?)\s+(?:魔攻|魔法攻击|法攻|特攻|spatk|SPATK|SpAtk|Magic Attack|magic attack)$', 'magic_attack'),
            # 无空格拼接
            (r'^(.+?)(?:魔攻|魔法攻击|法攻|特攻|spatk|SPATK)$', 'magic_attack'),
            
            # ====== 物防相关 ======
            # 带"的"的格式
            (r'^(.+?)\s*的\s*(?:物防|物理防御|防御|def|DEF|Defense|defense)$', 'physical_defense'),
            # 不带"的"的格式
            (r'^(.+?)\s+(?:物防|物理防御|防御|def|DEF|Defense|defense)$', 'physical_defense'),
            # 无空格拼接
            (r'^(.+?)(?:物防|物理防御|def|DEF)$', 'physical_defense'),
            
            # ====== 魔防相关 ======
            # 带"的"的格式
            (r'^(.+?)\s*的\s*(?:魔防|魔法防御|法防|特防|spdef|SPDEF|SpDef|Magic Defense|magic defense)$', 'magic_defense'),
            # 不带"的"的格式
            (r'^(.+?)\s+(?:魔防|魔法防御|法防|特防|spdef|SPDEF|SpDef|Magic Defense|magic defense)$', 'magic_defense'),
            # 无空格拼接
            (r'^(.+?)(?:魔防|魔法防御|法防|特防|spdef|SPDEF)$', 'magic_defense'),
            
            # ====== 速度相关 ======
            # 带"的"的格式
            (r'^(.+?)\s*的\s*(?:速度|速|spd|SPD|Speed|speed|先手)$', 'speed'),
            # 不带"的"的格式
            (r'^(.+?)\s+(?:速度|速|spd|SPD|Speed|speed|先手)$', 'speed'),
            # 无空格拼接
            (r'^(.+?)(?:速度|速|spd|SPD)$', 'speed'),
            
            # ====== 种族值/六维/面板 ======
            # 带"的"的格式
            (r'^(.+?)\s*的\s*(?:种族值|六维|面板|基础属性|能力值)$', 'stats'),
            # 不带"的"的格式
            (r'^(.+?)\s+(?:种族值|六维|面板|基础属性|能力值)$', 'stats'),
            # 无空格拼接
            (r'^(.+?)(?:种族值|六维|面板)$', 'stats'),
            
            # ====== 任务/课题相关 ======
            # 带"的"的格式
            (r'^(.+?)\s*的\s*(?:任务|课题|课题任务)$', 'quest_tasks'),
            # 不带"的"的格式
            (r'^(.+?)\s+(?:任务|课题|课题任务)$', 'quest_tasks'),
            # 自然语言格式
            (r'^(.+?)(?:要|需要)(?:做|完成)(?:什么|哪些)?任务$', 'quest_tasks'),
            (r'^(.+?)的任务是什么$', 'quest_tasks'),
            # 无空格拼接
            (r'^(.+?)(?:任务|课题)$', 'quest_tasks'),
            
            # ====== 进化相关 ======
            # 带"的"的格式
            (r'^(.+?)\s*的\s*(?:进化|进化条件|进化方式)$', 'evolution'),
            # 不带"的"的格式
            (r'^(.+?)\s+(?:进化|进化条件|进化方式)$', 'evolution'),
            # 自然语言格式
            (r'^(.+?)怎么进化$', 'evolution'),
            (r'^(.+?)进化成什么$', 'evolution'),
            (r'^(.+?)的进化条件是什么$', 'evolution'),
            # 无空格拼接
            (r'^(.+?)进化$', 'evolution'),
            
            # ====== 技能石相关 ======
            (r'^(.+?)技能石$', 'skill_stones'),
        ]
                
        for pattern, detail_type in detail_patterns:
            match = re.search(pattern, cleaned_query)
            if match:
                name = match.group(1).strip()
                # 清理宠物名末尾的"的"字（防止"迪莫的"被当作宠物名）
                if name.endswith('的'):
                    name = name[:-1].strip()
                        
                logger.info(f"🎯 匹配到详细查询: pattern='{pattern}', name='{name}', type='{detail_type}'")
                        
                # 过滤掉常见的非宠物名
                if name and len(name) >= 1 and name not in ['有', '的', '是', '怎么', '如何', '获得']:
                    return {
                        'type': 'pet_detail',
                        'pet_name': name,
                        'detail_type': detail_type
                    }
        
        # 检测技能石获取方式查询：“技能石 乘风”（反向语法）
        stone_pattern = r'^技能石\s*(.+)$'
        match = re.search(stone_pattern, cleaned_query)
        if match:
            stone_name = match.group(1).strip()
            if stone_name and len(stone_name) >= 1:
                return {
                    'type': 'skill_stone_info',
                    'stone_name': stone_name,
                    'only_source': False  # 显示完整信息
                }
        
        # 检测“怎么获得XX技能石”的查询
        source_pattern = r'(?:怎么|如何)(?:获得|获取|得到)(\S+?)(?:技能石|配方)'
        match = re.search(source_pattern, query)
        if match:
            stone_name = match.group(1).strip()
            if stone_name and len(stone_name) >= 1:
                return {
                    'type': 'skill_stone_info',
                    'stone_name': stone_name,
                    'only_source': True  # 只显示获取方式
                }
                
        # 检测属性筛选查询：“火系宠物有哪些”、“水系宠物列表”
        attr_pattern = r'(\S+?)(?:系|属性)?(?:宠物|精灵|有哪些|列表|推荐)'
        match = re.search(attr_pattern, cleaned_query)
        if match:
            attr_name = match.group(1).strip()
            # 移除“系”、“属性”等后缀
            attr_name = attr_name.replace('系', '').replace('属性', '').strip()
            # 常见属性列表
            valid_attrs = ['火', '水', '草', '电', '冰', '土', '风', '光', '暗', '毒', '龙', '机械', '武', '萌', '幽灵', '虫', '石', '普通']
            if attr_name in valid_attrs:
                return {
                    'type': 'attribute_filter',
                    'attribute': attr_name,
                    'entity_type': 'pet'
                }
        
        # 检测颜色宠物/精灵查询：“红色宠物”、“蓝色精灵”、“绿色宠物有哪些”
        color_pet_patterns = [
            (r'(\S+?)(?:的)?(?:宠物|精灵|魔灵|怪兽|伙伴)(?:有哪些|列表|推荐)?$', 'pet'),
            (r'(\S+?)(?:的)?(?:精灵蛋|蛋|宠物蛋)(?:有哪些|列表|推荐)?$', 'egg'),
        ]
                
        for pattern, entity_type in color_pet_patterns:
            match = re.search(pattern, cleaned_query)
            if match:
                keyword = match.group(1).strip()
                        
                # 检测是否明确指定了“颜色”关键词
                is_explicit_color = '颜色' in keyword or '色彩' in keyword
                        
                # 如果包含“颜色”关键词，提取实际颜色词
                if is_explicit_color:
                    keyword = re.sub(r'(?:颜色|色彩)', '', keyword).strip()
                        
                # 标准化颜色关键词
                color_normalization = {
                    '紫色': '紫', '蓝色': '蓝', '红色': '红', '绿色': '绿',
                    '黄色': '黄', '白色': '白', '黑色': '黑', '粉色': '粉', '橙色': '橙'
                }
                normalized_keyword = color_normalization.get(keyword, keyword)
                        
                # 检查是否是颜色关键词
                all_colors = ['红', '橙', '黄', '绿', '蓝', '紫', '粉', '白', '黑', '棕', '灰']
                if normalized_keyword in all_colors:
                    logger.info(f"🎨 检测到颜色{entity_type}查询: {normalized_keyword}")
                    return {
                        'type': 'color_filter',
                        'color': normalized_keyword,
                        'entity_type': entity_type
                    }
                
        # 检测稀有度宠物查询：“稀有宠物”、“史诗精灵”、“传说宠物有哪些”
        rarity_pet_patterns = [
            (r'(稀有|史诗|传说|绝版|限定)(?:的)?(?:宠物|精灵)(?:有哪些|列表|推荐)?$', 'pet'),
        ]
                
        for pattern, entity_type in rarity_pet_patterns:
            match = re.search(pattern, cleaned_query)
            if match:
                rarity = match.group(1).strip()
                logger.info(f"⭐ 检测到稀有度{entity_type}查询: {rarity}")
                return {
                    'type': 'rarity_filter',
                    'rarity': rarity,
                    'entity_type': entity_type
                }
                
        # 检测来源宠物查询：“家园宠物”、“活动精灵”、“限时宠物有哪些”
        source_pet_patterns = [
            (r'(家园|活动|限时|副本|挑战)(?:的)?(?:宠物|精灵)(?:有哪些|列表|推荐)?$', 'pet'),
        ]
                
        for pattern, entity_type in source_pet_patterns:
            match = re.search(pattern, cleaned_query)
            if match:
                source = match.group(1).strip()
                logger.info(f"📍 检测到来源{entity_type}查询: {source}")
                return {
                    'type': 'source_filter',
                    'source': source,
                    'entity_type': entity_type
                }
                
        # 检测阶段宠物查询：“初始形态宠物”、“最终形态精灵”、“幼年期宠物”
        stage_pet_patterns = [
            (r'(初始|最终|第一|第二|第三|第四|第五|幼年|成年|完全|终极)(?:形态|期|阶段)?(?:的)?(?:宠物|精灵)(?:有哪些|列表|推荐)?$', 'pet'),
        ]
                
        for pattern, entity_type in stage_pet_patterns:
            match = re.search(pattern, cleaned_query)
            if match:
                stage = match.group(1).strip()
                logger.info(f"🔄 检测到阶段{entity_type}查询: {stage}")
                return {
                    'type': 'stage_filter',
                    'stage': stage,
                    'entity_type': entity_type
                }
                
        # 检测道具类型/分类筛选：“家园家具”、“蓝色家具”、“紫色道具”、“紫色的家具”、“蓝颜色家具”
        item_patterns = [
            (r'(\S+?)(?:的)?(?:家具|装饰|摆件)', 'furniture'),  # 支持“紫色的家具”
            (r'(\S+?)(?:的)?(?:道具|物品|装备|材料)', 'item'),  # 支持“紫色的道具”
            (r'(\S+?)(?:的)?(?:技能石|配方|石头)', 'skill_stone'),  # 支持“紫色的技能石”
            (r'(\S+?)(?:的)?(?:咕噜球|球)', 'gumball'),  # 支持“蓝色的咕噜球”
            (r'(\S+?)(?:的)?(?:果实|果子)', 'fruit'),  # 支持“红色的果实”
        ]
                
        for pattern, category in item_patterns:
            match = re.search(pattern, cleaned_query)
            if match:
                keyword = match.group(1).strip()  # 去除前后空格
                logger.info(f"🔧 检测到分类模式: pattern='{pattern}', keyword='{keyword}', category='{category}'")
                
                # 检测是否明确指定了"颜色"关键词（如"蓝颜色家具"）
                is_explicit_color = '颜色' in keyword or '色彩' in keyword
                
                # 如果包含"颜色"关键词，提取实际颜色词
                if is_explicit_color:
                    # 移除"颜色"、"色彩"等词
                    keyword = re.sub(r'(?:颜色|色彩)', '', keyword).strip()
                    logger.info(f"🎨 检测到明确颜色查询: 原始keyword='{match.group(1)}', 提取后='{keyword}'")
                
                # 标准化颜色关键词：将“紫色”→“紫”，“蓝色”→“蓝”等
                color_normalization = {
                    '紫色': '紫', '蓝色': '蓝', '红色': '红', '绿色': '绿',
                    '黄色': '黄', '白色': '白', '黑色': '黑', '粉色': '粉', '橙色': '橙'
                }
                normalized_keyword = color_normalization.get(keyword, keyword)
                
                # 检查是否是颜色或稀有度关键词
                # 稀有度专用颜色：蓝、紫、橙（这些通常表示稀有度）
                rarity_colors = ['蓝', '紫', '橙']
                # 纯颜色关键词：红、绿、黄、白、黑、粉（这些通常是实际颜色）
                pure_colors = ['红', '绿', '黄', '白', '黑', '粉']
                # 稀有度文本关键词
                rarity_keywords = ['稀有', '史诗', '传说', '绝版', '限定']
                        
                # 判断逻辑：
                # 1. 如果用户明确说"颜色" → filter_type='actual_color'（只查main_color）
                # 2. 如果是稀有度文本关键词 → filter_type='rarity'（只查rarity）
                # 3. 如果是稀有度颜色（蓝/紫/橙）且未明确说"颜色" → filter_type='rarity_color'（优先查rarity，回退main_color）
                # 4. 如果是纯颜色 → filter_type='actual_color'（查main_color）
                is_rarity_text = any(r in normalized_keyword for r in rarity_keywords)
                is_rarity_color = normalized_keyword in rarity_colors
                is_pure_color = normalized_keyword in pure_colors
                
                # 确定filter_type
                if is_explicit_color:
                    # 用户明确说了"颜色"，查询实际颜色
                    filter_type_detected = 'actual_color'
                elif is_rarity_text:
                    # 稀有度文本关键词
                    filter_type_detected = 'rarity'
                elif is_rarity_color:
                    # 稀有度颜色（蓝/紫/橙），默认当作稀有度查询
                    filter_type_detected = 'rarity_color'
                elif is_pure_color:
                    # 纯颜色，查询实际颜色
                    filter_type_detected = 'actual_color'
                else:
                    filter_type_detected = None
                
                logger.info(f"🔧 颜色判断: normalized_keyword='{normalized_keyword}', is_explicit_color={is_explicit_color}, is_pure_color={is_pure_color}, is_rarity_color={is_rarity_color}, is_rarity_text={is_rarity_text}, filter_type={filter_type_detected}")
                        
                if filter_type_detected or normalized_keyword in ['家园', '活动', '限时']:
                    final_filter_type = filter_type_detected if filter_type_detected else 'source'
                    logger.info(f"🎯 返回分类筛选意图: keyword='{normalized_keyword}', filter_type='{final_filter_type}'")
                    return {
                        'type': 'category_filter',
                        'keyword': normalized_keyword,
                        'category': category,
                        'filter_type': final_filter_type
                    }
                
        # 默认意图：普通查询
        return {'type': 'normal'}
    
    def _format_pet_detail_info(self, pet: Dict, detail_type: str) -> str:
        """
        格式化宠物的详细信息（血脉技能、技能石等）
        
        Args:
            pet: 宠物数据字典
            detail_type: 详细信息类型
            
        Returns:
            格式化的文本
        """
        import json
        
        pet_name = pet.get('name', '未知')
        
        if detail_type == 'bloodline_skills':
            bloodline_skills = pet.get('bloodline_skills', '')
            skills_list = self._parse_list_field(bloodline_skills)
            
            response = f"💫 **{pet_name} - 血脉技能**\n"
            response += "━━━━━━━━━━━━━━\n"
            
            if skills_list:
                for i, skill in enumerate(skills_list, 1):
                    response += f"  {i}. {skill}\n"
            else:
                response += "  (暂无血脉技能信息)"
            
            return response
        
        elif detail_type == 'skill_stones' or detail_type == 'learnable_stones':
            learnable_stones = pet.get('learnable_skill_stones', '')
            stones_list = self._parse_list_field(learnable_stones)
            
            response = f"📖 **{pet_name} - 可学技能石**\n"
            response += "━━━━━━━━━━━━━━\n"
            
            if stones_list:
                for i, stone in enumerate(stones_list, 1):
                    response += f"  {i}. {stone}\n"
            else:
                response += "  (暂无可学技能石信息)"
            
            return response
        
        elif detail_type == 'quest_stones':
            quest_stones = pet.get('quest_skill_stones', '')
            stones_list = self._parse_list_field(quest_stones)
            
            response = f"🎯 **{pet_name} - 课题技能石**\n"
            response += "━━━━━━━━━━━━━━\n"
            
            if stones_list:
                for i, stone in enumerate(stones_list, 1):
                    response += f"  {i}. {stone}\n"
            else:
                response += "  (暂无课题技能石信息)"
            
            return response
        
        elif detail_type == 'all_skills':
            skills = pet.get('skills', '')
            skills_list = self._parse_list_field(skills)
            
            response = f"📚 **{pet_name} - 完整技能列表**\n"
            response += "━━━━━━━━━━━━━━\n"
            
            if skills_list:
                # 显示所有技能，每行5个
                for i in range(0, len(skills_list), 5):
                    batch = skills_list[i:i+5]
                    response += "  " + ", ".join(batch) + "\n"
                response += f"\n总计: {len(skills_list)} 个技能"
            else:
                response += "  (暂无技能信息)"
            
            return response
        
        elif detail_type == 'skills':
            # 与 all_skills 相同
            skills = pet.get('skills', '')
            skills_list = self._parse_list_field(skills)
            
            response = f"⚔️ **{pet_name} - 技能列表**\n"
            response += "━━━━━━━━━━━━━━\n"
            
            if skills_list:
                for i in range(0, len(skills_list), 5):
                    batch = skills_list[i:i+5]
                    response += "  " + ", ".join(batch) + "\n"
                response += f"\n总计: {len(skills_list)} 个技能"
            else:
                response += "  (暂无技能信息)"
            
            return response
        
        elif detail_type == 'ability' or detail_type == 'talent':
            ability = pet.get('ability', '')
            ability_desc = pet.get('ability_desc', '')
            
            response = f"✨ **{pet_name} - 特性**\n"
            response += "━━━━━━━━━━━━━━\n"
            
            if ability:
                response += f"🔮 **{ability}**\n"
                if ability_desc:
                    response += f"\n📝 {ability_desc}\n"
            else:
                response += "  (暂无特性信息)"
            
            return response
        
        elif detail_type == 'element':
            element = pet.get('element', '')
            element2 = pet.get('element2', '')
            
            response = f"🎯 **{pet_name} - 属性**\n"
            response += "━━━━━━━━━━━━━━\n"
            
            if element:
                if element2:
                    response += f"  主属性: {element}\n"
                    response += f"  副属性: {element2}\n"
                else:
                    response += f"  属性: {element}\n"
            else:
                response += "  (暂无属性信息)"
            
            return response
        
        elif detail_type == 'hp' or detail_type == 'stats':
            hp = pet.get('hp', 0)
            physical_attack = pet.get('physical_attack', 0)
            magic_attack = pet.get('magic_attack', 0)
            physical_defense = pet.get('physical_defense', 0)
            magic_defense = pet.get('magic_defense', 0)
            speed = pet.get('speed', 0)
            
            response = f"💪 **{pet_name} - 种族值**\n"
            response += "━━━━━━━━━━━━━━\n"
            response += f"  ❤️ HP: {hp}\n"
            response += f"  ⚔️ 物攻: {physical_attack}\n"
            response += f"  🔮 魔攻: {magic_attack}\n"
            response += f"  🛡️ 物防: {physical_defense}\n"
            response += f"  ✨ 魔防: {magic_defense}\n"
            response += f"  💨 速度: {speed}\n"
            total = hp + physical_attack + magic_attack + physical_defense + magic_defense + speed
            response += f"\n  📊 总和: {total}\n"
            
            return response
        
        elif detail_type == 'physical_attack':
            value = pet.get('physical_attack', 0)
            response = f"⚔️ **{pet_name} - 物理攻击**\n"
            response += "━━━━━━━━━━━━━━\n"
            response += f"  物攻: {value}\n"
            return response
        
        elif detail_type == 'magic_attack':
            value = pet.get('magic_attack', 0)
            response = f"🔮 **{pet_name} - 魔法攻击**\n"
            response += "━━━━━━━━━━━━━━\n"
            response += f"  魔攻: {value}\n"
            return response
        
        elif detail_type == 'physical_defense':
            value = pet.get('physical_defense', 0)
            response = f"🛡️ **{pet_name} - 物理防御**\n"
            response += "━━━━━━━━━━━━━━\n"
            response += f"  物防: {value}\n"
            return response
        
        elif detail_type == 'magic_defense':
            value = pet.get('magic_defense', 0)
            response = f"✨ **{pet_name} - 魔法防御**\n"
            response += "━━━━━━━━━━━━━━\n"
            response += f"  魔防: {value}\n"
            return response
        
        elif detail_type == 'speed':
            value = pet.get('speed', 0)
            response = f"💨 **{pet_name} - 速度**\n"
            response += "━━━━━━━━━━━━━━\n"
            response += f"  速度: {value}\n"
            return response
        
        elif detail_type == 'quest_tasks':
            quest_tasks = pet.get('quest_tasks', '')
            tasks_list = self._parse_list_field(quest_tasks)
            
            response = f"📋 **{pet_name} - 课题任务**\n"
            response += "━━━━━━━━━━━━━━\n"
            
            if tasks_list:
                for i, task in enumerate(tasks_list, 1):
                    response += f"  {i}. {task}\n"
            else:
                response += "  (暂无课题任务信息)"
            
            return response
        
        elif detail_type == 'evolution':
            evolution_condition = pet.get('evolution_condition', '')
            
            response = f"🔄 **{pet_name} - 进化条件**\n"
            response += "━━━━━━━━━━━━━━\n"
            
            if evolution_condition:
                response += f"  {evolution_condition}\n"
            else:
                response += "  (暂无进化信息)"
            
            return response
        
        else:
            return ""
    
    def _format_skill_stone_info(self, stone_name: str, only_source: bool = False) -> str:
        """
        格式化技能石的获取信息
            
        Args:
            stone_name: 技能石名称（如“乘风”）
            only_source: 是否只显示获取方式
                
        Returns:
            格式化的文本
        """
        import json
            
        # 1. 查询道具表中的技能石
        items = self.db_service.get_item_info(f"技能石/{stone_name}", fuzzy=False, limit=10)
            
        if not items:
            # 尝试直接匹配名称
            items = self.db_service.get_item_info(stone_name, fuzzy=True, limit=10)
            # 过滤出分类为“技能石”的
            items = [item for item in items if item.get('category') == '技能石']
            
        if not items:
            return f"❌ 未找到技能石 \"{stone_name}\""
        
        # 如果只需要获取方式，直接返回
        if only_source:
            item = items[0]
            source = item.get('source', '')
            if source and source.strip():
                response = f"💎 **技能石 - {stone_name}**\n"
                response += "━━━━━━━━━━━━━━\n\n"
                response += f"🛒 **获取方式:**\n{source}\n"
                return response
            else:
                return f"💎 **技能石 - {stone_name}**\n━━━━━━━━━━━━━━\n\n⚠️ 暂无获取方式信息\n"
            
        response = f"💎 **技能石 - {stone_name}**\n"
        response += "━━━━━━━━━━━━━━\n"
            
        for item in items[:3]:  # 最多显示3个
            response += f"\n📦 **{item['name']}**\n"
            if item.get('rarity'):
                response += f"⭐ 稀有度: {item['rarity']}\n"
            if item.get('subcategory'):
                response += f"🔹 类型: {item['subcategory']}\n"
                
            # 显示来源信息（关键修复）
            source = item.get('source', '')
            if source and source.strip():
                response += f"\n🛒 **获取方式:**\n{source}\n"
            else:
                response += f"\n⚠️ 暂无获取方式信息\n"
            
        # 2. 查询哪些宠物可以学习这个技能石
        cursor = self.db_service.conn.cursor()
        cursor.execute("""
            SELECT name FROM pets 
            WHERE learnable_skill_stones LIKE ?
            LIMIT 10
        """, (f'%{stone_name}%',))
            
        pets_with_stone = [row[0] for row in cursor.fetchall()]
            
        if pets_with_stone:
            response += f"\n🐾 **可学习此技能石的宠物** ({len(pets_with_stone)}个):\n"
            response += "  " + ", ".join(pets_with_stone[:10])
            if len(pets_with_stone) > 10:
                response += f"...等共{len(pets_with_stone)}个"
            response += "\n"
            
        # 3. 如果同时有同名技能，也显示一下
        skills = self.db_service.get_skill_info(stone_name, fuzzy=False, limit=1)
        if skills:
            skill = skills[0]
            response += f"\n📚 **相关技能:** {skill['name']} ({skill['element']}系)\n"
            if skill.get('power'):
                response += f"  威力: {skill['power']}"
            if skill.get('cost'):
                response += f" | PP: {skill['cost']}"
            if skill.get('category'):
                response += f" | 类型: {skill['category']}"
            response += "\n"
            
        return response
    
    def _handle_color_filter(self, color: str, entity_type: str) -> str:
        """
        处理颜色宠物/精灵蛋查询：“红色宠物”、“蓝色精灵蛋”
        
        Args:
            color: 颜色关键词（如“红”、“蓝”）
            entity_type: 实体类型（pet=宠物, egg=精灵蛋）
            
        Returns:
            格式化的文本
        """
        if entity_type not in ['pet', 'egg']:
            return f"❌ 不支持的实体类型: {entity_type}"
        
        # 查询 pets 表中 main_color 字段匹配的宠物
        cursor = self.db_service.conn.cursor()
        
        # 构建查询条件
        query = "SELECT name, element, element2, stage, main_color FROM pets WHERE main_color = ?"
        
        # 如果是精灵蛋，过滤出包含“蛋”字的宠物名
        if entity_type == 'egg':
            query += " AND (name LIKE '%蛋%' OR name LIKE '%卵%')"
        
        query += " ORDER BY name LIMIT 50"
        
        cursor.execute(query, (color,))
        pets = [dict(zip(['name', 'element', 'element2', 'stage', 'main_color'], row)) for row in cursor.fetchall()]
        
        logger.info(f"🎨 颜色{entity_type}筛选: color='{color}', 找到 {len(pets)} 个结果")
        
        if not pets:
            entity_name = "宠物" if entity_type == 'pet' else "精灵蛋"
            return f"❌ 未找到{color}色的{entity_name}"
        
        entity_name = "宠物" if entity_type == 'pet' else "精灵蛋"
        response = f"🎨 **{color}色{entity_name}列表** (共{len(pets)}个):\n"
        response += "━━━━━━━━━━━━━━\n\n"
        
        # 使用分页配置
        page_size = self.page_size
        display_pets = pets[:page_size]
        
        for i, pet in enumerate(display_pets, 1):
            element = pet.get('element', '未知')
            element2 = pet.get('element2', '')
            extra = f"/{element2}" if element2 else ""
            stage = pet.get('stage', '')
            stage_str = f" [{stage}]" if stage else ""
            response += f"{i}. {pet['name']} ({element}{extra}系){stage_str}\n"
        
        if len(pets) > page_size:
            response += f"\n...还有 {len(pets) - page_size} 个"
        
        response += f"\n💡 提示：输入完整名称可查看详细信息"
        return response
    
    def _handle_rarity_filter(self, rarity: str, entity_type: str) -> str:
        """
        处理稀有度宠物查询：“稀有宠物”、“史诗精灵”
        
        Args:
            rarity: 稀有度关键词（如“稀有”、“史诗”）
            entity_type: 实体类型（pet=宠物）
            
        Returns:
            格式化的文本
        """
        if entity_type != 'pet':
            return f"❌ 不支持的实体类型: {entity_type}"
        
        # 查询 pets 表中 description 或 ability 字段包含稀有度关键词的宠物
        cursor = self.db_service.conn.cursor()
        
        query = "SELECT name, element, element2, stage, description, ability FROM pets WHERE (description LIKE ? OR ability LIKE ?) ORDER BY name LIMIT 50"
        
        cursor.execute(query, (f'%{rarity}%', f'%{rarity}%'))
        pets = [dict(zip(['name', 'element', 'element2', 'stage', 'description', 'ability'], row)) for row in cursor.fetchall()]
        
        logger.info(f"⭐ 稀有度{entity_type}筛选: rarity='{rarity}', 找到 {len(pets)} 个结果")
        
        if not pets:
            return f"❌ 未找到{rarity}稀有度的宠物"
        
        response = f"⭐ **{rarity}稀有度宠物列表** (共{len(pets)}个):\n"
        response += "━━━━━━━━━━━━━━\n\n"
        
        # 使用分页配置
        page_size = self.page_size
        display_pets = pets[:page_size]
        
        for i, pet in enumerate(display_pets, 1):
            element = pet.get('element', '未知')
            element2 = pet.get('element2', '')
            extra = f"/{element2}" if element2 else ""
            stage = pet.get('stage', '')
            stage_str = f" [{stage}]" if stage else ""
            response += f"{i}. {pet['name']} ({element}{extra}系){stage_str}\n"
        
        if len(pets) > page_size:
            response += f"\n...还有 {len(pets) - page_size} 个"
        
        response += f"\n💡 提示：输入完整名称可查看详细信息"
        return response
    
    def _handle_source_filter(self, source: str, entity_type: str) -> str:
        """
        处理来源宠物查询：“家园宠物”、“活动精灵”
        
        Args:
            source: 来源关键词（如“家园”、“活动”）
            entity_type: 实体类型（pet=宠物）
            
        Returns:
            格式化的文本
        """
        if entity_type != 'pet':
            return f"❌ 不支持的实体类型: {entity_type}"
        
        # 查询 pets 表中 description 字段包含来源关键词的宠物
        cursor = self.db_service.conn.cursor()
        
        # 根据来源类型扩展关键词
        source_map = {
            '家园': ['家园', '家具店', '商店'],
            '活动': ['活动', '限时', '节日'],
            '限时': ['限时', '活动', '节日'],
            '副本': ['副本', '挑战', '关卡'],
            '挑战': ['挑战', '副本', '关卡'],
        }
        
        source_keywords = source_map.get(source, [source])
        like_conditions = ' OR '.join([f"description LIKE '%{s}%" for s in source_keywords])
        
        query = f"SELECT name, element, element2, stage, description FROM pets WHERE ({like_conditions}) ORDER BY name LIMIT 50"
        
        cursor.execute(query)
        pets = [dict(zip(['name', 'element', 'element2', 'stage', 'description'], row)) for row in cursor.fetchall()]
        
        logger.info(f"📍 来源{entity_type}筛选: source='{source}', 找到 {len(pets)} 个结果")
        
        if not pets:
            return f"❌ 未找到{source}相关的宠物"
        
        response = f"📍 **{source}相关宠物列表** (共{len(pets)}个):\n"
        response += "━━━━━━━━━━━━━━\n\n"
        
        # 使用分页配置
        page_size = self.page_size
        display_pets = pets[:page_size]
        
        for i, pet in enumerate(display_pets, 1):
            element = pet.get('element', '未知')
            element2 = pet.get('element2', '')
            extra = f"/{element2}" if element2 else ""
            stage = pet.get('stage', '')
            stage_str = f" [{stage}]" if stage else ""
            response += f"{i}. {pet['name']} ({element}{extra}系){stage_str}\n"
        
        if len(pets) > page_size:
            response += f"\n...还有 {len(pets) - page_size} 个"
        
        response += f"\n💡 提示：输入完整名称可查看详细信息"
        return response
    
    def _handle_stage_filter(self, stage: str, entity_type: str) -> str:
        """
        处理阶段宠物查询：“初始形态宠物”、“最终形态精灵”
        
        Args:
            stage: 阶段关键词（如“初始”、“最终”）
            entity_type: 实体类型（pet=宠物）
            
        Returns:
            格式化的文本
        """
        if entity_type != 'pet':
            return f"❌ 不支持的实体类型: {entity_type}"
        
        # 映射阶段关键词到数据库中的 stage 值
        stage_map = {
            '初始': ['初始形态', '初级'],
            '第一': ['初始形态', '初级'],
            '幼年': ['幼年', '幼年期'],
            '成年': ['成年', '成长期'],
            '完全': ['完全体', '成熟期'],
            '终极': ['终极形态', '完全体'],
            '最终': ['最终形态', '究极体'],
        }
        
        stage_keywords = stage_map.get(stage, [stage])
        
        # 查询 pets 表中 stage 字段匹配阶段关键词的宠物
        cursor = self.db_service.conn.cursor()
        
        like_conditions = ' OR '.join([f"stage LIKE '%{s}%" for s in stage_keywords])
        query = f"SELECT name, element, element2, stage FROM pets WHERE ({like_conditions}) ORDER BY name LIMIT 50"
        
        cursor.execute(query)
        pets = [dict(zip(['name', 'element', 'element2', 'stage'], row)) for row in cursor.fetchall()]
        
        logger.info(f"🔄 阶段{entity_type}筛选: stage='{stage}', 找到 {len(pets)} 个结果")
        
        if not pets:
            return f"❌ 未找到{stage}阶段的宠物"
        
        response = f"🔄 **{stage}阶段宠物列表** (共{len(pets)}个):\n"
        response += "━━━━━━━━━━━━━━\n\n"
        
        # 使用分页配置
        page_size = self.page_size
        display_pets = pets[:page_size]
        
        for i, pet in enumerate(display_pets, 1):
            element = pet.get('element', '未知')
            element2 = pet.get('element2', '')
            extra = f"/{element2}" if element2 else ""
            pet_stage = pet.get('stage', '')
            stage_str = f" [{pet_stage}]" if pet_stage else ""
            response += f"{i}. {pet['name']} ({element}{extra}系){stage_str}\n"
        
        if len(pets) > page_size:
            response += f"\n...还有 {len(pets) - page_size} 个"
        
        response += f"\n💡 提示：输入完整名称可查看详细信息"
        return response
    
    def _handle_attribute_filter(self, attribute: str, entity_type: str) -> str:
        """
        处理属性筛选查询：“火系宠物有哪些”
        
        Args:
            attribute: 属性名称（如“火”）
            entity_type: 实体类型（如“pet”）
            
        Returns:
            格式化的文本
        """
        if entity_type == 'pet':
            # 查询该属性的宠物
            pets = self.db_service.get_pets_by_element(attribute, limit=50)
            
            if not pets:
                return f"❌ 未找到{attribute}系宠物"
            
            response = f"🔥 **{attribute}系宠物列表** (共{len(pets)}个):\n"
            response += "━━━━━━━━━━━━━━\n\n"
            
            # 使用分页配置
            page_size = self.page_size
            display_pets = pets[:page_size]
            
            for i, pet in enumerate(display_pets, 1):
                element2 = pet.get('element2', '')
                extra = f"/{element2}" if element2 else ""
                response += f"{i}. {pet['name']} ({pet['element']}{extra}系)\n"
            
            if len(pets) > page_size:
                response += f"\n...还有 {len(pets) - page_size} 个"
            
            response += f"\n💡 提示：输入完整名称可查看详细信息"
            return response
        
        return f"❌ 不支持的实体类型: {entity_type}"
    
    def _handle_category_filter(self, keyword: str, category: str, filter_type: str) -> str:
        """
        处理分类/颜色/稀有度筛选：“蓝色家具”、“紫色道具”
        
        Args:
            keyword: 关键词（如“蓝”、“家园”）
            category: 类别（如“furniture”、“item”）
            filter_type: 筛选类型（color/rarity/source）
            
        Returns:
            格式化的文本
        """
        import json
        
        # 映射类别到数据库表
        db_category_map = {
            'furniture': '家具',
            'item': '',  # 所有道具
            'skill_stone': '技能石',
            'gumball': '咕噜球',
            'fruit': '精灵果实',
        }
        
        db_category = db_category_map.get(category, '')
        
        # 构建查询条件
        cursor = self.db_service.conn.cursor()
        
        if filter_type == 'actual_color':
            # 实际颜色筛选：只查询 main_color 字段（大模型识别的实际颜色）
            color_map = {
                '蓝': ['蓝'],
                '红': ['红'],
                '绿': ['绿'],
                '黄': ['黄'],
                '紫': ['紫'],
                '白': ['白'],
                '黑': ['黑'],
                '粉': ['粉'],
                '橙': ['橙'],
            }
            
            color_keywords = color_map.get(keyword, [keyword])
            like_conditions = ' OR '.join([f"main_color = '{c}'" for c in color_keywords])
            
            query = f"SELECT name, category, rarity, main_color, description FROM items WHERE ({like_conditions})"
            if db_category:
                query += f" AND category = '{db_category}'"
            query += " LIMIT 15"
            
            cursor.execute(query)
            items = [dict(zip(['name', 'category', 'rarity', 'main_color', 'description'], row)) for row in cursor.fetchall()]
            logger.info(f"🎨 实际颜色筛选: keyword='{keyword}', 找到 {len(items)} 个结果")
            
        elif filter_type == 'rarity_color':
            # 稀有度颜色筛选：优先查询 rarity 字段，回退到 main_color
            color_map = {
                '蓝': ['蓝'],
                '紫': ['紫'],
                '橙': ['橙'],
            }
            
            color_keywords = color_map.get(keyword, [keyword])
            
            # 先查询 rarity 字段
            like_conditions_rarity = ' OR '.join([f"rarity LIKE '%{c}%'" for c in color_keywords])
            query = f"SELECT name, category, rarity, main_color, description FROM items WHERE ({like_conditions_rarity})"
            if db_category:
                query += f" AND category = '{db_category}'"
            query += " LIMIT 15"
            
            cursor.execute(query)
            items = [dict(zip(['name', 'category', 'rarity', 'main_color', 'description'], row)) for row in cursor.fetchall()]
            
            # 如果 rarity 没有结果，回退到 main_color
            if not items:
                logger.info(f"🔄 rarity未找到结果，回退到main_color字段")
                like_conditions_main = ' OR '.join([f"main_color = '{c}'" for c in color_keywords])
                query = f"SELECT name, category, rarity, main_color, description FROM items WHERE ({like_conditions_main})"
                if db_category:
                    query += f" AND category = '{db_category}'"
                query += " LIMIT 15"
                
                cursor.execute(query)
                items = [dict(zip(['name', 'category', 'rarity', 'main_color', 'description'], row)) for row in cursor.fetchall()]
            
            logger.info(f"⭐ 稀有度颜色筛选: keyword='{keyword}', 找到 {len(items)} 个结果")
            
        elif filter_type == 'color':
            # 颜色筛选：同时从 main_color 和 rarity 字段匹配
            # main_color: 大模型识别的实际颜色
            # rarity: 稀有度颜色（蓝/紫/橙等）
            color_map = {
                '蓝': ['蓝'],
                '红': ['红'],
                '绿': ['绿'],
                '黄': ['黄'],
                '紫': ['紫'],
                '白': ['白'],
                '黑': ['黑'],
                '粉': ['粉'],
                '橙': ['橙'],
            }
            
            color_keywords = color_map.get(keyword, [keyword])
            
            # 同时查询 main_color 和 rarity 字段
            like_conditions_main = ' OR '.join([f"main_color = '{c}'" for c in color_keywords])
            like_conditions_rarity = ' OR '.join([f"rarity LIKE '%{c}%'" for c in color_keywords])
            
            query = f"SELECT name, category, rarity, main_color, description FROM items WHERE ({like_conditions_main}) OR ({like_conditions_rarity})"
            if db_category:
                query += f" AND category = '{db_category}'"
            query += " LIMIT 15"
            
            cursor.execute(query)
            items = [dict(zip(['name', 'category', 'rarity', 'main_color', 'description'], row)) for row in cursor.fetchall()]
            logger.info(f"🎨 颜色筛选: keyword='{keyword}', 找到 {len(items)} 个结果")
            
        elif filter_type == 'rarity':
            # 稀有度筛选
            rarity_map = {
                '稀有': '稀有',
                '史诗': '史诗',
                '传说': '传说',
                '绝版': '绝版',
                '限定': '限定',
            }
            
            rarity_value = rarity_map.get(keyword, keyword)
            
            query = "SELECT name, category, rarity, description FROM items WHERE (rarity LIKE ? OR description LIKE ?)"
            if db_category:
                query += f" AND category = '{db_category}'"
            query += " LIMIT 15"
            
            cursor.execute(query, (f'%{rarity_value}%', f'%{rarity_value}%'))
            items = [dict(zip(['name', 'category', 'rarity', 'description'], row)) for row in cursor.fetchall()]
            
        else:  # source
            # 来源筛选（如“家园”）
            source_map = {
                '家园': ['家园', '家具店'],
                '活动': ['活动', '限时'],
                '限时': ['限时', '活动'],
            }
            
            source_keywords = source_map.get(keyword, [keyword])
            like_conditions = ' OR '.join([f"source LIKE '%{s}%' OR description LIKE '%{s}%'" for s in source_keywords])
            
            query = f"SELECT name, category, rarity, description FROM items WHERE ({like_conditions})"
            if db_category:
                query += f" AND category = '{db_category}'"
            query += " LIMIT 15"
            
            cursor.execute(query)
            items = [dict(zip(['name', 'category', 'rarity', 'description'], row)) for row in cursor.fetchall()]
        
        if not items:
            filter_desc = {
                'actual_color': '颜色',
                'rarity_color': '稀有度',
                'color': '颜色',
                'rarity': '稀有度',
                'source': '来源'
            }.get(filter_type, '')
            return f"❌ 未找到{keyword}{filter_desc}的{db_category or '道具'}"
        
        # 格式化输出
        type_names = {
            'actual_color': '颜色',
            'rarity_color': '稀有度',
            'color': '颜色',
            'rarity': '稀有度',
            'source': '来源',
        }
        type_name = type_names.get(filter_type, '')
        
        response = f"🎨 **{keyword}{type_name}的{db_category or '道具'}** (共{len(items)}个):\n"
        response += "━━━━━━━━━━━━━━\n\n"
        
        # 使用分页配置
        page_size = self.page_size
        display_items = items[:page_size]
        
        for i, item in enumerate(display_items, 1):
            response += f"{i}. **{item['name']}**"
            # 根据筛选类型显示对应字段
            if filter_type == 'actual_color':
                # 实际颜色筛选：显示 main_color
                if item.get('main_color'):
                    response += f" [{item['main_color']}]"
            elif filter_type == 'rarity_color':
                # 稀有度颜色筛选：优先显示 rarity
                if item.get('rarity'):
                    response += f" [{item['rarity']}]"
                elif item.get('main_color'):
                    response += f" [颜色:{item['main_color']}]"
            else:
                # 其他类型：优先显示 main_color，没有则显示 rarity
                if item.get('main_color'):
                    response += f" [{item['main_color']}]"
                elif item.get('rarity'):
                    response += f" [{item['rarity']}]"
            response += "\n"
        
        if len(items) > page_size:
            response += f"\n...还有 {len(items) - page_size} 个"
        
        response += f"\n💡 提示：输入完整名称可查看详细信息"
        return response
    
    def _parse_type_query(self, query: str) -> Optional[Dict[str, Any]]:
        """
        解析智能查询（包括属性克制、拼音、编号等）
            
        Args:
            query: 用户输入
                
        Returns:
            查询类型和参数的字典，如果不是特殊查询返回 None
        """
        import re
        
        # 0. 宠物编号查询："82"、"#82"、"No.82"、"第82号"
        id_patterns = [
            r'^#?(\d+)$',  # "82"、"#82"
            r'(?:no|NO|No)\.?\s*(\d+)',  # "No.82"、"no82"
            r'第(\d+)号',  # "第82号"
            r'(\d+)号宠物',  # "82号宠物"
        ]
        
        for pattern in id_patterns:
            match = re.search(pattern, query)
            if match:
                return {
                    'type': 'pet_id',
                    'pet_id': int(match.group(1))
                }
            
        # 1. 属性克制查询：“火克草”、“水系被电系克”、“水vs电”
        type_patterns = [
            (r'(\w+)[系]?克(\w+)[系]?', 'type_advantage', False),
            (r'(\w+)[系]?被(\w+)[系]?克', 'type_advantage_reverse', False),
            (r'(\w+)[系]?vs(\w+)[系]?', 'type_advantage', False),
            (r'(\w+)[系]?对(\w+)[系]?', 'type_advantage', False),
            (r'(\w+)[系]?打(\w+)[系]?', 'type_advantage', False),  # "火打水"
            (r'(\w+)[系]?抗(\w+)[系]?', 'type_resistance', False),  # "火抗草"
        ]
            
        for pattern, qtype, is_reverse in type_patterns:
            match = re.search(pattern, query)
            if match:
                attack_type = match.group(1).replace('系', '')
                defense_type = match.group(2).replace('系', '')
                
                if is_reverse or '被' in pattern:
                    return {
                        'type': 'type_advantage',
                        'attack_type': defense_type,
                        'defense_type': attack_type
                    }
                elif qtype == 'type_resistance':
                    # “火抗草” = 火抵抗草 = 草打火效果不好
                    return {
                        'type': 'type_advantage',
                        'attack_type': defense_type,
                        'defense_type': attack_type
                    }
                else:
                    return {
                        'type': 'type_advantage',
                        'attack_type': attack_type,
                        'defense_type': defense_type
                    }
            
        # 2. 单属性完整克制关系：“火系”、“火的克制”、“火属性”
        single_type_patterns = [
            r'^(\w+)[系](?:的克制|克制关系)?$',  # "火系"、"火系的克制"
            r'^(\w+)(?:的克制|克制关系)$',  # "火的克制"
            r'^(\w+)[系]?属性$',  # "火属性"
            r'^(\w+)[系]?(?:被什么克|克什么|克制谁)$',  # "火被什么克"、"火克什么"
            r'^(\w+)[系]?(?:弱点|优势|劣势)$',  # "火弱点"、"火优势"
        ]
            
        for pattern in single_type_patterns:
            match = re.search(pattern, query)
            if match:
                element = match.group(1).replace('系', '')  # 去掉“系”字
                # 验证是否是有效的属性名（避免误匹配）
                valid_elements = ['火', '水', '草', '电', '冰', '龙', '光', '暗', '普通', '机械', '武', '毒', '翼', '萌', '虫', '幽', '幻', '地', '恶']
                if element in valid_elements or len(element) <= 2:  # 允许常见属性或短词
                    return {
                        'type': 'type_summary',
                        'element': element
                    }
        
        # 2.5 单属性宠物查询：“火系宠物”、“火系精灵”、“水系宝可梦”
        pet_element_patterns = [
            r'^(\w+)[系](?:宠物|精灵|怪兽|魔灵|伙伴)$',  # "火系宠物"、"火系精灵"
            r'^(\w+)[系]$',  # "火系" (单独的属性也可能是在查宠物)
        ]
        
        for pattern in pet_element_patterns:
            match = re.search(pattern, query)
            if match:
                element = match.group(1).replace('系', '')
                valid_elements = ['火', '水', '草', '电', '冰', '龙', '光', '暗', '普通', '机械', '武', '毒', '翼', '萌', '虫', '幽', '幻', '地', '恶']
                if element in valid_elements:
                    return {
                        'type': 'pet_by_element',
                        'element': element
                    }
            
        # 3. 技能威力排行：“最强草系技能”、“威力最大的火系技能”
        # 优先匹配带属性的模式
        top_skill_patterns = [
            r'(\w+)[系]?(?:最强|威力最大|最高)技能',  # "草系最强技能"
            r'(?:最强|威力最大|最高)(\w+)[系]?技能',  # "最强草系技能"
            r'(\w+)[系]?.*?(?:最强|威力最大|最高).*?技能',  # "火系最强的技能"
            r'(\w+)[系]?(?:最好用|最实用|推荐)技能',  # "草系最好用技能"
        ]
        
        for pattern in top_skill_patterns:
            match = re.search(pattern, query)
            if match:
                element = match.group(1).replace('系', '')  # 去掉“系”字
                # 过滤掉无意义的单字（如"的"、"是"等）
                if element and len(element) >= 1 and element not in ['的', '是', '有', '什么']:
                    return {
                        'type': 'top_skills',
                        'element': element
                    }
            
        # 无属性限定的技能排行
        if re.search(r'(?:最强|威力最大|最高|最好用|最实用)技能', query):
            return {
                'type': 'top_skills',
                'element': None
            }
        
        # 3.5 特定技能查询：“迪莫的技能”、“喵喵有什么招式”
        pet_skill_query = re.search(r'(\S+?)(?:的技能|有什么技能|有哪些技能|的招式)', query)
        if pet_skill_query:
            return {
                'type': 'pet_skills_query',
                'pet_name': pet_skill_query.group(1).strip()
            }
                
        # 3.6 宠物特性查询：“迪莫的特性”、“幻灵菇是什么特性”
        pet_ability_query = re.search(r'(\S+?)(?:的特性|是什么特性|有什么特性)', query)
        if pet_ability_query:
            return {
                'type': 'pet_ability_query',
                'pet_name': pet_ability_query.group(1).strip()
            }
                
        # 3.7 宠物分布/位置查询：“在哪里抓迪莫”、“幻灵菇在哪出现”、“幻灵菇分布”
        pet_location_query = re.search(r'(?:在哪里|在哪|哪里|什么地方|什么位置|分布|出没)(?:抓|捕捉|遇到|找|有)?(\S+?)|(\S+?)(?:在哪里|在哪|哪里|出没|分布)', query)
        if pet_location_query:
            pet_name = pet_location_query.group(1) or pet_location_query.group(2)
            if pet_name:
                return {
                    'type': 'pet_location_query',
                    'pet_name': pet_name.strip()
                }
                
        # 3.8 宠物进化查询：“迪莫怎么进化”、“小灵菇进化条件”、“幻灵菇进化成什么”
        pet_evolution_query = re.search(r'(\S+?)(?:怎么进化|如何进化|进化条件|进化成什么|进化形态)', query)
        if pet_evolution_query:
            return {
                'type': 'pet_evolution_query',
                'pet_name': pet_evolution_query.group(1).strip()
            }
                
        # 3.9 宠物六维/种族值查询：“迪莫的种族值”、“幻灵菇的六维”、“迪莫各项属性”
        pet_stats_query = re.search(r'(\S+?)(?:的种族值|的六维|各项属性|详细属性|面板数据)', query)
        if pet_stats_query:
            return {
                'type': 'pet_stats_query',
                'pet_name': pet_stats_query.group(1).strip()
            }
            
        # 4. 属性组合查询：“草毒系宠物”、“草+毒”、“草和毒系宠物”
        combo_patterns = [
            r'(\w+)[+和与](\w+)[系]?宠物',  # "草+毒宠物"、"草和毒宠物"
            r'(\w+)[+和与](\w+)系',  # "草+毒系"
            r'(\w+)(\w+)双系',  # "草毒双系"
            r'(\w+)(\w+)系宠物',  # "草毒系宠物" (连续两个属性)
        ]
        
        for pattern in combo_patterns:
            match = re.search(pattern, query)
            if match:
                elem1, elem2 = match.group(1), match.group(2)
                # 去掉“系”字后缀
                elem1 = elem1.replace('系', '')
                elem2 = elem2.replace('系', '')
                # 验证是否是有效的属性组合
                valid_elements = ['火', '水', '草', '电', '冰', '龙', '光', '暗', '普通', '机械', '武', '毒', '翼', '萌', '虫', '幽', '幻', '地', '恶']
                if elem1 in valid_elements and elem2 in valid_elements:
                    return {
                        'type': 'pet_elements',
                        'elements': [elem1, elem2]
                    }
            
        # 5. 属性筛选：“HP大于100的宠物”、“攻击力大于80”
        stat_patterns = [
            (r'HP(?:大于|>|超过|高于)\s*(\d+)', 'hp'),
            (r'(?:攻击|物攻|攻击力)(?:大于|>|超过|高于)\s*(\d+)', 'physical_attack'),
            (r'(?:魔攻|特攻|魔法攻击)(?:大于|>|超过|高于)\s*(\d+)', 'magic_attack'),
            (r'(?:防御|物防|物理防御)(?:大于|>|超过|高于)\s*(\d+)', 'physical_defense'),
            (r'(?:魔防|特防|魔法防御)(?:大于|>|超过|高于)\s*(\d+)', 'magic_defense'),
            (r'(?:速度|速)(?:大于|>|超过|高于)\s*(\d+)', 'speed'),
            # 小于筛选
            (r'HP(?:小于|<|低于)\s*(\d+)', 'hp_lt'),
            (r'(?:攻击|物攻|攻击力)(?:小于|<|低于)\s*(\d+)', 'physical_attack_lt'),
            (r'(?:魔攻|特攻|魔法攻击)(?:小于|<|低于)\s*(\d+)', 'magic_attack_lt'),
            (r'(?:防御|物防|物理防御)(?:小于|<|低于)\s*(\d+)', 'physical_defense_lt'),
            (r'(?:魔防|特防|魔法防御)(?:小于|<|低于)\s*(\d+)', 'magic_defense_lt'),
            (r'(?:速度|速)(?:小于|<|低于)\s*(\d+)', 'speed_lt'),
        ]
            
        for pattern, stat_key in stat_patterns:
            match = re.search(pattern, query)
            if match:
                is_less_than = stat_key.endswith('_lt')
                stat_name = stat_key.replace('_lt', '')
                return {
                    'type': 'pet_stat',
                    'stat_name': stat_name,
                    'min_value': int(match.group(1)),
                    'is_less_than': is_less_than
                }
        
        # 6. 更新日志查询：“最近的平衡调整”、“最近有什么更新”、“迪莫被削弱了吗”
        update_log_patterns = [
            r'(?:最近|最新).*(?:平衡|调整|更新|改动)',
            r'(?:平衡|调整|更新|改动).*(?:最近|最新|有哪些|是什么)',
            r'.*(?:被削|被强|削弱|加强|增强|nerf|buff).*',
        ]
        
        for pattern in update_log_patterns:
            if re.search(pattern, query):
                # 提取可能提到的宠物/技能名称
                mentioned_name = None
                name_match = re.search(r'(.+?)(?:被削|被强|削弱|加强|增强|nerf|buff)', query)
                if name_match:
                    mentioned_name = name_match.group(1).strip()
                
                return {
                    'type': 'update_log_query',
                    'mentioned_name': mentioned_name
                }
            
        return None
    
    def _handle_type_query(self, type_match: Dict[str, Any]) -> str:
        """
        处理智能查询
        
        Args:
            type_match: 解析后的查询信息
            
        Returns:
            格式化后的回复
        """
        query_type = type_match.get('type')
        
        # 0. 宠物编号查询
        if query_type == 'pet_id':
            pet_id = type_match['pet_id']
            pets = self.db_service.get_pet_info(str(pet_id), fuzzy=False, limit=1)
            
            if pets:
                return self._format_pet_response(pets[0])
            else:
                return f"❌ 未找到编号为 {pet_id} 的宠物"
        
        # 3.5 特定宠物技能查询
        elif query_type == 'pet_skills_query':
            pet_name = type_match['pet_name']
            pets = self.db_service.get_pet_info(pet_name, fuzzy=True, limit=1)
            
            if pets:
                pet = pets[0]
                name = pet.get('name', '未知')
                pet_skills = pet.get('skills', '')
                bloodline_skills = pet.get('bloodline_skills', '')
                learnable_skill_stones = pet.get('learnable_skill_stones', '')
                
                response = f"🎯 **{name}** 的技能:\n\n"
                
                # 普通技能
                if pet_skills:
                    skills_list = self._parse_list_field(pet_skills)
                    if skills_list:
                        response += f"📚 **技能列表** ({len(skills_list)}个):\n"
                        for i in range(0, len(skills_list), 3):
                            chunk = skills_list[i:i+3]
                            response += "  • " + " | ".join(chunk) + "\n"
                else:
                    response += "⚠️ 暂无普通技能信息\n"
                
                # 血脉技能
                if bloodline_skills:
                    bloodline_list = self._parse_list_field(bloodline_skills)
                    if bloodline_list and len(bloodline_list) > 0:
                        response += f"\n🧬 **血脉技能** ({len(bloodline_list)}个):\n"
                        for i in range(0, len(bloodline_list), 3):
                            chunk = bloodline_list[i:i+3]
                            response += "  • " + " | ".join(chunk) + "\n"
                
                # 可学技能石
                if learnable_skill_stones:
                    stone_list = self._parse_list_field(learnable_skill_stones)
                    if stone_list and len(stone_list) > 0:
                        response += f"\n💎 **可学技能石** ({len(stone_list)}个):\n"
                        for i in range(0, len(stone_list), 4):
                            chunk = stone_list[i:i+4]
                            response += "  • " + " | ".join(chunk) + "\n"
                
                return response
            else:
                return f"❌ 未找到宠物 '{pet_name}'"
        
        # 3.6 宠物特性查询
        elif query_type == 'pet_ability_query':
            pet_name = type_match['pet_name']
            pets = self.db_service.get_pet_info(pet_name, fuzzy=True, limit=1)
            
            if pets:
                pet = pets[0]
                ability = pet.get('ability', '无')
                ability_desc = pet.get('ability_desc', '')
                
                response = f"✨ **{pet['name']}** 的特性:\n\n"
                response += f"🎯 **{ability}**\n"
                if ability_desc:
                    response += f"> {ability_desc}\n"
                else:
                    response += "> 暂无详细描述\n"
                return response
            else:
                return f"❌ 未找到宠物 '{pet_name}'"
        
        # 3.7 宠物分布/位置查询
        elif query_type == 'pet_location_query':
            pet_name = type_match['pet_name']
            pets = self.db_service.get_pet_info(pet_name, fuzzy=True, limit=1)
            
            if pets:
                pet = pets[0]
                distribution = pet.get('distribution', '')
                
                response = f"📍 **{pet['name']}** 的分布信息:\n\n"
                if distribution:
                    response += f"🌍 **出现地点:** {distribution}\n"
                else:
                    response += "⚠️ 暂无分布信息\n"
                
                # 如果有体型信息，也显示
                size = pet.get('size', '')
                weight = pet.get('weight', '')
                if size or weight:
                    response += f"\n📏 **体型信息:**\n"
                    if size:
                        response += f"  • 身高: {size}m\n"
                    if weight:
                        response += f"  • 体重: {weight}kg\n"
                
                return response
            else:
                return f"❌ 未找到宠物 '{pet_name}'"
        
        # 3.8 宠物进化查询
        elif query_type == 'pet_evolution_query':
            pet_name = type_match['pet_name']
            pets = self.db_service.get_pet_info(pet_name, fuzzy=True, limit=1)
            
            if pets:
                pet = pets[0]
                stage = pet.get('stage', '')
                initial_stage = pet.get('initial_stage_name', '')
                form = pet.get('form', '')
                evolution_condition = pet.get('evolution_condition', '')
                
                response = f"🔄 **{pet['name']}** 的进化信息:\n\n"
                
                if stage:
                    response += f"📊 **当前阶段:** {stage}\n"
                if initial_stage:
                    response += f"🌱 **初始形态:** {initial_stage}\n"
                if form and form != '原始形态':
                    response += f"🎭 **形态:** {form}\n"
                
                if evolution_condition:
                    import json
                    try:
                        conditions = json.loads(evolution_condition)
                        if conditions:
                            response += f"\n🔮 **进化条件:**\n"
                            if isinstance(conditions, list):
                                for i, cond in enumerate(conditions, 1):
                                    response += f"  {i}. {cond}\n"
                            else:
                                response += f"  {conditions}\n"
                    except:
                        response += f"\n🔮 **进化条件:** {evolution_condition}\n"
                else:
                    response += "\n⚠️ 暂无进化条件信息\n"
                
                return response
            else:
                return f"❌ 未找到宠物 '{pet_name}'"
        
        # 3.9 宠物六维/种族值查询
        elif query_type == 'pet_stats_query':
            pet_name = type_match['pet_name']
            pets = self.db_service.get_pet_info(pet_name, fuzzy=True, limit=1)
            
            if pets:
                pet = pets[0]
                hp = pet.get('hp', 0)
                pa = pet.get('physical_attack', 0)
                ma = pet.get('magic_attack', 0)
                pd = pet.get('physical_defense', 0)
                md = pet.get('magic_defense', 0)
                spd = pet.get('speed', 0)
                total = hp + pa + ma + pd + md + spd
                
                response = f"📊 **{pet['name']}** 的种族值:\n\n"
                response += f"❤️ HP: {hp}\n"
                response += f"💪 物攻: {pa}\n"
                response += f"🔮 魔攻: {ma}\n"
                response += f"🛡️ 物防: {pd}\n"
                response += f"✨ 魔防: {md}\n"
                response += f"⚡ 速度: {spd}\n"
                response += f"\n📈 **总和:** {total}\n"
                
                # 计算平均值和最高属性
                stats = {'HP': hp, '物攻': pa, '魔攻': ma, '物防': pd, '魔防': md, '速度': spd}
                max_stat = max(stats, key=stats.get)
                min_stat = min(stats, key=stats.get)
                avg_stat = total / 6
                
                response += f"\n📊 **分析:**\n"
                response += f"  • 最高: {max_stat} ({stats[max_stat]})\n"
                response += f"  • 最低: {min_stat} ({stats[min_stat]})\n"
                response += f"  • 平均: {avg_stat:.1f}\n"
                
                return response
            else:
                return f"❌ 未找到宠物 '{pet_name}'"
        
        # 1. 属性克制查询
        if query_type == 'type_advantage':
            attack = type_match['attack_type']
            defense = type_match['defense_type']
            
            multiplier = self.db_service.get_type_advantage(attack, defense)
            
            if multiplier is not None:
                if multiplier > 1:
                    return f"⚔️ **{attack}系** 克制 **{defense}系**\n伤害倍率: **{multiplier}x**"
                elif multiplier == 1:
                    return f"⚖️ **{attack}系** 对 **{defense}系** 无克制关系\n伤害倍率: **1.0x**"
                elif multiplier == 0:
                    return f"🛡️ **{defense}系** 免疫 **{attack}系**\n伤害倍率: **0x**"
                else:
                    return f"🛡️ **{defense}系** 抵抗 **{attack}系**\n伤害倍率: **{multiplier}x**"
            else:
                return f"❌ 未找到 **{attack}系** 和 **{defense}系** 的克制关系"
        
        # 2. 单属性完整克制关系
        elif query_type == 'type_summary':
            element = type_match['element']
            summary = self.db_service.get_type_chart_summary(element)
            
            response = f"📊 **{summary['element']}系** 克制关系:\n\n"
            
            if summary['strong_against']:
                response += f"✅ **克制:** {', '.join(summary['strong_against'])}\n"
            
            if summary['weak_against']:
                response += f"❌ **被克:** {', '.join(summary['weak_against'])}\n"
            
            if summary['immune_to']:
                response += f"🛡️ **免疫:** {', '.join(summary['immune_to'])}\n"
            
            if summary['no_effect']:
                response += f"⚠️ **抵抗:** {', '.join(summary['no_effect'])}\n"
            
            if not any([summary['strong_against'], summary['weak_against'], 
                       summary['immune_to'], summary['no_effect']]):
                response += "暂无克制关系数据"
            
            return response
        
        # 3. 技能威力排行
        elif query_type == 'top_skills':
            element = type_match.get('element')
            skills = self.db_service.get_top_skills_by_power(element, limit=5)
            
            if not skills:
                return f"❌ 未找到{' ' + element + '系' if element else ''}技能数据"
            
            response = f"🏆 **{'最强' + element + '系' if element else '最高威力'}技能 TOP 5:**\n\n"
            for i, skill in enumerate(skills, 1):
                medal = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣'][i-1]
                response += f"{medal} **{skill['name']}** ({skill['element']}系)\n"
                response += f"   威力: {skill['power']} | 消耗: {skill['cost']} | 类型: {skill['category']}\n"
            
            return response
        
        # 2.5 单属性宠物查询
        elif query_type == 'pet_by_element':
            element = type_match['element']
            pets = self.db_service.search_pets_by_elements([element], limit=10)
            
            if not pets:
                return f"❌ 未找到 {element} 系的宠物"
            
            response = f"🔍 **{element}系宠物** (共{len(pets)}个):\n\n"
            page_size = self.page_size
            for i, pet in enumerate(pets[:page_size], 1):
                response += f"{i}. **{pet['name']}** ({pet['element']}系) HP:{pet['hp']}\n"
            
            if len(pets) > page_size:
                response += f"\n...还有 {len(pets) - page_size} 个\n"
                response += f"💡 提示：每页显示 {page_size} 个"
            
            return response
        
        # 4. 属性组合查询
        elif query_type == 'pet_elements':
            elements = type_match['elements']
            pets = self.db_service.search_pets_by_elements(elements, limit=10)
            
            if not pets:
                return f"❌ 未找到 {'+'.join(elements)} 系的宠物"
            
            response = f"🔍 **{'/'.join(elements)}系宠物** (共{len(pets)}个):\n\n"
            page_size = self.page_size
            for i, pet in enumerate(pets[:page_size], 1):
                response += f"{i}. **{pet['name']}** ({pet['element']}系) HP:{pet['hp']}\n"
            
            if len(pets) > page_size:
                response += f"\n...还有 {len(pets) - page_size} 个\n"
                response += f"💡 提示：每页显示 {page_size} 个"
            
            return response
        
        # 5. 属性筛选
        elif query_type == 'pet_stat':
            stat_name = type_match['stat_name']
            min_value = type_match['min_value']
            is_less_than = type_match.get('is_less_than', False)
            
            stat_names_cn = {
                'hp': 'HP',
                'physical_attack': '物攻',
                'magic_attack': '魔攻',
                'physical_defense': '物防',
                'magic_defense': '魔防',
                'speed': '速度'
            }
            
            pets = self.db_service.search_pets_by_stat(stat_name, min_value, limit=10)
            
            if not pets:
                operator = '<' if is_less_than else '>='
                return f"❌ 未找到 {stat_names_cn.get(stat_name, stat_name)}{operator}{min_value} 的宠物"
            
            # 如果是小于筛选，需要过滤结果
            if is_less_than:
                pets = [p for p in pets if p.get(stat_name, 0) < min_value]
            
            if not pets:
                operator = '<' if is_less_than else '>='
                return f"❌ 未找到 {stat_names_cn.get(stat_name, stat_name)}{operator}{min_value} 的宠物"
            
            operator = '<' if is_less_than else '>='
            response = f"📊 **{stat_names_cn.get(stat_name, stat_name)}{operator}{min_value} 的宠物** (共{len(pets)}个):\n\n"
            page_size = self.page_size
            for i, pet in enumerate(pets[:page_size], 1):
                stat_value = pet.get(stat_name, 0)
                response += f"{i}. **{pet['name']}** ({pet['element']}系) {stat_names_cn.get(stat_name, stat_name)}:{stat_value}\n"
            
            if len(pets) > page_size:
                response += f"\n...还有 {len(pets) - page_size} 个\n"
                response += f"💡 提示：每页显示 {page_size} 个"
            
            return response
        
        # 6. 更新日志查询
        elif query_type == 'update_log_query':
            mentioned_name = type_match.get('mentioned_name')
            
            if mentioned_name:
                # 搜索特定宠物/技能的改动
                logs = self.db_service.search_update_logs(mentioned_name, limit=5)
                if logs:
                    response = f"📝 **关于 '{mentioned_name}' 的平衡调整:**\n\n"
                    for log in logs[:3]:
                        response += f"📅 **{log['date']} - {log['title']}**\n"
                        response += f"> {log['content'][:200]}...\n\n"
                    return response
                else:
                    return f"❌ 未找到关于 '{mentioned_name}' 的平衡调整记录"
            else:
                # 获取最近的更新日志
                logs = self.db_service.get_latest_updates(limit=5)
                if logs:
                    response = f"📋 **最近的平衡调整:**\n\n"
                    for log in logs:
                        response += f"📅 **{log['date']} - {log['title']}**\n"
                        
                        # 显示改动统计
                        pet_count = len(log.get('pet_changes', []))
                        skill_count = len(log.get('skill_changes', []))
                        other_count = len(log.get('other_changes', []))
                        
                        if pet_count > 0:
                            response += f"  🐾 宠物改动: {pet_count}条\n"
                        if skill_count > 0:
                            response += f"  ⚔️ 技能改动: {skill_count}条\n"
                        if other_count > 0:
                            response += f"  🔧 其他改动: {other_count}条\n"
                        
                        # 显示具体改动（前几个）
                        pet_changes = log.get('pet_changes', [])
                        if pet_changes:
                            names = [c.get('name', '') for c in pet_changes[:5]]
                            response += f"  👉 {'、'.join(names)}{'等' if len(pet_changes) > 5 else ''}\n"
                        
                        skill_changes = log.get('skill_changes', [])
                        if skill_changes:
                            names = [c.get('name', '') for c in skill_changes[:5]]
                            response += f"  👉 {'、'.join(names)}{'等' if len(skill_changes) > 5 else ''}\n"
                        
                        response += "\n"
                    
                    return response
                else:
                    return "❌ 暂无更新日志记录"
        
        return "❌ 无法解析查询"
    
    async def _handle_admin_command_impl(self, event: AstrMessageEvent, command: str):
        """
        处理管理员命令（通过关键词触发，由 AstrBot 权限系统控制）
        
        Args:
            event: 事件对象
            command: 命令参数（去除前缀后的部分）
        """
        # 停止事件传播，防止被 Agent/LLM 拦截
        event.stop_event()
        
        # 解析命令
        parts = command.strip().split()
        if len(parts) < 1:
            yield event.plain_result(f"❌ 请提供命令\n用法: 洛克管理 <command>\n示例: 洛克管理 update")
            return
        
        cmd = parts[0].lower()
        
        # 执行命令
        if cmd == "update":
            async for msg in self._handle_update_db(event):
                yield event.plain_result(msg)
        elif cmd == "status":
            async for msg in self._handle_db_status(event):
                yield event.plain_result(msg)
        elif cmd == "tag-colors":
            async for msg in self._handle_tag_colors(event):
                yield event.plain_result(msg)
        elif cmd == "tag-pet-colors":
            async for msg in self._handle_tag_pet_colors(event):
                yield event.plain_result(msg)
        elif cmd == "force-tag-colors":
            async for msg in self._handle_force_tag_colors(event):
                yield event.plain_result(msg)
        elif cmd == "force-tag-pet-colors":
            async for msg in self._handle_force_tag_pet_colors(event):
                yield event.plain_result(msg)
        elif cmd == "fix-missing":
            async for msg in self._handle_fix_missing_data(event):
                yield event.plain_result(msg)
        elif cmd == "check-vision":
            async for msg in self._handle_check_vision_model(event):
                yield event.plain_result(msg)
        else:
            yield event.plain_result(f"❌ 未知命令: {cmd}\n\n📋 可用命令:\n  • update - 增量更新数据库\n  • status - 查看数据库状态\n  • tag-colors - 为道具标记颜色\n  • tag-pet-colors - 为宠物标记颜色\n  • force-tag-colors - 强制重新识别所有道具颜色\n  • force-tag-pet-colors - 强制重新识别所有宠物颜色\n  • fix-missing - 补全缺失的宠物数据\n  • check-vision - 检查视觉模型配置\n\n示例: 洛克管理 check-vision")
    
    @filter.command("查询", ["query", "wiki"])
    async def handle_query(self, event: AstrMessageEvent, content: str):
        """
        处理查询命令
        用法: /查询 <宠物/技能名称>
              /查询 <宠物/技能名称> 图片 (只返回图片)
        """
        
        # 参数验证
        if not content or len(content.strip()) < 1:
            yield "❌ 请输入要查询的宠物或技能名称！\n示例: /查询 喵喵\n示例: /查询 喵喵 图片"
            return
        
        content = content.strip()
        
        # 检查数据库服务是否可用
        if not self.db_service:
            yield "❌ 数据库服务不可用，请联系管理员检查配置"
            return
        
        # 检测是否是图片检索请求
        is_image_query, clean_content = self._extract_image_query(content)
        
        if is_image_query:
            logger.info(f"🖼️ 图片检索模式: {clean_content}")
            async for msg in self._handle_image_only_query(event, clean_content):
                yield msg
            return
        
        # 先尝试查询宠物
        pets = self.db_service.get_pet_info(
            content, 
            fuzzy=self.enable_fuzzy_search, 
            limit=self.search_limit
        )
        
        if pets:
            # 找到宠物，格式化返回
            if len(pets) == 1:
                # 精确匹配，返回详细信息 + 图片
                pet = pets[0]
                response = self._format_pet_response(pet)
                
                # 尝试获取宠物图片
                image_path = pet.get('sprite_image_local')
                if image_path and os.path.exists(image_path):
                    # 有本地图片，发送文字+图片
                    response_with_source = response + DATA_SOURCE_NOTICE
                    yield event.plain_result(response_with_source)
                    yield event.image_result(image_path)
                else:
                    # 没有图片，只发送文字
                    response_with_source = response + DATA_SOURCE_NOTICE
                    yield event.plain_result(response_with_source)
            else:
                # 多个结果，返回列表
                response = f"🔍 找到 {len(pets)} 个相关宠物:\n\n"
                for i, pet in enumerate(pets[:self.search_limit], 1):
                    response += f"{i}. {pet['name']} ({pet['element']}系)\n"
                
                response += DATA_SOURCE_NOTICE
                yield event.plain_result(response)
            return
        
        # 再尝试查询技能
        skills = self.db_service.get_skill_info(
            content,
            fuzzy=self.enable_fuzzy_search,
            limit=self.search_limit
        )
        
        if skills:
            # 找到技能，格式化返回
            if len(skills) == 1:
                response = self._format_skill_response(skills[0])
            else:
                response = f"🔍 找到 {len(skills)} 个相关技能:\n\n"
                for i, skill in enumerate(skills[:self.search_limit], 1):
                    response += f"{i}. {skill['name']} ({skill['element']}系, 威力:{skill['power']})\n"
            
            response += DATA_SOURCE_NOTICE
            yield event.plain_result(response)
            return
        
        # 最后尝试搜索 Wiki 页面
        pages = self.db_service.search_wiki_page(
            content,
            fuzzy=self.enable_fuzzy_search,
            limit=self.search_limit
        )
        
        if pages:
            response = f"📄 找到 {len(pages)} 个相关页面:\n\n"
            for i, page in enumerate(pages[:self.search_limit], 1):
                response += f"{i}. **{page['title']}** ({page['page_type']})\n"
                if page['preview']:
                    response += f"   _{page['preview'][:50]}..._\n"
                response += "\n"
            
            response += DATA_SOURCE_NOTICE
            yield event.plain_result(response)
            return
        
        # 未找到任何结果
        yield f"❌ 未找到与 \"{content}\" 相关的信息\n💡 提示: 可以尝试其他关键词或检查拼写"
    
    async def _handle_image_only_query(self, event: AstrMessageEvent, query: str):
        """
        处理纯图片检索请求（只返回图片，不返回文字）
        
        Args:
            event: 事件对象
            query: 查询关键词
        """
        # 获取插件目录（用于解析相对路径）
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 先尝试查询宠物
        pets = self.db_service.get_pet_info(
            query, 
            fuzzy=self.enable_fuzzy_search, 
            limit=1
        )
        
        if pets:
            pet = pets[0]
            image_path = pet.get('sprite_image_local')
            
            # 如果是相对路径，转换为绝对路径
            if image_path and not os.path.isabs(image_path):
                image_path = os.path.join(plugin_dir, image_path)
            
            if image_path and os.path.exists(image_path):
                # 发送简单的提示和图片
                yield event.plain_result(f"🖼️ {pet['name']}")
                yield event.image_result(image_path)
            else:
                logger.warning(f"⚠️ 宠物 '{pet['name']}' 的图片不存在: {image_path}")
                yield event.plain_result(f"❌ {pet['name']} 没有可用的图片")
            return
        
        # 再尝试查询技能
        skills = self.db_service.get_skill_info(
            query,
            fuzzy=self.enable_fuzzy_search,
            limit=1
        )
        
        if skills:
            skill = skills[0]
            image_path = skill.get('icon_image_local')
            
            # 如果是相对路径，转换为绝对路径
            if image_path and not os.path.isabs(image_path):
                image_path = os.path.join(plugin_dir, image_path)
            
            if image_path and os.path.exists(image_path):
                yield event.plain_result(f"🖼️ {skill['name']}")
                yield event.image_result(image_path)
            else:
                logger.warning(f"⚠️ 技能 '{skill['name']}' 的图片不存在: {image_path}")
                yield event.plain_result(f"❌ {skill['name']} 没有可用的图片")
            return
        
        # 最后尝试搜索道具
        items = self.db_service.search_item(
            query,
            fuzzy=self.enable_fuzzy_search,
            limit=1
        )
        
        if items:
            item = items[0]
            image_path = item.get('image_local')
            
            # 如果是相对路径，转换为绝对路径
            if image_path and not os.path.isabs(image_path):
                image_path = os.path.join(plugin_dir, image_path)
            
            if image_path and os.path.exists(image_path):
                yield event.plain_result(f"🖼️ {item['name']}")
                yield event.image_result(image_path)
            else:
                logger.warning(f"⚠️ 道具 '{item['name']}' 的图片不存在: {image_path}")
                yield event.plain_result(f"❌ {item['name']} 没有可用的图片")
            return
        
        # 未找到
        yield event.plain_result(f"❌ 未找到与 \"{query}\" 相关的图片\n💡 提示: 请检查名称是否正确")

    @filter.llm_tool(name="roco_wiki_lookup", description="查询洛克王国宠物或技能信息")
    async def wiki_lookup(self, event: AstrMessageEvent, pet_name: str = "") -> str:
        """
        洛克 Wiki 工具 - LLM 可调用
        
        Args:
            pet_name (str): 宠物或技能名称
        """
        
        logger.info(f"🔍 LLM 调用查询: {pet_name}")
        
        # 检查数据库服务
        if not self.db_service:
            return "❌ 数据库服务不可用"
        
        # 查询宠物
        pets = self.db_service.get_pet_info(
            pet_name,
            fuzzy=self.enable_fuzzy_search,
            limit=1
        )
        
        if pets:
            return self._format_pet_response(pets[0])
        
        # 查询技能
        skills = self.db_service.get_skill_info(
            pet_name,
            fuzzy=self.enable_fuzzy_search,
            limit=1
        )
        
        if skills:
            return self._format_skill_response(skills[0])
        
        return f"❌ 未找到 \"{pet_name}\" 的相关信息"
    
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """
        监听所有消息，检测触发关键词
        """
        if not self.db_service:
            return
        
        # 获取插件目录（用于解析相对路径）
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        
        message_str = event.message_str.strip()
        
        # 优先检查翻页命令（避免被当作普通查询）
        if message_str in ['洛克下页', 'wiki-next', 'wiki下一页', '下页']:
            event.stop_event()
            async for msg in self._handle_page_navigation(event, 'next'):
                yield msg
            return
        elif message_str in ['洛克上页', 'wiki-prev', 'wiki上一页', '上页']:
            event.stop_event()
            async for msg in self._handle_page_navigation(event, 'prev'):
                yield msg
            return
        
        # 检查是否是管理员命令（关键词触发）
        admin_cmd_prefixes = ["洛克管理", "wiki-admin", "wiki_admin"]
        for prefix in admin_cmd_prefixes:
            if message_str.startswith(prefix):
                # 提取命令参数
                command_arg = message_str[len(prefix):].strip()
                # 停止事件传播
                event.stop_event()
                # 调用 _handle_admin_command_impl 处理（避免与 @filter.command 装饰器冲突）
                async for response in self._handle_admin_command_impl(event, command_arg):
                    yield response
                return  # 阻止后续处理
        
        # 检查是否包含触发关键词
        triggered = any(keyword in message_str for keyword in self.trigger_keywords)
        
        if not triggered:
            return
        
        # 提取查询内容（去除触发关键词）
        query_content = message_str
        for keyword in self.trigger_keywords:
            query_content = query_content.replace(keyword, '').strip()
        
        if not query_content:
            yield "❌ 请提供要查询的宠物或技能名称\n示例：洛克王国 迪莫\n示例：洛克王国 暗突袭\n示例：洛克王国 82 (编号查询)\n示例：洛克王国 火克草 (属性克制)"
            return
        
        # 检测是否是图片检索请求
        is_image_query, clean_query = self._extract_image_query(query_content)
        
        if is_image_query:
            logger.info(f"🖼️ 图片检索模式: {clean_query}")
            async for msg in self._handle_image_only_query(event, clean_query):
                yield msg
            return
        
        # 执行查询
        logger.info(f"🔍 触发关键词查询: {query_content}")
        
        # 1. 优先使用规则匹配（快速响应）
        smart_query = self._parse_type_query(query_content)
        if smart_query:
            logger.info(f"🧠 规则匹配成功: {smart_query.get('type')}")
            response = self._handle_type_query(smart_query)
            yield event.plain_result(response)
            return
        
        # 2. 基础查询：宠物和技能搜索（大多数情况在这里处理）
        # 检测用户的详细查询意图
        query_intent = self._analyze_query_intent(query_content)
        
        # 如果是详细查询意图，直接提取宠物名进行查询
        if query_intent.get('type') == 'pet_detail':
            pet_name = query_intent.get('pet_name', '')
            detail_type = query_intent.get('detail_type', '')
            logger.info(f"🎯 检测到详细查询意图: 宠物='{pet_name}', 类型='{detail_type}'")
            
            # 使用宠物名查询
            pets = self.db_service.get_pet_info(
                pet_name,
                fuzzy=self.enable_fuzzy_search,
                limit=1
            )
            
            if pets:
                pet = pets[0]
                response = self._format_pet_detail_info(pet, detail_type)
                response += DATA_SOURCE_NOTICE
                yield event.plain_result(response)
                return
            else:
                # 未找到宠物，尝试作为技能石查询（例如“乘风 技能石”）
                if detail_type == 'skill_stones':
                    logger.info(f"🔄 未找到宠物 '{pet_name}'，尝试作为技能石查询")
                    response = self._format_skill_stone_info(pet_name)
                    response += DATA_SOURCE_NOTICE
                    yield event.plain_result(response)
                    return
                else:
                    # 未找到宠物
                    yield event.plain_result(f"❌ 未找到宠物 \"{pet_name}\"")
                    return
        
        # 如果是技能石查询意图
        if query_intent.get('type') == 'skill_stone_info':
            stone_name = query_intent.get('stone_name', '')
            only_source = query_intent.get('only_source', False)
            logger.info(f"🎯 检测到技能石查询意图: '{stone_name}', only_source={only_source}")
            
            response = self._format_skill_stone_info(stone_name, only_source=only_source)
            response += DATA_SOURCE_NOTICE
            yield event.plain_result(response)
            return
        
        # 如果是属性筛选查询：“火系宠物有哪些”
        if query_intent.get('type') == 'attribute_filter':
            attribute = query_intent.get('attribute', '')
            entity_type = query_intent.get('entity_type', 'pet')
            logger.info(f"🎯 检测到属性筛选查询: {attribute}系{entity_type}")
            
            if entity_type == 'pet':
                response = self._handle_attribute_filter(attribute, 'pet')
                
                # 保存会话状态（用于翻页）
                user_id = event.get_sender_id()
                pets = self.db_service.get_pets_by_element(attribute, limit=1000)
                total_count = len(pets)
                if total_count > self.page_size:
                    self._save_query_state(user_id, 'element_pets', {'element': attribute}, total_count)
                    response += f"\n\n📄 第 1/{(total_count + self.page_size - 1) // self.page_size} 页 | 回复“洛克下页”或“洛克上页”翻⻚"
                
                response += DATA_SOURCE_NOTICE
                yield event.plain_result(response)
                return
        
        # 如果是颜色宠物/精灵蛋查询：“红色宠物”、“蓝色精灵蛋”
        if query_intent.get('type') == 'color_filter':
            color = query_intent.get('color', '')
            entity_type = query_intent.get('entity_type', 'pet')
            logger.info(f"🎯 检测到颜色{entity_type}查询: {color}色")
            
            response = self._handle_color_filter(color, entity_type)
            
            # 保存会话状态（用于翻页）
            user_id = event.get_sender_id()
            # 估算总数：从响应文本中提取
            import re
            count_match = re.search(r'共(\d+)个', response)
            total_count = int(count_match.group(1)) if count_match else 0
            
            if total_count > self.page_size:
                self._save_query_state(user_id, 'color_pets', {'color': color, 'entity_type': entity_type}, total_count)
                response += f"\n\n📄 第 1/{(total_count + self.page_size - 1) // self.page_size} 页 | 回复“洛克下页”或“洛克上页”翻⻚"
            
            response += DATA_SOURCE_NOTICE
            yield event.plain_result(response)
            return
        
        # 如果是稀有度宠物查询：“稀有宠物”、“史诗精灵”
        if query_intent.get('type') == 'rarity_filter':
            rarity = query_intent.get('rarity', '')
            entity_type = query_intent.get('entity_type', 'pet')
            logger.info(f"🎯 检测到稀有度{entity_type}查询: {rarity}")
            
            response = self._handle_rarity_filter(rarity, entity_type)
            
            # 保存会话状态（用于翻页）
            user_id = event.get_sender_id()
            cursor = self.db_service.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM pets WHERE (description LIKE ? OR ability LIKE ?)", (f'%{rarity}%', f'%{rarity}%'))
            total_count = cursor.fetchone()[0]
            if total_count > self.page_size:
                self._save_query_state(user_id, 'rarity_pets', {'rarity': rarity}, total_count)
                response += f"\n\n📄 第 1/{(total_count + self.page_size - 1) // self.page_size} 页 | 回复“洛克下页”或“洛克上页”翻⻚"
            
            response += DATA_SOURCE_NOTICE
            yield event.plain_result(response)
            return
        
        # 如果是来源宠物查询：“家园宠物”、“活动精灵”
        if query_intent.get('type') == 'source_filter':
            source = query_intent.get('source', '')
            entity_type = query_intent.get('entity_type', 'pet')
            logger.info(f"🎯 检测到来源{entity_type}查询: {source}")
            
            response = self._handle_source_filter(source, entity_type)
            
            # 保存会话状态（用于翻页）
            user_id = event.get_sender_id()
            source_map = {
                '家园': ['家园', '家具店', '商店'],
                '活动': ['活动', '限时', '节日'],
            }
            source_keywords = source_map.get(source, [source])
            like_conditions = ' OR '.join([f"description LIKE '%{s}%" for s in source_keywords])
            cursor = self.db_service.conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM pets WHERE ({like_conditions})")
            total_count = cursor.fetchone()[0]
            if total_count > self.page_size:
                self._save_query_state(user_id, 'source_pets', {'source': source}, total_count)
                response += f"\n\n📄 第 1/{(total_count + self.page_size - 1) // self.page_size} 页 | 回复“洛克下页”或“洛克上页”翻⻚"
            
            response += DATA_SOURCE_NOTICE
            yield event.plain_result(response)
            return
        
        # 如果是阶段宠物查询：“初始形态宠物”、“最终形态精灵”
        if query_intent.get('type') == 'stage_filter':
            stage = query_intent.get('stage', '')
            entity_type = query_intent.get('entity_type', 'pet')
            logger.info(f"🎯 检测到阶段{entity_type}查询: {stage}")
            
            response = self._handle_stage_filter(stage, entity_type)
            
            # 保存会话状态（用于翻页）
            user_id = event.get_sender_id()
            stage_map = {
                '初始': ['初始形态', '初级'],
                '最终': ['最终形态', '究极体'],
            }
            stage_keywords = stage_map.get(stage, [stage])
            like_conditions = ' OR '.join([f"stage LIKE '%{s}%" for s in stage_keywords])
            cursor = self.db_service.conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM pets WHERE ({like_conditions})")
            total_count = cursor.fetchone()[0]
            if total_count > self.page_size:
                self._save_query_state(user_id, 'stage_pets', {'stage': stage}, total_count)
                response += f"\n\n📄 第 1/{(total_count + self.page_size - 1) // self.page_size} 页 | 回复“洛克下页”或“洛克上页”翻⻚"
            
            response += DATA_SOURCE_NOTICE
            yield event.plain_result(response)
            return
        
        # 如果是分类/颜色/稀有度筛选：“蓝色家具”、“紫色道具”
        if query_intent.get('type') == 'category_filter':
            keyword = query_intent.get('keyword', '')
            category = query_intent.get('category', '')
            filter_type = query_intent.get('filter_type', '')
            logger.info(f"🎯 检测到分类筛选: {keyword}{category}, 类型={filter_type}")
            
            response = self._handle_category_filter(keyword, category, filter_type)
            
            # 保存会话状态（用于翻页）
            user_id = event.get_sender_id()
            db_category_map = {
                'furniture': '家具',
                'item': '',
                'skill_stone': '技能石',
                'gumball': '咕噜球',
                'fruit': '精灵果实',
            }
            db_category = db_category_map.get(category, '')
            
            # 估算总数（简化处理，实际应该根据filter_type构建不同的COUNT查询）
            cursor = self.db_service.conn.cursor()
            if db_category:
                cursor.execute(f"SELECT COUNT(*) FROM items WHERE category = '{db_category}'")
            else:
                cursor.execute("SELECT COUNT(*) FROM items")
            total_count = cursor.fetchone()[0]
            
            if total_count > self.page_size:
                self._save_query_state(user_id, 'category_items', {
                    'keyword': keyword,
                    'category': category,
                    'filter_type': filter_type
                }, total_count)
                response += f"\n\n📄 第 1/{(total_count + self.page_size - 1) // self.page_size} 页 | 回复“洛克下页”或“洛克上页”翻⻚"
            
            response += DATA_SOURCE_NOTICE
            yield event.plain_result(response)
            return
                
        # 普通查询：清理查询词
        clean_query = query_content
        for suffix in ['技能', 'skill', 'skills', '招式', 'move', '血脉', 'bloodline', '技能石', 'stone', 'stones', '课题', 'quest']:
            clean_query = clean_query.replace(suffix, '').strip()
                
        # 额外清理常见语气词、助词和无意义后缀（但不要移除"图片"等关键词）
        for word in ['有什么', '有哪些', '是什么', '是多少', '的资料', '的介绍', '的信息', '的详情', '长什么样', '的样子', '的图片', '的照片', '的立绘', '的头像', '的图标', '的', '吗', '呢', '吧', '精灵', '宠物', '怪兽', '魔灵', '伙伴']:
            clean_query = clean_query.replace(word, '').strip()
                
        logger.info(f"🔧 清理后查询词: '{clean_query}' (原始: '{query_content}')")
        
        # 先尝试查询宠物（使用清理后的查询词）
        pets = self.db_service.get_pet_info(
            clean_query if clean_query else query_content,
            fuzzy=self.enable_fuzzy_search,
            limit=self.search_limit
        )
        
        if pets:
            # 检查是否有更多相似的宠物（用于判断是否显示变体列表）
            all_similar_pets = self.db_service.get_pet_info(
                clean_query if clean_query else query_content,
                fuzzy=True,
                limit=50  # 获取更多结果用于判断
            )
            has_variants = len(all_similar_pets) > 1
            
            # 显示第一个匹配项的详细信息
            pet = pets[0]
            response = self._format_pet_response(pet)
            
            # 如果有多个变体，附加变体列表
            if has_variants and len(all_similar_pets) > 1:
                response += f"\n\n🐾 **相关形态/变体** ({len(all_similar_pets)}个):\n"
                page_size = self.page_size
                for i, variant in enumerate(all_similar_pets[:page_size], 1):
                    variant_element = variant.get('element', '未知')
                    variant_stage = variant.get('stage', '')
                    variant_form = variant.get('form', '')
                    
                    extra = ""
                    if variant_stage:
                        extra += f" [{variant_stage}]"
                    if variant_form and variant_form != '原始形态':
                        extra += f" {variant_form}"
                    
                    # 标记当前显示的宠物
                    if variant['name'] == pet['name']:
                        response += f"  {i}. **{variant['name']}** ({variant_element}系){extra} ← 当前\n"
                    else:
                        response += f"  {i}. {variant['name']} ({variant_element}系){extra}\n"
                
                if len(all_similar_pets) > page_size:
                    response += f"  ... 还有 {len(all_similar_pets) - page_size} 个形态\n"
                    response += f"💡 提示：每页显示 {page_size} 个\n"
                
                response += f"\n💡 提示：输入完整名称（包含形态）可查看其他形态的详细信息"
            
            # 添加数据来源声明
            response += DATA_SOURCE_NOTICE
            
            # 检查是否有图片
            image_path = pet.get('sprite_image_local')
            logger.info(f"🖼️ 宠物 '{pet['name']}' 的图片路径: {image_path}")
            if image_path:
                # 清理路径前缀（移除 ./ 或 .\）
                if image_path.startswith('./') or image_path.startswith('.\\'):
                    image_path = image_path[2:]
                # 如果是相对路径，基于插件目录解析
                if not os.path.isabs(image_path):
                    image_path = os.path.join(plugin_dir, image_path)
                # 规范化路径分隔符（跨平台兼容）
                image_path = image_path.replace('\\', '/')
                logger.info(f"🖼️ 解析后的完整路径: {image_path}")
                logger.info(f"🖼️ 文件是否存在: {os.path.exists(image_path)}")
            
            # 如果有图片，使用 MessageChain 组合文本和图片
            if image_path and os.path.exists(image_path):
                try:
                    import astrbot.api.message_components as Comp
                    chain = [
                        Comp.Plain(response),
                        Comp.Image.fromFileSystem(image_path)
                    ]
                    logger.info(f"🖼️ 准备发送宠物图文消息: {image_path}")
                    yield event.chain_result(chain)
                    logger.info(f"✅ 已发送宠物图文消息")
                except Exception as e:
                    logger.warning(f"⚠️ 发送宠物图文消息失败: {e}", exc_info=True)
                    # 降级：分别发送
                    yield event.plain_result(response)
                    yield event.image_result(image_path)
            else:
                # 没有图片，只发送文本
                yield event.plain_result(response)
            return
        
        # 再尝试查询技能（使用原始查询词）
        skills = self.db_service.get_skill_info(
            query_content,
            fuzzy=self.enable_fuzzy_search,
            limit=self.search_limit
        )
        
        if skills:
            if len(skills) == 1:
                skill = skills[0]
                response = self._format_skill_response(skill)
                
                # 检查是否有图片
                image_path = skill.get('icon_image_local')
                logger.info(f"🖼️ 技能 '{skill['name']}' 的图片路径: {image_path}")
                if image_path:
                    # 清理路径前缀（移除 ./ 或 .\）
                    if image_path.startswith('./') or image_path.startswith('.\\'):
                        image_path = image_path[2:]
                    # 如果是相对路径，基于插件目录解析
                    if not os.path.isabs(image_path):
                        image_path = os.path.join(plugin_dir, image_path)
                    # 规范化路径分隔符（跨平台兼容）
                    image_path = image_path.replace('\\', '/')
                    logger.info(f"🖼️ 解析后的完整路径: {image_path}")
                    logger.info(f"🖼️ 文件是否存在: {os.path.exists(image_path)}")
                
                # 如果有图片，使用 MessageChain 组合文本和图片
                if image_path and os.path.exists(image_path):
                    try:
                        import astrbot.api.message_components as Comp
                        chain = [
                            Comp.Plain(response),
                            Comp.Image.fromFileSystem(image_path)
                        ]
                        logger.info(f"🖼️ 准备发送技能图文消息: {image_path}")
                        yield event.chain_result(chain)
                        logger.info(f"✅ 已发送技能图文消息")
                    except Exception as e:
                        logger.warning(f"⚠️ 发送技能图文消息失败: {e}", exc_info=True)
                        # 降级：分别发送
                        yield event.plain_result(response)
                        yield event.image_result(image_path)
                else:
                    # 没有图片，只发送文本
                    yield event.plain_result(response)
            else:
                response = f"🔍 找到 {len(skills)} 个相关技能:\n\n"
                for i, skill in enumerate(skills[:self.search_limit], 1):
                    response += f"{i}. {skill['name']} ({skill['element']}系)\n"
                
                response += DATA_SOURCE_NOTICE
                yield event.plain_result(response)
            return
        
        # 尝试查询道具
        items = self.db_service.get_item_info(
            query_content,
            fuzzy=self.enable_fuzzy_search,
            limit=self.search_limit
        )
        
        if items:
            # 检查是否有更多相似的道具（用于判断是否显示变体列表）
            all_similar_items = self.db_service.get_item_info(
                query_content,
                fuzzy=True,
                limit=50  # 获取更多结果用于判断
            )
            has_variants = len(all_similar_items) > 1
            
            # 显示第一个匹配项的详细信息
            item = items[0]
            response = f"🎒 **{item['name']}**\n"
            response += "━━━━━━━━━━━━━━\n"
            
            if item.get('category'):
                response += f"📦 分类: {item['category']}\n"
                if item.get('subcategory'):
                    response += f"🔹 子类: {item['subcategory']}\n"
            if item.get('rarity'):
                response += f"⭐ 稀有度: {item['rarity']}\n"
            if item.get('version'):
                response += f"🎮 版本: {item['version']}\n"
            
            if item.get('source'):
                response += f"\n🛒 获取方式:\n{item['source']}\n"
            
            if item.get('description'):
                response += f"\n📝 **描述:**\n{item['description']}\n"
            
            # 如果有多个变体，附加变体列表
            if has_variants and len(all_similar_items) > 1:
                response += f"\n📚 **相关变体** ({len(all_similar_items)}个):\n"
                page_size = self.page_size
                for i, variant in enumerate(all_similar_items[:page_size], 1):
                    variant_category = variant.get('category', '')
                    variant_rarity = variant.get('rarity', '')
                    extra = ""
                    if variant_category:
                        extra += f" [{variant_category}]"
                    if variant_rarity:
                        extra += f" ⭐{variant_rarity}"
                    # 标记当前显示的物品
                    if variant['name'] == item['name']:
                        response += f"  {i}. **{variant['name']}**{extra} ← 当前\n"
                    else:
                        response += f"  {i}. {variant['name']}{extra}\n"
                
                if len(all_similar_items) > page_size:
                    response += f"  ... 还有 {len(all_similar_items) - page_size} 个变体\n"
                    response += f"💡 提示：每页显示 {page_size} 个\n"
                
                response += f"\n💡 提示：输入完整名称可查看其他变体的详细信息"
            
            # 添加数据来源声明
            response += DATA_SOURCE_NOTICE
            
            # 检查是否有图片
            image_path = item.get('image_local')
            logger.info(f"🖼️ 道具 '{item['name']}' 的图片路径: {image_path}")
            if image_path:
                # 清理路径前缀（移除 ./ 或 .\）
                if image_path.startswith('./') or image_path.startswith('.\\'):
                    image_path = image_path[2:]
                # 如果是相对路径，基于插件目录解析
                if not os.path.isabs(image_path):
                    image_path = os.path.join(plugin_dir, image_path)
                # 规范化路径分隔符
                image_path = image_path.replace('\\', '/')
                logger.info(f"🖼️ 解析后的完整路径: {image_path}")
                logger.info(f"🖼️ 文件是否存在: {os.path.exists(image_path)}")
            
            # 如果有图片，发送图文消息
            if image_path and os.path.exists(image_path):
                try:
                    import astrbot.api.message_components as Comp
                    chain = [
                        Comp.Plain(response),
                        Comp.Image.fromFileSystem(image_path)
                    ]
                    logger.info(f"🖼️ 准备发送道具图文消息: {image_path}")
                    yield event.chain_result(chain)
                    logger.info(f"✅ 已发送道具图文消息")
                except Exception as e:
                    logger.warning(f"⚠️ 发送道具图文消息失败: {e}", exc_info=True)
                    # 降级：分别发送
                    yield event.plain_result(response)
                    yield event.image_result(image_path)
            else:
                # 没有图片，只发送文本
                yield event.plain_result(response)
            return
        
        yield event.plain_result(f"❌ 未找到与 \"{query_content}\" 相关的信息\n💡 提示：可以尝试只输入宠物名、技能名、编号或属性克制关系\n{DATA_SOURCE_NOTICE}")
    
    def _cleanup_expired_sessions(self):
        """
        清理超时的会话状态
        """
        import time
        current_time = time.time()
        expired_users = [
            user_id for user_id, state in self.session_states.items()
            if current_time - state['timestamp'] > self.session_timeout
        ]
        for user_id in expired_users:
            del self.session_states[user_id]
        if expired_users:
            logger.debug(f"🧹 清理了 {len(expired_users)} 个超时会话")
    
    def _save_query_state(self, user_id: str, query_type: str, params: dict, total: int):
        """
        保存查询状态到会话
        
        Args:
            user_id: 用户ID
            query_type: 查询类型
            params: 查询参数
            total: 总结果数
        """
        import time
        self.session_states[user_id] = {
            'query_type': query_type,
            'params': params,
            'page': 1,
            'total': total,
            'timestamp': time.time()
        }
        logger.debug(f"💾 保存会话状态: user={user_id}, type={query_type}, total={total}")
    
    def _get_query_state(self, user_id: str) -> Optional[dict]:
        """
        获取用户的查询状态
        
        Args:
            user_id: 用户ID
            
        Returns:
            会话状态字典，如果不存在或已超时则返回 None
        """
        import time
        self._cleanup_expired_sessions()
        
        if user_id not in self.session_states:
            return None
        
        state = self.session_states[user_id]
        # 再次检查是否超时
        if time.time() - state['timestamp'] > self.session_timeout:
            del self.session_states[user_id]
            return None
        
        return state
    
    async def _handle_page_navigation(self, event: AstrMessageEvent, action: str):
        """
        处理翻页操作
        
        Args:
            event: 事件对象
            action: 'next' 或 'prev'
        """
        # 停止事件传播
        event.stop_event()
        
        # 获取用户ID
        user_id = event.get_sender_id()
        
        # 获取会话状态
        state = self._get_query_state(user_id)
        if not state:
            yield event.plain_result("❌ 没有可翻⻚的查询记录\n💡 提示：先进行一次列表查询（如“火系宠物”、“红色家具”）")
            return
        
        # 计算新页码
        current_page = state['page']
        total = state['total']
        page_size = self.page_size
        total_pages = (total + page_size - 1) // page_size
        
        if action == 'next':
            new_page = current_page + 1
            if new_page > total_pages:
                yield event.plain_result(f"⚠️ 已经是最后一页了\n当前: 第 {current_page}/{total_pages} 页")
                return
        else:  # prev
            new_page = current_page - 1
            if new_page < 1:
                yield event.plain_result(f"⚠️ 已经是第一⻚了\n当前: 第 {current_page}/{total_pages} 页")
                return
        
        # 更新页码
        state['page'] = new_page
        state['timestamp'] = __import__('time').time()
        
        # 根据查询类型执行相应的查询
        query_type = state['query_type']
        params = state['params']
        
        try:
            if query_type == 'color_pets':
                response = await self._execute_color_pets_query(params, new_page)
            elif query_type == 'rarity_pets':
                response = await self._execute_rarity_pets_query(params, new_page)
            elif query_type == 'source_pets':
                response = await self._execute_source_pets_query(params, new_page)
            elif query_type == 'stage_pets':
                response = await self._execute_stage_pets_query(params, new_page)
            elif query_type == 'element_pets':
                response = await self._execute_element_pets_query(params, new_page)
            elif query_type == 'category_items':
                response = await self._execute_category_items_query(params, new_page)
            else:
                yield event.plain_result(f"❌ 不支持的查询类型: {query_type}")
                return
            
            # 添加分页提示
            response += f"\n\n📄 第 {new_page}/{total_pages} 页 | 回复“洛克下页”或“洛克上页”翻⻚"
            
            yield event.plain_result(response)
            
        except Exception as e:
            logger.error(f"❌ 翻⻚查询失败: {e}", exc_info=True)
            yield event.plain_result(f"❌ 翻⻚失败: {str(e)}")
    
    async def _execute_color_pets_query(self, params: dict, page: int) -> str:
        """执行颜色宠物查询"""
        color = params['color']
        offset = (page - 1) * self.page_size
        
        pets = self.db_service.search_pets_by_color(color, limit=self.page_size, offset=offset)
        
        if not pets:
            return f"❌ 未找到{color}色宠物"
        
        response = f"🎨 **{color}色宠物列表**:\n"
        response += "━━━━━━━━━━━━━━\n\n"
        
        for i, pet in enumerate(pets, offset + 1):
            element = pet.get('element', '未知')
            element2 = pet.get('element2', '')
            extra = f"/{element2}" if element2 else ""
            stage = pet.get('stage', '')
            stage_str = f" [{stage}]" if stage else ""
            response += f"{i}. {pet['name']} ({element}{extra}系){stage_str}\n"
        
        response += f"\n💡 提示：输入完整名称可查看详细信息"
        return response
    
    async def _execute_rarity_pets_query(self, params: dict, page: int) -> str:
        """执行稀有度宠物查询"""
        rarity = params['rarity']
        offset = (page - 1) * self.page_size
        
        cursor = self.db_service.conn.cursor()
        query = "SELECT name, element, element2, stage FROM pets WHERE (description LIKE ? OR ability LIKE ?) ORDER BY name LIMIT ? OFFSET ?"
        cursor.execute(query, (f'%{rarity}%', f'%{rarity}%', self.page_size, offset))
        pets = [dict(zip(['name', 'element', 'element2', 'stage'], row)) for row in cursor.fetchall()]
        
        if not pets:
            return f"❌ 未找到{rarity}稀有度的宠物"
        
        response = f"⭐ **{rarity}稀有度宠物列表**:\n"
        response += "━━━━━━━━━━━━━━\n\n"
        
        for i, pet in enumerate(pets, offset + 1):
            element = pet.get('element', '未知')
            element2 = pet.get('element2', '')
            extra = f"/{element2}" if element2 else ""
            stage = pet.get('stage', '')
            stage_str = f" [{stage}]" if stage else ""
            response += f"{i}. {pet['name']} ({element}{extra}系){stage_str}\n"
        
        response += f"\n💡 提示：输入完整名称可查看详细信息"
        return response
    
    async def _execute_source_pets_query(self, params: dict, page: int) -> str:
        """执行来源宠物查询"""
        source = params['source']
        offset = (page - 1) * self.page_size
        
        source_map = {
            '家园': ['家园', '家具店', '商店'],
            '活动': ['活动', '限时', '节日'],
        }
        source_keywords = source_map.get(source, [source])
        like_conditions = ' OR '.join([f"description LIKE '%{s}%" for s in source_keywords])
        
        cursor = self.db_service.conn.cursor()
        query = f"SELECT name, element, element2, stage FROM pets WHERE ({like_conditions}) ORDER BY name LIMIT ? OFFSET ?"
        cursor.execute(query, (self.page_size, offset))
        pets = [dict(zip(['name', 'element', 'element2', 'stage'], row)) for row in cursor.fetchall()]
        
        if not pets:
            return f"❌ 未找到{source}相关的宠物"
        
        response = f"📍 **{source}相关宠物列表**:\n"
        response += "━━━━━━━━━━━━━━\n\n"
        
        for i, pet in enumerate(pets, offset + 1):
            element = pet.get('element', '未知')
            element2 = pet.get('element2', '')
            extra = f"/{element2}" if element2 else ""
            stage = pet.get('stage', '')
            stage_str = f" [{stage}]" if stage else ""
            response += f"{i}. {pet['name']} ({element}{extra}系){stage_str}\n"
        
        response += f"\n💡 提示：输入完整名称可查看详细信息"
        return response
    
    async def _execute_stage_pets_query(self, params: dict, page: int) -> str:
        """执行阶段宠物查询"""
        stage_keyword = params['stage']
        offset = (page - 1) * self.page_size
        
        stage_map = {
            '初始': ['初始形态', '初级'],
            '最终': ['最终形态', '究极体'],
        }
        stage_keywords = stage_map.get(stage_keyword, [stage_keyword])
        like_conditions = ' OR '.join([f"stage LIKE '%{s}%" for s in stage_keywords])
        
        cursor = self.db_service.conn.cursor()
        query = f"SELECT name, element, element2, stage FROM pets WHERE ({like_conditions}) ORDER BY name LIMIT ? OFFSET ?"
        cursor.execute(query, (self.page_size, offset))
        pets = [dict(zip(['name', 'element', 'element2', 'stage'], row)) for row in cursor.fetchall()]
        
        if not pets:
            return f"❌ 未找到{stage_keyword}阶段的宠物"
        
        response = f"🔄 **{stage_keyword}阶段宠物列表**:\n"
        response += "━━━━━━━━━━━━━━\n\n"
        
        for i, pet in enumerate(pets, offset + 1):
            element = pet.get('element', '未知')
            element2 = pet.get('element2', '')
            extra = f"/{element2}" if element2 else ""
            pet_stage = pet.get('stage', '')
            stage_str = f" [{pet_stage}]" if pet_stage else ""
            response += f"{i}. {pet['name']} ({element}{extra}系){stage_str}\n"
        
        response += f"\n💡 提示：输入完整名称可查看详细信息"
        return response
    
    async def _execute_element_pets_query(self, params: dict, page: int) -> str:
        """执行属性宠物查询"""
        element = params['element']
        offset = (page - 1) * self.page_size
        
        pets = self.db_service.get_pets_by_element(element, limit=self.page_size, offset=offset)
        
        if not pets:
            return f"❌ 未找到{element}系宠物"
        
        response = f"🔥 **{element}系宠物列表**:\n"
        response += "━━━━━━━━━━━━━━\n\n"
        
        for i, pet in enumerate(pets, offset + 1):
            element2 = pet.get('element2', '')
            extra = f"/{element2}" if element2 else ""
            response += f"{i}. {pet['name']} ({pet['element']}{extra}系)\n"
        
        response += f"\n💡 提示：输入完整名称可查看详细信息"
        return response
    
    async def _execute_category_items_query(self, params: dict, page: int) -> str:
        """执行分类/颜色道具查询"""
        keyword = params['keyword']
        category = params['category']
        filter_type = params['filter_type']
        offset = (page - 1) * self.page_size
        
        db_category_map = {
            'furniture': '家具',
            'item': '',
            'skill_stone': '技能石',
            'gumball': '咕噜球',
            'fruit': '精灵果实',
        }
        db_category = db_category_map.get(category, '')
        
        cursor = self.db_service.conn.cursor()
        
        if filter_type == 'color':
            color_map = {
                '蓝': ['蓝'], '红': ['红'], '绿': ['绿'], '黄': ['黄'],
                '紫': ['紫'], '白': ['白'], '黑': ['黑'], '粉': ['粉'], '橙': ['橙'],
            }
            color_keywords = color_map.get(keyword, [keyword])
            like_conditions_main = ' OR '.join([f"main_color = '{c}'" for c in color_keywords])
            like_conditions_rarity = ' OR '.join([f"rarity LIKE '%{c}%'" for c in color_keywords])
            
            query = f"SELECT name, category, rarity, main_color FROM items WHERE ({like_conditions_main}) OR ({like_conditions_rarity})"
            if db_category:
                query += f" AND category = '{db_category}'"
            query += " ORDER BY name LIMIT ? OFFSET ?"
            
            cursor.execute(query, (self.page_size, offset))
            items = [dict(zip(['name', 'category', 'rarity', 'main_color'], row)) for row in cursor.fetchall()]
        else:
            # 其他筛选类型简化处理
            query = f"SELECT name, category, rarity, main_color FROM items WHERE category = '{db_category}' ORDER BY name LIMIT ? OFFSET ?"
            cursor.execute(query, (self.page_size, offset))
            items = [dict(zip(['name', 'category', 'rarity', 'main_color'], row)) for row in cursor.fetchall()]
        
        if not items:
            return f"❌ 未找到相关{db_category or '道具'}"
        
        type_names = {'color': '颜色', 'rarity': '稀有度', 'source': '来源'}
        type_name = type_names.get(filter_type, '')
        
        response = f"🎨 **{keyword}{type_name}的{db_category or '道具'}**:\n"
        response += "━━━━━━━━━━━━━━\n\n"
        
        for i, item in enumerate(items, offset + 1):
            response += f"{i}. **{item['name']}**"
            if item.get('main_color'):
                response += f" [{item['main_color']}]"
            elif item.get('rarity'):
                response += f" [{item['rarity']}]"
            response += "\n"
        
        response += f"\n💡 提示：输入完整名称可查看详细信息"
        return response
    
    @filter.command("洛克管理", ["wiki_admin", "wiki-admin"])
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def handle_admin(self, event: AstrMessageEvent, command: str):
        """
        管理员命令（通过 AstrBot 权限系统控制）
        用法: /洛克管理 <command>
        可用命令:
          - update: 更新数据库（从 Wiki 爬取最新数据）
          - status: 查看数据库状态
          - tag-colors: 为无颜色的家具/道具识别颜色（大模型视觉识别）
          - tag-pet-colors: 为无颜色的宠物/精灵蛋识别颜色（大模型视觉识别）
          - force-tag-colors: 强制重新识别所有家具/道具颜色（覆盖已有颜色）
          - force-tag-pet-colors: 强制重新识别所有宠物/精灵蛋颜色（覆盖已有颜色）
          - fix-missing: 补全缺失的宠物数据
        """
        # 停止事件传播，防止被 Agent/LLM 拦截
        event.stop_event()
        
        # 解析命令
        parts = command.strip().split()
        if len(parts) < 1:
            yield f"❌ 请提供命令\n用法: /洛克管理 <command>\n示例: /洛克管理 update"
            return
        
        cmd = parts[0].lower()
        
        # 执行命令
        if cmd == "update":
            async for msg in self._handle_update_db(event):
                yield msg
        elif cmd == "status":
            async for msg in self._handle_db_status(event):
                yield msg
        elif cmd == "tag-colors":
            async for msg in self._handle_tag_colors(event):
                yield msg
                    
        elif cmd == "tag-pet-colors":
            async for msg in self._handle_tag_pet_colors(event):
                yield msg
        elif cmd == "force-tag-colors":
            async for msg in self._handle_force_tag_colors(event):
                yield msg
        elif cmd == "force-tag-pet-colors":
            async for msg in self._handle_force_tag_pet_colors(event):
                yield msg
        elif cmd == "fix-missing":
            async for msg in self._handle_fix_missing_data(event):
                yield msg
        elif cmd == "check-vision":
            async for msg in self._handle_check_vision_model(event):
                yield msg
        else:
            yield f"❌ 未知命令: {cmd}\n\n📋 可用命令:\n  • update - 增量更新数据库\n  • status - 查看数据库状态\n  • tag-colors - 为道具标记颜色\n  • tag-pet-colors - 为宠物标记颜色\n  • force-tag-colors - 强制重新识别所有道具颜色\n  • force-tag-pet-colors - 强制重新识别所有宠物颜色\n  • fix-missing - 补全缺失的宠物数据\n  • check-vision - 检查视觉模型配置\n\n示例: 洛克管理 check-vision"
    
    async def _handle_update_db(self, event: AstrMessageEvent):
        """处理数据库更新命令"""
        yield "🔄 开始更新数据库，这可能需要几分钟时间..."
        
        try:
            # 获取插件目录
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            build_script = os.path.join(plugin_dir, "src", "build_wiki_db.py")
            
            if not os.path.exists(build_script):
                yield "❌ 找不到爬虫脚本"
                return
            
            # 运行爬虫脚本
            process = subprocess.Popen(
                [sys.executable, build_script, "build", "--full"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=plugin_dir
            )
            
            # 等待完成
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                yield "✅ 数据库更新成功！\n可以开始使用新数据进行查询。"
                logger.info("✅ 数据库更新成功")
            else:
                error_msg = stderr[:500] if stderr else "未知错误"
                yield f"❌ 数据库更新失败:\n{error_msg}"
                logger.error(f"❌ 数据库更新失败: {stderr}")
        
        except Exception as e:
            yield f"❌ 更新过程出错: {str(e)}"
            logger.error(f"❌ 更新过程出错: {e}", exc_info=True)
    
    async def _handle_db_status(self, event: AstrMessageEvent):
        """处理数据库状态查询命令"""
        if not self.db_service:
            yield "❌ 数据库服务不可用"
            return
        
        try:
            stats = self.db_service.get_database_stats()
            
            response = f"📊 **数据库状态**\n\n"
            response += f"宠物数量: {stats['pets']}\n"
            response += f"技能数量: {stats['skills']}\n"
            response += f"Wiki页面: {stats['pages']}\n"
            response += f"属性克制: {stats['type_chart']}\n"
            
            # 检查是否有图片
            has_images = False
            if stats['pets'] > 0:
                sample_pets = self.db_service.get_pet_info("", fuzzy=True, limit=5)
                for pet in sample_pets:
                    img_path = pet.get('sprite_image_local')
                    if img_path and os.path.exists(img_path):
                        has_images = True
                        break
            
            if has_images:
                response += "\n✅ 已包含宠物图片"
            else:
                response += "\n⚠️ 暂无宠物图片"
            
            yield response
        
        except Exception as e:
            yield f"❌ 获取数据库状态失败: {str(e)}"
            logger.error(f"❌ 获取数据库状态失败: {e}", exc_info=True)
    
    async def _handle_check_vision_model(self, event: AstrMessageEvent):
        """处理视觉模型诊断命令"""
        yield "🔍 开始检查视觉模型配置..."
        
        vision_model_config = self.config.get("vision_model_config", "")
        
        if not vision_model_config or not vision_model_config.strip():
            yield "❌ 未配置视觉模型\n💡 请在 WebUI 的插件配置中选择视觉模型"
            return
        
        yield f"📋 配置的视觉模型: {vision_model_config}"
        
        try:
            provider_manager = getattr(self.context, 'provider_manager', None)
            if not provider_manager:
                yield "❌ 无法访问 provider_manager"
                return
            
            providers = getattr(provider_manager, 'get_insts', lambda: [])()
            
            if not providers:
                yield "❌ 没有找到任何已配置的 Provider\n💡 请先在 AstrBot 中配置至少一个 Provider"
                return
            
            yield f"📊 找到 {len(providers)} 个 Provider"
            
            # 列出所有 provider 的详细信息
            response = "\n📋 Provider 列表:\n"
            selected_found = False
            
            for i, p in enumerate(providers, 1):
                pid = (getattr(p, 'id', None) or 
                       getattr(p, 'provider_id', None) or 
                       getattr(p, 'name', None) or 
                       getattr(p, 'model_name', None) or 
                       getattr(p, 'model', None) or 
                       str(type(p).__name__))
                
                pname = getattr(p, 'name', '') or getattr(p, 'model_name', '') or pid
                api_key = getattr(p, 'api_key', '') or ''
                base_url = getattr(p, 'base_url', '') or ''
                model = getattr(p, 'model_name', '') or getattr(p, 'model', '') or ''
                
                response += f"\n{i}. ID: {pid}\n"
                response += f"   名称: {pname}\n"
                response += f"   API Key: {'✓' if api_key else '✗'}\n"
                response += f"   Base URL: {base_url[:50] + '...' if len(base_url) > 50 else base_url}\n"
                response += f"   Model: {model}\n"
                
                # 精确匹配
                if pid == vision_model_config:
                    selected_found = True
                    response += "   ✅ 这是当前选中的视觉模型（精确匹配）\n"
                # 模糊匹配：去除前缀后匹配
                elif '/' in vision_model_config:
                    config_model_name = vision_model_config.split('/')[-1]
                    if pid == config_model_name or pid.endswith('/' + config_model_name):
                        selected_found = True
                        response += f"   ✅ 这是当前选中的视觉模型（模糊匹配）\n"
            
            yield response
            
            if not selected_found:
                yield f"\n❌ 未找到匹配 '{vision_model_config}' 的 Provider\n💡 请检查配置是否正确"
            else:
                yield f"\n✅ 视觉模型配置正确！"
                
                # 测试颜色提取器
                if self.color_extractor:
                    yield "✅ 颜色提取器已初始化成功"
                else:
                    yield "❌ 颜色提取器初始化失败，请检查日志"
        
        except Exception as e:
            yield f"❌ 检查过程出错: {str(e)}"
            logger.error(f"❌ 检查视觉模型配置失败: {e}", exc_info=True)
    
    async def _handle_tag_colors(self, event: AstrMessageEvent):
        """处理家具/道具颜色识别命令（大模型视觉识别，只标记无颜色的）"""
        yield "🎨 开始为无颜色的家具/道具识别颜色...（使用大模型视觉识别）"
        
        # 检查颜色提取器是否可用
        if not self.color_extractor:
            yield "❌ 颜色提取器不可用，请先在 WebUI 中配置视觉模型"
            return
        
        try:
            import sqlite3
            
            # 连接数据库
            db_path = self.config.get("db_path", "./wiki-local.db")
            if not os.path.isabs(db_path):
                db_path = os.path.join(plugin_dir, db_path)
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            try:
                # 检查并添加 main_color 字段（如果不存在）
                cursor.execute("PRAGMA table_info(items)")
                columns = [row[1] for row in cursor.fetchall()]
                if 'main_color' not in columns:
                    yield "📝 添加 main_color 字段到 items 表"
                    cursor.execute("ALTER TABLE items ADD COLUMN main_color TEXT")
                    conn.commit()
                
                # 查询所有未设置颜色的家具和道具
                cursor.execute("""
                    SELECT name, image_local, category, subcategory
                    FROM items 
                    WHERE (main_color IS NULL OR main_color = '')
                    AND image_local IS NOT NULL
                    AND image_local != ''
                """)
                
                items_list = cursor.fetchall()
                
                if not items_list:
                    yield "✅ 所有家具和道具都已设置颜色"
                    return
                
                total_count = len(items_list)
                yield f"📋 找到 {total_count} 个需要识别颜色的项目"
                yield "💡 提示：使用大模型视觉识别，速度较慢但更准确"
                
                success_count = 0
                fail_count = 0
                no_color_count = 0
                
                for i, (name, image_local, category, subcategory) in enumerate(items_list, 1):
                    # 构建完整图片路径
                    if image_local and not os.path.isabs(image_local):
                        full_path = os.path.join(plugin_dir, image_local)
                    else:
                        full_path = image_local
                    
                    # 检查图片是否存在
                    if not full_path or not os.path.exists(full_path):
                        logger.warning(f"图片不存在: {full_path}")
                        fail_count += 1
                        continue
                    
                    # 使用大模型视觉识别提取颜色
                    result = self.color_extractor.extract_main_colors(full_path)
                    
                    if result and result['main_color']:
                        cursor.execute(
                            "UPDATE items SET main_color = ? WHERE name = ?",
                            (result['main_color'], name)
                        )
                        conn.commit()
                        success_count += 1
                        colors_str = ', '.join(result['colors'])
                        logger.info(f"[{i}/{total_count}] {name}: {colors_str}")
                    elif result and not result['main_color']:
                        no_color_count += 1
                    else:
                        fail_count += 1
                    
                    # 每处理10个发送一次进度（大模型速度慢，降低频率）
                    if i % 10 == 0:
                        yield f"⏳ 进度: {i}/{total_count} (成功: {success_count}, 无颜色: {no_color_count}, 失败: {fail_count})"
                
                yield f"✅ 颜色识别完成！\n总计: {total_count}\n成功: {success_count}\n无颜色: {no_color_count}\n失败: {fail_count}"
                logger.info(f"颜色识别完成: 成功{success_count}, 无颜色{no_color_count}, 失败{fail_count}")
                
            finally:
                conn.close()
        
        except Exception as e:
            yield f"❌ 颜色识别过程出错: {str(e)}"
            logger.error(f"❌ 颜色识别过程出错: {e}", exc_info=True)
    
    async def _handle_tag_pet_colors(self, event: AstrMessageEvent):
        """处理宠物/精灵蛋颜色识别命令（大模型视觉识别，只标记无颜色的）"""
        yield "🎨 开始为无颜色的宠物/精灵蛋识别颜色...（使用大模型视觉识别）"
        
        # 检查颜色提取器是否可用
        if not self.color_extractor:
            yield "❌ 颜色提取器不可用，请先在 WebUI 中配置视觉模型"
            return
        
        try:
            import sqlite3
            
            # 连接数据库
            db_path = self.config.get("db_path", "./wiki-local.db")
            if not os.path.isabs(db_path):
                db_path = os.path.join(plugin_dir, db_path)
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            try:
                # 检查并添加 main_color 字段（如果不存在）
                cursor.execute("PRAGMA table_info(pets)")
                columns = [row[1] for row in cursor.fetchall()]
                if 'main_color' not in columns:
                    yield "📝 添加 main_color 字段到 pets 表"
                    cursor.execute("ALTER TABLE pets ADD COLUMN main_color TEXT")
                    conn.commit()
                
                # 查询所有未设置颜色的宠物
                cursor.execute("""
                    SELECT name, sprite_image_local
                    FROM pets 
                    WHERE (main_color IS NULL OR main_color = '')
                    AND sprite_image_local IS NOT NULL
                    AND sprite_image_local != ''
                """)
                
                pets_list = cursor.fetchall()
                
                if not pets_list:
                    yield "✅ 所有宠物都已设置颜色"
                    return
                
                total_count = len(pets_list)
                yield f"📋 找到 {total_count} 个需要识别颜色的宠物"
                yield "💡 提示：使用大模型视觉识别，速度较慢但更准确"
                
                success_count = 0
                fail_count = 0
                no_color_count = 0
                
                for i, (name, image_local) in enumerate(pets_list, 1):
                    # 构建完整图片路径
                    if image_local and not os.path.isabs(image_local):
                        full_path = os.path.join(plugin_dir, image_local)
                    else:
                        full_path = image_local
                    
                    # 检查图片是否存在
                    if not full_path or not os.path.exists(full_path):
                        logger.warning(f"图片不存在: {full_path}")
                        fail_count += 1
                        continue
                    
                    # 使用大模型视觉识别提取颜色
                    result = self.color_extractor.extract_main_colors(full_path)
                    
                    if result and result['main_color']:
                        cursor.execute(
                            "UPDATE pets SET main_color = ? WHERE name = ?",
                            (result['main_color'], name)
                        )
                        conn.commit()
                        success_count += 1
                        colors_str = ', '.join(result['colors'])
                        logger.info(f"[{i}/{total_count}] {name}: {colors_str}")
                    elif result and not result['main_color']:
                        no_color_count += 1
                    else:
                        fail_count += 1
                    
                    # 每处理10个发送一次进度（大模型速度慢，降低频率）
                    if i % 10 == 0:
                        yield f"⏳ 进度: {i}/{total_count} (成功: {success_count}, 无颜色: {no_color_count}, 失败: {fail_count})"
                
                yield f"✅ 颜色识别完成！\n总计: {total_count}\n成功: {success_count}\n无颜色: {no_color_count}\n失败: {fail_count}"
                logger.info(f"颜色识别完成: 成功{success_count}, 无颜色{no_color_count}, 失败{fail_count}")
                
            finally:
                conn.close()
        
        except Exception as e:
            yield f"❌ 颜色识别过程出错: {str(e)}"
            logger.error(f"❌ 颜色识别过程出错: {e}", exc_info=True)
    
    async def _handle_fix_missing_data(self, event: AstrMessageEvent):
        """处理补全缺失宠物数据命令"""
        yield "🔍 开始检查数据库中缺失数据的宠物..."
        
        try:
            import sys
            import subprocess
            
            # 获取插件目录
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(plugin_dir, "tools", "fix_missing_pet_data.py")
            
            # 检查脚本是否存在
            if not os.path.exists(script_path):
                yield f"❌ 找不到维护脚本: {script_path}"
                return
            
            yield f"📋 运行数据补全脚本...\n这可能需要几分钟时间，请耐心等待"
            
            # 执行脚本（非交互模式，自动执行）
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=600,  # 10分钟超时
                cwd=plugin_dir,
                input='y\n'  # 自动确认执行
            )
            
            if result.returncode == 0:
                output = result.stdout
                # 提取关键信息
                lines = output.split('\n')
                summary_lines = [line for line in lines if '✅' in line or '成功:' in line or '失败:' in line]
                
                if summary_lines:
                    yield "✅ 数据补全完成！\n\n" + '\n'.join(summary_lines[-5:])
                else:
                    yield "✅ 数据补全完成！请查看日志获取详细信息"
                
                logger.info(f"数据补全完成:\n{output}")
            else:
                error_msg = result.stderr if result.stderr else result.stdout
                yield f"❌ 数据补全失败:\n{error_msg[:500]}"
                logger.error(f"数据补全失败: {error_msg}")
        
        except subprocess.TimeoutExpired:
            yield "⏰ 数据补全超时（超过10分钟），请稍后重试或手动运行脚本"
            logger.error("数据补全超时")
        except Exception as e:
            yield f"❌ 执行出错: {str(e)}"
            logger.error(f"❌ 数据补全执行出错: {e}", exc_info=True)
    
    async def _handle_force_tag_colors(self, event: AstrMessageEvent):
        """处理强制重新识别家具/道具颜色命令（大模型视觉识别，覆盖已有颜色）"""
        yield "🎨 开始强制重新识别所有家具/道具颜色...（使用大模型视觉识别，将覆盖已有颜色）"
        
        # 检查颜色提取器是否可用
        if not self.color_extractor:
            yield "❌ 颜色提取器不可用，请先在 WebUI 中配置视觉模型"
            return
        
        try:
            import sqlite3
            
            # 连接数据库
            db_path = self.config.get("db_path", "./wiki-local.db")
            if not os.path.isabs(db_path):
                db_path = os.path.join(plugin_dir, db_path)
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            try:
                # 检查并添加 main_color 字段（如果不存在）
                cursor.execute("PRAGMA table_info(items)")
                columns = [row[1] for row in cursor.fetchall()]
                if 'main_color' not in columns:
                    yield "📝 添加 main_color 字段到 items 表"
                    cursor.execute("ALTER TABLE items ADD COLUMN main_color TEXT")
                    conn.commit()
                
                # 查询所有有图片的家具和道具（不论是否已有颜色）
                cursor.execute("""
                    SELECT name, image_local, category, subcategory, main_color
                    FROM items 
                    WHERE image_local IS NOT NULL
                    AND image_local != ''
                """)
                
                items_list = cursor.fetchall()
                
                if not items_list:
                    yield "✅ 没有找到需要识别的项目"
                    return
                
                total_count = len(items_list)
                has_color_count = sum(1 for item in items_list if item[4])
                no_color_count_initial = total_count - has_color_count
                
                yield f"📋 找到 {total_count} 个项目（已有颜色: {has_color_count}, 无颜色: {no_color_count_initial}）"
                yield "⚠️ 警告：这将覆盖所有已有的颜色数据！"
                yield "💡 提示：使用大模型视觉识别，速度较慢但更准确"
                
                success_count = 0
                fail_count = 0
                no_color_count = 0
                updated_count = 0
                
                for i, (name, image_local, category, subcategory, old_color) in enumerate(items_list, 1):
                    # 构建完整图片路径
                    if image_local and not os.path.isabs(image_local):
                        full_path = os.path.join(plugin_dir, image_local)
                    else:
                        full_path = image_local
                    
                    # 检查图片是否存在
                    if not full_path or not os.path.exists(full_path):
                        logger.warning(f"图片不存在: {full_path}")
                        fail_count += 1
                        continue
                    
                    # 使用大模型视觉识别提取颜色
                    result = self.color_extractor.extract_main_colors(full_path)
                    
                    if result and result['main_color']:
                        new_color = result['main_color']
                        cursor.execute(
                            "UPDATE items SET main_color = ? WHERE name = ?",
                            (new_color, name)
                        )
                        conn.commit()
                        success_count += 1
                        
                        # 统计覆盖情况
                        if old_color and old_color != new_color:
                            updated_count += 1
                            logger.info(f"[{i}/{total_count}] {name}: {old_color} → {new_color}")
                        elif not old_color:
                            logger.info(f"[{i}/{total_count}] {name}: 新增 {new_color}")
                        else:
                            logger.info(f"[{i}/{total_count}] {name}: {new_color} (未变化)")
                    elif result and not result['main_color']:
                        no_color_count += 1
                    else:
                        fail_count += 1
                    
                    # 每处理10个发送一次进度（大模型速度慢，降低频率）
                    if i % 10 == 0:
                        yield f"⏳ 进度: {i}/{total_count} (成功: {success_count}, 覆盖: {updated_count}, 无颜色: {no_color_count}, 失败: {fail_count})"
                
                yield f"✅ 强制颜色识别完成！\n总计: {total_count}\n成功: {success_count}\n覆盖旧值: {updated_count}\n无颜色: {no_color_count}\n失败: {fail_count}"
                logger.info(f"强制颜色识别完成: 成功{success_count}, 覆盖{updated_count}, 无颜色{no_color_count}, 失败{fail_count}")
                
            finally:
                conn.close()
        
        except Exception as e:
            yield f"❌ 颜色识别过程出错: {str(e)}"
            logger.error(f"❌ 颜色识别过程出错: {e}", exc_info=True)
    
    async def _handle_force_tag_pet_colors(self, event: AstrMessageEvent):
        """处理强制重新识别宠物/精灵蛋颜色命令（大模型视觉识别，覆盖已有颜色）"""
        yield "🎨 开始强制重新识别所有宠物/精灵蛋颜色...（使用大模型视觉识别，将覆盖已有颜色）"
        
        # 检查颜色提取器是否可用
        if not self.color_extractor:
            yield "❌ 颜色提取器不可用，请先在 WebUI 中配置视觉模型"
            return
        
        try:
            import sqlite3
            
            # 连接数据库
            db_path = self.config.get("db_path", "./wiki-local.db")
            if not os.path.isabs(db_path):
                db_path = os.path.join(plugin_dir, db_path)
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            try:
                # 检查并添加 main_color 字段（如果不存在）
                cursor.execute("PRAGMA table_info(pets)")
                columns = [row[1] for row in cursor.fetchall()]
                if 'main_color' not in columns:
                    yield "📝 添加 main_color 字段到 pets 表"
                    cursor.execute("ALTER TABLE pets ADD COLUMN main_color TEXT")
                    conn.commit()
                
                # 查询所有有图片的宠物（不论是否已有颜色）
                cursor.execute("""
                    SELECT name, sprite_image_local, main_color
                    FROM pets 
                    WHERE sprite_image_local IS NOT NULL
                    AND sprite_image_local != ''
                """)
                
                pets_list = cursor.fetchall()
                
                if not pets_list:
                    yield "✅ 没有找到需要识别的宠物"
                    return
                
                total_count = len(pets_list)
                has_color_count = sum(1 for pet in pets_list if pet[2])
                no_color_count_initial = total_count - has_color_count
                
                yield f"📋 找到 {total_count} 个宠物（已有颜色: {has_color_count}, 无颜色: {no_color_count_initial}）"
                yield "⚠️ 警告：这将覆盖所有已有的颜色数据！"
                yield "💡 提示：使用大模型视觉识别，速度较慢但更准确"
                
                success_count = 0
                fail_count = 0
                no_color_count = 0
                updated_count = 0
                
                for i, (name, image_local, old_color) in enumerate(pets_list, 1):
                    # 构建完整图片路径
                    if image_local and not os.path.isabs(image_local):
                        full_path = os.path.join(plugin_dir, image_local)
                    else:
                        full_path = image_local
                    
                    # 检查图片是否存在
                    if not full_path or not os.path.exists(full_path):
                        logger.warning(f"图片不存在: {full_path}")
                        fail_count += 1
                        continue
                    
                    # 使用大模型视觉识别提取颜色
                    result = await self.color_extractor.extract_main_colors_async(full_path)
                    # 清洗非法UTF-8字符，解决MALFORMED错误
                    import re
                    result = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', result)  # 删掉控制符
                    result = result.encode('utf-8', 'ignore').decode('utf-8')  # 强制清理畸形编码
                    result = result.strip()  # 去掉空字符/空格
                    
                    if result and result['main_color']:
                        new_color = result['main_color']
                        cursor.execute(
                            "UPDATE pets SET main_color = ? WHERE name = ?",
                            (new_color, name)
                        )
                        conn.commit()
                        success_count += 1
                        
                        # 统计覆盖情况
                        if old_color and old_color != new_color:
                            updated_count += 1
                            logger.info(f"[{i}/{total_count}] {name}: {old_color} → {new_color}")
                        elif not old_color:
                            logger.info(f"[{i}/{total_count}] {name}: 新增 {new_color}")
                        else:
                            logger.info(f"[{i}/{total_count}] {name}: {new_color} (未变化)")
                    elif result and not result['main_color']:
                        no_color_count += 1
                    else:
                        fail_count += 1
                    
                    # 每处理10个发送一次进度（大模型速度慢，降低频率）
                    if i % 10 == 0:
                        yield f"⏳ 进度: {i}/{total_count} (成功: {success_count}, 覆盖: {updated_count}, 无颜色: {no_color_count}, 失败: {fail_count})"
                
                yield f"✅ 强制颜色识别完成！\n总计: {total_count}\n成功: {success_count}\n覆盖旧值: {updated_count}\n无颜色: {no_color_count}\n失败: {fail_count}"
                logger.info(f"强制颜色识别完成: 成功{success_count}, 覆盖{updated_count}, 无颜色{no_color_count}, 失败{fail_count}")
                
            finally:
                conn.close()
        
        except Exception as e:
            yield f"❌ 颜色识别过程出错: {str(e)}"
            logger.error(f"❌ 颜色识别过程出错: {e}", exc_info=True)
        """插件卸载/停用时清理资源"""
        if self.db_service:
            self.db_service.close()
            logger.info("🔒 数据库连接已关闭")
