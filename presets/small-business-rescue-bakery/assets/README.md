# Family bakery: reference sheets for everything

Every recurring person, place and prop in the film has a sheet, and the rival store has one sheet per state (open,
closed), so nothing is re-invented between scenes. Each scene's keyframe (Nano Banana 2) gets only the sheets of what is
on screen in that scene, at most 10. The paid app and `tools/run_paid_demo.py` refuse to run while a sheet is
missing; the free draft runs with placeholders and prints the same list as a warning.
Check: `python3 tools/stage_preset.py --preset small-business-rescue-bakery --check`.

Every sheet: PNG, at least 1024 px on the short side, the same glossy 3D animated family-film style, fictional people
only, no real logos, no readable text except the rival sign and "FOR LEASE" where noted.

| File | Scenes | What it shows |
|---|---|---|
| `owner.png` | 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 13, 14, 15 | The owner: the baker in round glasses and a yellow headscarf. Character sheet: front, three-quarter, side; proud, tired and smug expressions. |
| `rival.png` | 1, 11, 12, 14, 15 | The rival influencer: the blond influencer in a gold puffer vest, with a phone on a selfie stick. Front, three-quarter, side; a grin and a deflated look. |
| `regular.png` | 2, 3, 10 | The loyal regular: the cheerful old man in a flat cap and a green cardigan. Front, three-quarter, side; a warm smile. |
| `hero1.png` | 6, 7 | Agency duo, hero 1: the muscular bearded man with wavy dark hair in a black t-shirt with thin green stripes. Front, three-quarter, side. |
| `hero2.png` | 6, 7, 8, 9 | Agency duo, hero 2: the muscular man with short curly dark hair and a thin moustache in a plain black t-shirt. Front, three-quarter, side. |
| `location.png` | 1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 | The owner's place: the small cozy family bakery with a striped awning. Street exterior and interior (the glass display counter). No readable shop sign. |
| `rival_store_open.png` | 1, 3, 10, 11 | The rival landmark OPEN, grand-opening day: the gold mega-bakery with a giant inflatable bun on the roof, sign lit and reading exactly "MEGABUN", balloons and bunting. Street level, the whole storefront in frame. |
| `rival_store_closed.png` | 12, 13, 14, 15 | The SAME rival building CLOSED for good: dark windows, the "MEGABUN" sign unlit, the metal shutter all the way down with a "FOR LEASE" sign, no banner, no balloons, nobody inside. Same angle as rival_store_open (make it from that sheet so the building matches). |
| `old_car.png` | 5, 13 | The owner's old car: the old dented blue hatchback. Two views of the same vehicle: parked and worn; BROKEN DOWN with the hood up and steam pouring out. No badges, no plate text. |
| `prize_car.png` | 13, 14, 15 | The prize car: a glossy candy-red original two-seat convertible with no badges, no emblems and no plate text. Front, three-quarter, side and rear views of the same car. |

`owner.png`, `rival.png`, `hero1.png`, `hero2.png` and `location.png` come from the v6/v9 work. `partner.png` and `rival_with_hero_orig.png` are from the older v6 story and are not used.
