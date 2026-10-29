"""The shipped App Mode workflow (made by tools/make_app.mjs in the real ComfyUI frontend)."""
import json
from pathlib import Path

WF = json.loads((Path(__file__).resolve().parent.parent / "workflows" / "underdog-story.json").read_text())
NODES = {n["id"]: n for n in WF["nodes"]}


def test_opens_in_app_mode_with_the_form():
    assert WF["extra"]["linearMode"] is True
    ins = WF["extra"]["linearData"]["inputs"]
    names = [(NODES[i]["type"], w) for i, w in ins]
    assert names.count(("LoadImage", "image")) == 6
    for w in ("business_name", "business_type", "owner", "rival", "partner", "hero_1", "hero_2", "tone", "model", "script_source"):
        assert ("UnderdogBrief", w) in names
    outs = sorted(NODES[i]["type"] for i in WF["extra"]["linearData"]["outputs"])
    assert outs == ["PreviewAny", "PreviewImage", "SaveVideo"]
    assert NODES[next(i for i in WF["extra"]["linearData"]["outputs"] if NODES[i]["type"] == "SaveVideo")]["title"] == "Your film"


def test_partner_nodes_and_no_random_seeds():
    types = [n["type"] for n in WF["nodes"]]
    assert types.count("Veo3VideoGenerationNode") == 12 and types.count("GeminiNanoBanana2") == 12 and types.count("GeminiNode") == 1
    assert not any("randomize" in (n.get("widgets_values") or []) for n in WF["nodes"]), "a re-run must reuse paid steps"
    for n in WF["nodes"]:
        if n["type"] == "Veo3VideoGenerationNode":
            model = next(i for i in n["inputs"] if i["name"] == "model")
            assert model["link"] is not None, "Veo model follows the app's model choice"
