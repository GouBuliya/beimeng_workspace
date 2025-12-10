"""
@PURPOSE: 测试 Web Panel 表格编辑器相关 API（图片上传、视频上传、JSON 数据提交）
@OUTLINE:
  - test_upload_image_success: 测试图片上传成功
  - test_upload_image_invalid_type: 测试无效图片类型被拒绝
  - test_upload_image_too_large: 测试超大图片被拒绝
  - test_upload_video_success: 测试视频上传成功
  - test_upload_video_invalid_type: 测试无效视频类型被拒绝
  - test_upload_video_too_large: 测试超大视频被拒绝
  - test_run_json_success: 测试 JSON 格式数据提交
  - test_run_json_empty_data: 测试空数据被拒绝
  - test_run_json_missing_product_name: 测试缺少产品名称被拒绝
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

# 设置 DEBUG_MODE 以启用 dev/dev 登录（测试环境）
os.environ["DEBUG_MODE"] = "true"

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "temu-auto-publish"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from web_panel.api import create_app  # type: ignore[import-not-found]
from web_panel.models import (  # type: ignore[import-not-found]
    LogChunk,
    RunState,
    RunStatus,
    WorkflowOptions,
)


class DummyManager:
    """最小化的任务管理器，便于注入到 FastAPI."""

    def __init__(self) -> None:
        self.started_with: WorkflowOptions | None = None
        self.return_status = RunStatus(state=RunState.RUNNING, message="mock-run")

    def start(self, options: WorkflowOptions) -> RunStatus:
        self.started_with = options
        return self.return_status

    def status(self) -> RunStatus:
        return RunStatus(state=RunState.IDLE, message="idle")

    def logs(self, after: int = -1) -> list[LogChunk]:
        return [LogChunk(index=0, timestamp=0.0, level="INFO", message="ready")]


async def login_client(client: AsyncClient) -> None:
    """使用开发模式账号登录."""
    await client.post("/login", data={"username": "dev", "password": "dev"})


# ==================== 图片上传测试 ====================


@pytest.mark.asyncio
async def test_upload_image_success() -> None:
    """测试图片上传成功（支持 OSS 或本地存储）."""
    manager = DummyManager()
    app = create_app(task_manager=manager)

    # 创建一个最小的 PNG 图片（1x1 透明像素）
    png_data = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await login_client(client)
        response = await client.post(
            "/api/upload-image",
            files={"file": ("test.png", png_data, "image/png")},
        )

    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert "filename" in data
    assert data["storage"] in ("local", "oss")
    # 根据存储类型验证 URL 格式
    if data["storage"] == "local":
        assert data["url"].startswith("/static/uploads/")
    else:
        assert data["url"].startswith("https://")
    assert data["filename"].endswith(".png")


@pytest.mark.asyncio
async def test_upload_image_invalid_type() -> None:
    """测试无效图片类型被拒绝."""
    manager = DummyManager()
    app = create_app(task_manager=manager)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await login_client(client)
        response = await client.post(
            "/api/upload-image",
            files={"file": ("test.txt", b"not an image", "text/plain")},
        )

    assert response.status_code == 400
    assert "不支持的文件类型" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_image_jpeg() -> None:
    """测试 JPEG 图片上传."""
    manager = DummyManager()
    app = create_app(task_manager=manager)

    # 最小的 JPEG 数据
    jpeg_data = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01"
        b"\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06"
        b"\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b"
        b"\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c"
        b"\x1c $.\' ",),

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await login_client(client)
        response = await client.post(
            "/api/upload-image",
            files={"file": ("photo.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 100, "image/jpeg")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["filename"].endswith(".jpg")


# ==================== 视频上传测试 ====================


@pytest.mark.asyncio
async def test_upload_video_success() -> None:
    """测试视频上传成功（支持 OSS 或本地存储）."""
    manager = DummyManager()
    app = create_app(task_manager=manager)

    # 最小的 MP4 数据（ftyp box）
    mp4_data = (
        b"\x00\x00\x00\x1cftypisom\x00\x00\x02\x00"
        b"isomiso2avc1mp41"
        + b"\x00" * 100
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await login_client(client)
        response = await client.post(
            "/api/upload-video",
            files={"file": ("test.mp4", mp4_data, "video/mp4")},
        )

    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert "filename" in data
    assert data["storage"] in ("local", "oss")
    # 根据存储类型验证 URL 格式
    if data["storage"] == "local":
        assert data["url"].startswith("/static/uploads/videos/")
    else:
        assert data["url"].startswith("https://")
        assert "/videos/" in data["url"]
    assert data["filename"].endswith(".mp4")


@pytest.mark.asyncio
async def test_upload_video_webm() -> None:
    """测试 WebM 视频上传."""
    manager = DummyManager()
    app = create_app(task_manager=manager)

    # WebM 文件头
    webm_data = b"\x1aE\xdf\xa3" + b"\x00" * 100

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await login_client(client)
        response = await client.post(
            "/api/upload-video",
            files={"file": ("clip.webm", webm_data, "video/webm")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["filename"].endswith(".webm")


@pytest.mark.asyncio
async def test_upload_video_invalid_type() -> None:
    """测试无效视频类型被拒绝."""
    manager = DummyManager()
    app = create_app(task_manager=manager)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await login_client(client)
        response = await client.post(
            "/api/upload-video",
            files={"file": ("test.txt", b"not a video", "text/plain")},
        )

    assert response.status_code == 400
    assert "不支持的文件类型" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_video_mov() -> None:
    """测试 MOV 视频上传."""
    manager = DummyManager()
    app = create_app(task_manager=manager)

    # QuickTime MOV 文件头
    mov_data = b"\x00\x00\x00\x14ftypqt  " + b"\x00" * 100

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await login_client(client)
        response = await client.post(
            "/api/upload-video",
            files={"file": ("movie.mov", mov_data, "video/quicktime")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["filename"].endswith(".mov")


# ==================== JSON 数据提交测试 ====================


@pytest.mark.asyncio
async def test_run_json_success() -> None:
    """测试 JSON 格式数据提交成功."""
    manager = DummyManager()
    app = create_app(task_manager=manager)

    selection_data = [
        {
            "product_name": "测试产品1",
            "title_suffix": "A001",
            "spec_unit": "个",
            "spec_array": ["大号", "小号"],
            "price_array": ["100", "80"],
            "sku_images": ["https://example.com/1.jpg", "https://example.com/2.jpg"],
            "video_url": "https://example.com/video.mp4",
            "availability": "1",
            "size_chart_url": "https://example.com/size.jpg",
        },
        {
            "product_name": "测试产品2",
            "title_suffix": "A002",
            "spec_unit": "套",
            "spec_array": ["红色"],
            "price_array": ["50"],
            "sku_images": ["https://example.com/3.jpg"],
            "video_url": "",
            "availability": "1",
            "size_chart_url": "",
        },
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await login_client(client)
        response = await client.post(
            "/api/run-json",
            json={
                "selection_data": selection_data,
                "collection_owner": "测试员(test001)",
            },
        )

    assert response.status_code == 200
    assert manager.started_with is not None
    assert manager.started_with.collection_owner == "测试员(test001)"
    assert manager.started_with.selection_path.exists()
    assert manager.started_with.selection_path.suffix == ".csv"


@pytest.mark.asyncio
async def test_run_json_empty_data() -> None:
    """测试空数据被拒绝."""
    manager = DummyManager()
    app = create_app(task_manager=manager)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await login_client(client)
        response = await client.post(
            "/api/run-json",
            json={
                "selection_data": [],
                "collection_owner": "测试员(test001)",
            },
        )

    assert response.status_code == 400
    assert "选品数据不能为空" in response.json()["detail"]


@pytest.mark.asyncio
async def test_run_json_missing_product_name() -> None:
    """测试缺少产品名称被拒绝."""
    manager = DummyManager()
    app = create_app(task_manager=manager)

    selection_data = [
        {
            "product_name": "",  # 空的产品名称
            "title_suffix": "A001",
        },
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await login_client(client)
        response = await client.post(
            "/api/run-json",
            json={
                "selection_data": selection_data,
                "collection_owner": "测试员(test001)",
            },
        )

    assert response.status_code == 400
    assert "产品名称不能为空" in response.json()["detail"]


@pytest.mark.asyncio
async def test_run_json_missing_collection_owner() -> None:
    """测试缺少妙手创建人员被拒绝."""
    manager = DummyManager()
    app = create_app(task_manager=manager)

    selection_data = [
        {
            "product_name": "测试产品",
            "title_suffix": "A001",
        },
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await login_client(client)
        response = await client.post(
            "/api/run-json",
            json={
                "selection_data": selection_data,
                "collection_owner": "",  # 空的创建人员
            },
        )

    assert response.status_code == 400
    assert "妙手创建人员不能为空" in response.json()["detail"]


@pytest.mark.asyncio
async def test_run_json_with_options() -> None:
    """测试 JSON 提交时携带运行配置."""
    manager = DummyManager()
    app = create_app(task_manager=manager)

    selection_data = [
        {"product_name": "测试产品"},
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await login_client(client)
        response = await client.post(
            "/api/run-json",
            json={
                "selection_data": selection_data,
                "collection_owner": "测试员(test001)",
                "headless_mode": "on",
                "use_ai_titles": "on",
                "single_run": "off",
                "publish_repeat_count": "3",
            },
        )

    assert response.status_code == 200
    assert manager.started_with is not None
    assert manager.started_with.use_ai_titles is True
    assert manager.started_with.single_run is False


# ==================== 认证测试 ====================


@pytest.mark.asyncio
async def test_upload_image_requires_auth() -> None:
    """测试图片上传需要认证."""
    manager = DummyManager()
    app = create_app(task_manager=manager)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 不登录直接上传
        response = await client.post(
            "/api/upload-image",
            files={"file": ("test.png", b"\x89PNG" + b"\x00" * 100, "image/png")},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_video_requires_auth() -> None:
    """测试视频上传需要认证."""
    manager = DummyManager()
    app = create_app(task_manager=manager)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 不登录直接上传
        response = await client.post(
            "/api/upload-video",
            files={"file": ("test.mp4", b"\x00\x00\x00\x1cftyp" + b"\x00" * 100, "video/mp4")},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_run_json_requires_auth() -> None:
    """测试 JSON 提交需要认证."""
    manager = DummyManager()
    app = create_app(task_manager=manager)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 不登录直接提交
        response = await client.post(
            "/api/run-json",
            json={
                "selection_data": [{"product_name": "测试"}],
                "collection_owner": "测试员",
            },
        )

    assert response.status_code == 401
