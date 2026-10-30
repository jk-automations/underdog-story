# Nail salon: reference sheets for everything

Every recurring person, place and prop in the film has a sheet, and the rival store has one sheet per state (open,
closed), so nothing is re-invented between scenes. Each scene's keyframe (Nano Banana 2) gets only the sheets of what is
on screen in that scene, at most 10. The paid app and `tools/run_paid_demo.py` refuse to run while a sheet is
missing; the free draft runs with placeholders and prints the same list as a warning.
Check: `python3 tools/stage_preset.py --preset nail-salon --check`.

Every sheet: PNG, at least 1024 px on the short side, the same glossy 3D animated family-film style, fictional people
only, no real logos, no readable text except the rival sign and "FOR LEASE" where noted.

| File | Scenes | What it shows |
|---|---|---|
| `owner.png` | 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 13, 14, 15 | The owner: the nail artist with a short silver bob, cat-eye glasses and a lavender smock. Character sheet: front, three-quarter, side; proud, tired and smug expressions. |
| `rival.png` | 1, 11, 12, 14, 15 | The rival influencer: the influencer with long platinum hair extensions in a pink sequin jacket, with a phone on a selfie stick. Front, three-quarter, side; a grin and a deflated look. |
| `regular.png` | 2, 3, 10 | The loyal regular: the retired schoolteacher with curly white hair in a bright floral blouse. Front, three-quarter, side; a warm smile. |
| `../small-business-rescue-bakery/assets/hero1.png` | 6, 7 | Agency duo, hero 1: the muscular bearded man with wavy dark hair in a black t-shirt with thin green stripes. Front, three-quarter, side. |
| `../small-business-rescue-bakery/assets/hero2.png` | 6, 7, 8, 9 | Agency duo, hero 2: the muscular man with short curly dark hair and a thin moustache in a plain black t-shirt. Front, three-quarter, side. |
| `location.png` | 1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 | The owner's place: the small family nail salon with pastel walls and shelves of polish bottles. Street exterior and interior (the manicure table by the window). No readable shop sign. |
| `rival_store_open.png` | 1, 3, 10, 11 | The rival landmark OPEN, grand-opening day: the glittering pink mega-spa with a giant diamond nail on the roof, sign lit and reading exactly "MEGANAILS", balloons and bunting. Street level, the whole storefront in frame. |
| `rival_store_closed.png` | 12, 13, 14, 15 | The SAME rival building CLOSED for good: dark windows, the "MEGANAILS" sign unlit, the metal shutter all the way down with a "FOR LEASE" sign, no banner, no balloons, nobody inside. Same angle as rival_store_open (make it from that sheet so the building matches). |
| `old_car.png` | 5, 13 | The owner's old car: the old faded silver sedan. Two views of the same vehicle: parked and worn; BROKEN DOWN with the hood up and steam pouring out. No badges, no plate text. |
| `prize_car.png` | 13, 14, 15 | The prize car: a glossy pastel-pink original convertible with no badges, no emblems and no plate text. Front, three-quarter, side and rear views of the same car. |

Hero 1 and hero 2 (the agency duo) are shared with the bakery sample and used automatically.
