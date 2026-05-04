"""
PharmaSignal — synthetic data generator
Produces 3 CSV files that mimic what a pharma sponsor's
safety database + sales system would export.
All drug names are fictional. AE patterns are seeded so
3 drugs (DRG001, DRG004, DRG006) carry elevated risk signals.
"""

import csv, random, math
from datetime import date, timedelta

random.seed(42)

# ── 1. drugs.csv ──────────────────────────────────────────
DRUGS = [
    ("DRG001","Veraximab",  "Oncology",   "HER2+ breast cancer",          "2022-04-01", 0.19),
    ("DRG002","Loretinib",  "Oncology",   "NSCLC EGFR-mutant",            "2021-09-01", 0.21),
    ("DRG003","Daxolimab",  "Oncology",   "Multiple myeloma",             "2020-03-01", 0.23),
    ("DRG004","Norafentix", "CNS",        "Treatment-resistant depression","2022-11-01", 0.12),
    ("DRG005","Zenpravox",  "CNS",        "Bipolar disorder",             "2019-06-01", 0.11),
    ("DRG006","Celvaxin",   "Cardiology", "Heart failure rEF",            "2022-08-01", 0.14),
    ("DRG007","Eptifenex",  "Cardiology", "Atrial fibrillation",          "2018-02-01", 0.13),
    ("DRG008","Durosamab",  "Cardiology", "Hypertrophic cardiomyopathy",  "2023-01-01", 0.15),
    ("DRG009","Symtravax",  "Infectious", "MDR-TB adjunct therapy",       "2020-07-01", 0.17),
    ("DRG010","Falotrimab", "Infectious", "HIV integrase inhibition",     "2021-03-01", 0.09),
    ("DRG011","Relixanib",  "Autoimmune", "Moderate-severe RA",           "2019-11-01", 0.16),
    ("DRG012","Omnivectin", "Autoimmune", "Moderate-severe Crohn's",      "2020-05-01", 0.14),
]

with open("/home/claude/pharmasignal/data/drugs.csv","w",newline="") as f:
    w = csv.writer(f)
    w.writerow(["drug_id","drug_name","therapeutic_area","indication",
                "launch_date","class_avg_serious_rate"])
    w.writerows(DRUGS)
print(f"drugs.csv — {len(DRUGS)} rows")

# ── 2. sales_volume.csv ───────────────────────────────────
MONTHLY_UNITS = {
    "DRG001":18500,"DRG002":22000,"DRG003":14200,"DRG004":31000,
    "DRG005":45000,"DRG006":28000,"DRG007":52000,"DRG008": 9800,
    "DRG009":12000,"DRG010":38000,"DRG011":41000,"DRG012":19500,
}

sales_rows = []
start = date(2018,1,1)
end   = date(2024,3,31)
d = start.replace(day=1)
while d <= end:
    for drug_id, base_units in MONTHLY_UNITS.items():
        launch_str_inner = next(r[4] for r in DRUGS if r[0]==drug_id)
        launch = date(*map(int, launch_str_inner.split("-")))
        if d >= launch.replace(day=1):
            noise = random.uniform(0.92, 1.08)
            sales_rows.append((drug_id, str(d)[:7], round(base_units * noise)))
    d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)

with open("/home/claude/pharmasignal/data/sales_volume.csv","w",newline="") as f:
    w = csv.writer(f)
    w.writerow(["drug_id","year_month","units_sold"])
    w.writerows(sales_rows)
print(f"sales_volume.csv — {len(sales_rows)} rows")

# ── 3. adverse_events.csv ─────────────────────────────────
BASE_REACTIONS = {
    "Oncology":   ["Nausea","Fatigue","Alopecia","Neutropenia","Thrombocytopenia","Anemia","Vomiting"],
    "CNS":        ["Headache","Dizziness","Insomnia","Somnolence","Nausea","Anxiety","Tremor"],
    "Cardiology": ["Dizziness","Hypotension","Bradycardia","Oedema","Fatigue","Dyspnea","Palpitations"],
    "Infectious": ["Nausea","Diarrhea","Fatigue","Headache","Rash","Fever","Vomiting"],
    "Autoimmune": ["Infection","Headache","Fatigue","Nausea","Rash","Arthralgia","Pyrexia"],
}
NOVEL_REACTIONS = {
    "DRG001": ["Hepatotoxicity","QT prolongation","Dyspnea"],
    "DRG004": ["Serotonin syndrome","Hallucination","Akathisia"],
    "DRG006": ["Hyperkalaemia","Renal impairment","Angioedema"],
}
OUTCOMES  = ["Non-serious","Moderate","Hospitalization","Disability","Death"]
REPORTERS = ["Physician","Consumer","Pharmacist","Other"]
COUNTRIES = ["US","US","US","US","US","US","DE","GB","FR","JP","CA"]

drug_lookup = {r[0]:r for r in DRUGS}
ae_rows = []
report_id = 10_000_000

for drug_id, drug_name, area, _, launch_str, class_avg in DRUGS:
    launch = date(*map(int, launch_str.split("-")))
    is_flagged = drug_id in NOVEL_REACTIONS
    out_w_normal  = [0.45, 0.30, 0.14, 0.07, 0.04]
    out_w_flagged = [0.25, 0.24, 0.28, 0.13, 0.10]

    d = launch.replace(day=1)
    while d <= date(2024,3,31):
        months_on = (d.year - launch.year)*12 + (d.month - launch.month)
        base_vol = min(20 + months_on*2, 80) + random.randint(-5,9)
        if is_flagged and months_on > 12:
            base_vol = int(base_vol * (1 + (months_on-12)*0.07))
        base_vol = max(base_vol, 3)

        for _ in range(base_vol):
            report_id += 1
            day  = random.randint(1,28)
            rdate = d.replace(day=day)
            qtr   = f"{rdate.year}-Q{(rdate.month-1)//3+1}"

            if is_flagged and months_on > 6 and random.random() < 0.38:
                reaction = random.choice(NOVEL_REACTIONS[drug_id])
                is_novel = True
            else:
                reaction = random.choice(BASE_REACTIONS[area])
                is_novel = False

            out_w   = out_w_flagged if is_flagged else out_w_normal
            outcome = random.choices(OUTCOMES, weights=out_w)[0]
            serious = outcome in ("Hospitalization","Disability","Death")

            ae_rows.append((
                report_id, drug_id, drug_name, area,
                str(rdate), qtr, months_on,
                reaction, int(is_novel), outcome, int(serious),
                random.choices(REPORTERS, weights=[42,28,18,12])[0],
                random.choice(COUNTRIES),
                random.choices(["18-44","45-64","65-74","75+"], weights=[15,40,30,15])[0],
                random.choice(["F","M","U"]),
            ))

        d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)

with open("/home/claude/pharmasignal/data/adverse_events.csv","w",newline="") as f:
    w = csv.writer(f)
    w.writerow(["report_id","drug_id","drug_name","therapeutic_area",
                "event_date","quarter","months_on_market",
                "reaction","is_novel_reaction","outcome","is_serious",
                "reporter_type","country","age_group","sex"])
    w.writerows(ae_rows)
print(f"adverse_events.csv — {len(ae_rows):,} rows")
