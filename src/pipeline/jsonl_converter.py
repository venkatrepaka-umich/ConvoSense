#!/usr/bin/env python3
"""Write multi-turn conversations to one JSONL file per brand.

Each input CSV row becomes one JSON object with the conversation and the last
customer message. Brand names stay as folders:

    data/conversations_multi_jsonl/<brand>/conversations.jsonl
"""

import argparse
import csv
import json
import sys
from pathlib import Path

csv.field_size_limit(sys.maxsize)


def brand_csvs(input_path):
    """Return (brand, csv path) pairs for one brand file or a directory of them."""
    if input_path.is_file():
        return [(input_path.stem, input_path)]
    return [
        (path.stem, path)
        for path in sorted(input_path.glob("*.csv"))
        if path.is_file()
    ]


def convert_brand(brand, csv_path, output_root):
    output_path = output_root / brand / "conversations.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with csv_path.open(newline="", encoding="utf-8") as source, output_path.open(
        "w", encoding="utf-8"
    ) as destination:
        for row in csv.DictReader(source):
            record = {
                "id": row["conversation_id"],
                "brand": brand,
                "conversation": row["conversation"],
                "last_customer_message": row["last_customer_message"],
            }
            destination.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1
    print(f"Wrote {written} conversations to {output_path}")
    return written


def main():
    parser = argparse.ArgumentParser(
        description="Convert multi-turn conversation CSVs to JSONL, one brand folder each."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="data/conversations_multi",
        help="Brand CSV, or a directory of <brand>.csv files (default: data/conversations_multi)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="data/conversations_multi_jsonl",
        help="Directory for per-brand JSONL folders (default: data/conversations_multi_jsonl)",
    )
    args = parser.parse_args()
    input_path = Path(args.input)
    output_root = Path(args.output)
    brands = brand_csvs(input_path)
    if not brands:
        raise SystemExit(f"No conversation CSV files found in {input_path}")
    for brand, csv_path in brands:
        convert_brand(brand, csv_path, output_root)


if __name__ == "__main__":
    main()
