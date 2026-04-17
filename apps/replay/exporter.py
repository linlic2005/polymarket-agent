"""
Replay 导出器。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from libs.models.schemas import (
    ReplayCandidateResult,
    ReplayExportManifest,
    ReplayRunSummary,
    ReplayTradeResult,
)

DEFAULT_EXPORT_ROOT = Path("artifacts") / "replay"


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def export_replay_artifacts(
    summary: ReplayRunSummary,
    candidate_results: list[ReplayCandidateResult],
    trade_results: list[ReplayTradeResult],
    equity_curve: list[dict[str, Any]],
    *,
    export_root: Path | None = None,
) -> ReplayExportManifest:
    base_root = export_root or DEFAULT_EXPORT_ROOT
    export_dir = base_root / str(summary.id)
    export_dir.mkdir(parents=True, exist_ok=True)

    summary_dict = summary.model_dump(mode="json")
    candidate_dicts = [row.model_dump(mode="json") for row in candidate_results]
    trade_dicts = [row.model_dump(mode="json") for row in trade_results]

    summary_csv = export_dir / "summary.csv"
    summary_json = export_dir / "summary.json"
    candidate_csv = export_dir / "candidate_results.csv"
    candidate_json = export_dir / "candidate_results.json"
    trade_csv = export_dir / "trade_results.csv"
    trade_json = export_dir / "trade_results.json"
    equity_csv = export_dir / "equity_curve.csv"
    manifest_json = export_dir / "manifest.json"

    _write_csv(summary_csv, [summary_dict])
    _write_json(summary_json, summary_dict)
    _write_csv(candidate_csv, candidate_dicts)
    _write_json(candidate_json, candidate_dicts)
    _write_csv(trade_csv, trade_dicts)
    _write_json(trade_json, trade_dicts)
    _write_csv(equity_csv, equity_curve)

    manifest = ReplayExportManifest(
        run_id=summary.id,
        export_dir=str(export_dir),
        files={
            "summary_csv": str(summary_csv),
            "summary_json": str(summary_json),
            "candidate_csv": str(candidate_csv),
            "candidate_json": str(candidate_json),
            "trade_csv": str(trade_csv),
            "trade_json": str(trade_json),
            "equity_csv": str(equity_csv),
            "manifest_json": str(manifest_json),
        },
    )
    _write_json(manifest_json, manifest.model_dump(mode="json"))
    return manifest
