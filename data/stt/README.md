# STT dataset (UFV campus utterances)

A custom speech-to-text test set built for this project: 30 English utterances
spoken on the UFV campus. Most carry one or more domain keywords (a building code, a
classroom number, or a place name); a few generic phrases carry none by design. It
is the set used to evaluate the speech-to-text models across the three STT phases:
server benchmark, on-device quantisation, and Flutter integration.

## Audio

The audio files are kept locally under `audios/` but are not committed to the
repository, because they contain the author's voice. The manifest, reference
transcripts and SHA-256 hashes document the dataset and support reproducibility.

All recordings share the same format: 16 kHz sample rate, mono, 16-bit PCM WAV.

## Contents

- `manifest.csv`: one row per utterance, with its reference transcript and metadata.
- `dataset_hashes.json`: SHA-256 of every audio file, so a privately held copy can be verified byte for byte against the set used here. These fingerprints match the ones recorded by the experiment, so this set is verified identical to the one that was benchmarked.

## manifest.csv columns

| Column | Meaning |
|-|-|
| `utterance_id` | Stable identifier, from `utterance_01` to `utterance_30`. |
| `filename` | Audio file name, found locally under `audios/` (not committed). |
| `category` | One of `initial_location`, `destination`, `navigation_command`, `confirmation`, `hard_domain`, `edge_case`. |
| `reference_transcript` | Ground truth transcription. |
| `duration_s` | Audio length in seconds. |
| `domain_keywords` | Domain keywords present in the reference, separated by `;`. Empty when the utterance carries none. |

## Domain keywords (DKA)

The main STT metric is Domain Keyword Accuracy (DKA): the fraction of utterances
whose domain keywords are all transcribed correctly. A keyword counts for an
utterance when it appears in its reference transcript. The 31 tracked keywords are:

- Room codes: `0.1`, `0.3`, `1.1`, `1.4`, `2.1`
- Buildings: `building g`, `building cd`
- Locations: `elevator`, `stairs`, `cafeteria`, `ai laboratory`, `restroom`, `faculty offices`, `main entrance`, `mentoring room`, `secretary`, `directory sign`, `gym`
- Floors: `ground floor`, `first floor`, `second floor`, `floor 1`, `floor 2`
- Commands and intents: `cancel`, `repeat`, `hurry`, `lost`, `stop`, `done`, `destination`, `doors are open`

The `domain_keywords` column lists, per utterance, which of these appear in its
reference. 27 of the 30 utterances carry at least one.

## Composition

30 utterances, 6 categories, 5 utterances each, about 143 seconds in total. English,
single speaker, recorded on the UFV campus. The categories span the conversational
situations the assistant must understand: stating an origin, stating a destination,
navigation commands, confirmations, hard domain vocabulary, and edge cases.
