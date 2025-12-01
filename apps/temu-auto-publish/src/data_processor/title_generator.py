"""
@PURPOSE: AI标题生成器，支持多种模式生成商品标题（基于SOP v2.0规则）
@OUTLINE:
  - class TitleGenerator: 标题生成器主类
  - def generate(): 生成商品标题
  - def generate_with_model_suffix(): 生成标题并添加型号后缀（SOP要求）
  - def generate_with_temu_ai(): 使用Temu AI生成
  - def generate_with_api(): 使用外部API生成
  - def generate_with_rules(): 基于规则生成（保底方案）
@GOTCHAS:
  - SOP要求：必须添加型号后缀（如"A0001型号"）
  - 可选添加修饰词（如"2025新款"）
  - 不要出现医疗相关词汇
@TECH_DEBT:
  - TODO: 实现外部API调用（OpenAI/通义千问）
  - TODO: 优化规则生成的标题质量
@DEPENDENCIES:
  - 外部: loguru
@RELATED: processor.py
"""

import random
import re
from typing import List

from loguru import logger


class TitleGenerator:
    """AI 标题生成器（基于SOP v2.0规则）.

    SOP要求（步骤4.1）：
    1. 提取5个原标题中的高频热搜词
    2. 生成5个新的中文标题
    3. **必须添加型号后缀**（如"A0001型号"）
    4. 可选添加修饰词（如"2025新款"）
    5. 不要出现医疗相关词汇
    6. 符合欧美阅读习惯
    7. 符合TEMU/亚马逊平台规则

    生成模式：
    1. placeholder - 占位符模式（MVP，标记为TEMU_AI）
    2. api - API模式（Phase 2实现）
    3. rule - 规则模式（保底方案）

    Attributes:
        mode: 生成模式 (placeholder|api|rule)

    Examples:
        >>> generator = TitleGenerator(mode="placeholder")
        >>> titles = generator.generate_with_model_suffix(
        ...     ["智能手表", "运动手表"],
        ...     model_prefix="A",
        ...     start_number=1
        ... )
        >>> "A0001型号" in titles[0]
        True
    """

    # SOP提示词模板
    PROMPT_TEMPLATE = """
提取上面{count}个商品标题中的高频热搜词，写{count}个新的中文标题，不要出现药品、急救等医疗相关的词汇
符合欧美人的阅读习惯，符合TEMU/亚马逊平台规则，提高搜索流量

原标题：
{titles}
"""

    # 可选修饰词库
    OPTIONAL_MODIFIERS = [
        "2025新款",
        "适用于多种场景",
        "节日必备",
        "热销款",
        "限时特惠",
        "高品质",
        "精选好物",
    ]

    def __init__(self, mode: str = "placeholder"):
        """初始化生成器.

        Args:
            mode: 生成模式 (placeholder|api|rule)
        """
        self.mode = mode
        logger.info(f"标题生成器初始化（SOP v2.0），模式: {mode}")

    def generate_with_model_suffix(
        self,
        original_titles: List[str],
        model_prefix: str = "A",
        start_number: int = 1,
        add_modifiers: bool = False,
    ) -> List[str]:
        """生成标题并添加型号后缀（SOP步骤4.1）.

        这是SOP要求的核心功能，必须添加型号后缀。

        Args:
            original_titles: 原始标题列表
            model_prefix: 型号前缀（默认"A"）
            start_number: 起始编号（默认1）
            add_modifiers: 是否添加可选修饰词

        Returns:
            带型号后缀的新标题列表

        Examples:
            >>> gen = TitleGenerator(mode="placeholder")
            >>> titles = gen.generate_with_model_suffix(
            ...     ["智能手表", "运动手表", "防水手表"],
            ...     model_prefix="A",
            ...     start_number=1,
            ...     add_modifiers=True
            ... )
            >>> len(titles)
            3
            >>> "A0001型号" in titles[0]
            True
        """
        logger.info(f"生成{len(original_titles)}个带型号的标题")

        # 1. 生成基础标题
        base_titles = self._generate_base_titles(original_titles)

        # 2. 添加型号后缀（必须）和可选修饰词
        result = []
        for i, title in enumerate(base_titles):
            model_number = f"{model_prefix}{start_number + i:04d}"

            # 构建完整标题
            if add_modifiers:
                modifier = random.choice(self.OPTIONAL_MODIFIERS)
                full_title = f"{title} {modifier} {model_number}型号"
            else:
                full_title = f"{title} {model_number}型号"

            result.append(full_title)
            logger.debug(f"  标题 {i + 1}: {full_title}")

        logger.success(f"生成完成，共{len(result)}个标题")
        return result

    def _generate_base_titles(self, original_titles: List[str]) -> List[str]:
        """生成基础标题（不含型号）.

        Args:
            original_titles: 原始标题列表

        Returns:
            新标题列表
        """
        if self.mode == "placeholder":
            # MVP模式：占位符，标记为需要Temu AI生成
            return [f"[TEMU_AI:{title}]" for title in original_titles]

        elif self.mode == "api":
            # API模式：调用实际AI服务
            return self._call_ai_service(original_titles)

        else:  # rule
            # 规则模式：基于规则生成
            return [self.generate_by_rule(title, title) for title in original_titles]

    def _call_ai_service(self, titles: List[str]) -> List[str]:
        """调用AI服务生成标题.

        Args:
            titles: 原始标题

        Returns:
            AI生成的新标题

        Note:
            Phase 2实现：接入GPT/Claude/Qwen等服务
        """
        # TODO: 接入实际AI API
        prompt = self.PROMPT_TEMPLATE.format(
            count=len(titles), titles="\n".join([f"{i + 1}. {t}" for i, t in enumerate(titles)])
        )
        # ai_response = call_ai_api(prompt)
        # return parse_ai_response(ai_response)

        logger.warning("AI模式尚未实现，使用placeholder模式")
        return [f"[TEMU_AI:{title}]" for title in titles]

    def get_prompt_preview(self, titles: List[str]) -> str:
        """预览AI提示词（用于调试）.

        Args:
            titles: 原始标题

        Returns:
            完整的提示词
        """
        return self.PROMPT_TEMPLATE.format(
            count=len(titles), titles="\n".join([f"{i + 1}. {t}" for i, t in enumerate(titles)])
        )

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
        """生成单个标题（主入口）.

        Note:
            推荐使用 generate_with_model_suffix() 批量生成带型号的标题。
            这个方法保留用于向后兼容。

        Args:
            product_name: 商品名称
            keyword: 关键词
            fallback: 失败时是否降级到规则生成

        Returns:
            生成的标题

        Examples:
            >>> gen = TitleGenerator(mode="placeholder")
            >>> title = gen.generate("智能手表", "手表")
            >>> "[TEMU_AI:" in title
            True
        """
        try:
            if self.mode == "placeholder":
                # Placeholder模式：标记为需要Temu AI生成
                logger.info("将使用Temu自带AI生成标题（Playwright执行）")
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
    print("=" * 60)
    print("标题生成器测试（SOP v2.0规则）")
    print("=" * 60)

    generator = TitleGenerator(mode="placeholder")

    # 测试1：批量生成带型号的标题（SOP要求）
    print("\n【测试1】批量生成带型号的标题（5条）：")
    original_titles = [
        "药箱收纳盒",
        "家用医药箱",
        "急救箱收纳",
        "医疗收纳盒",
        "药品整理箱",
    ]

    new_titles = generator.generate_with_model_suffix(
        original_titles, model_prefix="A", start_number=1, add_modifiers=True
    )

    print("\n原标题 → 新标题（带型号）：")
    for orig, new in zip(original_titles, new_titles):
        print(f"  {orig:15s} → {new}")

    # 测试2：不添加修饰词
    print("\n【测试2】生成标题（不添加修饰词）：")
    new_titles_simple = generator.generate_with_model_suffix(
        original_titles[:3], model_prefix="B", start_number=100, add_modifiers=False
    )

    for orig, new in zip(original_titles[:3], new_titles_simple):
        print(f"  {orig:15s} → {new}")

    # 测试3：AI提示词预览
    print("\n【测试3】AI提示词预览：")
    print(generator.get_prompt_preview(original_titles))

    # 测试4：单个生成（向后兼容）
    print("\n【测试4】单个生成（向后兼容）：")
    single_title = generator.generate("智能手表运动防水", "智能手表")
    print(f"  生成的标题: {single_title}")

    print("\n" + "=" * 60)
