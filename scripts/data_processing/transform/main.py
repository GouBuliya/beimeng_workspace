#!/usr/bin/env python3
"""数据转换脚本

一个展示最佳实践的数据处理脚本。

Examples:
    从文件读取::

        $ python main.py --input data.json --output result.json

    使用管道::

        $ cat data.json | python main.py | jq .
"""

import json
import sys
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from loguru import logger
from pydantic import BaseModel, Field


class Operation(str, Enum):
    """转换操作类型"""

    UPPERCASE = "uppercase"
    LOWERCASE = "lowercase"
    REVERSE = "reverse"


class InputData(BaseModel):
    """输入数据模型

    Attributes:
        data: 要处理的字符串列表
    """

    data: list[str] = Field(..., description="要处理的字符串列表")


class OutputData(BaseModel):
    """输出数据模型

    Attributes:
        result: 处理后的字符串列表
        operation: 执行的操作
        count: 处理的项目数量
    """

    result: list[str] = Field(..., description="处理后的字符串列表")
    operation: str = Field(..., description="执行的操作")
    count: int = Field(..., description="处理的项目数量")


def transform_data(data: list[str], operation: Operation) -> list[str]:
    """转换数据

    Args:
        data: 输入数据列表
        operation: 转换操作

    Returns:
        转换后的数据列表

    Examples:
        >>> transform_data(["hello", "world"], Operation.UPPERCASE)
        ['HELLO', 'WORLD']
        >>> transform_data(["HELLO", "WORLD"], Operation.LOWERCASE)
        ['hello', 'world']
    """
    if operation == Operation.UPPERCASE:
        return [item.upper() for item in data]
    elif operation == Operation.LOWERCASE:
        return [item.lower() for item in data]
    elif operation == Operation.REVERSE:
        return [item[::-1] for item in data]
    else:
        return data


def main(
    input_file: Optional[Path] = typer.Option(
        None,
        "--input",
        "-i",
        help="输入文件路径（JSON），不提供则从 stdin 读取",
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="输出文件路径（JSON），不提供则输出到 stdout",
    ),
    operation: Operation = typer.Option(
        Operation.UPPERCASE,
        "--operation",
        "-op",
        help="转换操作类型",
    ),
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        "-l",
        help="日志级别",
    ),
) -> None:
    """数据转换脚本主函数

    Args:
        input_file: 输入文件路径（可选）
        output_file: 输出文件路径（可选）
        operation: 转换操作
        log_level: 日志级别
    """
    # 配置日志
    logger.remove()
    logger.add(sys.stderr, level=log_level)

    try:
        # 读取输入
        if input_file:
            logger.info(f"从文件读取: {input_file}")
            with open(input_file) as f:
                raw_data = json.load(f)
        else:
            logger.info("从 stdin 读取")
            raw_data = json.load(sys.stdin)

        # 验证输入
        input_data = InputData(**raw_data)
        logger.debug(f"输入数据验证通过: {len(input_data.data)} 项")

        # 转换数据
        result = transform_data(input_data.data, operation)
        logger.info(f"数据转换完成: {operation.value}")

        # 构建输出
        output_data = OutputData(
            result=result,
            operation=operation.value,
            count=len(result),
        )

        # 输出结果
        output_json = output_data.model_dump_json(indent=2, ensure_ascii=False)

        if output_file:
            logger.info(f"写入文件: {output_file}")
            with open(output_file, "w") as f:
                f.write(output_json)
        else:
            logger.debug("输出到 stdout")
            print(output_json)

        logger.success("处理完成")

    except Exception as e:
        logger.error(f"处理失败: {e}")
        raise typer.Exit(code=1) from e


if __name__ == "__main__":
    typer.run(main)

