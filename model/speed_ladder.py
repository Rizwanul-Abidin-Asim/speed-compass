"""
Speed Ladder model: Amazon UAE same-day and next-day targets for 2027.

One rule decides every zone: a step of speed is funded only if the extra
sales it brings are at least 5x its delivery cost (case brief spending limit).
Urgent orders are offered first because each one is worth more.

Money is in AED unless noted. USD at the fixed peg of 3.6725.
Every input is tagged in INPUT_NOTES as a sourced figure or an assumption.
"""
import copy
import json
import os

AED_PER_USD = 3.6725
STEP = 0.005  # one ladder step = 0.5 percentage points of a zone's orders

BASE = {
    # Scale: Case 4 brief gives ~95M Middle East packages a year; the UAE is
    # 37.2% of UAE + KSA + Egypt e-commerce revenue (ECDB 2025). 1 package ~ 1 order.
    "orders_total": 95e6 * 0.372,
    "aov": 200.0,                 # assumption, below the AED 254.69 UAE online average (2024)
    "urgent_share": 0.20,         # Pattern UAE Shopper Report 2022: 20% want same-day
    "lift_per_day": 0.0145,       # Fisher, Gallino & Xu 2019: +1.45% sales per day faster
    "lost_sd": {"full": 0.20, "partial": 0.15, "none": 0.10},  # urgent sale lost without same-day
    "lost_nd": 0.12,              # urgent sale lost when promise is 2 days, not next day
    "van_day_cost": 450.0,        # assumption: driver, van, fuel, partner margin
    "cost_rise_per_10pts": 0.25,  # assumption: each +10 pts costs 25% more per order
    "ratio_min": 5.0,             # case brief: AED 1 cost per AED 5 extra sales
    "cost_mult": 1.0,             # sensitivity knob
    "urgent_skew_sd": 1.0,        # urgent orders' share of today's same-day orders vs their share of all orders
    "program_fixed": {            # shared, not tied to one zone (assumptions)
        "Speed Compass build and run": 1.1e6,
        "Cut-off test and zone tests": 0.4e6,
    },
    "budget_cap_usd": 10e6,       # case brief envelope USD 6-10M
}

# Population weights: latest official counts (dates differ, used only as weights).
ZONES = [
    dict(name="Dubai", short="Dubai", pop=4.58e6, sd0=0.30, nd0=0.88, rival="full",
         stops_2d=150, stops_nd=120, stops_sd=70, place_sd=1.5, standby_sd=0.9, place_nd=0.5, fixed_sd=0.0),
    dict(name="Abu Dhabi region", short="Abu Dhabi", pop=2.823e6, sd0=0.25, nd0=0.85, rival="full",
         stops_2d=135, stops_nd=110, stops_sd=60, place_sd=1.5, standby_sd=0.9, place_nd=0.5, fixed_sd=0.0),
    dict(name="Sharjah city and Ajman", short="Sharjah-Ajman", pop=1.899e6 + 0.583e6, sd0=0.20,
         nd0=0.85, rival="full",
         stops_2d=140, stops_nd=115, stops_sd=65, place_sd=1.5, standby_sd=0.9, place_nd=0.5, fixed_sd=0.0),
    dict(name="Al Ain", short="Al Ain", pop=0.987e6, sd0=0.08, nd0=0.75, rival="partial",
         stops_2d=100, stops_nd=80, stops_sd=35, place_sd=2.0, standby_sd=1.5, place_nd=0.75, fixed_sd=2.5e6),
    # RAK, Fujairah, UAQ, Al Dhafra, Sharjah east coast and central towns
    dict(name="Outer emirates", short="Outer", pop=0.400e6 + 0.3285e6 + 0.0492e6 + 0.3257e6 + 0.2367e6,
         sd0=0.04, nd0=0.60, rival="none",
         stops_2d=90, stops_nd=55, stops_sd=18, place_sd=2.5, standby_sd=2.5, place_nd=1.0, fixed_sd=4.0e6),
]


def zone_orders(p, zones):
    total_pop = sum(z["pop"] for z in zones)
    return {z["name"]: p["orders_total"] * z["pop"] / total_pop for z in zones}


def base_cost(p, z, speed):
    v = p["van_day_cost"]
    if speed == "sd":
        c = v / z["stops_sd"] - v / z["stops_nd"] + z["place_sd"] + z["standby_sd"]
    else:
        c = v / z["stops_nd"] - v / z["stops_2d"] + z["place_nd"]
    return c * p["cost_mult"]


