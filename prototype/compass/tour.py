"""Guided tour: highlights each feature in turn with Next and Back, using driver.js (MIT, bundled in vendor/).

The script runs in the app page itself (st.html with JavaScript allowed), so it can point at real elements and switch
tabs. Each step names the tab it lives on; the tour clicks that tab before moving.
"""
import base64
import json
from pathlib import Path

_VENDOR = Path(__file__).parent / "vendor"

# (tab index or None, CSS selector or None, title, text). A {"desktop", "mobile"} dict in place of the selector or
# the text picks by screen width: on a phone some sections are taller than the screen, so the tour points at a part.
STEPS = [
    (None, None, "Welcome to Speed Compass",
     "It decides, zone by zone, where faster delivery in the UAE pays for itself. This tour points at each feature "
     "in turn and takes about a minute. Press Next to start."),
    (0, {"desktop": ".sc-board", "mobile": ".sc-board .sc-zone"}, "Each zone's promise",
     {"desktop": "Each card is one delivery zone. The coloured badge is the promise Speed Compass sets: <b>Today</b> "
                 "(same-day for urgent orders), <b>Tomorrow</b>, or <b>No change</b>. Below it: spend, extra sales, "
                 "and whether the first step clears the 5 to 1 rule.",
      "mobile": "Each card is one delivery zone; scroll down for all five. The coloured badge is the promise Speed "
                "Compass sets: <b>Today</b> (same-day for urgent orders), <b>Tomorrow</b>, or <b>No change</b>. "
                "Below it: spend, extra sales, and whether the first step clears the 5 to 1 rule."}),
    (0, ".sc-kpis", "UAE totals",
     "Same-day and next-day share, what 2027 costs, the extra sales it brings, and the return per AED 1 of "
     "delivery cost. <b>No AI here</b>: these come from the same model as the written submission."),
    (0, ".st-key-card_ladder", "The ladder",
     "Each line is a zone. Funding climbs one step at a time while the next step stays in the green, above the "
     "rule line, and stops where urgent orders run out."),
    (0, "@sidebar", "Change any assumption",
     {"desktop": "Every assumption is a slider here. Move one, for example <b>Urgent shoppers lost without "
                 "same-day</b>, and every number on the page updates.",
      "mobile": "Tap <b>&raquo;</b> here to open the assumptions. Move any slider and every number on the page "
                "updates."}),
    (1, {"desktop": ".st-key-card_test_intro", "mobile": ".st-key-card_test_intro .stButton"}, "12 PM test",
     "At 12:00 the promise flips from Today to Tomorrow. The drop in buying at that moment shows how many sales "
     "same-day wins. Press <b>Run</b> to test it on simulated data with a known answer, then feed the results into "
     "the plan. <b>No AI here.</b>"),
    (2, ".st-key-card_tag_one", "Urgency tagger &#10022; uses AI",
     "Type a search in English or Arabic, or tap an example. <b>The AI</b> decides whether the shopper needs it "
     "today and says why. The urgent share of orders sets how far each zone's ladder can climb."),
    (2, ".st-key-card_tag_batch", "An hour of searches &#10022; uses AI",
     "Tag 30 searches at once to estimate the urgent share, then use it in the plan with one tap."),
    (3, {"desktop": ".st-key-card_rival_controls", "mobile": ".st-key-rival_moves"}, "Rival watch",
     "Set where rivals offer same-day, or try a move such as noon Minutes opening in RAK. Speed Compass matches a "
     "rival only if the step still pays. <b>No AI here.</b>"),
    (4, ".st-key-card_memo", "Monthly memo &#10022; uses AI",
     "The model computes every number. <b>The AI</b> only writes them up as a short memo for leaders."),
    (4, {"desktop": ".st-key-card_ask", "mobile": ".st-key-card_ask [data-testid='stTextInput']"},
     "Ask a what-if &#10022; uses AI",
     "Ask in English or Arabic, such as \"What if fuel costs rise 20% in Al Ain?\". <b>The AI</b> turns it into model "
     "inputs, the plan reruns, and the AI explains what moved."),
    (0, ".st-key-tour_btn", "That's the tour",
     "Replay it any time with this button. <b>Where the AI is used</b>, next to it, explains the AI in one place. "
     "All data is illustrative, not Amazon data."),
]

_CSS = """
.driver-popover.sc-tour { background:#fff; color:#0f172a; border-radius:16px; padding:18px 18px 14px;
  max-width:340px; box-shadow:0 18px 40px rgba(27,59,111,.35); font-family:'IBM Plex Sans','Segoe UI',sans-serif; }
.driver-popover.sc-tour .driver-popover-title { font-family:'Barlow Condensed','Arial Narrow',sans-serif;
  font-size:23px; font-weight:700; line-height:1.15; color:#0f172a; padding-right:22px; }
.driver-popover.sc-tour .driver-popover-description { font-size:14px; line-height:1.55; color:#334155; margin-top:6px; }
.driver-popover.sc-tour .driver-popover-progress-text { font-size:12px; color:#94a3b8; }
.driver-popover.sc-tour .driver-popover-footer { margin-top:14px; }
.driver-popover.sc-tour .driver-popover-footer button { border-radius:999px; padding:7px 14px; font-size:13.5px;
  font-weight:600; text-shadow:none; border:1px solid #d7ddef; background:#fff; color:#475569; }
.driver-popover.sc-tour .driver-popover-next-btn { background:linear-gradient(115deg,#1b3b6f 0%,#6b4c9a 58%,#e07a3f 100%)
  !important; color:#fff !important; border:none !important; }
.driver-popover.sc-tour .driver-popover-close-btn { color:#94a3b8; font-size:22px; top:6px; right:8px; }
svg.driver-overlay { z-index:999995 !important; }
.driver-popover { z-index:1000000000 !important; }
"""

