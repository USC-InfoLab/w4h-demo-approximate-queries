# W4H Demo: Approximate Queries (fft_approximate)

Notebook-only demo of [`fft_approximate`](https://github.com/USC-InfoLab/fft_approximate) — a PostgreSQL C extension for approximate range-aggregate queries over a compressed (FFT coefficient) representation of a time series — compared side by side against an exact query on the same raw data.

**Publisher:** usc-infolab · **Kind:** notebook (illustrative only — no CLI, no `[project.scripts]` entry) · **Language:** Python

## Not a replacement for exact aggregates

`fft_approximate` trades accuracy for size/speed by storing a **truncated Fourier coefficient representation** of a signal instead of (or alongside) the raw rows, then computing range averages directly from that compressed representation. It is useful when you want a fast, "good enough" estimate over a large or already-compressed series — it is **not** a substitute for an exact `AVG()`/`COUNT()` when correctness matters (billing, clinical thresholds, anything audited). The error bound depends entirely on how many harmonics (coefficients) you keep — more coefficients converge toward the exact value, at the cost of the "compression" that makes the approach worthwhile in the first place.

## Prerequisite: install the extension

`fft_approximate` must be installed on **your own PostgreSQL server** before this notebook can run — it is not part of `w4h-docker`'s Compose stack (Postgres is external, per [ADR-015](https://github.com/USC-InfoLab/w4h-docs/blob/main/dev/ADR-015-docker-deployment-packaging.md)). Follow [`guide/docker-deployment.md` § Optional: approximate-query extension (fft_approximate)](https://github.com/USC-InfoLab/w4h-docs/blob/main/guide/docker-deployment.md#optional-approximate-query-extension-fft_approximate) for the install steps and platform-specific gotchas (AppArmor on Ubuntu, SELinux `restorecon` on RHEL/Fedora, the macOS App Management privacy grant for Postgres.app).

**Not supported on RDS/Aurora/Cloud SQL** — those hosts don't allow custom C extensions.

## What this notebook actually demonstrates

`fft_approximate`'s own `create_approximation(...)` helper (which would compute and insert FFT coefficients from raw signal rows for you) is **explicitly marked "not implemented" in the extension's own README** — confirmed by reading the shipped source. This notebook does that step itself in Python (`numpy.fft.fft`) rather than depending on a feature the extension doesn't actually provide yet. If a future version of `fft_approximate` implements `create_approximation`, this notebook's manual coefficient-insertion cell becomes optional.

Steps:
1. Pull a bounded slice of real `heart_rate` values for one subject (a few thousand rows — this demo does **not** need or use the full multi-hundred-thousand-row sample file).
2. Compute the exact mean over a sub-window of that slice directly in Python/SQL — the ground truth.
3. Compute the full FFT of the slice (`numpy.fft.fft`), insert the resulting complex coefficients into a plain table (`k integer, c complex`).
4. Run `approximate_avg(c, t1, t2, signal_len ORDER BY k)` over the **same window**, using only the first `K` coefficients for increasing `K` (1, 5, 20, 100, all) — this is where the extension's compression/accuracy tradeoff actually shows up.
5. Compare each approximate result's error against the exact value, and compare query timings.

### Real numbers from a verification run against 2,048 real sample rows (one subject, `heart_rate`)

| Coefficients used (`K`) | Approx. mean | Exact mean | Error |
|---|---|---|---|
| 1 (DC term only) | 99.070 | 103.472 | 4.25% |
| 5 | 101.219 | 103.472 | 2.18% |
| 20 | 103.524 | 103.472 | 0.05% |
| 100 | 103.465 | 103.472 | 0.006% |
| 2048 (all) | 103.441 | 103.472 | 0.03%* |

\*Not exactly 0% even with all coefficients — floating-point round-trip through the `complex` type's text representation, not a bug.

At this small, bounded scale (2K rows), the *query timing* difference between the approximate and exact paths is negligible (sub-millisecond either way) — the honest takeaway from this demo is the **accuracy-vs-coefficient-count relationship**, not a timing win. The extension's real timing advantage shows up at a scale this demo deliberately does not exercise: querying a compact coefficient table (e.g. 20-100 rows) instead of scanning millions of raw rows. See the main [W4H Docker deployment guide](https://github.com/USC-InfoLab/w4h-docs/blob/main/guide/docker-deployment.md) for the real-world context (the bundled Fitbit sample's `calories.csv` alone is 1.2M+ rows) that motivates this extension in the first place.

## Prerequisites

- A PostgreSQL server with `fft_approximate` installed (see above)
- A dataset already imported with `heart_rate` or `calories` data (e.g. via [`w4h-sample-fitbit-csv-importer`](https://github.com/USC-InfoLab/w4h-sample-fitbit-csv-importer)) — only a bounded slice is needed, not the full file

## Credentials

```bash
cp .env.example .env
# set PGHOST / PGPORT / PGUSER / PGPASSWORD / PGDATABASE for your Postgres
```

This notebook connects to Postgres **directly** (not via the W4H API) — that's the point of the demo, comparing raw SQL query paths. `W4H_API_KEY` is not used here.

## Install

```bash
pip install -e ".[dev]"
```

## Notebook

Open [`notebook/approximate_vs_exact.ipynb`](notebook/approximate_vs_exact.ipynb).

## Tests

```bash
pytest tests -q
```

Tests exercise the coefficient-formatting and error-calculation logic against fixture arrays — they do **not** require a live Postgres connection (no CI-friendly way to install a C extension in a plain test run), so they cover the Python-side math only, not a live round trip through the extension.
