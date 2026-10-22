"""Monthly memo and what-if questions. Claude writes and interprets when connected; templates otherwise."""
import json
import re
from datetime import date

from . import bridge
from .ai import AIUnavailable

ZONE_ALIASES = {
    "Dubai": ["dubai", "دبي"],
    "Abu Dhabi region": ["abu dhabi", "أبوظبي", "ابوظبي", "أبو ظبي", "ابو ظبي"],
    "Sharjah city and Ajman": ["sharjah", "ajman", "الشارقة", "عجمان"],
    "Al Ain": ["al ain", "العين"],
    "Outer emirates": ["outer", "ras al khaimah", "rak", "fujairah", "umm al quwain", "uaq", "dhafra",
                       "northern emirates", "رأس الخيمة", "راس الخيمة", "الفجيرة", "أم القيوين", "الظفرة"],
}


def usd_m(aed):
    return aed / bridge.AED_PER_USD / 1e6


def facts(result, settings):
    """Compact, rounded numbers handed to Claude (and used by the templates)."""
    zones = []
    for z in result["zones"]:
        lost, src = bridge.lost_rate(settings, z["zone"])
        zones.append(dict(
            zone=z["zone"], same_day_now_pct=round(z["sd0"] * 100, 1), same_day_target_pct=round(z["sd1"] * 100, 1),
            next_day_or_faster_now_pct=round(z["nd0"] * 100, 1), next_day_or_faster_target_pct=round(z["nd1"] * 100, 1),
            cost_aed_m=round(z["cost"] / 1e6, 2), extra_sales_aed_m=round(z["value"] / 1e6, 1),
            first_same_day_step_return=round(z["sd_first_ratio"], 2),
            urgent_lost_sale_rate_pct=round(lost * 100, 1), lost_sale_rate_source=src,
            same_day_stops_needed_to_graduate=round(z["grad_stops"], 0) if z["grad_stops"] != float("inf") else None,
            same_day_stops_today_estimate=bridge.STOPS_SD_TODAY[z["zone"]],
            decision=bridge.decision(z),
        ))
    return dict(
        uae_same_day_now_pct=round(result["sd0"] * 100, 1), uae_same_day_target_pct=round(result["sd1"] * 100, 1),
        uae_next_day_or_faster_now_pct=round(result["nd0"] * 100, 1),
        uae_next_day_or_faster_target_pct=round(result["nd1"] * 100, 1),
        spend_2027_usd_m=round(usd_m(bridge.spend_2027(result)["spend"]), 2),
        annual_cost_from_2028_usd_m=round(usd_m(result["total_cost"]), 2),
        extra_sales_a_year_usd_m=round(usd_m(result["total_value"]), 1),
        extra_sales_per_aed_1_of_delivery_cost=round(result["ratio_delivery"], 2) if result["ratio_delivery"] else None,
        spending_rule=f"{settings['ratio_min']:.1f} to 1", budget_envelope_usd_m="6 to 10", zones=zones,
    )


# ------------------------------------------------------------------ memo
def template_memo(result, settings):
    f = facts(result, settings)
    up = [z for z in f["zones"] if z["same_day_target_pct"] > z["same_day_now_pct"]]
    hold = [z for z in f["zones"] if z not in up]
    lines = [f"**Speed Compass memo, {date.today():%B %Y}** (illustrative data)", ""]
    if up:
        names = ", ".join(z["zone"] for z in up)
        lines.append(f"**Recommendation.** Add same-day for urgent orders in {names}; hold same-day elsewhere and "
                     f"move urgent items to next-day. UAE same-day goes from {f['uae_same_day_now_pct']}% to "
                     f"{f['uae_same_day_target_pct']}%.")
    else:
        lines.append("**Recommendation.** Hold same-day in every zone. No same-day step clears the spending rule; "
                     "fund next-day upgrades for urgent items only.")
    ratio = f["extra_sales_per_aed_1_of_delivery_cost"]
    lines += ["", "**Why**",
              f"- 2027 spend USD {f['spend_2027_usd_m']}M; from 2028 USD {f['annual_cost_from_2028_usd_m']}M a year for "
              f"USD {f['extra_sales_a_year_usd_m']}M of extra sales, {ratio} per AED 1 of delivery cost against a "
              f"{f['spending_rule']} rule." if ratio else "- No spend clears the rule."]
    for z in up:
        lines.append(f"- {z['zone']}: same-day {z['same_day_now_pct']}% to {z['same_day_target_pct']}%; the first "
                     f"step returns {z['first_same_day_step_return']} per AED 1.")
    for z in hold:
        lines.append(f"- {z['zone']}: hold same-day at {z['same_day_now_pct']}%; the first step returns only "
                     f"{z['first_same_day_step_return']}.")
    near = [z for z in hold if z["same_day_stops_needed_to_graduate"]]
    lines += ["", "**Watch**"]
    if near:
        z = min(near, key=lambda z: z["same_day_stops_needed_to_graduate"] / z["same_day_stops_today_estimate"])
        lines.append(f"- {z['zone']} graduates to same-day at about {z['same_day_stops_needed_to_graduate']:.0f} "
                     f"stops per van-day; we estimate {z['same_day_stops_today_estimate']} today.")
    measured = [z for z in f["zones"] if z["lost_sale_rate_source"] == "12 PM test"]
    lines.append(f"- Lost-sale rates: {'measured by the 12 PM test in ' + str(len(measured)) + ' zones' if measured else 'still assumed; run the 12 PM test before scaling'}.")
    lines += ["", "**Decision needed.** Approve next month's steps; any zone below 4 to 1 for two months gives back "
                  "its last step."]
    return "\n".join(lines)


