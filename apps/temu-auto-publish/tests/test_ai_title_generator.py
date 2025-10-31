"""
@PURPOSE: AI标题生成器的单元测试
@OUTLINE:
  - test_ai_title_generator_init(): 测试初始化
  - test_build_prompt(): 测试提示词构建
  - test_generate_titles_simple(): 测试简单标题生成
  - test_generate_titles_fallback(): 测试降级策略
@DEPENDENCIES:
  - 内部: src.data_processor.ai_title_generator
  - 外部: pytest, pytest-asyncio
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.data_processor.ai_title_generator import AITitleGenerator, generate_titles_simple


class TestAITitleGenerator:
    """AI标题生成器测试套件."""
    
    def test_init_default(self):
        """测试默认初始化."""
        generator = AITitleGenerator()
        assert generator.provider == "openai"
        assert generator.max_retries == 3
        assert generator.timeout == 30
    
    def test_init_custom(self):
        """测试自定义初始化."""
        generator = AITitleGenerator(
            provider="anthropic",
            api_key="test-key",
            model="claude-3-haiku-20240307",
            max_retries=5,
            timeout=60
        )
        assert generator.provider == "anthropic"
        assert generator.api_key == "test-key"
        assert generator.model == "claude-3-haiku-20240307"
        assert generator.max_retries == 5
        assert generator.timeout == 60
    
    def test_build_prompt(self):
        """测试提示词构建."""
        generator = AITitleGenerator()
        original_titles = [
            "便携药箱家用急救包医疗收纳盒",
            "家庭药品收纳盒大容量医药箱",
            "医用急救箱车载药品盒",
            "便携式家用医疗箱急救包",
            "大容量药品收纳盒家庭医药箱"
        ]
        
        prompt = generator._build_prompt(original_titles)
        
        # 验证提示词包含所有标题
        for i, title in enumerate(original_titles):
            assert f"{i+1}. {title}" in prompt
        
        # 验证提示词包含关键要求
        assert "高频热搜词" in prompt
        assert "5个新的中文标题" in prompt
        assert "不要出现药品，急救等医疗相关的词汇" in prompt
        assert "符合欧美人的阅读习惯" in prompt
    
    @pytest.mark.asyncio
    async def test_generate_titles_without_ai(self):
        """测试不使用AI生成标题."""
        generator = AITitleGenerator()
        original_titles = ["标题1", "标题2", "标题3", "标题4", "标题5"]
        model_number = "A0049型号"
        
        new_titles = await generator.generate_titles(
            original_titles,
            model_number=model_number,
            use_ai=False
        )
        
        assert len(new_titles) == 5
        for i, title in enumerate(new_titles):
            assert original_titles[i] in title
            assert model_number in title
    
    @pytest.mark.asyncio
    async def test_generate_titles_with_fallback(self):
        """测试AI失败时的降级策略."""
        generator = AITitleGenerator()
        generator.max_retries = 1  # 减少重试次数加快测试
        
        # Mock失败的AI调用
        with patch.object(generator, '_call_openai_api', side_effect=Exception("API Error")):
            original_titles = ["标题1", "标题2", "标题3", "标题4", "标题5"]
            model_number = "A0049型号"
            
            new_titles = await generator.generate_titles(
                original_titles,
                model_number=model_number,
                use_ai=True
            )
            
            # 应该返回降级标题（原标题+型号）
            assert len(new_titles) == 5
            for i, title in enumerate(new_titles):
                assert original_titles[i] in title
                assert model_number in title
    
    @pytest.mark.asyncio
    async def test_generate_titles_insufficient_count(self):
        """测试原始标题数量不足的情况."""
        generator = AITitleGenerator()
        original_titles = ["标题1", "标题2"]  # 只有2个
        model_number = "A0049型号"
        
        new_titles = await generator.generate_titles(
            original_titles,
            model_number=model_number,
            use_ai=False
        )
        
        # 应该补齐到5个
        assert len(new_titles) == 5
    
    @pytest.mark.asyncio
    async def test_generate_titles_excess_count(self):
        """测试原始标题数量超出的情况."""
        generator = AITitleGenerator()
        original_titles = ["标题1", "标题2", "标题3", "标题4", "标题5", "标题6", "标题7"]  # 7个
        model_number = "A0049型号"
        
        new_titles = await generator.generate_titles(
            original_titles,
            model_number=model_number,
            use_ai=False
        )
        
        # 应该截断到5个
        assert len(new_titles) == 5
    
    @pytest.mark.asyncio
    async def test_model_number_deduplication(self):
        """测试型号后缀不重复添加."""
        generator = AITitleGenerator()
        model_number = "A0049型号"
        # 原标题已经包含型号
        original_titles = [f"标题{i} {model_number}" for i in range(1, 6)]
        
        new_titles = await generator.generate_titles(
            original_titles,
            model_number=model_number,
            use_ai=False
        )
        
        for title in new_titles:
            # 确保型号只出现一次
            assert title.count(model_number) == 1


class TestAITitleGeneratorIntegration:
    """AI标题生成器集成测试（需要真实API密钥）."""
    
    @pytest.mark.skip(reason="需要真实API密钥，手动测试")
    @pytest.mark.asyncio
    async def test_real_openai_call(self):
        """使用真实OpenAI API测试."""
        generator = AITitleGenerator(provider="openai")
        original_titles = [
            "便携药箱家用急救包医疗收纳盒",
            "家庭药品收纳盒大容量医药箱",
            "医用急救箱车载药品盒",
            "便携式家用医疗箱急救包",
            "大容量药品收纳盒家庭医药箱"
        ]
        
        new_titles = await generator.generate_titles(
            original_titles,
            model_number="A0049型号",
            use_ai=True
        )
        
        assert len(new_titles) == 5
        for title in new_titles:
            # 验证不包含违禁词
            assert "药品" not in title
            assert "急救" not in title
            assert "医疗" not in title
            # 验证包含型号
            assert "A0049型号" in title
        
        print("\n生成的标题：")
        for i, title in enumerate(new_titles):
            print(f"{i+1}. {title}")
    
    @pytest.mark.skip(reason="需要真实API密钥，手动测试")
    @pytest.mark.asyncio
    async def test_real_anthropic_call(self):
        """使用真实Anthropic API测试."""
        generator = AITitleGenerator(provider="anthropic")
        original_titles = [
            "便携药箱家用急救包医疗收纳盒",
            "家庭药品收纳盒大容量医药箱",
            "医用急救箱车载药品盒",
            "便携式家用医疗箱急救包",
            "大容量药品收纳盒家庭医药箱"
        ]
        
        new_titles = await generator.generate_titles(
            original_titles,
            model_number="A0050型号",
            use_ai=True
        )
        
        assert len(new_titles) == 5
        for title in new_titles:
            # 验证不包含违禁词
            assert "药品" not in title
            assert "急救" not in title
            assert "医疗" not in title
            # 验证包含型号
            assert "A0050型号" in title
        
        print("\n生成的标题：")
        for i, title in enumerate(new_titles):
            print(f"{i+1}. {title}")


def test_generate_titles_simple_function():
    """测试便捷函数."""
    original_titles = ["标题1", "标题2", "标题3", "标题4", "标题5"]
    model_number = "A0049型号"
    
    # 由于是async函数，需要在事件循环中运行
    result = asyncio.run(generate_titles_simple(
        original_titles,
        model_number=model_number,
        provider="openai"
    ))
    
    assert len(result) == 5


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s"])

