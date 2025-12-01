"""
@PURPOSE: High level Miaoshou controller composition.
@OUTLINE:
  - class MiaoshouController: concrete controller used across workflows
"""

from __future__ import annotations

from .claim import MiaoshouClaimMixin


class MiaoshouController(MiaoshouClaimMixin):
    """Concrete Miaoshou controller for automation workflows."""

    __slots__ = ()

    def __init__(self, selector_path: str = "config/miaoshou_selectors_v2.json") -> None:
        super().__init__(selector_path=selector_path)
