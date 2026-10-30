"""Underdog Story core: the v9 underdog arc as a template with business slots, prompt building, the script checks,
the $0 draft animatic, the final cut (the v9 recipe) and the score mix.
Pure Python + Pillow + ffmpeg, no ComfyUI imports, so it can be tested on its own. Apache-2.0."""
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
PRESETS_DIR = ROOT / "presets"
FONT = ROOT / "fonts" / "Inter.ttf"

# ---------------------------------------------------------------- cast, slots, rules
# Reference sheets for everything: every recurring person, place and prop has a sheet, and a prop that changes state has
# one sheet per state (the rival store open / closed), so nothing is left for the model to re-invent between scenes.
CHARACTERS = ["owner", "rival", "regular", "hero1", "hero2"]
PROP_SHEETS = ["location", "rival_store_open", "rival_store_closed", "old_car", "prize_car"]
ROLES = CHARACTERS + PROP_SHEETS   # reference image slots, in this order
MAX_REFS = 10   # Nano Banana 2 takes up to 14 (node tooltip); above 10 the node switches to inline upload, so stay at 10
SPEAKERS = set(CHARACTERS) | {"offscreen", "customer", "crowd"}
PLACEHOLDERS = set(CHARACTERS) | {"business"}
CARDS = {"SIX MONTHS LATER", "NEXT MORNING", "ONE YEAR LATER", "THREE MONTHS LATER", "SIX MONTHS EARLIER"}
TRANSITIONS = {"cut": ("fade", 0.05), "dissolve": ("fade", 0.3), "dissolve_long": ("fade", 0.8), "fadeblack": ("fadeblack", 0.6)}
TONES = {"funny": "Dry comedy timing, natural understated delivery, reactions carry the laughs.",
         "heartfelt": "Sincere, warm performances; let the quiet moments breathe."}
VEO_MODELS = ["veo-3.1-lite", "veo-3.1-fast-generate", "veo-3.1-generate"]   # exact Veo3VideoGenerationNode values
VEO_SECONDS = (4, 6, 8)
MAX_LINE_WORDS = 20          # one spoken line
WORDS_PER_SECOND = 4         # everything spoken in one take: 8 s -> 32 words, 6 s -> 24, 4 s -> 16
STYLE = "Glossy 3D animated family-film style"
LOCKED = "LOCKED-OFF STATIC CAMERA"
KEYFRAME_HEAD = (f"Keyframe for an animated film. {STYLE}, vertical 9:16 cinematic frame. Keep every character's face, hair, "
                 "facial hair, glasses, build and outfit exactly as in the reference images, and every building, vehicle and place exactly "
                 "as in its reference sheet (same shape, color and details). No captions, no subtitles, no real brand logos.")
RULES_TAIL = ("Background life: extras keep walking and cars keep passing; nobody in the background freezes. "
              "No object, prop or furniture appears or disappears during the take. "
              "Nobody walks through a counter or a wall, and no crowd files out through a door. "
              "All dialogue ends at least one second before the end of the take; the last second is a silent held reaction.")
MOTION_TAIL = (f"{STYLE}. Keep every character, face, outfit and the setting exactly as in the start frame. {RULES_TAIL} "
               "One continuous take, no cuts. No captions, no subtitles, no on-screen text except signs already in the frame.")
SILENT_VERBS = ("says", "shouts", "yells", "whispers", "asks", "replies", "mutters")
# Real people never appear by name. Brand names never appear (no real logos, no real car models, no lookalike rival brands).
# Stored as SHA-256 of the lower-case first name, so the repo itself holds no real names.
REAL_NAME_SHA256 = {"102cf10b5286bad9fcfe5e275ace3ddd7dcc23931fb0ca93dc223daf9877cabd",
                    "b8cca97395d6540ab952aee96f21521c2688b804d97357697e9dd7d0b49b6bb2"}
BRANDS = {"ferrari", "lamborghini", "lambo", "porsche", "mclaren", "bugatti", "tesla", "bmw", "mercedes", "audi", "starbucks",
          "mcdonald's", "mcdonalds", "dunkin", "nike", "adidas", "apple", "iphone", "instagram", "tiktok", "youtube", "facebook",
          "google", "coca-cola", "pepsi", "gucci", "louis vuitton", "rolex", "uber", "doordash", "supercuts", "great clips",
          "sport clips", "taco bell", "chipotle", "krispy kreme", "panera", "cinnabon", "chick-fil-a", "wendy's", "opi", "essie",
          "domino's", "pizza hut", "costco", "walmart", "target", "amazon"}
# Words that belong to the bakery sample only; they must never leak into another business's film.
BAKERY_WORDS = ("croissant", "croissants", "bakery", "baker", "baking", "bakes", "dough", "pastry", "pastries", "oven", "flour",
                "bun", "buns", "megabun", "bread")

# The slots a business fills. Lines are spoken; everything else is described on screen.
SLOTS = {
    "noun": "what the rival calls the business, e.g. 'barbershop'",
    "place": "the owner's business as seen in a keyframe, e.g. 'the old corner barbershop with a red-and-white barber pole'",
    "counter": "where the owner works, e.g. 'the vintage barber chair by the big mirror'",
    "product": "the signature product, singular, e.g. 'haircut'",
    "products": "the signature product, plural",
    "rival_brand": "the fictional rival chain's sign, ONE invented ALL-CAPS word (no lookalike of a real brand), e.g. 'MEGAFADE'",
    "rival_place": "the rival's flashy landmark storefront, e.g. 'chrome mega-salon with a giant spinning razor on the roof'",
    "gimmick": "the rival's gimmick product, e.g. 'free four-minute glitter fades'",
    "busy": "one sentence: the business on a good busy day, with moving extras",
    "unsold": "one sentence: closing time on a bad day, what sits unused",
    "count_line": "LINE (owner): the bad day in numbers, self-explanatory, e.g. 'Six cuts today. Six.'",
    "regular_line": "LINE (loyal regular): warm praise on a good day",
    "offer_item": "one sentence: the last item/free slot, visible from the first frame",
    "offer_action": "how the owner offers it, ending in 'and says kindly'",
    "offer_line": "LINE (owner): the offer, e.g. 'Last one. On the house.'",
    "taste_setup": "one sentence: hero 1 about to try it, hero 2 beside; use {hero1} and {hero2}",
    "taste": "hero 1 tries it: an action with a silent stunned beat, mouth closed",
    "bad_idea_line": "LINE (hero 1): two bad marketing ideas, e.g. 'Okay. Ideas. A dancing razor mascot? Glitter fades?'",
    "good_idea_line": "LINE (hero 1): the turn to the real idea",
    "heirloom": "the family heirloom/craft detail on the wall or counter",
    "heirloom_line": "LINE (owner): the heart line about the heirloom",
    "craft": "the owner's craft in action, e.g. 'giving a careful straight-razor shave'",
    "craft_line": "LINE (hero 2): 'Don't look at us. Look at the ...'",
    "regular_back_line": "LINE (loyal regular): first in the new line",
    "showdown_line": "LINE (owner): puts the rival in their place",
    "old_car": "the owner's old car that breaks down, e.g. 'the old rusty green pickup truck'",
    "payoff": "the earned prize car, an original design with no badges, no emblems and no plate text",
    "payoff_line": "LINE (owner): the treat-yourself payoff",
    "dm_business": "a DIFFERENT kind of small business that messages for episode 2, e.g. 'nail salon'",
}
SLOT_DEFAULTS = {
    "hook_line": "What's up, everybody! {rival_brand} is officially OPEN!",
    "hook_tag": "Sorry, little {noun}.",
    "drift_line": "Just you again, huh?",
    "low_line": "Not today... please, not today.",
    "film_line": "Can we film you?",
    "good_idea_line": "...No. This should have a line around the block.",
    "regular_back_line": "Told you. They always come back.",
    "fall_line": "Guys... {rival_brand} is... closed.",
    "payoff_line": "Okay, okay... ONE treat.",
    "ask_line": "So... you hiring?",
    "no_line": "Hmm. No.",
}
LINE_SLOTS = {k for k, v in SLOTS.items() if v.startswith("LINE")} | set(SLOT_DEFAULTS)

