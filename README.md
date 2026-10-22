# Speed Compass

Working prototype for Amazon Transcend 2026, Case Study 1 (Setting the Speed Bar), by Rizwanul Abidin Asim,
American University of Sharjah. It sets each UAE zone's delivery promise with one rule: a step of speed is funded only
if it brings at least five times its delivery cost in extra sales.

- App: `prototype/app.py` (Streamlit). Model: `model/speed_ladder.py`, the same model behind the written submission.
- Inputs are illustrative figures, not Amazon data.
- AI is optional: set `GEMINI_API_KEY` (or `ANTHROPIC_API_KEY`) as a secret; without it, offline rules are used.

Run locally: `pip install -r requirements.txt` then `python -m streamlit run prototype/app.py`.
