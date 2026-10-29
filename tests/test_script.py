import copy, hashlib, json, re
import pytest
import underdog_core as core

FAKE_REAL = "Zorbleton"   # stands in for a real person's name in these tests (the repo holds no real names)


@pytest.fixture(autouse=True)
def fake_real_name(monkeypatch):
    monkeypatch.setattr(core, "REAL_NAME_SHA256", core.REAL_NAME_SHA256 | {hashlib.sha256(FAKE_REAL.lower().encode()).hexdigest()})

PRESET = "small-business-rescue-bakery"
BANNED = {"rosa", "chad", "marco"}


def brief(source=f"preset: {PRESET}", tone="funny", **over):
    p = core.load_preset(PRESET)
    c = dict(p["cast"], **over)
    return core.make_brief(p["business_name"], p["business_type"], c["owner"], c["rival"], c["partner"], c["hero1"], c["hero2"],
                           tone, "veo-3.1-lite", source)


@pytest.fixture
def raw():
    return copy.deepcopy(core.load_preset(PRESET))


def test_preset_is_valid_and_complete(raw):
    assert core.validate_script(raw, BANNED) == []
    assert [s["beat"] for s in raw["scenes"]] == list(range(1, 13))
    assert len(core.BEATS) == 12


def test_preset_lines_fit_8_seconds(raw):
    for sc in raw["scenes"]:
        lines = [st["line"] for st in sc["performance"] if st.get("line")]
        assert all(core._words(ln) <= core.MAX_LINE_WORDS for ln in lines), sc["beat"]
        assert sum(core._words(ln) for ln in lines) <= core.MAX_SCENE_WORDS


def test_preset_is_the_v6_story(raw):
    lines = [(sc["beat"], st["who"], st["line"]) for sc in raw["scenes"] for st in sc["performance"] if st.get("line")]
    assert lines == [(1, "owner", "...Last one."), (2, "rival", "Love the little shop. Very... vintage."),
                     (3, "partner", "Babe. Six today."), (4, "owner", "Go. You'll be late."), (5, "hero1", "Is that the last one?"),
                     (6, "hero2", "Again. Slower."), (7, "owner", "Abuela's recipe. Forty years."), (8, "hero2", "We make ads."),
                     (9, "owner", "...Oh no."), (10, "owner", "Back of the line, Chad."), (11, "partner", "Oh wow... that's your car?"),
                     (12, "owner", "One of them."), (12, "owner", "Last one.")]
    assert "CLOSING SUNDAY" in raw["scenes"][0]["keyframe"] and "recipe card" in raw["scenes"][6]["keyframe"]
    assert "exhaust roar" in raw["scenes"][10]["camera"]


def test_cast_matches_the_sheets(raw):
    assert "striped" in raw["cast"]["hero1"] or "stripes" in raw["cast"]["hero1"]
    assert "plain black t-shirt" in raw["cast"]["hero2"]


def test_one_speaker_per_scene_in_rendered_prompts():
    s = core.build_script(brief(), core.load_preset(PRESET))
    for sc in s["scenes"]:
        assert f"Only {s['brief']['cast'][sc['speaker']]} speaks in this shot" in sc["motion_prompt"]
        assert "No new people enter the frame." in sc["motion_prompt"]
        assert sc["motion_prompt"].count('"') == 2 * len(sc["captions"])   # only the one speaker's lines are quoted


def test_rendered_prompts_follow_the_rules():
    s = core.build_script(brief(), core.load_preset(PRESET))
    assert len(s["scenes"]) == 12
    for i, sc in enumerate(s["scenes"]):
        mp = sc["motion_prompt"]
        assert mp.endswith(core.MOTION_TAIL)
        assert "One continuous take, no cuts. No captions, no subtitles" in mp
        assert re.search(r'"[^"]+"', mp), "dialogue is quoted"
        kp = core.keyframe_prompt(s, i, sc["refs"])
        assert kp.startswith(core.KEYFRAME_HEAD) and "no real brand logos" in kp
        for text in (kp, core._outside_quotes(mp)):
            assert "{" not in text, "all placeholders filled"
            for n in BANNED:
                assert not core._has_word(text, n), (i, n)
            assert core.real_names_in(text) == []
            for b in core.BRANDS:
                assert not core._has_word(text, b), (i, b)
        assert core.real_names_in(mp) == []
        assert sc["captions"] and all(c in mp for c in sc["captions"])


def test_keyframe_legend_lists_only_attached_sheets():
    s = core.build_script(brief(), core.load_preset(PRESET))
    kp = core.keyframe_prompt(s, 0, ["owner", "location"])
    assert "1) the character sheet of the baker" in kp and "2) the location (Abuela's Bakery)" in kp and "3)" not in kp
    assert "Reference images" not in core.keyframe_prompt(s, 0, [])