# ---------------------------------------------------------------- the arc (v9 "The Last Croissant", generalized)
# State lines: what state a recurring prop is in, per beat, so the prompt text and the attached state sheet agree.
RIVAL_GRAND = ('The rival store "{rival_brand}" is OPEN on its GRAND OPENING day: sign lit, balloons and bunting, the same building as '
               "its sheet.")
RIVAL_OPEN = ('The rival store "{rival_brand}" is OPEN and busy: sign lit, doors open; the same building as its sheet, the '
              "grand-opening balloons and bunting are gone.")
RIVAL_OPEN_EMPTY = ('The rival store "{rival_brand}" is still OPEN but EMPTY: sign lit, nobody inside or in line; the same building as '
                    "its sheet, no balloons, no bunting.")
RIVAL_CLOSED = ('The rival store "{rival_brand}" is CLOSED for good: dark windows, sign unlit, the metal shutter all the way down with '
                'a "FOR LEASE" sign on it, no banner, no balloons, nobody inside; the same building as its sheet.')
RIVAL_CLOSED_BG = ('If the rival store "{rival_brand}" across the street is in view, it is still CLOSED: dark, shutter down, '
                   '"FOR LEASE" sign, no banner, no balloons.')
OLD_CAR_BROKEN = ("{old_car} is BROKEN DOWN at the curb: hood up, steam pouring from the engine; the same vehicle as its sheet "
                  "(shape, color, dents).")
OLD_CAR_TOWED = "{old_car}, still broken down, is hooked to a tow truck; the same vehicle as its sheet (shape, color, dents)."
PRIZE_CAR = ("{payoff} is brand new and shiny, exactly as in its sheet: the same body shape, color, wheels and details in every "
             "shot.")
AT ="At {place}: {owner} works screen-left at {counter}, visitors screen-right."
ARC = [
    dict(name="grand opening", seconds=8, landmark=True, refs=["rival", "owner", "rival_store_open", "location"], state=[RIVAL_GRAND],
         transition="dissolve",
         keyframe='Bright morning on the street. Across the street, the brand-new {rival_place} with the big sign "{rival_brand}" is having its '
                  "grand opening: a ribbon, confetti cannons, gold balloons, a lively moving crowd. In the foreground screen-right, {rival} "
                  "vlogs to a phone on a selfie stick, grinning. Screen-left, {owner} watches from the doorway of {place}, arms folded. "
                  'The only readable text is "{rival_brand}".',
         camera="wide on the street, both storefronts in frame",
         performance=[("rival", "turns the selfie stick to show the opening and shouts to the phone", "{hook_line}"),
                      ("rival", "swings the phone toward the small shop across the street, smirks and says", "{hook_tag}"),
                      ("owner", "stays in the doorway, mouth closed, jaw tight")],
         props=['the "{rival_brand}" sign', "the ribbon", "the selfie stick"],
         ambience="Street ambience, a cheering crowd, confetti pops.", music="A bright brassy fanfare from the opening."),
    dict(name="the regulars", seconds=6, refs=["owner", "regular", "location"], transition="dissolve_long",
         keyframe="Warm busy morning. " + AT + " {busy} {regular} stands at {counter}, smiling. Extras move in the background.",
         camera="slow push-in on {regular}",
         performance=[("regular", "says warmly to {owner}", "{regular_line}"), ("owner", "smiles, mouth closed, and keeps working")],
         props=["{counter}"], ambience="Busy room tone, happy chatter.", music="A warm, light theme."),
    dict(name="the drift", seconds=8, card="SIX MONTHS LATER", landmark=True, refs=["owner", "regular", "location", "rival_store_open"],
         state=[RIVAL_OPEN], transition="dissolve",
         keyframe="Grey afternoon. " + AT + " The place is nearly empty. {regular} sits alone in the usual spot. Behind them, across the "
                  'street, a long line of people waits outside the {rival_place} with the sign "{rival_brand}", holding {gimmick}; the line '
                  'shuffles forward. The only readable text is "{rival_brand}".',
         camera="medium shot, the rival's line visible in the background",
         performance=[("owner", "glances across the street, then at {regular}, and says with a small smile", "{drift_line}"),
                      ("regular", "raises a hand, mouth closed, and nods")],
         props=["{counter}", 'the "{rival_brand}" sign across the street'],
         ambience="Quiet room tone, faint street noise from across the road.", music="The warm theme, slower and thinner."),
    dict(name="the count", seconds=6, refs=["owner", "location"], transition="dissolve_long",
         keyframe="Closing time, rain on the windows. " + AT + " {unsold} {owner} stands alone, counting a few coins. Dim warm light.",
         camera="slow push-in on {owner}",
         performance=[("owner", "looks at the coins, sighs and says quietly", "{count_line}")],
         props=["{counter}", "the coins"], ambience="Rain, a ticking clock.", music="A slow sad piano note."),
    dict(name="the low point", seconds=8, refs=["owner", "old_car"], state=[OLD_CAR_BROKEN], transition="dissolve_long",
         keyframe="Cold early morning on a quiet street. {owner} stands beside {old_car}, stalled at the curb with steam pouring from "
                  "the hood, holding an open wallet with only a few coins and a folded repair quote. Far down the road the gold "
                  '"{rival_brand}" sign glows. Cars pass in the background.',
         camera="medium shot; the camera holds as {owner} starts to walk",
         performance=[("owner", "looks at the steam, then at the few coins, and says under the breath", "{low_line}"),
                      ("owner", "pockets the wallet, mouth closed, and walks off down the sidewalk, leaving the car")],
         props=["{old_car}", "the wallet"], ambience="Cold wind, a hissing engine, passing cars.", music="Silence, then one low note."),
    dict(name="strangers", seconds=8, refs=["owner", "hero1", "hero2", "location"], transition="dissolve",
         keyframe="Rainy evening. " + AT + " {offer_item} {hero1} and {hero2} have just come in from the rain, screen-right, shaking off "
                  "water. Warm light, rain on the window.",
         camera="medium shot on {owner}, slight push-in",
         performance=[("hero1", "looks around the empty place, mouth closed"), ("owner", "{offer_action}", "{offer_line}"),
                      ("hero2", "smiles, mouth closed")],
         props=["{counter}", "the last item on offer"], ambience="Rain outside, quiet room tone.", music="A hopeful soft note."),
    dict(name="bad ideas", seconds=8, refs=["owner", "hero1", "hero2", "location"], transition="dissolve",
         keyframe="Rainy evening. " + AT + " {taste_setup} {owner} watches, arms crossed.",
         camera="static medium shot on {hero1}",
         performance=[("hero1", "{taste}"), ("hero1", "turns to {hero2}, counting on fingers, and says", "{bad_idea_line}"),
                      ("hero2", "shakes head slowly, mouth closed"),
                      ("hero1", "looks around the empty place and says, serious now", "{good_idea_line}")],
         props=["{counter}"], ambience="Rain outside.", music="A comic pluck, then a warm swell."),
    dict(name="the heart", seconds=8, refs=["owner", "hero2", "location"], transition="dissolve",
         keyframe="Night. " + AT + " {owner} is {craft}. Beside {owner}, in plain view: {heirloom}. {hero2} stands in the soft background, "
                  "phone lowered, listening. Warm low light.",
         camera="slow push-in on the hands, then the face",
         performance=[("owner", "pauses, looks at the old keepsake and says softly, with pride", "{heirloom_line}"),
                      ("hero2", "listens, mouth closed")],
         props=["{heirloom}"], ambience="Quiet night room tone.", music="Gentle piano."),
    dict(name="going viral", seconds=6, views=True, refs=["owner", "hero2", "location"], transition="dissolve",
         keyframe="Night. " + AT + " {hero2} films {owner} up close on a phone while {owner} keeps {craft}. Warm light.",
         camera="static close medium shot",
         performance=[("hero2", "raises the phone and asks gently", "{film_line}"),
                      ("owner", "looks up at the phone, unsure, mouth closed, then back to work"),
                      ("hero2", "nods toward the work and says", "{craft_line}")],
         props=["the phone", "{heirloom}"], ambience="Quiet room tone.", music="The theme returns, building."),
    dict(name="the line comes back", seconds=8, card="NEXT MORNING", landmark=True, refs=["regular", "location", "rival_store_open"],
         state=[RIVAL_OPEN_EMPTY], transition="dissolve",
         keyframe="Bright morning on the street. Outside {place}, a long line of excited customers wraps around the block, phones up, the "
                  "line moving forward step by step. {regular} stands first in line, beaming. Across the street, the {rival_place} with "
                  'the sign "{rival_brand}" stands empty. The only readable text is "{rival_brand}".',
         camera="wide on the street, both storefronts in frame",
         performance=[("regular", "turns to the people behind and says proudly", "{regular_back_line}")],
         props=['the "{rival_brand}" sign', "the line of customers"], ambience="Crowd murmur, street ambience.", music="The theme, full."),
    dict(name="the showdown", seconds=8, landmark=True, refs=["owner", "rival", "location", "rival_store_open"], state=[RIVAL_OPEN_EMPTY],
         transition="dissolve",
         keyframe="Busy morning. " + AT + " The place is full and lively. {rival} stands screen-right at the front of {counter}, having cut "
                  'the line, holding up a phone on a selfie stick. Through the window behind, the "{rival_brand}" sign across the street '
                  "stays in view. Customers wait behind {rival}, shifting and chatting.",
         camera="medium two-shot, the rival's sign visible through the window",
         performance=[("rival", "grins at the phone, mouth closed, smug"),
                      ("owner", "keeps working, does not look up, and says flatly", "{showdown_line}"),
                      ("rival", "deflates, mouth closed, and walks straight to the back of the line")],
         props=["{counter}", "the selfie stick", 'the "{rival_brand}" sign across the street'],
         ambience="Busy room tone, chatter.", music="An upbeat bass line."),
    dict(name="the fall", seconds=6, landmark=True, refs=["rival", "rival_store_closed", "location"], state=[RIVAL_CLOSED],
         transition="dissolve_long",
         keyframe='Late afternoon across the street. The {rival_place} with the sign "{rival_brand}" has closed for good: dark windows, '
                  'its metal shutter all the way down with a "FOR LEASE" sign on it, no banner. {rival} stands in front of it, vlogging to the selfie stick, deflated. '
                  'Across the street behind, the line outside {place} still moves. The only readable texts are "{rival_brand}" and "FOR LEASE".',
         camera="medium shot on {rival}, the shutter and sign in frame",
         performance=[("rival", "looks at the phone and says weakly", "{fall_line}")],
         props=['the "{rival_brand}" sign', 'the "FOR LEASE" sign', "the selfie stick"],
         ambience="Street ambience, a lonely gust of wind.", music="A deflating trombone note."),
    dict(name="the payoff", seconds=8, card="SIX MONTHS LATER", refs=["owner", "prize_car", "old_car", "location", "rival_store_closed"],
         state=[PRIZE_CAR, OLD_CAR_TOWED, RIVAL_CLOSED_BG], transition="dissolve",
         keyframe="Sunny morning at the curb outside {place}, a line of customers out the door. {owner} holds a set of new car keys "
                  "beside {payoff}. Behind, a tow truck slowly hauls away {old_car}. Cars pass.",
         camera="medium shot on {owner}, the old car leaving behind",
         performance=[("owner", "looks from the keys to the old car being towed away, grins and says", "{payoff_line}")],
         props=["{payoff}", "{old_car}", "the keys"], ambience="Street ambience, a tow truck winch.", music="A smug little sting."),
    dict(name="the ask", seconds=6, refs=["rival", "prize_car", "owner", "location", "rival_store_closed"], state=[PRIZE_CAR, RIVAL_CLOSED_BG],
         transition="dissolve",
         keyframe="Sunny afternoon on the sidewalk outside {place}. {rival} stands at the curb with no selfie stick, hands in pockets. "
                  "{payoff} with {owner} at the wheel, window down, has just pulled up beside {rival}. Pedestrians pass.",
         camera="medium shot on {rival} at the car window",
         performance=[("rival", "leans toward the car window, sheepish, and asks", "{ask_line}"),
                      ("owner", "looks at {rival}, mouth closed, eyebrows raised")],
         props=["{payoff}"], ambience="Street ambience.", music="A held, hopeful note."),
    dict(name="the last laugh", seconds=6, dm=True, refs=["owner", "rival", "prize_car", "location", "rival_store_closed"],
         state=[PRIZE_CAR, RIVAL_CLOSED_BG], transition="dissolve",
         keyframe="Same sidewalk. {owner} sits at the wheel of {payoff}, window down, sunglasses on. {rival} leans toward the window, "
                  "screen-right. Pedestrians pass.",
         camera="static close medium shot on {owner}",
         performance=[("owner", "pushes the sunglasses down, takes a beat and says", "{no_line}"),
                      ("owner", "drives off fast, mouth closed; the gust messes up the hair of {rival}, who freezes, silent")],
         props=["{payoff}"], ambience="Street ambience, an engine purr.", music="The theme's final sting."),
]
BEATS = [(i + 1, a["name"]) for i, a in enumerate(ARC)]


