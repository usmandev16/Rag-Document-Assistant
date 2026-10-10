"""Generate the synthetic shipments spreadsheet used by the eval.

Same 17 columns and 126 rows as the original (real) sheet, but every value is
made up: fake shipper, areas, CN numbers, products and amounts. Fixed seed, so
re-running produces the same file. Also prints the expected answers for the
10 aggregation questions in eval/dataset.jsonl, computed directly with pandas.

    python eval/make_synthetic_sheet.py
"""
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "Test documents" / "shipments_synthetic.xlsx"
ROWS = 126
rng = random.Random(2026)

CITIES = ["LAHORE"] * 10 + ["KARACHI"] * 4 + ["ISLAMABAD"] * 3 + ["RAWALPINDI"] * 3 + [
    "FAISALABAD", "MULTAN", "PESHAWAR", "QUETTA", "SIALKOT", "GUJRANWALA", "HYDERABAD", "BAHAWALPUR",
    "SARGODHA", "SUKKUR", "ABBOTTABAD", "MARDAN", "SAHIWAL", "OKARA",
]
PRODUCTS = ["Ceramic Mug", "Cotton T-Shirt", "Desk Lamp", "Phone Case", "Notebook Set", "Water Bottle",
            "Wireless Mouse", "Kitchen Towel Pack", "Hair Brush", "Travel Pouch", "Spice Jar Set", "Wall Clock"]
STATUSES = (["Delivered"] * 50 + ["Booked"] * 30 + ["Shipment Received"] * 15 + ["Return Submitted"] * 6
            + ["REACHED at DEST. BRANCH"] * 5 + ["MOVED to DEST. BRANCH"] * 4 + ["MOVED to ORIGIN BRANCH"] * 3)
UNDELIVERED = ["REFUSED TO RECEIVE", "HOLD ON CONSIGNEE REQUEST", "PAYMENT NOT AVAILABLE"]


def fmt(d: date) -> str:
    return d.strftime("%d %B %Y")  # same text format as the original, e.g. "01 September 2026"


rows = []
for i in range(ROWS):
    booked = date(2026, 9, 1) + timedelta(days=rng.choice([0] * 3 + list(range(1, 12))))
    status = rng.choice(STATUSES)
    non_cod = rng.random() < 0.08
    pieces = rng.choice([1, 1, 1, 2, 2, 3, 4])
    rows.append({
        "BookingDate": fmt(booked),
        "PickupDate": fmt(booked + timedelta(days=rng.choice([0, 1, 2]))) if rng.random() < 0.6 else None,
        "CNNo": 99900000000000 + rng.randrange(10**8),
        "Ref #": f"#S{1000 + i}",
        "Origin": "LAHORE",
        "Origin Area": rng.choice(["DEMO TOWN"] * 9 + ["SAMPLE PARK"]),
        "Shipper Name": "demo-store.example",
        "Destination": rng.choice(CITIES),
        "Pieces": pieces,
        "Weight": round(rng.uniform(0.2, 3.0) * pieces, 2),
        "Description": f"{rng.choice(PRODUCTS)} Qty={pieces}",
        "COD Amount": 0.0 if non_cod else float(rng.randrange(500, 12000, 10)),
        "Service Type": "NON-COD OverNight" if non_cod else "COD",
        "Status Date": fmt(booked + timedelta(days=rng.choice([1, 2, 3, 4]))),
        "Current Status": status,
        "Undelivered Reason": rng.choice(UNDELIVERED) if status == "Return Submitted" else None,
        "Canceled Reason": None,
    })

df = pd.DataFrame(rows)
OUT.parent.mkdir(exist_ok=True)
df.to_excel(OUT, index=False)

delivered = df[df["Current Status"] == "Delivered"]
by_city = df["Destination"].value_counts()
assert by_city.iloc[0] > by_city.iloc[1], "top destination must be unique"
print(f"Wrote {OUT} ({len(df)} rows, {len(df.columns)} columns)")
print("Expected answers:")
print("  q031 rows:", len(df))
print("  q032 delivered:", len(delivered))
print("  q033 total COD:", round(df["COD Amount"].sum(), 1))
print(f"  q034 top destination: {by_city.index[0].title()} ({by_city.iloc[0]} shipments)")
print("  q035 to Karachi:", int((df["Destination"] == "KARACHI").sum()))
print("  q036 NON-COD:", int(df["Service Type"].str.contains("NON-COD").sum()))
print("  q037 max COD:", df["COD Amount"].max())
print("  q038 Return Submitted:", int((df["Current Status"] == "Return Submitted").sum()))
print("  q039 booked 1 Sep 2026:", int((df["BookingDate"] == "01 September 2026").sum()))
print("  q040 delivered COD total:", round(delivered["COD Amount"].sum(), 1))
