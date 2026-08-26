"""Play a level headlessly, end to end, and report what happened.

    python tools/playtest.py --level 5              # play Germany to the end
    python tools/playtest.py --level 5 --shots out  # and save a PNG per screen
    python tools/playtest.py --all                  # every Adventure level
    python tools/playtest.py --speedrun             # the two-player mode
    python tools/playtest.py --level 6 --progress "1 1 1 1 1 0"
                                                    # prove a lock holds
    python tools/playtest.py --stop-at levels --progress "2 2 2 2 2 0"
                                                    # photograph a menu only

Reading a diff cannot tell you whether a new level's landmark actually
spawns, whether its rows still fit on the level-select screen, or whether
the round can be finished at all. This drives the real `main.py` through
the real screens and tells you.

How it works, and why it works this way:

  * `SDL_VIDEODRIVER=dummy` renders to an off-screen surface, so there is
    no window and no display hardware needed.
  * `main.py` runs through `exec(compile(...), g)`, which leaves every
    module global reachable in `g` afterwards - that is how the summary
    reads scores, lives and the landmark flags out of a finished round.
  * `time.time` is patched to advance a fixed 1/60s per call, so the run
    is deterministic and a 30-second level takes about a second of wall
    clock. Do not use the real clock here: `dt` would vary run to run.
  * `pygame.display.flip` is wrapped, and that wrapper is both the event
    pump and the screenshot trigger. Grabbing the surface from anywhere
    else (a driver thread, say) races the draw calls and catches
    half-drawn frames.
  * `pygame.key.get_pressed` is patched too. Posted KEYDOWN events drive
    the menus, but they do NOT update the real key-state array, and the
    in-game controls read that array - so held keys have to be faked.
  * Everything runs in a copy of the repo under a temp directory, so a
    playtest never touches your real `*Highscore.txt` or
    `AdventureProgress.txt`.

By default every level is starred so any can be picked; --progress sets an
exact campaign save instead, which is how gated content gets tested. A run
whose level the select refuses reports LOCKED rather than playing something
else, so "this should not be reachable yet" is a checkable claim.

Exit status is 0 when every requested level reached its end screen (or was
cleanly refused as locked), 1 otherwise, so this is usable as a pre-commit
check.
"""

import argparse
import os
import random
import shutil
import sys
import tempfile
import time as time_mod

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Must be set before pygame initialises a display or a mixer
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402  (import after the driver env vars are set)


# A playtest runs in a copy of the repo: the game writes its records and
# campaign progress relative to the working directory, and a test run has
# no business overwriting the player's own files
def copyRepo(dest):
    os.makedirs(dest, exist_ok=True)
    for name in ("main.py", "sounds.py"):
        shutil.copy(os.path.join(REPO_ROOT, name), dest)
    shutil.copytree(os.path.join(REPO_ROOT, "images"),
                    os.path.join(dest, "images"), dirs_exist_ok=True)
    return dest


# How many countries the campaign has, read out of the source rather than
# by importing it: main.py opens a display and builds every sound the
# moment it is imported
def countAdventureLevels():
    import ast
    tree = ast.parse(open(os.path.join(REPO_ROOT, "main.py")).read())
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign)
                and any(getattr(t, "id", None) == "ADVENTURE_LEVELS"
                        for t in node.targets)
                and isinstance(node.value, ast.List)):
            return len(node.value.elts)
    raise SystemExit("could not find ADVENTURE_LEVELS in main.py")