def value_per_order(p, z, speed, urgent):
    lost = 0.0
    if urgent:
        lost = p["lost_sd"][z["rival"]] if speed == "sd" else p["lost_nd"]
    return p["aov"] * (lost + p["lift_per_day"])


def graduation_stops(p, z):
    """Same-day stops per van-day at which the first urgent same-day step clears the 5:1 line."""
    v = p["van_day_cost"] * p["cost_mult"]
    allowed = value_per_order(p, z, "sd", True) / p["ratio_min"]
    other = (z["place_sd"] + z["standby_sd"]) * p["cost_mult"]
    room = allowed - other + v / z["stops_nd"]
    return v / room if room > 0 else float("inf")


def ladder_steps(p, z, n_orders, speed):
    """All candidate steps for one zone and one speed, urgent first."""
    u = p["urgent_share"]
    if speed == "sd":
        start, gap = z["sd0"], z["nd0"] - z["sd0"]  # next-day orders that could go same-day
        k = p.get("urgent_skew_sd", 1.0)
        urgent_pool = max(0.0, u * z["nd0"] - min(u, k * u * z["sd0"]))  # urgent orders now on next-day
        urgent_pool = min(urgent_pool, gap)
    else:
        start, gap = z["nd0"], 1.0 - z["nd0"]        # two-day orders that could go next-day
        urgent_pool = u * gap
    pools = [("urgent", urgent_pool), ("planned", gap - urgent_pool)]
    c0 = base_cost(p, z, speed)
    steps, level = [], start
    for kind, size in pools:
        left = size
        while left > 1e-9:
            d = min(STEP, left)
            mid = level + d / 2
            cost_per = c0 * (1 + p["cost_rise_per_10pts"] * (mid - start) / 0.10)
            val_per = value_per_order(p, z, speed, kind == "urgent")
            orders = n_orders * d
            steps.append(dict(zone=z["name"], speed=speed, kind=kind, frm=level, to=level + d,
                              orders=orders, cost=orders * cost_per, value=orders * val_per,
                              cost_per=cost_per, val_per=val_per, ratio=val_per / cost_per))
            level += d
            left -= d
    return steps


def run(p=None, zones=None):
    p = copy.deepcopy(p or BASE)
    zones = copy.deepcopy(zones or ZONES)
    orders = zone_orders(p, zones)
    funded, first_step = [], {}
    for z in zones:
        for speed in ("sd", "nd"):
            steps = ladder_steps(p, z, orders[z["name"]], speed)
            first_step[(z["name"], speed)] = steps[0]
            chosen = []
            for s in steps:  # ratios fall as we climb, so stop at the first failure
                if s["ratio"] >= p["ratio_min"]:
                    chosen.append(s)
                else:
                    break
            fixed = z["fixed_sd"] if speed == "sd" else 0.0
            if chosen:
                v = sum(s["value"] for s in chosen)
                c = sum(s["cost"] for s in chosen) + fixed
                if v / c < p["ratio_min"]:
                    chosen = []
            for s in chosen:
                s["zone_fixed"] = fixed
            funded += chosen
            if chosen and fixed:
                funded.append(dict(zone=z["name"], speed=speed, kind="fixed", frm=0, to=0, orders=0,
                                   cost=fixed, value=0, cost_per=0, val_per=0, ratio=0))

    program_fixed = sum(p["program_fixed"].values())
    cap = p["budget_cap_usd"] * AED_PER_USD
    # trim lowest-ratio variable steps if the plan is over the envelope
    var = sorted([s for s in funded if s["kind"] != "fixed"], key=lambda s: s["ratio"])
    while var and sum(s["cost"] for s in funded) + program_fixed > cap:
        worst = var.pop(0)
        funded.remove(worst)

    return summarise(p, zones, orders, funded, program_fixed, first_step)


