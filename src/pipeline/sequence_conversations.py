#!/usr/bin/env python3
"""Turn grouped support tweets into labeled conversations.

Each conversation is one line. Turns are ordered by time and separated by |:

    [customer] - message | [agent] - message | [customer] - message

The line keeps every turn, including the last customer message. A second file
repeats that last customer message for the same record.
User ids, customer-service handles, and agent sign-offs such as ^AJ are
removed. Links become [link], and image URLs become [image].
"""

import argparse
import csv
import html
import re
from pathlib import Path

from group_conversations import (
    brand_authors,
    group_conversations,
    load_tweets,
    normalize_text,
    strip_mentions,
)

URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
IMAGE_EXTENSION_PATTERN = re.compile(r"\.(?:jpg|jpeg|png|gif|webp)(?:$|\?)", re.IGNORECASE)
IMAGE_CONTEXT_PATTERN = re.compile(
    r"\b(?:attached|attachment|photo|image|pic|picture|screenshot)\b",
    re.IGNORECASE,
)
TRAILING_URL_PUNCTUATION = ".,;:!?)]\"'"
BLANK_OR_LINK = re.compile(r"^(?:\s|\[link\]|\[image\]|[.,;:!?()\"'\-])*$")
# Agent initials and first names written as ^AJ, ^SV, or ^Madison.
AGENT_SIGNATURE = re.compile(r"\s*\^(?=[A-Z])[A-Za-z]{1,15}(?![A-Za-z'])\.?")


def _split_trailing_punctuation(url):
    extra = ""
    while url and url[-1] in TRAILING_URL_PUNCTUATION:
        extra = url[-1] + extra
        url = url[:-1]
    return url, extra


def replace_links(text):
    """Replace URLs with [link], and image URLs with [image]."""
    image_context = IMAGE_CONTEXT_PATTERN.search(text) is not None

    def replace(match):
        url, extra = _split_trailing_punctuation(match.group(0))
        lowered = url.lower()
        is_image = (
            "pic.twitter.com" in lowered
            or "pbs.twimg.com" in lowered
            or IMAGE_EXTENSION_PATTERN.search(lowered) is not None
            or (image_context and "t.co/" in lowered)
        )
        token = "[image]" if is_image else "[link]"
        return f"{token}{extra}"

    return URL_PATTERN.sub(replace, text)


def strip_agent_signatures(text):
    """Remove agent sign-offs such as ^AJ and ^Madison."""
    return AGENT_SIGNATURE.sub("", text)


def clean_message(text):
    """Drop ids, agent sign-offs, and links, then collapse the message onto one line."""
    text = html.unescape(text or "")
    text = strip_mentions(text)
    text = strip_agent_signatures(text)
    text = replace_links(text)
    return normalize_text(text)


def speaker_label(tweet):
    if tweet["inbound"].strip().lower() == "false":
        return "agent"
    return "customer"


def is_blank_or_link(message):
    return BLANK_OR_LINK.match(message or "") is not None


def last_customer_text(messages):
    """Join the last run of customer messages, skipping a trailing link or blank.

    Each message is labeled, including the first one in the run. If that run
    is only a link, use the previous customer message instead.
    """
    groups = []
    current = []
    for speaker, message in messages:
        if speaker == "customer":
            current.append(message)
            continue
        if current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)

    for group in reversed(groups):
        kept = group
        if kept and is_blank_or_link(kept[-1]):
            kept = [message for message in kept[:-1] if not is_blank_or_link(message)]
        if not kept:
            continue
        return " | ".join(f"[customer] - {message}" for message in kept)
    return ""


def sequence_thread(thread):
    """Return labeled turns and the last customer message."""
    turns = []
    messages = []
    for tweet in thread:
        message = clean_message(tweet["text"])
        if not message:
            continue
        speaker = speaker_label(tweet)
        turns.append(f"[{speaker}] - {message}")
        messages.append((speaker, message))
    return turns, last_customer_text(messages)


def write_brand_files(conversations, output_dir, brand_filter=None):
    """Write one conversation file and one last-customer file per brand."""
    handles = {}
    counts = {}
    try:
        for thread in conversations:
            turns, last_customer_message = sequence_thread(thread)
            if not turns or not last_customer_message:
                continue
            conversation_id = thread[0]["tweet_id"].strip()
            conversation = " | ".join(turns)
            brands = brand_authors(thread) or ["unknown"]
            if brand_filter is not None:
                brands = [brand for brand in brands if brand == brand_filter]
            for brand in brands:
                pair = handles.get(brand)
                if pair is None:
                    brand_dir = output_dir / brand
                    brand_dir.mkdir(parents=True, exist_ok=True)
                    conversation_path = brand_dir / "conversation.csv"
                    last_customer_path = brand_dir / "last_customer_message.csv"
                    conversation_file = conversation_path.open("w", encoding="utf-8", newline="")
                    last_customer_file = last_customer_path.open("w", encoding="utf-8", newline="")
                    conversation_writer = csv.writer(conversation_file)
                    last_customer_writer = csv.writer(last_customer_file)
                    conversation_writer.writerow(["conversation_id", "conversation"])
                    last_customer_writer.writerow(["conversation_id", "last_customer_message"])
                    pair = (conversation_file, last_customer_file, conversation_writer, last_customer_writer)
                    handles[brand] = pair
                    counts[brand] = 0
                _, _, conversation_writer, last_customer_writer = pair
                conversation_writer.writerow([conversation_id, conversation])
                last_customer_writer.writerow([conversation_id, last_customer_message])
                counts[brand] += 1
    finally:
        for conversation_file, last_customer_file, _, _ in handles.values():
            conversation_file.close()
            last_customer_file.close()
    return counts


def main():
    parser = argparse.ArgumentParser(
        description="Write labeled conversations and the last customer message for each one."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="data/sample.csv",
        help="Path to the input CSV (default: data/sample.csv)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="data/conversations_sequenced",
        help="Directory for per-brand output (default: data/conversations_sequenced)",
    )
    parser.add_argument(
        "--brand",
        help="Write only this brand folder (for example AirbnbHelp)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)
    tweets = load_tweets(input_path)
    conversations = group_conversations(tweets)
    counts = write_brand_files(conversations, output_dir, args.brand)

    conversation_count = sum(counts.values())
    print(f"Read {len(tweets)} tweets from {input_path}")
    print(
        f"Wrote {conversation_count} conversations across {len(counts)} brands to {output_dir}"
    )


if __name__ == "__main__":
    main()
