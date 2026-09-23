# Session 2 (group hackathon) data

All data for session 2 is located in [`/session-2/data/`](/session-2/data/).
Individual challenge descriptions:
* [Challenge 1 — Talos Case Review](/session-2/challenge-1-case-review.md)
* [Challenge 2 — Why is this candidate interesting?](/session-2/challenge-2-explanation.md)
* [Challenge 3 — Natural-language Talos](/session-2/challenge-3-natural-language.md)
* [Challenge 4 — Reanalysis triage](/session-2/challenge-4-reanalysis-triage.md)
* [Challenge 5 — Open pitch](/session-2/challenge-5-open-pitch.md)
* [Challenge 6 — HPO annotation tool](/session-2/challenge-6-hpo-annotation.md)
* [Challenge 7 — Interactive exploration of computational facial phenotyping results](/session-2/challenge-7-facial-phenotyping.md)
* [Challenge 8 — Find patients matching trial criteria](/session-2/challenge-8-cohort-finder.md)
* [Challenge 9 — Undiagnosed patient investigation](/session-2/challenge-9-undiagnosed-investigation.md)

## Challenges 1 - 3

These challenges can all be completed using either, or a combination of, the example multi-variant report and json results files from Talos v11.0.1:
* `multi_variant_report_2026-07-27.html`
* `multi_variant_results_2026-07-27.json`

## Challenge 4

Synthetic case-level data for the reanalysis-triage challenge. It is intentionally artificial and must not be presented as clinical evidence:
* `synthetic_reanalysis_cases.tsv` — 300 unresolved cases from a single reanalysis cycle dated 2026-09-01
* `synthetic_reanalysis_outcomes.tsv` — what happened when each case was actually reviewed

### Using the outcomes file

`synthetic_reanalysis_outcomes.tsv` is for **evaluating** your triage, not for building it. In a real lab you do not know these outcomes at the moment you decide what to perform reanalysis, that is the whole problem. Build your prioritisation from the case table, then use the outcomes to check how well it worked.

A good evaluation asks: of the top 20 cases your tool surfaces, how many were resolved? How does that compare with simply sorting by the oldest analysis date?

`review_outcome` takes four values: `solved`, `candidate_for_followup`, `no_change`, and `not_reviewed_already_solved`.

### Data dictionary — `synthetic_reanalysis_cases.tsv`

| Column | Meaning |
|---|---|
| `case_id` | Unique case identifier |
| `case_status` | `unsolved`, `partially_solved`, or `solved` at the start of this cycle |
| `first_analysis` | Date the case was first analysed |
| `last_analysis` | Date of the most recent previous analysis |
| `current_analysis` | Date of this reanalysis cycle (constant) |
| `sequencing_type` | `exome` or `genome` |
| `family_structure` | `singleton`, `duo`, or `trio` at the last analysis |
| `hpo_term_count` | Number of HPO terms currently recorded |
| `phenotype_changes` | New HPO terms added since the last analysis |
| `candidate_count` | Total candidate variants in the current output |
| `new_candidates` | Candidates not present at the last analysis |
| `new_high_priority_candidates` | Candidates now in a high-confidence category, including existing ones newly promoted |
| `new_gene_evidence` | Candidates whose gene–disease association has strengthened |
| `new_clinvar_evidence` | Candidates with any ClinVar reclassification |
| `clinvar_upgrades_to_plp` | Subset of the above reclassified specifically to Pathogenic / Likely Pathogenic |
| `prior_analysis_complete` | `1` if the previous analysis ran to completion, `0` if not |
| `prior_analysis_flag` | Why the previous analysis was incomplete: `qc_fail`, `partial_panel`, `pipeline_error`, `no_parental_data` |
| `note` | Free-text laboratory note. Mostly administrative, but some notes record real events |

Missing values are encoded as `NA` and appear in several columns. Decide deliberately how to handle them — dropping incomplete rows is a choice with consequences.

## Challenge 6