MEMO_SYSTEM = (
    "You are Speed Compass, writing the monthly delivery-speed memo for Amazon UAE's speed planning lead. Use only "
    "the numbers in the JSON you are given and do not invent any. Write in plain, direct Amazon style: short "
    "sentences, active voice, numbers instead of adjectives, no hype. Never use em dashes or en dashes. Use this "
    "structure in Markdown: a bold title line with the month; a bold 'Recommendation.' paragraph of one or two "
    "sentences; '**Why**' with two or three bullets; '**Watch**' with one or two bullets; a bold 'Decision needed.' "
    "line. Keep it under 170 words. End with a short italic line saying the inputs are illustrative, not Amazon data."
)


def memo(claude, result, settings):
    """Returns (markdown, engine, note)."""
    if claude and claude.configured():
        try:
            payload = dict(month=f"{date.today():%B %Y}", plan=facts(result, settings))
            text = claude.ask(MEMO_SYSTEM, json.dumps(payload, ensure_ascii=False), effort="low", max_tokens=6000)
            return text, claude.label, None
        except AIUnavailable as e:
            return template_memo(result, settings), "Offline template", f"{e} Showing the offline template."
    return template_memo(result, settings), "Offline template", None


# ------------------------------------------------------------------ questions
NUM = r"(\d+(?:\.\d+)?)"
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٪", "0123456789%")


def rule_changes(question):
    """Offline reading of a what-if question. Handles the common patterns in English and some Arabic."""
    q = question.lower().translate(ARABIC_DIGITS)
    ch = dict(fuel_change_pct=None, delivery_cost_change_pct=None, lost_sale_rate_pct=None, lost_sale_scale=None,
              average_order_aed=None, urgent_share_pct=None, speed_lift_pct=None, rival_changes=[],
              focus_zone=None, answerable=True)
    down = re.search(r"\b(fall|falls|drop|drops|down|lower|decrease|cut|cheaper)\b|انخفض|تنخفض|انخفاض", q)
    sign = -1 if down else 1
    m = re.search(r"(fuel|petrol|diesel|الوقود|البنزين)[^0-9%]{0,40}" + NUM + r"\s*%", q)
    if m:
        ch["fuel_change_pct"] = sign * float(m.group(2))
    m = re.search(r"(delivery cost|delivery costs|costs|cost|driver|wages|تكاليف|تكلفة)[^0-9%]{0,40}" + NUM + r"\s*%", q)
    if m and ch["fuel_change_pct"] is None:
        ch["delivery_cost_change_pct"] = sign * float(m.group(2))
    m = re.search(r"lost[- ]sale[^0-9%]{0,30}" + NUM + r"\s*%", q)
    if m:
        ch["lost_sale_rate_pct"] = float(m.group(1))
    if re.search(r"half as likely|halve|halved|half the", q):
        ch["lost_sale_scale"] = 0.5
    elif re.search(r"twice as likely|double", q):
        ch["lost_sale_scale"] = 2.0
    m = re.search(r"(order|basket|aov)[^0-9]{0,40}(aed\s*)?" + NUM, q)
    if m:
        ch["average_order_aed"] = float(m.group(3))
    m = re.search(r"urgent share[^0-9%]{0,30}" + NUM + r"\s*%", q)
    if m:
        ch["urgent_share_pct"] = float(m.group(1))
    for zone, aliases in ZONE_ALIASES.items():
        if any(a in q for a in aliases):
            ch["focus_zone"] = zone
            if re.search(r"rival|competitor|noon|careem|talabat|منافس", q) and re.search(
                    r"open|launch|expand|enter|arrive|يفتح|يطلق", q):
                ch["rival_changes"].append(dict(zone=zone, level="full"))
            break
    if all(v in (None, []) for k, v in ch.items() if k not in ("focus_zone", "answerable")):
        ch["answerable"] = bool(ch["focus_zone"])
    return ch


