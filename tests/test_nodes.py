"""The ComfyUI nodes with the partner nodes mocked: Gemini's reply is canned text, Nano Banana's keyframe is a plain
tensor, Veo's video is a dummy ffmpeg clip and Sonilo's score is a generated tone. Nothing is sent to any API."""
import json, subprocess, sys
from pathlib import Path
import pytest
import underdog_core as core

ROOT = Path(core.__file__).parent


@pytest.fixture(scope="module")
def nodes(comfy_path):
    import underdog_nodes
    return underdog_nodes


def _brief(nodes, source="preset: barber-shop", btype=""):
    return nodes.UnderdogBrief().run("", btype, "", "", "", "", "", "funny", "veo-3.1-lite", source)


def test_brief_outputs_and_sources(nodes):
    assert nodes.UnderdogBrief.RETURN_TYPES[2] == core.VEO_MODELS
    inputs = nodes.UnderdogBrief.INPUT_TYPES()["required"]
    assert inputs["script_source"][0][0] == "preset: barber-shop" and nodes.GEMINI_SOURCE in inputs["script_source"][0]
    assert {"regular", "hero_1", "hero_2"} <= set(inputs) and "partner" not in inputs
    b, wp, model = _brief(nodes)
    assert json.loads(b)["preset"] == "barber-shop" and model == "veo-3.1-lite" and "JSON only" in wp


def test_script_skips_gemini_for_preset(nodes):
    b = _brief(nodes)[0]
    n = nodes.UnderdogScript()
    assert n.check_lazy_status(b, None) == []
    script, text = n.run(b)
    assert len(json.loads(script)["scenes"]) == 15 and "Back of the line, pal." in text and "[SIX MONTHS LATER]" in text


def test_script_uses_mocked_gemini_for_any_business(nodes):
    b = _brief(nodes, nodes.GEMINI_SOURCE, "bike repair shop")[0]
    n = nodes.UnderdogScript()
    assert n.check_lazy_status(b, None) == ["writer_reply"]
    p = core.load_preset("barber-shop")
    reply = "```json\n" + json.dumps({"title": "Mock", "cast": {k: p["cast"][k] for k in ("owner", "rival", "regular")},
                                      "slots": dict(p["slots"], rival_brand="MEGASPOKE")}) + "\n```"
    assert n.check_lazy_status(b, reply) == []
    s = json.loads(n.run(b, reply)[0])
    assert s["title"] == "Mock" and s["overlay"]["rival_brand"] == "MEGASPOKE"
    with pytest.raises(ValueError, match="slots"):
        n.run(b, json.dumps({"title": "x"}))


def test_scene_picks_sheets_skips_blanks_and_gives_seconds(nodes):
    import torch
    script = nodes.UnderdogScript().run(_brief(nodes)[0])[0]
    sheet, blank = torch.rand(1, 600, 400, 3), torch.ones(1, 64, 64, 3)
    kp, mp, refs, cap, secs = nodes.UnderdogScene().run(script, 1, rival=sheet, owner=blank, rival_store=torch.rand(1, 300, 500, 3))
    assert refs.shape == (2, nodes.REF_SIZE, nodes.REF_SIZE, 3)     # rival + rival_store; owner slot blank, location absent
    assert "1) the character sheet of the young influencer" in kp and "2) the rival's storefront" in kp
    assert secs == 8 and core.LOCKED in mp and cap.startswith("What's up, everybody! MEGAFADE")
    assert nodes.UnderdogScene().run(script, 2)[4] == 6
    assert nodes.UnderdogScene().run(script, 5)[2] is None              # no sheets at all -> Nano Banana gets no images


def test_contact_sheet(nodes):
    import torch
    out = nodes.UnderdogContactSheet().run(**{f"keyframe_{i:02d}": torch.rand(1, 1280, 720, 3) for i in range(1, 16)})[0]
    assert out.shape == (1, 1440, 1350, 3)