No data is supplied for this challenge. Download the HPO annotation files yourself from https://hpo.jax.org/data/annotations (CC BY 4.0):
* `phenotype.hpoa` — disease-level annotations: for each OMIM, ORPHANET or DECIPHER disease, the HPO terms curated for it, with frequency, onset and evidence code.
* `genes_to_phenotype.txt` / `phenotype_to_genes.txt` — the same annotations viewed per gene.

These files map diseases and genes to HPO term IDs. They do not contain the ontology itself, so they carry no term labels, synonyms or parent/child relationships. For term search and hierarchy, download `hp.json` or `hp.obo` from https://hpo.jax.org/data/ontology.

## Challenge 7 — Interactive exploration of computational facial phenotyping results

Build an interactive tool to explore computational facial phenotyping results. Participants receive:
* 125 aligned facial images covering 5 rare disorders, with 25 images per disorder
* Image metadata
* One GestaltMatcher embedding per image
* One GestaltMatcher prediction JSON file per image

Download the dataset from [Sciebo](https://uni-bonn.sciebo.de/s/z9c26aWQBqxDb9Q).

The dataset is password-protected. Please request the password from the workshop organizers.

The extracted dataset structure is approximately:

```text
demo_data/
├── demo_align/
│   ├── 1_aligned.jpg
│   ├── 2_aligned.jpg
│   └── ...
├── image_metadata_demo.tsv
├── demo_embeddings_v115.tsv
└── demo_output_v115/
    ├── 1_aligned.json
    ├── 2_aligned.json
    └── ...
```

## Challenges 8 and 9

`phenopackets.jsonl` holds 100 synthetic PhenoTips family exports, one JSON object per line and one line per patient record (`FAM0002001` … `FAM0002100`), each in [Phenopacket schema v1.0.0](https://phenopacket-schema.readthedocs.io/en/1.0.0/) `Family` form. Together they hold 100 probands and 529 relatives. The data is intentionally artificial and must not be presented as clinical evidence.

### Shape

```
{
  "id": "FAM0002001",
  "proband":   { phenopacket },
  "relatives": [ { phenopacket }, ... ],
  "pedigree":  { "persons": [ { "familyId", "individualId", "paternalId"?, "maternalId"?, "sex" }, ... ] },
  "metaData":  { "created", "createdBy", "resources": [ ... ] }
}
```

A phenopacket has `id` (UUID), `subject { id, dateOfBirth?, sex }`, `phenotypicFeatures[] { type { id, label }, negated? }`, `genes[] { id, alternateIds, symbol }`, `diseases[] { term { id, label } }` and `metaData`. Empty lists are omitted, not written as `[]`. Every phenopacket repeats the same `metaData.resources` block; that is how PhenoTips exports.

### Data dictionary

| What | Where | Example |
|---|---|---|
| Patient record | proband `subject.id` | `P0003001` |
| Pedigree-only relative | relative `subject.id` | `"0"`, `"1"`, … |
| Parent links | `pedigree.persons[].paternalId` / `maternalId`; founders have neither | |
| Molecular (final) diagnosis | `diseases[].term.id` with prefix `MIM:` | `MIM:604370` |
| Clinical diagnosis | `diseases[].term.id` with prefix `ORDO:` (Orphanet) | `ORDO:145` |
| Gene finding | `genes[]`, HGNC id plus Ensembl id and symbol | `HGNC:1100` / `BRCA1` |
| Phenotype | `phenotypicFeatures[].type`, HPO release 2024-08-13 | `HP:0003002` Breast carcinoma |
| Excluded phenotype | `phenotypicFeatures[].negated: true` | |
| Family history | relatives' `phenotypicFeatures` and `diseases`, joined to the proband through `pedigree.persons` | |
| Age | `subject.dateOfBirth`, year precision; absent for 20% of probands and most relatives | `1978-01-01T00:00:00Z` |
| Affected status | not exported; derive it from the relative's record | |

A patient can have a gene finding without a diagnosis, a clinical diagnosis without a gene, both, or neither. Roughly a third of the probands have neither. The organisers hold the table used to generate the files.

## Important data policy

No patient data is supplied by the workshop. Participants must not upload patient-identifiable or otherwise confidential clinical data to Claude or the workshop repository.

Public and synthetic data are encouraged.
