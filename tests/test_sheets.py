"""Reference sheets for everything: every recurring person, place and prop (and each state of the rival store) has a
sheet; each scene's keyframe gets the sheets of what is on screen, in the right state for its beat; the paid path refuses
to run with a sheet missing and the free draft warns with the same list. No network, no key, nothing queued."""
import importlib.util, json, sys
from pathlib import Path
import pytest
import underdog_core as core

ROOT = Path(core.__file__).parent
sys.path.insert(0, str(ROOT / "tools"))
from build_app import build  # noqa: E402

PRESETS = ["barber-shop", "nail-salon", "small-business-rescue-bakery", "taco-truck"]
REQUIRED = {"old_car", "prize_car", "rival_store_open", "rival_store_closed", "location"}


def script(preset="barber-shop"):
    b = core.make_brief("", "", "", "", "", "", "", "funny", "veo-3.1-lite", f"preset: {preset}")
    return core.build_script(b, core.story_from_preset(preset))


# ---------------------------------------------------------------- the sheet set and the per-call limit
def test_every_recurring_entity_has_a_sheet_slot_and_every_slot_is_used():
    assert REQUIRED | set(core.CHARACTERS) == set(core.ROLES)
    use = core.sheet_use()
    assert all(use[r] for r in core.ROLES), "a sheet slot no scene uses"
    assert use["old_car"] == [5, 13] and use["prize_car"] == [13, 14, 15]
    assert use["rival_store_open"] == [1, 3, 10, 11] and use["rival_store_closed"] == [12, 13, 14, 15]


def test_no_scene_goes_over_the_nano_banana_reference_limit():
    assert core.MAX_REFS <= 14          # GeminiNanoBanana2 'images' tooltip on the live :8193: "up to 14"
    for a in core.ARC:
        assert 1 <= len(a["refs"]) <= core.MAX_REFS and len(set(a["refs"])) == len(a["refs"])


@pytest.mark.parametrize("preset", PRESETS)
def test_each_preset_lists_every_sheet_with_a_description(preset):
    rows = core.sheet_rows(preset)
    assert [r for r, _, _ in rows] == core.ROLES
    for role, rel, desc in rows:
        assert rel.endswith(".png") and len(desc) > 40 and "{" not in desc
    readme = (core.PRESETS_DIR / preset / "assets" / "README.md").read_text()
    for f in ("old_car.png", "prize_car.png", "rival_store_open.png", "rival_store_closed.png", "location.png"):
        assert f"`{f}`" in readme, (preset, f)
    slots = core.load_preset(preset)["slots"]
    assert slots["old_car"] in readme and slots["rival_brand"] in readme


# ---------------------------------------------------------------- state selection by beat
def test_rival_store_state_follows_the_beat():
    s = script()
    for sc in s["scenes"]:
        b, refs = sc["beat"], sc["refs"]
        if b < 12:
            assert "rival_store_closed" not in refs, b
        else:   # after the fall only the closed sheet is ever attached, and the text says CLOSED
            assert "rival_store_open" not in refs and "rival_store_closed" in refs, b
            assert "CLOSED" in sc["keyframe_body"] and "CLOSED" in sc["motion_prompt"], b
        if "rival_store_open" in refs:
            assert "is OPEN" in sc["keyframe_body"] or "still OPEN" in sc["keyframe_body"], b
    assert "GRAND OPENING" in s["scenes"][0]["keyframe_body"]
    assert all("GRAND OPENING" not in sc["keyframe_body"] for sc in s["scenes"][1:])
    fall = s["scenes"][11]["keyframe_body"]
    assert "shutter all the way down" in fall and "FOR LEASE" in fall and "no banner" in fall and "half down" not in fall


def test_car_states_follow_the_beat():
    s = script()
    low, payoff = s["scenes"][4], s["scenes"][12]
    assert low["refs"] == ["owner", "old_car"] and "BROKEN DOWN" in low["keyframe_body"] and "BROKEN DOWN" in low["motion_prompt"]
    assert "tow truck" in payoff["state"] and "brand new and shiny, exactly as in its sheet" in payoff["state"]
    for sc in s["scenes"][12:]:
        assert "prize_car" in sc["refs"] and "exactly as in its sheet" in sc["keyframe_body"]
    assert all("prize_car" not in sc["refs"] for sc in s["scenes"][:12])


def test_state_lines_pass_the_script_checks_for_every_preset():
    for p in PRESETS:
        s = script(p)
        assert core.load_preset(p)["slots"]["old_car"].lower() in s["scenes"][4]["state"].lower()


# ---------------------------------------------------------------- references wired per scene (the graph)
@pytest.mark.parametrize("draft", [False, True])
def test_each_scene_is_wired_to_exactly_its_sheets(draft):
    g = build("barber-shop", draft=draft)
    title = lambda k: g[k]["_meta"]["title"]
    scene_cls = "UnderdogDraftScene" if draft else "UnderdogScene"
    scenes = {n["inputs"]["scene"]: n for n in g.values() if n["class_type"] == scene_cls}
    assert sorted(scenes) == list(range(1, 16))
    for k, n in scenes.items():
        wired = [r for r in core.ROLES if r in n["inputs"]]
        assert set(wired) == set(core.ARC[k - 1]["refs"]), k
        for r in wired:
            assert title(n["inputs"][r][0]) == f"Sheet: {r}"
    if not draft:
        for k, n in g.items():
            if n["class_type"] == "GeminiNanoBanana2":
                assert g[n["inputs"]["images"][0]]["class_type"] == "UnderdogScene" and n["inputs"]["images"][1] == 2


