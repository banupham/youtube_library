#!/usr/bin/env python3
"""Inspect exported Android AccessibilityService snapshots locally.

This tool is for parser development/validation. It does not upload data.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="JSONL exported from Android app internal snapshot storage")
    parser.add_argument("--show-text", action="store_true", help="Also print common text/contentDescription values")
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()

    surfaces = Counter()
    view_ids = Counter()
    classes = Counter()
    texts = Counter()
    descriptions = Counter()
    snapshots = 0
    nodes = 0

    with args.input.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            snapshots += 1
            surface = (payload.get("surface_guess") or {}).get("surface") or "unknown"
            surfaces[surface] += 1
            for node in payload.get("nodes") or []:
                nodes += 1
                if node.get("view_id"):
                    view_ids[str(node["view_id"])] += 1
                if node.get("class_name"):
                    classes[str(node["class_name"])] += 1
                if args.show_text and node.get("text"):
                    texts[str(node["text"])] += 1
                if args.show_text and node.get("content_description"):
                    descriptions[str(node["content_description"])] += 1

    print(f"Snapshots: {snapshots}")
    print(f"Evidence nodes: {nodes}")
    print("\nSurface guesses:")
    for key, count in surfaces.most_common():
        print(f"  {key:16} {count}")

    print("\nTop view IDs:")
    for value, count in view_ids.most_common(args.top):
        print(f"  {count:5}  {value}")

    print("\nTop classes:")
    for value, count in classes.most_common(args.top):
        print(f"  {count:5}  {value}")

    if args.show_text:
        print("\nTop text values (local-sensitive):")
        for value, count in texts.most_common(args.top):
            print(f"  {count:5}  {value[:180]}")
        print("\nTop content descriptions (local-sensitive):")
        for value, count in descriptions.most_common(args.top):
            print(f"  {count:5}  {value[:240]}")


if __name__ == "__main__":
    main()
