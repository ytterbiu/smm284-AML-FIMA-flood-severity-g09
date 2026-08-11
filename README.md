# MSc AS - Term 3: SMM284 Applied Machine Learning - Group Project

![notebook CI](../../actions/workflows/notebook-ci.yml/badge.svg)

Term 3 group project for Applied Machine Learning (60% of coursework grade - 60%
of module).

- Group 09 working directory
- [Submitted Notebook](https://github.com/ytterbiu/smm284-AML-FIMA-flood-severity-g09/blob/main/a_submission-files-v0/SMM284_Group09_EvansKhanLiSudarmo.ipynb)
- [Final Notebook Updated After Submission](https://github.com/ytterbiu/smm284-AML-FIMA-flood-severity-g09/blob/main/a_submission-files-v1/SMM284_Group09_EvansKhanLiSudarmo.ipynb)

The updates contained within the git log. Changes made to the Final Version compared to the submitted notebook, include an additional GitHub actions check to see if the notebook runs from top to bottom without error, and markdown QOL formatting tweaks for the GitHub `ipynb` viewer.

## Dashboard

- Update 2026-07-17 Fri: merged dev_ui branch into main. To run dashboard
  created by @asudarmo, run:

```zsh
python dashboard/app.py
```

See the dashboard
[README](https://github.com/ytterbiu/smm284-AML-FIMA-flood-severity-g09/tree/main/dashboard)
for more information and setup information.

## Background

For this project we chose to look at a theoretical pricing review for a Lloyd's
syndicate writing US property-catastrophe flood reinsurance, prepared for the
pricing & capital committee ahead of the 2026–27 renewal.

We also recorded a YouTube presentation as part of this submission, available
via: https://youtu.be/B8rsYvt4Pxk

## Structure

```zsh
.
├── BE_notes.ipynb
├── README.md
├── a_submission-files-v0
│   ├── Generative_AI_statement.md
│   ├── Group Coursework Submission Form.docx
│   ├── README.txt
│   └── SMM284_Group09_EvansKhanLiSudarmo.ipynb
├── data
│   ├── processed
│   │   └── claims_sample.parquet
│   ├── raw
│   │   ├── FimaNfipClaimsV2.parquet
│   │   ├── cpiaucsl.csv
│   │   ├── cpiaucsl.provenance.json
│   │   └── provenance.json
│   └── sample
│       ├── nfip_sample.parquet
│       └── nfip_sample.provenance.json
├── data.py
├── export_sample.py
├── exports
│   └── dashboard
│       ├── baseline_zone_means.csv
│       ├── checksums.txt
│       ├── dashboard_support.py
│       ├── metadata.json
│       ├── model_gbm.joblib
│       ├── model_glm.joblib
│       ├── model_rf.joblib
│       ├── oot_scoreboard.csv
│       ├── oot_scoreboard_insurance.csv
│       ├── shap_mean_abs_by_feature.csv
│       ├── shap_sample_raw_features.parquet
│       └── shap_values_oot_sample.npz
├── models
│   ├── cv_results_full_oot_gbm.csv
│   ├── cv_results_full_oot_gbm_gammadev.csv
│   ├── cv_results_full_oot_glm.csv
│   ├── cv_results_full_oot_glm_gammadev.csv
│   ├── cv_results_sample_oot_gbm.csv
│   ├── cv_results_sample_oot_gbm_gammadev.csv
│   ├── cv_results_sample_oot_glm.csv
│   ├── cv_results_sample_oot_glm_gammadev.csv
│   └── tuned_params.json
└── requirements.txt
```

## Contents

- The full notebook executed end-to-end on the full 2.7M-row dataset with all
  outputs and figures saved.
- **data/** - provenance sidecars only. The FEMA claims parquet (~0.5 GB)
  exceeds upload limits and is deliberately excluded: the notebook's data cell
  downloads it from the pinned OpenFEMA URL and verifies the recorded hash
  against data/provenance.json. data/sample/ holds the small development fixture
  used when USE_SAMPLE = True.
- **models/** - read by the notebook at run time. tuned params.json lets re-runs
  load the hyperparameter search (seconds) instead of repeating it (hours); it
  retains the superseded MAE-scored record as evidence for the tuning-scorer
  correction discussed in the report (Reflection 8). The cv_results\*\*.csv
  files are the complete per-candidate search records for both scorer
  generations; one is read directly by the notebook.
- **exports/dashboard/** - static chart exports referenced in the video.

## Requirements

- Python 3.13.2 -> see requirements.txt