def test_draft_scene_finish_and_master(nodes, tmp_path):
    """The $0 path end to end in the nodes: draft clips -> final cut -> master (no score)."""
    import torch
    script = nodes.UnderdogScript().run(_brief(nodes)[0])[0]
    vids = {f"scene_{i:02d}": nodes.UnderdogDraftScene().run(script, i, location=torch.rand(1, 400, 300, 3))[0] for i in (1, 14, 15)}
    (cut,) = nodes.UnderdogFinish().run(script, True, True, True, **vids)
    mix = nodes.UnderdogScoreMix()
    assert mix.check_lazy_status(cut, False, "", None) == []
    (film,) = mix.run(cut, False, "")
    p = tmp_path / "film.mp4"
    film.save_to(str(p))
    info = core.probe(p)
    assert info["audio"] and info["dur"] > 15


def test_score_mix_asks_for_sonilo_only_when_on(nodes, clips, tmp_path):
    import torch
    cut = nodes.VideoFromFile(str(clips[0]))
    mix = nodes.UnderdogScoreMix()
    assert mix.check_lazy_status(cut, True, "", None) == ["music"]
    assert mix.check_lazy_status(cut, False, "", None) == []
    assert mix.check_lazy_status(cut, True, "/my/track.wav", None) == []
    fake_sonilo = {"waveform": torch.sin(torch.linspace(0, 900, 48000 * 3))[None, None].repeat(1, 2, 1) * 0.5, "sample_rate": 48000}
    (film,) = mix.run(cut, True, "", fake_sonilo)
    p = tmp_path / "f.mp4"
    film.save_to(str(p))
    assert core.probe(p)["audio"]
    with pytest.raises(ValueError, match="music_path"):
        mix.run(cut, True, "/nope/song.mp3")


def _graph(tmp_path, *args):
    out = tmp_path / "api.json"
    subprocess.run([sys.executable, str(ROOT / "tools/build_app.py"), "--out", str(out), *args], check=True)
    return json.loads(out.read_text())


def test_api_graph(tmp_path):
    g = _graph(tmp_path)
    by = lambda cls: [k for k, v in g.items() if v["class_type"] == cls]
    assert len(by("GeminiNanoBanana2")) == 15 and len(by("Veo3VideoGenerationNode")) == 15 and len(by("LoadImage")) == 7
    assert len(by("SaveVideo")) == 16 and len(by("SoniloVideoToMusic")) == 1
    brief = by("UnderdogBrief")[0]
    assert g[brief]["inputs"]["script_source"] == "preset: barber-shop"
    for k in by("Veo3VideoGenerationNode"):
        i = g[k]["inputs"]
        assert i["aspect_ratio"] == "9:16" and i["generate_audio"] is True and i["resolution"] == "720p"
        assert g[i["duration_seconds"][0]]["class_type"] == "UnderdogScene" and i["duration_seconds"][1] == 4
        assert i["model"] == [brief, 2] and g[i["image"][0]]["class_type"] == "GeminiNanoBanana2"
    script = by("UnderdogScript")[0]
    assert g[g[script]["inputs"]["writer_reply"][0]]["class_type"] == "GeminiNode"
    son = g[by("SoniloVideoToMusic")[0]]["inputs"]
    assert g[son["video"][0]]["class_type"] == "UnderdogFinish"
    mix = g[by("UnderdogScoreMix")[0]]["inputs"]
    assert mix["score"] is True and g[mix["music"][0]]["class_type"] == "SoniloVideoToMusic"
    fin = g[by("UnderdogFinish")[0]]["inputs"]
    assert sorted(k for k in fin if k.startswith("scene_")) == [f"scene_{i:02d}" for i in range(1, 16)]


def test_draft_graph_is_free(tmp_path):
    sys.path.insert(0, str(ROOT / "tools"))
    from build_app import PARTNER_NODES
    g = _graph(tmp_path, "--draft")
    assert not {n["class_type"] for n in g.values()} & PARTNER_NODES
    assert sum(n["class_type"] == "UnderdogDraftScene" for n in g.values()) == 15
    mix = next(n for n in g.values() if n["class_type"] == "UnderdogScoreMix")["inputs"]
    assert mix["score"] is False and "music" not in mix
