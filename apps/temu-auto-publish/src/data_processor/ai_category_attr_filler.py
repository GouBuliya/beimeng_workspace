"""
@PURPOSE: AI 智能类目属性补全，根据商品信息推断必填属性值
@OUTLINE:
  - class CategoryAttrCache: 类目属性规则 LRU 缓存
  - class CategoryAttrRule: 类目属性规则数据类
  - class ProductAttrContext: 产品属性推断上下文
  - class AICategoryAttrFiller: AI 属性补全主类
    - async def fill_required_attrs(): 主入口，补全产品的必填属性
    - async def fill_batch_attrs(): 批量处理多个产品
    - async def _get_required_attrs(): 获取必填属性规则
    - async def _infer_attr_values(): LLM 推断属性值
    - def _validate_attr_values(): 验证属性值
    - def _build_prompt(): 构建 LLM 提示词
@GOTCHAS:
  - LLM 返回的值必须在可选范围内，否则需要降级处理
  - 相同类目的属性规则应缓存，避免重复 API 调用
  - 批量处理时可合并相同类目的推断请求
@DEPENDENCIES:
  - 内部: ..browser.miaoshou.api_client.MiaoshouApiClient
  - 外部: openai, loguru
@RELATED: ai_title_generator.py, batch_edit_api.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from ..browser.miaoshou.api_client import MiaoshouApiClient

# 检查 openai 库是否可用
try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("openai 库未安装，AI 属性补全功能不可用")


@dataclass
class CategoryAttrRule:
    """类目属性规则."""

    attr_id: str
    attr_name: str
    is_required: bool
    input_type: str  # select, input, multi_select
    attr_values: list[dict[str, str]] = field(default_factory=list)


@dataclass
class ProductAttrContext:
    """产品属性推断上下文."""

    detail_id: str
    title: str
    cid: str
    breadcrumb: str = ""
    existing_attrs: list[dict[str, str]] = field(default_factory=list)


class CategoryAttrCache:
    """类目属性规则 LRU 缓存."""

    def __init__(self, max_size: int = 100):
        """初始化缓存.

        Args:
            max_size: 最大缓存条目数
        """
        self._cache: dict[str, list[CategoryAttrRule]] = {}
        self._max_size = max_size

    def get(self, cid: str) -> list[CategoryAttrRule] | None:
        """获取缓存的属性规则."""
        return self._cache.get(cid)

    def set(self, cid: str, rules: list[CategoryAttrRule]) -> None:
        """设置缓存."""
        if len(self._cache) >= self._max_size:
            # LRU: 移除最早的条目
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[cid] = rules

    def clear(self) -> None:
        """清空缓存."""
        self._cache.clear()


class AICategoryAttrFiller:
    """AI 类目属性智能补全.

    根据商品标题、类目等信息，使用 LLM 推断必填属性的值。
    使用阿里云百炼 API（qwen-flash 模型）。

    Attributes:
        api_client: 妙手 API 客户端
        model: 使用的模型名称
        cache: 类目属性规则缓存

    Examples:
        >>> filler = AICategoryAttrFiller(api_client)
        >>> attrs = await filler.fill_required_attrs(
        ...     detail_id="123",
        ...     title="便携药箱收纳盒家用",
        ...     cid="6625",
        ...     breadcrumb="工业和科学>商业清洁>垃圾桶"
        ... )
        >>> print(attrs)
        [{"attrName": "材质", "attrValue": "塑料"}]
    """

    # 阿里云百炼 API 配置
    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DEFAULT_MODEL = "qwen-flash"

    # LLM 提示词模板
    PROMPT_TEMPLATE = """根据商品标题为以下属性选择最合适的值。

商品: {title}
类目: {breadcrumb}

属性列表：
{attributes_list}

规则：
- 有可选项的属性：必须从选项中选择原文，禁止编造
- 自由输入的数字属性（如重量、高度、容量）：填写合理数值，如"5kg"、"30cm"、"10L"
- 不确定时：有选项选第一个，数字填常见值
- 木材类型、木种等不相关属性：选第一个选项
- 电源方式若商品不带电：选"不带电"
- 插头规格、工作电压等其他电气属性：即使不带电也要选第一个选项，不要填"不带电"