def test_tone_changes_the_performance_note():
    funny = core.build_script(brief(tone="funny"), core.load_preset(PRESET))["scenes"][0]["motion_prompt"]
    warm = core.build_script(brief(tone="heartfelt"), core.load_preset(PRESET))["scenes"][0]["motion_prompt"]
    assert core.TONES["funny"] in funny and core.TONES["heartfelt"] in warm


@pytest.mark.parametrize("breakit, msg", [
    (lambda r: r["scenes"].pop(), "exactly 12 scenes"),
    (lambda r: r["scenes"][0]["performance"][0].update(line=" ".join(["word"] * 21)), "21 words"),
    (lambda r: r["scenes"][0]["performance"].extend([{"who": "owner", "how": "x", "line": " ".join(["la"] * 20)}] * 2), "won't fit 8 s"),
    (lambda r: r["scenes"][2].update(keyframe="Rosa stands at the counter."), "character name 'rosa'"),
    (lambda r: r["scenes"][3]["performance"][0].update(line="Hey Zorbleton, look!"), "real person's name 'Zorbleton'"),
    (lambda r: r["scenes"][10].update(keyframe="A red Ferrari at the curb."), "brand name 'ferrari'"),
    (lambda r: r["scenes"][4].update(keyframe="{villain} laughs."), "unknown placeholder"),
    (lambda r: r["scenes"][5].update(refs=["owner", "dog"]), "refs must be"),
    (lambda r: r["scenes"][6]["performance"][0].update(who="narrator"), "who must be"),
    (lambda r: r["scenes"][7].update(beat=3), "beat must be 8"),
    (lambda r: r["scenes"][8].update(transition="spin"), "transition must be"),
    (lambda r: r["scenes"][9]["performance"][1].update(line='He said "hi"'), "double quotes"),
    (lambda r: r["scenes"][2]["performance"][1].update(line="It's fine."), "exactly one on-screen speaker"),
    (lambda r: r["scenes"][0]["performance"].append({"who": "rival", "how": "laughs", "line": "Ha."}), "exactly one on-screen speaker"),
    (lambda r: r["scenes"][8]["performance"][0].update(who="offscreen"), "exactly one on-screen speaker"),
    (lambda r: r["scenes"][1]["performance"][1].update(how="smiles and says nothing back"), "silent step must not speak"),
    (lambda r: [st.update(line=None) for st in r["scenes"][10]["performance"]], "exactly one on-screen speaker"),
])
def test_validator_rejects(raw, breakit, msg):
    breakit(raw)
    errs = core.validate_script(raw, BANNED)
    assert any(msg in e for e in errs), errs
    with pytest.raises(ValueError):
        core.build_script(brief(), raw)


def test_real_name_check_is_hashed():
    assert core.real_names_in("hello Zorbleton!") == ["Zorbleton"] and core.real_names_in("hello there") == []
    assert all(len(h) == 64 for h in core.REAL_NAME_SHA256)


def test_names_allowed_inside_dialogue_only(raw):
    assert any("Chad" in (st.get("line") or "") for sc in raw["scenes"] for st in sc["performance"])
    assert core.validate_script(raw, BANNED) == []


def test_brief_rejects_real_names_and_empty_cast():
    with pytest.raises(ValueError, match="real person's name"):
        brief(owner="Zorbleton in a hoodie")
    with pytest.raises(ValueError, match="describe the rival"):
        brief(rival="  ")
    assert "best friend" in brief(partner="")["cast"]["partner"]


def test_writer_prompt_and_reply_round_trip(raw):
    b = brief(source="write with Gemini")
    assert b["preset"] is None
    wp = core.writer_prompt(b)
    for _, name, _ in core.BEATS:
        assert name in wp
    assert "at most 20 words" in wp and "JSON only" in wp and b["cast"]["rival"] in wp
    reply = "Sure! Here it is:\n```json\n" + json.dumps({"title": "T", "scenes": raw["scenes"]}) + "\n```"
    parsed = core.parse_reply(reply)
    assert core.build_script(b, parsed)["title"] == "T"
    assert core.parse_reply(json.dumps(raw["scenes"]))["scenes"] == raw["scenes"]
    with pytest.raises(ValueError):
        core.parse_reply("I can't help with that.")


def test_caption_cues_cover_the_take():
    cues = core.caption_cues(["one two three", "four"], 10.0, 8.0)
    assert cues[0][0] == pytest.approx(10.3) and cues[-1][1] == pytest.approx(17.6)
    assert cues[0][1] - cues[0][0] == pytest.approx(3 * (cues[1][1] - cues[1][0]))
    assert core.caption_cues([], 0, 8) == []
