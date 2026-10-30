import copy, hashlib, json, re
import pytest
import underdog_core as core

FAKE_REAL = "Zorbleton"   # stands in for a real person's name in these tests (the repo holds no real names)
PRESETS = ["barber-shop", "nail-salon", "small-business-rescue-bakery", "taco-truck"]
BAKERY = "small-business-rescue-bakery"
BANNED = {"rosa", "chad", "marco"}


@pytest.fixture(autouse=True)
def fake_real_name(monkeypatch):
    monkeypatch.setattr(core, "REAL_NAME_SHA256", core.REAL_NAME_SHA256 | {hashlib.sha256(FAKE_REAL.lower().encode()).hexdigest()})


def brief(preset=BAKERY, source=None, tone="funny", **cast):
    c = {k: cast.get(k, "") for k in ("owner", "rival", "regular", "hero1", "hero2")}
    return core.make_brief("", "", c["owner"], c["rival"], c["regular"], c["hero1"], c["hero2"], tone, "veo-3.1-lite",
                           source or f"preset: {preset}")


def script(preset=BAKERY, **kw):
    return core.build_script(brief(preset, **kw), core.story_from_preset(preset))


def raw(preset=BAKERY):
    return {"title": "", "scenes": core.arc_scenes(core.load_preset(preset)["slots"])}


def all_text(s):
    out = [s["title"], json.dumps(s["overlay"])]
    for i, sc in enumerate(s["scenes"]):
        out += [core.keyframe_prompt(s, i, sc["refs"]), sc["motion_prompt"]] + sc["captions"] + [sc.get("card") or ""]
    return "\n".join(out)


def test_presets_are_the_four_businesses():
    assert core.list_presets() == PRESETS
    assert len(core.ARC) == 15 and [b for b, _ in core.BEATS] == list(range(1, 16))


@pytest.mark.parametrize("preset", PRESETS)
def test_every_preset_passes_the_script_checks(preset):
    assert core.check_slots(core.load_preset(preset)["slots"]) == []
    assert core.validate_script(raw(preset), BANNED) == []
    s = script(preset)
    assert len(s["scenes"]) == 15 and s["title"] == core.load_preset(preset)["title"]
    for sc in s["scenes"]:
        assert sum(core._words(c) for c in sc["captions"]) <= sc["seconds"] * core.WORDS_PER_SECOND
        assert all(core._words(c) <= core.MAX_LINE_WORDS for c in sc["captions"])
        assert sc["seconds"] in core.VEO_SECONDS


@pytest.mark.parametrize("preset", [p for p in PRESETS if p != BAKERY])
def test_no_bakery_words_leak_into_other_businesses(preset):
    text = all_text(script(preset))
    assert core.bakery_words_in(text) == [], core.bakery_words_in(text)
    assert core.load_preset(preset)["slots"]["rival_brand"] in text


def test_the_arc_template_itself_has_no_bakery_words():
    for a in core.ARC:
        blob = json.dumps(a)
        assert core.bakery_words_in(blob) == [], (a["name"], core.bakery_words_in(blob))
    assert core.bakery_words_in(json.dumps(core.SLOT_DEFAULTS)) == []


def test_bakery_preset_is_the_v9_story():
    s = script(BAKERY)
    lines = [(sc["beat"], sc["speaker"], c) for sc in s["scenes"] for c in sc["captions"]]
    flat = [c for _, _, c in lines]
    for want in ["What's up, everybody! MEGABUN is officially OPEN!", "Sorry, little bakery.", "Best croissants in town, Rosa! Don't you ever change.",
                 "Not today... please, not today.", "Last one. On the house.", "...No. This should have a line around the block.",
                 "Can we film you?", "Abuela's recipe. Forty years.", "Don't look at us. Look at the dough.", "Okay, okay... ONE treat.",
                 "So... you hiring?", "Hmm. No."]:
        assert want in flat, want
    assert [sc["card"] for sc in s["scenes"] if sc["card"]] == ["SIX MONTHS LATER", "NEXT MORNING", "SIX MONTHS LATER"]
    assert s["overlay"] == {"rival_brand": "MEGABUN", "dm_business": "taco truck", "business_name": "Abuela's Bakery"}


def test_arc_order_cause_before_effect():
    names = [n for _, n in core.BEATS]
    order = lambda n: names.index(n)
    assert order("grand opening") < order("the drift") < order("the low point") < order("strangers") < order("bad ideas")
    assert order("strangers") < order("bad ideas")            # the offer comes before the taste
    assert order("going viral") < order("the line comes back") < order("the showdown") < order("the payoff")   # earned payoff
    assert order("the ask") + 1 == order("the last laugh")    # the question is on screen right before 'Hmm. No.'
    assert [a["name"] for a in core.ARC if a.get("views")] == ["going viral"] and core.ARC[-1].get("dm")


