# Conversation Sense annotation - annotator_03

## What you do

Read each customer-support conversation and pick its sense, as described in
the annotation guidelines: <add link to guidelines>

## Requirements

Python 3 (python.org). Nothing else; the script installs the annotation tool
(Potato 2.9.4) into the batch folder the first time.

## Steps

1. Unzip this folder. Open `batch_1`.
2. Start the tool:
   - Mac/Linux: open a terminal in `batch_1` and run `bash run.sh`
   - Windows: double-click `run.bat`

   The first run takes a minute or two to install.
3. Open <http://localhost:8000> in your browser and log in with the username
   `annotator_03` (exactly this, so your labels are attributed to you).
4. Label all 100 conversations. Your answers save automatically and you
   can stop and resume later by running the script again.
5. Press Ctrl+C in the terminal to stop the tool.

## Want to do more?

`batch_2` is a separate set of 100 conversations. Repeat the steps in
`batch_2`. Run only one batch at a time (they share port 8000).

## Send back

When a batch is finished, zip the whole `annotation_output` folder inside it
and send the zip to the contact below:

- `batch_N/annotation_output/` -> `annotation_output.zip`

Please name the zip with your username and batch, for example
`annotator_03_batch_1.zip`. Do this for each batch you completed.

## Contact

- venkar@umich.edu
- kvvy@umich.edu
