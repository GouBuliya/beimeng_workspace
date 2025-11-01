"""
@PURPOSE: AI标题生成器，用于从5个原始标题生成5个优化的新标题
@OUTLINE:
  - class AITitleGenerator: AI标题生成主类
  - async def generate_titles(): 调用AI生成新标题
  - def _build_prompt(): 构建AI提示词
  - async def _call_openai_api(): 调用OpenAI API
  - async def _call_anthropic_api(): 调用Anthropic API
@GOTCHAS:
  - AI调用可能失败，需要实现fallback机制
  - 必须确保生成5个不同的标题
  - 型号后缀在AI生成后自动追加
@DEPENDENCIES:
  - 内部: config.settings, core.utils.retry_handler
  - 外部: openai, anthropic, loguru
@RELATED: first_edit_controller.py, five_to_twenty_workflow.py
"""

import asyncio
import os
from typing import List, Optional

from loguru import logger

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("openai 库未安装，OpenAI 功能不可用")

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("anthropic 库未安装，Anthropic 功能不可用")


class AITitleGenerator:
    """AI标题生成器.
    
    使用AI（OpenAI/Anthropic）从5个原始标题生成5个优化的新标题。
    
    Attributes:
        provider: AI提供商 ('openai' 或 'anthropic')
        api_key: API密钥
        model: 使用的模型名称
        max_retries: 最大重试次数
        
    Examples:
        >>> generator = AITitleGenerator(provider="openai")
        >>> original_titles = ["标题1", "标题2", "标题3", "标题4", "标题5"]
        >>> new_titles = await generator.generate_titles(original_titles, "A0049型号")
        >>> print(new_titles)
        ['新标题1 A0049型号', '新标题2 A0049型号', ...]
    """
    
    # 固定的AI提示词模板（批量模式 - 5个标题）
    PROMPT_TEMPLATE = """提取上面5个商品标题中的高频热搜词，写5个新的中文标题，
不要出现药品，急救等医疗相关的词汇
符合欧美人的阅读习惯，符合TEMU/亚马逊平台规则，提高搜索流量

原标题：
{titles}

请生成5个不同的新标题，每个标题独立且有差异。
每行一个标题，不要编号，不要其他说明文字。"""

    # 单个标题的AI提示词模板（逐个模式 - 1个标题）
    SINGLE_PROMPT_TEMPLATE = """请基于下面的商品标题，生成一个优化的新中文标题：

原标题：{title}

要求：
1. 提取标题中的高频热搜词
2. 生成一个新的中文标题（必须是中文，不要英文）
3. 如果原标题是英文，请翻译成中文
4. 不要出现药品、急救等医疗相关的词汇
5. 符合欧美人的阅读习惯
6. 符合TEMU/亚马逊平台规则
7. 优化搜索流量

重要：输出必须是中文标题，不要包含编号、说明文字。"""

    def __init__(
        self,
        provider: str = "openai",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 30
    ):
        """初始化AI标题生成器.
        
        Args:
            provider: AI提供商 ('openai' 或 'anthropic')
            api_key: API密钥（如果为None，从环境变量读取）
            model: 模型名称（如果为None，使用默认模型）
            base_url: API基础URL（支持OpenAI兼容接口，如通义千问）
            max_retries: 最大重试次数
            timeout: 超时时间（秒）
        """
        self.provider = provider.lower()
        self.max_retries = max_retries
        self.timeout = timeout
        
        # 获取API密钥（优先使用DASHSCOPE_API_KEY，兼容OPENAI_API_KEY）
        if api_key:
            self.api_key = api_key
        elif self.provider == "openai":
            # 优先使用阿里云DashScope的API Key
            self.api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY", "")
        elif self.provider == "anthropic":
            self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        else:
            self.api_key = ""
            
        # 设置默认模型
        if model:
            self.model = model
        elif self.provider == "openai":
            self.model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        elif self.provider == "anthropic":
            self.model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
        else:
            self.model = ""
            
        # 设置base_url（支持OpenAI兼容接口）
        if base_url:
            self.base_url = base_url
        else:
            self.base_url = os.getenv("OPENAI_BASE_URL", None)
            
        if self.base_url:
            logger.info(f"AI标题生成器初始化: provider={self.provider}, model={self.model}, base_url={self.base_url}")
        else:
            logger.info(f"AI标题生成器初始化: provider={self.provider}, model={self.model}")
        
    def _build_prompt(self, original_titles: List[str]) -> str:
        """构建AI提示词.
        
        Args:
            original_titles: 5个原始标题列表
            
        Returns:
            完整的提示词
        """
        # 格式化标题列表
        titles_text = "\n".join([f"{i+1}. {title}" for i, title in enumerate(original_titles)])
        
        # 构建完整提示词
        prompt = self.PROMPT_TEMPLATE.format(titles=titles_text)
        
        return prompt
    
    async def _call_openai_api(self, prompt: str) -> List[str]:
        """调用OpenAI API生成标题.
        
        Args:
            prompt: 提示词
            
        Returns:
            生成的5个标题列表
            
        Raises:
            Exception: API调用失败
        """
        if not OPENAI_AVAILABLE:
            raise Exception("openai 库未安装")
            
        if not self.api_key:
            raise Exception("OpenAI API密钥未配置")
            
        logger.debug(f"调用OpenAI API: model={self.model}")
        
        try:
            # 创建客户端，支持自定义base_url（OpenAI兼容接口）
            client_params = {
                "api_key": self.api_key,
                "timeout": self.timeout
            }
            if self.base_url:
                client_params["base_url"] = self.base_url
                logger.debug(f"使用自定义base_url: {self.base_url}")
            
            client = openai.AsyncOpenAI(**client_params)
            
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的电商产品标题优化专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            # 解析响应
            content = response.choices[0].message.content.strip()
            
            # 按行分割，获取5个标题
            titles = [line.strip() for line in content.split('\n') if line.strip()]
            
            # 去除可能的编号（如：1. 、一、等）
            cleaned_titles = []
            for title in titles:
                # 去除开头的数字、点、空格
                import re
                cleaned = re.sub(r'^\d+[\.\)、]\s*', '', title)
                cleaned = re.sub(r'^[一二三四五]\s*[、．.]\s*', '', cleaned)
                if cleaned:
                    cleaned_titles.append(cleaned)
            
            if len(cleaned_titles) < 5:
                logger.warning(f"AI生成的标题数量不足: {len(cleaned_titles)}/5")
                # 用第一个标题补齐
                while len(cleaned_titles) < 5:
                    cleaned_titles.append(cleaned_titles[0] if cleaned_titles else "产品标题")
                    
            return cleaned_titles[:5]  # 只返回前5个
            
        except Exception as e:
            logger.error(f"OpenAI API调用失败: {e}")
            raise
    
    async def _call_anthropic_api(self, prompt: str) -> List[str]:
        """调用Anthropic API生成标题.
        
        Args:
            prompt: 提示词
            
        Returns:
            生成的5个标题列表
            
        Raises:
            Exception: API调用失败
        """
        if not ANTHROPIC_AVAILABLE:
            raise Exception("anthropic 库未安装")
            
        if not self.api_key:
            raise Exception("Anthropic API密钥未配置")
            
        logger.debug(f"调用Anthropic API: model={self.model}")
        
        try:
            client = anthropic.AsyncAnthropic(
                api_key=self.api_key,
                timeout=self.timeout
            )
            
            response = await client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # 解析响应
            content = response.content[0].text.strip()
            
            # 按行分割，获取5个标题
            titles = [line.strip() for line in content.split('\n') if line.strip()]
            
            # 去除可能的编号
            cleaned_titles = []
            for title in titles:
                import re
                cleaned = re.sub(r'^\d+[\.\)、]\s*', '', title)
                cleaned = re.sub(r'^[一二三四五]\s*[、．.]\s*', '', cleaned)
                if cleaned:
                    cleaned_titles.append(cleaned)
            
            if len(cleaned_titles) < 5:
                logger.warning(f"AI生成的标题数量不足: {len(cleaned_titles)}/5")
                while len(cleaned_titles) < 5:
                    cleaned_titles.append(cleaned_titles[0] if cleaned_titles else "产品标题")
                    
            return cleaned_titles[:5]
            
        except Exception as e:
            logger.error(f"Anthropic API调用失败: {e}")
            raise
    
    async def generate_titles(
        self,
        original_titles: List[str],
        model_number: str = "",
        use_ai: bool = True
    ) -> List[str]:
        """生成5个新标题.
        
        从5个原始标题中提取关键词，生成5个优化的新标题，并自动添加型号后缀。
        
        Args:
            original_titles: 5个原始标题列表
            model_number: 型号后缀（如：A0049型号）
            use_ai: 是否使用AI生成（False则返回原标题+型号）
            
        Returns:
            5个新生成的标题（已包含型号后缀）
            
        Examples:
            >>> generator = AITitleGenerator()
            >>> titles = await generator.generate_titles(
            ...     ["标题1", "标题2", "标题3", "标题4", "标题5"],
            ...     "A0049型号"
            ... )
        """
        logger.info(f"开始生成标题: use_ai={use_ai}, model_number={model_number}")
        
        # 验证输入
        if len(original_titles) != 5:
            logger.warning(f"原始标题数量不是5个: {len(original_titles)}")
            # 补齐或截断到5个
            if len(original_titles) < 5:
                original_titles = original_titles + ["产品标题"] * (5 - len(original_titles))
            else:
                original_titles = original_titles[:5]
        
        # 如果不使用AI，直接返回原标题+型号
        if not use_ai:
            logger.info("未启用AI，直接使用原标题")
            result = []
            for title in original_titles:
                if model_number:
                    result.append(f"{title} {model_number}")
                else:
                    result.append(title)
            return result
        
        # 使用AI生成标题（带重试）
        new_titles = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"AI生成尝试 {attempt+1}/{self.max_retries}")
                
                # 构建提示词
                prompt = self._build_prompt(original_titles)
                
                # 调用对应的API
                if self.provider == "openai":
                    new_titles = await self._call_openai_api(prompt)
                elif self.provider == "anthropic":
                    new_titles = await self._call_anthropic_api(prompt)
                else:
                    raise Exception(f"不支持的AI提供商: {self.provider}")
                
                logger.success(f"✓ AI生成标题成功")
                break
                
            except Exception as e:
                logger.warning(f"AI生成失败（尝试 {attempt+1}/{self.max_retries}）: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                else:
                    logger.error("AI生成失败，使用降级方案")
        
        # 如果AI生成失败，使用降级方案
        if not new_titles:
            logger.warning("⚠️ AI生成失败，使用原标题作为降级方案")
            new_titles = original_titles
        
        # 为每个标题添加型号后缀
        result = []
        for i, title in enumerate(new_titles):
            if model_number:
                # 确保型号后缀不重复
                if model_number not in title:
                    result.append(f"{title} {model_number}")
                else:
                    result.append(title)
            else:
                result.append(title)
        
        logger.info(f"标题生成完成: {len(result)} 个")
        for i, title in enumerate(result):
            logger.debug(f"  {i+1}. {title}")
        
        return result
    
    async def generate_single_title(
        self,
        original_title: str,
        model_number: str = "",
        use_ai: bool = True
    ) -> str:
        """生成单个新标题（逐个模式）.
        
        为单个产品生成优化的标题。每次调用都是独立的AI对话。
        
        Args:
            original_title: 单个原始标题
            model_number: 型号后缀（如：A0001型号）
            use_ai: 是否使用AI生成（False则返回原标题+型号）
            
        Returns:
            新生成的标题（已包含型号后缀）
            
        Examples:
            >>> generator = AITitleGenerator()
            >>> new_title = await generator.generate_single_title(
            ...     "便携药箱家用急救包",
            ...     "A0001型号"
            ... )
            >>> print(new_title)
            '便携收纳盒家用医疗包 A0001型号'
        """
        logger.info(f"开始生成单个标题: use_ai={use_ai}, model_number={model_number}")
        logger.debug(f"原始标题: {original_title}")
        
        # 如果不使用AI，直接返回原标题+型号
        if not use_ai:
            logger.info("未启用AI，直接使用原标题")
            if model_number:
                return f"{original_title} {model_number}"
            else:
                return original_title
        
        # 使用AI生成标题（带重试）
        new_title = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"AI生成尝试 {attempt+1}/{self.max_retries}")
                
                # 构建单个标题的提示词
                prompt = self.SINGLE_PROMPT_TEMPLATE.format(title=original_title)
                logger.debug(f"Prompt: {prompt[:100]}...")
                
                # 调用对应的API
                if self.provider == "openai":
                    # 调用OpenAI API，返回单个标题
                    result_list = await self._call_openai_api(prompt)
                    # 取第一个结果
                    new_title = result_list[0] if result_list else original_title
                elif self.provider == "anthropic":
                    # 调用Anthropic API，返回单个标题
                    result_list = await self._call_anthropic_api(prompt)
                    # 取第一个结果
                    new_title = result_list[0] if result_list else original_title
                else:
                    raise Exception(f"不支持的AI提供商: {self.provider}")
                
                logger.success(f"✓ AI生成标题成功: {new_title}")
                break
                
            except Exception as e:
                logger.warning(f"AI生成失败（尝试 {attempt+1}/{self.max_retries}）: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                else:
                    logger.error("AI生成失败，使用降级方案（原标题）")
        
        # 如果AI生成失败，使用降级方案
        if not new_title:
            logger.warning("⚠️ AI生成失败，使用原标题作为降级方案")
            new_title = original_title
        
        # 添加型号后缀
        if model_number:
            # 确保型号后缀不重复
            if model_number not in new_title:
                result = f"{new_title} {model_number}"
            else:
                result = new_title
        else:
            result = new_title
        
        logger.info(f"单个标题生成完成: {result}")
        
        return result


# 便捷函数
async def generate_titles_simple(
    original_titles: List[str],
    model_number: str = "",
    provider: str = "openai"
) -> List[str]:
    """简化的标题生成函数.
    
    Args:
        original_titles: 5个原始标题
        model_number: 型号后缀
        provider: AI提供商
        
    Returns:
        5个新标题
    """
    generator = AITitleGenerator(provider=provider)
    return await generator.generate_titles(original_titles, model_number)