# ---------------------------------------------------------------- presets
def list_presets():
    return sorted(p.name for p in PRESETS_DIR.iterdir() if (p / "preset.json").exists()) if PRESETS_DIR.exists() else []


def load_preset(name):
    return json.loads((PRESETS_DIR / name / "preset.json").read_text())


# ---------------------------------------------------------------- reference sheets for everything
SHEET_SPEC = {
    "owner": "The owner: {owner}. Character sheet: front, three-quarter, side; proud, tired and smug expressions.",
    "rival": "The rival influencer: {rival}, with a phone on a selfie stick. Front, three-quarter, side; a grin and a deflated look.",
    "regular": "The loyal regular: {regular}. Front, three-quarter, side; a warm smile.",
    "hero1": "Agency duo, hero 1: {hero1}. Front, three-quarter, side.",
    "hero2": "Agency duo, hero 2: {hero2}. Front, three-quarter, side.",
    "location": "The owner's place: {place}. Street exterior and interior ({counter}). No readable shop sign.",
    "rival_store_open": 'The rival landmark OPEN, grand-opening day: the {rival_place}, sign lit and reading exactly "{rival_brand}", '
                        "balloons and bunting. Street level, the whole storefront in frame.",
    "rival_store_closed": 'The SAME rival building CLOSED for good: dark windows, the "{rival_brand}" sign unlit, the metal shutter all the '
                          'way down with a "FOR LEASE" sign, no banner, no balloons, nobody inside. Same angle as rival_store_open '
                          "(make it from that sheet so the building matches).",
    "old_car": "The owner's old car: {old_car}. Two views of the same vehicle: parked and worn; BROKEN DOWN with the hood up and "
               "steam pouring out. No badges, no plate text.",
    "prize_car": "The prize car: {payoff}. Front, three-quarter, side and rear views of the same car.",
}


def sheet_use():
    """{role: [beats that attach this sheet]}: every sheet some scene uses (all of ROLES)."""
    use = {r: [] for r in ROLES}
    for i, a in enumerate(ARC):
        for r in a["refs"][:MAX_REFS]:
            use[r].append(i + 1)
    return use


def sheet_rows(preset):
    """[(role, asset path relative to the preset folder, one-line description)] for every sheet a preset needs."""
    p = load_preset(preset)
    words = dict(p.get("cast", {}), **p.get("slots", {}))
    assets = p.get("assets", {})
    return [(r, assets.get(r, f"assets/{r}.png"), _fill_slots(SHEET_SPEC[r], words)) for r in ROLES]


