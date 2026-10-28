# Demo plan: the app makes the film

Goal: one short screen recording where a viewer watches Underdog Story turn a form into a finished, funny vertical
film. Flow (Google's web tool) is where we iterate shots; this app is the reproducible, shareable version, so the demo
shows the *app* doing every step.

## Before the paid run (no money spent)

1. `python3 -m pytest` passes (script rules, final cut on test clips, nodes with the partner nodes mocked).
2. `tools/check_graph.py workflows/underdog-story-api.json` against the ComfyUI that will run the demo: OK.
3. Put the six sheets in `presets/small-business-rescue-bakery/assets/` (git-ignored: fictional characters, or people
   who gave written permission), then `python3 tools/stage_preset.py --input-dir <ComfyUI>/input`.
4. Founder approval for the spend: about **$6** (Veo 3.1 lite 12 × 8 s ≈ $4.80, Nano Banana 2 12 × 1K ≈ $1), one run,
   plus a cap of about $3 for re-running failed scenes.
5. Sign in to the Comfy account (or set the API key) in that ComfyUI. Check the credit balance.

## The run (recorded)

1. Open `workflows/underdog-story.json` (App Mode). Pick the six staged sheets, keep `veo-3.1-lite`, `funny`, the preset.
2. Start the screen recording, then press **Run**.
3. The recording shows, in order: the script text (the 12 beats with the jokes), the keyframe sheet filling in, the
   job queue as the 12 Veo clips render, and the finished MP4 playing in the app's output panel.
4. If a scene is blocked or breaks character, fix that scene's sheet or line and press Run again: fixed seeds mean only
   that scene is paid for again.

## The demo video (about 45 s, 9:16 and 16:9)

| Time | Shows |
|---|---|
| 0–3 s | Hook: the end of the film (the supercar beat), then "made with one ComfyUI app" |
| 3–12 s | The form: business name, cast lines, sheets dropped in, Run |
| 12–20 s | Sped-up progress: script text → keyframe sheet → clips arriving |
| 20–40 s | The film's best moments with captions: the threat, the low point, the viral ad, the showdown |
| 40–45 s | End card + "Underdog Story for ComfyUI · Apache-2.0" |

Post the full film next to it so viewers can judge it whole. Both carry the AI-generated label.

## Proof to keep

- The run's MP4 from `output/underdog/`, the keyframe sheet, the script text.
- ComfyUI's history JSON for the run (`/history`), which shows every partner call and the exact prompts.
- The credit charge for the run, to back the cost line in the README.
