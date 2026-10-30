# Demo plan: one form, any business (under 2 minutes)

Goal: a viewer sees Underdog Story turn a short form into a finished, funny vertical episode, for a barber shop, and
understands it works for any small business. The bakery v9 cut (drafted in Google Flow with the same arc) shows how
far the arc carries.

## Before recording (no money spent)

1. `python3 -m pytest` passes; `tools/check_graph.py` against the ComfyUI that will run the demo prints OK.
2. The five barber sheets are in `presets/barber-shop/assets/` (`python3 tools/stage_preset.py --preset barber-shop --check`
   prints `ok` for all seven roles).
3. `python3 tools/run_paid_demo.py` (dry run) prints the estimate, about **$7.59**, under the $10 cap.
4. Founder runs `python3 tools/run_paid_demo.py --confirm-spend` himself. The ledger row is written before anything is
   queued. Output: `runs/paid/barber-shop/underdog-barber-demo.mp4`, `keyframes.png`, `receipt.json`.

## The video (about 110 s, 9:16 and 16:9)

| Time | Shows |
|---|---|
| 0–4 s | Hook: the barber's "Hmm. No." and the car pulling away, then "one ComfyUI app, any small business" |
| 4–20 s | The form in App Mode: Business = barber shop, sheets dropped in, Sonilo score on, **Run** |
| 20–32 s | Sped up: the script text (15 beats, SIX MONTHS LATER), the keyframe sheet filling in, clips arriving |
| 32–70 s | Barber highlights: MEGAFADE's grand opening, the pickup dying, "My father's razor. Fifty years in this chair.", the view counter, the line back with MEGAFADE locked in frame, "Back of the line, kid." |
| 70–95 s | "Same arc, any business": the bakery v9 (Flow draft) highlights, MEGABUN, "Abuela's recipe. Forty years.", the red car, the episode 2 DM |
| 95–110 s | The form again: business type "dog groomer" → the $0 draft plays → end card "Underdog Story for ComfyUI · Apache-2.0" |

Label the bakery part on screen: "drafted in Google Flow with the same arc". Both films carry the AI-generated label.
Post the full barber film next to the demo so viewers can judge it whole.

## Proof to keep

- The barber MP4, the keyframe sheet, the script text, `receipt.json` and the ledger rows.
- ComfyUI's `/history` JSON for the run (every partner call and its exact prompt).
- The credit charge, to back the cost table in the README.
