# ConvoSense

Group [Customer Support on Twitter](https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter) tweets into conversations. Each conversation is written on one line, with tweets ordered by time and separated by `##||##`.

Tweets are linked through `response_tweet_id` and `in_response_to_tweet_id`.

## 1. Raw data

- **Source:** the [Customer Support on Twitter](https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter) dataset (Kaggle, `thoughtvector`), file `twcs/twcs.csv`. Download it from Kaggle and place it at `data/twcs/twcs.csv`. We did not scrape Twitter ourselves.
- **Content:** public tweets between customers and the support accounts of 108 brands.
- **Instance in the raw file:** one tweet (one row).
- **Number of instances:** 2,811,774 tweets, of which 1,537,843 are customer tweets (`inbound` is true) and 1,273,931 are company replies.
- **Collection period:** almost all tweets are from 2017-10-03 to 2017-12-03 (first to last percentile of tweet times). A small number of older tweets (20,813) go back to 2008, mostly earlier messages in the same threads.
- **Chosen brand:** **AmazonHelp**. We picked one brand so every annotator sees the same kind of company and customer problems.

## 2. License

- **Raw dataset:** [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 (CC BY-NC-SA 4.0)](https://creativecommons.org/licenses/by-nc-sa/4.0/), as given for the Kaggle dataset. The tweets were also posted on Twitter, so Twitter's terms of service apply to the tweet text.
- **Our processed data and labels:** because of the ShareAlike term, the processed conversations and the labels our annotators add are shared under the same license, CC BY-NC-SA 4.0, with attribution to the original dataset. Use is non-commercial only.
- **Code** in this repository is under the MIT License (see `LICENSE`).

## 3. Raw data dictionary

`data/twcs/twcs.csv`, one tweet per row:

| Column | Type | Meaning |
| --- | --- | --- |
| `tweet_id` | int | Unique id of the tweet. |
| `author_id` | string | Numeric id of a customer, or the handle of the company (for example `AmazonHelp`). |
| `inbound` | bool | `True` when the tweet was sent to a company (customer tweet). `False` when the company sent it. |
| `created_at` | string | Time the tweet was posted, for example `Tue Oct 31 22:10:47 +0000 2017`. |
| `text` | string | Tweet text. It contains `@mentions`, URLs, emoji and agent sign-offs such as `^AJ`. |
| `response_tweet_id` | string | Comma-separated ids of tweets that reply to this one. Empty if none. |
| `in_response_to_tweet_id` | int | Id of the tweet this one replies to. Empty if it starts a thread. |

## 4. Data transformation pipeline

Each step reads the output of the previous one. The commands are under "How to run".

1. **Group** (`group_conversations.py`). Tweets are linked into threads with `response_tweet_id` and `in_response_to_tweet_id` (union-find over the reply links), ordered by `created_at`. `@mentions` are removed, so author ids do not appear in the text. A thread belongs to the brand whose `author_id` replied (`inbound` is false).
2. **Sequence** (`sequence_conversations.py`). Each tweet becomes a `[customer]` or `[agent]` turn from the `inbound` flag. HTML entities are decoded, agent sign-offs (`^AJ`) are removed, URLs become `[link]` and image URLs become `[image]`. Empty tweets are skipped, and a conversation with no customer message left is dropped. The last customer turn is saved as `last_customer_message`.
3. **Translate and filter languages** (`translate_conversations.py`).
   - The language of every message is detected with **fastText** (`fasttext-wheel`, model `lid.176.ftz`). A prediction counts only with confidence of at least 0.45. `[link]` and `[image]` are ignored, and a message with no letters (for example only emoji) is treated as neutral and kept.
   - **English** messages are kept unchanged.
   - **Spanish** messages are translated to English with **Argos Translate** (`argostranslate`, offline model `es` to `en`). Translation is done per sentence piece, and `[link]` and `[image]` are kept in place.
   - A conversation is **dropped when any message is in another language** (or is below the confidence threshold). Nothing is translated from any language other than Spanish.
4. **Keep multi-turn conversations** (`select_multi_turn.py`). A conversation stays only if the customer has **at least 2 turns and the agent has at least 2 turns**, and it still has a last customer message. This removes one-question, one-answer threads, which are the large majority of threads, so annotators see tone develop over a real exchange.
5. **JSONL** (`jsonl_converter.py`). The final CSV is written as JSONL for the annotation tool (Potato).

Number of AmazonHelp conversations after each step:

| Step | Output | Conversations |
| --- | --- | --- |
| 1. Group | `data/conversations/` | 798,012 threads for all brands. 82,534 threads (374,042 tweets) with an AmazonHelp reply |
| 2. Sequence | `data/conversations_sequenced/` | 82,408 (126 had no usable text or no customer message left) |
| 3. Translate and language filter | `data/conversations_sequenced_cleaned/` | 60,601 |
| 4. Keep multi-turn | `data/conversations_multi/AmazonHelp.csv` | 25,421 |
| 5. JSONL | `data/conversations_multi_jsonl/AmazonHelp/conversations.jsonl` | 25,421 |

## 5. Final instances and data dictionary

- **Instance:** one customer-support conversation on Twitter between a customer and the Amazon support account, written on one line with labeled turns (`[customer] - ...` / `[agent] - ...`) in time order. The annotation task is to label the customer's tone in the last customer message (see `Customer Tone Annotation Guidelines.md`).
- **Number of instances:** **25,421** conversations.
- **Size:** 171,478 turns in total (mean 6.7, median 6, max 139 per conversation) and about 153 words per conversation on average (median 125).

`data/conversations_multi_jsonl/AmazonHelp/conversations.jsonl`, one JSON object per line:

| Field | Meaning |
| --- | --- |
| `id` | `tweet_id` of the first tweet in the thread. |
| `brand` | Always `AmazonHelp`. |
| `conversation` | Whole conversation, turns separated by ` | `, each turn written `[customer] - text` or `[agent] - text`. `@mentions`, agent sign-offs and URLs are removed or replaced by `[link]` and `[image]`. |
| `last_customer_message` | The last customer turn, or the last run of customer turns. This is what annotators label. |

The CSV versions have the columns `conversation_id`, `conversation` and `last_customer_message` (steps 2 and 3 keep the last customer message in its own file).

### Sampling and missing data

- AmazonHelp was chosen from the 108 brands, and every AmazonHelp conversation that passes the steps above is kept. No random sample is taken at this stage. Annotation batches are drawn in step 6.
- Conversations with a language other than English or Spanish are removed, so the dataset is not representative of all Amazon customers. Spanish messages are machine translated and may read awkwardly.
- Links, images, user handles and agent sign-offs are removed or replaced, so some context is lost. Messages can also be cut short by Twitter's length limit.
- There are no empty tweets in the raw file. Tweets from customers who later deleted them may be missing from threads, which can leave an agent turn without its question.
- Tweets are public, and author ids are removed from the text, but the text itself may still contain names or other personal details that a customer wrote.

### Estimated time per item

Reading one conversation (about 150 words) and picking a tone label takes about **30 to 45 seconds**, so one annotator can label about 80 to 100 items in an hour. This is why each batch is 100 conversations. Replace this with the measured time from our own annotation before submitting.

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

The pipeline has six steps. `src/pipeline/sequence_conversations.py` is required: `src/pipeline/translate_conversations.py` reads the labeled files it writes, not the raw tweets.

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

### 4. Keep multi-turn conversations

`src/pipeline/select_multi_turn.py` keeps conversations where the customer and the agent each speak at least twice.

```bash
python src/pipeline/select_multi_turn.py
```

That reads `data/conversations_sequenced_cleaned/AmazonHelp` and writes `data/conversations_multi/AmazonHelp.csv`.

### 5. Convert to JSONL

```bash
python src/pipeline/jsonl_converter.py
```

That reads `data/conversations_multi` and writes `data/conversations_multi_jsonl/<brand>/conversations.jsonl`.

### 6. Build annotator packages with shared overlap

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
