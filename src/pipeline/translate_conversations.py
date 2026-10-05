#!/usr/bin/env python3
"""Keep English turns, translate Spanish to English, and drop every other language.

Each conversation stays one line, with turns separated by `` | ``. A line is
left out when any message is not English or Spanish, and empty conversations
are not written. Spanish messages are replaced with an offline Argos
translation. ``[link]`` and ``[image]`` are left unchanged.

Reads a brand folder of sequenced conversations and writes the same two files
under the cleaned output folder.
"""

import argparse
import csv
import re
import sys
from pathlib import Path

import numpy as np
import argostranslate.translate
import fasttext

from sequence_conversations import last_customer_text

csv.field_size_limit(sys.maxsize)
fasttext.FastText.eprint = lambda *_args, **_kwargs: None


def _predict_compatible(self, text, k=1, threshold=0.0, on_unicode_error="strict"):
    """fasttext 0.9 calls np.array(..., copy=False), which NumPy 2 rejects."""
    if "\n" in text:
        raise ValueError("predict processes one line at a time (remove '\\n')")
    predictions = self.f.predict(text + "\n", k, threshold, on_unicode_error)
    if predictions:
        probs, labels = zip(*predictions)
    else:
        probs, labels = ([], ())
    return labels, np.asarray(probs)


fasttext.FastText._FastText.predict = _predict_compatible

TURN_PATTERN = re.compile(r"^\[(customer|agent)\] - (.*)$")
PLACEHOLDER_SPLIT = re.compile(r"(\[link\]|\[image\])")
LETTER_PATTERN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]")
KEEP_LANGUAGES = {"en", "es"}
MIN_CONFIDENCE = 0.45

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "models" / "lid.176.ftz"


def load_detector():
    return fasttext.load_model(str(MODEL_PATH))


def detectable_text(text):
    cleaned = PLACEHOLDER_SPLIT.sub(" ", text)
    return " ".join(cleaned.split())


def detect_language(detector, text):
    """Return 'en', 'es', 'neutral', or 'other'."""
    sample = detectable_text(text)
    if not LETTER_PATTERN.search(sample):
        return "neutral"
    labels, scores = detector.predict(sample.replace("\n", " "), k=1)
    language = labels[0].removeprefix("__label__")
    if language in KEEP_LANGUAGES and float(scores[0]) >= MIN_CONFIDENCE:
        return language
    return "other"


def translate_spanish(text, cache):
    cached = cache.get(text)
    if cached is not None:
        return cached

    pieces = []
    for piece in PLACEHOLDER_SPLIT.split(text):
        if piece in ("[link]", "[image]") or not piece.strip():
            pieces.append(piece)
            continue
        pieces.append(argostranslate.translate.translate(piece, "es", "en"))
    translated = " ".join("".join(pieces).split())
    cache[text] = translated
    return translated


def clean_message(detector, message, cache):
    """Translate a Spanish message. Return '' when the message is not English or Spanish."""
    message = " ".join(message.split())
    if not message:
        return ""
    language = detect_language(detector, message)
    if language == "other":
        return ""
    if language == "es":
        return translate_spanish(message, cache)
    return message


def clean_conversation(detector, conversation, cache):
    """Keep the conversation only when every message is English or Spanish."""
    turns = []
    messages = []
    for turn in conversation.split(" | "):
        turn = turn.strip()
        if not turn:
            continue
        match = TURN_PATTERN.match(turn)
        if not match:
            return "", ""
        speaker, message = match.group(1), match.group(2)
        cleaned = clean_message(detector, message, cache)
        if not cleaned:
            return "", ""
        turns.append(f"[{speaker}] - {cleaned}")
        messages.append((speaker, cleaned))
    last_customer_message = last_customer_text(messages)
    if not turns or not last_customer_message:
        return "", ""
    return " | ".join(turns), last_customer_message


def clean_brand(input_dir, output_dir, detector=None, cache=None):
    if detector is None:
        detector = load_detector()
    if cache is None:
        cache = {}
    input_conversations = input_dir / "conversation.csv"
    input_last = input_dir / "last_customer_message.csv"
    output_dir.mkdir(parents=True, exist_ok=True)

    kept = 0
    read = 0
    with input_conversations.open(encoding="utf-8", newline="") as conversation_handle, input_last.open(
        encoding="utf-8", newline=""
    ) as last_handle, (output_dir / "conversation.csv").open(
        "w", encoding="utf-8", newline=""
    ) as out_conversation_handle, (output_dir / "last_customer_message.csv").open(
        "w", encoding="utf-8", newline=""
    ) as out_last_handle:
        conversations = csv.DictReader(conversation_handle)
        last_rows = csv.DictReader(last_handle)
        conversation_writer = csv.writer(out_conversation_handle)
        last_writer = csv.writer(out_last_handle)
        conversation_writer.writerow(["conversation_id", "conversation"])
        last_writer.writerow(["conversation_id", "last_customer_message"])

        for conversation_row, last_row in zip(conversations, last_rows):
            read += 1
            conversation_id = conversation_row["conversation_id"]
            if conversation_id != last_row["conversation_id"]:
                raise ValueError(
                    f"Mismatched conversation_id {conversation_id} vs {last_row['conversation_id']}"
                )
            conversation, last_customer = clean_conversation(
                detector, conversation_row["conversation"], cache
            )
            if not conversation.strip() or not last_customer.strip():
                continue
            conversation_writer.writerow([conversation_id, conversation])
            last_writer.writerow([conversation_id, last_customer])
            kept += 1
            if read % 2000 == 0:
                out_conversation_handle.flush()
                out_last_handle.flush()
                print(f"{input_dir.name}: processed {read}, kept {kept}", flush=True)

    print(f"Read {read} conversations from {input_dir}")
    print(f"Wrote {kept} conversations to {output_dir}")
    print(f"Translated {len(cache)} unique Spanish snippets")


def clean_all(input_root, output_root):
    """Clean every brand folder under input_root into output_root."""
    detector = load_detector()
    cache = {}
    brands = sorted(
        path for path in input_root.iterdir() if (path / "conversation.csv").is_file()
    )
    print(f"Cleaning {len(brands)} brands from {input_root}", flush=True)
    for brand in brands:
        print(f"=== {brand.name} ===", flush=True)
        clean_brand(brand, output_root / brand.name, detector, cache)


def main():
    parser = argparse.ArgumentParser(
        description="Translate Spanish conversation turns to English and drop other languages."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="data/conversations_sequenced",
        help="Brand folder, or a directory of brand folders (default: data/conversations_sequenced)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="data/conversations_sequenced_cleaned",
        help="Output folder (default: data/conversations_sequenced_cleaned)",
    )
    args = parser.parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    if (input_path / "conversation.csv").is_file():
        clean_brand(input_path, output_path)
    else:
        clean_all(input_path, output_path)


if __name__ == "__main__":
    main()
