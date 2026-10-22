"""The 12 PM cut-off test (Appendix C1), run on simulated data.

Every day at 12 PM the promise on a same-day item flips from "Today" to "Tomorrow". Shoppers just before
and just after the flip are alike, so the drop in buying at 12 PM, net of the same 12 PM change for items
whose promise does not flip, measures how many sales "Today" wins. Some of the lost buyers come back within
seven days; those sales were delayed, not lost, and are removed.

The simulation plants a known lost-sale rate so the estimate can be checked against the truth.
"""
import numpy as np

MINUTES = np.arange(-60, 60)        # minutes relative to 12:00
DONUT = 10                          # ignore the 10 minutes before 12 PM (shoppers rushing to beat the cut-off)
BANDWIDTH = 50
TOTAL_VIEWS_PER_MIN = 20000         # same-day item page views per minute across the UAE, 11:00 to 13:00 (illustrative)
CONV_SAMEDAY = 0.06
CONV_CONTROL = 0.05
CAME_BACK = 0.25                    # share of lost buyers who buy the same item within 7 days (simulated truth)
BOOT = 150

# Item groups on same-day items. 'mult' scales the zone's lost-sale rate; urgent multipliers are
# normalised below so that their view-weighted average is exactly 1 (the plan's assumption).
ITEM_GROUPS = [
    dict(name="Phone and laptop accessories", urgent=True, share=0.22, mult=1.10),
    dict(name="Baby, health and pharmacy", urgent=True, share=0.18, mult=1.20),
    dict(name="Party, gifts and occasions", urgent=True, share=0.12, mult=0.80),
    dict(name="School and office supplies", urgent=True, share=0.10, mult=0.75),
    dict(name="Home and kitchen", urgent=False, share=0.20, mult=None),
    dict(name="Books, toys and furniture", urgent=False, share=0.18, mult=None),
]
_u = [g for g in ITEM_GROUPS if g["urgent"]]
_norm = sum(g["share"] * g["mult"] for g in _u) / sum(g["share"] for g in _u)
for g in _u:
    g["mult"] = g["mult"] / _norm
PLANNED_LOST = 0.02

WORLDS = {
    "As assumed in the plan": 1.0,
    "Speed matters half as much": 0.5,
    "Speed matters 1.5 times as much": 1.5,
}
# Urgent lost-sale rate the simulated world plants in each zone (document defaults by rival level).
ZONE_BASE = {"full": 0.20, "partial": 0.15, "none": 0.10}


def _fit_at_zero(x, y, w):
    b = np.polyfit(x, y, 1, w=np.sqrt(np.maximum(w, 1)))
    return np.polyval(b, 0.0), b


def _jump(views, orders, idx_l, idx_r):
    rate = orders / np.maximum(views, 1)
    yl, bl = _fit_at_zero(MINUTES[idx_l], rate[idx_l], views[idx_l])
    yr, br = _fit_at_zero(MINUTES[idx_r], rate[idx_r], views[idx_r])
    return yr / yl - 1.0, bl, br


def simulate_cell(true_lost, views_per_min, rng):
    gross = true_lost / (1.0 - CAME_BACK)
    m = MINUTES
    tod = 1.0 - 0.10 * np.exp(-((m - 20) / 22.0) ** 2)                 # lunch dip that hits every item
    rush = np.where((m >= -DONUT) & (m < 0), 1.0 + 0.8 * gross * (m + DONUT) / DONUT, 1.0)
    p_t = CONV_SAMEDAY * tod * rush * np.where(m >= 0, 1.0 - gross, 1.0)
    p_c = CONV_CONTROL * tod
    v_t = rng.poisson(views_per_min, size=m.size)
    v_c = rng.poisson(views_per_min * 0.8, size=m.size)
    o_t = rng.binomial(v_t, np.clip(p_t, 0, 1))
    o_c = rng.binomial(v_c, np.clip(p_c, 0, 1))
    after = m >= 0
    lost_n = int(round(float(np.sum(v_t[after] * CONV_SAMEDAY * tod[after] * gross))))
    came_back = int(rng.binomial(max(lost_n, 1), CAME_BACK))
    return dict(v_t=v_t, o_t=o_t, v_c=v_c, o_c=o_c, lost_n=max(lost_n, 1), came_back=came_back)


