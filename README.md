# AI × Genomics Hackathon

A workshop package for an AI-assisted coding hackathon centred on [Talos](https://www.nature.com/articles/s41591-026-04477-5), rare-disease variant prioritisation, genome reanalysis, and phenotype parsing.

## Core idea

This workshop does not teach people to code.

Instead, it shows clinical scientists and bioinformaticians how an AI coding agent (in this case, Claude) lets them build useful software in a short time frame, tackling projects they would previously not have attempted without a software engineering background.

The workshop runs as two sessions: an individual session, followed by a group session.

## Setup and cheatsheet documentation
Please complete the [participant setup](/setup/participant_setup.md) **before** the event. This will ensure that no time is wasted on technical problems during the hackathon.

Additionally, read the [Claude cheatsheet](/setup/claude_cheatsheet.md) for tips on working with Claude Chat and Claude Code.

## Session 1 — Individual onboarding

In Session 1, you get a short, contained experience of using an AI coding agent. Both tracks use synthetic or public Talos-derived material, so you can focus on the workflow rather than on handling patient data.

- **Track A: Tidy the Talos data**: inspect a messy variants table and turn it into a concise, clinician-readable summary. You will practise understanding unfamiliar data, choosing useful fields, and iterating on a practical output rather than writing code.
- **Track B: Reskin the Talos report**: work with the real Talos output and make one useful presentation change to its HTML report. You will practise using Claude to analyse a file, identify areas fit for improvement, and test a small change without altering the underlying variant interpretation.

Track A is a good starting point if you'd rather work with data than code; Track B is a good starting point if you're comfortable diving into HTML, JavaScript and CSS.

## Session 2 — Team Hackathon

In Session 2, work with your team on a small, working prototype that could make Talos or genome reanalysis more useful. Choose one of the challenges below, decide what a useful result would look like, and use Claude to help you build and demonstrate it. You do not need to build a complete product.

1. **[Talos Case Review](/session-2/challenge-1-case-review.md)** — improve the Talos HTML view for someone reviewing a case. You could focus on the case overview, phenotype summary, candidate table, evidence, filters, ranking explanations, links, visualisation, or export.
2. **[Why is this candidate interesting?](/session-2/challenge-2-explanation.md)** — build a component that explains an individual candidate using its gene, variant, rank, inheritance or reason, Talos evidence, phenotype evidence, supporting evidence, limitations, and source links. Make sure each explanation can be traced back to the data and does not make unsupported clinical claims.
3. **[Natural-language Talos](/session-2/challenge-3-natural-language.md)** — let a user ask questions about the Talos JSON output in plain English, such as "which candidates are de novo or have phenotype support?". Claude can interpret the question, and return the relevant results, but the actual result set should come from a deterministic query over the data.
4. **[Reanalysis triage](/session-2/challenge-4-reanalysis-triage.md)** — help a laboratory decide which unresolved cases to review first after a reanalysis cycle. You could use signals such as new candidates, updated gene-disease or ClinVar evidence, phenotype changes, and time since analysis. Show why each case was prioritised rather than presenting an unexplained score.
5. **[Open pitch](/session-2/challenge-5-open-pitch.md)** — propose and prototype another improvement to Talos, rare-disease diagnostics, or genome reanalysis. Start with a real user problem, make sure your idea meaningfully interacts with Talos or its outputs, and demonstrate a working proof of concept. It does not need to contain AI.
6. **[HPO annotation tool](/session-2/challenge-6-hpo-annotation.md)** — build a graphical annotation tool for tagging inputs such as hand radiographs or free-text diagnosis descriptions with HPO terms. Focus on making annotation fast and consistent, and export the collected annotations in a form that could later train a model to predict or suggest HPO terms.
7. **[Explore computational facial phenotypes](/session-2/challenge-7-facial-phenotyping.md)** — build an interactive research tool to explore rare-disease facial images together with GestaltMatcher embeddings, known syndrome labels, and diagnostic predictions. Possible directions include interactive t-SNE/UMAP visualisation, image exploration by syndrome, nearest-neighbour analysis, patient-level prediction review, and investigation of clustering or prediction errors.
8. **[Find patients matching trial criteria](/session-2/challenge-8-cohort-finder.md)** — search 100 synthetic PhenoTips phenopacket exports for patients meeting inclusion criteria such as a family history of breast cancer, a particular diagnosis or a positive gene finding. Family history has to come from the pedigree, and every match should show the fields that qualified it.
9. **[Undiagnosed patient investigation](/session-2/challenge-9-undiagnosed-investigation.md)** — filter the same dataset to patients without a diagnosis and use PubCaseFinder's public API to build a differential diagnosis with links to case reports. Show scores and matched terms rather than a single answer.

### Working with your team
**Workshop GitHub repository:**  
Please fork the repo, make a subdirectory for your team with a creative (and unlikely to be duplicated) name under `session-2/projects`. Please push your work here, including your final presentation and working prototype.

## Source material

The workshop deliberately uses the public Talos project and its test fixtures as the foundation. The upstream repository contains small VCF/pedigree/test JSON fixtures, and the HTML report is assembled by Python/Jinja code.

Other source data not directly related to Talos, including the PhenoTips phenopacket exports for challenges 8 and 9, have been synthetically generated for the purposes of this workshop.

## Data policy

No patient data is provided. Use synthetic/public data only.

## Funding and support
The AI x Genomics Hackathon at the Arbeitsgemeinschaft für Gen-Diagnostik e.V. Jahrestagung 2026 was supported by the following institutions, companies, and projects:
![image](/img/GHGA_full_Logo_orange.png)![image](/img/anthropic_logo.png)![image](/img/igsb_logo.png)
