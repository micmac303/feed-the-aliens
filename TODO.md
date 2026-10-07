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
