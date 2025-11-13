"""Example: run the Temu claim Airtest script via Python."""

from __future__ import annotations

from pathlib import Path

from scripts.temu_claim_airtest.launcher import run_airtest_claim

if __name__ == "__main__":
    templates = Path(__file__).resolve().parents[1] / "temu_claim.air" / "templates"
    run_airtest_claim(
        product_count=5,
        iterations=4,
        template_dir=templates,
        device_uri="OSX:///",
    )
