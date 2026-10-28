"""The ComfyUI nodes with the partner nodes mocked: Gemini's reply is canned text, Nano Banana's keyframe is a plain
tensor and Veo's video is a dummy ffmpeg clip. Nothing is sent to any API."""
import json
import pytest
import underdog_core as core


@pytest.fixture(scope="module")
def nodes(comfy_path):
    import underdog_nodes
    return underdog_nodes


def _brief(nodes, source=None):
    p = core.load_preset("small-business-rescue-bakery")
    c = p["cast"]
    return nodes.UnderdogBrief().run(p["business_name"], p["business_type"], c["owner"], c["rival"], c["partner"], c["hero1"],
                                     c["hero2"], "funny", "veo-3.1-lite", source or nodes.PRESET_SOURCES[0])


def test_brief_outputs_and_model_combo(nodes):
    types = nodes.UnderdogBrief.RETURN_TYPES
    assert types[2] == core.VEO_MODELS and types[2][0] == "veo-3.1-lite"
    inputs = nodes.UnderdogBrief.INPUT_TYPES()["required"]
    assert set(core.VEO_MODELS) <= set(inputs["model"][0])
    b, wp, model = _brief(nodes)
    assert json.loads(b)["preset"] == "small-business-rescue-bakery" and model == "veo-3.1-lite" and "JSON only" in wp


def test_script_skips_gemini_for_preset(nodes):
    b = _brief(nodes)[0]
    n = nodes.UnderdogScript()
    assert n.check_lazy_status(b, None) == []
    script, text = n.run(b)
    assert len(json.loads(script)["scenes"]) == 12 and "BANKRUPTCY" not in text and "bankruptcy" in text


def test_script_uses_mocked_gemini_reply(nodes):
    b = _brief(nodes, nodes.GEMINI_SOURCE)[0]
    n = nodes.UnderdogScript()
    assert n.check_lazy_status(b, None) == ["writer_reply"]
    reply = "```json\n" + json.dumps({"title": "Mock", "scenes": core.load_preset("small-business-rescue-bakery")["scenes"]}) + "\n```"
    assert n.check_lazy_status(b, reply) == []
    assert json.loads(n.run(b, reply)[0])["title"] == "Mock"
    bad = json.loads(reply.strip("`json\n"))
    bad["scenes"] = bad["scenes"][:5]
    with pytest.raises(ValueError, match="exactly 12"):
        n.run(b, json.dumps(bad))


def test_scene_picks_sheets_and_skips_blanks(nodes):
    import torch
    script = nodes.UnderdogScript().run(_brief(nodes)[0])[0]
    sheet = torch.rand(1, 600, 400, 3)
    blank = torch.ones(1, 64, 64, 3)
    kp, mp, refs, cap = nodes.UnderdogScene().run(script, 1, owner=sheet, rival=blank, location=torch.rand(1, 300, 500, 3))
    assert refs.shape == (2, nodes.REF_SIZE, nodes.REF_SIZE, 3)     # owner + location; the rival slot was blank
    assert "1) the character sheet of the baker" in kp and "2) the location" in kp and "influencer in a gold puffer vest;" not in kp
    assert mp.endswith(core.MOTION_TAIL) and "bankruptcy" in cap
    assert nodes.UnderdogScene().run(script, 5)[2] is None              # no sheets at all -> Nano Banana gets no images


def test_contact_sheet(nodes):
    import torch
    out = nodes.UnderdogContactSheet().run(**{f"keyframe_{i:02d}": torch.rand(1, 1280, 720, 3) for i in range(1, 13)})[0]
    assert out.shape == (1, 960, 1620, 3)


def test_finish_node_with_mocked_veo_clips(nodes, clips):
    script = nodes.UnderdogScript().run(_brief(nodes)[0])[0]
    vids = {f"scene_{i:02d}": nodes.VideoFromFile(str(c)) for i, c in enumerate(clips, 1)}
    (video,) = nodes.UnderdogFinish().run(script, True, True, True, **vids)
    import tempfile, pathlib
    p = pathlib.Path(tempfile.mkdtemp()) / "out.mp4"
    video.save_to(str(p))
    info = core.probe(p)
    assert info["audio"] and info["dur"] > 8


def test_api_graph(tmp_path):
    import subprocess, sys
    from pathlib import Path
    root = Path(core.__file__).parent
    out = tmp_path / "api.json"
    subprocess.run([sys.executable, str(root / "tools/build_app.py"), "--out", str(out)], check=True)
    g = json.loads(out.read_text())
    by = lambda cls: [k for k, v in g.items() if v["class_type"] == cls]
    assert len(by("GeminiNanoBanana2")) == 12 and len(by("Veo3VideoGenerationNode")) == 12 and len(by("LoadImage")) == 6
    brief = by("UnderdogBrief")[0]
    for k in by("Veo3VideoGenerationNode"):
        i = g[k]["inputs"]
        assert i["aspect_ratio"] == "9:16" and i["duration_seconds"] == 8 and i["generate_audio"] is True
        assert i["model"] == [brief, 2] and g[i["image"][0]]["class_type"] == "GeminiNanoBanana2"
    for k in by("GeminiNanoBanana2"):
        assert g[k]["inputs"]["aspect_ratio"] == "9:16" and g[g[k]["inputs"]["images"][0]]["class_type"] == "UnderdogScene"
    script = by("UnderdogScript")[0]
    assert g[g[script]["inputs"]["writer_reply"][0]]["class_type"] == "GeminiNode"
    fin = g[by("UnderdogFinish")[0]]["inputs"]
    assert sorted(k for k in fin if k.startswith("scene_")) == [f"scene_{i:02d}" for i in range(1, 13)]
