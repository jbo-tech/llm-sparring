#!/usr/bin/env python3
"""Refresh pricing.json depuis le référentiel LiteLLM.

Usage: python scripts/refresh_pricing.py
Fréquence conseillée : ~1 fois par trimestre.
"""

import json
import sys
import urllib.request
from pathlib import Path

SOURCE_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
TARGET = Path(__file__).resolve().parent.parent / "pricing.json"


def main() -> int:
    print(f"Fetching {SOURCE_URL} ...")
    with urllib.request.urlopen(SOURCE_URL, timeout=30) as response:
        raw = response.read()

    data = json.loads(raw)
    if not isinstance(data, dict) or len(data) < 100:
        print(f"ERROR: unexpected payload ({type(data).__name__}, len={len(data) if hasattr(data, '__len__') else '?'})")
        return 1

    TARGET.write_bytes(raw)
    print(f"Wrote {TARGET} ({len(data)} entries, {len(raw)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
