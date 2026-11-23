# Opening the Power BI project

1. Install Power BI Desktop (Microsoft Store version works) and enable *File > Options > Preview features >
   Power BI Project (.pbip) save option* if your version asks for it.
2. Regenerate the project with the path of YOUR copy of the repository (the published files contain a placeholder):
   `python src/build_pbip.py --data-folder "C:\path\to\your\copy\data\processed\\"` (keep the trailing backslash).
3. Open `powerbi/GrowthCampaigns.pbip`, then *Refresh*. Three pages: **Campaign scorecard**, **Funnel**,
   **Cohorts & retention**. Every visual title ends with "· SIMULATED".
4. The model reads `campaign_scorecard.csv`, `funnel_by_region_channel.csv`, `cohort_matrix_weekly.csv` and
   `retention_by_channel_month_model.csv`; measures are in `_Measures` (also listed in `measures.dax`).

If the project does not open in your Desktop version, `bi_spec.md` describes the same pages, measures and filters.
