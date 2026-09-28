# Data — download these yourself

Neither file is committed (see `../.gitignore`). Both are CC BY 4.0 from HPO.

| File | Source | What it gives you |
| --- | --- | --- |
| `hp.json` | https://hpo.jax.org/data/ontology | Term labels, synonyms, definitions, parent/child edges. Needed for search and hierarchy. ~100 MB. |
| `phenotype.hpoa` | https://hpo.jax.org/data/annotations | For each OMIM / ORPHANET / DECIPHER disease, its curated HPO terms with frequency, onset and evidence code. Small, ~20 MB. |

`hp.obo` works in place of `hp.json` if you prefer the OBO parser — it is smaller but
fiddlier to parse. Pick one and note the choice here.

`phenotype.hpoa` has **no term labels** — it is disease-to-HPO-ID only. Any UI that shows
a human-readable term name needs the ontology file as well.

## Record the release you used

HPO ships monthly and term IDs are occasionally obsoleted, so annotations are only
reproducible against a stated release. Fill this in once you have downloaded:

- `hp.json` release: _(the `version` field near the top of the file)_
- `phenotype.hpoa` release: _(the `#version:` header line)_
- Downloaded on: _(date)_

## Input material

Use public or synthetic images and text only — no patient-identifiable material.
Record here where each input came from, so the exported annotations can state their
provenance.
