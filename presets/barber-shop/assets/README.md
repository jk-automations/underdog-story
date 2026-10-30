# Barber shop: reference sheets for everything

Every recurring person, place and prop in the film has a sheet, and the rival store has one sheet per state (open,
closed), so nothing is re-invented between scenes. Each scene's keyframe (Nano Banana 2) gets only the sheets of what is
on screen in that scene, at most 10. The paid app and `tools/run_paid_demo.py` refuse to run while a sheet is
missing; the free draft runs with placeholders and prints the same list as a warning.
Check: `python3 tools/stage_preset.py --preset barber-shop --check`.

Every sheet: PNG, at least 1024 px on the short side, the same glossy 3D animated family-film style, fictional people
only, no real logos, no readable text except the rival sign and "FOR LEASE" where noted.

| File | Scenes | What it shows |
|---|---|---|
| `owner.png` | 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 13, 14, 15 | The owner: the barber in his sixties with a grey pompadour, a neat white beard and a navy barber smock. Character sheet: front, three-quarter, side; proud, tired and smug expressions. |
| `rival.png` | 1, 11, 12, 14, 15 | The rival influencer: the young influencer with bleached spiky hair in a shiny silver tracksuit, with a phone on a selfie stick. Front, three-quarter, side; a grin and a deflated look. |
| `regular.png` | 2, 3, 10 | The loyal regular: the retired mail carrier with a big grey moustache in a tan windbreaker. Front, three-quarter, side; a warm smile. |
| `../small-business-rescue-bakery/assets/hero1.png` | 6, 7 | Agency duo, hero 1: the muscular bearded man with wavy dark hair in a black t-shirt with thin green stripes. Front, three-quarter, side. |
| `../small-business-rescue-bakery/assets/hero2.png` | 6, 7, 8, 9 | Agency duo, hero 2: the muscular man with short curly dark hair and a thin moustache in a plain black t-shirt. Front, three-quarter, side. |
| `location.png` | 1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 | The owner's place: the old corner barbershop with a red-and-white barber pole. Street exterior and interior (the vintage barber chair by the big mirror). No readable shop sign. |
| `rival_store_open.png` | 1, 3, 10, 11 | The rival landmark OPEN, grand-opening day: the chrome mega-salon with a giant spinning razor on the roof, sign lit and reading exactly "MEGAFADE", balloons and bunting. Street level, the whole storefront in frame. |
| `rival_store_closed.png` | 12, 13, 14, 15 | The SAME rival building CLOSED for good: dark windows, the "MEGAFADE" sign unlit, the metal shutter all the way down with a "FOR LEASE" sign, no banner, no balloons, nobody inside. Same angle as rival_store_open (make it from that sheet so the building matches). |
| `old_car.png` | 5, 13 | The owner's old car: the old rusty green pickup truck. Two views of the same vehicle: parked and worn; BROKEN DOWN with the hood up and steam pouring out. No badges, no plate text. |
| `prize_car.png` | 13, 14, 15 | The prize car: a glossy cherry-red original vintage-style coupe with whitewall tires, no badges, no emblems and no plate text. Front, three-quarter, side and rear views of the same car. |

Example: one paid run (`runs/paid/barber-shop/`) was made before the prop and state sheets existed; the cast held (they had sheets) but the prize car, the old pickup and the MEGAFADE building drifted. These sheets fix that. The earlier `rival_store.png` (grand opening, balloons) is kept as `rival_store_open.png`. Hero 1 and hero 2 (the agency duo) are shared with the bakery sample and used automatically.
