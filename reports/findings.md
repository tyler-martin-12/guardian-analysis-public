# Guardian Hansard LLM Probe Findings

## Scope

This is a scrappy methods probe, not a validation study. I used Commons Hansard XML from TheyWorkForYou/Public Whip for 2015-2025, filtered for immigration/asylum/refugee trigger terms, sampled small subsets, and ran three LLM probes with cached Claude calls.

Main data output:

- `data/processed/immigration_speeches_2015_2025.parquet`
- `reports/sample_50.csv`
- `reports/direction_a_defensive_candidates.csv`
- `reports/direction_b_speech_types.csv`
- `reports/direction_c_policy_extraction.csv`

## Data Access

The practical route was TheyWorkForYou bulk XML plus `parlparse` raw member JSON. The API route was unnecessary for this stage, and local Python packages were not needed. Detailed notes are in `reports/data_access_notes.md`.

The script keeps only the latest XML suffix per sitting date. Initial sanity checks showed that `border` alone produced obvious false positives, so I excluded `border/borders`-only matches.

Final trigger-filtered sample:

| Metric | Count |
|---|---:|
| Commons sitting-day XML files | 1,614 |
| Matching speeches, 2015-2025 | 22,708 |
| Conservative | 10,891 |
| Labour | 6,032 |
| Labour/Co-op | 917 |
| SNP | 2,713 |
| Lib Dem | 704 |
| Unknown party | 582 |

By year:

| Year | Speeches |
|---|---:|
| 2015 | 1,981 |
| 2016 | 2,246 |
| 2017 | 1,578 |
| 2018 | 2,567 |
| 2019 | 1,801 |
| 2020 | 1,836 |
| 2021 | 1,637 |
| 2022 | 2,425 |
| 2023 | 2,711 |
| 2024 | 1,772 |
| 2025 | 2,154 |

Speaker-role proxy:

| Role | Speeches |
|---|---:|
| Backbench/unknown | 16,132 |
| Questioner | 3,938 |
| Answerer | 2,638 |

Sanity check: the tightened filter is mostly on-topic, but still includes broader foreign-policy refugee speeches and some procedural material. That is acceptable for this scoped probe, but a proper analysis should add a relevance classifier or topic model.

## Direction A: Negation And Defensive Rhetoric

What I tried:

I selected 20 candidate speeches with both hostile/restrictive surface vocabulary and defensive cues such as `shameful`, `safe routes`, `compassion`, `must not`, or `scapegoat`. The baseline is intentionally crude: a negative lexicon would treat these as hostile/restrictive. Sonnet then classified actual stance.

Result:

| LLM stance | Count |
|---|---:|
| Pro-immigration/pro-refugee | 12 |
| Restrictive/hostile | 5 |
| Mixed/unclear | 3 |

Signal:

This is the strongest immediate signal. In 15 of 20 cases, a surface lexicon would be misleading or at least incomplete. Examples include hostile words aimed at the Rwanda policy or government handling, not at migrants/refugees. This directly tests a likely blind spot in dictionary-based or weakly supervised sentiment measures.

Scaling difficulty:

Moderate. The hard part is constructing a gold-ish evaluation set: speeches containing hostile words, negation, quotation, or criticism of hostile rhetoric. Once sampled, LLM stance labels are cheap enough to run at thousands of speeches with caching. A rigorous version should compare lexicon, supervised classifier, and LLM labels against hand-coded examples.

Novelty:

High. This feels closest to a clear blog-post contribution: rhetoric measures can invert when hostile terms are quoted, negated, or aimed at policy rather than people.

## Direction B: Speech-Type Classification

What I tried:

Haiku tagged 50 sampled speeches as set-piece policy speech, ministerial response, backbench intervention, debate contribution, or question. I spot-checked a small random subset against raw Hansard `type` and text context. The labels were plausible: direct questions were usually questions, ministerial answers were usually responses, and debate/intervention distinctions looked usable but fuzzier.

Quick reweighting signal using the rough lexicon score (`defensive cues - negative cues`):

| LLM speech type | Count | Mean rough score |
|---|---:|---:|
| Set-piece policy speech | 2 | 4.00 |
| Debate contribution | 10 | 2.80 |
| Backbench intervention | 9 | 1.56 |
| Ministerial response | 11 | 1.09 |
| Question | 18 | 0.50 |

Signal:

There is a signal, but it is probably more methodological hygiene than headline finding. Questions look more compressed and lower-scoring; set-piece/debate contributions carry more rhetorical language. That means raw sentiment averages may be partly compositional: a year with more questions or urgent statements could look rhetorically cooler even if substantive position does not change.

Scaling difficulty:

