# ConvoSense

Group [Customer Support on Twitter](https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter) tweets into conversations. Each conversation is written on one line, with tweets ordered by time and separated by `##||##`.

Tweets are linked through `response_tweet_id` and `in_response_to_tweet_id`.

## Setup

Requires Python 3.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, activate the environment with:

```bash
.venv\Scripts\activate
```

## How to run

The pipeline has four steps. `src/pipeline/sequence_conversations.py` is required: `src/pipeline/translate_conversations.py` reads the labeled files it writes, not the raw tweets.

### 1. Group tweets

`src/pipeline/group_conversations.py` reads a customer-support CSV, groups tweets into conversations, removes `@mentions` (including author ids), and writes one file per brand.

```bash
python src/pipeline/group_conversations.py
```

That reads `data/twcs/twcs.csv` and writes `data/conversations/<brand>/conversations.csv`.

```bash
python src/pipeline/group_conversations.py data/sample.csv -o data
```

`-o` / `--output` is the directory that contains `conversations/`. It defaults to `data`. A brand is the `author_id` on a company reply (`inbound` is false). Each conversation is one line, with tweets ordered by time and separated by `##||##`. A thread with no company reply is written to `data/conversations/unknown/conversations.csv`.

```text
first tweet text##||##second tweet text##||##third tweet text
```

### 2. Label customer and agent turns

`src/pipeline/sequence_conversations.py` rewrites each conversation as one line of labeled turns separated by ` | `. It also writes the last customer turn, or the last run of customer turns, for the same record. A trailing message that is empty or only `[link]` / `[image]` is skipped. Links become `[link]` and images become `[image]`.

```bash
python src/pipeline/sequence_conversations.py data/twcs/twcs.csv -o data/conversations_sequenced
```

One brand only:

```bash
python src/pipeline/sequence_conversations.py data/twcs/twcs.csv -o data/conversations_sequenced --brand AirbnbHelp
```

```text
data/conversations_sequenced/AirbnbHelp/conversation.csv
data/conversations_sequenced/AirbnbHelp/last_customer_message.csv
```

```text
[customer] - first message | [agent] - reply | [customer] - last message
```

### 3. Translate Spanish and drop other languages

`src/pipeline/translate_conversations.py` reads `data/conversations_sequenced`. English messages stay as they are. Spanish messages are translated to English with the installed Argos model. A conversation is dropped when any message is not English or Spanish, and empty conversations are not written.

Install dependencies first, and keep the FastText language-id model at `models/lid.176.ftz`. The Argos Spanish-to-English package must already be installed. The script does not download either model.

```bash
python src/pipeline/translate_conversations.py
```

That reads every brand under `data/conversations_sequenced` and writes `data/conversations_sequenced_cleaned/<brand>/`. One brand:

```bash
python src/pipeline/translate_conversations.py data/conversations_sequenced/AirbnbHelp -o data/conversations_sequenced_cleaned/AirbnbHelp
```

### 4. Build annotator packages with shared overlap

`src/pipeline/make_overlap_annotator_packages.py` reads one brand's conversations as JSONL (one object per line with `id`, `brand`, `conversation` and `last_customer_message`) and writes one Potato package per annotator. Each annotator gets two batch folders of 100 conversations, so someone who wants to contribute more can do the second.

```bash
python src/pipeline/make_overlap_annotator_packages.py
```

That reads `data/conversations_multi_jsonl/AmazonHelp/conversations.jsonl` and writes `annotator_packages_overlap/`. Set another input path as the first argument and the output folder with `-o`.

Each batch is built from four groups. Batch 1 and batch 2 use different shared conversations and never overlap.

| Group | Per batch | Given to |
| --- | --- | --- |
| all | 20 | every annotator |
| pair | 10 | exactly 2 annotators |
| triple | 5 | exactly 3 annotators |
| unique | the rest of the 100 | 1 annotator |

Options (defaults shown): `--annotators 6`, `--batches 2`, `--per-batch 100`, `--all-shared 20`, `--pair-shared 10`, `--triple-shared 5`, `--seed 42`, `--config potato/config.yaml`, `--guidelines`, `--contact`. The three shared counts must be multiples of 5 so each tone label appears equally often in a group.

There are no gold labels, so the shared conversations are chosen with a rule-based tone estimate that follows `Customer Tone Annotation Guidelines.md`. It reads the customer's last messages and applies the order of precedence: Escalatory, Frustrated, Help-seeking, Appreciative, Neutral. Only high-confidence conversations enter the shared groups, and each group gets the same number per label. Unique conversations are a random draw from everything else. The estimate is approximate, so check `shared_items.jsonl` before sending packages out.

```text
annotator_packages_overlap/
  manifest.json
  shared_items.jsonl
  annotator_01/
    README.md
    batch_1/
      data.jsonl
      config.yaml
      run.sh
      run.bat
    batch_2/
  annotator_01.zip
```

`data.jsonl` is the Potato input for that batch: the conversation is rendered as HTML turns (customer in blue, agent in orange), and the order is shuffled per annotator. `config.yaml` is a copy of `potato/config.yaml` that points at `data.jsonl`. `shared_items.jsonl` lists every overlapped conversation with its group, annotators and estimated label. `manifest.json` maps each batch to its ids and groups. Both are for you only and are not inside the zips. Send each annotator their `annotator_NN.zip`.
