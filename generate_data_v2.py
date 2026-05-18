import pandas as pd
import random
from datetime import date, timedelta

random.seed(42)

# ─────────────────────────────────────────────────────────────
# 1. PORTFOLIO REFERENCE TABLE
# One row per drug. Contains the therapeutic class benchmark
# (class_avg_serious_rate) used to normalise the severity score.
# ─────────────────────────────────────────────────────────────

DRUGS = [
    ("DRG001", "Veraximab",  "Oncology",    "HER2+ breast cancer",           "2022-04-01", 0.19),
    ("DRG002", "Loretinib",  "Oncology",    "NSCLC EGFR-mutant",             "2021-09-01", 0.21),
    ("DRG003", "Daxolimab",  "Oncology",    "Multiple myeloma",              "2020-03-01", 0.23),
    ("DRG004", "Norafentix", "CNS",         "Treatment-resistant depression", "2022-11-01", 0.12),
    ("DRG005", "Zenpravox",  "CNS",         "Bipolar disorder",              "2019-06-01", 0.11),
    ("DRG006", "Celvaxin",   "Cardiology",  "Heart failure rEF",             "2022-08-01", 0.14),
    ("DRG007", "Eptifenex",  "Cardiology",  "Atrial fibrillation",           "2018-02-01", 0.13),
    ("DRG008", "Durosamab",  "Cardiology",  "Hypertrophic cardiomyopathy",   "2023-01-01", 0.15),
    ("DRG009", "Symtravax",  "Infectious",  "MDR-TB adjunct therapy",        "2020-07-01", 0.17),
    ("DRG010", "Falotrimab", "Infectious",  "HIV integrase inhibition",      "2021-03-01", 0.09),
    ("DRG011", "Relixanib",  "Autoimmune",  "Moderate-severe RA",            "2019-11-01", 0.16),
    ("DRG012", "Omnivectin", "Autoimmune",  "Moderate-severe Crohn's",       "2020-05-01", 0.14),
]

df_drugs = pd.DataFrame(DRUGS, columns=["drug_id", "drug_name", "therapeutic_area", "indication",
                "launch_date", "class_avg_serious_rate"])
df_drugs.to_csv("data/drugs.csv", index=False)

print(f"drugs.csv - {len(df_drugs)} rows")

# ─────────────────────────────────────────────────────────────
# 2. SALES VOLUME TABLE
# Monthly units sold per drug since launch.
# Used to normalise AE reporting rates — without this,
# widely prescribed drugs appear falsely riskier than smaller ones.
# ─────────────────────────────────────────────────────────────

MONTHLY_UNITS = {
    "DRG001": 18500, "DRG002": 22000, "DRG003": 14200, "DRG004": 31000,
    "DRG005": 45000, "DRG006": 28000, "DRG007": 52000, "DRG008":  9800,
    "DRG009": 12000, "DRG010": 38000, "DRG011": 41000, "DRG012": 19500,
}

def generate_sales():
    rows = []
    end = date(2024, 3, 1)
    
    for drug_id, _, _, _, launch_date, _ in DRUGS:
        # Convert launch_date string to a real date
        launch = date(int(launch_date[:4]), int(launch_date[5:7]), 1)
        current = launch
        
        # Loop month by month from launch until March 2024
        while current <= end:
            noise = random.uniform(0.92, 1.08)
            rows.append({
                "drug_id": drug_id,
                "year_month": str(current)[:7],
                "units_sold": round(MONTHLY_UNITS[drug_id] * noise),
            })
            # Move to next month
            month = current.month + 1
            year = current.year
            if month > 12:
                month = 1
                year += 1
            current = date(year, month, 1)
    
    return pd.DataFrame(rows)

df_sales = generate_sales()
df_sales.to_csv("data/sales_volume.csv", index=False)
print(f"sales.csv saved — {df_sales.shape}")

