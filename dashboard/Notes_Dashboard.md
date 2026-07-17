# Flood Insurance Pricing prediction.

This is my note, documenting prompts I used. AI agents should not refer to this file for context.

## Claude Code first prompt

I cloned this git repo that contains code and analysis from my friend for a ML group project.
I plan to create a dashboard to visualise the data and a UI for predictive model.
Could you summarise what has been done so far and the key findings.
I believe the main analysis is in BE_notes.ipynb notebook.
We can start by generating the summary as a markdown file as well as a CLAUDE.md to facilitate future work.

## Drafting Plan

Let's create a PLAN.md to outline our plan for the dashboard, and to keep track progress.

First, I think I want to pull the full data and the CPI series, apply the cleaning (step 4 in the notebook) and inflation adjustment steps (step 5) and save the output to data/processed folder.
I don't want to touch Ben's notebook.
So we need to extract the relevant logic from the notebook, put them into python scripts (e.g. ingest.py, clean.py, inflation_adjust.py etc ) under src/data/ subfolder .
We will run these scripts on both full and sampled data.

Next, we probably need to do EDA and profiling, in a separate notebook (under notebooks/ subfolder).
I will likely use this draft what visualisations we want to put in the dashboard.

Then we can build an interactive dashboard using dash. The dashboard will have two main sections.
First, an interactive EDA, showing relevant features and findings in the dataset.
Second, a UI for the model: input features, models predictions, model explanations (feature importance, SHAP, lifts)  etc
We will do the second part later once we have the saved model from my friend.

Let me know if this is reasonable.



### Jupyter Notebook
In CLAUDE.md, I have added 'Working with Jupyter Notebooks' section, that I copied from one of my other project.
Essentially I want you to use Jupyter MCP Server. That section gives more details.

Let's try if the set-up and notebook workflow is working.
I have added an empty notebook notebooks/EDA.ipynb.
We will start with a simple plot:
I am thinking about how the median inflation-adjusted amountPaidOnBuildingClaim (target variable) varies by state.
We can show this in a Chloropeth map

I want to do this using plotly and polars. Use the processed sampled data.

Let me know if it is not clear, or not feasible or you notice a problem.


### Dashboard prototype

I want to start building the dash app.
What I roughly have in mind for the first page.

On the top:
A title: How much does flood insurance pay out in the USA ?

A control row of filters and Indicator cards showing summary of dataset:
Year dropdown selector (Let's call this F_Year for reference). Can be used to filter. Default is no year selected (not filtered).
Stat toggle: Median (or mean toggle) (F_Stat)
Real (Inflation-adjusted) amountPaidOnBuildingClaim payout (let's call this I_Payout for reference)
Number of records (does this correspond to number of claims ?) in the dataset (I_Freq)

Chart 1 (C1) Choropleth map showing median / mean (depends on what is selected) of payout for the selected year.
Clicking a state on the map would act like a filter.
It will affect I_Payout, I_Freq, C2, C3

Chart 2 (C2) would be histogram of both nominal / and real (inflation-adjusted) amountPaidOnBuildingClaim (just like in in BE_notes notebook section 6 EDA). There should be a toggle button of raw value vs log transformed, so that we can visualise its skewness.
This chart is affected by active filter on C1 (state), C3 (zone_family), F_Year selection.
C2 will be positioned to the right of C1.

Charts 3 (C3) is  a row of boxplots of payout by flood zone (zone_family), positioned under C1 and C2. Each flood zone will have its own boxplot, but they all share the same y-axis scale for ease of comparison
The order of flood zone family (from left to right would be Unknown, D (undetermined), A (SFHA no BFE), V (velocity), A (SFHA w/ BFE)).
This order should follow more or less increasing median payout. 
In each boxplots, there will horizontal line indicating the reference median (or mean accordingly) of the global (not filtered by zone) data.

If any boxplot is clicked, it would act as filter,
so it would update I_Payout, I_Freq, C1 and C2 accordingly with data filtered for that flood zone.
It will highlight the selected zone boxplot, and dim the other boxplots

Clicking any filter triggered again will remove that filter
And there should be a way to reset all filters.

So the basic layout would be something like

(Control and KPI row)
-------
C1 | C2
-------
  C3


Please look at similar dashboard implementation I have done before in C:\Users\ardih\Data\CMS_Health_Insurance_Exchange\dashboard
It has similar top row KPI, choropleth map and boxplots layout.
See the attached image for example layout. But of course note the different layout (C2 position) that I specify for our dashboard.

Let's plan how we would implement the dash app and let me review it first.
Don't generate code yet.
We will update the PLAN_UI.md with the plan details first, and we should generate AGENTS.md as well under the dashboard subfolder. Refer to PLAN.md and AGENTS.md structure in the above example implementation.

Let me know if this makes sense and feasible. Please flag if there is anything not clear or if you notice issue.


------

Read the dashboard/README.md .
Both EDA and model prediction section will likely have multiple pages each.
