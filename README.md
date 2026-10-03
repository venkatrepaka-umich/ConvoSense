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

`group_conversations.py` reads a customer-support CSV, groups tweets into conversations, removes `@mentions` (including author ids), and writes one file per brand.

```bash
python group_conversations.py
```

That reads `data/twcs/twcs.csv` and writes `data/conversations/<brand>/conversations.txt`.

Pass another CSV if you do not want the default file:

```bash
python group_conversations.py data/sample.csv -o data
```

`-o` / `--output` is the directory that contains `conversations/`. It defaults to `data`. A brand is the `author_id` on a company reply (`inbound` is false). Each conversation is one line in that brand's file, with tweets ordered by time and separated by `##||##`. A thread with no company reply is written to `data/conversations/unknown/conversations.txt`.

```text
data/conversations/AppleSupport/conversations.txt
data/conversations/sprintcare/conversations.txt
data/conversations/unknown/conversations.txt
```

An output line looks like this:

```text
first tweet text##||##second tweet text##||##third tweet text
```
