# Rhetorical Echo Summary

Parsed `704,442` speeches from the 1,614 cached Commons XML files into `data/processed/all_speeches_2015_2025.parquet`. Party metadata is missing for about 7% of speeches, so `unknown` is retained in the tables rather than imputed.

The cleanest echo-style case is `stop the boats`: after filtering to high-confidence immigration-context uses from 2022 onward, Conservatives account for 306 own-voice occurrences, while Labour has 39/50 occurrences marked quoted/critical. A naive party word count would treat every Labour mention as adoption of the slogan; the echo-aware split shows most Labour mentions are references to or criticism of the slogan.

`hostile environment` is also echo-like, but in a different way: Labour plus SNP account for 713/880 total mentions. Because the phrase is now a policy label, many critical uses are not locally quoted, so the heuristic likely undercounts echo/critique.

`small boats` does not support the echo hypothesis cleanly. In 2025, own-use mentions are spread across governing and opposition parties (134 own-use occurrences), suggesting genuine convergence around an operational term rather than mainly quotation.

`invasion`, `swarm`, and `swamped` need caution in the trigger-free corpus. `invasion` has 2014 own-use occurrences, but many are military/geopolitical rather than migration rhetoric; `swarm` is sparse; `swamped` is often about institutional overload. These are candidates for a stricter immigration-context pass, not headline claims.

Skipped as too sparse under the 30-occurrence rule: none.