class Playtest:
    """One run of one level, driven to its end screen."""

    def __init__(self, level_index=0, mode_index=1, shots_dir=None,
                 seed=1234, invincible=False, max_flips=12000, unlock=True,
                 progress=None, stop_at=None):
        self.level_index = level_index      # 0-based, into mode["levels"]
        self.mode_index = mode_index        # 0-based, into MODES
        self.shots_dir = shots_dir
        self.seed = seed
        self.invincible = invincible        # pin lives, to reach the clock
        self.max_flips = max_flips
        self.unlock = unlock                # pre-star the campaign
        self.progress = progress            # explicit star counts instead
        self.stop_at = stop_at              # quit once this screen is shown
        self.stopped_at = None
        self.refused = None                 # level name the select refused
        self.g = {}                         # main.py's globals, after exec
        self.flips = 0
        self.menu_keys_sent = 0
        self.held = set()
        self.screen_flips = {}              # screen name -> frames seen
        self.shot_screens = []              # screens in the order first seen
        self.seen_info = False
        self.reached_end = False
        self.landmark_seen_at = None

    # --- the patches that make a headless, deterministic run possible ---

    def patchClock(self):
        t = [1000.0]

        def fake_time():
            t[0] += 1.0 / 60.0
            return t[0]

        time_mod.time = fake_time
        time_mod.sleep = lambda *a, **k: None
        pygame.time.get_ticks = lambda: int((t[0] - 1000.0) * 1000)

    def patchKeys(self):
        held = self.held

        class HeldKeys:
            def __getitem__(self, key):
                return key in held

        pygame.key.get_pressed = lambda: HeldKeys()

    # --- driving the menus ---

    def press(self, key):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key,
                                             mod=0, unicode=""))

    def driveMenus(self, screen_name):
        """One keypress per flip: the screen functions drain the event queue
        once per frame, so batching presses would drop all but the last."""
        if screen_name == "info":
            self.press(pygame.K_RETURN)      # ENTER starts the level from here
            return
        if screen_name == "start":
            if self.menu_keys_sent < self.mode_index:
                self.press(pygame.K_DOWN)
                self.menu_keys_sent += 1
            else:
                self.press(pygame.K_RETURN)
                self.menu_keys_sent = 0
        elif screen_name == "levels":
            if self.menu_keys_sent < self.level_index:
                self.press(pygame.K_DOWN)
                self.menu_keys_sent += 1
            elif self.menu_keys_sent == self.level_index:
                self.press(pygame.K_RETURN)      # exactly one confirm
                self.menu_keys_sent += 1
            else:
                # Confirming would have left this screen on the very next
                # frame. Still here means the row refused: it is locked, or
                # it is a bonus level whose stars have not been earned
                self.refused = self.g["mode"]["levels"][self.level_index]["name"]
                self.reached_end = True
        elif screen_name == "instructions":
            # The menu opens on Start Level. Detour through Level Info first,
            # so a playtest sees the legend and records for the level it is
            # about to play - that page is where a new level's animal table
            # shows up wrong
            if self.menu_keys_sent == 0 and not self.seen_info:
                self.press(pygame.K_DOWN)
                self.menu_keys_sent = 1
            else:
                self.press(pygame.K_RETURN)
                self.menu_keys_sent = 0

    # --- playing the level ---

    def autopilot(self):
        """Chase the nearest thing worth points, dodge nothing in particular,
        and once the landmark is up, fly for the open air above it. Enough of
        a player to score, take the landmark path and finish a level."""
        self.held.clear()
        # Every seat flies itself, using its own control keys - player 1 is
        # on WASD in Speed Run, so driving the arrow keys alone would leave
        # that UFO parked and the race would never finish
        for p in self.g["players"]:
            self.flyPlayer(p)

    def flyPlayer(self, p):
        g = self.g
        level = g["level"]
        px, py = p.x + 32, p.y + 32

        landmark = g.get("landmark")
        limit = level.get("time_limit")
        elapsed = g.get("current_time", 0) / 1000.0
        if landmark is not None:
            # Aim at the middle of the strip of sky above the roofline
            tx = landmark.sky_rect.centerx
            ty = max(landmark.sky_rect.centery, 90)
            # Climb before turning in. Sideways movement is faster than
            # vertical, so a straight diagonal run clips the building's top
            # corner - which counts as a crash, not a clearance
            if px > landmark.rect.right + 20 and py > ty + 6:
                tx = px
        elif level.get("landmark") and limit and elapsed > limit - 1.5:
            # Wait out the last second in the far corner. Parked in the sky
            # strip instead, the UFO clears the landmark on the very frame it
            # spawns - which passes, but tests nothing and shows nothing
            tx, ty = 900, 480
        else:
            target = None
            best = None
            for a in g["animals"]:
                if a.y > 900:                      # collected, parked offscreen
                    continue
                effect = level["animals"][a.image_name]["effect"]
                if effect not in ("points", "shield"):
                    continue
                if a.x < -100 or a.x > 1000:
                    continue
                value = level["animals"][a.image_name].get("value") or 3
                # Prefer close and valuable; distance dominates
                cost = abs(a.x - px) + abs(a.y - py) - value * 8
                if best is None or cost < best:
                    best, target = cost, a
            if target is None:
                return
            tx, ty = target.x + 32, target.y + 32

        if tx < px - 6:
            self.held.add(p.controls["left"])
        elif tx > px + 6:
            self.held.add(p.controls["right"])
        if ty < py - 6:
            self.held.add(p.controls["up"])
        elif ty > py + 6:
            self.held.add(p.controls["down"])

    def saveShot(self, name):
        if not self.shots_dir:
            return
        os.makedirs(self.shots_dir, exist_ok=True)
        path = os.path.join(self.shots_dir, name)
        pygame.image.save(pygame.display.get_surface(), path)

    # --- the flip wrapper: event pump, autopilot and camera in one place ---

    def onFlip(self):
        self.flips += 1
        screen_name = self.g.get("screen_name")

        # Post QUIT every frame once the round is over, not once: a screen
        # function that returns partway through its event batch discards the
        # events it had already pulled off the queue, QUIT included
        if self.reached_end:
            self.held.clear()
            pygame.event.post(pygame.event.Event(pygame.QUIT))
            return

        # How long this screen has been up. Menus are driven from the third
        # frame on, which leaves a settled frame to photograph: a menu keyed
        # on its first flip can vanish before it is ever captured
        seen = self.screen_flips.get(screen_name, 0) + 1
        self.screen_flips[screen_name] = seen
        if seen == 1 and screen_name not in self.shot_screens:
            self.shot_screens.append(screen_name)
        if seen == 2 and screen_name != "game":
            self.saveShot("%02d-%s.png"
                          % (self.shot_screens.index(screen_name) + 1,
                             screen_name))
        if screen_name == "info":
            self.seen_info = True
        # Stopping at a menu is a successful run in its own right: it is how
        # a locked or hidden level gets inspected without playing anything
        if screen_name == self.stop_at and seen >= 2:
            self.stopped_at = screen_name
            self.reached_end = True
            return

        if screen_name == "game":
            if self.landmark_seen_at is None and self.g.get("landmark"):
                self.landmark_seen_at = self.flips
            if self.invincible:
                for p in self.g["players"]:
                    p.lives = self.g["mode"]["lives"]
            self.autopilot()
            if seen == 120:
                self.saveShot("%02d-game.png"
                              % (self.shot_screens.index("game") + 1))
            # The landmark frame is the interesting one - grab it once the
            # building has actually been drawn
            if (self.landmark_seen_at is not None
                    and self.flips == self.landmark_seen_at + 8):
                self.saveShot("landmark.png")
        elif screen_name == "end":
            # Not on the first frame: flip() at the top of a screen's loop
            # publishes what the *previous* screen drew, so a shot taken the
            # moment "end" appears is really the last frame of the game
            if seen >= 2 and not self.reached_end:
                self.reached_end = True
                self.saveShot("%02d-end.png"
                              % (self.shot_screens.index("end") + 1))
        elif screen_name == "start" and self.reached_end:
            # The end screen is the finish line. Anything past it would be a
            # second round, which would overwrite the globals this run is
            # about to report on
            pass
        elif seen >= 3:
            self.held.clear()
            self.driveMenus(screen_name)

        if self.flips > self.max_flips:
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    def run(self, workdir):
        os.chdir(workdir)
        # main.py does `import sounds`, and the copy is what should be found
        if workdir not in sys.path:
            sys.path.insert(0, workdir)
        if self.progress is not None:
            # An exact campaign state, for testing what is locked and what
            # a partly-starred save can reach
            with open("AdventureProgress.txt", "w") as f:
                f.write(self.progress + "\n")
        elif self.unlock:
            # Star every level so the level select lets us pick any of them
            with open("AdventureProgress.txt", "w") as f:
                f.write(" ".join(["3"] * 30) + "\n")

        self.patchClock()
        self.patchKeys()
        random.seed(self.seed)

        real_flip = pygame.display.flip

        def flip_wrapper():
            real_flip()
            self.onFlip()

        pygame.display.flip = flip_wrapper

        self.g = {"__name__": "__main__",
                  "__file__": os.path.join(workdir, "main.py")}
        source = open(os.path.join(workdir, "main.py")).read()
        try:
            exec(compile(source, "main.py", "exec"), self.g)
        except SystemExit:
            pass
        finally:
            pygame.display.flip = real_flip
        return self.summary(workdir)

    def summary(self, workdir):
        g = self.g
        level = g.get("level", {})
        players = g.get("players", [])
        records = "(none)"
        path = level.get("highscore_file")
        if path and os.path.exists(os.path.join(workdir, path)):
            records = open(os.path.join(workdir, path)).read().strip()
        elapsed = round(g.get("current_time", 0) / 1000, 2)
        limit = level.get("time_limit")
        if g.get("landmark_crashed"):
            ended_by = "crashed into the landmark"
        elif g.get("landmark_cleared"):
            ended_by = "cleared the landmark"
        elif any(p.lives is not None and p.lives <= 0 for p in players):
            ended_by = "out of lives"
        elif limit and elapsed >= limit:
            ended_by = "clock ran out"
        elif players and g.get("mode", {}).get("ends_on_goal"):
            ended_by = "reached the point goal"
        else:
            ended_by = "unknown"
        return {
            "level": level.get("name") or "Speed Run",
            "reached_end": self.reached_end,
            "stopped_at": self.stopped_at,
            "refused": self.refused,
            "ended_by": ended_by,
            "flips": self.flips,
            "score": [p.score for p in players],
            "lives": [p.lives for p in players],
            "elapsed": round(g.get("current_time", 0) / 1000, 2),
            "time_limit": level.get("time_limit"),
            "has_landmark": bool(level.get("landmark")),
            "landmark_spawned": self.landmark_seen_at is not None,
            "landmark_cleared": g.get("landmark_cleared"),
            "landmark_crashed": g.get("landmark_crashed"),
            "records": records,
        }