@pytest.mark.parametrize("preset", PRESETS)
def test_prompt_rules_are_baked_in(preset):
    s = script(preset)
    brand = core.load_preset(preset)["slots"]["rival_brand"]
    for i, sc in enumerate(s["scenes"]):
        mp, kp = sc["motion_prompt"], core.keyframe_prompt(s, i, sc["refs"])
        assert mp.endswith(core.MOTION_TAIL) and "One continuous take, no cuts." in mp
        assert "Background life" in mp and "nobody in the background freezes" in mp           # background life
        assert "No object, prop or furniture appears or disappears" in mp                     # prop continuity
        assert "Visible from the first frame and staying in place" in mp
        assert "no crowd files out through a door" in mp                                      # no crowds through doors
        assert "All dialogue ends at least one second before the end of the take" in mp       # no cut inside a word
        assert "Ambience bed:" in mp
        assert f"Only {s['brief']['cast'][sc['speaker']]} speaks in this shot" in mp
        assert all(f'"{c}"' in mp for c in sc["captions"])
        if sc["landmark"]:
            assert mp.startswith(f"Animate this start frame: {core.LOCKED}") and f'"{brand}" storefront stays visible' in mp
            assert core.LOCKED in kp
        else:
            assert core.LOCKED not in mp
        for text in (kp, core._outside_quotes(mp)):
            assert "{" not in text, "all placeholders filled"
            for n in BANNED:
                assert not core._has_word(text, n), (i, n)
            assert core.real_names_in(text) == []
            for b in core.BRANDS:
                assert not core._has_word(text, b), (i, b)
    assert [sc["beat"] for sc in s["scenes"] if sc["landmark"]] == [1, 3, 10, 11, 12]


def test_keyframe_legend_lists_only_attached_sheets():
    s = script("barber-shop")
    kp = core.keyframe_prompt(s, 0, ["rival", "rival_store_open"])
    assert "1) the character sheet of the young influencer" in kp and '2) the rival\'s storefront "MEGAFADE", OPEN' in kp and "3)" not in kp
    assert "Reference images" not in core.keyframe_prompt(s, 0, [])


def test_form_cast_overrides_the_preset_and_tone():
    s = script("taco-truck", owner="the cook in a green cap", tone="heartfelt")
    assert s["brief"]["cast"]["owner"] == "the cook in a green cap" and "the cook in a green cap" in s["scenes"][0]["motion_prompt"].lower()
    assert core.TONES["heartfelt"] in s["scenes"][0]["motion_prompt"]
    assert s["brief"]["business_name"] == "La Esquina Tacos"


@pytest.mark.parametrize("breakit, msg", [
    (lambda r: r["scenes"].pop(), "exactly 15 scenes"),
    (lambda r: r["scenes"][0]["performance"][0].update(line=" ".join(["word"] * 21)), "21 words"),
    (lambda r: r["scenes"][1]["performance"].append({"who": "regular", "how": "adds", "line": " ".join(["la"] * 20)}), "won't fit 6 s"),
    (lambda r: r["scenes"][2].update(keyframe="Rosa stands at the counter."), "character name 'rosa'"),
    (lambda r: r["scenes"][3]["performance"][0].update(line="Hey Zorbleton, look!"), "real person's name 'Zorbleton'"),
    (lambda r: r["scenes"][12].update(keyframe="A red Ferrari at the curb."), "brand name 'ferrari'"),
    (lambda r: r["scenes"][4].update(keyframe="{villain} laughs."), "unknown placeholder"),
    (lambda r: r["scenes"][5].update(refs=["owner", "dog"]), "refs must be"),
    (lambda r: r["scenes"][6]["performance"][0].update(who="narrator"), "who must be"),
    (lambda r: r["scenes"][7].update(beat=3), "beat must be 8"),
    (lambda r: r["scenes"][8].update(transition="spin"), "transition must be"),
    (lambda r: r["scenes"][9]["performance"][0].update(line='He said "hi"'), "double quotes"),
    (lambda r: r["scenes"][2]["performance"][1].update(line="Every day."), "exactly one on-screen speaker"),
    (lambda r: r["scenes"][1]["performance"][1].update(how="smiles and says nothing back"), "silent step must not speak"),
    (lambda r: r["scenes"][9].update(camera="slow pan across the street"), "LOCKED-OFF STATIC CAMERA"),
    (lambda r: r["scenes"][2].update(keyframe="The customers follow him straight out the door."), "crowd exits through a door"),
    (lambda r: r["scenes"][1].update(keyframe="Six months later, the shop is empty."), "without a title card"),
    (lambda r: r["scenes"][2].update(card="LATER THAT YEAR"), "title card must be one of"),
    (lambda r: r["scenes"][4]["performance"][0].update(line="Six."), "answers a question nobody asked"),
    (lambda r: r["scenes"][13]["performance"][0].update(line="So, you hiring now."), "answers a question nobody asked"),
    (lambda r: r["scenes"][0].update(seconds=5), "seconds must be one of"),
])
def test_validator_rejects(breakit, msg):
    r = raw()
    breakit(r)
    errs = core.validate_script(r, BANNED)
    assert any(msg in e for e in errs), errs


