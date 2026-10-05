#!/usr/bin/env python3
"""Keep conversations where the customer and the agent each speak more than once.

Reads one brand folder of sequenced or cleaned conversations and writes a
single CSV with the full conversation and the last customer message.
"""

import argparse
import csv
import sys
from pathlib import Path

from sequence_conversations import last_customer_text

csv.field_size_limit(sys.maxsize)

TURN_SEPARATOR = " | "


def speaker_counts(conversation):
    """Count customer and agent turns in one conversation line."""
    customer = 0
    agent = 0
    for turn in conversation.split(TURN_SEPARATOR):
        turn = turn.strip()
        if turn.startswith("[customer]"):
            customer += 1
        elif turn.startswith("[agent]"):
            agent += 1
    return customer, agent


def has_multiple_interactions(conversation):
    """True when both sides take part more than once."""
    customer, agent = speaker_counts(conversation)
    return customer >= 2 and agent >= 2


def labeled_turns(conversation):
    """Return (speaker, message) pairs from a labeled conversation line."""
    messages = []
    for turn in conversation.split(TURN_SEPARATOR):
        turn = turn.strip()
        if turn.startswith("[customer] - "):
            messages.append(("customer", turn.removeprefix("[customer] - ")))
        elif turn.startswith("[agent] - "):
            messages.append(("agent", turn.removeprefix("[agent] - ")))
    return messages


def select_conversations(input_dir, output_path):
    conversation_path = input_dir / "conversation.csv"
    last_path = input_dir / "last_customer_message.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    read = 0
    kept = 0
    with conversation_path.open(newline="", encoding="utf-8") as conversation_handle, last_path.open(
        newline="", encoding="utf-8"
    ) as last_handle, output_path.open("w", newline="", encoding="utf-8") as output_handle:
        conversations = csv.DictReader(conversation_handle)
        last_rows = csv.DictReader(last_handle)
        writer = csv.writer(output_handle)
        writer.writerow(["conversation_id", "conversation", "last_customer_message"])

        for conversation_row, last_row in zip(conversations, last_rows):
            read += 1
            conversation_id = conversation_row["conversation_id"]
            if conversation_id != last_row["conversation_id"]:
                raise ValueError(
                    f"Mismatched conversation_id {conversation_id} vs {last_row['conversation_id']}"
                )
            conversation = conversation_row["conversation"]
            last_customer_message = last_customer_text(labeled_turns(conversation))
            if not has_multiple_interactions(conversation) or not last_customer_message:
                continue
            writer.writerow(
                [
                    conversation_id,
                    conversation,
                    last_customer_message,
                ]
            )
            kept += 1

    print(f"Read {read} conversations from {input_dir}")
    print(f"Wrote {kept} multi-turn conversations to {output_path}")
    return kept


def main():
    parser = argparse.ArgumentParser(
        description="Write Amazon conversations that have multiple customer and agent turns."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="data/conversations_sequenced_cleaned/AmazonHelp",
        help="Brand folder with conversation.csv and last_customer_message.csv",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="data/conversations_multi/AmazonHelp.csv",
        help="Output CSV (default: data/conversations_multi/AmazonHelp.csv)",
    )
    args = parser.parse_args()
    select_conversations(Path(args.input), Path(args.output))


if __name__ == "__main__":
    main()
