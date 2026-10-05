#!/usr/bin/env python3
"""Build Potato annotator packages with a label-balanced overlap.

Per batch (default: 6 annotators x 100 conversations):
  - ALL_SHARED conversations are given to every annotator,
  - PAIR_SHARED conversations are each given to exactly 2 annotators,
  - TRIPLE_SHARED conversations are each given to exactly 3 annotators,
  - the rest are unique to one annotator.
Batch 1 and batch 2 use different shared conversations and never overlap.

The shared conversations are picked so every tone label is equally common in
each shared group. There are no gold labels, so a rule-based estimator that
follows "Customer Tone Annotation Guidelines.md" (Part B order of precedence,
last customer messages decide) picks high-confidence conversations. The
estimated labels are written to shared_items.jsonl for you; annotators never
see them.

    annotator_packages_overlap/
      manifest.json
      shared_items.jsonl
      annotator_01/{README.md, batch_1/, batch_2/}
      annotator_01.zip
"""

import argparse
import json
import random
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

from make_annotator_packages import (
    DEFAULT_INPUT,
    POTATO_VERSION,
    README,
    make_config,
    read_rows,
    write_batch,
)

LABELS = [
    "Appreciative or positive",
    "Neutral or informational",
    "Help-seeking or asking a question",
    "Frustrated or complaining",
    "Escalatory or requesting immediate resolution",
]

# --- tone estimator (Customer Tone Annotation Guidelines, Part B) -----------

ESCALATION_CUES = {
    "manager": r"\b(manager|supervisor|escalat\w*)\b",
    "human": r"\b(need|want|speak to|talk to)\s+(a\s+)?(real\s+)?(human|person|someone)\b",
    "urgent": r"\b(asap|immediately|right now|today or|urgent\w*)\b",
    "legal": r"\b(lawsuit|sue|suing|lawyer|attorney|legal action|small claims|dispute the charge|chargeback)\b",
    "cancel": r"\bcancel(l?ing|led)?\s+(my\s+)?(amazon\s+)?(prime|order|account|subscription|membership)\b",
    "report": r"\b(report(ing)?\s+(you|this|amazon)|better business bureau|bbb|go(ing)? public|trading standards)\b",
    "accuse": r"\b(fraud\w*|scam\w*|liar\w*|lying|lied|stealing|stole|theft|thieves|rip(ped|ping)? (me )?off|cheat\w*)\b",
    "unacceptable": r"\bunacceptable\b",
    "owe": r"\b(you owe me|owe me|give me my money|want my money|refund me)\b",
    "bangs": r"!{3,}",
}
FRUSTRATION_CUES = {
    "negative": r"\b(lame|horrible|terrible|awful|ridiculous|disgusting|useless|pathetic|joke|worst|annoying|frustrat\w*|disappoint\w*|ugh|sick of|tired of|nonsense|crap|stupid|incompetent|rubbish|shambles|hopeless|fed up|unhappy|poor service|bad service|never again|lost a (regular )?customer|did(n'?t| not) work|not working|inferior|what is the point|waste|unhelpful|ignored|no (response|reply|answer)|nobody|no one|never (got|received|arrived|came)|poor)\b",
    "mild_profanity": r"\b(shit\w*|damn|hell|wtf|bullshit|pissed)\b",
    "persisting": r"\b(still (waiting|no|not|haven'?t|hasn'?t|nothing)|again|yet again|once again|for (days|weeks|months)|every time)\b",
    "emphasis": r"[?!]{2,}|\?!|!\?",
    "sarcasm": r"\bthank(s| you)\b[^.]{0,40}\.{3}|\bgreat\b[^.]{0,20}\.{3}|\bthanks a lot\b|\bwow\b",
}
HELP_CUES = {
    "question": r"\?",
    "phrase": r"\b(how (do|can|should|would) i|can (you|someone|somebody)|could you|any (suggestions|ideas|advice)|please help|help me|is there a way|where (can|do) i|what (is|are|should)|do you know|am i able)\b",
}
APPRECIATION_CUES = {
    "praise": r"\b(awesome|love[sd]?|so happy|amazing|perfect|excellent|fantastic|wonderful|brilliant|superb|you rock|best|great (job|service|help)|well done|impressed|delighted)\b",
    "thanks_strong": r"\b(thank you so much|thanks so much|thank you very much|thanks a (lot|million)|many thanks|really appreciate\w*|much appreciated|thank you thank you)\b",
    "emoji": "[\U0001f60a\U0001f60d❤\U0001f64f\U0001f44d\U0001f600\U0001f603\U0001f604\U0001f970\U0001f49b\U0001f389]",
}
FACTUAL_CUES = {
    "digits": r"\d",
    "order_words": r"\b(order(ed)?|tracking|delivered|delivery|package|parcel|arrived|received|account|website|shipped|refund|email(ed)?)\b",
    "confirm": r"\b(i did|yes|no|it is|it was|i have|i ordered)\b",
}
ACRONYMS = {"AMAZON", "PRIME", "ASIN", "USA", "FBA", "AWS", "FLEX", "KINDLE", "ALEXA", "FIRE", "ECHO", "FREE", "HELP"}


