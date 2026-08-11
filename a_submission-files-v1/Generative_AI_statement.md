# Generative AI Statement

GenAI functioned as an additional technical resource to assist with code
troubleshooting, methodological validation, and drafting visualisations. All
analysis, statistical interpretation, and substantive content originated with
the group. Where AI tools assisted with prose, the group authored the draft
first, reviewed every suggestion, and retained final editorial control.

## 1. Tools Used

- Google Gemini 3 Pro (Deep Research)
- Claude (Anthropic) Opus 4.8 & Fable 5

## 2. Permitted Tasks & Usage Notes

The tools were provided with the coursework word document, weekly `.ipynb`
notebooks, and extracts from our codebase. Usage fell into the following
permitted categories:

- Code Help, Debugging, and Syntax Lookup:
  - Used to identify compilation errors and review Python code structure
- Drafting Visualisations and Chart Code:
  - Assisted in formatting and debugging plotting issues
- Editing or Improving Writing:
  - Assisted with converting draft content between document formats and checking
    grammatical structure
  - Simplified unnecessarily technical phrasing in draft prose with
    plain-English equivalents
  - Suggested restructuring within sections including reordering paragraphs so
    that rejected alternatives follow the options adopted
  - In one instance the tool proposed a qualifier on our target-leakage claim
    ("on its own"), which we reviewed against our own audit and accepted
- Explaining Methods/Concepts:
  - Used to clarify conceptual assumptions (e.g., explaining nuances in flood
    reinsurance)

## 3. Example Prompts

Below is a representative sample of prompts used for coding and debugging
assistance. Rather than an exhaustive list of every iterative query, we have
included one example of each primary prompt type:

- Code Troubleshooting:
  - "When running the full data rather than sample this throws up error
    NameError: name 'full' is not defined..."
- Conceptual Clarification:
  - "We have used an out-of-time validation to try to see what edge survives on
    future years, does this make sense?"
- Content Summarisation:
  - "Help to identify the key points in this extract/paper..."
- Prose Editing:
  - "Help with rephrasing something in plain business English: [draft
    paragraph]... terms like 'idempotently' are potentially confusing"
- Plotting Adjustments:
  - "This histogram takes ~4 minutes to plot - how can we make this more
    efficient"
