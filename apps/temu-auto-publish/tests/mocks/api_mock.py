"""
@PURPOSE: 外部 API Mock 类
@OUTLINE:
  - MockOpenAIResponse: 模拟 OpenAI API 响应
  - MockOpenAIClient: 模拟 OpenAI 客户端
  - MockHTTPResponse: 模拟 HTTP 响应
@DEPENDENCIES:
  - 外部: unittest.mock
"""

from dataclasses import dataclass, field


@dataclass
class MockOpenAIMessage:
    """模拟 OpenAI 消息"""

    role: str = "assistant"
    content: str = "Mock response content"


@dataclass
class MockOpenAIChoice:
    """模拟 OpenAI 选择"""

    index: int = 0
    message: MockOpenAIMessage = field(default_factory=MockOpenAIMessage)
    finish_reason: str = "stop"


@dataclass
class MockOpenAIUsage:
    """模拟 OpenAI 使用统计"""

    prompt_tokens: int = 10
    completion_tokens: int = 20
    total_tokens: int = 30


@dataclass
class MockOpenAIResponse:
    """模拟 OpenAI API 响应"""

    id: str = "mock-response-id"
    object: str = "chat.completion"
    created: int = 1234567890
    model: str = "gpt-3.5-turbo"
    choices: list[MockOpenAIChoice] = field(default_factory=lambda: [MockOpenAIChoice()])
    usage: MockOpenAIUsage = field(default_factory=MockOpenAIUsage)

    @classmethod
    def create(cls, content: str = "Mock response") -> "MockOpenAIResponse":
        """创建带指定内容的响应"""
        return cls(choices=[MockOpenAIChoice(message=MockOpenAIMessage(content=content))])


class MockOpenAIChatCompletions:
    """模拟 OpenAI Chat Completions API"""

    def __init__(self, default_response: str = "Generated title for product"):
        self.default_response = default_response
        self.call_count = 0
        self.last_messages: list[dict] | None = None
        self.last_model: str | None = None

    async def create(
        self, model: str = "gpt-3.5-turbo", messages: list[dict[str, str]] | None = None, **kwargs
    ) -> MockOpenAIResponse:
        """模拟创建聊天完成"""
        self.call_count += 1
        self.last_messages = messages
        self.last_model = model
        return MockOpenAIResponse.create(self.default_response)

    def create_sync(
        self, model: str = "gpt-3.5-turbo", messages: list[dict[str, str]] | None = None, **kwargs
    ) -> MockOpenAIResponse:
        """同步版本"""
        self.call_count += 1
        self.last_messages = messages
        self.last_model = model
        return MockOpenAIResponse.create(self.default_response)


class MockOpenAIChat:
    """模拟 OpenAI Chat API"""

    def __init__(self, default_response: str = "Generated title for product"):
        self.completions = MockOpenAIChatCompletions(default_response)


class MockOpenAIClient:
    """模拟 OpenAI 客户端"""

    def __init__(self, api_key: str = "mock-api-key", default_response: str = "Generated title"):
        self.api_key = api_key
        self.chat = MockOpenAIChat(default_response)

    def set_response(self, response: str) -> None:
        """设置默认响应内容"""
        self.chat.completions.default_response = response


@dataclass
class MockHTTPResponse:
    """模拟 HTTP 响应"""

    status_code: int = 200
    text: str = ""
    content: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)
    json_data: dict | None = None

    def json(self) -> dict:
        """返回JSON数据"""
        return self.json_data or {}

    def raise_for_status(self) -> None:
        """检查状态码"""
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    @property
    def ok(self) -> bool:
        """是否成功"""
        return 200 <= self.status_code < 300


class MockHTTPClient:
    """模拟 HTTP 客户端 (aiohttp/httpx)"""

    def __init__(self):
        self.responses: dict[str, MockHTTPResponse] = {}
        self.default_response = MockHTTPResponse()
        self.request_history: list[dict] = []

    def set_response(self, url: str, response: MockHTTPResponse) -> None:
        """设置特定URL的响应"""
        self.responses[url] = response

    async def get(self, url: str, **kwargs) -> MockHTTPResponse:
        """GET请求"""
        self.request_history.append({"method": "GET", "url": url, **kwargs})
        return self.responses.get(url, self.default_response)

    async def post(self, url: str, **kwargs) -> MockHTTPResponse:
        """POST请求"""
        self.request_history.append({"method": "POST", "url": url, **kwargs})
        return self.responses.get(url, self.default_response)

    async def put(self, url: str, **kwargs) -> MockHTTPResponse:
        """PUT请求"""
        self.request_history.append({"method": "PUT", "url": url, **kwargs})
        return self.responses.get(url, self.default_response)

    async def delete(self, url: str, **kwargs) -> MockHTTPResponse:
        """DELETE请求"""
        self.request_history.append({"method": "DELETE", "url": url, **kwargs})
        return self.responses.get(url, self.default_response)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
