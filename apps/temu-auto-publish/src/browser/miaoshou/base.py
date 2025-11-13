"""
@PURPOSE: Provide shared selector loading utilities for Miaoshou controller classes.
@OUTLINE:
  - class MiaoshouControllerBase: core selector helpers
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from loguru import logger


class MiaoshouControllerBase:
    """Common selector helpers for Miaoshou workflows."""

    def __init__(self, selector_path: str = "config/miaoshou_selectors_v2.json") -> None:
        """Initialise the base controller.

        Args:
            selector_path: Path to selector configuration.
        """
        self.selector_path = Path(selector_path)
        self.selectors = self._load_selectors()
        logger.info("Miaoshou controller initialised (text locator strategy)")

    def _load_selectors(self) -> dict[str, Any]:
        """Load selector configuration from disk.

        Returns:
            Loaded selector mapping. Returns an empty dictionary if loading fails.
        """
        try:
            if self.selector_path.is_absolute():
                selector_file = self.selector_path
            else:
                relative_path = self.selector_path
                current_file = Path(__file__).resolve()
                selector_file: Path | None = None

                for parent in current_file.parents:
                    candidate = parent / relative_path
                    if candidate.exists():
                        selector_file = candidate
                        break

                if selector_file is None:
                    # Fallback to historical project root inference for clearer error logging
                    selector_file = current_file.parent.parent.parent / relative_path

            with open(selector_file, encoding="utf-8") as file:
                return json.load(file)
        except Exception as exc:  # pragma: no cover - config loading
            logger.warning(f"Failed to load selector config: {exc}")
            return {}

    def _normalize_selector_value(self, value: object) -> list[str]:
        """Normalise a selector entry into a list of strings.

        Args:
            value: Raw selector configuration value.

        Returns:
            A list of selector strings extracted from ``value``.
        """
        if value is None:
            return []

        if isinstance(value, list):
            selectors: list[str] = []
            for item in value:
                selectors.extend(self._normalize_selector_value(item))
            return selectors

        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",") if part.strip()]
            return parts

        normalised = str(value).strip()
        return [normalised] if normalised else []

    def _resolve_selectors(
        self,
        config: dict[str, Any],
        keys: Sequence[str],
        default: Sequence[str],
    ) -> list[str]:
        """Resolve selectors from configuration with sensible fallbacks.

        Args:
            config: The configuration block containing selector information.
            keys: Preferred keys to inspect within ``config``.
            default: Fallback selectors used when the preferred keys are missing.

        Returns:
            A list of unique selectors derived from configuration or defaults.
        """
        selectors: list[str] = []
        for key in keys:
            if key not in config:
                continue
            selectors.extend(self._normalize_selector_value(config.get(key)))

        unique_selectors: list[str] = []
        for selector in selectors:
            if selector and selector not in unique_selectors:
                unique_selectors.append(selector)

        if unique_selectors:
            return unique_selectors

        fallback_selectors: list[str] = []
        for selector in default:
            candidate = selector.strip()
            if candidate and candidate not in fallback_selectors:
                fallback_selectors.append(candidate)

        return fallback_selectors

