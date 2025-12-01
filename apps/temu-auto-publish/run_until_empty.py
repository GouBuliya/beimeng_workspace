"""CLI entry that repeatedly runs the publish workflow until the selection
table is empty or invalid."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from loguru import logger
from config.settings import settings
from src.browser.login_controller import LoginController
from src.data_processor.selection_table_queue import (
    SelectionBatch,
    SelectionTableEmptyError,
    SelectionTableFormatError,
    SelectionTableQueue,
)
from src.workflows.complete_publish_workflow import CompletePublishWorkflow

DEFAULT_BATCH_SIZE = max(1, min(settings.business.collect_count, 5))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Temu publish workflow repeatedly until the selection table is empty.",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the selection Excel/CSV file",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Number of rows to process per round (default: business collect_count)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Seconds to wait between rounds (default: 5s)",
    )
    parser.add_argument(
        "--start-round",
        type=int,
        default=1,
        help="Round index to start from (1-based). Determines which products to edit in the list.",
    )
    parser.add_argument(
        "--headless",
        dest="headless",
        action="store_true",
        help="Force headless browser",
    )
    parser.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="Force headed browser",
    )
    parser.add_argument(
        "--archive",
        dest="archive",
        action="store_true",
        help="Archive processed batches to data/output/processed (default: enabled)",
    )
    parser.add_argument(
        "--no-archive",
        dest="archive",
        action="store_false",
        help="Disable batch archiving",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Log level (default: INFO)",
    )
    parser.set_defaults(headless=None, archive=True)
    return parser.parse_args()


def configure_logger(level: str) -> None:
    logger.remove()
    logger.add(sys.stdout, level=level.upper())


async def navigate_to_common_collect_box(
    login_ctrl: LoginController, target_url: str
) -> None:
    """Jump back to the shared collection box to prepare for the next round."""

    page = login_ctrl.browser_manager.page
    if page is None:
        return

    try:
        await page.goto(target_url, timeout=60_000)
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(800)
        logger.info("Returned to common collect box for the next round")
    except Exception as exc:  # pragma: no cover - tolerate transient navigation errors
        logger.warning("Failed to navigate to common collect box: {}", exc)


async def run_batch(
    batch: SelectionBatch,
    *,
    selection_table_path: Path,
    headless: bool | None,
    execution_round: int,
    login_ctrl: LoginController,
) -> bool:
    workflow = CompletePublishWorkflow(
        headless=headless,
        selection_table=selection_table_path,
        selection_rows_override=batch.rows,
        execution_round=execution_round,
        login_ctrl=login_ctrl,
        reuse_existing_login=True,
    )
    result = await workflow.execute_async()

    logger.info(
        f"Batch completed: success={result.total_success}, "
        f"stages={[stage.name for stage in result.stages]}, errors={result.errors}"
    )

    return result.total_success


async def main_async() -> None:
    args = parse_args()
    configure_logger(args.log_level)
    batch_size = args.batch_size or DEFAULT_BATCH_SIZE
    execution_round = max(1, args.start_round)

    selection_path = Path(args.input).expanduser().resolve()
    queue = SelectionTableQueue(selection_path)
    login_ctrl = LoginController()
    target_collect_url = "https://erp.91miaoshou.com/common_collect_box/items"

    logger.info(
        f"Start continuous publish: input={selection_path}, batch_size={batch_size}, "
        f"interval={args.interval:.1f}s, start_round={execution_round}"
    )

    try:
        while True:
            try:
                batch = queue.pop_next_batch(batch_size)
            except SelectionTableEmptyError as exc:
                logger.success(str(exc))
                break
            except SelectionTableFormatError as exc:
                logger.error("Selection table format error: {}", exc)
                break

            logger.info("Current batch size={} (round {})", batch.size, execution_round)

            try:
                success = await run_batch(
                    batch,
                    selection_table_path=selection_path,
                    headless=args.headless,
                    execution_round=execution_round,
                    login_ctrl=login_ctrl,
                )
            except Exception as exc:
                logger.exception(f"Publish workflow raised: {exc}")
                queue.return_batch(batch.rows)
                raise SystemExit(1) from exc

            if success:
                if args.archive:
                    queue.archive_batch(batch.rows, suffix="success")
                logger.success("Batch finished, continue to next round...")
                execution_round += 1
                if queue.has_pending_rows():
                    await navigate_to_common_collect_box(login_ctrl, target_collect_url)
            else:
                queue.return_batch(batch.rows)
                if args.archive:
                    queue.archive_batch(batch.rows, suffix="failed")
                logger.error("Batch failed, rolled back selection table, exit.")
                raise SystemExit(1)

            if args.interval > 0:
                logger.debug("Waiting %.1f seconds before next round", args.interval)
                await asyncio.sleep(args.interval)

    except KeyboardInterrupt:
        logger.warning("Interrupted by user, exiting continuous publish")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