def summarise(p, zones, orders, funded, program_fixed, first_step):
    zrows = []
    tot_orders = sum(orders.values())
    for z in zones:
        n = orders[z["name"]]
        sd_steps = [s for s in funded if s["zone"] == z["name"] and s["speed"] == "sd" and s["kind"] != "fixed"]
        nd_steps = [s for s in funded if s["zone"] == z["name"] and s["speed"] == "nd" and s["kind"] != "fixed"]
        zfixed = sum(s["cost"] for s in funded if s["zone"] == z["name"] and s["kind"] == "fixed")
        sd1 = z["sd0"] + sum(s["to"] - s["frm"] for s in sd_steps)
        nd1 = z["nd0"] + sum(s["to"] - s["frm"] for s in nd_steps)
        cost = sum(s["cost"] for s in sd_steps + nd_steps) + zfixed
        value = sum(s["value"] for s in sd_steps + nd_steps)
        u = p["urgent_share"]
        # urgent orders delivered same-day: assume today's same-day orders are a random mix
        k = p.get("urgent_skew_sd", 1.0)
        urgent_sd_share = (min(u, k * u * z["sd0"]) + sum(s["to"] - s["frm"] for s in sd_steps if s["kind"] == "urgent")) / u
        fs, fn = first_step[(z["name"], "sd")], first_step[(z["name"], "nd")]
        lost_sd = p["lost_sd"][z["rival"]]
        zrows.append(dict(
            zone=z["name"], short=z["short"], order_share=n / tot_orders, orders=n,
            sd0=z["sd0"], sd1=sd1, nd0=z["nd0"], nd1=nd1,
            sd_cost=sum(s["cost"] for s in sd_steps) + zfixed, nd_cost=sum(s["cost"] for s in nd_steps),
            sd_value=sum(s["value"] for s in sd_steps), nd_value=sum(s["value"] for s in nd_steps),
            cost=cost, value=value, ratio=(value / cost if cost else None),
            sd_first_ratio=fs["ratio"], nd_first_ratio=fn["ratio"],
            sd_c0=fs["cost_per"], nd_c0=fn["cost_per"],
            sd_last_cost=(sd_steps[-1]["cost_per"] if sd_steps else None),
            lost_sd=lost_sd,
            breakeven_lost_first=p["ratio_min"] * fs["cost_per"] / p["aov"] - p["lift_per_day"],
            breakeven_lost_last=(p["ratio_min"] * sd_steps[-1]["cost_per"] / p["aov"] - p["lift_per_day"]
                                 if sd_steps else None),
            urgent_sd_share=urgent_sd_share,
            grad_stops=graduation_stops(p, z),
            fixed_sd=z["fixed_sd"],
        ))
    var_cost = sum(r["cost"] for r in zrows)
    total_cost = var_cost + program_fixed
    total_value = sum(r["value"] for r in zrows)
    nat = lambda key: sum(r[key] * r["order_share"] for r in zrows)
    return dict(
        params=p, zones=zrows, program_fixed=program_fixed,
        delivery_cost=var_cost, total_cost=total_cost, total_value=total_value,
        ratio_all_in=total_value / total_cost if total_cost else None,
        ratio_delivery=total_value / var_cost if var_cost else None,
        sd0=nat("sd0"), sd1=nat("sd1"), nd0=nat("nd0"), nd1=nat("nd1"),
        total_cost_usd=total_cost / AED_PER_USD, total_value_usd=total_value / AED_PER_USD,
        orders_total=tot_orders, funded=funded,
    )


def even_spread(p, zones, spend):
    """Same delivery spend, no urgency targeting: each upgrade is urgent with probability u."""
    orders = zone_orders(p, zones)
    u = p["urgent_share"]
    tot = sum(orders.values())
    value = cost = 0.0
    for z in zones:
        share = orders[z["name"]] / tot
        budget = spend * share
        c0 = base_cost(p, z, "sd")
        val = p["aov"] * (u * p["lost_sd"][z["rival"]] + p["lift_per_day"])
        # climb untargeted steps until this zone's share of the budget is used
        level, spent, v = z["sd0"], 0.0, 0.0
        while spent < budget and level < z["nd0"]:
            cpo = c0 * (1 + p["cost_rise_per_10pts"] * (level + STEP / 2 - z["sd0"]) / 0.10)
            n = orders[z["name"]] * STEP
            spent += n * cpo
            v += n * val
            level += STEP
        value += v
        cost += spent
    return dict(cost=cost, value=value, ratio=value / cost)


def match_everywhere(p, zones, target=None):
    """Raise every zone to the same same-day share, untargeted (a 'match the rival everywhere' plan)."""
    orders = zone_orders(p, zones)
    u = p["urgent_share"]
    res = run(p, zones)
    target = target if target is not None else res["sd1"]
    value = cost = 0.0
    for z in zones:
        if z["sd0"] >= target:
            continue
        c0 = base_cost(p, z, "sd")
        val = p["aov"] * (u * p["lost_sd"][z["rival"]] + p["lift_per_day"])
        level = z["sd0"]
        while level < target - 1e-9:
            cpo = c0 * (1 + p["cost_rise_per_10pts"] * (level + STEP / 2 - z["sd0"]) / 0.10)
            n = orders[z["name"]] * STEP
            cost += n * cpo
            value += n * val
            level += STEP
        cost += z["fixed_sd"]
    return dict(target=target, cost=cost, value=value, ratio=value / cost)


