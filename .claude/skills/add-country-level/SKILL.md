---
name: add-country-level
description: Add a new country level to Feed the Aliens' Adventure campaign (a new ADVENTURE_LEVELS entry - animals, flag, landmark, colours), or change an existing level's cast, art or palette. Use when the user asks for a new country/level, names a country to add, or drops new animal/flag/landmark art into images/.
---

# Adding a country level

Levels are pure data: a dict in `main.py` appended to `ADVENTURE_LEVELS`. No
new code should be needed. `CLAUDE.md` is the reference for what the keys
mean and how modes/levels split — read it rather than guessing, and don't
duplicate it here.

## 1. Look at `images/` before writing anything

```bash
git status --short images/     # newly dropped art is usually already staged
ls -t images/ | head -20
```

The user drops art into `images/` and often stages it *before* asking, so
the assets for the level you are about to write may already be there under
obvious names (`germany.png`, `brandenburg-gate.png`, `alsatian.png`).

**Never generate or overwrite art without checking this first.** A
generated flag once clobbered the user's own staged `germany.png`; it was
only recoverable because the real one was still in the index
(`git restore images/<file>`). If a level needs art that is genuinely
missing, say so and ask — do not invent it.

Asset conventions, worth checking with `pygame.image.load(...).get_size()`:

| Asset | Size | Notes |
|---|---|---|
| Animal sprite | 64×64 | flat-icon style, faces right |
| Flag | 32×32 | shown by the level name, the timer and the level-select row |
| Landmark | any, ~512 tall | halved at runtime, sits bottom-left. **Crop it to the silhouette** — the whole image box is solid, so transparent padding is invisible death |

## 2. Write the level dict

Copy the nearest existing country (they are all the same shape) and change
the content. Every country keeps the same cast *shape*, which is what makes
levels comparable:

- 1 point: hedgehog (shared by every country so far)
- 2 points: a small mammal
- 5 points: a common national animal
- 10 points: a rare, fast, far-recycling animal (`speed`/`recycle_x`)
- deadly: the jet in the top half (`y_range`), a national road/rail vehicle
  in the bottom half
- the single-use shield in the rare pool

Take the palette from the flag: `background_color`, `score_color` and
`timer_color` should be three of its colours, picked so the score and timer
stay readable against the background.

**Each animal path goes in exactly three places** — the `animals` table, the
`animal_images` or `rare_animal_images` pool, and `legend_layout`. A path in
a pool with no `animals` entry trips a startup assertion; a path missing
from `legend_layout` just silently vanishes from the Level Info page, which
nothing catches for you.

Give the level its own `highscore_file` (`<Country>Highscore.txt` — the
`*Highscore.txt` gitignore rule already covers it). `AdventureProgress.txt`
pads itself with zeros, so an existing save file survives a new level.

## 3. Check what scales with the level count

Adding the fifth level walked the level-select rows off the bottom of the
600px window, because their spacing was a hardcoded 90px from y=250. When
the list grows, grep for layout constants that assume its old length:

```bash
grep -n "i \* [0-9]\|index \* [0-9]\|len(mode\[.levels.\])" main.py
```

## 4. Play it

```bash
.venv/bin/python tools/playtest.py --level N --invincible --shots /tmp/shots
.venv/bin/python tools/playtest.py --all      # nothing else broke
```

`--invincible` pins lives so the round reaches its time limit — without it
the autopilot often dies first and the landmark never spawns, so the
landmark path goes untested. The run reports how the round ended, whether
the landmark spawned/cleared/crashed, and what landed in the records file;
exit status is non-zero if any level never reached its end screen.

Then **look at the screenshots** — `04-info.png` (the legend and records)
and `landmark.png` are the two that catch content mistakes a passing run
will not: a missing legend row, an unreadable score colour, a landmark
that is the wrong size for its corner.

## 5. Finish

Update `CLAUDE.md` (the country list and anything the new level does
differently), then show the user a screenshot or two before committing.
