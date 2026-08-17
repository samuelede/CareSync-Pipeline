# Landing zone (Week 1-2 testing phase)

This is the drop zone for the six weekly CSVs during the pandas +
GitHub Actions build (Phase 1). It plays the role of the shared Google
Drive folder the third-party aggregation agent delivers into:

```
data/landing/<run_id>/organizations.csv
data/landing/<run_id>/providers.csv
data/landing/<run_id>/payers.csv
data/landing/<run_id>/patients.csv
data/landing/<run_id>/encounters.csv
data/landing/<run_id>/conditions.csv
```

Populate it with:

```bash
python -m scripts.simulate_weekly_drop --run-id <run_id>       # synthetic, no dependencies
./scripts/generate_synthea_data.sh <num_patients> <run_id>     # real Synthea, needs Java
```

`sensing/drive_sensor.py` reads from here in local-simulation mode (used
whenever `GDRIVE_FOLDER_ID` is not configured) and downloads real Drive
files here in live mode. Week 3 (production) points the same downstream
pipeline at an SFTP server instead. Nothing past the sensing step reads
"Google Drive" or "SFTP" directly; everything downstream just reads
`data/landing/<run_id>/*.csv`, so that swap changes zero pipeline logic.
