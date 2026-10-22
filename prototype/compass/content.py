"""Static content shown in the prototype. Promises and sources match Appendix F of the supporting document."""

RIVAL_PROMISES = [
    # service, speed badge, badge kind, promise, coverage, source
    ("Amazon.ae same-day", "Same day", "day", "Free on eligible orders over AED 100 placed before 12 PM",
     "Select metro areas", "[2]"),
    ("Amazon 2-hour delivery", "2 hours", "hours", "Free over AED 100, otherwise AED 3",
     "Thousands of items, 30+ categories", "[4]"),
    ("Amazon Now", "15 min", "minutes", "15 minutes, 24/7", "25 locations incl. Dubai, Abu Dhabi Central, Al Ain",
     "[4, 19]"),
    ("noon", "Same day", "day", "Free same-day over AED 100; free next-day, no minimum", "UAE", "[5]"),
    ("noon Minutes", "15 min", "minutes", "15 minutes", "Dubai, Abu Dhabi, Sharjah, Ajman; hubs planned in ADNOC "
                                                        "stations", "[6, 28]"),
    ("Careem Quik", "15 min", "minutes", "15 minutes", "Dubai and Abu Dhabi", "[7]"),
    ("talabat mart", "20 to 30 min", "minutes", "20 to 30 minutes", "Group figure, eight markets", "[8]"),
    ("Carrefour (Majid Al Futtaim)", "60 min", "hours", "60 minutes or less, 24/7", "Dubai", "[52]"),
]

# Rival events a presenter can switch on during the demo.
RIVAL_EVENTS = [
    ("noon Minutes opens in RAK and Fujairah", {"Outer emirates": "full"}),
    ("Careem Quik covers all of Al Ain", {"Al Ain": "full"}),
    ("A rival leaves Sharjah-Ajman", {"Sharjah city and Ajman": "none"}),
]

# 30 searches standing in for one hour of Dubai searches (illustrative, English and Arabic).
SAMPLE_SEARCHES = [
    "iphone charger same day",
    "sofa 3 seater grey",
    "baby formula stage 1",
    "bookshelf white 5 tier",
    "air fryer 5 litre",
    "kids digital thermometer",
    "office chair ergonomic",
    "lego technic car",
    "birthday balloons for tonight",
    "king size mattress",
    "phone case iphone 15",
    "paulo coelho novel",
    "running shoes men",
    "power bank urgent",
    "65 inch tv",
    "yoga mat",
    "printer ink hp 305",
    "school bag for boys",
    "eid gift box for her",
    "sunscreen spf 50",
    "usb c cable 2m",
    "شاحن ايفون اليوم",
    "كنبة زاوية",
    "حفاضات بامبرز مقاس 4",
    "خلاط كهربائي",
    "مكتبة خشب",
    "عطر عود",
    "ساعة ذكية",
    "سماعات بلوتوث",
    "طقم أواني طبخ",
]

EXAMPLE_SEARCHES = ["laptop charger tonight", "شاحن ايفون اليوم", "3 seater sofa", "baby thermometer"]

EXAMPLE_QUESTIONS = [
    "What happens in Al Ain if fuel costs rise 20%?",
    "What if urgent shoppers are half as likely to leave?",
    "What if the average order drops to AED 150?",
    "ماذا يحدث إذا ارتفعت تكاليف التوصيل 30%؟",
]
