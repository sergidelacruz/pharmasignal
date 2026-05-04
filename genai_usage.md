# GenAI Usage — PharmaSignal

This document is transparent about where and how AI tools were used in this project.
Being explicit about AI usage is a sign of professional maturity, not a weakness.

---

## Summary

| Phase | AI used? | How |
|---|---|---|
| Project design | Yes | Scoping business question, choosing domain, designing scoring model |
| Data generation | Yes | Writing `generate_data.py` with realistic seeding logic |
| SQL logic | Partial | First drafts generated, then reviewed, corrected, and understood line by line |
| Data validation | No | Manual review of row counts and score outputs |
| README & documentation | Partial | Structure suggested by AI, content written and verified by me |
| Power BI setup | No | Built manually following the README instructions |

---

## What AI helped with

**1. Scoping the problem**
I used Claude to brainstorm which pharma analytics problem would best demonstrate risk detection skills while being achievable with public data. The pharmacovigilance angle — adverse event monitoring — came from that conversation.

**2. Scoring model design**
I described what I wanted to measure (reporting rate, severity, novelty, velocity) and asked Claude to suggest appropriate weights and normalization approaches. I then adjusted the weights based on my own judgment about what a real pharmacovigilance team would prioritize.

**3. CTE chain structure**
The `03_risk_scores.sql` file was drafted with AI assistance. I then read every CTE step carefully, ran it in DuckDB, verified the intermediate outputs, and corrected two errors in the normalization logic (the portfolio average was initially being computed incorrectly before the drug filter was applied).

**4. Synthetic data realism**
The `generate_data.py` logic for seeding elevated risk patterns in three drugs was co-written with AI. I reviewed the output distribution to confirm it produced realistic-looking AE rates.

---

## What I did independently

- Chose the domain, business question, and storytelling structure
- Made all weight and threshold decisions in the scoring model
- Validated every output table against expected values
- Debugged the DuckDB pipeline (INITCAP function incompatibility, view vs table resolution)
- Built the Power BI report layout and chose the visual types
- Wrote all SQL comments explaining the business logic behind each step

---

## Why I'm documenting this

Modern analytics engineers use AI tools the same way they use Stack Overflow or documentation — to move faster and unblock themselves, not to avoid thinking. What matters is whether I can explain every line of code, defend every design decision, and debug what goes wrong. I can.

If you want to test this in an interview: ask me to walk through `03_risk_scores.sql` step by step, explain why the severity score uses the class average rather than the portfolio average, or describe what happens to the velocity score for a brand-new drug with no prior quarter. I know the answers.

---

## Tools used

- **Claude (Anthropic)** — project design, SQL drafts, data generation logic
- **DuckDB** — local SQL execution and validation
- **Power BI Desktop** — dashboard construction
- **GitHub** — version control and portfolio presentation