_JS = r"""
(function () {
  const W = window, D = document;
  if (!D.querySelector('meta[name="color-scheme"]')) {
    const m = D.createElement("meta"); m.name = "color-scheme"; m.content = "only light"; D.head.appendChild(m);
  }
  const RUN = __RUN__, STEPS = __STEPS__;
  if (!W.driver) {
    const css = D.createElement("style"); css.textContent = __CSS__; D.head.appendChild(css);
    const lib = D.createElement("script"); lib.textContent = __LIB__; D.head.appendChild(lib);
  }
  if (!W.__scTourDefined) {
    W.__scTourDefined = true;
    const tour = D.createElement("script");
    tour.textContent = "(" + function () {
      window.__scTour = function (steps) {
        const mobile = window.innerWidth <= 640;
        const tabs = () => document.querySelectorAll('[data-testid="stTab"]');
        const sidebarOpen = () => {
          const s = document.querySelector('[data-testid="stSidebar"]');
          return s && s.getBoundingClientRect().right > 60;
        };
        const items = steps.map(([tab, sel, title, text]) => {
          let el = sel && typeof sel === "object" ? (mobile ? sel.mobile : sel.desktop) : sel;
          if (el === "@sidebar") {
            el = sidebarOpen() ? '[data-testid="stSidebar"]'
              : '[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapsedControl"] button';
          }
          if (typeof text === "object") {
            const small = el && el.indexOf("stExpandSidebarButton") >= 0 ? true : mobile;
            text = small ? text.mobile : text.desktop;
          }
          const step = { popover: { title: title, description: text } };
          if (!sel) step.popover.showButtons = ["next", "close"];
          if (el) step.element = el;
          return { tab: tab, step: step };
        });
        let closing = false;
        const d = window.driver.js.driver({
          steps: items.map(i => i.step), showProgress: true, progressText: "{{current}} of {{total}}",
          nextBtnText: "Next", prevBtnText: "Back", doneBtnText: "Done", popoverClass: "sc-tour",
          stagePadding: 6, stageRadius: 14, overlayOpacity: 0.62, smoothScroll: false,
          onNextClick: () => go(d.getActiveIndex() + 1),
          onPrevClick: () => go(d.getActiveIndex() - 1),
          onCloseClick: () => { closing = true; d.destroy(); },
          // Only the close button or Done end the tour, so a stray tap on the dark area does not lose your place.
          onDestroyStarted: () => { if (closing) d.destroy(); },
          onDestroyed: () => { const t = tabs()[0]; if (t) t.click(); },
        });
        function go(i) {
          if (i < 0) return;
          if (i >= items.length) { closing = true; d.destroy(); return; }
          const t = items[i].tab, tab = t === null ? null : tabs()[t];
          if (tab && tab.getAttribute("aria-selected") !== "true") {
            tab.click();
            setTimeout(() => d.moveTo(i), 450);
          } else {
            d.moveTo(i);
          }
        }
        const main = document.querySelector('[data-testid="stMain"]');
        if (main && !main.__scTourScroll) {
          main.__scTourScroll = true;
          main.addEventListener("scroll", () => { if (window.__scTourActive && window.__scTourActive.isActive()) window.__scTourActive.refresh(); });
        }
        window.__scTourActive = d;
        d.drive(0);
      };
    } + ")();";
    D.head.appendChild(tour);
  }
  if (RUN > 0 && W.__scTourLastRun !== RUN) {
    W.__scTourLastRun = RUN;
    let tries = 0;
    const wait = setInterval(() => {
      tries += 1;
      const ready = D.querySelector(".sc-board") && D.querySelectorAll('[data-testid="stTab"]').length >= 5;
      if ((ready && W.__scTour && W.driver) || tries > 60) {
        clearInterval(wait);
        if (ready) setTimeout(() => W.__scTour(STEPS), 400);
      }
    }, 250);
  }
})();
"""


def tour_html(run):
    """HTML for st.html. A new `run` number starts the tour once; the same number does nothing."""
    js = (_JS.replace("__RUN__", str(int(run)))
          .replace("__STEPS__", json.dumps(STEPS))
          .replace("__CSS__", json.dumps((_VENDOR / "driver.css").read_text(encoding="utf-8") + _CSS))
          .replace("__LIB__", json.dumps((_VENDOR / "driver.js").read_text(encoding="utf-8"))))
    # Streamlit sanitises st.html and drops any script whose text contains "<" followed by a letter, which both
    # driver.js and the step text do. So the code travels base64-encoded and is decoded in the browser.
    payload = base64.b64encode(js.encode("utf-8")).decode("ascii")
    return ("<script>(function(){var s=document.createElement('script');"
            "s.textContent=new TextDecoder().decode(Uint8Array.from(atob('" + payload + "'),"
            "function(c){return c.charCodeAt(0);}));document.head.appendChild(s);})();</script>")
