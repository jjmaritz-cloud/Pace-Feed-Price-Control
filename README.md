
# Pace Feed Price Control

Standalone Streamlit prototype for reviewing on-farm feed price, feedmill delivered price, farm recon confidence, and farms needing supportive follow-up before the Monday 12pm cutoff.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Upload files

Upload:
1. `Amino feedmill report.xlsx`
2. `Amino Farm report.xlsx`
3. Optional `farm_master_template.csv`

## Key design rule

The dashboard is designed to help people, not scold them.

It separates:
- farms ready to finalise
- farms where review is suggested
- farms needing support
- farms where the price is not ready to finalise

It avoids labels like "problem farms", "bad farms", or "non-compliant farms".

## Optional farm master file

Use `farm_master_template.csv` to map farms to area managers, regions, and farm type.