def missing_sheets_message(missing):
    """The one message for missing sheets: the paid path raises it, the free draft prints it as a warning."""
    if not missing:
        return f"All {len(ROLES)} reference sheets are attached."
    use = sheet_use()
    rows = "; ".join(f"{r} (scene{'s' if len(use[r]) > 1 else ''} {', '.join(map(str, use[r]))})" for r in missing)
    return (f"Missing reference sheets ({len(missing)} of {len(ROLES)}): {rows}. Every recurring person, prop and place needs its "
            "sheet, or it drifts between scenes.")


# ---------------------------------------------------------------- small text helpers
def _words(s):
    return len(re.findall(r"[A-Za-z0-9']+", s))


def _outside_quotes(s):
    return re.sub(r'"[^"]*"', " ", s)


def _has_word(text, word):
    return re.search(r"(?<![A-Za-z])" + re.escape(word) + r"(?![A-Za-z])", text, re.I) is not None


def real_names_in(text):
    return sorted({w for w in re.findall(r"[A-Za-z]+", text) if hashlib.sha256(w.lower().encode()).hexdigest() in REAL_NAME_SHA256})


def bakery_words_in(text):
    return sorted({w for w in BAKERY_WORDS if _has_word(text, w)})


def brand_lookalike(name):
    """A real brand this invented rival name contains or closely resembles, else None."""
    n = re.sub(r"[^a-z]", "", name.lower())
    for b in BRANDS:
        bb = re.sub(r"[^a-z]", "", b)
        if len(bb) >= 4 and (bb in n or difflib.SequenceMatcher(None, n, bb).ratio() >= 0.75):
            return b
    return None


def _cap(s):
    return s[:1].upper() + s[1:]