EXTRACT_SYSTEM = (
    "Convert a leader's what-if question about the Speed Compass delivery-speed plan into scenario changes. Fill "
    "only the fields the question changes and leave the others null. Percent fields are whole numbers (20 means 20%) "
    "and keep their sign (a 10% fall is -10). Fuel changes go in fuel_change_pct; delivery, driver or general cost "
    "changes go in delivery_cost_change_pct. 'Half as likely to leave' means lost_sale_scale 0.5. A rival launching "
    "or expanding fast delivery in a zone is a rival change for that zone to 'full'; a rival leaving is 'none'. "
    "Zones: Dubai; Abu Dhabi region; Sharjah city and Ajman; Al Ain; Outer emirates (Ras Al Khaimah, Fujairah, Umm "
    "Al Quwain, Al Dhafra, Sharjah east coast). Set focus_zone when the question names a zone. Set answerable to "
    "false when the question is not about delivery speed, cost, customers or this plan. Questions may be in English "
    "or Arabic."
)


def _nullable(t):
    return {"anyOf": [{"type": t}, {"type": "null"}]}


EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "fuel_change_pct": _nullable("number"),
        "delivery_cost_change_pct": _nullable("number"),
        "lost_sale_rate_pct": _nullable("number"),
        "lost_sale_scale": _nullable("number"),
        "average_order_aed": _nullable("number"),
        "urgent_share_pct": _nullable("number"),
        "speed_lift_pct": _nullable("number"),
        "rival_changes": {"type": "array", "items": {
            "type": "object",
            "properties": {"zone": {"type": "string", "enum": bridge.ZONE_NAMES},
                           "level": {"type": "string", "enum": list(bridge.RIVAL_LEVELS)}},
            "required": ["zone", "level"], "additionalProperties": False}},
        "focus_zone": {"anyOf": [{"type": "string", "enum": bridge.ZONE_NAMES}, {"type": "null"}]},
        "answerable": {"type": "boolean"},
    },
    "required": ["fuel_change_pct", "delivery_cost_change_pct", "lost_sale_rate_pct", "lost_sale_scale",
                 "average_order_aed", "urgent_share_pct", "speed_lift_pct", "rival_changes", "focus_zone",
                 "answerable"],
    "additionalProperties": False,
}

ANSWER_SYSTEM = (
    "You are Speed Compass. Answer the leader's question in the same language as the question (English or Arabic), "
    "in at most 90 words, using only the before and after numbers provided. Lead with the direct answer in one "
    "sentence, then give the reason. If a zone's decision does not change, say so plainly. State any assumption "
    "listed in the input (for example how fuel maps to delivery cost). Never use em dashes or en dashes."
)


def describe_changes(ch):
    parts = []
    if ch.get("fuel_change_pct") is not None:
        parts.append(f"fuel {ch['fuel_change_pct']:+.0f}% (about {bridge.FUEL_SHARE * ch['fuel_change_pct']:+.1f}% "
                     f"on delivery cost, since fuel is about {bridge.FUEL_SHARE:.0%} of a van-day's cost)")
    if ch.get("delivery_cost_change_pct") is not None:
        parts.append(f"delivery cost {ch['delivery_cost_change_pct']:+.0f}%")
    if ch.get("lost_sale_rate_pct") is not None:
        parts.append(f"urgent lost-sale rate {ch['lost_sale_rate_pct']:.0f}%")
    if ch.get("lost_sale_scale") is not None:
        parts.append(f"lost-sale rates x{ch['lost_sale_scale']:g}")
    if ch.get("average_order_aed") is not None:
        parts.append(f"average order AED {ch['average_order_aed']:.0f}")
    if ch.get("urgent_share_pct") is not None:
        parts.append(f"urgent share {ch['urgent_share_pct']:.0f}%")
    if ch.get("speed_lift_pct") is not None:
        parts.append(f"speed lift {ch['speed_lift_pct']:.2f}% per day")
    for rc in ch.get("rival_changes") or []:
        parts.append(f"{rc['zone']}: rival same-day or faster in {bridge.RIVAL_LABEL[rc['level']].lower()}")
    return "; ".join(parts)


def compare(settings, changes):
    before = bridge.plan(settings)
    after = bridge.plan(bridge.with_changes(settings, changes))
    return before, after


def kind(z):
    if z["sd1"] > z["sd0"] + 1e-9:
        return "raise same-day"
    if z["nd1"] > z["nd0"] + 1e-9:
        return "hold same-day, urgent items to next-day"
    return "no change"


