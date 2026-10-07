# To do

## Next: difficulty curve (agreed 2026-10-07)

Levels get harder as the campaign goes on. Each level dict sets its own
`speed` by hand on the jet (top-half hazard) and the ground hazard - a
table edit, no new code. Bonus/secret levels are the hardest.

| Level              | Jet | Ground |
|--------------------|-----|--------|
| UK                 | 7   | 4      |
| France             | 8   | 4      |
| Italy              | 9   | 5      |
| Spain              | 10  | 5      |
| Germany            | 11  | 6      |
| Ireland (bonus)    | 12  | 6      |
| Poland (secret)    | 13  | 7      |
| Mediterranean      | 14  | 7      |  (battleship / submarine)

Today every jet is 12 and every ground hazard the default 5. Faster
hazards also come round more often (same `recycle_x`), so speed and
frequency rise together. Keep time limit, goal, lives and spawn mix as
they are; keep existing records and stars. Check with
`tools/playtest.py --all`, then hand-play Poland and the Mediterranean to
be sure 13-14 is still dodgeable. Update CLAUDE.md.

Later ideas: jets speeding up during a level as the clock runs down;
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
