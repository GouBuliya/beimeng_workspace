"""Temu 商品发布自动化系统.

这是一个使用 Python + Playwright 纯代码方案的自动化系统，
用于自动化 Temu 平台的商品发布流程。

主要功能：
- Excel 选品表处理
- 自动登录 Temu 后台（Playwright + 反检测）
- 站内搜索和商品采集
- 批量编辑和发布

使用方法：
    # CLI 方式
    python -m apps.temu-auto-publish process products.xlsx
    
架构：
    纯 Python + Playwright 异步实现
"""

__version__ = "0.2.0"
__author__ = "Beimeng Team"


