# -*- coding: utf-8 -*-
"""Airtest automation for Temu claim workflow."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from airtest.core.api import Template, auto_setup, connect_device, exists, touch, wait

# Initialise Airtest runtime using the current script directory.
auto_setup(__file__)

DEFAULT_TEMPLATES = {
    "claim_button": "toolbar_claim_button.png",
    "temu_checkbox": "temu_checkbox.png",
    "confirm_button": "confirm_button.png",
    "close_button": "dialog_close.png",
}

DEFAULT_THRESHOLDS = {
    "claim_button": 0.85,
    "temu_checkbox": 0.88,
    "confirm_button": 0.88,
    "close_button": 0.8,
}


def parse_runtime_args() -> dict[str, str]:
    """Parse Airtest runtime arguments passed via ``--args``."""

    if "--args" not in sys.argv:
        return {}

    idx = sys.argv.index("--args")
    raw_items = sys.argv[idx + 1 :]

    # Airtest allows ``--args "a=1 b=2"`` 或 ``--args a=1 b=2`` 两种方式.
    if len(raw_items) == 1 and "=" in raw_items[0] and " " in raw_items[0]:
        raw_items = raw_items[0].split()

    parsed: dict[str, str] = {}
    for item in raw_items:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


ARGS = parse_runtime_args()

PRODUCT_COUNT = int(ARGS.get("product_count", 5))
ITERATIONS = int(ARGS.get("iterations", 4))
DEVICE_URI = ARGS.get("device_uri")
TEMPLATES_DIR = Path(
    ARGS.get("template_dir") or Path(__file__).resolve().parent / "templates"
).resolve()

if DEVICE_URI:
    connect_device(DEVICE_URI)

if not TEMPLATES_DIR.exists():
    raise FileNotFoundError(f"Template directory not found: {TEMPLATES_DIR}")


def load_template(key: str) -> Template:
    """Load a template image for a given logical key."""

    template_name = ARGS.get(f"{key}_template", DEFAULT_TEMPLATES[key])
    threshold = float(ARGS.get(f"{key}_threshold", DEFAULT_THRESHOLDS[key]))
    template_path = TEMPLATES_DIR / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found for {key}: {template_path}")
    return Template(str(template_path), threshold=threshold)


def wait_and_touch(key: str, timeout: float) -> None:
    """Wait for the template to appear and touch it."""

    template = load_template(key)
    wait(template, timeout=timeout)
    touch(template)
    time.sleep(float(ARGS.get("post_click_delay", 0.25)))


def claim_once() -> None:
    """Execute a single Temu claim iteration."""

    wait_and_touch("claim_button", timeout=float(ARGS.get("claim_button_timeout", 10)))
    wait_and_touch("temu_checkbox", timeout=float(ARGS.get("temu_checkbox_timeout", 5)))
    wait_and_touch("confirm_button", timeout=float(ARGS.get("confirm_button_timeout", 5)))

    # 某些场景会出现额外的“关闭”按钮，尝试点击一次即可。
    try:
        close_template = load_template("close_button")
    except FileNotFoundError:
        close_template = None

    if close_template is not None and exists(close_template):
        touch(close_template)
        time.sleep(0.2)


if __name__ == "__main__":
    print(
        f"[Airtest] Temu claim automation started: products={PRODUCT_COUNT}, iterations={ITERATIONS}, templates={TEMPLATES_DIR}"
    )
    for iteration in range(ITERATIONS):
        print(f"[Airtest] Claim iteration {iteration + 1}/{ITERATIONS}")
        claim_once()
        time.sleep(float(ARGS.get("iteration_interval", 0.6)))
    print("[Airtest] Claim automation finished successfully")
