// Real-browser E2E of the free path: open the $0 draft app in ComfyUI's App Mode, fill the form, press Run, wait for the
// finished draft film to play in the output panel, and screenshot it. Every POST /prompt is inspected and refused if it
// contains a paid partner node, so this can never spend money.
// node tools/e2e_draft.mjs <comfy_url> <workflow.json> <screenshot.png> [business name]
import { chromium } from "playwright";
import fs from "fs";

const [url, wfPath, shot, name = "Corner Chair Barbershop"] = process.argv.slice(2);
const PARTNER = new Set(["GeminiNode", "GeminiNanoBanana2", "Veo3VideoGenerationNode", "SoniloVideoToMusic"]);
const wf = JSON.parse(fs.readFileSync(wfPath, "utf8"));
const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1440, height: 1300 } })).newPage();
const errors = [];
let promptId = null, queued = 0;
page.on("pageerror", (e) => errors.push(e.message));
await page.route("**/prompt", async (r) => {
  const req = r.request();
  if (req.method() !== "POST") return r.continue();
  const body = JSON.parse(req.postData() || "{}");
  const types = Object.values(body.prompt || {}).map((n) => n.class_type);
  const paid = types.filter((t) => PARTNER.has(t));
  if (paid.length) { console.log("BLOCKED paid nodes:", paid); return r.abort(); }
  if (body.extra_data && body.extra_data.api_key_comfy_org) { console.log("BLOCKED: an API key was attached"); return r.abort(); }
  queued += 1;
  console.log(`queueing a free graph: ${types.length} nodes`);
  const resp = await r.fetch();
  const j = await resp.json();
  promptId = j.prompt_id;
  return r.fulfill({ response: resp, json: j });
});
await page.goto(url, { waitUntil: "load", timeout: 120000 });
await page.waitForFunction(() => window.app && window.app.graph, null, { timeout: 120000 });
await page.evaluate(async (w) => { await window.app.loadGraphData(w, true, true, "underdog-story-draft"); }, wf);
await page.waitForTimeout(3000);
try { await page.click("text=Skip", { timeout: 4000 }); } catch {}
// Fill the form like a user: the business name field sits under its label in the App Mode panel.
const nameBox = page.locator("xpath=//*[normalize-space(text())='Business name']/following::input[1] | //*[normalize-space(text())='Business name']/following::textarea[1]").first();
await nameBox.click();
await nameBox.fill(name);
await nameBox.press("Tab");
await page.waitForTimeout(800);
const typed = await page.evaluate(() => {
  const n = window.app.graph.nodes.find((x) => x.type === "UnderdogBrief");
  return n.widgets.find((w) => w.name === "business_name").value;
});
console.log("form business_name ->", JSON.stringify(typed));
await page.locator("button", { hasText: /^\s*Run\s*$/ }).last().click();
const t0 = Date.now();
let status = null, hist = null;
while (Date.now() - t0 < 20 * 60 * 1000) {
  await page.waitForTimeout(5000);
  if (!promptId) continue;
  hist = await (await fetch(`${url}/history/${promptId}`)).json();
  const h = hist[promptId];
  if (h && h.status && ["success", "error"].includes(h.status.status_str)) { status = h.status.status_str; break; }
}
console.log("run status", status, "after", Math.round((Date.now() - t0) / 1000), "s; queued", queued);
const outs = hist && hist[promptId] ? Object.values(hist[promptId].outputs || {}) : [];
const films = outs.flatMap((o) => o.images || o.videos || o.gifs || []).filter((f) => /draft.*\.mp4$/.test(f.filename));
console.log("draft film:", JSON.stringify(films));
if (status === "error") console.log(JSON.stringify(hist[promptId].status.messages.find((m) => m[0] === "execution_error")).slice(0, 1500));
// Let the output panel show the film, then capture the page as the user sees it.
try { await page.locator("video").first().waitFor({ state: "visible", timeout: 60000 }); } catch { console.log("no <video> visible"); }
await page.evaluate(async () => { const v = document.querySelector("video"); if (v) { v.muted = true; v.currentTime = 30; await v.play().catch(() => {}); } });
await page.waitForTimeout(2500);
await page.screenshot({ path: shot });
const scriptShown = await page.evaluate(() => /SIX MONTHS LATER|Back of the line/.test(document.body.innerText));
console.log("script text visible", scriptShown, "page errors", errors.length, JSON.stringify(errors.slice(0, 3)));
// Reference sheets for everything: the free draft runs on placeholders and shows the missing-sheet list as a warning.
const report = hist && hist[promptId] ? JSON.stringify(hist[promptId].outputs || {}) : "";
const warned = /Missing reference sheets/.test(report);
console.log("sheet warning in outputs", warned, "| shown on page", await page.evaluate(() => /Missing reference sheets/.test(document.body.innerText)));
await browser.close();
process.exit(status === "success" && films.length && warned ? 0 : 1);
