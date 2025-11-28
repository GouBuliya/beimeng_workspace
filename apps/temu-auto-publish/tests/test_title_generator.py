"""
@PURPOSE: 测试 TitleGenerator 标题生成器
@OUTLINE:
  - TestTitleGenerator: 测试标题生成器主类
  - TestTitleGeneratorModes: 测试不同生成模式
  - TestTitleGeneratorModelSuffix: 测试型号后缀生成
  - TestTitleGeneratorRules: 测试规则生成
@DEPENDENCIES:
  - 外部: pytest
  - 内部: src.data_processor.title_generator
"""

import pytest

from src.data_processor.title_generator import TitleGenerator


class TestTitleGenerator:
    """测试标题生成器主类"""
    
    def test_init_default_mode(self):
        """测试默认模式初始化"""
        generator = TitleGenerator()
        
        assert generator.mode == "placeholder"
    
    def test_init_custom_mode(self):
        """测试自定义模式初始化"""
        generator = TitleGenerator(mode="rule")
        
        assert generator.mode == "rule"
    
    def test_init_api_mode(self):
        """测试API模式初始化"""
        generator = TitleGenerator(mode="api")
        
        assert generator.mode == "api"
    
    def test_optional_modifiers_exist(self):
        """测试可选修饰词存在"""
        assert TitleGenerator.OPTIONAL_MODIFIERS is not None
        assert len(TitleGenerator.OPTIONAL_MODIFIERS) > 0
    
    def test_prompt_template_exist(self):
        """测试提示词模板存在"""
        assert TitleGenerator.PROMPT_TEMPLATE is not None
        assert "{count}" in TitleGenerator.PROMPT_TEMPLATE
        assert "{titles}" in TitleGenerator.PROMPT_TEMPLATE


class TestTitleGeneratorModes:
    """测试不同生成模式"""
    
    def test_placeholder_mode_generate(self):
        """测试占位符模式生成"""
        generator = TitleGenerator(mode="placeholder")
        
        title = generator.generate("智能手表", "手表")
        
        assert "[TEMU_AI:" in title
        assert "手表" in title
    
    def test_rule_mode_generate(self):
        """测试规则模式生成"""
        generator = TitleGenerator(mode="rule")
        
        title = generator.generate("智能手表运动防水", "智能手表")
        
        assert len(title) > 0
        assert "智能手表" in title
    
    def test_api_mode_fallback(self):
        """测试API模式回退"""
        generator = TitleGenerator(mode="api")
        
        # API未实现，应该回退
        title = generator.generate("智能手表", "手表")
        
        assert len(title) > 0


class TestTitleGeneratorModelSuffix:
    """测试型号后缀生成"""
    
    def test_generate_with_model_suffix_basic(self):
        """测试基本型号后缀生成"""
        generator = TitleGenerator(mode="placeholder")
        
        titles = generator.generate_with_model_suffix(
            ["药箱收纳盒", "厨房收纳架"],
            model_prefix="A",
            start_number=1
        )
        
        assert len(titles) == 2
        assert "A0001型号" in titles[0]
        assert "A0002型号" in titles[1]
    
    def test_generate_with_model_suffix_custom_prefix(self):
        """测试自定义前缀"""
        generator = TitleGenerator(mode="placeholder")
        
        titles = generator.generate_with_model_suffix(
            ["测试产品"],
            model_prefix="B",
            start_number=100
        )
        
        assert "B0100型号" in titles[0]
    
    def test_generate_with_model_suffix_with_modifiers(self):
        """测试带修饰词生成"""
        generator = TitleGenerator(mode="placeholder")
        
        titles = generator.generate_with_model_suffix(
            ["测试产品"],
            model_prefix="A",
            start_number=1,
            add_modifiers=True
        )
        
        assert "A0001型号" in titles[0]
        # 应该包含修饰词
        has_modifier = any(
            mod in titles[0] 
            for mod in TitleGenerator.OPTIONAL_MODIFIERS
        )
        assert has_modifier
    
    def test_generate_with_model_suffix_without_modifiers(self):
        """测试不带修饰词生成"""
        generator = TitleGenerator(mode="placeholder")
        
        titles = generator.generate_with_model_suffix(
            ["测试产品"],
            model_prefix="A",
            start_number=1,
            add_modifiers=False
        )
        
        # 不应该包含修饰词（大部分情况）
        assert "A0001型号" in titles[0]
    
    def test_generate_with_model_suffix_multiple_products(self):
        """测试多产品生成"""
        generator = TitleGenerator(mode="placeholder")
        
        original = [f"产品{i}" for i in range(5)]
        titles = generator.generate_with_model_suffix(
            original,
            model_prefix="A",
            start_number=10
        )
        
        assert len(titles) == 5
        assert "A0010型号" in titles[0]
        assert "A0011型号" in titles[1]
        assert "A0014型号" in titles[4]
    
    def test_generate_with_model_suffix_numbering(self):
        """测试编号格式"""
        generator = TitleGenerator(mode="placeholder")
        
        titles = generator.generate_with_model_suffix(
            ["产品"],
            model_prefix="A",
            start_number=9999
        )
        
        assert "A9999型号" in titles[0]


