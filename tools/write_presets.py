"""Writes presets/<name>/preset.json for every built-in business (kept as code so the slots are easy to review in one place).
The story is the same for all of them (underdog_core.ARC, from v9 "The Last Croissant"); a preset only fills the slots.
python3 tools/write_presets.py"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The agency duo is the same pair in every episode.
HEROES = {"hero1": "the muscular bearded man with wavy dark hair in a black t-shirt with thin green stripes",
          "hero2": "the muscular man with short curly dark hair and a thin moustache in a plain black t-shirt"}
HERO_ASSETS = {"hero1": "../small-business-rescue-bakery/assets/hero1.png", "hero2": "../small-business-rescue-bakery/assets/hero2.png"}
NO_BADGES = "no badges, no emblems and no plate text"


def assets(own=("owner", "rival", "regular", "location", "rival_store"), heroes=HERO_ASSETS):
    a = {r: f"assets/{r}.png" for r in own}
    a.update(heroes)
    return a


PRESETS = {
 "small-business-rescue-bakery": {
  "title": "The Last Croissant", "version": "v9", "business_name": "Abuela's Bakery", "business_type": "family bakery",
  "note": "The founder-approved v9 story. Its rough cut was drafted in Google Flow with the same arc (docs/examples).",
  "cast": {"owner": "the baker in round glasses and a yellow headscarf",
           "rival": "the blond influencer in a gold puffer vest",
           "regular": "the cheerful old man in a flat cap and a green cardigan", **HEROES},
  "cast_names": ["Rosa", "Chad", "Marco"],
  "assets": assets(heroes={"hero1": "assets/hero1.png", "hero2": "assets/hero2.png"}),
  "slots": {
   "noun": "bakery", "place": "the small cozy family bakery with a striped awning", "counter": "the glass display counter",
   "product": "croissant", "products": "croissants",
   "rival_brand": "MEGABUN", "rival_place": "gold mega-bakery with a giant inflatable bun on the roof", "gimmick": "free gold croissants",
   "busy": "Customers queue with paper bags of warm croissants while fresh trays fill the display case.",
   "unsold": "A full tray of unsold croissants sits in the display case.",
   "count_line": "Six. We sold six croissants today.",
   "regular_line": "Best croissants in town, Rosa! Don't you ever change.",
   "offer_item": "A single golden croissant sits alone on the counter, in plain view.",
   "offer_action": "slides the last croissant across the counter toward them and says kindly",
   "offer_line": "Last one. On the house.",
   "taste_setup": "{hero1} holds the last croissant, about to bite; {hero2} stands beside, curious.",
   "taste": "bites the croissant: a loud flaky crunch, flakes everywhere; a silent stunned beat, mouth closed while chewing",
   "bad_idea_line": "Okay. Ideas. A dancing croissant mascot? Free gold croissants?",
   "good_idea_line": "...No. This should have a line around the block.",
   "heirloom": "a faded photo of a grandmother baking in this same bakery and a handwritten recipe card",
   "heirloom_line": "Abuela's recipe. Forty years.",
   "craft": "folding butter into dough by hand", "craft_line": "Don't look at us. Look at the dough.",
   "regular_back_line": "Told you. They always come back.", "showdown_line": "Back of the line, Chad.",
   "old_car": "the old dented blue hatchback", "payoff": f"a glossy candy-red original two-seat convertible with {NO_BADGES}",
   "payoff_line": "Okay, okay... ONE treat.", "dm_business": "taco truck"}},
 "barber-shop": {
  "title": "The Last Chair", "version": "v9", "business_name": "Corner Chair Barbershop", "business_type": "barber shop",
  "cast": {"owner": "the barber in his sixties with a grey pompadour, a neat white beard and a navy barber smock",
           "rival": "the young influencer with bleached spiky hair in a shiny silver tracksuit",
           "regular": "the retired mail carrier with a big grey moustache in a tan windbreaker", **HEROES},
  "cast_names": [], "assets": assets(),
  "slots": {
   "noun": "barbershop", "place": "the old corner barbershop with a red-and-white barber pole",
   "counter": "the vintage barber chair by the big mirror", "product": "haircut", "products": "haircuts",
   "rival_brand": "MEGAFADE", "rival_place": "chrome mega-salon with a giant spinning razor on the roof",
   "gimmick": "free four-minute glitter fades",
   "busy": "Customers wait on the bench reading newspapers while clippers buzz and a hot towel steams.",
   "unsold": "A row of empty waiting chairs and a stack of untouched hot towels.",
   "count_line": "Six cuts today. Six.",
   "regular_line": "Same as always. Don't you ever change this place.",
   "offer_item": "The vintage barber chair stands empty and ready with a clean cape folded on it, in plain view.",
   "offer_action": "pats the empty barber chair and says kindly",
   "offer_line": "Chair's open. First cut's on the house.",
   "taste_setup": "{hero1} sits in the barber chair with a fresh sharp cut, the cape still on; {hero2} stands beside, curious.",
   "taste": "checks the fresh cut in the mirror: a silent stunned beat, mouth closed, running a hand over it",
   "bad_idea_line": "Okay. Ideas. A dancing razor mascot? Glitter fade Fridays?",
   "good_idea_line": "...No. This should have a line around the block.",
   "heirloom": "an old straight razor in a small glass case and a framed black-and-white photo of the shop on opening day",
   "heirloom_line": "My father's razor. Fifty years in this chair.",
   "craft": "giving a careful straight-razor shave with a hot towel", "craft_line": "Don't look at us. Look at the razor.",
   "showdown_line": "Back of the line, kid.",
   "old_car": "the old rusty green pickup truck",
   "payoff": f"a glossy cherry-red original vintage-style coupe with whitewall tires, {NO_BADGES}",
   "dm_business": "nail salon"}},
 "taco-truck": {
  "title": "The Last Taco", "version": "v9", "business_name": "La Esquina Tacos", "business_type": "taco truck",
  "cast": {"owner": "the taco cook with a long black braid, a red bandana and a white apron",
           "rival": "the influencer with slicked-back hair and mirrored sunglasses in a gold bomber jacket",
           "regular": "the construction worker in an orange hi-vis vest and a dusty hard hat", **HEROES},
  "cast_names": [], "assets": assets(),
  "slots": {
   "noun": "taco truck", "place": "the little turquoise taco truck on the corner, with string lights and two folding tables",
   "counter": "the truck's order window", "product": "taco", "products": "tacos",
   "rival_brand": "MEGATACO", "rival_place": "gold-wrapped mega food hall with a giant spinning taco on the roof",
   "gimmick": "free gold-leaf tacos",
   "busy": "Customers line up at the order window while tortillas sizzle on the griddle and people eat at the folding tables.",
   "unsold": "A stack of unused tortillas and a full pot of untouched salsa sit by the griddle.",
   "count_line": "Six orders today. Six.",
   "regular_line": "Best tacos in the city. Don't you ever change.",
   "offer_item": "A single fresh taco sits on a paper plate on the order window ledge, in plain view.",
   "offer_action": "slides the last taco across the window ledge toward them and says kindly",
   "offer_line": "Last one. On the house.",
   "taste_setup": "{hero1} holds the last taco, about to bite; {hero2} stands beside, curious.",
   "taste": "bites the taco: a crunchy, juicy bite; a silent stunned beat, mouth closed while chewing",
   "bad_idea_line": "Okay. Ideas. A dancing taco mascot? Gold-leaf tortillas?",
   "good_idea_line": "...No. This should have a line around the block.",
   "heirloom": "a worn stone molcajete bowl and a faded photo of a grandmother at a market stall",
   "heirloom_line": "My grandmother's salsa. Same stone bowl, sixty years.",
   "craft": "grinding salsa in the old stone bowl by hand", "craft_line": "Don't look at us. Look at the salsa.",
   "showdown_line": "Back of the line, amigo.",
   "old_car": "the old dented white minivan",
   "payoff": f"a glossy sunflower-yellow original convertible with {NO_BADGES}",
   "dm_business": "barbershop"}},
 "nail-salon": {
  "title": "The Last Appointment", "version": "v9", "business_name": "Steady Hands Nails", "business_type": "nail salon",
  "cast": {"owner": "the nail artist with a short silver bob, cat-eye glasses and a lavender smock",
           "rival": "the influencer with long platinum hair extensions in a pink sequin jacket",
           "regular": "the retired schoolteacher with curly white hair in a bright floral blouse", **HEROES},
  "cast_names": [], "assets": assets(),
  "slots": {
   "noun": "nail salon", "place": "the small family nail salon with pastel walls and shelves of polish bottles",
   "counter": "the manicure table by the window", "product": "manicure", "products": "manicures",
   "rival_brand": "MEGANAILS", "rival_place": "glittering pink mega-spa with a giant diamond nail on the roof",
   "gimmick": "free diamond-dust nails",
   "busy": "Customers chat at the manicure tables while walls of colorful polish bottles glow.",
   "unsold": "Rows of polish bottles stand untouched and every manicure chair is empty.",
   "count_line": "Six clients today. Six.",
   "regular_line": "Best manicures in town. Don't you ever change.",
   "offer_item": "One manicure chair stands empty with a fresh towel and a bottle of red polish set out, in plain view.",
   "offer_action": "pats the empty manicure chair and says kindly",
   "offer_line": "Chair's open. First one's on the house.",
   "taste_setup": "{hero1} sits at the manicure table admiring a fresh, perfect manicure; {hero2} stands beside, curious.",
   "taste": "holds the freshly painted nails up to the light: a silent stunned beat, mouth closed",
   "bad_idea_line": "Okay. Ideas. A dancing polish-bottle mascot? Diamond-dust Fridays?",
   "good_idea_line": "...No. This should have a line around the block.",
   "heirloom": "a framed photo of a mother at the first salon and a hand-painted sign from opening day",
   "heirloom_line": "My mom's first salon. Thirty years of steady hands.",
   "craft": "painting a tiny flower on a nail with a fine brush", "craft_line": "Don't look at us. Look at the brush.",
   "showdown_line": "Back of the line, sweetie.",
   "old_car": "the old faded silver sedan",
   "payoff": f"a glossy pastel-pink original convertible with {NO_BADGES}",
   "dm_business": "pizza shop"}},
}

if __name__ == "__main__":
    for name, p in PRESETS.items():
        out = ROOT / "presets" / name / "preset.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"name": name, **p}, indent=1, ensure_ascii=False) + "\n")
        print("wrote", out.relative_to(ROOT))
