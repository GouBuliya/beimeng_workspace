"""Temu 商品发布自动化系统.

这是一个使用 Python + 影刀 RPA 混合架构的自动化系统，
用于自动化 Temu 平台的商品发布流程。

主要功能：
- Excel 选品表处理
- 自动登录 Temu 后台
- 站内搜索和商品采集
- 批量编辑和发布

使用方法：
    from apps.temu_auto_publish import TemuAutoPublish
    
    # 或使用 CLI
    python -m apps.temu-auto-publish process products.xlsx
"""

__version__ = "0.1.0"
__author__ = "Beimeng Team"


