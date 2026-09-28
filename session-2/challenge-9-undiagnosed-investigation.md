# Challenge 9 — Undiagnosed patient investigation

Most of the 100 patients in `/session-2/data/phenopackets.jsonl` have a diagnosis or a gene finding. Some have only HPO terms.

Build a personal investigation tool answering:

> For a patient with no diagnosis, what should I look at next?

1. Decide from the data which patients count as undiagnosed, and show the rule.
2. Send the patient's HPO terms to PubCaseFinder and show the ranked differential with each candidate's score and matched terms.
3. Link to further reading: PubCaseFinder, OMIM, Orphanet, PubMed case reports.

## PubCaseFinder API

Public, no key. Documentation: https://pubcasefinder.dbcls.jp/api. Verified working on 2026-09-23:

```
GET https://pubcasefinder.dbcls.jp/api/pcf_get_ranked_list?target=omim&format=json&hpo_id=HP:0001250,HP:0000253,HP:0000098
```

`target` may be `omim`, `orphanet` or `gene`. Each result carries `rank`, `score`, `matched_hpo_id` and the disease or gene ids and names. Lookups:

```
GET https://pubcasefinder.dbcls.jp/api/pcf_get_hpo_data_by_hpo_id?hpo_id=HP:0001250
GET https://pubcasefinder.dbcls.jp/api/pcf_get_omim_data_by_omim_id?omim_id=OMIM:136140
```

## Worth thinking about

- Cache responses, and never query for a patient who already has a diagnosis. The service is shared.
- A ranked list is not a diagnosis. Show the score and the matched terms so the reader can judge for themselves.
- Some patients have few, non-specific terms. The honest output there is "this list is not informative", not the top hit.
- Relatives can carry phenotypes. Decide whether they enter the query.
- A negated term must never be sent as a positive one.

**Success:** a clinician opens one undiagnosed patient, sees a differential they can check, and can follow every link back to its source.
