# Contributing

Thanks for taking a look. This is a small showcase/benchmark repo for
[django-mindoff](https://github.com/mindoffwork/django-mindoff), so contributions
usually fall into one of three buckets: fixing something that's wrong, making a
demo clearer, or improving the benchmark so the numbers are more honest.

## Getting set up

See the [README](README.md#quick-start) for the clone → `.env` → install → migrate →
run flow. In short:

```bash
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
pytest
```

## Ground rules

- **Keep handlers thin.** APIs live in `apps/<app>/apis/`; reusable logic lives in
  `apps/<app>/components/`. Match the structure that's already there.
- **Prefer the framework.** Reach for `mo_crud_kit`, `mo_response_kit`,
  `mo_validation_kit`, and the Polars utilities before hand-rolling plumbing — the
  whole point of the repo is to show those off.
- **Benchmark changes must stay fair.** If you touch the benchmark, both the
  standard-Django and the django-mindoff paths must do equivalent work, run a
  warmup plus at least five measured iterations, and report the median. Skipped
  comparisons should be called out explicitly (see `apps/catalog/components/config.py`).
- **Don't commit generated output.** Live runs write to `output/` (gitignored).
  The tracked, published artifacts live in `benchmarks/`; only refresh those when
  you've intentionally re-run the benchmark and want to update the published numbers.

## Commits and PRs

We follow a gitmoji-style convention. Each commit and PR title is:

```
:<gitmoji>: <Capitalised verb> <short description>
```

Examples:

```
:sparkles: Add bulk update benchmark
:bug: Fix read parity check on empty queryset
:memo: Clarify benchmark methodology in the README
```

PR titles are checked by CI (`.github/workflows/pr-validation.yml`), and the test
suite runs on Python 3.12 and 3.13 (`.github/workflows/ci.yml`). Green CI is
required before merge.

## Code of Conduct

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