@pytest.mark.parametrize("draft", [False, True])
def test_sheet_check_gates_gemini_and_the_script(draft):
    g = build("barber-shop", draft=draft)
    (ck,) = [k for k, n in g.items() if n["class_type"] == "UnderdogSheetCheck"]
    assert g[ck]["inputs"]["require"] is (not draft)
    assert {r for r in core.ROLES if r in g[ck]["inputs"]} == set(core.ROLES)
    script = next(n for n in g.values() if n["class_type"] == "UnderdogScript")
    assert script["inputs"]["brief"] == [ck, 0]
    if not draft:
        assert next(n for n in g.values() if n["class_type"] == "GeminiNode")["inputs"]["prompt"] == [ck, 1]
    assert any(n["class_type"] == "PreviewAny" and n["inputs"]["source"] == [ck, 2] for n in g.values())


# ---------------------------------------------------------------- the nodes: refuse (paid) / warn (draft)
@pytest.fixture(scope="module")
def nodes(comfy_path):
    import underdog_nodes
    return underdog_nodes


def test_paid_sheet_check_refuses_and_lists_the_missing(nodes):
    import torch
    sheet = torch.rand(1, 64, 64, 3)
    have = {r: sheet for r in core.ROLES if r not in ("prize_car", "rival_store_closed")}
    with pytest.raises(ValueError) as e:
        nodes.UnderdogSheetCheck().run("{}", "wp", True, **have, prize_car=torch.ones(1, 64, 64, 3))   # blank placeholder
    msg = str(e.value)
    assert msg.startswith("REFUSED") and "prize_car (scenes 13, 14, 15)" in msg and "rival_store_closed (scenes 12, 13, 14, 15)" in msg
    assert "old_car" not in msg
    assert nodes.UnderdogSheetCheck().run("{}", "wp", True, **{r: sheet for r in core.ROLES}) == ("{}", "wp", "All 10 reference sheets are attached.")


def test_draft_sheet_check_warns_with_the_same_list(nodes, capsys):
    b, wp, report = nodes.UnderdogSheetCheck().run("{}", "wp", False)
    assert (b, wp) == ("{}", "wp") and report.startswith("WARNING")
    assert core.missing_sheets_message(core.ROLES) in report and core.missing_sheets_message(core.ROLES) in capsys.readouterr().out


def test_scene_keeps_the_most_important_sheets_when_over_the_limit(nodes, monkeypatch):
    import torch
    s = nodes.UnderdogScript().run(nodes.UnderdogBrief().run("", "", "", "", "", "", "", "funny", "veo-3.1-lite", "preset: barber-shop")[0])[0]
    monkeypatch.setattr(core, "MAX_REFS", 2)
    imgs = {r: torch.rand(1, 64, 64, 3) for r in core.ROLES}
    kp, _, refs, _, _ = nodes.UnderdogScene().run(s, 13, **imgs)
    assert refs.shape[0] == 2 and "1) the character sheet of the barber" in kp and "2) the prize car" in kp and "3)" not in kp


def test_draft_backdrop_uses_the_state_sheet(nodes, monkeypatch):
    import torch
    seen = {}
    monkeypatch.setattr(core, "draft_clip", lambda out, sc, s, bg: seen.setdefault("bg", bg) or out)
    s = nodes.UnderdogScript().run(nodes.UnderdogBrief().run("", "", "", "", "", "", "", "funny", "veo-3.1-lite", "preset: barber-shop")[0])[0]
    closed = torch.zeros(1, 64, 64, 3); closed[..., 0] = 1.0; closed[0, 0, 0] = 0   # red, not flat -> not blank
    try:
        nodes.UnderdogDraftScene().run(s, 12, rival_store_closed=closed, location=torch.rand(1, 64, 64, 3))
    except Exception:
        pass   # VideoFromFile of the fake path; the backdrop choice is what is checked
    assert seen["bg"].getpixel((5, 5))[0] > 200


# ---------------------------------------------------------------- the paid runner refuses too
def test_paid_runner_refuses_with_the_missing_list(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("run_paid_demo", ROOT / "tools/run_paid_demo.py")
    rpd = importlib.util.module_from_spec(spec); spec.loader.exec_module(rpd)
    pdir = tmp_path / "presets" / "barber-shop"
    (pdir / "assets").mkdir(parents=True)
    (pdir / "preset.json").write_text((core.PRESETS_DIR / "barber-shop" / "preset.json").read_text())
    from PIL import Image
    for r in ("owner", "rival", "regular", "location", "rival_store_open"):
        Image.new("RGB", (600, 600), (r == "owner") * 255).save(pdir / "assets" / f"{r}.png")
    monkeypatch.setattr(core, "PRESETS_DIR", tmp_path / "presets")

    class Done:
        returncode = 1
    monkeypatch.setattr(rpd.subprocess, "run", lambda *a, **k: Done())
    with pytest.raises(SystemExit) as e:
        rpd.main(["--confirm-spend", "--preset", "barber-shop", "--comfy-base", str(tmp_path / "base"),
                  "--key-file", str(tmp_path / "no-key"), "--ledger", str(tmp_path / "ledger.jsonl")])
    msg = str(e.value)
    assert msg.startswith("REFUSED: Missing reference sheets")
    for r in ("rival_store_closed", "old_car", "prize_car", "hero1", "hero2"):
        assert r in msg
    assert "rival_store_open" not in msg and not (tmp_path / "ledger.jsonl").exists()
