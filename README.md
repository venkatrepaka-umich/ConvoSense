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

Sample data:

```bash
python group_conversations.py
```

That reads `sample_data/sample.csv` and writes `data/<brand>/conversations.txt`.

Full Twitter customer-support file:

```bash
python group_conversations.py sample_data/twcs/twcs.csv -o data
```

`-o` / `--output` is the output directory. It defaults to `data`. A brand is the `author_id` on a company reply (`inbound` is false). Each conversation is one line in that brand's file, with tweets ordered by time and separated by `##||##`. A thread with no company reply is written to `data/unknown/conversations.txt`.

```text
data/AppleSupport/conversations.txt
data/sprintcare/conversations.txt
data/unknown/conversations.txt
```

An output line looks like this:

```text
first tweet text##||##second tweet text##||##third tweet text
```