def describe(result):
    ok = result["reached_end"]
    lines = ["%s  %s" % ("PASS" if ok else "FAIL", result["level"])]
    if result.get("refused"):
        return ("LOCKED  %s\n    the level select refused to enter it - "
                "not unlocked by this campaign save" % result["refused"])
    if result.get("stopped_at"):
        lines.append("    stopped at the %s screen as asked" % result["stopped_at"])
        return "\n".join(lines)
    lines.append("    score %s   lives %s   elapsed %ss/%s   ended: %s"
                 % (result["score"], result["lives"], result["elapsed"],
                    result["time_limit"], result["ended_by"]))
    if result["has_landmark"]:
        lines.append("    landmark: spawned=%s cleared=%s crashed=%s"
                     % (result["landmark_spawned"], result["landmark_cleared"],
                        result["landmark_crashed"]))
        # A landmark that never appeared is only suspicious when the clock
        # actually got there - the autopilot dying first is just bad flying
        reached_clock = (result["time_limit"]
                         and result["elapsed"] >= result["time_limit"])
        if reached_clock and not result["landmark_spawned"]:
            lines.append("    ! the clock ran out but the landmark never "
                         "appeared")
        elif not result["landmark_spawned"]:
            lines.append("    (round ended before the landmark was due - "
                         "use --invincible to test it)")
    lines.append("    records file: %s" % result["records"])
    if not ok:
        lines.append("    ! never reached the end screen (%d frames)"
                     % result["flips"])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--level", type=int, default=1,
                        help="Adventure level number, 1-based (default 1)")
    parser.add_argument("--all", action="store_true",
                        help="play every Adventure level in turn")
    parser.add_argument("--speedrun", action="store_true",
                        help="play the two-player Speed Run mode instead")
    parser.add_argument("--shots", metavar="DIR",
                        help="save a PNG per screen into DIR")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--invincible", action="store_true",
                        help="pin lives, so the clock (and the landmark) is "
                             "what ends the round")
    parser.add_argument("--progress", metavar="STARS",
                        help="exact campaign save to start from, e.g. "
                             "\"2 2 2 2 2 0\" - by default every level is "
                             "starred so any of them can be picked")
    parser.add_argument("--stop-at", metavar="SCREEN", dest="stop_at",
                        choices=("start", "levels", "instructions", "info"),
                        help="screenshot this menu and quit, without playing")
    parser.add_argument("--keep", action="store_true",
                        help="keep the temp copy of the repo and print its path")
    args = parser.parse_args(argv)

    workdir = copyRepo(tempfile.mkdtemp(prefix="playtest-"))
    mode_index = 0 if args.speedrun else 1

    level_count = 1 if args.speedrun else countAdventureLevels()

    if args.speedrun:
        targets = [0]
    elif args.all:
        targets = list(range(level_count))
    else:
        targets = [args.level - 1]

    results = []
    for index in targets:
        if index < 0 or index >= level_count:
            parser.error("level %d does not exist (there are %d)"
                         % (index + 1, level_count))
        shots = args.shots
        if shots and len(targets) > 1:
            shots = os.path.join(shots, "level%d" % (index + 1))
        # A fresh process per level would be cleaner, but pygame's event
        # queue survives between exec runs in one process - so clear it, or
        # the previous run's shutdown QUIT kills the next run instantly.
        # Nothing to clear before the first run: main.py calls pygame.init()
        if pygame.get_init():
            pygame.event.clear()
        test = Playtest(level_index=index, mode_index=mode_index,
                        shots_dir=shots, seed=args.seed,
                        invincible=args.invincible, progress=args.progress,
                        stop_at=args.stop_at)
        result = test.run(workdir)
        results.append(result)
        print(describe(result))

    if args.keep:
        print("workdir kept: %s" % workdir)
    else:
        shutil.rmtree(workdir, ignore_errors=True)
    if args.shots:
        print("screenshots: %s" % os.path.abspath(args.shots))
    return 0 if all(r["reached_end"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
