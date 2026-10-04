#!/usr/bin/env python3
"""Group customer-support tweets into one line per conversation.

Tweets are linked through response_tweet_id and in_response_to_tweet_id.
Each conversation is written on a single line, with tweet texts separated
by ##||## and ordered by created_at. @mentions are removed from the text.
Company replies are filed under data/conversations/<brand>/conversations.csv.
"""

import argparse
import csv
import re
from datetime import datetime
from pathlib import Path

SEPARATOR = "##||##"
DATE_FORMAT = "%a %b %d %H:%M:%S %z %Y"
# @handles, including chains like @115850@AmazonHelp. The handle must end before
# the next character, and a following dot-and-letter keeps user@domain.com.
MENTION_PATTERN = re.compile(
    r"@[A-Za-z0-9_]+(?![A-Za-z0-9_])(?!\.[A-Za-z0-9])"
)


class UnionFind:
    def __init__(self):
        self.parent = {}

    def add(self, item):
        if item not in self.parent:
            self.parent[item] = item

    def find(self, item):
        self.add(item)
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left, right):
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left != root_right:
            self.parent[root_right] = root_left


def split_ids(value):
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def strip_mentions(text):
    """Remove @mentions, including author ids, without touching email addresses."""
    return MENTION_PATTERN.sub("", text)


def normalize_text(text):
    """Collapse whitespace so a conversation stays on one output line."""
    return " ".join(text.split())


def conversation_line(thread):
    """Join cleaned tweet texts. Drop tweets that are empty after stripping."""
    texts = []
    for tweet in thread:
        cleaned = normalize_text(strip_mentions(tweet["text"]))
        if cleaned:
            texts.append(cleaned)
    return SEPARATOR.join(texts)


def brand_authors(thread):
    """Return company author ids that replied in this thread, in first-seen order."""
    brands = []
    seen = set()
    for tweet in thread:
        if tweet["inbound"].strip().lower() != "false":
            continue
        brand = tweet["author_id"].strip()
        if brand and brand not in seen:
            seen.add(brand)
            brands.append(brand)
    return brands


def parse_created_at(value):
    return datetime.strptime(value, DATE_FORMAT)


def load_tweets(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def group_conversations(tweets):
    """Return conversations as lists of tweet rows, oldest tweet first."""
    groups = UnionFind()
    for tweet in tweets:
        tweet_id = tweet["tweet_id"].strip()
        groups.add(tweet_id)
        parent_id = tweet["in_response_to_tweet_id"].strip()
        if parent_id:
            groups.union(tweet_id, parent_id)
        for response_id in split_ids(tweet["response_tweet_id"]):
            groups.union(tweet_id, response_id)

    conversations = {}
    for tweet in tweets:
        root = groups.find(tweet["tweet_id"].strip())
        conversations.setdefault(root, []).append(tweet)

    ordered = []
    for thread in conversations.values():
        thread.sort(key=lambda row: (parse_created_at(row["created_at"]), row["tweet_id"]))
        ordered.append(thread)

    ordered.sort(key=lambda thread: parse_created_at(thread[0]["created_at"]))
    return ordered


def write_conversations(conversations, output_dir):
    """Write one conversations.txt per brand under output_dir."""
    handles = {}
    counts = {}
    try:
        for thread in conversations:
            line = conversation_line(thread)
            if not line:
                continue
            for brand in brand_authors(thread) or ["unknown"]:
                handle = handles.get(brand)
                if handle is None:
                    path = output_dir / "conversations" / brand / "conversations.csv"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    handle = path.open("w", encoding="utf-8")
                    handles[brand] = handle
                    counts[brand] = 0
                handle.write(line)
                handle.write("\n")
                counts[brand] += 1
    finally:
        for handle in handles.values():
            handle.close()
    return counts


def main():
    parser = argparse.ArgumentParser(
        description="Group tweets from a customer-support CSV into conversations."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="data/twcs/twcs.csv",
        help="Path to the input CSV (default: data/twcs/twcs.csv)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="data",
        help="Directory that contains the conversations folder (default: data)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)
    tweets = load_tweets(input_path)
    conversations = group_conversations(tweets)
    grouped = write_conversations(conversations, output_dir)

    conversation_count = sum(grouped.values())
    print(f"Read {len(tweets)} tweets from {input_path}")
    print(
        f"Wrote {conversation_count} conversations across {len(grouped)} brands to {output_dir / 'conversations'}"
    )


if __name__ == "__main__":
    main()