Low to moderate. Haiku can tag this cheaply. The main work is defining categories cleanly and validating ambiguous cases such as interventions during debates.

Novelty:

Medium. Useful as a control or robustness check, less compelling as the main post unless it reveals a major year/party compositional artifact.

## Direction C: Rhetoric Vs Policy

What I tried:

I sampled speeches from 2016, 2022, and 2024, then asked Sonnet to extract advocated policy positions separately from rhetorical register. I compared this informally with enacted policy context.

LLM register counts:

| Year | Register | Count |
|---|---|---:|
| 2016 | Economic | 3 |
| 2016 | Humanitarian | 3 |
| 2016 | Mixed | 2 |
| 2016 | Security/control | 1 |
| 2016 | Technocratic | 3 |
| 2022 | Humanitarian | 4 |
| 2022 | Partisan attack | 2 |
| 2022 | Security/control | 2 |
| 2022 | Technocratic | 4 |
| 2024 | Humanitarian | 3 |
| 2024 | Mixed | 1 |
| 2024 | Partisan attack | 1 |
| 2024 | Security/control | 2 |
| 2024 | Technocratic | 5 |

Policy context:

2016 centres on the Immigration Act 2016, including right-to-rent/right-to-work enforcement and restrictions around support for failed asylum seekers. The official explanatory notes describe enforcement around illegal immigration and asylum support limits. Sources: GOV.UK Immigration Act 2016 collection and legislation.gov.uk explanatory notes.

2022 centres on the Nationality and Borders Act 2022. GOV.UK frames it as a New Plan for Immigration reform to deter illegal entry and disrupt trafficking networks, and official explanatory notes describe reforming asylum, controlling borders, and safe/legal routes. Sources: GOV.UK Nationality and Borders Act collection and legislation.gov.uk explanatory notes.

2024 centres on the Safety of Rwanda (Asylum and Immigration) Act 2024. GOV.UK describes it as confirming Rwanda as a safe third country and enabling removals of people arriving under the Immigration Acts; Royal Assent was 25 April 2024. Source: GOV.UK Rwanda Act factsheet/collection.

Signal:

There is a visible divergence worth probing, but the current sample is too small and noisy. In 2016, several speeches are humanitarian or technocratic, while enacted policy leans enforcement/hostile-environment infrastructure. In 2022 and 2024, technocratic and humanitarian registers often coexist with hard control policies: inadmissibility, overseas processing/removal, Rwanda safety declarations, and deterrence.

Scaling difficulty:

High. This needs year-level policy coding, possibly bill/act timelines, and a cleaner distinction between government policy advocacy, opposition critique, and constituency casework. It is promising but would become a bigger research project.

Novelty:

Medium-high. The rhetoric/policy split is intellectually richer than speech-type classification, but it needs more scaffolding than Direction A. It could work as a second layer after establishing that surface rhetoric is not stance.

## Recommendation

Best main direction: Direction A.

It has the clearest methodological bite: a measurable disagreement between hostile surface vocabulary and actual stance. It also speaks directly to where additional LLM use adds value beyond lexicons or shallow classifiers.

Best supporting direction: Direction B.

Use speech type as a robustness control: show whether a year/party effect survives after separating questions, ministerial answers, and fuller debate speeches.

Direction C is interesting, but I would keep it as a short exploratory section unless the blog post is allowed to become more policy-history heavy.

## Sources

- TheyWorkForYou/Public Whip bulk XML: https://www.theyworkforyou.com/pwdata/scrapedxml/debates/
- `parlparse` people metadata: https://raw.githubusercontent.com/mysociety/parlparse/master/members/people.json
- `parlparse` ministers metadata: https://raw.githubusercontent.com/mysociety/parlparse/master/members/ministers.json
- Immigration Act 2016 GOV.UK collection: https://www.gov.uk/government/collections/immigration-bill-2015-16
- Immigration Act 2016 explanatory notes: https://www.legislation.gov.uk/ukpga/2016/19/notes/division/3/index.htm
- Nationality and Borders Act 2022 GOV.UK collection: https://www.gov.uk/government/collections/the-nationality-and-borders-bill
- Nationality and Borders Act 2022 explanatory notes: https://www.legislation.gov.uk/ukpga/2022/36/notes/division/3/index.htm
- Safety of Rwanda Act GOV.UK collection: https://www.gov.uk/government/collections/the-safety-of-rwanda-asylum-and-immigration-bill
- Safety of Rwanda Bill factsheet: https://www.gov.uk/government/publications/the-safety-of-rwanda-asylum-and-immigration-bill-factsheets/safety-of-rwanda-asylum-and-immigration-bill-factsheet-accessible
