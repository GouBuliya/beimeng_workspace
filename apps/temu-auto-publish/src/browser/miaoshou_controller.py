"""
@PURPOSE: Backwards compatible entry point for the Miaoshou controller.
@OUTLINE:
  - from .miaoshou import MiaoshouController: re-export concrete controller
@GOTCHAS:
  - Prefer importing from src.browser.miaoshou; this wrapper remains for legacy usage.
"""

from __future__ import annotations

from .miaoshou import MiaoshouController

__all__ = ["MiaoshouController"]

