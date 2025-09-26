
# Housing Affordability Dashboard — Sydney (SA2, Synthetic)

This prototype implements the logic from your **Dashboard proposal design** using **synthetic** SA2-level data and an **approximate SA2 grid** around Sydney.
No uncertain metrics are included: only Median Rent, Median Price, Median Income, PTI, RTI, plus buyer-specific calculations (Years_to_Deposit, MTI).

## Features
- Interactive choropleth map (12 SA2-like cells) with layers: Median Rent, Median Price, Median Income, PTI, RTI.
- Renter view: bedroom slider (1–3 BR) with transparent coefficients (1.00/1.35/1.75), RTI highlighting.
- Buyer view: inputs for savings, income, saving rate, deposit %, mortgage rate and term; calculates Years_to_Deposit, monthly payment, and MTI with threshold warnings.
- Time-series charts with presets (Max/5y/3y/1y) and custom dates. Synthetic data from 2015-01 to 2025-09.
- Comparison table for up to 3 selected SA2 areas.
- Clear tooltips/explanations and rule-based insights (stress thresholds).

## How to run
```bash
# 1) Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate

# 2) Install dependencies
pip install -r requirements.txt

# 3) Launch Streamlit app
streamlit run app.py
```

## Notes
- The SA2 geometry here is an **approximate grid** purely for prototyping interactions. Replace it later with official SA2 GeoJSON for Sydney.
- All calculations and UI logic follow the **proposal** (PTI, RTI, buyer calculator). No questionable metrics (like vacancy) are included.
- Defaults: Deposit 20%, Saving Rate 20%, Mortgage 25/30 years, Interest 6% p.a.