返回JSON数组：
[{{"attrName":"属性名","attrValue":"值"}}]"""

    def __init__(
        self,
        api_client: MiaoshouApiClient,
        api_key: str | None = None,
        model: str | None = None,
        max_retries: int = 1,
        timeout: int = 30,
    ):
        """初始化 AI 属性补全器.

        Args:
            api_client: 妙手 API 客户端，用于获取类目属性规则
            api_key: 百炼 API 密钥（默认从 DASHSCOPE_API_KEY 环境变量读取）
            model: 模型名称（默认 qwen-flash）
            max_retries: 最大重试次数
            timeout: API 调用超时时间（秒）
        """
        self.api_client = api_client
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY", "")
        self.model = model or self.DEFAULT_MODEL
        self.max_retries = max_retries
        self.timeout = timeout
        self.cache = CategoryAttrCache()

        if not self.api_key:
            logger.warning("未设置 DASHSCOPE_API_KEY，AI 属性补全将使用降级方案")

        logger.info(f"AI 属性补全器初始化: model={self.model}")

    async def fill_required_attrs(
        self,
        detail_id: str,
        title: str,
        cid: str,
        breadcrumb: str = "",
        existing_attrs: list[dict[str, str]] | None = None,
    ) -> list[dict[str, str]]:
        """补全产品的必填类目属性.

        Args:
            detail_id: 产品 ID
            title: 产品标题
            cid: 类目 ID
            breadcrumb: 类目面包屑路径
            existing_attrs: 已有的属性列表

        Returns:
            补全后的属性列表，格式为 [{"attrName": "...", "attrValue": "..."}]
        """
        logger.info(f"[{detail_id}] 开始 AI 属性补全: cid={cid}")

        # 获取必填属性规则
        required_rules = await self._get_required_attrs(cid)
        if not required_rules:
            logger.info(f"[{detail_id}] 类目 {cid} 无必填属性")
            return existing_attrs or []

        # 检查哪些必填属性缺失
        existing_names = {a.get("attrName") for a in (existing_attrs or [])}
        missing_rules = [r for r in required_rules if r.attr_name not in existing_names]

        if not missing_rules:
            logger.info(f"[{detail_id}] 所有必填属性已填写")
            return existing_attrs or []

        logger.info(
            f"[{detail_id}] 需要补全 {len(missing_rules)} 个必填属性: "
            f"{[r.attr_name for r in missing_rules]}"
        )

        # 使用 LLM 推断属性值
        inferred = await self._infer_attr_values(
            title=title,
            breadcrumb=breadcrumb,
            rules=missing_rules,
        )

        # 验证推断的属性值
        validated = self._validate_attr_values(inferred, missing_rules)

        # 合并已有属性和新推断的属性
        result = list(existing_attrs or []) + validated

        logger.success(f"[{detail_id}] 属性补全完成: 新增 {len(validated)} 个属性")
        return result

    async def fill_batch_attrs(
        self,
        products: list[ProductAttrContext],
        max_concurrency: int = 5,
    ) -> dict[str, list[dict[str, str]]]:
        """批量补全多个产品的属性（并行处理）.

        按类目分组处理，相同类目的产品共享属性规则缓存。
        使用信号量限制并发数量，避免 API 过载。

        Args:
            products: 产品上下文列表
            max_concurrency: 最大并发数（默认 5）

        Returns:
            字典，key 为 detail_id，value 为补全后的属性列表
        """
        results: dict[str, list[dict[str, str]]] = {}
        semaphore = asyncio.Semaphore(max_concurrency)

        # 按类目分组
        by_cid: dict[str, list[ProductAttrContext]] = {}
        for p in products:
            by_cid.setdefault(p.cid, []).append(p)

        logger.info(f"批量属性补全: {len(products)} 个产品, {len(by_cid)} 个类目, 并发={max_concurrency}")

        # 预加载所有类目的属性规则到缓存（并行）
        await asyncio.gather(*[self._get_required_attrs(cid) for cid in by_cid])

        # 定义带信号量的处理函数
        async def process_product(p: ProductAttrContext) -> tuple[str, list[dict[str, str]]]:
            async with semaphore:
                attrs = await self.fill_required_attrs(
                    detail_id=p.detail_id,
                    title=p.title,
                    cid=p.cid,
                    breadcrumb=p.breadcrumb,
                    existing_attrs=p.existing_attrs,
                )
                return p.detail_id, attrs

        # 并行处理所有产品
        tasks = [process_product(p) for p in products]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集结果
        for item in completed:
            if isinstance(item, Exception):
                logger.error(f"属性补全异常: {item}")
                continue
            detail_id, attrs = item
            results[detail_id] = attrs

        return results

    async def _get_required_attrs(self, cid: str) -> list[CategoryAttrRule]:
        """获取类目的必填属性规则（带缓存）.

        Args:
            cid: 类目 ID

        Returns:
            必填属性规则列表
        """
        # 检查缓存
        cached = self.cache.get(cid)
        if cached is not None:
            return [r for r in cached if r.is_required]

        # 调用 API 获取属性规则
        result = await self.api_client.get_category_attribute_rules(cid)
        if result.get("result") != "success":
            logger.warning(f"获取类目 {cid} 属性规则失败: {result.get('message')}")
            return []

        # 解析属性规则 (API 返回 productAttributeRules)
        rules = []
        for item in result.get("productAttributeRules", []):
            # 转换 values 格式: [{vid, name}, ...] -> [{valueId, valueName}, ...]
            raw_values = item.get("values") or []
            attr_values = [
                {"valueId": str(v.get("vid", "")), "valueName": v.get("name", "")}
                for v in raw_values
                if v.get("name")
            ]
            rule = CategoryAttrRule(
                attr_id=str(item.get("templatePid", "")),
                attr_name=item.get("name", ""),
                is_required=item.get("required", False) is True,
                input_type="select" if item.get("controlType") == 1 else "input",
                attr_values=attr_values,
            )
            rules.append(rule)

        # 缓存所有规则
        self.cache.set(cid, rules)

        # 返回必填属性
        required = [r for r in rules if r.is_required]
        logger.debug(f"类目 {cid} 属性规则: 共 {len(rules)} 个, 必填 {len(required)} 个")
        return required

    async def _infer_attr_values(
        self,
        title: str,
        breadcrumb: str,
        rules: list[CategoryAttrRule],
    ) -> list[dict[str, str]]:
        """使用 LLM 推断属性值.

        Args:
            title: 产品标题
            breadcrumb: 类目面包屑
            rules: 需要推断的属性规则列表

        Returns:
            推断的属性列表
        """
        if not rules:
            return []

        # 检查 API 密钥
        if not self.api_key or not OPENAI_AVAILABLE:
            logger.warning("LLM 不可用，使用降级方案")
            return self._fallback_attrs(rules)

        # 构建属性列表描述
        attr_lines = []
        for r in rules:
            if r.attr_values:
                # 限制可选项数量，避免 prompt 过长
                options = ", ".join([v.get("valueName", "") for v in r.attr_values[:15]])
                if len(r.attr_values) > 15:
                    options += f" 等共 {len(r.attr_values)} 个选项"
                attr_lines.append(f"- {r.attr_name}（可选项：{options}）")
            else:
                attr_lines.append(f"- {r.attr_name}（自由输入）")

        # 构建 prompt
        prompt = self.PROMPT_TEMPLATE.format(
            title=title,
            breadcrumb=breadcrumb or "未知类目",
            attributes_list="\n".join(attr_lines),
        )

        # 调用 LLM（带重试）
        for attempt in range(self.max_retries):
            try:
                result = await self._call_llm(prompt)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"LLM 调用失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2**attempt)  # 指数退避

        # 全部重试失败，使用降级方案
        logger.warning("LLM 调用失败，使用降级方案")
        return self._fallback_attrs(rules)

    async def _call_llm(self, prompt: str) -> list[dict[str, str]]:
        """调用阿里云百炼 API.

        Args:
            prompt: 提示词

        Returns:
            解析后的属性列表
        """
        if not OPENAI_AVAILABLE:
            raise RuntimeError("openai 库未安装")

        client = openai.AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.BASE_URL,
            timeout=self.timeout,
        )

        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个电商产品属性专家。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=500,
        )

        content = response.choices[0].message.content
        if not content:
            return []

        return self._parse_llm_response(content.strip())

    def _parse_llm_response(self, content: str) -> list[dict[str, str]]:
        """解析 LLM 返回的 JSON.

        Args:
            content: LLM 返回的文本

        Returns:
            解析后的属性列表
        """
        # 尝试提取 JSON 数组
        json_match = re.search(r"\[[\s\S]*\]", content)
        if not json_match:
            logger.warning(f"LLM 返回格式异常: {content[:200]}")
            return []

        try:
            parsed = json.loads(json_match.group())
            if isinstance(parsed, list):
                return [
                    {"attrName": item.get("attrName", ""), "attrValue": item.get("attrValue", "")}
                    for item in parsed
                    if item.get("attrName") and item.get("attrValue")
                ]
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败: {e}")

        return []

    def _validate_attr_values(
        self,
        inferred: list[dict[str, str]],
        rules: list[CategoryAttrRule],
    ) -> list[dict[str, str]]:
        """验证属性值是否在可选范围内.

        Args:
            inferred: LLM 推断的属性列表
            rules: 属性规则列表

        Returns:
            验证/修正后的属性列表
        """
        rule_map = {r.attr_name: r for r in rules}
        validated = []

        for attr in inferred:
            name = attr.get("attrName", "")
            value = attr.get("attrValue", "")
            rule = rule_map.get(name)

            if not rule:
                continue

            # 如果属性有可选值，验证值是否有效
            if rule.attr_values:
                valid_values = {v.get("valueName", "") for v in rule.attr_values}
                if value in valid_values:
                    validated.append(attr)
                else:
                    # 尝试模糊匹配
                    matched = self._fuzzy_match(value, valid_values)
                    if matched:
                        validated.append({"attrName": name, "attrValue": matched})
                        logger.debug(f"属性 '{name}' 模糊匹配: '{value}' -> '{matched}'")
                    else:
                        # 使用第一个可选值作为降级
                        fallback = rule.attr_values[0].get("valueName", "")
                        logger.warning(f"属性 '{name}' 值 '{value}' 无效，使用降级值: {fallback}")
                        validated.append({"attrName": name, "attrValue": fallback})
            else:
                # 自由输入类型，直接接受
                validated.append(attr)

        # 检查是否有遗漏的必填属性
        validated_names = {a.get("attrName") for a in validated}
        for rule in rules:
            if rule.attr_name not in validated_names:
                # 使用降级方案补充
                fallback_attr = self._get_fallback_value(rule)
                validated.append(fallback_attr)
                logger.warning(
                    f"属性 '{rule.attr_name}' 未推断，使用降级值: {fallback_attr['attrValue']}"
                )

        return validated

    def _fuzzy_match(self, value: str, valid_set: set[str]) -> str | None:
        """模糊匹配属性值.

        Args:
            value: 待匹配的值
            valid_set: 有效值集合

        Returns:
            匹配到的有效值，或 None
        """
        value_lower = value.lower().strip()

        for v in valid_set:
            v_lower = v.lower().strip()
            # 完全匹配（忽略大小写）
            if v_lower == value_lower:
                return v
            # 包含匹配
            if value_lower in v_lower or v_lower in value_lower:
                return v

        return None

    def _fallback_attrs(self, rules: list[CategoryAttrRule]) -> list[dict[str, str]]:
        """降级方案：为每个必填属性选择默认值.

        Args:
            rules: 属性规则列表

        Returns:
            默认属性值列表
        """
        result = []
        for r in rules:
            result.append(self._get_fallback_value(r))
        return result

    def _get_fallback_value(self, rule: CategoryAttrRule) -> dict[str, str]:
        """获取单个属性的降级值.

        Args:
            rule: 属性规则

        Returns:
            降级属性值
        """
        # 有可选值选择第一个，否则使用"通用"
        value = rule.attr_values[0].get("valueName", "") if rule.attr_values else "通用"
        return {"attrName": rule.attr_name, "attrValue": value}

    def convert_to_api_format(
        self,
        cid: str,
        attrs: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """将 AI 输出格式转换为 API 保存格式.

        Args:
            cid: 类目 ID
            attrs: AI 输出的属性列表 [{"attrName": "材质", "attrValue": "不锈钢"}]

        Returns:
            API 格式的属性列表 [{"templatePid": "952645", "vid": "381"}]
        """
        rules = self.cache.get(cid)
        if not rules:
            logger.warning(f"类目 {cid} 规则未缓存，无法转换属性格式")
            return []

        # 构建查找映射: attrName -> rule
        rule_map = {r.attr_name: r for r in rules}

        api_attrs = []
        for attr in attrs:
            attr_name = attr.get("attrName", "")
            attr_value = attr.get("attrValue", "")

            rule = rule_map.get(attr_name)
            if not rule:
                logger.debug(f"属性 '{attr_name}' 未在类目规则中找到，跳过")
                continue

            # 构建 API 格式
            api_attr: dict[str, Any] = {"templatePid": rule.attr_id}

            # 查找 vid（如果有可选值）
            if rule.attr_values:
                vid = None
                for v in rule.attr_values:
                    if v.get("valueName") == attr_value:
                        vid = v.get("valueId")
                        break
                if vid:
                    api_attr["vid"] = vid
                else:
                    # 值不在选项中，作为自由输入处理
                    api_attr["value"] = attr_value
            else:
                # 自由输入属性
                api_attr["value"] = attr_value

            api_attrs.append(api_attr)

        logger.debug(f"类目 {cid} 属性转换: {len(attrs)} -> {len(api_attrs)} 个")
        return api_attrs
