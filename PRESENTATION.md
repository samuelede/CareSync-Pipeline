# CareSync: Quality-Gated Weekly Data Platform
### Nexora Health — Project Presentation

---

## Slide 1: The Problem

Nexora's partner clinics deliver data through a third-party agent, six
CSVs a week, no control over timing or quality. Before this project:

- No SLA monitoring, late files discovered only when reports go stale
- No pre-ingestion quality gate, malformed data flows straight to the warehouse
- No failure isolation, one bad file holds five healthy datasets hostage
- No stakeholder alerting, failures found by reading logs
- No post-processing check that the reporting layer is actually trustworthy

---

## Slide 2: The Fix, Two Ideas

1. **Validate at both ends.** A gate before ingestion protects the
   warehouse; a gate after transformation protects stakeholders.
2. **Skip, don't fail.** A rejected file is quarantined; its dependents
   cascade-skip; everything else loads normally.

---

## Slide 3: Architecture

Sensing → Pre-validation → Load (Snowflake RAW) → dbt (STAGING → PROD) →
Post-validation → Notify. Three databases: `NEXORA_RAW_WH`,
`NEXORA_STAGING_WH`, `NEXORA_PROD_WH`.

---

## Slide 4: The Dimensional Model

Single-fact star schema: `fct_appointments` surrounded by
`dim_patients`, `dim_clinics`, `dim_providers`, `dim_payers`, plus
`conditions_detail`. Schema verified against a real Synthea export,
caught real gaps (`NPI`, `OWNERSHIP`, `SYSTEM`, `hospice`/`snf`).

---

## Slide 5: Proof, Not Assertions

- Real Synthea data run through the full pipeline
- Comprehensive dirty batch: two failure modes in one run
- Full pipeline run live against real Snowflake, locally and in GitHub Actions
- Great Expectations verified to agree exactly with pandas on both
  pre-validation AND post-validation, live, on the same real run

---

## Slide 6: Dev-to-Prod, One Environment Variable

| | Testing | Production |
|---|---|---|
| Validation | pandas | Great Expectations |
| Orchestration | GitHub Actions | Airflow |
| Landing zone | Google Drive | SFTP |

---

## Slide 7: Confirmed vs. Needs Your Environment

Confirmed live: Snowflake load, dbt, both validation engines
(pre-validation and post-validation), Slack/email, GitHub Actions,
cascade-skip, dirty-data drill.

Needs live confirmation: SFTP live path, Airflow DAG under a real
scheduler.

---

## Slide 8: Lessons

- A pre-ingestion gate and a post-transformation gate catch different failures
- "Skip" and "fail" collapsed into one status trains teams to ignore alerts
- Prove logic simply first, then re-express it, don't redesign when tools change
- PHI minimization at the staging boundary is structural; enforced later it's a promise
