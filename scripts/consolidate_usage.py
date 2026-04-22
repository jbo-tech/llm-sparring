#!/usr/bin/env python3
"""Consolidation du journal usage.jsonl du serveur Sparring.

Usage:
  python scripts/consolidate_usage.py                  # résumé global
  python scripts/consolidate_usage.py --by-model       # breakdown par modèle
  python scripts/consolidate_usage.py --by-session     # top sessions (cost desc)
  python scripts/consolidate_usage.py --session <id>   # détail d'une session
  python scripts/consolidate_usage.py --day 2026-04-22 # une journée
  python scripts/consolidate_usage.py --json           # sortie JSON

Par défaut, lit ~/.config/mcp/llm-sparring/usage.jsonl (surchargeable via --file).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

DEFAULT_JOURNAL = Path("~/.config/mcp/llm-sparring/usage.jsonl").expanduser()


def iter_events(path: Path, day: str | None = None):
    """Itère les évènements du journal, filtrés sur --day si fourni (préfixe ISO)."""
    if not path.exists():
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if day and not (ev.get("ts") or "").startswith(day):
                continue
            yield ev


def _empty_bucket() -> dict:
    return {"cost": 0.0, "requests": 0, "errors": 0, "input_tokens": 0, "output_tokens": 0}


def _accumulate(bucket: dict, ev: dict):
    bucket["cost"] += ev.get("cost") or 0
    bucket["requests"] += 1
    bucket["input_tokens"] += ev.get("input_tokens") or 0
    bucket["output_tokens"] += ev.get("output_tokens") or 0
    if ev.get("error"):
        bucket["errors"] += 1


def summarize(events) -> dict:
    total = _empty_bucket()
    by_model: dict[str, dict] = defaultdict(_empty_bucket)
    by_session: dict[str, dict] = defaultdict(_empty_bucket)
    by_day: dict[str, dict] = defaultdict(_empty_bucket)
    by_tool: dict[str, dict] = defaultdict(_empty_bucket)

    for ev in events:
        _accumulate(total, ev)
        _accumulate(by_model[ev.get("model", "unknown")], ev)
        _accumulate(by_session[ev.get("session_id") or "(no session)"], ev)
        _accumulate(by_tool[ev.get("tool", "unknown")], ev)
        ts = ev.get("ts") or ""
        if ts:
            _accumulate(by_day[ts[:10]], ev)

    return {
        "total": total,
        "by_model": dict(by_model),
        "by_session": dict(by_session),
        "by_day": dict(by_day),
        "by_tool": dict(by_tool),
    }


def _fmt_row(name: str, bucket: dict) -> str:
    return (
        f"  {name:<40} "
        f"${bucket['cost']:>8.4f}  "
        f"req={bucket['requests']:<4}  "
        f"err={bucket['errors']:<3}  "
        f"tok={bucket['input_tokens']}/{bucket['output_tokens']}"
    )


def _print_section(title: str, mapping: dict, sort_key="cost", limit: int | None = None):
    print(f"\n{title}")
    print("-" * len(title))
    items = sorted(mapping.items(), key=lambda kv: kv[1].get(sort_key, 0), reverse=True)
    if limit:
        items = items[:limit]
    for name, bucket in items:
        print(_fmt_row(name, bucket))


def print_human(summary: dict, args):
    total = summary["total"]
    print(f"\n== Total ==")
    print(_fmt_row("total", total))

    _print_section("Par modèle", summary["by_model"])

    if args.by_session:
        _print_section("Top sessions (par coût)", summary["by_session"], limit=20)

    if args.by_tool:
        _print_section("Par outil", summary["by_tool"])

    if args.session:
        bucket = summary["by_session"].get(args.session)
        print(f"\n== Session {args.session} ==")
        if not bucket:
            print("  (aucun évènement)")
        else:
            print(_fmt_row("total", bucket))

    if not args.day:
        _print_section("Par jour", summary["by_day"], sort_key="cost", limit=10)


def main() -> int:
    parser = argparse.ArgumentParser(description="Consolidation usage.jsonl")
    parser.add_argument("--file", type=Path, default=DEFAULT_JOURNAL, help="Chemin du journal JSONL")
    parser.add_argument("--session", help="Filtre sur un session_id spécifique")
    parser.add_argument("--day", help="Filtre sur une journée (préfixe YYYY-MM-DD)")
    parser.add_argument("--by-model", action="store_true", help="(toujours affiché) — conservé pour compatibilité")
    parser.add_argument("--by-session", action="store_true", help="Top sessions par coût")
    parser.add_argument("--by-tool", action="store_true", help="Breakdown par outil")
    parser.add_argument("--json", action="store_true", help="Sortie JSON (pour scripts)")
    args = parser.parse_args()

    if not args.file.exists():
        print(f"Journal introuvable: {args.file}", file=sys.stderr)
        return 1

    events = list(iter_events(args.file, day=args.day))
    if args.session:
        events = [e for e in events if e.get("session_id") == args.session]

    summary = summarize(events)

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False, default=float))
        return 0

    print_human(summary, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
