# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running

```bash
.venv/bin/python main.py     # or: python main.py, with pygame installed
```

Run from the repo root — asset paths (`images/...`) and `Highscore.txt` are relative to the working directory. `.venv/` holds Python 3.14 + **pygame-ce** (the maintained community fork; same `import pygame` API — never install the stalled `pygame` package alongside it). `requirements.txt` has the one dependency: `pip install -r requirements.txt` into a fresh venv is the full setup. There is no build step, no lint config, and no test suite.

`Highscore.txt` is local player data, gitignored and not tracked. It is created from `default_scores` on first run, so a fresh clone needs no setup.

## Architecture

Two-player local-multiplayer pygame game in a single file, `main.py` (~400 lines). Player 1 uses WASD, player 2 uses the arrow keys; first to 100 points wins.

**Screen state machine.** Three functions — `runStartScreen()`, `runGame()`, `runEndScreen()` — each own one screen: its loop, its drawing, its `pygame.display.flip()` and its event handling. Each returns the name of the next screen (`"game"`, `"end"`, `"start"` or `"quit"`), and the small dispatch loop at the bottom of the file hops between them until one returns `"quit"`. A transition is just a `return`; there are no screen flags to keep in sync. `runGame()` writes `current_time`/`last_time` and `runEndScreen()` writes `scores`/`trophy` through `global` declarations.

**Simulation and rendering are separate.** `updateGame(all_intents, dt)` advances the whole sim — player movement, animal movement, recycling, collisions, scoring — with no drawing and no input reads; it is what a headless server (or a test) runs. Input reaches the sim only as **intent dicts** (`{"left"/"right"/"up"/"down": bool}`, one per player, aligned with `players` by index): `runGame()` reads the keyboard and converts it through `keyboardIntents(pressed, controls)`, and anything that produces the same dict (a replay, an AI, a network packet) can drive a player instead. **New sim behaviour goes in `updateGame()`/the classes' update methods; drawing stays in the `run*` screen functions.**

**Game state lives in module-level globals** (`players`, `animals`, `rng`, `chosen_color`, `scores`, `trophy`, ...), but every starting value is written in exactly one place: `newRound(seed=None)`. It is called once at startup and again from the `K_r` handler in `runEndScreen()`, just before it returns `"start"`. **Any new piece of round state belongs in `newRound()`** — for per-player state that means `Player.__init__` (newRound builds fresh `Player` objects each round, which is what resets them); anything else is set in `newRound()` directly. **All sim randomness goes through `rng`** (a `random.Random` built in `newRound()` from the optional seed — spawns, gift coin flips, background colour), so a seeded round replays exactly; never call the module-level `random` functions from sim code.

**Players live in the `players` list** — instances of the `Player` class: score, position, shield, hitbox, plus the identity that tells them apart (`number`, control keys, colours, HUD placement), passed as constructor arguments in `newRound()`. The sim (`updateGame`, `collect`) never assumes a player count; only `newRound()` and the end-screen layout know there are two. `update(intents, dt)` syncs `self.rect` (the 32x32 hitbox at the centre of the 64x64 sprite) to the *pre-move* position — the same one-frame lag as `Animal.update` — then moves; `draw(screen)` and `draw_hud(screen)` are read-only rendering, so a headless sim never calls them.

**Frame-rate independence.** `dt = (time.time() - last_time) * 60`, clamped to 1.9 to absorb the slow first frames; every movement/velocity value is multiplied by `dt`. `clock.tick(600)` caps the loop. Movement constants are deliberately asymmetric (left 5.8, right 7.0).

**Animals are instances of the `Animal` class** (a plain class, not `pygame.sprite`). The constructor rolls the type (1-in-8 from the rare pool) and sets `image_name` (the path, used as the type tag), the shared `img` surface, its own `rect`, position, `speed` and `recycle_x`. `newRound()` spawns 27 as `Animal(slot=i)`, staggered off the left edge. They are recycled rather than pooled: once `x > recycle_x` the object is removed and a fresh `Animal()` appended. Collected animals are parked at `y = 1000` instead of being removed. `update(dt)` syncs the hitbox *before* moving, so collisions track the previous frame's drawn position; below `x = -1000` everything moves at 5 so the spawn queue keeps its pacing.

**Scoring is table-driven.** The `ANIMALS` dict maps each image path to `{effect, value, legend}`, where `effect` is one of `points` / `obstacle` / `opponent` / `shield` / `random`. `Player.collect(image_name, opponents)` looks up the table and mutates the players directly — `opponents` is every other player (the `opponent` effect loops over them, so with one player it is a no-op), and the collision loop in `updateGame()` builds it per collision. Shields are consumed in the `obstacle` branch: the shield absorbs the hit, otherwise the (negative) table value is applied. The start screen legend is drawn by looping over `legend_layout` (image path + two positions) and takes its label text from `ANIMALS`, so point values cannot drift out of step with the legend.

**To add an animal:** add an `ANIMALS` entry, add the path to `animal_images` or `rare_animal_images` (the spawn pools; rare spawns on a 1-in-8 roll in `Animal.__init__`), and add a `legend_layout` row. A startup assertion fails loudly if a spawnable animal has no `ANIMALS` entry. Nothing is index-coupled any more, so reordering the pools is safe. `EAGLE` is a named constant because it is special-cased in `Animal.__init__` (`speed` 10 rather than 5, `recycle_x` 3200 rather than 1100).

**High scores are times, lower is better.** `Highscore.txt` is one line of five space-separated floats sorted ascending. `loadScores()` / `saveScores()` own all file access; `loadScores()` falls back to `default_scores` and rewrites the file if it is missing, empty, corrupt, or short, so the game never crashes on bad data. On the end screen, if the round's time beats `scores[4]` (the worst kept score), the slowest entry is dropped and the file is written — guarded by `not trophy` so it saves once per round rather than on every rendered frame.

## Other files

- `highscoretest.py` — standalone scratch script for the high-score file logic; reads a score from stdin and rewrites `Highscore.txt`. Not imported by the game.
- `security.py` — unfinished tkinter login prototype, not wired into `main.py`.

A "To do" comment block at the top of `main.py` tracks the author's intended features (sound, combos, animal counter).
