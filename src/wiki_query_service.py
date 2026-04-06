"""
Wiki 查询服务 - 供 Agent 调用的 API 接口
提供简单高效的本地数据查询功能
"""
from typing import Optional, List, Dict
from src.wiki_local_db import WikiLocalDB


class WikiQueryService:
    """
    Wiki 查询服务（单例模式）
    
    使用示例:
        service = WikiQueryService.get_instance()
        result = service.get_pet_info("炽心勇狮")
    """
    
    _instance = None
    _db = None
    
    @classmethod
    def get_instance(cls, db_path: str = "./wiki-local.db"):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls(db_path)
        return cls._instance
    
    def __init__(self, db_path: str = "./wiki-local.db"):
        """初始化查询服务"""
        self.db = WikiLocalDB(db_path)
    
    def get_pet_info(self, pet_name: str) -> dict:
        """
        获取宠物详细信息
        
        Args:
            pet_name: 宠物名称
        
        Returns:
            包含 success 和 data/message 的字典
        """
        result = self.db.query_pet(pet_name)
        if result:
            return {
                "success": True,
                "data": result
            }
        return {
            "success": False,
            "message": f"未找到宠物: {pet_name}"
        }
    
    def get_skill_info(self, skill_name: str) -> dict:
        """
        获取技能详细信息
        
        Args:
            skill_name: 技能名称
        
        Returns:
            包含 success 和 data/message 的字典
        """
        result = self.db.query_skill(skill_name)
        if result:
            return {
                "success": True,
                "data": result
            }
        return {
            "success": False,
            "message": f"未找到技能: {skill_name}"
        }
    
    def search_pets(self, keyword: str, limit: int = 10) -> dict:
        """
        搜索宠物（模糊匹配）
        
        Args:
            keyword: 搜索关键词
            limit: 返回结果数量限制
        
        Returns:
            包含 success, count, data 的字典
        """
        results = self.db.search_pets(keyword, limit)
        return {
            "success": True,
            "count": len(results),
            "data": results
        }
    
    def search_skills(self, keyword: str, limit: int = 10) -> dict:
        """
        搜索技能（模糊匹配）
        
        Args:
            keyword: 搜索关键词
            limit: 返回结果数量限制
        
        Returns:
            包含 success, count, data 的字典
        """
        results = self.db.search_skills(keyword, limit)
        return {
            "success": True,
            "count": len(results),
            "data": results
        }
    
    def get_pets_by_element(self, element: str, limit: int = 50) -> dict:
        """
        根据属性获取宠物列表
        
        Args:
            element: 属性名称（如：火、水、草）
            limit: 返回结果数量限制
        
        Returns:
            包含 success, count, data 的字典
        """
        results = self.db.get_pets_by_element(element, limit)
        return {
            "success": True,
            "element": element,
            "count": len(results),
            "data": results
        }
    
    def get_skills_by_element(self, element: str, limit: int = 50) -> dict:
        """
        根据属性获取技能列表
        
        Args:
            element: 属性名称
            limit: 返回结果数量限制
        
        Returns:
            包含 success, count, data 的字典
        """
        results = self.db.get_skills_by_element(element, limit)
        return {
            "success": True,
            "element": element,
            "count": len(results),
            "data": results
        }
    
    def get_type_advantage(self, element: str) -> dict:
        """
        查询属性克制关系
        
        Args:
            element: 属性名称
        
        Returns:
            包含克制关系的字典
        """
        result = self.db.get_type_advantage(element)
        if result['attack_type']:
            return {
                "success": True,
                "data": result
            }
        return {
            "success": False,
            "message": f"未知属性: {element}"
        }
    
    def get_database_stats(self) -> dict:
        """
        获取数据库统计信息
        
        Returns:
            包含统计信息的字典
        """
        stats = self.db.get_stats()
        return {
            "success": True,
            "stats": stats
        }
    
    def close(self):
        """关闭数据库连接"""
        if self.db:
            self.db.close()
    
    def __del__(self):
        """析构函数"""
        self.close()


# 便捷函数 - 直接调用
def query_pet(pet_name: str) -> dict:
    """快捷查询宠物"""
    service = WikiQueryService.get_instance()
    return service.get_pet_info(pet_name)


def query_skill(skill_name: str) -> dict:
    """快捷查询技能"""
    service = WikiQueryService.get_instance()
    return service.get_skill_info(skill_name)


def search_pets(keyword: str, limit: int = 10) -> dict:
    """快捷搜索宠物"""
    service = WikiQueryService.get_instance()
    return service.search_pets(keyword, limit)


def get_type_advantage(element: str) -> dict:
    """快捷查询属性克制"""
    service = WikiQueryService.get_instance()
    return service.get_type_advantage(element)


if __name__ == "__main__":
    import json
    
    print("=" * 60)
    print("Wiki 查询服务测试")
    print("=" * 60)
    
    service = WikiQueryService.get_instance()
    
    try:
        # 测试 1: 查询宠物
        print("\n【测试 1】查询宠物信息")
        result = service.get_pet_info("炽心勇狮")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # 测试 2: 查询技能
        print("\n【测试 2】查询技能信息")
        result = service.get_skill_info("暗突袭")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # 测试 3: 搜索宠物
        print("\n【测试 3】搜索宠物")
        result = service.search_pets("喵", limit=3)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # 测试 4: 属性克制
        print("\n【测试 4】属性克制关系")
        result = service.get_type_advantage("火")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # 测试 5: 数据库统计
        print("\n【测试 5】数据库统计")
        result = service.get_database_stats()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
    finally:
        service.close()
