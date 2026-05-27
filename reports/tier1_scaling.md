# Tier 1 Scaling: Direction A

## Status

Tier 1 sample, lexicon labels, Sonnet stance labels, and a 50-row hand-coding file have been generated.

Do not proceed to Tier 2 until `reports/handcoded_sample.csv` has been reviewed and `my_label` has been filled.

## Sample

- Full filtered corpus: `data/processed/immigration_speeches_2015_2025.parquet`
- Tier 1 sample: `reports/tier1_direction_a_sample_200.csv`
- Sample size: 200
- Sampling: 18 speeches per year for 2015-2025, plus 2 random top-up speeches from the remaining eligible pool.
- Eligibility: `word_count` between 40 and 900.

By year:

|   year |   n |
|-------:|----:|
|   2015 |  18 |
|   2016 |  18 |
|   2017 |  18 |
|   2018 |  18 |
|   2019 |  18 |
|   2020 |  20 |
|   2021 |  18 |
|   2022 |  18 |
|   2023 |  18 |
|   2024 |  18 |
|   2025 |  18 |

## Lexicon Baseline

Spec: `reports/lexicon_spec.md`

Lexicon label counts:

| lexicon_label                  |   n |
|:-------------------------------|----:|
| pro_immigration_or_pro_refugee | 102 |
| mixed_or_unclear               |  78 |
| restrictive_or_hostile         |  20 |

## Sonnet Stance Classification

Output: `reports/tier1_direction_a_llm_stance.csv`

LLM label counts:

| llm_label                      |   n |
|:-------------------------------|----:|
| pro_immigration_or_pro_refugee |  81 |
| restrictive_or_hostile         |  64 |
| mixed_or_unclear               |  55 |

## Agreement Available Now

Lexicon vs LLM:

| lexicon_label                  |   pro_immigration_or_pro_refugee |   restrictive_or_hostile |   mixed_or_unclear |   not_immigration_stance |
|:-------------------------------|---------------------------------:|-------------------------:|-------------------:|-------------------------:|
| pro_immigration_or_pro_refugee |                               45 |                       27 |                 30 |                        0 |
| restrictive_or_hostile         |                                4 |                       11 |                  5 |                        0 |
| mixed_or_unclear               |                               32 |                       26 |                 20 |                        0 |
| not_immigration_stance         |                                0 |                        0 |                  0 |                        0 |

## Hand Coding

Hand-coding file for review: `reports/handcoded_sample.csv`

Fill `my_label` with one of:

- `pro_immigration_or_pro_refugee`
- `restrictive_or_hostile`
- `mixed_or_unclear`

Rows with `both_maybe_wrong_review` in `notes` are the highest-value cases to discuss in the post.

## Agreement Matrices

Me vs lexicon:

| my_label                       |   pro_immigration_or_pro_refugee |   restrictive_or_hostile |   mixed_or_unclear |   not_immigration_stance |
|:-------------------------------|---------------------------------:|-------------------------:|-------------------:|-------------------------:|
| pro_immigration_or_pro_refugee |                                4 |                        0 |                 11 |                        0 |
| restrictive_or_hostile         |                                6 |                        2 |                  5 |                        0 |
| mixed_or_unclear               |                                7 |                        0 |                  7 |                        0 |
| not_immigration_stance         |                                4 |                        1 |                  3 |                        0 |

Me vs LLM:

| my_label                       |   pro_immigration_or_pro_refugee |   restrictive_or_hostile |   mixed_or_unclear |   not_immigration_stance |
|:-------------------------------|---------------------------------:|-------------------------:|-------------------:|-------------------------:|
| pro_immigration_or_pro_refugee |                               12 |                        0 |                  3 |                        0 |
| restrictive_or_hostile         |                                0 |                       11 |                  2 |                        0 |
| mixed_or_unclear               |                                3 |                        4 |                  7 |                        0 |
| not_immigration_stance         |                                0 |                        4 |                  4 |                        0 |

Lexicon vs LLM on hand-coded subset:

| lexicon_label                  |   pro_immigration_or_pro_refugee |   restrictive_or_hostile |   mixed_or_unclear |   not_immigration_stance |
|:-------------------------------|---------------------------------:|-------------------------:|-------------------:|-------------------------:|
| pro_immigration_or_pro_refugee |                                3 |                        7 |                 11 |                        0 |
| restrictive_or_hostile         |                                0 |                        1 |                  2 |                        0 |
| mixed_or_unclear               |                               12 |                       11 |                  3 |                        0 |
| not_immigration_stance         |                                0 |                        0 |                  0 |                        0 |
