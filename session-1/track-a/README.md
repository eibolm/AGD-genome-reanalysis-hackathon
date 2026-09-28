# Session 1A — Tidy the Talos data

## Mission

Turn [messy_talos_candidates.tsv](/session-1/track-a/messy_talos_candidates.tsv) into a concise, clinician-readable summary.

You do not need to understand every field. Use Claude to inspect the data and help you decide what information is useful. For this challenge, we suggest using [Claude chat](https://claude.ai/).

### Minimum goal

Produce a table containing:

- gene
- genomic variant
- consequence
- inheritance/reason for prioritisation
- population frequency
- ClinVar information
- one or more Talos evidence/category fields

### Optional extensions

- hyperlinks to external resources
- human-readable variant notation
- clearer evidence labels
- filtering/sorting
- a short case-level summary
- export to HTML or Excel

### Important

This file is a **derived workshop file based on the public Talos test fixture**. It does not contain patient data.

The objective is not to write perfect Python (or other language code). The objective is to experience an agent-assisted workflow:

    inspect → plan → implement → run → inspect → iterate

### Suggested first prompt

> Inspect this table and tell me what each column appears to represent. I want to turn it into a concise table for a clinical geneticist reviewing a rare-disease case. Don't modify anything yet; propose a sensible output structure first.
