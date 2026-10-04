#!/usr/bin/env python3
"""Build Potato annotation packages, one folder per annotator.

Conversations are sampled at random, with no overlap between annotators or
batches. Each annotator gets several batch folders so they can do more if they
want to:

    annotator_packages/
      manifest.json
      annotator_01/
        README.md
        batch_1/{data.jsonl, config.yaml, run.sh, run.bat}
        batch_2/...
      annotator_01.zip
"""

import argparse
import html
import json
import random
import re
import shutil
import stat
import sys
from pathlib import Path

DEFAULT_INPUT = "data/conversations_multi_jsonl/AmazonHelp/conversations.jsonl"
POTATO_VERSION = "2.9.4"

TURN_STYLE = (
    "display:block;color:{fg};background-color:{bg};padding:8px 12px;"
    "margin-bottom:8px;border-radius:6px;"
)
ROLES = {
    "customer": ("#0b3a82", "#dbeafe"),
    "agent": ("#9a3412", "#ffedd5"),
}

RUN_SH = f"""#!/usr/bin/env bash
# Starts the annotation tool. Needs Python 3.
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv || exit 1
  .venv/bin/pip install "potato-annotation=={POTATO_VERSION}" || exit 1
fi
echo "Open http://localhost:8000 in your browser. Press Ctrl+C here when you are done."
.venv/bin/potato start config.yaml -p 8000
"""

RUN_BAT = f"""@echo off
rem Starts the annotation tool. Needs Python 3.
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv || exit /b 1
  .venv\\Scripts\\pip install "potato-annotation=={POTATO_VERSION}" || exit /b 1
)
echo Open http://localhost:8000 in your browser. Press Ctrl+C here when you are done.
.venv\\Scripts\\potato start config.yaml -p 8000
"""

README = """# Conversation Sense annotation - {annotator}

## What you do

Read each customer-support conversation and pick its sense, as described in
the annotation guidelines: {guidelines}

## Requirements

Python 3 (python.org). Nothing else; the script installs the annotation tool
(Potato {potato}) into the batch folder the first time.

## Steps

1. Unzip this folder. Open `batch_1`.
2. Start the tool:
   - Mac/Linux: open a terminal in `batch_1` and run `bash run.sh`
   - Windows: double-click `run.bat`

   The first run takes a minute or two to install.
3. Open <http://localhost:8000> in your browser and log in with the username
   `{annotator}` (exactly this, so your labels are attributed to you).
4. Label all {per_batch} conversations. Your answers save automatically and you
   can stop and resume later by running the script again.
5. Press Ctrl+C in the terminal to stop the tool.

## Want to do more?

`batch_2` is a separate set of {per_batch} conversations. Repeat the steps in
`batch_2`. Run only one batch at a time (they share port 8000).

## Send back

When a batch is finished, zip the whole `annotation_output` folder inside it
and send the zip to the contact below:

- `batch_N/annotation_output/` -> `annotation_output.zip`

Please name the zip with your username and batch, for example
`{annotator}_batch_1.zip`. Do this for each batch you completed.

## Questions

{contact}
"""


def render_conversation(text):
    """Turn '[customer] - a | [agent] - b' into the colored HTML turns Potato shows."""
    parts = []
    for turn in text.split(" | "):
        match = re.match(r"\[(customer|agent)\] - (.*)", turn, re.DOTALL)
        if not match:
            raise ValueError(f"Unrecognised turn: {turn[:80]!r}")
        role, body = match.groups()
        fg, bg = ROLES[role]
        style = TURN_STYLE.format(fg=fg, bg=bg)
        parts.append(f'<div style="{style}"><b>{role}</b> — {html.escape(body)}</div>')
    return "".join(parts)


def to_record(row):
    return {
        "id": row["id"],
        "brand": row["brand"],
        "conversation": render_conversation(row["conversation"]),
        "last_customer_message": row["last_customer_message"],
    }


def read_rows(path):
    with path.open(encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def make_config(template_path):
    """Point the template config at data.jsonl, keeping its comments and layout."""
    text = template_path.read_text(encoding="utf-8")
    text, count = re.subn(
        r'(data_files:\s*\n\s*-\s*)"[^"]*"', r'\1"data.jsonl"', text, count=1
    )
    if count != 1:
        raise SystemExit(f"Could not find data_files entry in {template_path}")
    return text


def write_batch(folder, rows, config_text, rng):
    folder.mkdir(parents=True)
    rows = rows[:]
    rng.shuffle(rows)
    with (folder / "data.jsonl").open("w", encoding="utf-8") as out:
        for row in rows:
            out.write(json.dumps(to_record(row), ensure_ascii=False) + "\n")
    (folder / "config.yaml").write_text(config_text, encoding="utf-8")
    run_sh = folder / "run.sh"
    run_sh.write_text(RUN_SH, encoding="utf-8", newline="\n")
    run_sh.chmod(run_sh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    (folder / "run.bat").write_text(RUN_BAT, encoding="utf-8", newline="\r\n")


def main():
    parser = argparse.ArgumentParser(
        description="Create per-annotator Potato folders with random, non-overlapping conversations."
    )
    parser.add_argument("input", nargs="?", default=DEFAULT_INPUT, help=f"JSONL file (default: {DEFAULT_INPUT})")
    parser.add_argument("-o", "--output", default="annotator_packages", help="Output directory (default: annotator_packages)")
    parser.add_argument("--annotators", type=int, default=6)
    parser.add_argument("--batches", type=int, default=2, help="Folders per annotator")
    parser.add_argument("--per-batch", type=int, default=100, help="Conversations per folder")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--config", default="potato/config.yaml", help="Potato config used as the template")
    parser.add_argument("--guidelines", default="<add link to guidelines>")
    parser.add_argument("--contact", default="<add your email>")
    args = parser.parse_args()

    rows = read_rows(Path(args.input))
    ids = [row["id"] for row in rows]
    if len(set(ids)) != len(ids):
        raise SystemExit("Input has duplicate ids")
    needed = args.annotators * args.batches * args.per_batch
    if len(rows) < needed:
        raise SystemExit(f"Need {needed} conversations but input has {len(rows)}")

    rng = random.Random(args.seed)
    sample = rng.sample(rows, needed)
    config_text = make_config(Path(args.config))

    output = Path(args.output)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    manifest = {}
    cursor = 0
    for a in range(1, args.annotators + 1):
        annotator = f"annotator_{a:02d}"
        folder = output / annotator
        for b in range(1, args.batches + 1):
            chunk = sample[cursor : cursor + args.per_batch]
            cursor += args.per_batch
            write_batch(folder / f"batch_{b}", chunk, config_text, rng)
            manifest[f"{annotator}/batch_{b}"] = [row["id"] for row in chunk]
        (folder / "README.md").write_text(
            README.format(
                annotator=annotator,
                per_batch=args.per_batch,
                potato=POTATO_VERSION,
                guidelines=args.guidelines,
                contact=args.contact,
            ),
            encoding="utf-8",
        )
        shutil.make_archive(str(output / annotator), "zip", output, annotator)
        print(f"Wrote {folder} ({args.batches} x {args.per_batch}) and {annotator}.zip")

    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {needed} conversations to {output} (manifest.json is for you only; do not share)")


if __name__ == "__main__":
    sys.exit(main())