def test_bare_answer_allowed_after_a_question():
    r = raw()
    r["scenes"][3]["performance"][0]["line"] = "How many today? ...Six."
    assert core.validate_script(r, BANNED) == []


@pytest.mark.parametrize("key, value, msg", [
    ("rival_brand", "STARBUCKZ", "looks like the real brand 'starbucks'"),
    ("rival_brand", "Megabun", "ALL-CAPS"),
    ("payoff", "a red Porsche", "brand name 'porsche'"),
    ("offer_line", " ".join(["free"] * 21), "max 20"),
    ("noun", "", "missing"),
])
def test_slot_checks(key, value, msg):
    story = core.story_from_preset("barber-shop")
    story["slots"] = dict(story["slots"], **{key: value})
    errs = core.check_slots(story["slots"])
    with pytest.raises(ValueError) as e:
        core.build_script(brief("barber-shop"), story)
    assert any(msg in x for x in errs) or msg in str(e.value), (errs, str(e.value))


def test_real_name_check_is_hashed():
    assert core.real_names_in("hello Zorbleton!") == ["Zorbleton"] and core.real_names_in("hello there") == []
    assert all(len(h) == 64 for h in core.REAL_NAME_SHA256)


def test_brief_rejects_real_names_and_needs_a_type_for_gemini():
    with pytest.raises(ValueError, match="real person's name"):
        brief(owner="Zorbleton in a hoodie")
    with pytest.raises(ValueError, match="what kind of business"):
        brief(source="any other business: write with Gemini")
    b = core.make_brief("", "dog groomer", "", "", "", "", "", "funny", "veo-3.1-lite", "x")
    assert b["preset"] is None and b["business_type"] == "dog groomer"


def test_gemini_slots_round_trip_for_any_business():
    b = core.make_brief("Paws & Suds", "dog groomer", "", "", "", "", "", "funny", "veo-3.1-lite", "any other business: write with Gemini")
    assert b["cast"]["hero1"] and b["cast"]["owner"] == ""     # the house duo; the rest comes from Gemini
    wp = core.writer_prompt(b)
    assert "dog groomer" in wp and "JSON only" in wp and "not a bakery" in wp and all(f'"{k}"' in wp for k in core.SLOTS)
    slots = dict(core.load_preset("barber-shop")["slots"], noun="dog grooming shop", product="bath", products="baths",
                 rival_brand="MEGAPAWS", gimmick="free glitter bubble baths", dm_business="bike shop")
    reply = "Sure!\n```json\n" + json.dumps({"title": "The Last Bath", "cast": {"owner": "the groomer in a yellow apron",
            "rival": "the influencer in a white fur coat", "regular": "the old man with a sleepy bulldog"}, "slots": slots}) + "\n```"
    s = core.build_script(b, core.parse_reply(reply))
    assert s["title"] == "The Last Bath" and s["overlay"]["rival_brand"] == "MEGAPAWS"
    assert "the groomer in a yellow apron" in s["scenes"][0]["motion_prompt"].lower()
    with pytest.raises(ValueError):
        core.parse_reply("I can't help with that.")
    bad = json.loads(reply.split("```json\n")[1].split("\n```")[0])
    del bad["cast"]["owner"]
    with pytest.raises(ValueError, match="describe the owner"):
        core.build_script(b, core.parse_reply(json.dumps(bad)))


def test_film_length_and_caption_cues():
    s = script("barber-shop")
    assert 100 <= core.film_seconds(s) <= 115
    cues = core.caption_cues(["one two three", "four"], 10.0, 8.0)
    assert cues[0][0] == pytest.approx(10.3) and cues[-1][1] == pytest.approx(17.0)
    assert core.caption_cues([], 0, 8) == []