def cues_in(text, table):
    return [name for name, pattern in table.items() if re.search(pattern, text, re.I)]


def caps_emphasis(text):
    words = [w for w in re.findall(r"\b[A-Z]{3,}\b", text) if w not in ACRONYMS]
    return len(words) >= 2


def customer_turns(conversation):
    turns = []
    for turn in conversation.split(" | "):
        match = re.match(r"\[customer\] - (.*)", turn, re.DOTALL)
        if match:
            turns.append(clean(match.group(1)))
    return turns


def clean(text):
    return re.sub(r"\[(link|image)\]", " ", text).strip()


def estimate(row):
    """Return (label, confidence, cues). Confidence is 'high' only for clear cases."""
    last = clean(re.sub(r"^\[customer\] - ", "", row["last_customer_message"]))
    last = re.sub(r" \| \[customer\] - ", " ", last)
    earlier = " ".join(customer_turns(row["conversation"]))

    esc = cues_in(last, ESCALATION_CUES)
    frus = cues_in(last, FRUSTRATION_CUES) + (["caps"] if caps_emphasis(last) else [])
    help_ = cues_in(last, HELP_CUES)
    praise = cues_in(last, APPRECIATION_CUES)
    negative_context = bool(cues_in(earlier, ESCALATION_CUES) or cues_in(earlier, FRUSTRATION_CUES))
    words = len(last.split())

    # 1. Escalatory: a demand, threat, accusation or clear build-up.
    if esc:
        strong = {"manager", "human", "legal", "cancel", "report", "accuse", "owe"}
        high = len(esc) >= 2 or bool(strong & set(esc))
        return LABELS[4], "high" if high else "low", esc
    # 2. Frustrated: negative emotion, no demand or threat.
    if frus:
        sarcastic_or_strong = {"negative", "mild_profanity", "sarcasm"} & set(frus)
        high = len(frus) >= 2 or bool(sarcastic_or_strong)
        return LABELS[3], "high" if high else "low", frus
    # 3. Help-seeking: asks a question, no negative emotion.
    if help_:
        rhetorical = bool(re.search(r"\b(why (do|does|did|is|are|would)|what is the point|how (come|hard|difficult))\b", last, re.I))
        high = "question" in help_ and "phrase" in help_ and not negative_context and not rhetorical and words <= 40
        return LABELS[2], "high" if high else "low", help_
    # 4. Appreciative: genuine thanks or praise.
    if praise:
        high = (not negative_context) and "?" not in last and words <= 40
        return LABELS[0], "high" if high else "low", praise
    # 5. Neutral: nothing else applies.
    factual = cues_in(last, FACTUAL_CUES)
    thankful = bool(re.search(r"\bthank|\bappreciat|\bgrateful", last, re.I))
    flat = "!" not in last and not negative_context and not thankful and 3 <= words <= 30
    return LABELS[1], "high" if (factual and flat) else "low", factual


