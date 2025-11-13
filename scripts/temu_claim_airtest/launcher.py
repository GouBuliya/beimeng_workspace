"""Programmatic runner for the Temu Airtest claim workflow."""

from __future__ import annotations

from pathlib import Path

from airtest.cli.parser import cli_setup
from airtest.cli.runner import AirtestCase

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AIRTEST_DIR = PROJECT_ROOT / "scripts" / "temu_claim_airtest" / "temu_claim.air"
TEMPLATE_DIR = AIRTEST_DIR / "templates"


class TemuClaimTestCase(AirtestCase):
    """Airtest test case wrapper for the Temu claim workflow."""

    def setUp(self) -> None:  # type: ignore[override]
        super().setUp()


def run_airtest_claim(
    *,
    product_count: int,
    iterations: int,
    template_dir: Path | None = None,
    device_uri: str = "OSX:///",
    post_click_delay: float = 0.25,
    iteration_interval: float = 0.6,
) -> None:
    """Run the Airtest claim flow programmatically."""

    if product_count <= 0:
        raise ValueError("product_count must be positive")
    if iterations <= 0:
        raise ValueError("iterations must be positive")

    if template_dir is None:
        template_dir = TEMPLATE_DIR

    if not template_dir.exists():
        raise FileNotFoundError(f"Template directory not found: {template_dir}")

    script_path = AIRTEST_DIR / "script.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Airtest script not found: {script_path}")

    args = {
        "product_count": str(product_count),
        "iterations": str(iterations),
        "template_dir": str(template_dir.resolve()),
        "device_uri": device_uri,
        "post_click_delay": str(post_click_delay),
        "iteration_interval": str(iteration_interval),
    }

    airtest_args = ["--device", device_uri]
    if not cli_setup(airtest_args):
        raise RuntimeError("Failed to initialise Airtest CLI")

    case = TemuClaimTestCase(script=str(script_path), device=device_uri)
    case.setUpClass()
    case.args = args

    try:
        case.run_script(str(script_path))
    finally:
        case.tearDown()


__all__ = ["run_airtest_claim"]