def graduation_answer(result):
    rows = [z for z in result["zones"] if kind(z) != "raise same-day" and z["grad_stops"] != float("inf")]
    if not rows:
        return "Every zone already adds same-day under the current assumptions."
    z = min(rows, key=lambda z: z["grad_stops"] / bridge.STOPS_SD_TODAY[z["zone"]])
    now = bridge.STOPS_SD_TODAY[z["zone"]]
    return (f"{z['zone']} is closest. Same-day there pays once a same-day van makes about {z['grad_stops']:.0f} "
            f"stops a day; we estimate {now} today, so it needs about {z['grad_stops'] / now - 1:.0%} more "
            f"same-day orders per area. Its first same-day step returns {z['sd_first_ratio']:.1f} per AED 1 now.")


def template_answer(question, changes, before, after):
    desc = describe_changes(changes)
    if re.search(r"graduat|next zone|which zone", question.lower()) and not desc:
        return graduation_answer(before)
    if not desc and not changes.get("focus_zone"):
        return ("I can answer what-if questions about fuel or delivery costs, lost-sale rates, order value, urgent "
                "share or rivals in a zone. Try: \"What happens in Al Ain if fuel costs rise 20%?\"")
    zone = changes.get("focus_zone")
    lines = []
    if zone:
        zb, za = bridge.zone_row(before, zone), bridge.zone_row(after, zone)
        lead = (f"{zone} keeps the same decision: {kind(za)}." if kind(zb) == kind(za) else
                f"{zone} moves from '{kind(zb)}' to '{kind(za)}'.")
        lines.append(lead)
        lines.append(f"Its first same-day step returns {zb['sd_first_ratio']:.1f} per AED 1 before and "
                     f"{za['sd_first_ratio']:.1f} after, against a {after['params']['ratio_min']:.0f} to 1 rule. "
                     f"Same-day target: {zb['sd1'] * 100:.1f}% before, {za['sd1'] * 100:.1f}% after.")
    else:
        flips = [f"{z['zone']} ({kind(z)} to {kind(w)})" for z, w in zip(before["zones"], after["zones"])
                 if kind(z) != kind(w)]
        moves = [f"{z['zone']} {z['sd1'] * 100:.1f}% to {w['sd1'] * 100:.1f}%"
                 for z, w in zip(before["zones"], after["zones"])
                 if kind(z) == kind(w) and abs(z["sd1"] - w["sd1"]) > 1e-6]
        lines.append(("Decisions that change: " + "; ".join(flips) + ".") if flips else
                     "No zone changes its decision.")
        if moves:
            lines.append("Same-day targets that move: " + "; ".join(moves) + ".")
    rb = before["ratio_delivery"] or 0
    ra = after["ratio_delivery"] or 0
    sb, sa = bridge.spend_2027(before)["spend"], bridge.spend_2027(after)["spend"]
    lines.append(f"UAE plan: same-day {before['sd1'] * 100:.1f}% to {after['sd1'] * 100:.1f}%, 2027 spend USD "
                 f"{usd_m(sb):.2f}M to {usd_m(sa):.2f}M, return {rb:.1f} to {ra:.1f} per AED 1 of delivery cost.")
    if desc:
        lines.append(f"Scenario: {desc}.")
    return " ".join(lines)


def answer(claude, settings, question):
    """Returns dict(text, engine, note, changes, before, after)."""
    note = None
    if claude and claude.configured():
        try:
            changes = claude.ask(EXTRACT_SYSTEM, question, schema=EXTRACT_SCHEMA, effort="low", max_tokens=3000)
            if not changes.get("answerable", True):
                return dict(text="That question is outside this plan. Ask about delivery speed, costs, customers or "
                                 "rivals in a zone.", engine=claude.label, note=None, changes=changes,
                            before=None, after=None)
            before, after = compare(settings, changes)
            payload = dict(question=question, scenario=describe_changes(changes), focus_zone=changes.get("focus_zone"),
                           before=facts(before, settings),
                           after=facts(after, bridge.with_changes(settings, changes)))
            text = claude.ask(ANSWER_SYSTEM, json.dumps(payload, ensure_ascii=False), effort="low", max_tokens=4000)
            return dict(text=text, engine=claude.label, note=None, changes=changes, before=before, after=after)
        except AIUnavailable as e:
            note = f"{e} Showing the offline answer."
    changes = rule_changes(question)
    before, after = compare(settings, changes)
    return dict(text=template_answer(question, changes, before, after), engine="Offline rules", note=note,
                changes=changes, before=before, after=after)
