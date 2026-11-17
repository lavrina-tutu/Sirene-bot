#!/usr/bin/env python3
"""Deterministic back-of-the-envelope capacity estimator for system design.

The script intentionally avoids server-count recommendations: those require a
benchmark of the actual workload and consistency/index configuration.
"""

from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation
from typing import Any


SECONDS_PER_DAY = Decimal("86400")
SECONDS_PER_30_DAYS = SECONDS_PER_DAY * Decimal("30")
SECONDS_PER_365_DAYS = SECONDS_PER_DAY * Decimal("365")


def decimal_arg(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError(f"not a number: {value}") from exc
    if not parsed.is_finite() or parsed < 0:
        raise argparse.ArgumentTypeError("value must be a finite non-negative number")
    return parsed


def positive_decimal_arg(value: str) -> Decimal:
    parsed = decimal_arg(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def headroom_arg(value: str) -> Decimal:
    parsed = positive_decimal_arg(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("headroom must be at least 1.0")
    return parsed


def availability_arg(value: str) -> Decimal:
    parsed = positive_decimal_arg(value)
    if parsed > 100:
        raise argparse.ArgumentTypeError("availability must be at most 100")
    return parsed


def compute(inputs: dict[str, Decimal]) -> dict[str, Decimal]:
    average_read_rps = inputs["dau"] * inputs["reads_per_user_day"] / SECONDS_PER_DAY
    average_write_rps = inputs["dau"] * inputs["writes_per_user_day"] / SECONDS_PER_DAY
    peak_multiplier = inputs["peak_factor"] * inputs["headroom"]
    peak_read_rps = average_read_rps * peak_multiplier
    peak_write_rps = average_write_rps * peak_multiplier

    daily_write_bytes = inputs["dau"] * inputs["writes_per_user_day"] * inputs["write_bytes"]
    raw_retention_bytes = daily_write_bytes * inputs["retention_days"]
    physical_retention_bytes = (
        raw_retention_bytes * inputs["replication_factor"] * inputs["headroom"]
    )

    error_budget_fraction = Decimal("1") - inputs["availability"] / Decimal("100")

    return {
        "average_read_rps": average_read_rps,
        "average_write_rps": average_write_rps,
        "peak_read_rps": peak_read_rps,
        "peak_write_rps": peak_write_rps,
        "peak_total_rps": peak_read_rps + peak_write_rps,
        "peak_read_egress_bytes_per_second": peak_read_rps * inputs["read_bytes"],
        "peak_write_ingress_bytes_per_second": peak_write_rps * inputs["write_bytes"],
        "daily_raw_write_bytes": daily_write_bytes,
        "raw_retention_bytes": raw_retention_bytes,
        "physical_retention_bytes": physical_retention_bytes,
        "error_budget_fraction": error_budget_fraction,
        "allowed_bad_seconds_30_days": SECONDS_PER_30_DAYS * error_budget_fraction,
        "allowed_bad_seconds_365_days": SECONDS_PER_365_DAYS * error_budget_fraction,
    }


def compact_number(value: Decimal) -> str:
    magnitude = abs(value)
    units = [
        (Decimal("1e12"), "T"),
        (Decimal("1e9"), "B"),
        (Decimal("1e6"), "M"),
        (Decimal("1e3"), "K"),
    ]
    for threshold, suffix in units:
        if magnitude >= threshold:
            return f"{value / threshold:.3g}{suffix}"
    if magnitude >= 100:
        return f"{value:.0f}"
    if magnitude >= 1:
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{value:.3g}"


def human_bytes(value: Decimal) -> str:
    units = ["B", "kB", "MB", "GB", "TB", "PB", "EB"]
    current = value
    unit = units[0]
    for unit in units:
        if abs(current) < 1000 or unit == units[-1]:
            break
        current /= Decimal("1000")
    return f"{current:.3g} {unit}"


def human_duration(seconds: Decimal) -> str:
    if seconds == 0:
        return "0 s"
    if seconds < 60:
        return f"{seconds:.3g} s"
    minutes = seconds / Decimal("60")
    if minutes < 60:
        return f"{minutes:.3g} min"
    hours = minutes / Decimal("60")
    if hours < 48:
        return f"{hours:.3g} h"
    days = hours / Decimal("24")
    return f"{days:.3g} d"


def decimal_to_json(value: Decimal) -> float:
    return float(value)


def render_markdown(inputs: dict[str, Decimal], results: dict[str, Decimal]) -> str:
    lines = [
        "# Capacity envelope",
        "",
        "## Assumptions",
        "",
        f"- DAU / active units: {compact_number(inputs['dau'])}",
        (
            "- Actions per active unit per day: "
            f"{compact_number(inputs['reads_per_user_day'])} reads, "
            f"{compact_number(inputs['writes_per_user_day'])} writes"
        ),
        (
            "- Payload: "
            f"{human_bytes(inputs['read_bytes'])} read, "
            f"{human_bytes(inputs['write_bytes'])} write"
        ),
        (
            "- Peak factor × headroom: "
            f"{compact_number(inputs['peak_factor'])} × {compact_number(inputs['headroom'])}"
        ),
        (
            "- Retention / replication: "
            f"{compact_number(inputs['retention_days'])} days / "
            f"{compact_number(inputs['replication_factor'])} copies"
        ),
        f"- Availability target: {inputs['availability']}%",
        "",
        "## Traffic",
        "",
        "| Metric | Average | Peak incl. headroom |",
        "|---|---:|---:|",
        (
            "| Reads | "
            f"{compact_number(results['average_read_rps'])} RPS | "
            f"{compact_number(results['peak_read_rps'])} RPS |"
        ),
        (
            "| Writes | "
            f"{compact_number(results['average_write_rps'])} RPS | "
            f"{compact_number(results['peak_write_rps'])} RPS |"
        ),
        "",
        f"- Peak total: {compact_number(results['peak_total_rps'])} RPS",
        (
            "- Peak payload bandwidth: "
            f"{human_bytes(results['peak_write_ingress_bytes_per_second'])}/s ingress, "
            f"{human_bytes(results['peak_read_egress_bytes_per_second'])}/s egress"
        ),
        "",
        "## Storage",
        "",
        f"- Raw writes per day: {human_bytes(results['daily_raw_write_bytes'])}",
        f"- Raw data at retention: {human_bytes(results['raw_retention_bytes'])}",
        (
            "- Replicated data incl. headroom: "
            f"{human_bytes(results['physical_retention_bytes'])}"
        ),
        "- Excludes indexes, WAL/logs, metadata, backups, compaction and temporary migration space.",
        "",
        "## Error budget",
        "",
        (
            f"- 30-day window: {human_duration(results['allowed_bad_seconds_30_days'])} "
            "of bad events/time if time-based"
        ),
        (
            f"- 365-day window: {human_duration(results['allowed_bad_seconds_365_days'])} "
            "of bad events/time if time-based"
        ),
        "",
        "## Interpretation guardrails",
        "",
        "- Treat results as order-of-magnitude estimates, not a capacity promise.",
        "- Add read/write amplification from indexes, replicas, fanout, retries and projections.",
        "- Size servers/partitions only from a representative benchmark and failure headroom.",
    ]
    return "\n".join(lines)


def render_json(inputs: dict[str, Decimal], results: dict[str, Decimal]) -> str:
    payload: dict[str, Any] = {
        "units": {
            "storage": "decimal bytes",
            "rate": "requests or bytes per second",
            "availability_window": "seconds",
        },
        "inputs": {key: decimal_to_json(value) for key, value in inputs.items()},
        "results": {key: decimal_to_json(value) for key, value in results.items()},
        "excludes": [
            "indexes",
            "WAL and logs",
            "metadata",
            "backups",
            "compaction",
            "temporary migration space",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Estimate RPS, payload bandwidth, storage and error budget."
    )
    parser.add_argument("--dau", type=positive_decimal_arg, help="Daily active users/units")
    parser.add_argument("--reads-per-user-day", type=decimal_arg, default=Decimal("0"))
    parser.add_argument("--writes-per-user-day", type=decimal_arg, default=Decimal("0"))
    parser.add_argument("--read-bytes", type=decimal_arg, default=Decimal("0"))
    parser.add_argument("--write-bytes", type=decimal_arg, default=Decimal("0"))
    parser.add_argument("--retention-days", type=decimal_arg, default=Decimal("0"))
    parser.add_argument("--peak-factor", type=positive_decimal_arg, default=Decimal("1"))
    parser.add_argument("--replication-factor", type=positive_decimal_arg, default=Decimal("1"))
    parser.add_argument("--headroom", type=headroom_arg, default=Decimal("1"))
    parser.add_argument("--availability", type=availability_arg, default=Decimal("99.9"))
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--self-test", action="store_true", help="Run deterministic checks and exit")
    return parser


def run_self_test() -> None:
    inputs = {
        "dau": Decimal("86400"),
        "reads_per_user_day": Decimal("1"),
        "writes_per_user_day": Decimal("1"),
        "read_bytes": Decimal("200"),
        "write_bytes": Decimal("100"),
        "retention_days": Decimal("10"),
        "peak_factor": Decimal("2"),
        "replication_factor": Decimal("3"),
        "headroom": Decimal("1.25"),
        "availability": Decimal("99"),
    }
    results = compute(inputs)
    assert results["average_read_rps"] == Decimal("1")
    assert results["average_write_rps"] == Decimal("1")
    assert results["peak_total_rps"] == Decimal("5.00")
    assert results["raw_retention_bytes"] == Decimal("86400000")
    assert results["physical_retention_bytes"] == Decimal("324000000.00")
    assert results["allowed_bad_seconds_365_days"] == Decimal("315360.00")
    print("self-test: OK")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.self_test:
        run_self_test()
        return
    if args.dau is None:
        parser.error("--dau is required unless --self-test is used")

    inputs = {
        "dau": args.dau,
        "reads_per_user_day": args.reads_per_user_day,
        "writes_per_user_day": args.writes_per_user_day,
        "read_bytes": args.read_bytes,
        "write_bytes": args.write_bytes,
        "retention_days": args.retention_days,
        "peak_factor": args.peak_factor,
        "replication_factor": args.replication_factor,
        "headroom": args.headroom,
        "availability": args.availability,
    }
    results = compute(inputs)
    if args.format == "json":
        print(render_json(inputs, results))
    else:
        print(render_markdown(inputs, results))


if __name__ == "__main__":
    main()
