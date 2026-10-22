"""Tags a shopping search as urgent (needed today) or planned, in English or Arabic.

Claude does the tagging when connected; the offline rules below keep the demo working without it.
"""
import re

from .ai import AIUnavailable

GROUPS = ["Phone and laptop accessories", "Baby, health and pharmacy", "Party, gifts and occasions",
          "School and office supplies", "Home and kitchen", "Books, toys and furniture", "Other"]
URGENT_GROUPS = set(GROUPS[:4])

TIME_WORDS = ["today", "tonight", "now", "urgent", "asap", "same day", "same-day", "emergency", "right away",
              "immediately", "last minute", "within an hour", "this evening",
              "اليوم", "الليلة", "الآن", "الان", "عاجل", "ضروري", "مستعجل", "فورا", "فوراً", "حالا", "حالاً", "بسرعة"]

GROUP_WORDS = {
    "Phone and laptop accessories": ["charger", "cable", "adapter", "power bank", "powerbank", "earphone", "earbuds",
                                     "airpods", "headphone", "phone case", "screen protector", "usb", "type c",
                                     "lightning", "mouse", "شاحن", "كيبل", "كابل", "سماعات", "سماعة", "باور بانك",
                                     "جراب", "واقي شاشة"],
    "Baby, health and pharmacy": ["formula", "diaper", "diapers", "nappies", "wipes", "thermometer", "medicine",
                                  "panadol", "paracetamol", "plaster", "sunscreen", "mask", "vitamin", "حفاض",
                                  "حفاضات", "حليب أطفال", "حليب اطفال", "ميزان حرارة", "دواء", "بنادول",
                                  "واقي شمس", "مناديل مبللة"],
    "Party, gifts and occasions": ["birthday", "balloon", "balloons", "gift", "candles", "party", "eid",
                                   "decoration", "wrapping", "cake topper", "هدية", "بالونات", "بالون",
                                   "عيد ميلاد", "شموع", "زينة", "عيد", "حفلة"],
    "School and office supplies": ["printer ink", "ink", "toner", "notebook", "stationery", "school bag",
                                   "calculator", "a4 paper", "pens", "pencil", "حبر", "دفتر", "قرطاسية",
                                   "حاسبة", "شنطة مدرسية", "أقلام", "اقلام"],
    "Home and kitchen": ["blender", "air fryer", "pan", "bedsheet", "lamp", "curtain", "kettle", "vacuum",
                         "خلاط", "قلاية", "مقلاة", "ستارة", "غلاية", "مكنسة"],
    "Books, toys and furniture": ["sofa", "bookshelf", "wardrobe", "mattress", "desk", "chair", "table", "novel",
                                  "book", "lego", "toy", "كنبة", "مكتبة", "خزانة", "مرتبة", "رواية", "كتاب",
                                  "ليغو", "لعبة", "كرسي"],
}

# Items people rarely buy unless they need them now.
NOW_ITEMS = ["charger", "power bank", "powerbank", "formula", "diaper", "diapers", "nappies", "thermometer",
             "medicine", "panadol", "paracetamol", "balloons", "candles", "party plates",
             "شاحن", "باور بانك", "حفاض", "حليب أطفال", "حليب اطفال", "ميزان حرارة", "دواء", "بنادول", "بالونات",
             "شموع"]

ARABIC = re.compile(r"[؀-ۿ]")
LATIN = re.compile(r"[A-Za-z]")


def language(text):
    a, l = bool(ARABIC.search(text)), bool(LATIN.search(text))
    return "mixed" if a and l else "ar" if a else "en"


def _has(text, word):
    if ARABIC.search(word):
        return word in text
    return re.search(r"(?<![a-z])" + re.escape(word) + r"(?![a-z])", text) is not None


def rule_tag(query):
    t = query.lower()
    time_hit = next((w for w in TIME_WORDS if _has(t, w)), None)
    now_hit = next((w for w in NOW_ITEMS if _has(t, w)), None)
    group = "Other"
    for g, words in GROUP_WORDS.items():
        hit = next((w for w in words if _has(t, w)), None)
        if hit:
            group = g
            break
    if time_hit:
        label, conf = "urgent", 0.85 if group in URGENT_GROUPS or group == "Other" else 0.65
        reason = f"Asks for it now ('{time_hit}')"
    elif now_hit:
        label, conf, reason = "urgent", 0.65, "Item people usually need the same day"
    elif group in URGENT_GROUPS:
        label, conf, reason = "planned", 0.55, "Useful soon, rarely needed today"
    elif group == "Other":
        label, conf, reason = "planned", 0.5, "No sign of urgency"
    else:
        label, conf, reason = "planned", 0.8, "Item people usually plan ahead"
    return dict(query=query, label=label, item_group=group, confidence=conf, reason=reason,
                language=language(query), engine="Offline rules")


SYSTEM = (
    "You tag UAE online shopping searches for Speed Compass, a delivery-speed planning tool. For each search, "
    "decide whether the shopper most likely needs the item today (urgent) or can wait a day or more (planned).\n"
    "Urgent signals: words such as today, tonight, now, urgent, asap, same day, and Arabic words such as اليوم, "
    "الليلة, الآن, عاجل, ضروري, مستعجل; and items people usually need quickly: phone and laptop chargers, cables "
    "and power banks, baby care and formula, medicine and thermometers, party supplies and last-minute gifts, "
    "school and office supplies.\n"
    "Planned signals: furniture, mattresses, books, toys, large appliances and home decor, unless the search asks "
    "for it today.\n"
    "Searches may be in English, Arabic or both. Choose the item group from the allowed list. Give a confidence "
    "between 0 and 1 and a reason of at most 12 words, in English. Do not use dashes as punctuation."
)

ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "label": {"type": "string", "enum": ["urgent", "planned"]},
        "item_group": {"type": "string", "enum": GROUPS},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["label", "item_group", "confidence", "reason"],
    "additionalProperties": False,
}


def ai_tag(claude, query):
    out = claude.ask(SYSTEM, f"Search: {query}", schema=ITEM_SCHEMA, effort="low", max_tokens=3000)
    out.update(query=query, language=language(query), engine=claude.label)
    return out


def ai_tag_batch(claude, queries):
    schema = {"type": "object", "properties": {"results": {"type": "array", "items": ITEM_SCHEMA}},
              "required": ["results"], "additionalProperties": False}
    listing = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(queries))
    out = claude.ask(SYSTEM, "Tag each search below. Return one result per search, in the same order.\n\n" + listing,
                     schema=schema, effort="low", max_tokens=12000)
    results = out.get("results", [])
    if len(results) != len(queries):
        raise AIUnavailable("Claude returned a different number of results.")
    for q, r in zip(queries, results):
        r.update(query=q, language=language(q), engine=claude.label)
    return results


def tag(claude, query):
    """Claude if connected, otherwise the offline rules. Returns (result, note)."""
    if claude and claude.configured():
        try:
            return ai_tag(claude, query), None
        except AIUnavailable as e:
            return rule_tag(query), f"{e} Showing the offline rules instead."
    return rule_tag(query), None


def tag_batch(claude, queries):
    if claude and claude.configured():
        try:
            return ai_tag_batch(claude, queries), None
        except AIUnavailable as e:
            return [rule_tag(q) for q in queries], f"{e} Showing the offline rules instead."
    return [rule_tag(q) for q in queries], None
