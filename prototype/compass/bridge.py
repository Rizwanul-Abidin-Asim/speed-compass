"""Connects the app to the Speed Ladder model used in the submitted documents (model/speed_ladder.py).

Nothing here re-implements the economics: every number comes from speed_ladder.run().
"""
import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "model"))
if MODEL_DIR not in sys.path:
    sys.path.insert(0, MODEL_DIR)

import speed_ladder as sl  # noqa: E402

AED_PER_USD = sl.AED_PER_USD
ZONE_NAMES = [z["name"] for z in sl.ZONES]
SHORT = {z["name"]: z["short"] for z in sl.ZONES}
STOPS_SD_TODAY = {z["name"]: z["stops_sd"] for z in sl.ZONES}
RIVAL_LEVELS = ("none", "partial", "full")
RIVAL_LABEL = {"none": "None", "partial": "Some areas", "full": "Everywhere"}

# Fuel is roughly this share of a van-day's cost in the model (assumption used for fuel questions).
FUEL_SHARE = 0.15

# Document defaults. Percent-style values are stored as fractions here.
DEFAULTS = dict(
    lost_full=0.20,      # urgent sale lost without same-day where a rival offers same-day or faster
    lost_nd=0.12,        # urgent sale lost when the promise is two days, not next day
    aov=200.0,
    urgent_share=0.20,
    lift=0.0145,
    cost_change=0.0,     # 0.2 = delivery costs 20% higher
    ratio_min=5.0,
    skew=1.0,
    rivals={z["name"]: z["rival"] for z in sl.ZONES},
    measured={},         # zone -> lost-sale rate measured by the 12 PM test
)


def default_settings():
    return copy.deepcopy(DEFAULTS)


def build(settings):
    """Turn app settings into the model's (params, zones)."""
    p = copy.deepcopy(sl.BASE)
    full = settings["lost_full"]
    p["lost_sd"] = {"full": full, "partial": full * 0.75, "none": full * 0.5}
    p["lost_nd"] = settings["lost_nd"]
    p["aov"] = settings["aov"]
    p["urgent_share"] = settings["urgent_share"]
    p["lift_per_day"] = settings["lift"]
    p["cost_mult"] = 1.0 + settings["cost_change"]
    p["ratio_min"] = settings["ratio_min"]
    p["urgent_skew_sd"] = settings["skew"]
    zones = copy.deepcopy(sl.ZONES)
    for z in zones:
        z["rival"] = settings["rivals"].get(z["name"], z["rival"])
        measured = settings["measured"].get(z["name"])
        if measured is not None:
            key = "measured:" + z["name"]
            p["lost_sd"][key] = measured
            z["rival"] = key
    return p, zones


def plan(settings):
    p, zones = build(settings)
    return sl.run(p, zones)


def lost_rate(settings, zone):
    """Lost-sale rate the plan uses for a zone, and where it comes from."""
    p, zones = build(settings)
    z = next(z for z in zones if z["name"] == zone)
    source = "12 PM test" if z["rival"].startswith("measured:") else "assumed"
    return p["lost_sd"][z["rival"]], source


def curves(settings, speed="sd"):
    """Every candidate ladder step per zone (funded or not), for the chart."""
    p, zones = build(settings)
    orders = sl.zone_orders(p, zones)
    return {z["name"]: sl.ladder_steps(p, z, orders[z["name"]], speed) for z in zones}


def alternatives(settings, result=None):
    p, zones = build(settings)
    r = result or sl.run(p, zones)
    sd_spend = r["delivery_cost"] - sum(z["nd_cost"] for z in r["zones"])
    out = {"ladder": dict(cost=r["delivery_cost"], value=r["total_value"], ratio=r["ratio_delivery"] or 0.0)}
    if sd_spend > 0:
        out["even"] = sl.even_spread(p, zones, sd_spend)
    out["match"] = sl.match_everywhere(p, zones)
    return out


def spend_2027(result):
    """Money spent in 2027 as the plan climbs through the gates (the case budget means 2027 spend)."""
    gates = sl.ramp_2027(result)
    spend = sum(g["cost"] for g in gates)
    delivery = sum(g["delivery"] for g in gates)
    value = sum(g["value"] for g in gates)
    return dict(spend=spend, delivery=delivery, value=value, ratio=(value / delivery if delivery else 0.0),
                gates=gates)


def breakpoints(settings, rates):
    """Same-day target per zone as the urgent lost-sale rate changes (measured overrides switched off)."""
    rows = {name: [] for name in ZONE_NAMES}
    for rate in rates:
        s = copy.deepcopy(settings)
        s["lost_full"] = rate
        s["measured"] = {}
        r = plan(s)
        for z in r["zones"]:
            rows[z["zone"]].append((z["sd0"], z["sd1"]))
    return rows


def with_changes(settings, changes):
    """Copy settings and apply what-if changes (used by the question box)."""
    s = copy.deepcopy(settings)
    cost = 0.0
    if changes.get("fuel_change_pct") is not None:
        cost += FUEL_SHARE * changes["fuel_change_pct"] / 100
    if changes.get("delivery_cost_change_pct") is not None:
        cost += changes["delivery_cost_change_pct"] / 100
    if cost:
        s["cost_change"] = (1 + s["cost_change"]) * (1 + cost) - 1
    if changes.get("lost_sale_rate_pct") is not None:
        s["lost_full"] = changes["lost_sale_rate_pct"] / 100
        s["measured"] = {}
    if changes.get("lost_sale_scale") is not None:
        k = changes["lost_sale_scale"]
        s["lost_full"] *= k
        s["lost_nd"] *= k
        s["measured"] = {z: v * k for z, v in s["measured"].items()}
    if changes.get("average_order_aed") is not None:
        s["aov"] = changes["average_order_aed"]
    if changes.get("urgent_share_pct") is not None:
        s["urgent_share"] = changes["urgent_share_pct"] / 100
    if changes.get("speed_lift_pct") is not None:
        s["lift"] = changes["speed_lift_pct"] / 100
    for rc in changes.get("rival_changes") or []:
        if rc.get("zone") in s["rivals"] and rc.get("level") in RIVAL_LEVELS:
            s["rivals"][rc["zone"]] = rc["level"]
            s["measured"].pop(rc["zone"], None)
    return s


def zone_row(result, name):
    return next(z for z in result["zones"] if z["zone"] == name)


def decision(z):
    """Plain-language decision for one zone."""
    up_sd = (z["sd1"] - z["sd0"]) * 100
    up_nd = (z["nd1"] - z["nd0"]) * 100
    if up_sd > 0.05:
        return f"Raise same-day by {up_sd:.1f} points"
    if up_nd > 0.05:
        return "Hold same-day; urgent items to next-day"
    return "No change"
