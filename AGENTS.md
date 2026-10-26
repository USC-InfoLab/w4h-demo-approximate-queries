# AGENTS.md — w4h-demo-approximate-queries

Notebook-only W4H contribution that compares **`fft_approximate` approximate range averages** with exact averages on real imported wearable data. Setup and measured results: [README.md](./README.md). The shared W4H architecture overview is at the end of this file.

## Where this repo fits in W4H

- **Layer:** contribution, `kind: notebook` only, catalog slug `w4h-demo-approximate-queries` (default branch **`master`**, not `main`). It is not `runnable`, has no `run.sh` and no CLI entry point.
- **Unusual position:** this is the one contribution that **bypasses `w4h-api`** and connects straight to PostgreSQL with `psycopg2`. Comparing raw SQL query paths is the point of the demo, so `W4H_API_KEY` is not used.
- **Upstream dependencies:**
  1. `fft_approximate` installed on the same Postgres (`CREATE EXTENSION fft_approximate`).
  2. A dataset already ingested through the API, typically by `w4h-sample-fitbit-csv-importer`. The notebook reads its physical table directly, by default `ds_sample_fitbit_csv.fitbit_heart_rate` (`W4H_DATASET_SCHEMA`, `W4H_SIGNAL_TABLE`, `W4H_SUBJECT_ID` in `.env`). Those names come from the ingest convention `ds_<dataset_id>.<table_prefix>_<signal>`.
- **Downstream:** none. It produces notebook output and a scratch coefficient table; nothing in the platform reads them.

## What the notebook does

1. Pull a bounded slice (thousands of rows, not the full file) of `heart_rate` for one subject.
2. Compute the exact mean over a sub-window: the ground truth.
3. `numpy.fft.fft` the slice and insert `(k, c)` rows using the extension's `complex` type. This is done in Python because the extension's `create_approximation(...)` is not implemented.
4. Run `approximate_avg(c, t1, t2, signal_len ORDER BY k)` with increasing `K` (1, 5, 20, 100, all).
5. Report error against the exact value, plus timings.

At this scale the timing difference is negligible. The real takeaway is **accuracy versus number of coefficients kept**; keep README claims consistent with that.

## Layout and commands

```text
notebook/approximate_vs_exact.ipynb   the demo (direct psycopg2 + NumPy)
tests/test_coeffs.py                  pure-Python checks mirroring notebook helpers
pyproject.toml                        psycopg2-binary, numpy, python-dotenv; dev extra: pytest
.env.example                          PG* connection + dataset schema/table/subject
```

| Command | Purpose |
|---|---|
| `cp .env.example .env` | Set `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`, plus `W4H_DATASET_SCHEMA` / `W4H_SIGNAL_TABLE` / `W4H_SUBJECT_ID` |
| `pip install -e ".[dev]"` | Install dependencies |
| `pytest tests -q` | Python-side tests; no database needed |

**Client contract:** complex literals must be formatted `({real}{imag:+}j)`; `(1.5+-2.5j)` is rejected by the extension. `tests/test_coeffs.py` guards this.

## Hard boundaries

| Rule | Reason |
|---|---|
| No API key, no `csv-batch`, no writes to dataset tables | The demo reads imported data; ingest belongs to importer contributions |
| No CI tests that need `CREATE EXTENSION` | The C extension cannot be installed in a plain test run |
| Do not present approximate results as substitutes for exact clinical or audited aggregates | The README states this explicitly |
| Do not assume `w4h-docker` provides the extension | Postgres is external (ADR-015) |

## Git expectations for agents

- Do not `git commit` or `git push` unless the user asks.
- If notebook results change materially, update the README results table.

<!-- BEGIN w4h-system-overview: identical in every W4H repo's AGENTS.md. Edit all copies together. -->

## W4H system overview (shared across all repos)

**W4H (Wearables for Health) Toolkit** loads wearable-device data into PostgreSQL, organizes it by team, project and dataset, controls access, and runs curated analyses on it. Each signal is a **GeoMTS** (Geospatial Multivariate Time Series) table whose roles (`subject`, `time`, optional `geo`, `values[]`) are stored in `w4h.tables.mapping_json`, not in fixed column names. Three repos form the platform, one packages it, and the rest are **contributions** listed in the in-app catalog (`w4h.contributions`).

| Repo | Role |
|---|---|
| `w4h-api` | Express API and Postgres DDL (`w4h` schema): auth, ACL, ingest, catalog, contribution runner, SQL engine. Port 2026 |
| `w4h-app` | Vue 3 + Vite SPA; talks only to `w4h-api`. Port 5173 |
| `w4h-docs` | Product rules, MVP, ADRs and guides; imported by the API as in-app Help. Owns product decisions |
| `w4h-docker` | Compose stack (`api`, `app`, `notebooks`) built from sibling repos; Postgres is external |
| `w4h-sample-fitbit-csv`, `w4h-sample-icde-demo-csv` | Synthetic sample CSVs plus `manifest.yaml` (ICDE includes a `gps_track` geo signal) |
| `w4h-sample-fitbit-csv-importer`, `w4h-sample-icde-demo-csv-importer` | Runnable importers (notebook, CLI, `run.sh`) for those samples |
| `w4h-fitbit-csv-file-importer` | Runnable importer for user-supplied Fitbit CSVs: profile headers, review a drafted mapping, ingest |
| `w4h-sql-compute-mets` | SQL contribution (YAML + SQL template) that `w4h-api` executes in-process |
| `fft_approximate` | Postgres C extension, catalog slug `fft-approximate`; no API involvement |
| `w4h-demo-approximate-queries` | Notebook comparing `fft_approximate` with exact averages over direct Postgres |

**Main flows:**

1. **Ingest:** importers post 500-row chunks to `POST /datasets/:id/import/csv-batch`. `lib/ingest-csv.js` creates `ds_<dataset_id>.<table_prefix>_<signal>` and upserts its `w4h.tables` mapping.
2. **In-app Run (ADR-022):** `POST /contributions/:slug/run` makes `lib/contribution-runner.js` spawn `../<slug>/run.sh` with the user's `W4H_API_KEY`, `W4H_API_BASE` and `W4H_DATASET_ID`. Stdout lines `@@PROGRESS@@ {json}` drive the progress bar.
3. **SQL analytics (ADR-023):** `lib/sql-contribution-engine.js` reads `../<slug>/manifest.yaml` and `sql/`, binds identifiers from `w4h.tables`, and runs in-process. There is no free-SQL endpoint.
4. **Extensions:** the operator installs `fft_approximate` on their Postgres; notebooks call it directly.

**Layout:** clone every repo as a sibling in one folder. The API finds contributions at `../<slug>` (override `CONTRIBUTION_RUNNER_REPO_ROOT`) and docs at `DOCS_REPO_PATH=../w4h-docs`.

**Cross-repo changes:** `w4h-api` first (regenerate `API_INDEX.md`), then `w4h-app`, then `w4h-docs`. Catalog rows are seeded in `w4h-api/data/schema.sql`. Start at `w4h-docs/dev/mvp.md` and `w4h-docs/dev/ADR-README.md` for decisions, and `w4h-docs/dev/developer-setup.md` for local setup, getting an API key, test personas, troubleshooting, per-repo test commands, default branches and a glossary. Do not commit or push unless asked; never commit `.env` files, API keys or participant data.

<!-- END w4h-system-overview -->
