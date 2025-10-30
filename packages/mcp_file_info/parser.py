"""
@PURPOSE: 实现文件元信息解析器，提取文件头部的元数据注释
@OUTLINE:
  - class FileInfoParser: 文件元信息解析器主类
  - _extract_comment_block(): 提取注释块
  - _parse_metadata_fields(): 解析元信息字段
  - _normalize_content(): 规范化内容
@GOTCHAS:
  - 不同语言的注释语法不同，需要正确识别
  - 多行字段的内容需要保持缩进关系
  - 某些注释可能不包含元信息，需要区分
@DEPENDENCIES:
  - 内部: .models, .config
  - 外部: pathlib, re
"""

import re
from pathlib import Path

from .config import COMMENT_PATTERNS, ParserConfig, SUPPORTED_EXTENSIONS
from .models import METADATA_FIELDS, FileMetadata


class FileInfoParser:
    """文件元信息解析器.

    从源代码文件头部提取并解析元数据注释。

    Attributes:
        config: 解析器配置

    Examples:
        >>> parser = FileInfoParser()
        >>> metadata = parser.parse_file("example.py")
        >>> print(metadata.get_field("PURPOSE"))
    """

    def __init__(self, config: ParserConfig | None = None):
        """初始化解析器.

        Args:
            config: 解析器配置，如果为None则使用默认配置
        """
        self.config = config or ParserConfig()

    def parse_file(self, file_path: str | Path) -> FileMetadata:
        """解析文件并提取元信息.

        Args:
            file_path: 文件路径

        Returns:
            FileMetadata 对象

        Raises:
            FileNotFoundError: 文件不存在
        """
        file_path = Path(file_path)

        # 检查文件是否存在
        if not file_path.exists():
            return FileMetadata(
                file_path=str(file_path),
                has_metadata=False,
                error=f"文件不存在: {file_path}",
            )

        # 检查文件扩展名是否支持
        extension = file_path.suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            return FileMetadata(
                file_path=str(file_path),
                has_metadata=False,
                error=f"不支持的文件类型: {extension}",
            )

        try:
            # 读取文件头部
            content = self._read_file_head(file_path)

            # 提取注释块
            comment_block = self._extract_comment_block(content, extension)

            if not comment_block:
                return FileMetadata(
                    file_path=str(file_path),
                    has_metadata=False,
                    raw_content="",
                )

            # 解析元信息字段
            fields = self._parse_metadata_fields(comment_block)

            # 检查是否真的包含元信息（至少有一个字段）
            has_metadata = len(fields) > 0

            return FileMetadata(
                file_path=str(file_path),
                has_metadata=has_metadata,
                fields=fields,
                raw_content=comment_block,
            )

        except Exception as e:
            return FileMetadata(
                file_path=str(file_path),
                has_metadata=False,
                error=f"解析错误: {str(e)}",
            )

    def _read_file_head(self, file_path: Path) -> str:
        """读取文件头部内容.

        Args:
            file_path: 文件路径

        Returns:
            文件头部内容（最多 max_lines_to_read 行）
        """
        lines = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= self.config.max_lines_to_read:
                        break
                    lines.append(line)
        except UnicodeDecodeError:
            # 尝试其他编码
            with open(file_path, "r", encoding="latin-1") as f:
                for i, line in enumerate(f):
                    if i >= self.config.max_lines_to_read:
                        break
                    lines.append(line)

        return "".join(lines)

    def _extract_comment_block(self, content: str, extension: str) -> str:
        """提取注释块.

        Args:
            content: 文件内容
            extension: 文件扩展名

        Returns:
            提取的注释内容（去除注释标记）
        """
        patterns = COMMENT_PATTERNS.get(extension, [])

        for start_marker, end_marker, line_prefix in patterns:
            if end_marker:  # 多行注释
                comment = self._extract_multiline_comment(
                    content, start_marker, end_marker, line_prefix
                )
                if comment:
                    return comment
            else:  # 单行注释
                comment = self._extract_singleline_comments(content, start_marker)
                if comment:
                    return comment

        return ""

    def _extract_multiline_comment(
        self, content: str, start: str, end: str, line_prefix: str
    ) -> str:
        """提取多行注释.

        Args:
            content: 文件内容
            start: 开始标记
            end: 结束标记
            line_prefix: 行前缀（如 * 号）

        Returns:
            提取的注释内容
        """
        # 查找第一个注释块
        start_idx = content.find(start)
        if start_idx == -1:
            return ""

        end_idx = content.find(end, start_idx + len(start))
        if end_idx == -1:
            return ""

        # 提取注释内容
        comment = content[start_idx + len(start) : end_idx]

        # 移除行前缀
        if line_prefix:
            lines = comment.split("\n")
            cleaned_lines = []
            for line in lines:
                # 先检查原始行（可能有前导空格）
                trimmed = line.lstrip()
                # 检查是否以行前缀开头（去除空格后）
                prefix_stripped = line_prefix.strip()
                if trimmed.startswith(prefix_stripped):
                    # 移除前缀并继续处理
                    cleaned_lines.append(trimmed[len(prefix_stripped) :].lstrip())
                elif line.strip():
                    # 非空行但没有前缀
                    cleaned_lines.append(line.strip())
                else:
                    # 空行
                    cleaned_lines.append("")
            comment = "\n".join(cleaned_lines)

        return comment.strip()

    def _extract_singleline_comments(self, content: str, marker: str) -> str:
        """提取连续的单行注释.

        Args:
            content: 文件内容
            marker: 注释标记

        Returns:
            提取的注释内容
        """
        lines = content.split("\n")
        comment_lines = []
        started = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith(marker):
                started = True
                # 移除注释标记
                comment_line = stripped[len(marker) :].lstrip()
                comment_lines.append(comment_line)
            elif started and stripped:
                # 遇到非注释的非空行，停止
                break
            elif started and not stripped:
                # 空行也加入
                comment_lines.append("")

        return "\n".join(comment_lines).strip()

    def _parse_metadata_fields(self, comment: str) -> dict[str, str]:
        """解析元信息字段.

        Args:
            comment: 注释内容

        Returns:
            字段名到值的字典
        """
        fields = {}
        current_field = None
        current_value = []

        lines = comment.split("\n")

        for line in lines:
            # 检查是否是字段开始行
            match = re.match(r"@([A-Z_]+):\s*(.*)", line.strip())
            if match:
                # 保存之前的字段
                if current_field:
                    fields[current_field] = "\n".join(current_value).strip()

                # 开始新字段
                current_field = match.group(1)
                current_value = [match.group(2)] if match.group(2) else []
            elif current_field and line.strip():
                # 续行（属于当前字段）
                current_value.append(line.strip())
            elif current_field and not line.strip():
                # 空行也加入（保持格式）
                current_value.append("")

        # 保存最后一个字段
        if current_field:
            fields[current_field] = "\n".join(current_value).strip()

        # 只返回已定义的字段
        return {k: v for k, v in fields.items() if k in METADATA_FIELDS}

    def parse_multiple_files(
        self, file_paths: list[str | Path]
    ) -> dict[str, FileMetadata]:
        """批量解析多个文件.

        Args:
            file_paths: 文件路径列表

        Returns:
            文件路径到 FileMetadata 的字典
        """
        results = {}
        for file_path in file_paths:
            metadata = self.parse_file(file_path)
            results[str(file_path)] = metadata
        return results