def estimate_cell(d, rng, boot=BOOT):
    m = MINUTES
    idx_l = np.where((m < -DONUT) & (m >= -BANDWIDTH))[0]
    idx_r = np.where((m >= 0) & (m < BANDWIDTH))[0]

    def one(il, ir, back_share):
        jt, _, _ = _jump(d["v_t"], d["o_t"], il, ir)
        jc, _, _ = _jump(d["v_c"], d["o_c"], il, ir)
        # time-of-day effects scale both series alike, so compare the jumps as a ratio
        gross = 1.0 - (1.0 + jt) / (1.0 + jc)
        return gross * (1.0 - back_share), gross

    back = d["came_back"] / d["lost_n"]
    net, gross = one(idx_l, idx_r, back)
    draws = []
    for _ in range(boot):
        il = rng.choice(idx_l, size=idx_l.size, replace=True)
        ir = rng.choice(idx_r, size=idx_r.size, replace=True)
        b = rng.binomial(d["lost_n"], back) / d["lost_n"]
        draws.append(one(il, ir, b)[0])
    draws = np.array(draws)
    return dict(net=net, gross=gross, came_back=back, lo=float(np.percentile(draws, 5)),
                hi=float(np.percentile(draws, 95)), draws=draws)


def run_test(zone_shares, zone_rivals, world, days, seed):
    """Run the test for every zone and item group. Returns cell rows, zone summaries and raw series."""
    rng = np.random.default_rng(seed)
    factor = WORLDS[world]
    cells, series, zones = [], {}, {}
    for zone, share in zone_shares.items():
        urgent_draws, weights, truth_w = [], [], []
        for g in ITEM_GROUPS:
            if g["urgent"]:
                true_lost = ZONE_BASE[zone_rivals[zone]] * g["mult"] * factor
            else:
                true_lost = PLANNED_LOST * factor
            views = TOTAL_VIEWS_PER_MIN * share * g["share"] * days
            d = simulate_cell(true_lost, views, rng)
            e = estimate_cell(d, rng)
            cells.append(dict(zone=zone, group=g["name"], urgent=g["urgent"], true=true_lost,
                              measured=e["net"], lo=e["lo"], hi=e["hi"], came_back=e["came_back"],
                              views=float(np.sum(d["v_t"]))))
            series[(zone, g["name"])] = d
            if g["urgent"]:
                urgent_draws.append(e["draws"])
                weights.append(g["share"])
                truth_w.append(true_lost)
        w = np.array(weights) / np.sum(weights)
        point = float(sum(wi * c["measured"] for wi, c in zip(w, [c for c in cells if c["zone"] == zone
                                                                    and c["urgent"]])))
        comb = np.sum(np.array(urgent_draws) * w[:, None], axis=0)
        zones[zone] = dict(measured=point, lo=float(np.percentile(comb, 5)), hi=float(np.percentile(comb, 95)),
                           true=float(np.sum(w * np.array(truth_w))))
    return cells, zones, series


def series_for_plot(d):
    """Purchase rate per minute and the fitted lines on each side of 12 PM."""
    m = MINUTES
    idx_l = np.where((m < -DONUT) & (m >= -BANDWIDTH))[0]
    idx_r = np.where((m >= 0) & (m < BANDWIDTH))[0]
    out = {}
    for key, v, o in (("sameday", d["v_t"], d["o_t"]), ("control", d["v_c"], d["o_c"])):
        rate = o / np.maximum(v, 1)
        _, bl, br = _jump(v, o, idx_l, idx_r)
        out[key] = dict(rate=rate, left_fit=(m[idx_l].tolist() + [0], np.polyval(bl, list(m[idx_l]) + [0])),
                        right_fit=(m[idx_r], np.polyval(br, m[idx_r])))
    return out