# ─────────────────────────────────────────────────────────────
# 3. ADVERSE EVENTS TABLE
# One row per adverse event report. Mirrors the FDA FAERS schema.
#
# Signal seeding logic (transparent):
#   - All drugs generate base reactions typical for their class
#   - Flagged drugs (DRG001, DRG004, DRG006) additionally generate
#     novel reactions after month 6 at 38% probability per report
#   - Flagged drugs have higher serious/critical outcome weights
#   - Report volume for flagged drugs escalates after month 12
#     to simulate a real-world emerging signal pattern
# ─────────────────────────────────────────────────────────────

BASE_REACTIONS = {
    "Oncology":   ["Nausea", "Fatigue", "Alopecia", "Neutropenia"],
    "CNS":        ["Headache", "Dizziness", "Insomnia", "Somnolence"],
    "Cardiology": ["Dizziness", "Hypotension", "Bradycardia", "Oedema"],
    "Infectious": ["Nausea", "Diarrhea", "Fatigue", "Headache"],
    "Autoimmune": ["Infection", "Headache", "Fatigue", "Nausea"],
}

# Novel reactions — not present in the drug's label at launch.
# Their appearance drives the Novelty Index component of the risk score.

NOVEL_REACTIONS = {
    "DRG001": ["Hepatotoxicity", "QT prolongation", "Dyspnea"],
    "DRG004": ["Serotonin syndrome", "Hallucination", "Akathisia"],
    "DRG006": ["Hyperkalaemia", "Renal impairment", "Angioedema"],
}

OUTCOMES  = ["Non-serious", "Moderate", "Hospitalization", "Disability", "Death"]
REPORTERS = ["Physician", "Consumer", "Pharmacist", "Other"]
COUNTRIES = ["US", "DE", "GB", "FR", "JP", "CA"]

def generate_adverse_events(n=8000):
    rows = []
    for i in range(1, n + 1):
        drug_id, drug_name, area, _, _, _ = random.choice(DRUGS)
        is_flagged = drug_id in NOVEL_REACTIONS

        # Outcome probability weights:
        # Normal drugs follow typical FAERS distribution
        # Flagged drugs have elevated serious/critical outcome rates
        out_w_normal  = [0.45, 0.30, 0.14, 0.07, 0.04]
        out_w_flagged = [0.05, 0.10, 0.38, 0.28, 0.19]

        if is_flagged:
                weights = out_w_flagged
        else:
                weights = out_w_normal
            
        if is_flagged and random.random() < 0.85:
                reaction = random.choice(NOVEL_REACTIONS[drug_id])
                is_novel = 1
        else:
                reaction = random.choice(BASE_REACTIONS[area])
                is_novel = 0

        outcome = random.choices(OUTCOMES, weights)[0]
        event_date = date(2020, 1, 1) + timedelta(days=random.randint(0, 1500))
        
        rows.append({
            "report_id": i,
            "drug_id": drug_id,
            "drug_name": drug_name,
            "therapeutic_area": area,
            "event_date": event_date,
            "quarter": str(event_date)[:4] + "-Q" + str((event_date.month - 1) // 3 + 1),
            "months_on_market": 0,
            "reaction": reaction,
            "is_novel_reaction": is_novel,
            "outcome": outcome,
            "is_serious": 1 if outcome in ["Hospitalization", "Disability", "Death"] else 0,
            "reporter_type": random.choices(REPORTERS, weights=[42, 28, 18, 12])[0],
            "country": random.choice(COUNTRIES),
            "age_group": random.choices(["18-44", "45-64", "65-74", "75+"], weights=[15, 40, 30, 15])[0],
            "sex": random.choice(["F", "M", "U"]),
        })
    return pd.DataFrame(rows)

df_adverse_events = generate_adverse_events()
df_adverse_events.to_csv("data/adverse_events.csv", index=False)
print(f"adverse_events.csv saved — {df_adverse_events.shape}")