def _sentence_case(text):
    """Capitalise each sentence start outside quoted dialogue (a filled-in cast description starts lower-case)."""
    parts = re.split(r'("[^"]*")', text)
    for k in range(0, len(parts), 2):
        parts[k] = re.sub(r"([.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), parts[k])
    return _cap("".join(parts))


def _fill_slots(text, slots):
    for _ in range(4):   # slots may refer to other slots ({rival_brand} inside hook_line)
        new = re.sub(r"\{(\w+)\}", lambda m: slots.get(m.group(1), m.group(0)), text)
        if new == text:
            break
        text = new
    return text


def _fill_cast(text, brief):
    cast = dict(brief["cast"], business=brief["business_name"])
    return re.sub(r"\{(\w+)\}", lambda m: cast.get(m.group(1), m.group(0)), text)


# ---------------------------------------------------------------- slots -> raw script
def check_slots(slots):
    errors = []
    if not isinstance(slots, dict):
        return ["slots must be an object"]
    for k in SLOTS:
        v = slots.get(k, SLOT_DEFAULTS.get(k))
        if not isinstance(v, str) or not v.strip():
            errors.append(f"slot '{k}' is missing ({SLOTS[k]})"); continue
        if len(v) > 400:
            errors.append(f"slot '{k}' is too long")
        if k in LINE_SLOTS and _words(v) > MAX_LINE_WORDS:
            errors.append(f"slot '{k}' line has {_words(v)} words (max {MAX_LINE_WORDS})")
    rb = slots.get("rival_brand", "")
    if isinstance(rb, str) and rb:
        if not re.fullmatch(r"[A-Z][A-Z0-9\-]{2,15}", rb):
            errors.append(f"rival_brand '{rb}' must be one invented ALL-CAPS word, 3 to 16 letters")
        lk = brand_lookalike(rb)
        if lk:
            errors.append(f"rival_brand '{rb}' looks like the real brand '{lk}'")
    return errors


def arc_scenes(slots):
    """The 15-beat arc with a business's slots filled in. Cast placeholders ({owner}, ...) stay for the checks."""
    s = dict(SLOT_DEFAULTS, **{k: v for k, v in slots.items() if isinstance(v, str)})
    f = lambda t: _fill_slots(t, s)
    raw = []
    for i, a in enumerate(ARC):
        camera = f(a["camera"])
        if a.get("landmark"):
            camera = f'{LOCKED}, no pan, no zoom; the "{s["rival_brand"]}" storefront stays visible in frame the whole take; ' + camera
        state = " ".join(f(x) for x in a.get("state", []))
        raw.append({"beat": i + 1, "name": a["name"], "seconds": a["seconds"], "card": a.get("card"), "landmark": bool(a.get("landmark")),
                    "views": bool(a.get("views")), "dm": bool(a.get("dm")), "keyframe": f(a["keyframe"]), "state": state, "camera": camera,
                    "performance": [{"who": p[0], "how": f(p[1]), "line": f(p[2]) if len(p) > 2 else None} for p in a["performance"]],
                    "props": [f(p) for p in a["props"]], "ambience": f(a["ambience"]), "music": f(a["music"]),
                    "refs": list(a["refs"]), "transition": a["transition"]})
    return raw


# ---------------------------------------------------------------- the checks
CROWD_EXIT = re.compile(r"\b(customers|crowd|people|everyone|regulars|extras|the line)\b[^.]{0,60}?\b(walk|walks|file|files|leave|leaves|"
                        r"exit|exits|follow|follows|stream|streams|pour|pours|rush|rushes)\b[^.]{0,40}?\b(out|through|over)\b[^.]{0,12}?"
                        r"\b(door|doors|doorway|counter|counters)\b", re.I)
TIME_JUMP = re.compile(r"\b(next morning|next day|months later|weeks later|years later|days later)\b", re.I)
BARE = {"yes", "no", "nope", "yeah", "yep", "sure", "hmm", "ok", "okay", "maybe", "one", "two", "three", "four", "five", "six",
        "seven", "eight", "nine", "ten", "dozen", "none", "zero"}


def _bare_answer(line):
    w = re.findall(r"[a-z0-9']+", line.lower())
    return 0 < len(w) <= 3 and all(x in BARE or x.isdigit() for x in w)


def _check_text(where, text, banned_names, errors, dialogue=False):
    for w in real_names_in(text):
        errors.append(f"{where}: real person's name '{w}'")
    for b in BRANDS:
        if _has_word(text, b):
            errors.append(f"{where}: brand name '{b}'")
    if not dialogue:
        for n in banned_names:
            if _has_word(_outside_quotes(text), n):
                errors.append(f"{where}: character name '{n}' (describe characters, never name them)")
        for ph in re.findall(r"\{(\w+)\}", text):
            if ph not in PLACEHOLDERS:
                errors.append(f"{where}: unknown placeholder {{{ph}}}")
        if CROWD_EXIT.search(text):
            errors.append(f"{where}: a crowd exits through a door/counter (use a time-skip dissolve instead)")


def validate_script(script, banned_names=()):
    """Return a list of problems (empty = valid). The same rules for every preset and for Gemini's slots."""
    errors = []
    if not isinstance(script, dict) or not isinstance(script.get("scenes"), list):
        return ["script must be an object with a 'scenes' list"]
    scenes = script["scenes"]
    if len(scenes) != len(ARC):
        errors.append(f"need exactly {len(ARC)} scenes, got {len(scenes)}")
    prev_last_line = ""
    for i, sc in enumerate(scenes):
        w = f"scene {i + 1}"
        if not isinstance(sc, dict):
            errors.append(f"{w}: not an object"); continue
        if sc.get("beat") != i + 1:
            errors.append(f"{w}: beat must be {i + 1}")
        secs = sc.get("seconds", 8)
        if secs not in VEO_SECONDS:
            errors.append(f"{w}: seconds must be one of {VEO_SECONDS}")
            secs = 8
        for k in ("keyframe", "camera", "music", "ambience"):
            if not isinstance(sc.get(k), str) or not sc[k].strip():
                errors.append(f"{w}: '{k}' must be a non-empty string")
            else:
                _check_text(f"{w} {k}", sc[k], banned_names, errors)
        if sc.get("state"):
            _check_text(f"{w} state", sc["state"], banned_names, errors)
        if sc.get("card") is not None and sc["card"] not in CARDS:
            errors.append(f"{w}: title card must be one of {sorted(CARDS)}")
        if isinstance(sc.get("keyframe"), str) and TIME_JUMP.search(sc["keyframe"]) and not sc.get("card"):
            errors.append(f"{w}: the story jumps in time ('{TIME_JUMP.search(sc['keyframe']).group(0)}') without a title card")
        if sc.get("landmark") and LOCKED not in (sc.get("camera") or ""):
            errors.append(f"{w}: the rival landmark must stay in frame: camera must say {LOCKED}")
        if not isinstance(sc.get("props", []), list):
            errors.append(f"{w}: props must be a list")
        refs = sc.get("refs")
        if not isinstance(refs, list) or not refs or any(r not in ROLES for r in refs):
            errors.append(f"{w}: refs must be a non-empty list of {ROLES}")
        if sc.get("transition", "cut") not in TRANSITIONS:
            errors.append(f"{w}: transition must be one of {sorted(TRANSITIONS)}")
        perf = sc.get("performance")
        if not isinstance(perf, list) or not (1 <= len(perf) <= 8):
            errors.append(f"{w}: performance must be a list of 1 to 8 steps"); continue
        spoken, speakers, asked = 0, set(), prev_last_line.rstrip().endswith("?")
        for j, st in enumerate(perf):
            pw = f"{w} step {j + 1}"
            if not isinstance(st, dict) or not isinstance(st.get("how"), str) or not st["how"].strip():
                errors.append(f"{pw}: needs a non-empty 'how'"); continue
            if st.get("who") is not None and st["who"] not in SPEAKERS:
                errors.append(f"{pw}: who must be one of {sorted(SPEAKERS)} or null")
            _check_text(pw, st["how"], banned_names, errors)
            line = st.get("line")
            if line is None and any(_has_word(st["how"], v) for v in SILENT_VERBS):
                errors.append(f"{pw}: a silent step must not speak ('{st['how']}')")
            if line is not None:
                speakers.add(st.get("who"))
                if not isinstance(line, str) or not line.strip():
                    errors.append(f"{pw}: line must be a non-empty string or null"); continue
                if '"' in line:
                    errors.append(f"{pw}: line must not contain double quotes")
                n = _words(line)
                spoken += n
                if n > MAX_LINE_WORDS:
                    errors.append(f"{pw}: line has {n} words (max {MAX_LINE_WORDS}): {line!r}")
                if _bare_answer(line) and not asked:
                    errors.append(f"{pw}: '{line}' answers a question nobody asked (put the question on screen first)")
                asked = line.rstrip().endswith("?")
                prev_last_line = line
                _check_text(pw, line, banned_names, errors, dialogue=True)
        if len(speakers) != 1 or not speakers <= set(CHARACTERS):
            errors.append(f"{w}: exactly one on-screen speaker per scene (a cast member), got {sorted(map(str, speakers))}")
        if spoken > secs * WORDS_PER_SECOND:
            errors.append(f"{w}: {spoken} spoken words won't fit {secs} s (max {secs * WORDS_PER_SECOND})")
    return errors


# ---------------------------------------------------------------- the brief + Gemini writer
def make_brief(business_name, business_type, owner, rival, regular, hero_1, hero_2, tone, model, source):
    preset = source.split(":", 1)[1].strip() if source.startswith("preset:") else None
    p = load_preset(preset) if preset else {}
    pc = p.get("cast", {})
    cast = {"owner": owner.strip() or pc.get("owner", ""), "rival": rival.strip() or pc.get("rival", ""),
            "regular": regular.strip() or pc.get("regular", ""), "hero1": hero_1.strip() or pc.get("hero1", ""),
            "hero2": hero_2.strip() or pc.get("hero2", "")}
    if not cast["hero1"] or not cast["hero2"]:   # the agency duo is the same in every episode
        d = load_preset(list_presets()[0])["cast"] if list_presets() else {}
        cast["hero1"] = cast["hero1"] or d.get("hero1", "")
        cast["hero2"] = cast["hero2"] or d.get("hero2", "")
    for k, v in cast.items():
        for n in real_names_in(v):
            raise ValueError(f"The {k} description contains a real person's name ('{n}'). Describe looks, not names.")
    btype = business_type.strip() or p.get("business_type", "")
    if not preset and not btype:
        raise ValueError("Please say what kind of business it is (e.g. 'barber shop'), or pick a preset.")
    return {"business_name": business_name.strip() or p.get("business_name", "Your Business"), "business_type": btype or "small business",
            "cast": cast, "tone": tone if tone in TONES else "funny", "model": model, "preset": preset}


def writer_prompt(brief):
    ex = load_preset("barber-shop") if "barber-shop" in list_presets() else (load_preset(list_presets()[0]) if list_presets() else {})
    beats = "\n".join(f"{n}. {name}" for n, name in BEATS)
    slots = "\n".join(f'- "{k}": {v}' for k, v in SLOTS.items())
    return f"""You fill in an underdog sitcom for one small business. The story is fixed; you only supply the business-specific details.

Business: {brief['business_name']} ({brief['business_type']}). Tone: {brief['tone']} ({TONES[brief['tone']]})
The fixed arc ({len(BEATS)} scenes): a flashy fictional rival chain opens across the street with an influencer vlogging; six months
later the regulars drift to the rival and one loyal regular stays; the owner's old car breaks down and they can't pay the fix, so they
walk; an ad-agency duo arrives, pitches bad ideas, finds the heart (a family heirloom); their video goes viral and the line comes
back; the owner puts the rival in their place and the rival closes; six months later the owner earns a prize car; the out-of-work
influencer asks for a job and gets "Hmm. No."
Beats: {beats}

Reply with JSON only, exactly this shape:
{{"title": "...", "cast": {{"owner": "...", "rival": "...", "regular": "..."}}, "slots": {{ ...every key below... }}}}
- "cast": what each person LOOKS like, one line each, no names (the owner, the rival influencer, the loyal regular).
- "slots" keys:
{slots}
Rules: everything must fit a {brief['business_type']}, not a bakery. Spoken LINE slots are at most {MAX_LINE_WORDS} words, short and natural;
not a joke on every line. No person's name anywhere. No real brands, logos, products, apps or car makers; the rival brand is invented
and must not resemble a real chain. The prize car is an original design with no badges. You may use {{hero1}} and {{hero2}} inside
"taste_setup". Never use double quotes inside a value.
Example for a barber shop (write your own for this business):
{json.dumps({"title": ex.get("title", ""), "cast": {k: ex.get("cast", {}).get(k, "") for k in ("owner", "rival", "regular")}, "slots": ex.get("slots", {})}, indent=1)}
"""


def parse_reply(text):
    """Gemini's reply -> {"title", "cast", "slots"}. Tolerates code fences and chatter around the JSON."""
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    a, b = t.find("{"), t.rfind("}")
    try:
        data = json.loads(t[a:b + 1]) if 0 <= a < b else None
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("slots"), dict):
        raise ValueError("Gemini's reply had no readable slots JSON. Run again (or pick a preset).")
    return {"title": data.get("title", ""), "cast": data.get("cast", {}) or {}, "slots": data["slots"]}


# ---------------------------------------------------------------- rendering prompts
def story_from_preset(name):
    p = load_preset(name)
    return {"title": p.get("title", ""), "cast": p.get("cast", {}), "slots": p["slots"], "cast_names": p.get("cast_names", [])}


