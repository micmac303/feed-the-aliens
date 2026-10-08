# To do

## Difficulty follow-ups

The per-level hazard speed curve is done (see the comment above
`UK_LEVEL` in main.py). Later ideas: jets speeding up during a level as the clock runs down;
tuning time/goal/lives/spawn mix per level; tanks as a late-game hazard
(needs art); remembering the fullscreen setting.

## Also wanted (2026-10-07, not designed yet - grill first)

**Admin reset.** A way to wipe high scores, campaign stars, bonus fish.
Open questions: everything at once or pick what to wipe (one level's
records? just stars?); how it's reached (hidden key combo on the start
screen vs a visible menu item) and whether it needs protecting from
accidental use (a confirm step, a password - `security.py` is an old
unfinished login prototype); whether Speed Run's `Highscore.txt` is
included.

**Show each animal's points value on the field.** Open questions: which
style - a small number badge on/next to the sprite, a coloured ring or
glow per value tier, sizing sprites by value, or a "+5" pop-up when one is
eaten (or several of these); whether hazards and the shield get a marker
too (e.g. red for deadly); whether it's always on or an Adventure/easy-
level helper. The legend already lives on the Level Info page.

**Package as a standalone app** (so it runs without Python installed).
Likely PyInstaller (or pygbag for a browser build). Things to sort out:
asset paths and the `*Highscore.txt`/progress files are relative to the
working directory, which breaks inside a bundle - assets need resolving
from the bundle, and save files need a per-user folder; builds are
per-platform (a Mac build makes a .app, Windows needs building on
Windows); an unsigned Mac app trips Gatekeeper's warning.

## Older ideas

- Flash the score
- Pic of animals eaten / counter of animals
- Reward for no lorrys/bombs ('clean run')
- Combos, e.g. five cows in a row +500
- Change highscore UI

## Playtest timings (Speed Run)

Reference runs, seconds elapsed at each score milestone:

- To score 200: 29.48, 31.9, 33.88, 34.34, 34.64
- To score 100: 11.435, 13.15, 14.301, 14.58, 14.718, 14.807, 14.517, 14.562, 14.927
- To score 30: 6.52, 6.8, 6.88, 7.04, 7.13
- To score 1: 1.91, 2.44, 2.67, 3.08, 3.44
