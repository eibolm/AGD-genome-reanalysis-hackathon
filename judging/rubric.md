# Session 2 — Judging rubric

Session 1 is onboarding and is not scored.

Three things separate a good project here: it solves a problem a lab actually has, everything on screen is true and traceable, and it runs. Technical complexity, framework choice and slide polish are noise at this timescale — don't score them.

## Scoring — 100 points

| # | Criterion | Points |
|---|---|---:|
| 1 | Clinical usefulness and problem fit | 30 |
| 2 | Evidence integrity | 25 |
| 3 | Working prototype and honest demo | 25 |
| 4 | AI-assisted build | 20 |

### 1. Clinical usefulness and problem fit — 30
Does it address a real pain point in case review or reanalysis?

- **24–30** — Specific user, specific step in the workflow. A clinician says "that would save me time" unprompted.
- **17–23** — Genuine pain point, but loosely defined user or the most obvious problem available.
- **8–16** — Plausible-sounding, no clear user. Or restates what the tool already does.
- **0–7** — Technology in search of a problem.

Ask: *who opens this, and when?* No concrete answer means it isn't a 24+. Choosing a sharp, non-obvious problem is the creative act here, and it's scored in this criterion.

### 2. Evidence integrity — 25
Can every claim be traced to source data?

- **20–25** — Every claim traces to input data. Input data read correctly. Limitations and missing data shown, not hidden. Where an LLM writes prose, the facts still come from the data.
- **14–19** — Mostly sound; one or two unsourced claims that don't mislead clinically.
- **6–13** — Presents assumed values as if from the source data, or misreads a field in a misleading way.
- **0–5** — Invents results, or implies a classification (e.g. ACMG) that was never computed.

A beautiful interface that invents its result set loses to a plain one that doesn't.

### 3. Working prototype and honest demo — 25
Can they show it working on the supplied data, and are they straight about what's real?

- **20–25** — Runs live on the supplied output. Team states plainly what's complete, what's not, what would break at scale.
- **14–19** — Core path works with rough edges.
- **6–13** — Works only on a handpicked example, or vague about what's real.
- **0–5** — Mocked demo presented as working.

### 4. AI-assisted build — 20
Did the agent let them build beyond their prior ability, and did they stay in control?

- **16–20** — Clearly beyond the team's prior ability. Non-programmers contributed directly.
- **11–15** — Used effectively to move faster, with some evidence of review.
- **4–10** — Autocomplete for people who could already do the work, or output accepted unreviewed.
- **0–3** — No meaningful use, or uncritical acceptance that introduced errors.

About development acceleration and oversight, not whether the product contains an LLM. A product with no AI can score full marks.

## Probe question, per challenge

1. **Case Review** — Did they do 2–3 improvements properly rather than reskinning everything? Did presentation changes stay presentation changes?
2. **Candidate explanation** — Does the explanation add anything valuable beyond the data in the report? Will this speed up clinical evaluation? 
3. **Natural-language Talos** — Show the query the question produced. Then ask something unanswerable: does it decline, or guess?
4. **Reanalysis triage** — Is the weighting inspectable or arbitrary? What happens to a case with no new evidence?
5. **Open pitch** — Does it genuinely touch Talos output? Same four criteria as everyone else, no handicap or bonus.
8. **Trial criteria** — Pick a family-history criterion and ask for the pedigree traversal. Does "breast cancer" match HPO descendants of Neoplasm of the breast, or a label string? What happens to a patient with no date of birth?
9. **Undiagnosed investigation** — How is "undiagnosed" decided from the data? Show a raw PubCaseFinder response next to what the screen displays for the same patient.

## Awards

- **🏆 Best Overall** — highest total. Criteria 1 and 2 are 55 points, so this is effectively the clinical-impact award.
- **🤖 Best AI-Assisted Build** — furthest beyond the team's prior ability while staying in control. Mainly Criterion 4, with Criterion 3 as evidence something real came out. A team of clinical scientists who shipped should beat developers who used the agent as autocomplete. This is the award a non-programming team can win.
- **💡 Most Creative** — judges' choice: the idea that most changed how the room thought about the problem. Discretionary, not computed from the total, so flair doesn't distort scoring. Still needs a working demo.
