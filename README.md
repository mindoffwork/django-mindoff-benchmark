<h1>Django Mindoff Benchmark</h1>

_See what django-mindoff actually does, then measure it against the tools you already reach for._

This is a small, runnable Django project that puts [django-mindoff][framework] to work on real endpoints. It is not a tutorial app and it is not a starter template. Its job is to let you read a few files, call a few endpoints, and decide for yourself whether the framework earns a place in your stack.

The headline is the benchmark. For bulk work over a Django model (create, read, update), it runs the same job four ways: a DRF serializer with `many=True`, pandas, plain Polars, and django-mindoff. Every number is measured the same way and written out as a CSV plus charts, so you are never asked to trust a claim you cannot reproduce.

If you only have ten minutes, start the server, hit one or two endpoints, open the matching file, and run the benchmark once. That is enough to form an honest opinion.

[![CI](https://github.com/mindoffwork/django-mindoff-benchmark/actions/workflows/ci.yml/badge.svg)](https://github.com/mindoffwork/django-mindoff-benchmark/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-3776AB?logo=python&logoColor=white)](https://github.com/mindoffwork/django-mindoff-benchmark/actions/workflows/ci.yml)
[![License: BSD-3-Clause](https://img.shields.io/badge/license-BSD--3--Clause-blue.svg)](LICENSE)
[![django-mindoff](https://img.shields.io/pypi/v/django-mindoff.svg?logo=pypi&logoColor=white&label=django-mindoff)](https://pypi.org/project/django-mindoff/)

**Framework**: [https://github.com/mindoffwork/django-mindoff][framework]

**Documentation**: [https://django.mindoff.work][docs]

**Package**: [https://pypi.org/project/django-mindoff/][pypi]

## The Numbers

We are not going to paste benchmark figures into this README and let them go stale. The numbers stay where they are produced. The charts below are the actual output of the latest run, committed to [benchmarks/](benchmarks/) and re-rendered every time the benchmark runs, so what you see here is whatever the last run measured.

| Create | Read | Update |
| --- | --- | --- |
| ![Create benchmark](benchmarks/catalog_benchmark_create.png) | ![Read benchmark](benchmarks/catalog_benchmark_read.png) | ![Update benchmark](benchmarks/catalog_benchmark_update.png) |

Each chart plots time and memory as the row count grows, for every approach that has a real workflow for that operation. If you want the raw figures behind the lines, every measured value, across every row count we ran, sits in [benchmarks/catalog_benchmark_values.csv](benchmarks/catalog_benchmark_values.csv). It includes a `remarks` column that explains each comparison we left out and why.

The shape of the result is steady across all of it. For bulk create, read, and update, django-mindoff finishes faster and uses less memory than the DRF serializer with `many=True`, pandas, and plain Polars, and the lead grows as the data gets bigger. The eager lane does full, model-aware validation, the same work a serializer does, just vectorized instead of row by row. The streaming lane skips validation to stay flat on memory, because it never loads the whole result set at once.

Worth saying plainly: at small batch sizes, plain Django usually wins. django-mindoff pays a fixed cost to build frames and run vectorized validation, and below a few thousand rows that overhead does not pay off. This is a complement for bulk tabular work, not a replacement for the ORM, and the benchmark is built to show both sides of that.

> Keeping this honest is cheap. When a new django-mindoff release lands, we bump the pin in [requirements.txt](requirements.txt), run the benchmark, and drop the fresh files into [benchmarks/](benchmarks/). This README hardcodes no figures and no version, so it never needs editing for a new run. The exact version any result was produced with is always the one pinned in [requirements.txt](requirements.txt).

## What's Inside

Every feature maps to a file you can open. Reading the code is the point, so the README does not repeat what the docstrings already explain.

| To see this | Open this | Endpoint |
| --- | --- | --- |
| A managed API and the standard response envelope | [apps/shop/apis/get_profile.py](apps/shop/apis/get_profile.py) | `GET /v1/shop/get_profile/` |
| Payload validation and versioning on one route | [apps/shop/apis/create_order.py](apps/shop/apis/create_order.py) | `POST /v1/shop/create_order/`, `POST /v2/shop/create_order/` |
| Bulk row validation that keeps good rows and rejects bad ones | [apps/catalog/apis/import_products.py](apps/catalog/apis/import_products.py) | `POST /v1/catalog/import_products/` |
| A queryset turned into a Polars frame and aggregated without a loop | [apps/catalog/apis/list_products_report.py](apps/catalog/apis/list_products_report.py) | `GET /v1/catalog/list_products_report/` |
| The create, read, and update benchmark | [apps/catalog/components/products.py](apps/catalog/components/products.py) | `POST /v1/catalog/run_product_benchmark/` |
| A queue-mode API driven by one config switch | [apps/jobs/apis/generate_inventory_report.py](apps/jobs/apis/generate_inventory_report.py) | `POST /v1/jobs/generate_inventory_report/` |

A good place to start reading is a `components/` file, for example [apps/catalog/components/products.py](apps/catalog/components/products.py), which walks through the whole catalog flow.

## Quick Start

You need Python 3.12 or 3.13.

### 1. Get the code

```bash
git clone https://github.com/mindoffwork/django-mindoff-benchmark.git
cd django-mindoff-benchmark
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

This pulls `django-mindoff[internal]`, which brings DRF, Polars, ConnectorX, and the rest of the runtime stack, plus the two chart helpers this repo needs.

### 4. Add your environment file

```bash
cp .env.example .env
```

Settings read a secret key and a `REDIS_URL` through this file, and the server will not start without it. The defaults in `.env.example` are fine for local use.

### 5. Migrate and run

```bash
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/` for the landing page, then try the endpoints below.

> A note on `DEBUG`. Settings read it from `.env`. If your shell already exports a global `DEBUG` variable, python-decouple may pick that one up instead, so keep it boolean-friendly:
>
> ```powershell
> $env:DEBUG="True"
> ```

## Try the Endpoints

The easiest way in is Postman. Import [django-mindoff-showcase.postman_collection.json](django-mindoff-showcase.postman_collection.json) and you get every request below, plus a `base_url` variable already set to `http://127.0.0.1:8000`. If you would rather stay in the terminal, here is the same thing with curl.

### Shop: managed APIs, responses, validation, versioning

```bash
curl http://127.0.0.1:8000/v1/shop/get_profile/

curl -X POST http://127.0.0.1:8000/v1/shop/create_order/ \
  -H "Content-Type: application/json" \
  -d '{"customer_name":"Asha","customer_email":"asha@example.com","product_name":"Wireless Mouse","quantity":2}'

# same route, richer v2 response
curl -X POST http://127.0.0.1:8000/v2/shop/create_order/ \
  -H "Content-Type: application/json" \
  -d '{"customer_name":"Asha","customer_email":"asha@example.com","product_name":"Mechanical Keyboard","quantity":1}'
```

### Catalog: bulk data and reporting

```bash
# one valid row, one bad row (empty sku, negative price) that gets rejected
curl -X POST http://127.0.0.1:8000/v1/catalog/import_products/ \
  -H "Content-Type: application/json" \
  -d '{"rows":[{"sku":"SKU-001","name":"Keyboard","price":49.99,"stock":20,"category":"accessories"},{"sku":"","name":"Bad Product","price":-10,"stock":5,"category":"misc"}]}'

curl http://127.0.0.1:8000/v1/catalog/list_products_report/
```

### Jobs: optional queue mode

Only this endpoint needs Redis. Skip it and everything else still works.

```bash
redis-server
dramatiq django_mindoff.queue_worker
curl -X POST http://127.0.0.1:8000/v1/jobs/generate_inventory_report/ \
  -H "Content-Type: application/json" \
  -d '{"report_name":"weekly_inventory_snapshot"}'
```

## Reproduce the Benchmark

This is the part written for a skeptical reader. The whole thing lives in [apps/catalog/components/](apps/catalog/components/), where `config.py` holds the methodology as plain constants and `measure.py` holds the measurement code.

### Run it

```bash
curl -X POST http://127.0.0.1:8000/v1/catalog/run_product_benchmark/ \
  -H "Content-Type: application/json" \
  -d '{"row_count":[10000,50000,100000],"iterations":5}'
```

That writes four files into `output/`:

- `catalog_benchmark_values.csv`, every measured number, with a `remarks` column that records each comparison we deliberately skipped and why.
- `catalog_benchmark_create.png`, `catalog_benchmark_read.png`, and `catalog_benchmark_update.png`, one file per operation, each with a time panel and a memory panel.

The published copies in [benchmarks/](benchmarks/) came from exactly this command, run against the `django-mindoff` version pinned in [requirements.txt](requirements.txt). We refresh them on every new release: bump the pin, run again, and copy the four files over the old ones. The README points at the artifacts and the pin rather than restating any figures, so it does not need touching when the results change.

### What gets compared

Each operation is judged on both time and memory against every method that has a real workflow for it. A method with no idiomatic path for an operation is skipped, and the skip is called out with a footnote on the chart and a row in the CSV.

- **Create** compares the DRF serializer, pandas, and django-mindoff.
- **Read** is queryset to frame to CSV, so it compares pandas (`from_records`), plain Polars (`pl.DataFrame(list(qs))`), and django-mindoff in both its eager and streaming modes. DRF sits out, because serializers build API representations, not dataframes.
- **Update** compares the DRF serializer and django-mindoff. pandas sits out, because it has no idiomatic bulk-update path.

### How the numbers are taken

- **Realistic input.** Bulk rows come from a Parquet file, so each engine reads data the way it actually would, rather than from hand-built Python objects that would unfairly tax some engines with construction overhead.
- **Time** is the median of at least five measured runs after one warmup.
- **Memory** is peak RSS delta, sampled in a separate worker process for each lane, so native Polars and Arrow allocations are counted without noise from the long-running server.
- **Validation is labeled per line.** The eager django-mindoff and DRF create and update paths run full model-aware validation. The streaming django-mindoff and pandas paths skip it. The chart legend and the CSV say which is which, so a validated path is never quietly compared against an unvalidated one.
- **Query count is a diagnostic, not a score.** django-mindoff bulk writes can persist through a path that Django's cursor instrumentation never sees, so a `0` there does not mean no database work happened. The output says as much.
- **Read results are checked for parity** across engines before any timing counts, so everyone is producing the same rows.

### Make it a fair fight

The committed charts run on local SQLite, which is the worst case for django-mindoff. SQLite is single-writer and has no native bulk-load path. For numbers closer to production, point the project at PostgreSQL or MySQL and turn the row counts up:

```json
{ "row_count": [50000, 250000, 1000000], "iterations": 5 }
```

A file lock plus SQLite WAL and `busy_timeout` settings keep repeated local runs from colliding on the shared demo database.

## Running the Tests

```bash
pytest
```

A couple of focused examples:

```bash
pytest apps/shop/tests/test_apis/test_create_order.py -q
pytest apps/catalog/tests/test_apis/test_run_product_benchmark.py -q
```

CI runs the same suite on Python 3.12 and 3.13 for every pull request and every push to the protected branch. The workflow is in [.github/workflows/ci.yml](.github/workflows/ci.yml).

## Project Layout

```
apps/
  shop/      managed APIs, response envelopes, payload validation, v1 and v2 versioning
  catalog/   bulk import, Polars reporting, and the create/read/update benchmark
  jobs/      the optional queue-mode API (Redis and Dramatiq)
config/      settings, root URLs, and the response-code registry (responses.csv)
benchmarks/  the published benchmark artifacts (charts and CSV), tracked in git
mindoff.py   the framework's project manager for scaffolding commands
```

Each app follows the same shape: thin handlers in `apis/`, reusable logic in `components/`, and tests in `tests/`.

## Contributing and Conduct

Contributions are welcome. [CONTRIBUTING.md](CONTRIBUTING.md) covers setup, the commit style, and how to keep a benchmark change honest. By taking part you agree to the [Code of Conduct](CODE_OF_CONDUCT.md). If you find a security issue, please read the [Security Policy](SECURITY.md) first and report it privately. Past changes are recorded in the [Changelog](CHANGELOG.md).

## License

This project uses the BSD 3-Clause License, the same one django-mindoff uses. See the [LICENSE](LICENSE) file for the full terms.

[framework]: https://github.com/mindoffwork/django-mindoff
[docs]: https://django.mindoff.work
[pypi]: https://pypi.org/project/django-mindoff/