class TestTitleGeneratorRules:
    """测试规则生成"""
    
    def test_generate_by_rule_basic(self):
        """测试基本规则生成"""
        generator = TitleGenerator(mode="rule")
        
        title = generator.generate_by_rule("智能手表运动防水", "智能手表")
        
        assert "智能手表" in title
        assert len(title) > 0
    
    def test_generate_by_rule_length_limit(self):
        """测试规则生成长度限制"""
        generator = TitleGenerator(mode="rule")
        
        # 超长输入
        long_name = "这是一个非常长的产品名称" * 20
        title = generator.generate_by_rule(long_name, "关键词")
        
        assert len(title) <= 80
    
    def test_generate_by_rule_special_characters(self):
        """测试特殊字符处理"""
        generator = TitleGenerator(mode="rule")
        
        title = generator.generate_by_rule("产品【特殊】名称", "关键词")
        
        # 应该清理特殊字符
        assert len(title) > 0
    
    def test_generate_by_rule_modifiers(self):
        """测试规则生成包含修饰语"""
        generator = TitleGenerator(mode="rule")
        
        title = generator.generate_by_rule("测试产品", "测试")
        
        # 应该包含修饰语
        assert "【" in title


class TestTitleGeneratorPrompt:
    """测试提示词生成"""
    
    def test_get_prompt_preview(self):
        """测试获取提示词预览"""
        generator = TitleGenerator()
        
        titles = ["标题1", "标题2", "标题3"]
        prompt = generator.get_prompt_preview(titles)
        
        assert "3" in prompt  # count
        assert "标题1" in prompt
        assert "标题2" in prompt
        assert "标题3" in prompt
    
    def test_get_prompt_preview_format(self):
        """测试提示词格式"""
        generator = TitleGenerator()
        
        titles = ["药箱收纳盒"]
        prompt = generator.get_prompt_preview(titles)
        
        assert "高频热搜词" in prompt
        assert "中文标题" in prompt
        assert "TEMU" in prompt or "亚马逊" in prompt


class TestTitleGeneratorFallback:
    """测试回退机制"""
    
    def test_generate_with_fallback_enabled(self):
        """测试启用回退"""
        generator = TitleGenerator(mode="api")
        
        # API模式应该自动回退
        title = generator.generate("测试产品", "测试", fallback=True)
        
        assert len(title) > 0
    
    def test_generate_api_falls_back_to_placeholder(self):
        """测试API模式回退到规则"""
        generator = TitleGenerator(mode="api")
        
        title = generator.generate_by_api("测试产品", "测试")
        
        # 由于API未实现，应该返回规则生成的结果
        assert len(title) > 0


class TestTitleGeneratorEdgeCases:
    """测试边界情况"""
    
    def test_empty_original_titles(self):
        """测试空原始标题列表"""
        generator = TitleGenerator(mode="placeholder")
        
        titles = generator.generate_with_model_suffix(
            [],
            model_prefix="A",
            start_number=1
        )
        
        assert len(titles) == 0
    
    def test_single_original_title(self):
        """测试单个原始标题"""
        generator = TitleGenerator(mode="placeholder")
        
        titles = generator.generate_with_model_suffix(
            ["唯一产品"],
            model_prefix="A",
            start_number=1
        )
        
        assert len(titles) == 1
        assert "A0001型号" in titles[0]
    
    def test_unicode_in_titles(self):
        """测试Unicode字符"""
        generator = TitleGenerator(mode="placeholder")
        
        titles = generator.generate_with_model_suffix(
            ["测试产品 ™"],
            model_prefix="A",
            start_number=1
        )
        
        assert len(titles) == 1
    
    def test_whitespace_handling(self):
        """测试空白字符处理"""
        generator = TitleGenerator(mode="rule")
        
        title = generator.generate_by_rule("  产品名称  ", "  关键词  ")
        
        # 应该正常处理
        assert len(title) > 0
    
    def test_empty_product_name(self):
        """测试空产品名"""
        generator = TitleGenerator(mode="rule")
        
        title = generator.generate_by_rule("", "关键词")
        
        # 应该至少包含关键词
        assert "关键词" in title





