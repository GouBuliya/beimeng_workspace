"""AI 标题生成器.

生成商品标题，支持多种模式。
"""

import re
from typing import Optional

from loguru import logger


class TitleGenerator:
    """AI 标题生成器.
    
    优先级：
    1. 使用 Temu 自带 AI 功能（通过影刀触发）
    2. 调用外部 API（如 OpenAI, 通义千问等）
    3. 基于规则生成（保底方案）
    
    Attributes:
        mode: 生成模式 (temu|api|rule)
        
    Examples:
        >>> generator = TitleGenerator(mode="rule")
        >>> title = generator.generate("智能手表", "手表")
        >>> "智能手表" in title
        True
    """

    def __init__(self, mode: str = "temu"):
        """初始化生成器.
        
        Args:
            mode: 生成模式 (temu|api|rule)
        """
        self.mode = mode
        logger.info(f"标题生成器初始化，模式: {mode}")

    def generate_by_rule(self, product_name: str, keyword: str) -> str:
        """基于规则生成标题（保底方案）.
        
        规则：
        - 提取核心词汇
        - 添加修饰词（新款、热卖、优质等）
        - 控制长度 50-80 字符
        
        Args:
            product_name: 商品名称
            keyword: 关键词
            
        Returns:
            生成的标题
            
        Examples:
            >>> gen = TitleGenerator(mode="rule")
            >>> title = gen.generate_by_rule("智能手表运动防水", "智能手表")
            >>> len(title) > 0
            True
        """
        # 简单规则：关键词 + 产品名 + 修饰语
        modifiers = ["新款", "热卖", "优质", "精选"]

        # 清理产品名
        clean_name = re.sub(r"[^\w\s-]", "", product_name).strip()

        # 组合标题
        title = f"{keyword} {clean_name} 【{modifiers[0]}】"

        # 截断到合理长度
        if len(title) > 80:
            title = title[:77] + "..."

        logger.debug(f"规则生成标题: {title}")
        return title

    def generate_by_api(self, product_name: str, keyword: str) -> str:
        """调用 API 生成标题.
        
        Args:
            product_name: 商品名称
            keyword: 关键词
            
        Returns:
            生成的标题
            
        Note:
            MVP 阶段可以先返回 None，后续再实现
        """
        logger.warning("API 模式暂未实现，使用规则生成")
        return self.generate_by_rule(product_name, keyword)

    def generate(self, product_name: str, keyword: str, fallback: bool = True) -> str:
        """生成标题（主入口）.
        
        Args:
            product_name: 商品名称
            keyword: 关键词
            fallback: 失败时是否降级到规则生成
            
        Returns:
            生成的标题
            
        Examples:
            >>> gen = TitleGenerator(mode="temu")
            >>> title = gen.generate("智能手表", "手表")
            >>> title.startswith("[TEMU_AI:")
            True
        """
        try:
            if self.mode == "temu":
                # Temu 模式：在影刀中触发，这里只是标记
                logger.info("将使用 Temu 自带 AI 生成标题（影刀执行）")
                return f"[TEMU_AI:{keyword}]"  # 占位符

            elif self.mode == "api":
                return self.generate_by_api(product_name, keyword)

            else:  # rule
                return self.generate_by_rule(product_name, keyword)

        except Exception as e:
            logger.error(f"标题生成失败: {e}")
            if fallback:
                logger.info("降级到规则生成")
                return self.generate_by_rule(product_name, keyword)
            raise


# 测试代码
if __name__ == "__main__":
    generator = TitleGenerator(mode="rule")

    test_cases = [
        ("智能手表 运动防水", "智能手表"),
        ("无线蓝牙耳机 降噪 TWS", "蓝牙耳机"),
        ("咖啡机 全自动 家用", "咖啡机"),
    ]

    for name, keyword in test_cases:
        title = generator.generate(name, keyword)
        print(f"原名: {name}")
        print(f"标题: {title}\n")


