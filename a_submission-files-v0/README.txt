# README.txt

> Note: whilst this is a txt file, we have formatting this using Markdown for
> section headers and overall clarity

## Key information:

- SMM284 - Applied Machine Learning
- Group Coursework 2025-26
- Group: Group 09
- Authors in alphabetical order (student IDs):
  - Benjamin Evans (170047831)
  - Basmah Khan (250059342)
  - Cheng Li (250050117)
  - Ardi Wira Sudarmo (250056737)

- Institution: Bayes Business School - City St George's, University of London
- Date: 15 Jul 2026
- Description: Term 3 group project for SMM284 Applied Machine Learning

## Video link

The video for our presentation is available via: https://youtu.be/B8rsYvt4Pxk

- This is an unlisted video on YouTube.

## Submission file structure

The directory structure is as follows

Created and pasted using the `tree -L 3` command in the zsh terminal

```{zsh}
.
└── SMM284_Group09_EvansKhanLiSudarmo
    ├── Generative_AI_statement.md
    ├── SMM284_Group09_EvansKhanLiSudarmo.ipynb
    ├── README.txt
    └── TBC
    ├── data
    │   ├── processed
    │   │   └── claims_sample.parquet
    │   ├── raw
    │   │   ├── cpiaucsl.csv
    │   │   ├── cpiaucsl.provenance.json
    │   │   └── provenance.json
    │   └── sample
    │       ├── nfip_sample.parquet
    │       └── nfip_sample.provenance.json
    └── models
        ├── cv_results_full_oot_gbm.csv
        ├── cv_results_full_oot_gbm_gammadev.csv
        ├── cv_results_full_oot_glm.csv
        ├── cv_results_full_oot_glm_gammadev.csv
        ├── cv_results_sample_oot_gbm.csv
        ├── cv_results_sample_oot_gbm_gammadev.csv
        ├── cv_results_sample_oot_glm.csv
        ├── cv_results_sample_oot_glm_gammadev.csv
        └── tuned_params.json
```

## Submission checklist

1. [x] Jupyter notebook (.ipynb), which is the report
2. [x - included in ipynb] Dataset file, or a script that downloads or generates
   it
3. [x] README.txt listing group members, student IDs, and the presentation video
       link (can be inside the notebook appendix, or as a separate file)
4. [x] Generative AI usage statement (can be inside the notebook appendix or as
       a separate file)