def build_script(brief, story):
    """story = {"title", "slots", "cast"?}. Check the slots, fill the arc, check the script, render every prompt.
    Raises ValueError on any problem, before anything is generated."""
    errs = check_slots(story.get("slots"))
    if errs:
        raise ValueError("The business details broke the rules:\n- " + "\n- ".join(errs[:20]))
    cast = dict(brief["cast"])
    for k, v in (story.get("cast") or {}).items():
        if k in cast and not cast[k] and isinstance(v, str):
            cast[k] = v.strip()
    for k in CHARACTERS:
        if not cast.get(k):
            raise ValueError(f"Please describe the {k} (what they look like, not their name).")
        for n in real_names_in(cast[k]):
            raise ValueError(f"The {k} description contains a real person's name ('{n}').")
    brief = dict(brief, cast=cast)
    banned = set()
    for p in list_presets():
        banned |= {n.lower() for n in load_preset(p).get("cast_names", [])}
    raw = {"title": story.get("title", ""), "scenes": arc_scenes(story["slots"])}
    errs = validate_script(raw, banned)
    if errs:
        raise ValueError("The script broke the rules:\n- " + "\n- ".join(errs[:20]))
    scenes = []
    for sc in raw["scenes"]:
        steps = []
        for st in sc["performance"]:
            s = _fill_cast(st["how"], brief)
            if st.get("who") in CHARACTERS:
                s = _fill_cast("{" + st["who"] + "} ", brief) + s
            s = _cap(s)
            steps.append(f'{s}: "{st["line"]}"' if st.get("line") else s.rstrip(".") + ".")
        speaker = next(st["who"] for st in sc["performance"] if st.get("line"))
        only = (f"Only {_fill_cast('{' + speaker + '}', brief)} speaks in this shot; everyone else stays silent with mouth closed and "
                "no lip movement. No new people enter the frame.")
        props = [_fill_cast(p, brief) for p in sc["props"]]
        keep = f"Visible from the first frame and staying in place: {'; '.join(props)}." if props else ""
        state = _sentence_case(_fill_cast(sc.get("state") or "", brief))
        motion = " ".join(x for x in [f"Animate this start frame: {_cap(_fill_cast(sc['camera'], brief)).rstrip('.')}.", state] + steps +
                          [only, keep, f"Ambience bed: {_fill_cast(sc['ambience'], brief).rstrip('.')}.",
                           _cap(_fill_cast(sc["music"], brief).rstrip(".")) + ".", TONES[brief["tone"]], MOTION_TAIL] if x)
        motion = _sentence_case(motion)
        body = _sentence_case(_fill_cast(sc["keyframe"], brief))
        if state:
            body += " " + state
        if sc["landmark"]:
            body += f" {LOCKED} framing: the rival's storefront and sign are clearly in frame."
        if props:
            body += f" In the frame: {'; '.join(props)}."
        scenes.append({"beat": sc["beat"], "name": sc["name"], "seconds": sc["seconds"], "card": sc["card"], "landmark": sc["landmark"],
                       "views": sc["views"], "dm": sc["dm"], "keyframe_body": body, "motion_prompt": motion, "refs": sc["refs"][:MAX_REFS],
                       "state": state,
                       "speaker": speaker, "captions": [st["line"] for st in sc["performance"] if st.get("line")],
                       "transition": sc["transition"]})
        for k in ("keyframe_body", "motion_prompt"):   # descriptions typed by the user are checked once filled in
            for n in real_names_in(scenes[-1][k]):
                raise ValueError(f"scene {sc['beat']}: a real person's name ('{n}') ended up in the prompt")
    slots = dict(SLOT_DEFAULTS, **story["slots"])
    labels = {r: _sentence_free(_fill_cast(_fill_slots(REF_LABEL[r], slots), brief)) for r in ROLES}
    return {"title": story.get("title") or "An Underdog Story", "brief": brief, "scenes": scenes, "ref_labels": labels,
            "overlay": {"rival_brand": slots["rival_brand"], "dm_business": slots["dm_business"], "business_name": brief["business_name"]}}


REF_LABEL = {"owner": "the character sheet of {owner}", "rival": "the character sheet of {rival}",
             "regular": "the character sheet of {regular}", "hero1": "the character sheet of {hero1}",
             "hero2": "the character sheet of {hero2}", "location": "the location ({place})",
             "rival_store_open": 'the rival\'s storefront "{rival_brand}", OPEN',
             "rival_store_closed": 'the same rival storefront "{rival_brand}", CLOSED (dark, shutter down, FOR LEASE, no banner)',
             "old_car": "the owner's old car ({old_car}), normal and broken down",
             "prize_car": "the prize car ({payoff})"}


def _sentence_free(s):
    return re.sub(r"\s+", " ", s).strip()


def keyframe_prompt(script, scene_idx, present_refs):
    """present_refs: the roles whose reference image is really attached, in the order they are sent."""
    sc = script["scenes"][scene_idx]
    legend = ""
    if present_refs:
        labels = script.get("ref_labels") or {}
        legend = " Reference images, in order: " + "; ".join(
            f"{k + 1}) {labels.get(r) or _fill_cast(REF_LABEL[r], script['brief'])}" for k, r in enumerate(present_refs)) + "."
    return f"{KEYFRAME_HEAD}{legend}\n{sc['keyframe_body']}"


def script_text(script):
    lines = [f"{script['brief']['business_name']}: {script.get('title') or 'Underdog Story'}"]
    for sc in script["scenes"]:
        if sc.get("card"):
            lines.append(f"\n    [{sc['card']}]")
        lines.append(f"\n{sc['beat']:>2}. {sc['name'].upper()} ({sc['seconds']} s, {sc['speaker']})")
        lines += [f'    "{c}"' for c in sc["captions"]]
    return "\n".join(lines)


def film_seconds(script, end_secs=3.0):
    """Expected film length: scene takes minus the dissolve overlaps plus the end card."""
    t = 0.0
    for k, sc in enumerate(script["scenes"]):
        t += sc["seconds"] - TRANSITIONS[sc["transition"]][1]
    return round(t + end_secs, 2)


# ---------------------------------------------------------------- media helpers
def _ff():
    return shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg", shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"


def probe(path):
    _, fp = _ff()
    out = json.loads(subprocess.check_output([fp, "-v", "error", "-show_streams", "-of", "json", str(path)]))
    v = next(s for s in out["streams"] if s["codec_type"] == "video")
    dur = float(v.get("duration") or json.loads(subprocess.check_output(
        [fp, "-v", "error", "-show_format", "-of", "json", str(path)]))["format"]["duration"])
    return {"w": int(v["width"]), "h": int(v["height"]), "dur": dur, "audio": any(s["codec_type"] == "audio" for s in out["streams"])}


def _font(size):
    try:
        return ImageFont.truetype(str(FONT), size)
    except OSError:
        return ImageFont.load_default(size)


def _wrap(d, txt, f, width):
    lines, cur = [], ""
    for wd in txt.split():
        trial = (cur + " " + wd).strip()
        if d.textlength(trial, font=f) > width and cur:
            lines.append(cur); cur = wd
        else:
            cur = trial
    return lines + [cur]