def scenarios():
    out = []

    def sc(label, mutate):
        p = copy.deepcopy(BASE)
        mutate(p)
        r = run(p)
        out.append(dict(label=label, cost_usd=r["total_cost_usd"], value_usd=r["total_value_usd"],
                        delivery_usd=r["delivery_cost"] / AED_PER_USD,
                        ratio=r["ratio_delivery"] or 0.0, sd1=r["sd1"], nd1=r["nd1"],
                        sd_zones=[z["short"] for z in r["zones"] if z["sd1"] > z["sd0"] + 1e-9]))

    sc("Base case", lambda p: None)
    sc("Lost-sale rates halved", lambda p: p.update(lost_sd={k: v / 2 for k, v in p["lost_sd"].items()},
                                                    lost_nd=p["lost_nd"] / 2))
    sc("Speed lift halved (0.73%/day)", lambda p: p.update(lift_per_day=p["lift_per_day"] / 2))
    sc("Delivery costs +30%", lambda p: p.update(cost_mult=1.3))
    sc("Urgent share 15% (not 20%)", lambda p: p.update(urgent_share=0.15))
    sc("Urgent share 25% (not 20%)", lambda p: p.update(urgent_share=0.25))
    sc("Average order AED 150 (not 200)", lambda p: p.update(aov=150.0))
    sc("Lost-sale rates x1.5", lambda p: p.update(lost_sd={k: v * 1.5 for k, v in p["lost_sd"].items()},
                                                  lost_nd=p["lost_nd"] * 1.5))

    sc("Urgent shoppers already 1.5x over-represented in same-day",
       lambda p: p.update(urgent_skew_sd=1.5))

    def bad(p):
        p.update(lost_sd={k: v * 0.75 for k, v in p["lost_sd"].items()}, lost_nd=p["lost_nd"] * 0.75,
                 cost_mult=1.2, urgent_share=0.15)
    sc("Combined downside (lost -25%, cost +20%, urgent 15%)", bad)
    return out


def ramp_2027(r):
    """2027 spend and extra sales by gate. Money follows the gates; delivery cost is what the 5:1 test uses."""
    zr = {z["zone"]: z for z in r["zones"]}
    dense = ("Dubai", "Abu Dhabi region", "Sharjah city and Ajman")
    dense_sd_cost = sum(zr[n]["sd_cost"] for n in dense)
    dense_sd_val = sum(zr[n]["sd_value"] for n in dense)
    pilot_cost_base = zr["Dubai"]["sd_cost"] + zr["Sharjah city and Ajman"]["sd_cost"]
    pilot_val_base = zr["Dubai"]["sd_value"] + zr["Sharjah city and Ajman"]["sd_value"]
    nd_cost = sum(z["nd_cost"] for z in r["zones"])
    nd_val = sum(z["nd_value"] for z in r["zones"])
    pf = r["params"]["program_fixed"]
    compass_m = pf["Speed Compass build and run"] / 12
    tests = pf["Cut-off test and zone tests"]
    pilot_share = 0.20   # 12 of 24 matched zones hold about 20% of Dubai + Sharjah-Ajman orders
    climb = 0.60         # April to June: dense zones climb to target, averaging 60% of the year-end level
    gates = [
        dict(gate="Gate 0", months="Jan", m=1, other=compass_m * 1 + tests * 0.25, delivery=0.0, value=0.0),
        dict(gate="Gate 1", months="Feb to Mar", m=2, other=compass_m * 2 + tests * 0.75,
             delivery=pilot_cost_base * pilot_share * 2 / 12, value=pilot_val_base * pilot_share * 2 / 12),
        dict(gate="Gate 2", months="Apr to Jun", m=3, other=compass_m * 3,
             delivery=dense_sd_cost * climb * 3 / 12 + nd_cost * 3 / 12,
             value=dense_sd_val * climb * 3 / 12 + nd_val * 3 / 12),
        dict(gate="Gate 3", months="Jul to Dec", m=6, other=compass_m * 6,
             delivery=dense_sd_cost * 6 / 12 + nd_cost * 6 / 12,
             value=dense_sd_val * 6 / 12 + nd_val * 6 / 12),
    ]
    for g in gates:
        g["cost"] = g["delivery"] + g["other"]
        g["cost_usd"] = g["cost"] / AED_PER_USD
        g["delivery_usd"] = g["delivery"] / AED_PER_USD
        g["value_usd"] = g["value"] / AED_PER_USD
    return gates


