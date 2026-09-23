# Challenge 8 — Find patients matching trial criteria

A study coordinator has a list of inclusion criteria and a registry of 100 patient records exported from PhenoTips as phenopackets.

Build a prototype answering:

> Which patients qualify, and why?

Use the family phenopackets in `/session-2/data/phenopackets.jsonl`, one family per line. The file shape and encoding conventions are documented in the [session 2 data README](/session-2/README.md#challenges-8-and-9).

Start from criteria like these, then let the user write their own:
- female, born 1965–2005, with a first- or second-degree relative with breast cancer
- confirmed finding in BRCA1 or BRCA2
- clinical or molecular diagnosis of Lynch syndrome
- child under 10 with seizures and no molecular diagnosis
- two or more relatives with a recorded phenotype or diagnosis

Do not just return ids. For each match, show which fields satisfied each criterion.

## Worth thinking about

- Family history lives in the relatives and the pedigree, not in the proband record. "Mother has breast cancer" means following `pedigree.persons` parent links to the relative's phenopacket. Degree of relationship is computed, not stored.
- Three different things can look like "has the disease": a `genes` entry (a finding), a `MIM:` disease (molecular diagnosis) and an `ORDO:` disease (clinical diagnosis). A trial may accept some of these and not others.
- "Seizures" is HP:0001250, but a record may say "Focal-onset seizure". Matching means matching HPO descendants, which needs the ontology, not the label. The data uses HPO release 2024-08-13; `hp.json` is on the [HPO releases page](https://github.com/obophenotype/human-phenotype-ontology/releases).
- A feature with `"negated": true` was looked for and found absent.
- Some patients have no date of birth. Decide what an age criterion does with them, and show it.

**Success:** a coordinator sees every matching patient, the fields that qualified them, and the patients that could not be assessed for missing data.
