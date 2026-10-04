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

The pipeline has three steps. `src/pipeline/sequence_conversations.py` is required: `src/pipeline/translate_conversations.py` reads the labeled files it writes, not the raw tweets.

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
