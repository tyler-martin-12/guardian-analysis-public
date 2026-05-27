# Echo Chart Methodology

This note documents the filter used for the `stop the boats` chart in the blog post.

## Filter Rules

The chart starts from `data/processed/echo_stop_the_boats_llm.parquet` and keeps only rows where:

- `immigration_context == "yes"`
- `year >= 2022`
- `confidence == "high"`

The year filter treats pre-2022 appearances as pre-slogan uses. The confidence filter removes uncertain LLM classifications before aggregating party/use-type counts.

## Count Delta

| stage | count |
|---|---:|
| Pre-filter immigration-context occurrences | 426 |
| Removed because year < 2022 | 9 |
| Removed because year >= 2022 but confidence != high | 17 |
| Post-filter chart occurrences | 400 |

## Stella Creasy 2015 True Positive

The 2015 Stella Creasy occurrence is a genuine immigration-context use of the phrase, but it is filtered out because it predates the Sunak-era slogan period used for the chart.

| speech_id                                  | date       | speaker       | party              | echo_type          | confidence   | sentence_context                                                                                                                                                                                                                  |
|:-------------------------------------------|:-----------|:--------------|:-------------------|:-------------------|:-------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| uk.org.publicwhip/debate/2015-09-08c.281.5 | 2015-09-08 | Stella Creasy | labourco-operative | quoted_or_critical | high         | We should also understand the consequences of not hearing their voices. We cut the funding for Operation Mare Nostrum, thinking that somehow that would stop the boats. The boats came anyway, and the lorries are still running. |
| uk.org.publicwhip/debate/2015-09-08c.281.5 | 2015-09-08 | Stella Creasy | labourco-operative | own_voice          | medium       | Let us not make it an either-or with our European neighbours; let us help all those people. If we want to stop the boats and lorries, that is what we must do. I want to make a final plea to the Home Secretary.                 |

## Small Boats Consistency Check

The same year filter does not materially change the blog's point about `small boats`: in 2025, the heuristic echo table still has 78 Labour own-use mentions and 28 Conservative own-use mentions. The term remains operational cross-party vocabulary rather than a clean quotation/criticism echo case.
