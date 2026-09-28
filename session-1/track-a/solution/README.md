# Track A — Tidy the Talos data

A worked solution for [Session 1A](../README.md): turn
[messy_talos_candidates.tsv](../messy_talos_candidates.tsv) into something a clinical
geneticist can actually review.

## Run it

Two implementations, same output. Pick whichever your environment has:

```bash
python session-1/track-a/solution/tidy_talos.py
perl   session-1/track-a/solution/tidy_talos.pl
# both take: <input.tsv> <output_dir>
```

Python 3.8+ or Perl 5, standard library only — nothing to install. Then open
`talos_case_report.html` in a browser.

The two scripts are kept deliberately in step: apart from the generation timestamp,
they produce byte-identical files. That is also how the CRLF bug below was caught.

## What comes out

| File | What it is |
| --- | --- |
| `talos_case_report.html` | The deliverable. Per-case review report, self-contained, printable. |
| `talos_candidates_tidy.tsv` | One row per unique variant, 41 normalised columns. Opens straight in Excel. |
| `talos_cleaning_log.txt` | Every change made to the source data, row by row. |

The report gives each case a header block (variant counts per tier, leading candidate),
a sortable and filterable table, and an expandable detail panel per variant holding the
in-silico scores, transcript annotation and links out to gnomAD, ClinVar, Ensembl,
PanelApp and OMIM.

## What was wrong with the source file

16 rows, 30 columns, and the same fact encoded several different ways:

- **Sample IDs** — `SAMPLE_1`, `sample_1`, and `SAMPLE_1 ` with a trailing space.
- **Chromosomes** — `6` in one row, `chr6` in another, for the same variant.
- **Booleans** — `TRUE`/`True`/`yes`/`1` and `FALSE`/`False`/`no`/`0`, mixed within a column.
- **`Talos_category_4`** — not a boolean at all. It holds the sample ID the de novo call
  fired for, so casting it to a boolean marks every row de novo. It is read here as de
  novo only when it matches that row's own sample.
- **Inheritance** — `AD` and `Autosomal Dominant` are the same mode, written two ways.
- **Genotypes** — a JSON object embedded in a TSV field, with its quotes doubled.
- **Protein changes** — `p.P405S` vs `p.Pro405Ser`, `p.(His916Leu)` with parentheses,
  `ENSP00000264161.4:p.Ala274Gly` with an accession glued on the front.
- **`MANE_HGVSc`** — mostly empty, and where present usually not HGVS at all
  (`135912503G>A`, `89279566CCTTCGGGG>C`). Only `c.` notation is kept.
- **gnomAD AF** — float noise: `2.499999936844688e-06` and `2.5e-06` are one number.
- **ClinVar** — `P/LP` and `Pathogenic/Likely Pathogenic`; `VUS` and `Uncertain significance`.
- **Nulls** — empty, `.`, and the literal string `missing`, interchangeably.
- **Dates** — `2026-07-27` alongside `27/07/2026`.
- **Duplicates** — 16 rows describe 13 variants. Rows 10 and 14 are identical; rows 3/11
  and 6/16 are the same variant reported under two different modes of inheritance.
- **CRLF line endings** — worth knowing about, because it fails quietly. Python's
  `open()` translates `\r\n` for you; Perl's `chomp` does not, so the last column name
  becomes `extra_technical_field\r`, the lookup misses, and the transcript annotation
  comes back empty with no error. Strip `\r?\n` explicitly rather than trusting `chomp`.

## How candidates are ranked

No score. Each variant gets a tier from rules that are printed next to it under
*Why prioritised*, so a reviewer can disagree with the reasoning rather than with a number.

- **Tier A** — ClinVar P/LP **and** a supporting genotype: loss of function, de novo,
  homozygous, hemizygous, or compound heterozygous in trans.
- **Tier B** — one of those without the other.
- **Tier C** — everything else. A variant predicted likely benign with no ClinVar P/LP
  is demoted here regardless of what else it has.

Parental origin is inferred from the trio genotypes (de novo, maternal, paternal,
biparental, unresolved), and compound heterozygotes are paired within a gene and checked
for being in trans. That is what promotes DARS1 `p.Ala274Gly` — maternal and paternal
alleles in the same gene, in trans, in both cases.

## Result

13 unique variants across 2 cases. SAMPLE_1 has 6 tier A, led by a de novo ANKRD11
frameshift and a de novo WT1 nonsense; SAMPLE_2 has 3 tier A, led by a homozygous POC1B
splice-donor variant and a hemizygous IL2RG missense with 3 ClinVar review stars.

Two contradictions in the source data are flagged rather than silently resolved:

- Rows 3/11 and 6/16 disagree on the mode of inheritance for the same variant.
- SAMD9 `7:93105286` has `Talos_category_1` set (the ClinVar-driven category) but no
  ClinVar record in the file.

## Caveats

- **Assembly is inferred.** The coordinates match GRCh38 (RNU4-2 at 12:120291834, ANKRD11
  at 16:89279566), but the file does not declare one. The external links assume GRCh38 —
  confirm before trusting them.
- **Talos category labels** follow the public Talos documentation. Check them against the
  version of Talos that produced your data.
- Synthetic workshop data derived from the public Talos test fixture. No patient data,
  and nothing here is a clinical interpretation.
