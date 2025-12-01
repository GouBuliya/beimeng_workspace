"""
@PURPOSE: 批量下载副本10月.csv 中的视频资源到指定目录。
@OUTLINE:
  - def sanitize_name(): 清洗文件名
  - def resolve_filename(): 处理重名逻辑
  - def download_videos(): 主下载流程
  - def parse_args(): 命令行参数解析
@DEPENDENCIES:
  - 外部: requests
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable

import requests

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/118.0.0.0 Safari/537.36"
    ),
    "Referer": "https://erp.91miaoshou.com/",
    "Accept": "*/*",
}


def sanitize_name(value: str | None) -> str:
    """清洗文件名，只保留字母、数字、下划线和短横线."""

    if not value:
        return ""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return safe.strip("_") or ""


def resolve_filename(base: str, directory: Path) -> Path:
    """避免重名，必要时追加序号."""

    candidate = directory / f"{base}.mp4"
    index = 1
    while candidate.exists():
        candidate = directory / f"{base}_{index}.mp4"
        index += 1
    return candidate


def iter_rows(csv_path: Path) -> Iterable[dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        yield from reader


def download_videos(csv_path: Path, output_dir: Path, overwrite: bool = False) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for row in iter_rows(csv_path):
        video_url = row.get("视频链接") or row.get("video_url") or row.get("product_video_url")
        if not video_url:
            continue

        model = (
            row.get("标题后缀")
            or row.get("model_number")
            or row.get("产品名称")
            or row.get("product_name")
            or row.get("序号")
            or row.get("index")
        )
        safe_name = sanitize_name(model)
        if not safe_name:
            safe_name = sanitize_name(row.get("序号")) or "video"

        target = output_dir / f"{safe_name}.mp4"
        if target.exists() and not overwrite:
            target = resolve_filename(safe_name, output_dir)

        print(f"下载 {video_url} -> {target.name}")
        try:
            response = requests.get(
                video_url,
                timeout=30,
                stream=True,
                headers=DEFAULT_HEADERS,
            )
            response.raise_for_status()
            with target.open("wb") as file:
                for chunk in response.iter_content(chunk_size=512 * 1024):
                    if chunk:
                        file.write(chunk)
        except Exception as exc:
            print(f"下载失败: {video_url} -> {exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="下载 CSV 中的视频到指定目录")
    parser.add_argument(
        "--input",
        required=True,
        help="CSV 文件路径，例如 apps/temu-auto-publish/data/input/副本10月.csv",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="视频输出目录，例如 apps/temu-auto-publish/data/video",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="覆盖已存在的同名文件",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV 文件不存在: {csv_path}")

    download_videos(csv_path, output_dir, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
