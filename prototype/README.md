# Speed Compass prototype

Working prototype for Amazon Transcend 2026, Case Study 1 (Appendix D of the supporting document).
Every number comes from `../model/speed_ladder.py`, the same model behind the submitted documents.

## Run it

Double-click `Start Speed Compass.bat`. It starts the app, waits until it is ready, then opens
http://127.0.0.1:8501 in your browser. Keep its window open; closing it stops the app. Or, from this folder:

```
python -m streamlit run app.py
```

The app only listens on this computer (127.0.0.1), not on the network. No internet is needed; without a Claude API
key every feature uses offline rules.

## Let judges try it on their own phones

1. Connect the laptop and the judges to the same network. Your phone's hotspot is the most reliable choice, since
   venue Wi-Fi often blocks devices from seeing each other.
2. Close any open Speed Compass window, then double-click `Share with judges.bat`.
3. The sidebar shows a QR code and an address such as `http://192.168.x.x:8501`. Judges scan it or type it.
4. The first time, Windows may ask whether Python can use networks: tick **Private networks** and click **Allow**.

Each judge gets their own copy of the app, so their changes never affect yours or each other's. About 8 judges at
once is fine on a normal laptop.

## AI (optional): Gemini or Claude

Pick the provider in the sidebar and paste a key, or set `GEMINI_API_KEY` (or `ANTHROPIC_API_KEY`) before starting.
The model then tags searches, writes the memo and answers questions in English or Arabic.

- **Gemini (free tier):** get a key at aistudio.google.com. The app tries `gemini-3.8-flash` first, then
  `gemini-3.6-flash`, `gemini-3-flash-preview` and `gemini-3.5-flash-lite` when a model is overloaded or at its free
  limit. Use a project without billing so it can never cost money.
- Every AI request stops after 25 seconds at most; the app then answers with the offline rules. The sidebar's
  **Check the AI connection** sends a one-word test and shows which models answered.
- **Claude:** `claude-opus-5-5`, with server-side refusal fallback enabled. Paid per use.
- Identical requests are answered once and shared, so 8 judges clicking the same example use one API call.
- If the model is unavailable or busy, the app says so and uses the offline rules.

## Tabs

| Tab | What it shows |
|---|---|
| Plan | Zone board, UAE totals, the ladder chart, alternatives, and how the plan changes with the lost-sale rate |
| 12 PM test | The cut-off test on simulated data with a planted answer; results can feed the plan |
| Urgency tagger | Tags English or Arabic searches as urgent or planned; an hour of searches sets the urgent share |
| Rival watch | Change the fastest rival per zone and see whether matching pays |
| Memo and questions | Monthly memo and what-if questions |

All inputs are illustrative, not Amazon data.

## 90-second demo script

1. **Plan tab.** "One rule sets every zone. Dubai, Abu Dhabi and Sharjah-Ajman get same-day for urgent orders;
   Al Ain and the outer emirates get next-day for urgent items. USD 7.0M a year, 7.1 per AED 1."
2. **Move the first slider down to 10%.** "If urgent shoppers are half as likely to leave, same-day stops paying and
   the zones turn red. That is why we measure before we spend."
3. **12 PM test tab, Run.** "At 12:00 the promise flips from Today to Tomorrow. The drop in blue, against the grey
   items that don't flip, is the value of Today. Here it recovers the planted 20%." Click **Use these results**.
4. **Rival watch, noon Minutes opens in RAK and Fujairah.** "Even with a rival there, same-day returns 1.95, under 5.
   We don't match."
5. **Memo and questions.** Ask "What happens in Al Ain if fuel costs rise 20%?"

Start the app before you walk in: the first load takes about 20 seconds.
