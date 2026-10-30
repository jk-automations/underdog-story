"""The shipped App Mode workflows (made by tools/make_app.mjs in the real ComfyUI frontend)."""
import json
from pathlib import Path
import pytest

WF_DIR = Path(__file__).resolve().parent.parent / "workflows"
PARTNER = {"GeminiNode", "GeminiNanoBanana2", "Veo3VideoGenerationNode", "SoniloVideoToMusic"}


def load(name):
    wf = json.loads((WF_DIR / name).read_text())
    return wf, {n["id"]: n for n in wf["nodes"]}


@pytest.mark.parametrize("name", ["underdog-story.json", "underdog-story-draft.json"])
def test_opens_in_app_mode_with_the_form(name):
    wf, nodes = load(name)
    assert wf["extra"]["linearMode"] is True
    ins = [(nodes[i]["type"], w) for i, w in wf["extra"]["linearData"]["inputs"]]
    assert ins.count(("LoadImage", "image")) == 10     # reference sheets for everything: cast, places, props, states
    for w in ("script_source", "business_name", "business_type", "owner", "rival", "regular"):
        assert ("UnderdogBrief", w) in ins
    film = [i for i in wf["extra"]["linearData"]["outputs"] if nodes[i]["type"] == "SaveVideo"]
    assert len(film) == 1 and nodes[film[0]]["title"] == "Your film"
    assert "PreviewAny" in [nodes[i]["type"] for i in wf["extra"]["linearData"]["outputs"]]
    assert not any("randomize" in (n.get("widgets_values") or []) for n in wf["nodes"]), "a re-run must reuse paid steps"


def test_full_app_uses_the_partner_nodes():
    wf, nodes = load("underdog-story.json")
    types = [n["type"] for n in wf["nodes"]]
    assert types.count("Veo3VideoGenerationNode") == 15 and types.count("GeminiNanoBanana2") == 15
    assert types.count("GeminiNode") == 1 and types.count("SoniloVideoToMusic") == 1
    ins = [(nodes[i]["type"], w) for i, w in wf["extra"]["linearData"]["inputs"]]
    assert ("UnderdogScoreMix", "score") in ins and ("UnderdogBrief", "model") in ins


def test_draft_app_costs_nothing():
    wf, _ = load("underdog-story-draft.json")
    types = {n["type"] for n in wf["nodes"]}
    assert not types & PARTNER and "UnderdogDraftScene" in types