def text_png(path, txt, size, w, pad=40):
    f = _font(size)
    d = ImageDraw.Draw(Image.new("RGBA", (w, 10)))
    lines = _wrap(d, txt, f, w - 2 * pad)
    img = Image.new("RGBA", (w, int(size * 1.25 * len(lines)) + 12), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    for k, ln in enumerate(lines):
        d.text(((w - d.textlength(ln, font=f)) / 2, k * size * 1.25), ln, font=f, fill="white",
               stroke_width=max(2, size // 12), stroke_fill="black")
    img.save(path)


def card_png(path, txt, size, pad=22, bg=(0, 0, 0, 150)):
    """The v9 title card / view counter: white text on a translucent block."""
    f = _font(size)
    w = int(ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(txt, font=f))
    im = Image.new("RGBA", (w + 2 * pad, size + 2 * pad), bg)
    ImageDraw.Draw(im).text((pad, pad - size // 8), txt, font=f, fill="white")
    im.save(path)


def dm_png(path, lines, scale=1.0):
    """The next-episode DM: a message bubble from another business. lines = [from, message..., tag]."""
    s = scale
    W, H = int(660 * s), int(230 * s)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, W - 1, H - 1), int(34 * s), fill=(250, 248, 244, 245))
    d.ellipse((int(26 * s), int(30 * s), int(86 * s), int(90 * s)), fill=(232, 140, 70))
    x, avail = int(106 * s), W - int(106 * s) - int(20 * s)
    d.text((x, int(26 * s)), lines[0], font=_font(int(28 * s)), fill=(30, 30, 30))
    y = int(66 * s)
    for ln in lines[1:-1]:
        size = int(32 * s)
        while d.textlength(ln, font=_font(size)) > avail and size > 14:
            size -= 1
        d.text((x, y), ln, font=_font(size), fill=(20, 20, 20)); y += int(40 * s)
    d.text((x, int(160 * s)), lines[-1], font=_font(int(28 * s)), fill=(190, 110, 50))
    im.save(path)


def caption_cues(lines, start, dur, lead=0.3, tail=1.0):
    """Spread a scene's spoken lines over its take, in proportion to their length. Dialogue ends 1 s before the take does."""
    if not lines:
        return []
    span = max(0.5, dur - lead - tail)
    weights = [max(1, _words(t)) for t in lines]
    tot, t, cues = sum(weights), start + lead, []
    for txt, wgt in zip(lines, weights):
        d = span * wgt / tot
        cues.append((round(t, 3), round(t + d, 3), txt)); t += d
    return cues


def cut_lint(clip, td, noise_db=-35):
    """No cut inside a word: is the audio under the last td seconds (where the dissolve starts) quiet? Returns True when quiet."""
    ffmpeg, _ = _ff()
    dur = probe(clip)["dur"]
    if td < 0.1:
        return True
    r = subprocess.run([ffmpeg, "-hide_banner", "-ss", f"{max(0, dur - td):.3f}", "-i", str(clip), "-af",
                        f"silencedetect=n={noise_db}dB:d={max(0.05, td * 0.8):.3f}", "-f", "null", "-"], capture_output=True, text=True)
    return "silence_start" in r.stderr


# ---------------------------------------------------------------- the $0 draft animatic (no generation)
def draft_frame(path, scene, script, bg=None, W=720, H=1280):
    """One storyboard card for a scene: the reference image (or a warm gradient), the beat, the shot and the spoken lines."""
    if bg is not None:
        im = bg.convert("RGB")
        r = max(W / im.width, H / im.height)
        im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1), Image.LANCZOS)
        im = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H))
        im = Image.blend(im.filter(ImageFilter.GaussianBlur(6)), Image.new("RGB", (W, H), (20, 16, 14)), 0.55)
    else:
        im = Image.new("RGB", (W, H))
        px = ImageDraw.Draw(im)
        for y in range(H):
            k = y / H
            px.line([(0, y), (W, y)], fill=(int(70 - 40 * k), int(52 - 30 * k), int(44 - 26 * k)))
    d = ImageDraw.Draw(im)
    s = W / 720
    d.text((int(40 * s), int(120 * s)), f"BEAT {scene['beat']} · {scene['name'].upper()}", font=_font(int(30 * s)), fill=(244, 200, 140))
    y = int(170 * s)
    body = re.sub(r"\s+", " ", scene["keyframe_body"])[:330] + ("…" if len(scene["keyframe_body"]) > 330 else "")
    for ln in _wrap(d, body, _font(int(22 * s)), W - int(80 * s)):
        d.text((int(40 * s), y), ln, font=_font(int(22 * s)), fill=(230, 222, 210)); y += int(30 * s)
    y = max(y + int(30 * s), int(H * 0.52))
    who = script["brief"]["cast"].get(scene["speaker"], scene["speaker"])
    for ln in _wrap(d, who, _font(int(22 * s)), W - int(80 * s)):
        d.text((int(40 * s), y), ln, font=_font(int(22 * s)), fill=(244, 200, 140)); y += int(30 * s)
    y += int(8 * s)
    for c in scene["captions"]:
        for ln in _wrap(d, f"“{c}”", _font(int(38 * s)), W - int(80 * s)):
            d.text((int(40 * s), y), ln, font=_font(int(38 * s)), fill="white"); y += int(50 * s)
    d.text((int(40 * s), H - int(90 * s)), "DRAFT · storyboard only · $0", font=_font(int(20 * s)), fill=(200, 190, 175))
    im.save(path)


def draft_clip(out, scene, script, bg=None, W=720, H=1280, fps=24):
    """A scene-length animatic clip with a slow push-in and a quiet ambience bed (brown noise). Free, CPU only."""
    ffmpeg, _ = _ff()
    out = Path(out)
    png = out.with_suffix(".png")
    draft_frame(png, scene, script, bg, W, H)
    secs = scene["seconds"]
    n = int(secs * fps)
    vf = (f"scale={W * 2}:{H * 2},zoompan=z='1+0.04*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps={fps},"
          "format=yuv420p")
    subprocess.run([ffmpeg, "-v", "error", "-y", "-loop", "1", "-framerate", str(fps), "-t", f"{secs}", "-i", str(png),
                    "-f", "lavfi", "-t", f"{secs}", "-i", "anoisesrc=color=brown:amplitude=0.03:sample_rate=48000",
                    "-vf", vf, "-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-ac", "2",
                    "-shortest", str(out)], check=True)
    return out


