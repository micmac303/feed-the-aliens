# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running

```bash
.venv/bin/python main.py     # or: python main.py, with pygame installed
```

Run from the repo root — asset paths (`images/...`) and `Highscore.txt` are relative to the working directory. `.venv/` holds Python 3.12 + pygame 2.6.1; there is no `requirements.txt`, no build step, no lint config, and no test suite.

`Highscore.txt` is local player data, gitignored and not tracked. It is created from `default_scores` on first run, so a fresh clone needs no setup.

## Architecture

Two-player local-multiplayer pygame game in a single file, `main.py` (~400 lines). Player 1 uses WASD, player 2 uses the arrow keys; first to 100 points wins.

**Screen state machine.** An outer `while start:` loop contains three sequential inner loops — `while start_screen:`, `while running:`, `while end_screen:` — each with its own `pygame.display.flip()` and event handling. Transitions happen by flipping the boolean flags. Quitting sets both the inner flag and `start = False` so the outer loop also exits.

**All game state is module-level globals** (`player_score`, `playerX/Y`, `shield`, `animals`, `chosen_color`, `scores`, `trophy`, ...), but every starting value is written in exactly one place: `newRound()`. It is called once at startup and again from the `K_r` handler on the end screen, which otherwise only flips the three screen flags. **Any new piece of round state belongs in `newRound()`** — set it there rather than at module level, or it will leak across rounds. The screen flags (`start`, `start_screen`, `end_screen`) are deliberately outside it, as loop control rather than round state.

**Frame-rate independence.** `dt = (time.time() - last_time) * 60`, clamped to 1.9 to absorb the slow first frames; every movement/velocity value is multiplied by `dt`. `clock.tick(600)` caps the loop. Movement constants are deliberately asymmetric (left 5.8, right 7.0).

**Animals are plain dicts, not `pygame.sprite`.** Each has `image_name` (the path, used as the type tag), `img`, `animal_rect`, `x_pos`, `y_pos`, `x_velocity`. 27 are spawned at startup off the left edge at staggered `x` offsets. They are recycled rather than pooled: once `x_pos > 1100` (`> 3200` for the fast eagle) the dict is removed and `summonAnimal(0)` appends a fresh one. Collected animals are parked at `y_pos = 1000` instead of being removed.

**Collision/scoring is duplicated per player.** Two near-identical blocks compare `animal["image_name"]` against `animal_images[N]` / `rare_animal_images[N]` by index. Adding or reordering an entry in those lists means updating both scoring blocks *and* the hardcoded legend blits on the start screen. Rare items (star/eagle/gift) spawn on a 1-in-8 roll in `summonAnimal`.

**Shields** are consumed in `checkForStar(shield_active, score, obstacle)`: it returns the updated `(shield, score)` pair, absorbing a truck (-5) or bomb (-2) hit if the shield is up. Callers must reassign both returned values.

**High scores are times, lower is better.** `Highscore.txt` is one line of five space-separated floats sorted ascending. `loadScores()` / `saveScores()` own all file access; `loadScores()` falls back to `default_scores` and rewrites the file if it is missing, empty, corrupt, or short, so the game never crashes on bad data. On the end screen, if the round's time beats `scores[4]` (the worst kept score), the slowest entry is dropped and the file is written — guarded by `not trophy` so it saves once per round rather than on every rendered frame.

## Other files

- `highscoretest.py` — standalone scratch script for the high-score file logic; reads a score from stdin and rewrites `Highscore.txt`. Not imported by the game.
- `security.py` — unfinished tkinter login prototype, not wired into `main.py`.

A "To do" comment block at the top of `main.py` tracks the author's intended features (sound, combos, animal counter).
