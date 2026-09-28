# hpo-scribe

Challenge 6 — paste clinical text in any language, get back HPO terms that are
guaranteed to exist in `phenotype.hpoa`.

## The user and the moment

_TODO — the rubric scores this directly, and generic framing scores badly._

- **Who:**
- **The moment:**
- **What they do today instead:**

## What it does

```
clinical text (any language)
         ↓
  1. extract    Claude lists the findings: verbatim span + English paraphrase
         ↓
  2. retrieve   deterministic search over the allowed vocabulary → candidate IDs
         ↓
  3. choose     Claude picks one of those candidates, or none
         ↓
  4. validate   re-checked against phenotype.hpoa before anything is returned
         ↓
  annotator confirms or corrects → annotations.jsonl
```

## The guarantee, and why it is not a prompt

The requirement is that output is *only* ever an HPO term listed in `phenotype.hpoa`.
Asking a model nicely does not achieve that, so the model is never allowed to name an
identifier at all:

- **It cannot invent one.** Stage 1 returns text spans and English paraphrases — no IDs.
  All candidate IDs come from `hpo_vocab.py`, which is built from `phenotype.hpoa` and
  contains nothing else.
- **It cannot pick one outside the candidates.** The stage 3 response schema pins
  `hpo_id` to a JSON-Schema `enum` of exactly the retrieved IDs plus `"none"`. An
  out-of-vocabulary value is rejected by the API before it reaches us.
- **It cannot slip through anyway.** Every returned ID is re-checked with
  `Vocabulary.is_allowed()` and against that mention's own candidate list. Anything that
  fails is dropped and shown in the UI as *rejected* rather than silently discarded.
- **A human cannot introduce one either.** The correction dropdown offers only the
  retrieved candidates, and `/api/save` re-validates before writing to disk.

The third and fourth layers are redundant if the second works. They are there because
"the schema should prevent it" is not a guarantee worth shipping on, and because a
rejected term is evidence worth showing.

## Why translation happens before retrieval

The lexical index is built from English HPO labels and synonyms. Searching it for
`krampfanfälle` or `kleinwuchs` returns **zero** hits. The model translates to an English
clinical phrase first, and the search runs on that. Getting this order wrong is the
obvious way to build a tool that silently fails on every non-English input.

## Running it

```bash
pip install anthropic                     # the only dependency
```

Download the two data files — see [data/README.md](data/README.md). Then:

```powershell
setx ANTHROPIC_API_KEY "sk-ant-..."       # restart the terminal afterwards
python server.py                          # opens http://127.0.0.1:8765
```

<kbd>Ctrl</kbd>+<kbd>Enter</kbd> in the text box annotates. The manual lookup at the
bottom of the page searches the same vocabulary with no API call, so it costs nothing —
use it to check what the tool *could* have chosen.

Other entry points:

```bash
python hpo_vocab.py seizures "small head"   # search the vocabulary, no API call
python annotate.py "Der Junge zeigt eine Mikrozephalie."   # one-shot CLI
```

Override the model with `HPO_SCRIBE_MODEL` (default `claude-opus-5`).

## Numbers

| | |
| --- | --- |
| HPO release | 2026-09-01 (both files; verified to match) |
| IDs in `phenotype.hpoa` | 11,658 |
| Allowed vocabulary | **11,570** (`aspect=P`, phenotypic abnormalities) |
| Searchable strings | 30,659 labels and synonyms |
| Vocabulary load | ~0.5 s (cached after first build) |
| Model calls per annotation | 2 |

The 88 excluded IDs are inheritance modes, clinical course and clinical modifiers. They
are in `phenotype.hpoa` but are not phenotypes, and "Autosomal dominant inheritance" is
not a sensible output for a phenotype annotation tool. Pass `aspects=None` to
`hpo_vocab.load()` to allow all 11,658.

## Export format

`annotations.jsonl`, one JSON object per annotation:

```json
{
  "text": "Der 4-jährige Junge zeigt eine Mikrozephalie.",
  "terms": [
    {"hpo_id": "HP:0000252", "label": "Microcephaly",
     "span": "Mikrozephalie", "english": "microcephaly",
     "negated": false, "certainty": "stated", "source": "suggested"}
  ],
  "annotator": "eb", "model": "claude-opus-5",
  "vocabulary_release": "2026-09-02 (hpoa) / 2026-09-01 (hp.json)",
  "created_at": "2026-09-23T18:30:00+00:00"
}
```

`source` is `suggested` when the tool proposed the term and the annotator accepted it,
`annotator` when it was corrected by hand. That field is what later tells you whether the
suggestions were any good — without it you have training data but no way to measure the
thing you were trying to measure.

`negated` and `certainty` are kept rather than filtered, because "seizures were ruled
out" is a useful training signal and throwing it away is not free.

## Does it beat annotating by hand?

_TODO — this is the stated success criterion, so it needs a number._

| | By hand | With hpo-scribe |
| --- | --- | --- |
| Inputs annotated | | |
| Time taken | | |
| Terms per input | | |
| Agreement between annotators | | |

## Limits

- **Recall is bounded by the lexical index.** A finding phrased in a way that shares no
  tokens with any HPO label or synonym will retrieve no candidates, and the tool will
  correctly return no term rather than a wrong one. Embedding search would raise recall;
  it would also weaken the traceability that makes the current design defensible.
- **The choose step is the error surface.** If retrieval returns eight plausible
  siblings, picking the wrong level of specificity ("seizure" vs "tonic-clonic seizure")
  is the likely failure. This is why the reason string is shown in the UI.
- **No ontology hierarchy yet.** Parent/child links are in `hp.json` but unused, so the
  annotator cannot currently walk up or down from a suggestion.
- **Not validated against a gold standard.** No measured precision or recall.
- Synthetic and public text only. No patient-identifiable material.

## Working with Claude

_TODO — what Claude got wrong and how you caught it. Scored directly, so keep notes as
you go._

Two worth recording already, from building this:

- The first version of the tidy-data script for Session 1A parsed a CRLF file with Perl's
  `chomp`, which strips `\n` but not `\r`. The last column name silently became
  `extra_technical_field\r`, the lookup missed, and a whole block of the report rendered
  empty with no error. Caught only by writing a second implementation in Python and
  diffing the output byte for byte.
- A version check comparing `phenotype.hpoa`'s build date against `hp.json`'s release
  date produced a false mismatch warning. The file records the ontology it was curated
  against in a separate `#hpo-version` header; that is the field to compare.