# ---------------------------------------------------------------- final cut: the v9 recipe
def finish(clips, scenes, out, work, end_lines, overlay=None, ai_label=True, credit=True, end_secs=3.0, fps=24):
    """clips: mp4 paths in order; scenes: the matching rendered scenes (captions, transition, card, views, dm).
    Dissolves (video + audio), the title cards, the view counter, the next-episode DM, captions, the AI label and an end card.
    The audio is the scenes' own dialogue and sound, not yet mastered: score_mix() adds the score and masters. Returns a receipt."""
    ffmpeg, _ = _ff()
    overlay = overlay or {}
    work = Path(work); ov = work / "ov"; ov.mkdir(parents=True, exist_ok=True)
    info = [probe(c) for c in clips]
    W, H = info[0]["w"] - info[0]["w"] % 2, info[0]["h"] - info[0]["h"] % 2
    s = W / 720
    dur = [i["dur"] for i in info]
    trans = []
    for k, sc in enumerate(scenes):
        name, td = TRANSITIONS.get(sc.get("transition", "dissolve"), TRANSITIONS["dissolve"])
        trans.append((name, min(td, dur[k] / 3, (dur[k + 1] / 3) if k + 1 < len(dur) else end_secs / 3)))
    starts, t = [], 0.0
    for d, (_, td) in zip(dur, trans):
        starts.append(t); t += d - td
    end_start = t
    total = end_start + end_secs
    lint = [{"scene": k + 1, "dissolve": round(td, 3), "quiet_tail": cut_lint(clips[k], td)} for k, (_, td) in enumerate(trans)]
    cues = []
    for k, sc in enumerate(scenes):
        cues += caption_cues(sc.get("captions", []), starts[k], dur[k] - trans[k][1])
    cap_size = max(28, W // 16)
    for k, (_, _, txt) in enumerate(cues):
        text_png(ov / f"cap{k:02d}.png", txt, cap_size, W)
    ovl = []   # (png, x, y, start, end, kind, text)
    for k, sc in enumerate(scenes):
        if sc.get("card"):
            p = ov / f"card{k:02d}.png"; card_png(p, sc["card"], int(46 * s))
            ovl.append((p, "(W-w)/2", int(200 * H / 1280), starts[k], starts[k] + min(2.2, dur[k] * 0.6), "card", sc["card"]))
        if sc.get("views"):
            marks = [0.15, 0.38, 0.62, 0.94]
            for j, v in enumerate(["1,204 views", "48K views", "2.1M views"]):
                p = ov / f"views{k:02d}_{j}.png"; card_png(p, v, int(40 * s), bg=(200, 40, 60, 220))
                ovl.append((p, "(W-w)/2", int(260 * H / 1280), starts[k] + marks[j] * dur[k], starts[k] + marks[j + 1] * dur[k], "views", v))
    if any(sc.get("dm") for sc in scenes) and overlay.get("rival_brand"):
        lines = ["New message", f"Help. A {overlay['rival_brand']} just opened", f"next to my {overlay.get('dm_business', 'shop')}.", "Episode 2"]
        p = ov / "dm.png"; dm_png(p, lines, s)
        ovl.append((p, "(W-w)/2", int(150 * H / 1280), max(0.0, end_start - 3.2), total, "dm", " / ".join(lines)))
    if ai_label:
        f = _font(max(16, W // 34)); tw = int(ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength("AI-generated", font=f))
        lab = Image.new("RGBA", (tw + 24, max(16, W // 34) + 18), (0, 0, 0, 110))
        ImageDraw.Draw(lab).text((12, 7), "AI-generated", font=f, fill="white"); lab.save(ov / "ai.png")
    card = Image.new("RGB", (W, H), (24, 20, 18)); d = ImageDraw.Draw(card)
    rows = [(end_lines[0], W // 12, .40)] + [(ln, W // 20, .40 + .07 * (k + 1)) for k, ln in enumerate(end_lines[1:])]
    rows.append(("AI-generated animation", W // 30, .86))
    if credit:
        rows.append(("made with Underdog Story for ComfyUI", W // 36, .90))
    for txt, size, y in rows:
        fo = _font(size)
        if d.textlength(txt, font=fo) > W * .9:
            fo = _font(int(size * W * .9 / d.textlength(txt, font=fo)))
        d.text(((W - d.textlength(txt, font=fo)) / 2, H * y), txt, font=fo, fill=(244, 234, 220))
    card.save(ov / "endcard.png")

    inp, fc, n = [], [], len(clips)
    for c in clips:
        inp += ["-i", str(c)]
    inp += ["-loop", "1", "-t", f"{end_secs}", "-i", str(ov / "endcard.png"),
            "-f", "lavfi", "-t", f"{max(dur) + end_secs}", "-i", "anullsrc=r=48000:cl=stereo"]
    silent = n + 1
    for i in range(n):
        fc.append(f"[{i}:v]fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,format=yuv420p,"
                  f"settb=AVTB,setpts=PTS-STARTPTS[v{i}]")
        src = f"[{i}:a]"
        if not info[i]["audio"]:
            fc.append(f"[{silent}:a]atrim=0:{dur[i]:.3f}[s{i}]"); src = f"[s{i}]"
        fc.append(f"{src}aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,apad,atrim=0:{dur[i]:.3f},asetpts=PTS-STARTPTS[a{i}]")
    fc.append(f"[{n}:v]fps={fps},scale={W}:{H},format=yuv420p,setsar=1,settb=AVTB,setpts=PTS-STARTPTS[v{n}]")
    fc.append(f"[{silent}:a]atrim=0:{end_secs},aformat=sample_fmts=fltp:channel_layouts=stereo,asetpts=PTS-STARTPTS[a{n}]")
    vprev, aprev = "v0", "a0"
    for i in range(1, n + 1):
        name, td = trans[i - 1]
        off = starts[i] if i < n else end_start
        fc.append(f"[{vprev}][v{i}]xfade=transition={name}:duration={td:.3f}:offset={off:.3f}[x{i}]")
        fc.append(f"[{aprev}][a{i}]acrossfade=d={td:.3f}:c1=tri:c2=tri[y{i}]")
        vprev, aprev = f"x{i}", f"y{i}"
    base, idx, extra = vprev, n + 2, []
    if ai_label:
        extra += ["-i", str(ov / "ai.png")]
        fc.append(f"[{base}][{idx}:v]overlay=24:24:enable='lt(t,{end_start:.3f})'[o0]"); base = "o0"; idx += 1
    for k, (p, x, y, a, b, _, _) in enumerate(ovl):
        extra += ["-i", str(p)]
        fc.append(f"[{base}][{idx}:v]overlay={x}:{y}:enable='between(t,{a:.3f},{b:.3f})'[g{k}]"); base = f"g{k}"; idx += 1
    for k, (a, b, _) in enumerate(cues):
        extra += ["-i", str(ov / f"cap{k:02d}.png")]
        fc.append(f"[{base}][{idx}:v]overlay=(W-w)/2:H*0.74:enable='between(t,{a:.3f},{b:.3f})'[c{k}]"); base = f"c{k}"; idx += 1
    fc.append(f"[{aprev}]aresample=48000[aout]")
    cmd = [ffmpeg, "-v", "error", "-y"] + inp + extra + ["-filter_complex", ";".join(fc), "-map", f"[{base}]", "-map", "[aout]",
           "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", str(out)]
    (work / "ffmpeg_cmd.txt").write_text(" ".join(cmd))
    subprocess.run(cmd, check=True)
    receipt = {"starts": starts, "end_start": end_start, "total": total, "size": [W, H], "transitions": trans, "cues": cues,
               "overlays": [{"kind": k, "text": tx, "start": round(a, 3), "end": round(b, 3)} for (_, _, _, a, b, k, tx) in ovl],
               "cut_lint": lint}
    (work / "receipt.json").write_text(json.dumps(receipt, indent=1))
    return receipt


# ---------------------------------------------------------------- score mix: level, duck, master
MUSIC_LEVEL = "loudnorm=I=-27:LRA=3:TP=-6"
DUCK = "sidechaincompress=threshold=0.02:ratio=12:attack=40:release=450"
MASTER = "loudnorm=I=-14:TP=-1:LRA=11"


def write_wav(path, waveform, sample_rate):
    """A ComfyUI AUDIO waveform (torch or numpy, [batch, channels, samples] or [channels, samples]) -> 16-bit PCM WAV."""
    import numpy as np
    a = waveform.detach().cpu().float().numpy() if hasattr(waveform, "detach") else np.asarray(waveform, dtype="float32")
    if a.ndim == 3:
        a = a[0]
    if a.ndim == 1:
        a = a[None]
    pcm = (np.clip(a.T, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(pcm.shape[1]); w.setsampwidth(2); w.setframerate(int(sample_rate)); w.writeframes(pcm.tobytes())
    return Path(path)


def score_mix(video, out, work, music=None, fade=2.0):
    """The v9 mix. With a score: the score is levelled first (-27 LUFS, narrow range), faded out, then ducked under the
    dialogue with a sidechain compressor keyed by the dialogue, and mixed. Then the whole film is mastered to -14 LUFS / -1 dBTP.
    Without a score the dialogue is mastered alone. The picture is copied untouched."""
    ffmpeg, _ = _ff()
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    total = probe(video)["dur"]
    fmt = "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"
    if music:
        fc = (f"[0:a]{fmt},asplit[dia][key];"
              f"[1:a]{fmt},apad,atrim=0:{total:.3f},asetpts=PTS-STARTPTS,{MUSIC_LEVEL},{fmt},"
              f"afade=t=out:st={max(0.0, total - fade):.3f}:d={fade}[mus];"
              f"[mus][key]{DUCK}[duck];[dia]volume=0.85[dia2];[dia2][duck]amix=inputs=2:duration=first:normalize=0[mix];"
              f"[mix]{MASTER},aresample=48000[aout]")
        inp = ["-i", str(video), "-i", str(music)]
    else:
        fc = f"[0:a]{fmt},{MASTER},aresample=48000[aout]"
        inp = ["-i", str(video)]
    cmd = [ffmpeg, "-v", "error", "-y"] + inp + ["-filter_complex", fc, "-map", "0:v", "-map", "[aout]", "-c:v", "copy",
                                                 "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    (work / "mix_cmd.txt").write_text(" ".join(cmd))
    subprocess.run(cmd, check=True)
    return {"music": str(music) if music else None, "filter": fc, "total": total}
