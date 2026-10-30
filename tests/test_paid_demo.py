"""The paid-demo runner's money logic, with no network and no key: estimate from badge prices, the $10 refusal, the ledger."""
import importlib.util, json, sys
from pathlib import Path
import pytest
import underdog_core as core

ROOT = Path(core.__file__).parent
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("run_paid_demo", ROOT / "tools/run_paid_demo.py")
rpd = importlib.util.module_from_spec(spec); spec.loader.exec_module(rpd)
from build_app import build  # noqa: E402


def _est(model="veo-3.1-lite"):
    g = build("barber-shop", staged=True)
    next(n for n in g.values() if n["class_type"] == "UnderdogBrief")["inputs"]["model"] = model
    script, brief = rpd.script_for(g)
    return rpd.estimate(g, script, brief), script


def test_barber_estimate_is_under_the_cap():
    (total, cost, scene_of), script = _est()
    secs = sum(sc["seconds"] for sc in script["scenes"])
    expect = 15 * rpd.NB2_1K + secs * 0.05 + rpd.SONILO_PPS * core.film_seconds(script)
    assert total == pytest.approx(expect, abs=0.01) and 7 < total < rpd.HARD_CAP
    assert sorted(set(scene_of.values())) == list(range(1, 16))


def test_dearer_model_would_be_refused():
    (total, _, _), _ = _est("veo-3.1-fast-generate")
    assert total > rpd.HARD_CAP


def test_cap_above_the_approved_cap_is_refused_before_anything_runs():
    with pytest.raises(SystemExit, match="above the approved"):
        rpd.main(["--cap", str(rpd.HARD_CAP + 0.5)])   # never a value under the cap: that would dry-run for real


def test_badge_check_and_ledger(tmp_path):
    badges = {"Veo3VideoGenerationNode": {"price_badge": {"expr": '$contains($m, "lite") ? ($a ? 0.05 : 0.03) : ($a ? 0.10 : 0.08)'}},
              "GeminiNanoBanana2": {"price_badge": {"expr": '{"1k": 0.0835, "2k": 0.1217}'}},
              "SoniloVideoToMusic": {"price_badge": {"expr": '{"type":"usd","usd":0.009}'}}}
    rpd.check_badges(badges)
    badges["SoniloVideoToMusic"]["price_badge"]["expr"] = '{"type":"usd","usd":0.02}'
    with pytest.raises(SystemExit, match="price badge changed"):
        rpd.check_badges(badges)
    led = tmp_path / "runs/paid/ledger.jsonl"
    rpd.append_ledger(led, {"estimate_usd": 7.5, "status": "about to queue"})
    rpd.append_ledger(led, {"status": "success"})
    rows = [json.loads(x) for x in led.read_text().splitlines()]
    assert rows[0]["estimate_usd"] == 7.5 and len(rows) == 2


def test_key_is_only_read_after_confirm_and_only_sent_in_extra_data():
    src = (ROOT / "tools/run_paid_demo.py").read_text()
    assert src.index("if not a.confirm_spend:") < src.index("kf.read_text()")
    assert src.index("append_ledger(a.ledger") < src.index('urllib.request.Request(a.url + "/prompt"')
    assert '"extra_data": {"api_key_comfy_org": secret[0]}' in src
    assert "print(secret" not in src and "log(secret" not in src
