# Guardian immigration rhetoric probe

This repository contains the code and final data artifacts for a methodological probe of UK parliamentary immigration rhetoric, focusing on cases where surface affective vocabulary diverges from substantive stance. It accompanies the blog post [Stance without affect](https://tyler-alexander-martin.com/blog/stance-without-affect) and was motivated by the Guardian/UCL analysis of 100 years of immigration rhetoric in Hansard.

## Reproduce

```bash
uv run python -m scripts.acquire_hansard --start-year 2015 --end-year 2025
uv run python -m scripts.defensive_rhetoric_results
uv run python -m scripts.echo_analysis && uv run python -m scripts.generate_blog_chart_data
```

The repository includes the final processed sample and echo-analysis parquet files used in the post. Raw TheyWorkForYou XML and the full 704k-speech parsed corpus are intentionally excluded.

## Structure

- `blog/`: standalone static HTML post and optimized image assets.
- `data/processed/`: final labelled sample, per-term echo data, and Plotly chart JSON.
- `prompts/`: prompts used for stance and echo classification.
- `reports/`: final markdown reports referenced by the post.
- `scripts/`: data acquisition, lexicon scoring, LLM classification, echo analysis, and chart-data generation scripts.

Acknowledgements: thanks to the Guardian/UCL team for the transparent original analysis that motivated this probe.
