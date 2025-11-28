"""
@PURPOSE: AI标题生成器的单元测试
@OUTLINE:
  - TestAITitleGenerator: 基础测试
    - test_init_default: 测试默认初始化
    - test_init_custom: 测试自定义初始化
    - test_build_prompt: 测试提示词构建
    - test_generate_titles_without_ai: 测试不使用AI
    - test_generate_titles_with_mock_api: 测试Mock API调用
  - TestAITitleGeneratorMocked: Mock API 测试
  - TestAITitleGeneratorIntegration: 集成测试
@DEPENDENCIES:
  - 内部: src.data_processor.ai_title_generator
  - 外部: pytest, pytest-asyncio
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from dataclasses import dataclass

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
    
    def test_init_with_base_url(self):
        """测试自定义base_url（兼容接口）"""
        generator = AITitleGenerator(
            provider="openai",
            api_key="test-key",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        assert generator.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    def test_init_unsupported_provider(self):
        """测试不支持的提供商"""
        generator = AITitleGenerator(provider="unknown")
        assert generator.provider == "unknown"
        assert generator.api_key == ""
    
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


class TestAITitleGeneratorMocked:
    """使用 Mock 的 AI 标题生成器测试"""
    
    @pytest.mark.asyncio
    async def test_generate_titles_with_mocked_openai(self):
        """测试使用 Mock OpenAI API 生成标题"""
        generator = AITitleGenerator(provider="openai", api_key="test-key")
        
        # Mock OpenAI API 响应
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """便携收纳盒家用整理箱
大容量收纳盒多功能整理包
家用便携式收纳箱储物盒
多功能收纳整理盒便携款
大容量家用收纳包整理箱"""
        
        with patch('openai.AsyncOpenAI') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            original_titles = ["标题1", "标题2", "标题3", "标题4", "标题5"]
            new_titles = await generator.generate_titles(
                original_titles,
                model_number="A0001型号",
                use_ai=True
            )
            
            assert len(new_titles) == 5
            for title in new_titles:
                assert "A0001型号" in title
    
    @pytest.mark.asyncio
    async def test_generate_single_title_without_ai(self):
        """测试不使用AI生成单个标题"""
        generator = AITitleGenerator()
        
        result = await generator.generate_single_title(
            "便携药箱家用急救包",
            model_number="A0001型号",
            use_ai=False
        )
        
        assert "便携药箱家用急救包" in result
        assert "A0001型号" in result
    
    @pytest.mark.asyncio
    async def test_generate_single_title_fallback(self):
        """测试单个标题生成的降级策略"""
        generator = AITitleGenerator(api_key="test-key")
        generator.max_retries = 1
        
        with patch.object(generator, '_call_openai_api', side_effect=Exception("API Error")):
            result = await generator.generate_single_title(
                "原始标题",
                model_number="型号001",
                use_ai=True
            )
            
            # 降级返回原标题+型号
            assert "原始标题" in result
            assert "型号001" in result
    
    @pytest.mark.asyncio
    async def test_api_response_parsing(self):
        """测试API响应解析（去除编号）"""
        generator = AITitleGenerator(provider="openai", api_key="test-key")
        
        # 模拟带编号的响应
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """1. 收纳盒标题一
2. 收纳盒标题二
3. 收纳盒标题三
4. 收纳盒标题四
5. 收纳盒标题五"""
        
        with patch('openai.AsyncOpenAI') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            original_titles = ["标题1", "标题2", "标题3", "标题4", "标题5"]
            new_titles = await generator.generate_titles(
                original_titles,
                model_number="",
                use_ai=True
            )
            
            assert len(new_titles) == 5
            # 验证编号被正确去除
            for title in new_titles:
                assert not title.startswith("1.")
                assert not title.startswith("2.")
    
    @pytest.mark.asyncio
    async def test_insufficient_api_response(self):
        """测试API返回标题数量不足的情况"""
        generator = AITitleGenerator(provider="openai", api_key="test-key")
        
        # 模拟只返回3个标题的响应
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """收纳盒标题一
收纳盒标题二
收纳盒标题三"""
        
        with patch('openai.AsyncOpenAI') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            original_titles = ["标题1", "标题2", "标题3", "标题4", "标题5"]
            new_titles = await generator.generate_titles(
                original_titles,
                model_number="",
                use_ai=True
            )
            
            # 应该自动补齐到5个
            assert len(new_titles) == 5


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

