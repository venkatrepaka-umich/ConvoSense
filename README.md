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

## Usage

Sample data is in `sample_data/sample.csv`.

```bash
python group_conversations.py
```

That reads `sample_data/sample.csv` and writes `sample_data/conversations.txt`.

Use your own file and output path:

```bash
python group_conversations.py path/to/twcs.csv -o conversations.txt
```

An output line looks like this:

```text
first tweet text##||##second tweet text##||##third tweet text
```