def main(outdir):
    r = run()
    p = r["params"]
    es = even_spread(p, ZONES, r["delivery_cost"] - sum(z["nd_cost"] for z in r["zones"]))
    me = match_everywhere(p, ZONES)
    sc = scenarios()
    gates = ramp_2027(r)
    out = dict(
        base={k: v for k, v in r.items() if k not in ("funded",)},
        even_spread=es, match_everywhere=me, scenarios=sc, gates=gates,
        aed_per_usd=AED_PER_USD,
    )
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "results.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    # ladder curves for the chart (all candidate steps, funded or not)
    orders = zone_orders(p, ZONES)
    curves = {}
    for z in ZONES:
        for speed in ("sd", "nd"):
            curves[f"{z['name']}|{speed}"] = [
                dict(frm=s["frm"], to=s["to"], ratio=s["ratio"], kind=s["kind"])
                for s in ladder_steps(p, z, orders[z["name"]], speed)]
    with open(os.path.join(outdir, "curves.json"), "w", encoding="utf-8") as f:
        json.dump(curves, f)
    return out


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    out = main(os.path.join(here, "out"))
    b = out["base"]
    print(f"Orders/yr {b['orders_total']/1e6:.1f}M")
    print(f"{'zone':24s} share  sd0   sd1   nd0   nd1   costM  valueM  ratio  sd1st  nd1st  c0sd  c0nd  BEfirst BElast urgSD")
    for z in b["zones"]:
        print(f"{z['zone']:24s} {z['order_share']*100:4.1f} {z['sd0']*100:5.1f} {z['sd1']*100:5.1f} "
              f"{z['nd0']*100:5.1f} {z['nd1']*100:5.1f} {z['cost']/1e6:6.2f} {z['value']/1e6:7.2f} "
              f"{(z['ratio'] or 0):5.2f} {z['sd_first_ratio']:5.2f} {z['nd_first_ratio']:5.2f} "
              f"{z['sd_c0']:5.2f} {z['nd_c0']:5.2f} {z['breakeven_lost_first']*100:6.1f} "
              f"{(z['breakeven_lost_last'] or 0)*100:6.1f} {z['urgent_sd_share']*100:5.1f}")
    for z in b["zones"]:
        print(f"  graduation stops {z['zone']}: {z['grad_stops']:.1f} (now {[x for x in ZONES if x['name']==z['zone']][0]['stops_sd']})")
    print(f"National same-day {b['sd0']*100:.1f}% -> {b['sd1']*100:.1f}%; 1-day-or-faster {b['nd0']*100:.1f}% -> {b['nd1']*100:.1f}%")
    print(f"Delivery cost AED {b['delivery_cost']/1e6:.1f}M + program AED {b['program_fixed']/1e6:.1f}M = "
          f"AED {b['total_cost']/1e6:.1f}M (USD {b['total_cost_usd']/1e6:.2f}M)")
    print(f"Extra sales AED {b['total_value']/1e6:.1f}M (USD {b['total_value_usd']/1e6:.1f}M); "
          f"ratio all-in {b['ratio_all_in']:.2f}, delivery-only {b['ratio_delivery']:.2f}")
    es, me = out["even_spread"], out["match_everywhere"]
    print(f"Even spread: cost {es['cost']/1e6:.1f}M value {es['value']/1e6:.1f}M ratio {es['ratio']:.2f}")
    print(f"Match everywhere at {me['target']*100:.1f}%: cost {me['cost']/1e6:.1f}M (USD {me['cost']/AED_PER_USD/1e6:.1f}M) "
          f"value {me['value']/1e6:.1f}M ratio {me['ratio']:.2f}")
    for s in out["scenarios"]:
        print(f"  {s['label']:52s} USD {s['cost_usd']/1e6:5.2f}M (delivery {s['delivery_usd']/1e6:4.2f}M) sales USD {s['value_usd']/1e6:6.1f}M  "
              f"{s['ratio']:.2f}:1  SD {s['sd1']*100:4.1f}%  ND {s['nd1']*100:4.1f}%  SD zones {s['sd_zones']}")
    tc = td = tv = 0
    for g in out["gates"]:
        tc += g["cost_usd"]; td += g["delivery_usd"]; tv += g["value_usd"]
        print(f"  {g['gate']} {g['months']:11s} spend USD {g['cost_usd']/1e6:5.2f}M (delivery {g['delivery_usd']/1e6:4.2f}M) "
              f"extra sales USD {g['value_usd']/1e6:5.1f}M")
    print(f"  2027 spend USD {tc/1e6:.2f}M (delivery {td/1e6:.2f}M), 2027 extra sales USD {tv/1e6:.1f}M, "
          f"delivery return {tv/td:.2f}")
