# Orchestrated FX Rates Pipeline (Apache Airflow)

A production-style batch pipeline orchestrated by **Apache Airflow 3**. Every day it
extracts foreign-exchange reference rates from a public API, validates and reshapes
them, loads them into a warehouse table, and verifies what landed. Failures retry with
exponential backoff and page a Slack channel.

```mermaid
flowchart LR
    A[Frankfurter API<br/>ECB reference rates] -->|GET /v1/&lt;ds&gt;| B[extract]
    B -->|raw JSON<br/>data/landing/raw/&lt;ds&gt;.json| C[transform]
    C -->|validated CSV<br/>data/landing/clean/&lt;ds&gt;.csv| D[load]
    D -->|replace partition<br/>in one transaction| E[(fx_rates)]
    E --> F[quality_check]
    F -.->|fails fast, no retry| X[:rotating_light: Slack]
    B & C & D -.->|retry ×3, backoff 1→2→4 min| R[:warning: Slack]
    R -.->|retries exhausted| X
    subgraph Airflow DAG: fx_rates_pipeline · daily 06:00 UTC
      B
      C
      D
      F
    end
```

## What it demonstrates

| Concern | How it is handled |
| --- | --- |
| **Orchestration** | TaskFlow DAG `extract → transform → load → quality_check`. Tasks pass file paths and row counts through XCom, never data. `catchup=False`, `max_active_runs=1`. |
| **Idempotency** | Every task is keyed by the run's logical date (`ds`). Raw and clean files are overwritten per day; the loader deletes and re-inserts the day's partition inside **one transaction**, so re-runs and backfills never duplicate rows. |
| **Retries** | Two layers. Inside a task, `requests` retries 429/5xx a few times with short backoff. At the Airflow layer, `default_args` set `retries=3` with **exponential backoff** (1 → 2 → 4 min, capped at 15) and a 10-minute `execution_timeout` so a hung call fails and retries instead of blocking a worker slot. |
| **Alerts** | `on_retry_callback` posts a warning on every failed attempt; `on_failure_callback` posts once when retries are exhausted, with DAG, task, run, attempt count, exception and a log link. A DAG-level success callback gives a heartbeat. Without a webhook everything is still written to the task log. Callbacks never raise. |
| **Data quality gate** | `transform` rejects the whole day on any contract violation (non-numeric or non-positive rate, bad ISO code, duplicate pair) because partial FX data is worse than none. `quality_check` re-reads the warehouse and fails the run immediately (`retries=0`) if the row count, uniqueness or sign checks fail. |
| **Testing** | 46 pytest tests: HTTP behaviour with mocked responses (retry on 503, no retry on 404, bad payloads), validation rules, transactional reload semantics on SQLite, the quality gate, alert formatting and delivery, and **DAG integrity tests** (import errors, task order, retry settings, callbacks wired). |
| **CI** | GitHub Actions installs Airflow with its official constraints, lints, runs the tests, then executes the real DAG twice with `airflow dags test` and asserts the partition did not grow. |
| **Portability** | SQLite by default (zero setup), Postgres via `DATABASE_URL`. Docker Compose brings up Postgres + Airflow in one command. |

## Project structure

```
├── airflow/
│   ├── dags/fx_rates_pipeline.py   # the DAG: tasks, retry policy, callbacks
│   └── Dockerfile                  # apache/airflow:3.0.6 + pipeline deps
├── src/pipelines/
│   ├── extract.py     # API → raw landing zone (HTTP retries, payload checks)
│   ├── transform.py   # unpivot + validation contract → clean CSV
│   ├── load.py        # SQLAlchemy table, transactional partition replace, health query
│   ├── quality.py     # post-load gate shared by the DAG task and the CLI runner
│   ├── alerts.py      # Slack/log alerting callbacks for failure, retry, success
│   ├── config.py      # settings from env / .env
│   └── run.py         # run the same steps without Airflow
├── tests/             # unit tests + DAG integrity tests
├── sql/init.sql       # creates the airflow + warehouse databases in Postgres
├── docker-compose.yml # Postgres + Airflow standalone
└── Makefile
```

## Quick start

### 1. Run the ETL without Airflow

```bash
make setup                      # venv + pipeline + dev tools
make run DATE=2024-01-15        # extract → transform → load → quality check
make test                       # 46 tests; DAG tests skip until Airflow is installed
```

Output lands in `data/landing/` and `data/warehouse.db` (SQLite).

### 2. Run the DAG with Airflow, no Docker

```bash
make setup-airflow              # installs Airflow 3.0.6 with official constraints
make test                       # now includes the DAG integrity tests
make dag-test DATE=2024-01-15   # executes every task through Airflow's runner
```

### 3. Full stack with Docker (Airflow UI + Postgres)

```bash
cp .env.example .env            # optionally add SLACK_WEBHOOK_URL
make up                         # http://localhost:8080, no login needed locally
```

Trigger `fx_rates_pipeline` from the UI, or backfill a range:

```bash
docker compose exec airflow airflow backfill create \
  --dag-id fx_rates_pipeline --from-date 2024-01-01 --to-date 2024-01-31
```

## Alerts

Set `SLACK_WEBHOOK_URL` to a Slack incoming webhook. Example of what arrives
after an outage of the source API:

```
:warning: *Airflow task retrying* `fx_rates_pipeline.extract`
run: `scheduled__2024-01-15T06:00:00+00:00`  attempt 1 of 4 failed
error: `ExtractError: https://api.frankfurter.dev/v1/2024-01-15 returned HTTP 503: ...`
logs: http://localhost:8080/dags/fx_rates_pipeline/runs/scheduled__2024-01-15T06:00:00+00:00/tasks/extract

... (attempts 2 and 3) ...

:rotating_light: *Airflow task FAILED* `fx_rates_pipeline.extract`
run: `scheduled__2024-01-15T06:00:00+00:00`  logical date: 2024-01-15
attempts exhausted: 4/4
error: `ExtractError: ... returned HTTP 503: ...`
logs: http://localhost:8080/dags/fx_rates_pipeline/runs/scheduled__2024-01-15T06:00:00+00:00/tasks/extract
```

`ALERT_ON_RETRY=false` keeps the channel quiet until retries are exhausted.
To use email instead, point the same callbacks at Airflow's SMTP provider or set
`email_on_failure` in `default_args`; the message builders in `alerts.py` are channel-agnostic.

## Design notes

* **Why a public API instead of a CSV?** Extracting over the network is where retries and
  alerts earn their keep: timeouts, 5xx responses and rate limits are the realistic
  failure modes the retry policy is tuned for.
* **Why file hand-offs between tasks?** Tasks may run on different workers. Passing
  paths through XCom keeps XCom small and makes each step independently re-runnable.
* **Weekend semantics.** The API answers a Saturday request with Friday's fixing. The
  table keeps both `as_of_date` (the run's logical date, the idempotency key) and
  `rate_date` (what the rate actually represents).
* **Quality check has no retries.** A retry only helps with transient faults. Bad data
  is not transient, so the gate fails immediately and alerts.
* **Airflow 3.** Uses the `airflow.sdk` TaskFlow API. Task SLAs were removed in
  Airflow 3.0; `execution_timeout` plus alerting covers the "took too long" case here.

## Configuration

See [.env.example](.env.example). Everything is read from the environment, so the same
code runs locally, in Docker and in CI without edits.
