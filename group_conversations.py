#!/usr/bin/env python3
"""Group customer-support tweets into one line per conversation.

Tweets are linked through response_tweet_id and in_response_to_tweet_id.
Each conversation is written on a single line, with tweet texts separated
by ##||## and ordered by created_at.
"""

import argparse
import csv
from datetime import datetime
from pathlib import Path

SEPARATOR = "##||##"
DATE_FORMAT = "%a %b %d %H:%M:%S %z %Y"


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


def normalize_text(text):
    """Collapse whitespace so a conversation stays on one output line."""
    return " ".join(text.split())


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


def write_conversations(conversations, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for thread in conversations:
            texts = [normalize_text(tweet["text"]) for tweet in thread]
            handle.write(SEPARATOR.join(texts))
            handle.write("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Group tweets from a customer-support CSV into conversations."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="sample_data/sample.csv",
        help="Path to the input CSV (default: sample_data/sample.csv)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="sample_data/conversations.txt",
        help="Path to the output file (default: sample_data/conversations.txt)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    tweets = load_tweets(input_path)
    conversations = group_conversations(tweets)
    write_conversations(conversations, output_path)

    tweet_count = sum(len(thread) for thread in conversations)
    print(f"Read {len(tweets)} tweets from {input_path}")
    print(f"Wrote {len(conversations)} conversations ({tweet_count} tweets) to {output_path}")


if __name__ == "__main__":
    main()
