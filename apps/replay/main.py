"""
Replay CLI 入口。
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apps.replay.exporter import DEFAULT_EXPORT_ROOT
from apps.replay.service import ReplayService
from libs.storage.database import get_async_session


def _parse_datetime(raw_value: str, *, is_end: bool) -> datetime:
    if len(raw_value) == 10:
        parsed = datetime.fromisoformat(raw_value).replace(tzinfo=UTC)
        if is_end:
            parsed = parsed + timedelta(days=1) - timedelta(seconds=1)
        return parsed

    parsed = datetime.fromisoformat(raw_value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


async def run_cli(
    *,
    start: datetime,
    end: datetime,
    session_factory: Callable[[], AbstractAsyncContextManager],
    export_root: Path,
):
    async with session_factory() as session:
        service = ReplayService(session)
        return await service.run(start=start, end=end, export_root=export_root)


def main(
    argv: list[str] | None = None,
    *,
    session_factory: Callable[[], AbstractAsyncContextManager] = get_async_session,
    export_root: Path = DEFAULT_EXPORT_ROOT,
) -> int:
    parser = argparse.ArgumentParser(description="Replay historical candidate orders.")
    parser.add_argument("--start", required=True, help="Replay start date or datetime.")
    parser.add_argument("--end", required=True, help="Replay end date or datetime.")
    args = parser.parse_args(argv)

    start = _parse_datetime(args.start, is_end=False)
    end = _parse_datetime(args.end, is_end=True)
    summary = asyncio.run(
        run_cli(
            start=start,
            end=end,
            session_factory=session_factory,
            export_root=export_root,
        )
    )

    print(f"Replay run: {summary.id}")
    print(f"Candidates: {summary.candidate_count}")
    print(f"Tradable: {summary.tradable_count}")
    print(f"Filled: {summary.simulated_fill_count}")
    print(f"Cumulative PnL: {summary.cumulative_pnl}")
    print(f"Export dir: {summary.export_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