# --- assignment ---------------------------------------------------------------


def pick_balanced(pool_by_label, per_label_counts, rng):
    """Draw distinct items per label: per_label_counts maps group -> items per label."""
    groups = {name: [] for name in per_label_counts}
    for label in LABELS:
        needed = sum(per_label_counts.values())
        picks = rng.sample(pool_by_label[label], needed)
        pool_by_label[label] = [r for r in pool_by_label[label] if r not in picks]
        cursor = 0
        for name, count in per_label_counts.items():
            groups[name].extend((r, label) for r in picks[cursor : cursor + count])
            cursor += count
    return groups


def assign_annotators(items, size, annotators, load, rng):
    """Give each item to the `size` annotators with the fewest shared slots so far."""
    assignment = {}
    items = items[:]
    rng.shuffle(items)
    for row, label in items:
        order = sorted(annotators, key=lambda a: (load[a], rng.random()))
        chosen = sorted(order[:size])
        for a in chosen:
            load[a] += 1
        assignment[row["id"]] = chosen
    return assignment


def main():
    parser = argparse.ArgumentParser(
        description="Create annotator packages with a label-balanced shared overlap."
    )
    parser.add_argument("input", nargs="?", default=DEFAULT_INPUT, help=f"JSONL file (default: {DEFAULT_INPUT})")
    parser.add_argument("-o", "--output", default="annotator_packages_overlap")
    parser.add_argument("--annotators", type=int, default=6)
    parser.add_argument("--batches", type=int, default=2)
    parser.add_argument("--per-batch", type=int, default=100)
    parser.add_argument("--all-shared", type=int, default=20, help="Items per batch given to every annotator")
    parser.add_argument("--pair-shared", type=int, default=10, help="Items per batch given to exactly 2 annotators")
    parser.add_argument("--triple-shared", type=int, default=5, help="Items per batch given to exactly 3 annotators")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--config", default="potato/config.yaml")
    parser.add_argument("--guidelines", default="<add link to guidelines>")
    parser.add_argument("--contact", default="<add your email>")
    args = parser.parse_args()

    n_labels = len(LABELS)
    for name in ("all_shared", "pair_shared", "triple_shared"):
        if getattr(args, name) % n_labels:
            raise SystemExit(f"--{name.replace('_', '-')} must be a multiple of {n_labels} to balance labels")
    if args.annotators < 3:
        raise SystemExit("Need at least 3 annotators for the triple-shared group")

    output = Path(args.output)
    if output.name == "annotator_packages":
        raise SystemExit("Refusing to overwrite the original annotator_packages folder")

    rows = read_rows(Path(args.input))
    if len({r["id"] for r in rows}) != len(rows):
        raise SystemExit("Input has duplicate ids")

    # Estimate tone labels for every conversation.
    estimates = {r["id"]: estimate(r) for r in rows}
    totals = Counter(label for label, _, _ in estimates.values())
    highs = Counter(label for label, conf, _ in estimates.values() if conf == "high")
    print("Estimated label distribution over all conversations (all / high-confidence):")
    for label in LABELS:
        print(f"  {label:48s} {totals[label]:6d} / {highs[label]:6d}")

    shared_per_label = (args.all_shared + args.pair_shared + args.triple_shared) // n_labels
    for label in LABELS:
        if highs[label] < shared_per_label * args.batches:
            raise SystemExit(f"Not enough high-confidence '{label}' conversations")

    rng = random.Random(args.seed)
    annotators = [f"annotator_{a:02d}" for a in range(1, args.annotators + 1)]
    pool_by_label = {
        label: [r for r in rows if estimates[r["id"]][0] == label and estimates[r["id"]][1] == "high"]
        for label in LABELS
    }

    # Pick shared items for every batch (distinct across batches and groups).
    per_label = {
        "all": args.all_shared // n_labels,
        "pair": args.pair_shared // n_labels,
        "triple": args.triple_shared // n_labels,
    }
    shared = {}  # batch -> {id: (row, group, label, annotators)}
    for b in range(1, args.batches + 1):
        groups = pick_balanced(pool_by_label, per_label, rng)
        load = {a: 0 for a in annotators}
        assigned = {}
        assigned.update({r["id"]: annotators[:] for r, _ in groups["all"]})
        for a in annotators:
            load[a] += len(groups["all"])
        assigned.update(assign_annotators(groups["triple"], 3, annotators, load, rng))
        assigned.update(assign_annotators(groups["pair"], 2, annotators, load, rng))
        shared[b] = {
            r["id"]: (r, group, label, assigned[r["id"]])
            for group, items in groups.items()
            for r, label in items
        }

    # Unique conversations: one disjoint random draw for all remaining slots.
    shared_ids = {i for batch in shared.values() for i in batch}
    slots = {}
    for b in range(1, args.batches + 1):
        for a in annotators:
            n_shared = sum(1 for _, _, _, who in shared[b].values() if a in who)
            slots[(a, b)] = args.per_batch - n_shared
    unique_needed = sum(slots.values())
    remaining = [r for r in rows if r["id"] not in shared_ids]
    if len(remaining) < unique_needed:
        raise SystemExit(f"Need {unique_needed} unique conversations but only {len(remaining)} remain")
    unique_rows = rng.sample(remaining, unique_needed)

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    config_text = make_config(Path(args.config))

    manifest = {}
    cursor = 0
    for a in annotators:
        folder = output / a
        for b in range(1, args.batches + 1):
            mine = [(r, g) for r, g, _, who in shared[b].values() if a in who]
            chunk = unique_rows[cursor : cursor + slots[(a, b)]]
            cursor += slots[(a, b)]
            batch_rows = [r for r, _ in mine] + chunk
            assert len(batch_rows) == args.per_batch
            write_batch(folder / f"batch_{b}", batch_rows, config_text, rng)
            manifest[f"{a}/batch_{b}"] = [{"id": r["id"], "group": g} for r, g in mine] + [
                {"id": r["id"], "group": "unique"} for r in chunk
            ]
        (folder / "README.md").write_text(
            README.format(
                annotator=a,
                per_batch=args.per_batch,
                potato=POTATO_VERSION,
                guidelines=args.guidelines,
                contact=args.contact,
            ),
            encoding="utf-8",
        )
        shutil.make_archive(str(output / a), "zip", output, a)

    # One file with every overlapped conversation (for you only).
    with (output / "shared_items.jsonl").open("w", encoding="utf-8") as out:
        for b in range(1, args.batches + 1):
            order = {"all": 0, "triple": 1, "pair": 2}
            for r, group, label, who in sorted(
                shared[b].values(), key=lambda x: (order[x[1]], LABELS.index(x[2]), x[0]["id"])
            ):
                _, conf, cues = estimates[r["id"]]
                out.write(
                    json.dumps(
                        {
                            "id": r["id"],
                            "batch": b,
                            "group": group,
                            "annotators": who,
                            "estimated_label": label,
                            "confidence": conf,
                            "cues": cues,
                            "conversation": r["conversation"],
                            "last_customer_message": r["last_customer_message"],
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    n_shared = sum(len(v) for v in shared.values())
    print(f"Wrote {len(annotators)} annotators x {args.batches} batches x {args.per_batch} to {output}")
    print(f"{n_shared} shared conversations (see shared_items.jsonl), {unique_needed} unique")
    print("manifest.json and shared_items.jsonl are for you only; they are not inside the zips")


if __name__ == "__main__":
    sys.exit(main())
