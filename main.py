import random
import time
import pygame

import sounds

# A small mixer buffer keeps effects snappy (a big one plays them noticeably
# after the collision they belong to); must be set before pygame.init()
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()
# Synthesise every effect up front; with no audio device the game runs silent
sounds.init()

# vsync makes flip() block until the display actually refreshes, so frames
# land exactly on the refresh cadence. Pacing with a timer instead (the old
# clock.tick) drifts against the refresh rate and skips a frame roughly once
# a second - visible as the whole field jumping forward. SCALED is required
# for vsync in pygame-ce; the window looks the same.
screen = pygame.display.set_mode((1000, 600), pygame.SCALED, vsync=1)
pygame.display.set_icon(pygame.image.load("images/006-ufo-1.png"))
pygame.display.set_caption("Feed The Aliens")

timer_font = pygame.font.SysFont("impact", 60)
huge_font = pygame.font.SysFont("impact", 352)
score_font = pygame.font.SysFont("impact", 120)
points_font = pygame.font.SysFont("impact", 32)
tagline_font = pygame.font.SysFont("impact", 22)
instruction_font = pygame.font.SysFont("ebrima", 38)
space_font = pygame.font.SysFont("impact", 40)
title_font = pygame.font.SysFont("impact", 90)

clock = pygame.time.Clock()

# Per-round state (the players list, animals, rng, scores, ...) is created by
# newRound() below, so each starting value is written in exactly one place.

colours = [(49, 201, 235), (34, 52, 153), (50, 92, 166), (89, 125, 189), (89, 146, 189), (84, 180, 199),  # Blue
           (163, 11, 11), (207, 41, 41), (194, 39, 98), (199, 42, 94), (168, 5, 5), (189, 0, 126),  # Red
           (122, 0, 156), (145, 24, 196), (171, 34, 199), (77, 13, 181), (120, 76, 207), (96, 3, 171),  # Purple
           (171, 173, 184), (194, 197, 209), (226, 204, 227), (173, 174, 179), (204, 197, 212), (107, 90, 91),  # Gray
           ]

# Highscores are player data, not source, so the files below are not in git.
# Each mode owns its own file and its own starting defaults - Speed Run
# tracks times (lower is better), Adventure tracks points (higher is better)


def saveScores(path, score_list):
    with open(path, "w") as scores_file:
        scores_file.write(" ".join(str(x) for x in score_list))


# Recreates the file if it is missing, empty, corrupt or short, so the game
# never crashes on bad data.
def loadScores(path, defaults):
    try:
        with open(path, "r") as scores_file:
            loaded = sorted(map(float, scores_file.read().split()))[:5]
        if len(loaded) < 5:
            raise ValueError("not enough scores")
        return loaded
    except (OSError, ValueError):
        saveScores(path, defaults)
        return list(defaults)


# Campaign progress is player data too (gitignored like the highscores):
# one star count (0-3) per level, space-separated, aligned with the mode's
# levels list. 0 = never completed; 1+ = completed, so the next level is
# unlocked. Missing/corrupt/short files degrade to zeros, and the list is
# padded to the level count so newly added levels appear as uncompleted.
def loadProgress(mode):
    if not mode.get("progress_file"):
        return [0] * len(mode["levels"])
    try:
        with open(mode["progress_file"], "r") as progress_file:
            stars = [min(max(int(x), 0), 3) for x in progress_file.read().split()]
    except (OSError, ValueError):
        stars = []
    return (stars + [0] * len(mode["levels"]))[:len(mode["levels"])]


def saveProgress(mode, stars):
    with open(mode["progress_file"], "w") as progress_file:
        progress_file.write(" ".join(str(s) for s in stars))


# Images are loaded from disk once and reused. The instructions screen
# redraws ten legend images every frame, and every animal spawn needs a
# surface.
image_cache = {}


def loadImage(path):
    if path not in image_cache:
        image_cache[path] = pygame.image.load(path)
    return image_cache[path]


player_img = loadImage("images/001-ufo.png")
player2_img = loadImage("images/021-ufo.png")

animals = []

# A level's finish line: None until level["time_limit"] elapses, then a
# Landmark, a genuine obstacle rather than a target - a UFO must fly over
# its roofline to finish; touching the building itself crashes.
# landmark_cleared/landmark_crashed flip on those two outcomes - runGame()
# reads them the same way it reads lives/score, rather than updateGame()
# deciding a screen transition itself.
landmark = None
landmark_cleared = False
landmark_crashed = False

# Sound events the sim emits, one name per thing that happened ("collect",
# "explosion", ...). The sim only ever appends names here - it never touches
# the mixer - and runGame() drains the list after each sim step and plays
# them, so a headless server can forward or ignore the same list. Cleared in
# newRound() so a fresh round never replays a dead round's leftovers.
sound_events = []

# A level is the *content* of a round: the animals table, the spawn pools,
# the legend layout and the point goal. The modes table further down carries
# the *rules* (player count, highscore policy) and points at a list of
# levels. Per the roadmap, per-level spawn scripts and hazards will hang off
# these dicts too.
#
# The "animals" table maps each image path to what collecting it does and
# how the instructions screen legend describes it:
#   points   - add value to the collecting player's score
#   obstacle - add value (negative) unless a shield absorbs it
#   opponent - add value (negative) to the *other* player's score
#   shield   - grant a single use shield
#   random   - plus or minus value, a coin flip
#   deadly   - the player explodes and loses a life (a shield absorbs the
#              hit); only meaningful in modes that grant lives
# An entry may also carry "speed" and "recycle_x" (defaults 5 and 1100) for
# animals that fly fast and far off the right edge before recycling, and
# "y_range" (defaults (120, 500), the field's full vertical band) to confine
# an animal to part of it, e.g. only the top or bottom half.
#
# "legend_layout" is where each animal sits on the instructions screen:
# (image, image position, label position). Label text comes from "animals",
# so point values cannot drift out of step with the legend.
#
# To add an animal to a level: add an "animals" entry, add the path to one
# of its spawn pools ("rare_animal_images" comes up on a 1 in 8 roll), and
# give it a legend_layout spot. A startup assertion below fails loudly if a
# spawnable animal has no table entry.
CLASSIC_LEVEL = {
    "name": None,  # Speed Run shows no level name
    "point_goal": 100,
    "animals": {
        "images/003-cow.png": {"effect": "points", "value": 3, "legend": "+3"},
        "images/001-hen.png": {"effect": "points", "value": 1, "legend": "+1"},
        "images/003-elephant.png": {"effect": "points", "value": 5, "legend": "+5"},
        "images/002-rabbit.png": {"effect": "points", "value": 1, "legend": "+1"},
        "images/001-eagle.png": {"effect": "points", "value": 8, "legend": "+8",
                                 "speed": 10, "recycle_x": 3200},
        "images/002-truck.png": {"effect": "obstacle", "value": -5, "legend": "-5"},
        "images/001-bomb.png": {"effect": "obstacle", "value": -2, "legend": "-2"},
        "images/003-tiger.png": {"effect": "opponent", "value": -3, "legend": "-3 to opponent"},
        "images/shield.png": {"effect": "shield", "value": None, "legend": "Single use shield"},
        "images/001-gift.png": {"effect": "random", "value": 10, "legend": "Random +10 / -10"},
    },
    "animal_images": ["images/003-cow.png", "images/001-hen.png", "images/003-elephant.png",
                      "images/002-rabbit.png", "images/001-bomb.png", "images/002-truck.png",
                      "images/003-tiger.png"],
    "rare_animal_images": ["images/shield.png", "images/001-eagle.png", "images/001-gift.png"],
    "legend_layout": [
        ("images/001-eagle.png", (30, 30), (100, 40)),
        ("images/003-elephant.png", (30, 130), (100, 140)),
        ("images/003-cow.png", (30, 230), (100, 240)),
        ("images/001-hen.png", (30, 330), (100, 340)),
        ("images/002-rabbit.png", (30, 430), (100, 440)),
        ("images/002-truck.png", (910, 30), (860, 40)),
        ("images/001-bomb.png", (910, 130), (860, 140)),
        ("images/001-gift.png", (340, 330), (420, 345)),
        ("images/003-tiger.png", (340, 400), (420, 410)),
        ("images/shield.png", (340, 470), (420, 480)),
    ],
}

# Level 1 of the Adventure world tour. All art is the real UK set.
UK_LEVEL = {
    "name": "Level 1 - United Kingdom",
    "point_goal": 100,
    "time_limit": 30,
    # 2-star threshold; defaults to double point_goal when unset
    "two_star_score": 150,
    # 3-star threshold (also requires no lives lost); defaults to
    # two_star_score when unset
    "three_star_score": 175,
    # A fixed background instead of newRound()'s random pick
    "background_color": (255, 255, 255),
    # Optional - the in-game score and timer text colour; default is the
    # player's own colour for the score and black for the timer
    "score_color": (200, 16, 46),
    "timer_color": (34, 52, 153),
    # Optional - shown next to the level name on instructions and next to
    # the timer in game. Levels without a flag simply don't set this key
    "flag": "images/uk.png",
    # Optional - once time_limit elapses, this appears on the field instead
    # of the round ending outright; a UFO must reach it to finish. Levels
    # without a landmark keep the old behaviour: time_limit ends it directly
    "landmark": "images/big-ben.png",
    "landmark_name": "Big Ben",
    "animals": {
        "images/hedgehog.png": {"effect": "points", "value": 1, "legend": "Hedgehog +1"},
        "images/squirrel.png": {"effect": "points", "value": 2, "legend": "Squirrel +2"},
        "images/fox.png": {"effect": "points", "value": 5, "legend": "Fox +5"},
        "images/swan.png": {"effect": "points", "value": 10, "legend": "Swan +10",
                            "speed": 10, "recycle_x": 3200},
        "images/jet.png": {"effect": "deadly", "value": None, "legend": "-1 life",
                           "speed": 12, "recycle_x": 3200, "y_range": (120, 310)},
        "images/bus.png": {"effect": "deadly", "value": None, "legend": "-1 life",
                           "y_range": (310, 500)},
        "images/shield.png": {"effect": "shield", "value": None, "legend": "Single use shield"},
    },
    "animal_images": ["images/hedgehog.png", "images/squirrel.png", "images/fox.png",
                      "images/jet.png", "images/bus.png"],
    "rare_animal_images": ["images/shield.png", "images/swan.png"],
    "legend_layout": [
        ("images/swan.png", (30, 30), (100, 40)),
        ("images/fox.png", (30, 130), (100, 140)),
        ("images/squirrel.png", (30, 230), (100, 240)),
        ("images/hedgehog.png", (30, 330), (100, 340)),
        ("images/jet.png", (910, 30), (790, 40)),
        ("images/bus.png", (910, 130), (790, 140)),
        ("images/shield.png", (340, 400), (420, 410)),
    ],
}

# Level 2. The same cast as the UK, with the cockerel - France's national
# symbol - standing in for the swan, and the boar standing in for the fox.
FRANCE_LEVEL = {
    "name": "Level 2 - France",
    "point_goal": 100,
    "time_limit": 30,
    "two_star_score": 150,
    "three_star_score": 175,
    # Navy, like the France football kit, rather than the UK's white
    "background_color": (16, 34, 77),
    "score_color": (239, 65, 53),
    "timer_color": (255, 255, 255),
    "flag": "images/france.png",
    "landmark": "images/eiffel-tower.png",
    "landmark_name": "the Eiffel Tower",
    "animals": {
        "images/hedgehog.png": {"effect": "points", "value": 1, "legend": "Hedgehog +1"},
        "images/squirrel.png": {"effect": "points", "value": 2, "legend": "Squirrel +2"},
        "images/boar.png": {"effect": "points", "value": 5, "legend": "Boar +5"},
        "images/cockerel.png": {"effect": "points", "value": 10, "legend": "Cockerel +10",
                            "speed": 10, "recycle_x": 3200},
        "images/jet.png": {"effect": "deadly", "value": None, "legend": "-1 life",
                           "speed": 12, "recycle_x": 3200, "y_range": (120, 310)},
        "images/paris-tram.png": {"effect": "deadly", "value": None, "legend": "-1 life",
                           "y_range": (310, 500)},
        "images/shield.png": {"effect": "shield", "value": None, "legend": "Single use shield"},
    },
    "animal_images": ["images/hedgehog.png", "images/squirrel.png", "images/boar.png",
                      "images/jet.png", "images/paris-tram.png"],
    "rare_animal_images": ["images/shield.png", "images/cockerel.png"],
    "legend_layout": [
        ("images/cockerel.png", (30, 30), (100, 40)),
        ("images/boar.png", (30, 130), (100, 140)),
        ("images/squirrel.png", (30, 230), (100, 240)),
        ("images/hedgehog.png", (30, 330), (100, 340)),
        ("images/jet.png", (910, 30), (790, 40)),
        ("images/paris-tram.png", (910, 130), (790, 140)),
        ("images/shield.png", (340, 400), (420, 410)),
    ],
}

# Level 3. The same cast again, with the stallion standing in for the
# swan/cockerel and the fox back in its UK slot.
ITALY_LEVEL = {
    "name": "Level 3 - Italy",
    "point_goal": 100,
    "time_limit": 30,
    "two_star_score": 150,
    "three_star_score": 175,
    "background_color": (0, 146, 70),
    "score_color": (255, 255, 255),
    "timer_color": (206, 43, 55),
    "flag": "images/italy.png",
    "landmark": "images/colosseum.png",
    "landmark_name": "the Colosseum",
    "animals": {
        "images/hedgehog.png": {"effect": "points", "value": 1, "legend": "Hedgehog +1"},
        "images/squirrel.png": {"effect": "points", "value": 2, "legend": "Squirrel +2"},
        "images/fox.png": {"effect": "points", "value": 5, "legend": "Fox +5"},
        "images/stallion.png": {"effect": "points", "value": 10, "legend": "Stallion +10",
                            "speed": 10, "recycle_x": 3200},
        "images/jet.png": {"effect": "deadly", "value": None, "legend": "-1 life",
                           "speed": 12, "recycle_x": 3200, "y_range": (120, 310)},
        "images/vespa.png": {"effect": "deadly", "value": None, "legend": "-1 life",
                           "y_range": (310, 500)},
        "images/shield.png": {"effect": "shield", "value": None, "legend": "Single use shield"},
    },
    "animal_images": ["images/hedgehog.png", "images/squirrel.png", "images/fox.png",
                      "images/jet.png", "images/vespa.png"],
    "rare_animal_images": ["images/shield.png", "images/stallion.png"],
    "legend_layout": [
        ("images/stallion.png", (30, 30), (100, 40)),
        ("images/fox.png", (30, 130), (100, 140)),
        ("images/squirrel.png", (30, 230), (100, 240)),
        ("images/hedgehog.png", (30, 330), (100, 340)),
        ("images/jet.png", (910, 30), (790, 40)),
        ("images/vespa.png", (910, 130), (790, 140)),
        ("images/shield.png", (340, 400), (420, 410)),
    ],
}

# Adventure's world tour, one country per level. Spain, Germany and
# friends append here; continent chapters will group lists like this one.
ADVENTURE_LEVELS = [UK_LEVEL, FRANCE_LEVEL, ITALY_LEVEL]

# A mode is one rules configuration for a round: how many players, which
# levels, and whether the round's time counts for the high scores. The mode
# select screen picks one; the chosen mode persists across rounds (newRound()
# reads it, nothing resets it). A rule that varies by mode belongs in this
# table, not in an if somewhere - a new mode is a new entry.
MODES = [
    {"name": "Speed Run",
     "tagline": "The first to 100 points wins",
     "player_count": 2,
     "saves_highscore": True,
     "score_type": "time",  # lower is better
     "highscore_file": "Highscore.txt",
     "default_scores": [30.0, 40.0, 50.0, 60.0, 70.0],
     # Reaching the goal ends the race immediately - that is the whole game
     "ends_on_goal": True,
     # No lives in a race - deadly animals only exist in Adventure levels
     "lives": None,
     # One level and no campaign, so nothing to remember between sessions
     "progress_file": None,
     "levels": [CLASSIC_LEVEL]},
    {"name": "Adventure",
     "tagline": "One player - eat your way around the world",
     "player_count": 1,
     "saves_highscore": True,
     "score_type": "points",  # higher is better
     "highscore_file": "AdventureHighscore.txt",
     "default_scores": [10.0, 20.0, 30.0, 40.0, 50.0],
     # The point goal does not end the round - the player keeps scoring
     # against the clock/lives, chasing as high a total as possible
     "ends_on_goal": False,
     "lives": 3,
     # Star ratings per level (0-3); a starred level unlocks the next one
     "progress_file": "AdventureProgress.txt",
     "levels": ADVENTURE_LEVELS},
]
mode = MODES[0]
# Which of mode["levels"] is active - the campaign position for level-based
# modes (Adventure). Reset to 0 whenever a mode is freshly chosen (runStartScreen);
# left alone on a replay (newRound() with no other change) and advanced by
# runEndScreen's next-level key, so it survives exactly like mode does.
level_index = 0

# A spawnable animal with no table entry would silently score nothing
for m in MODES:
    for lvl in m["levels"]:
        for name in lvl["animal_images"] + lvl["rare_animal_images"]:
            assert name in lvl["animals"], "no animals entry for " + name


# One drifting animal. The type is rolled at construction from the active
# level's pools: 1 in 8 spawns come from the rare pool. What an animal *does*
# when collected stays in the level's animals table - the object only carries
# movement state and its type tag.
class Animal:
    def __init__(self, slot=0, start_offset=1000):
        if rng.randint(1, 8) == 8:
            self.image_name = level["rare_animal_images"][rng.randint(0, len(level["rare_animal_images"]) - 1)]
        else:
            self.image_name = level["animal_images"][rng.randint(0, len(level["animal_images"]) - 1)]
        # The surface is shared between animals of the same type - it is only
        # ever blitted, never drawn into - but get_rect() gives each one its
        # own hitbox
        self.img = loadImage(self.image_name)
        self.rect = self.img.get_rect()
        # slot staggers the 27 starting animals off the left edge. start_offset
        # only matters for the initial newRound() batch (recycled animals keep
        # the default 1000, same as before) - a smaller one shortens how long
        # the field stays empty right after a round begins
        self.x = ((slot + 1) * -81) - start_offset
        animal_type = level["animals"][self.image_name]
        # Most animals spawn anywhere in the field's vertical band; the table
        # entry can restrict that (the jet only flies the top half, the bus
        # only the bottom half)
        min_y, max_y = animal_type.get("y_range", (120, 500))
        self.y = rng.randint(min_y, max_y)
        # Most animals drift at 5 and recycle just off the right edge; the
        # table entry can say otherwise (the eagle and the swan fly fast, and
        # far off the edge before recycling)
        self.speed = animal_type.get("speed", 5)
        self.recycle_x = animal_type.get("recycle_x", 1100)

    def update(self, dt):
        # The hitbox syncs to the pre-move position, so a collision tracks the
        # previous frame's drawn spot - same as the original dict-based loop
        self.rect.x = self.x
        self.rect.y = self.y
        # Left of x = -1000 everything moves at 5 so the staggered spawn queue
        # keeps its pacing; an eagle only speeds up once it is clear of it
        self.x += (self.speed if self.x >= -1000 else 5) * dt

    def draw(self, screen):
        screen.blit(self.img, (self.x, self.y))


# A level's finish line: fixed position, no movement, no recycling - the
# opposite of Animal. Half native size, snug against the bottom-left
# corner. Its own rect is the building - a solid obstacle, not a target -
# and sky_rect covers only the strip of open sky directly above the
# roofline. Entering sky_rect clears it (flies over); entering rect
# crashes into it.
class Landmark:
    def __init__(self, image_path):
        full = loadImage(image_path)
        self.img = pygame.transform.smoothscale(full, (full.get_width() // 2, full.get_height() // 2))
        self.x = 0
        self.y = 600 - self.img.get_height()
        self.rect = pygame.Rect(self.x, self.y, self.img.get_width(), self.img.get_height())
        self.sky_rect = pygame.Rect(self.x, 0, self.img.get_width(), self.y)

    def draw(self, screen):
        screen.blit(self.img, (self.x, self.y))


# One UFO: score, position, shield, plus the controls and HUD placement that
# tell the two players apart. Both players are instances of this class, so
# there is no per-player duplication; newRound() builds two fresh ones, which
# is what resets score/position/shield each round.
class Player:
    def __init__(self, img, start_x, number, controls, controls_text, color, score_color, hud_x, score_x, lives=None, start_y=30):
        # Identity: fixed for the whole session
        self.img = img
        # Half-size copy for the lives row in the top right corner
        self.small_img = pygame.transform.smoothscale(img, (32, 32))
        self.number = number              # 1-based, and the future network id
        self.label = "PLAYER " + str(number)
        self.controls = controls          # {"left"/"right"/"up"/"down": key constant}
        self.controls_text = controls_text
        self.color = color
        self.score_color = score_color
        self.hud_x = hud_x
        self.score_x = score_x
        # Round state: starts fresh because each round gets a fresh Player
        self.x = start_x
        self.y = start_y
        self.score = 0
        self.shield = False
        # None means the mode has no lives concept (deadly animals then
        # cannot end the round); explosion_timer counts down in frames while
        # the death explosion is on screen
        self.lives = lives
        self.explosion_timer = 0
        self.rect = img.get_rect()

    # Movement constants are deliberately asymmetric (left 5.8, right 7.0).
    # intents is {"left"/"right"/"up"/"down": bool} - the sim never touches
    # the keyboard, so a replay, an AI or a network packet can drive a player
    # by producing the same dict
    def move(self, intents, dt):
        if intents["left"] and self.x > 0:
            self.x -= 5.8 * dt
        if intents["right"] and self.x < 936:
            self.x += 7 * dt
        if intents["up"] and self.y > -8:
            self.y -= 5.9 * dt
        if intents["down"] and self.y < 544:
            self.y += 5.9 * dt

    # Advance one sim step. The hitbox is the 32x32 centre of the 64x64
    # sprite, so a collision needs real overlap; it syncs to the pre-move
    # position, so collisions track the previous frame's drawn spot - the
    # same one-frame lag as Animal.update
    def update(self, intents, dt):
        self.rect = pygame.Rect(self.x + 16, self.y + 16, 32, 32)
        self.move(intents, dt)
        if self.explosion_timer > 0:
            self.explosion_timer -= dt

    def draw(self, screen):
        if self.shield:
            pygame.draw.rect(screen, (66, 239, 245), (self.x, self.y, 64, 64), 6)
        pygame.draw.rect(screen, (0, 0, 0), (self.x + 16, self.y + 16, 32, 32), 0)
        # While the death explosion plays the UFO is drawn as the blast
        screen.blit(loadImage("images/explosion.png") if self.explosion_timer > 0 else self.img,
                    (self.x, self.y))

    def draw_hud(self, screen):
        # Solo HUD is a slim top bar - score top left, time top centre
        # (drawn in runGame), lives top right - so no player label, no
        # controls reminder and no giant background score
        if len(players) == 1:
            score_color = level.get("score_color", self.score_color)
            screen.blit(space_font.render(str(self.score), True, score_color), (20, 5))
        else:
            screen.blit(points_font.render(self.label, True, self.color), (self.hud_x, 0))
            screen.blit(points_font.render(self.controls_text, True, self.color), (self.hud_x, 30))
            screen.blit(huge_font.render(str(self.score), True, self.score_color), (self.score_x, 150))
        # Remaining lives as a row of small UFOs in the top right corner
        if self.lives is not None:
            for i in range(max(self.lives, 0)):
                screen.blit(self.small_img, (990 - (i + 1) * 40, 8))

    # Apply one collected animal, looked up in the level's animals table.
    # opponents is every other player, so in a one-player mode an opponent
    # effect simply does nothing
    def collect(self, image_name, opponents):
        animal_type = level["animals"][image_name]
        effect = animal_type["effect"]
        value = animal_type["value"]

        if effect == "points":
            self.score += value
            # Big hauls (the swan, the eagle) sound richer than +1 blips
            sound_events.append("collect_big" if value >= 5 else "collect")
        elif effect == "obstacle":
            # A shield absorbs one hit instead of the player taking the penalty
            if self.shield:
                self.shield = False
                sound_events.append("shield_break")
            else:
                self.score += value
                sound_events.append("hurt")
        elif effect == "opponent":
            for opponent in opponents:
                opponent.score += value
            sound_events.append("zap")
        elif effect == "deadly":
            # A shield saves the life; otherwise the UFO blows up. The round
            # ends in runGame() once lives hit 0 and the explosion has played
            if self.shield:
                self.shield = False
                sound_events.append("shield_break")
            elif self.lives is not None:
                self.lives -= 1
                self.explosion_timer = 50
                sound_events.append("explosion")
        elif effect == "shield":
            self.shield = True
            sound_events.append("shield_up")
        elif effect == "random":
            if rng.randint(0, 1) == 0:
                self.score -= value
                sound_events.append("hurt")
            else:
                self.score += value
                sound_events.append("collect_big" if value >= 5 else "collect")


# Translate held keys into one player's intent dict. This is the only place
# the keyboard feeds the sim; anything that produces the same dict (a replay,
# an AI, a network packet) can drive a player instead
def keyboardIntents(pressed, controls):
    return {direction: pressed[key] for direction, key in controls.items()}


# Advance the whole sim one step: player movement, animal movement, recycling,
# collisions and scoring. No drawing and no input reads - this is the function
# a headless server would run. all_intents lines up with players by index
def updateGame(all_intents, dt):
    global landmark, landmark_cleared, landmark_crashed

    for p, intents in zip(players, all_intents):
        p.update(intents, dt)
    for animal in animals:
        animal.update(dt)
        if animal.x > animal.recycle_x:
            # Once the landmark has appeared, nothing new spawns - existing
            # animals just thin out as they recycle off, rather than being
            # replaced
            if landmark is None:
                animals.append(Animal())
            animals.remove(animal)
        for p in players:
            if p.rect.colliderect(animal.rect):
                animal.y = 1000
                p.collect(animal.image_name, [o for o in players if o is not p])

    # A level with a landmark doesn't end on the clock - time_limit instead
    # marks when the finish line appears, and the round ends once a UFO
    # either clears it or crashes into it
    if landmark is None and level.get("landmark") and level.get("time_limit") is not None \
            and current_time / 1000 >= level["time_limit"]:
        landmark = Landmark(level["landmark"])
    if landmark is not None:
        for p in players:
            if not landmark_cleared and p.rect.colliderect(landmark.sky_rect):
                landmark_cleared = True
            if not landmark_crashed and p.rect.colliderect(landmark.rect):
                landmark_crashed = True
                # A crash is a hard fail, not just a hit - all lives gone,
                # same explosion as any other deadly collision
                p.lives = 0
                p.explosion_timer = 50
                sound_events.append("explosion")


# Reset everything that belongs to a single round. Called once at startup and
# again on restart, so a starting value only ever has to be written here.
# Anything new that should start fresh each round belongs in this function.
def newRound(seed=None):
    global players, rng, level, level_index
    global scores, trophy, chosen_color
    global current_time, last_time
    global landmark, landmark_cleared, landmark_crashed

    # Every roll the sim makes (spawns, gift coin flips, background colour)
    # comes from this generator. Pass a seed to replay a round exactly - the
    # hook a future server uses to make every client roll the same spawns
    rng = random.Random(seed)

    # The active level supplies the round's content: spawn pools, animal
    # effects, legend and point goal. level_index is the campaign position -
    # 0 for a fresh mode, unchanged on a replay, advanced by the end
    # screen's next-level key; clamped so a shorter mode's list can't run
    # off the end. Must be set before the animals below are spawned
    level_index = min(level_index, len(mode["levels"]) - 1)
    level = mode["levels"][level_index]

    # Fresh Player objects reset score, position and shield; the identity
    # arguments (controls, colours, HUD spots) are what tell the two apart.
    # The mode decides the seat layout: solo modes get one seat on the arrow
    # keys starting in the middle of the screen, two-player modes get the
    # classic WASD-vs-arrows pair
    arrow_controls = {"left": pygame.K_LEFT, "right": pygame.K_RIGHT,
                      "up": pygame.K_UP, "down": pygame.K_DOWN}
    if mode["player_count"] == 1:
        players = [
            Player(player_img, start_x=468, start_y=268, number=1,
                   controls=arrow_controls, controls_text="ARROW KEYS",
                   color=(240, 90, 26), score_color=(181, 91, 53),
                   hud_x=100, score_x=20, lives=mode["lives"]),
        ]
    else:
        players = [
            Player(player_img, start_x=200, number=1,
                   controls={"left": pygame.K_a, "right": pygame.K_d,
                             "up": pygame.K_w, "down": pygame.K_s},
                   controls_text="WASD",
                   color=(240, 90, 26), score_color=(181, 91, 53),
                   hud_x=100, score_x=20, lives=mode["lives"]),
            Player(player2_img, start_x=700, number=2,
                   controls=arrow_controls, controls_text="ARROW KEYS",
                   color=(97, 8, 207), score_color=(125, 99, 171),
                   hud_x=780, score_x=530, lives=mode["lives"]),
        ][:mode["player_count"]]

    animals.clear()
    for i in range(0, 27):
        animals.append(Animal(slot=i, start_offset=250))

    landmark = None
    landmark_cleared = False
    landmark_crashed = False

    sound_events.clear()

    scores = loadScores(mode["highscore_file"], mode["default_scores"])
    trophy = False

    current_time = 0
    last_time = time.time()

    # A level can pin the background to a fixed colour; otherwise each round
    # gets a random one, same as always
    chosen_color = level.get("background_color") or colours[rng.randint(0, len(colours) - 1)]


# Each screen below owns its loop, drawing and event handling, and returns
# the name of the next screen: "start", "instructions", "game", "end" or
# "quit". The state machine at the bottom of the file hops between them
# until one quits. The pre-game flow is title/mode-select (one combined
# screen) -> instructions -> game.
def runStartScreen():
    global mode, level_index

    selected = MODES.index(mode)
    # The two player UFOs, blown up to twice sprite size, flanking the
    # bottom of the screen below the mode list
    ufo1 = pygame.transform.smoothscale(player_img, (128, 128))
    ufo2 = pygame.transform.smoothscale(player2_img, (128, 128))
    while True:
        pygame.display.flip()
        screen.fill((0, 0, 0))
        title = title_font.render("Feed The Aliens", True, (199, 199, 199))
        screen.blit(title, (500 - title.get_width() // 2, 60))
        # One row per mode - name plus tagline - with the selected one in gold
        for i, m in enumerate(MODES):
            color = (224, 185, 9) if i == selected else (120, 120, 120)
            screen.blit(space_font.render(("> " if i == selected else "   ") + m["name"], True, color), (330, 200 + i * 110))
            screen.blit(tagline_font.render(m["tagline"], True, color), (360, 248 + i * 110))
        screen.blit(ufo1, (500 - 128 - 24, 455))
        screen.blit(ufo2, (500 + 24, 455))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                # Both players' up/down keys move the highlight
                if event.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % len(MODES)
                    sounds.play("menu_move")
                if event.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % len(MODES)
                    sounds.play("menu_move")
                # Confirm: newRound() rebuilds the players list so the seat
                # count matches the chosen mode
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    sounds.play("menu_select")
                    mode = MODES[selected]
                    # Default to the campaign's first level, even if a
                    # previous run had advanced further
                    level_index = 0
                    # Multi-level modes pick a level first; newRound() runs
                    # once that choice is made
                    if len(mode["levels"]) > 1:
                        return "levels"
                    newRound()
                    return "instructions"


# Level select for multi-level (campaign) modes: one row per level with its
# flag and earned stars; a level is unlocked once the one before it has at
# least one star, so the list is playable strictly in order. Locked rows are
# dimmed and refuse to confirm.
def runLevelSelect():
    global level_index

    progress = loadProgress(mode)
    unlocked = [i == 0 or progress[i - 1] > 0 for i in range(len(mode["levels"]))]
    selected = level_index if unlocked[min(level_index, len(unlocked) - 1)] else 0
    star_img = pygame.transform.smoothscale(loadImage("images/001-star.png"), (28, 28))
    while True:
        pygame.display.flip()
        screen.fill((0, 0, 0))
        heading = title_font.render("Choose a level", True, (199, 199, 199))
        screen.blit(heading, (500 - heading.get_width() // 2, 60))
        for i, lvl in enumerate(mode["levels"]):
            row_y = 250 + i * 90
            if not unlocked[i]:
                color = (70, 70, 70)
            elif i == selected:
                color = (224, 185, 9)
            else:
                color = (120, 120, 120)
            if lvl.get("flag"):
                flag = loadImage(lvl["flag"])
                if not unlocked[i]:
                    flag = flag.copy()
                    flag.set_alpha(60)
                screen.blit(flag, (290, row_y + 8))
            name = lvl["name"] + ("" if unlocked[i] else "  -  LOCKED")
            name_surf = space_font.render(("> " if i == selected else "   ") + name, True, color)
            screen.blit(name_surf, (330, row_y))
            # Earned stars follow the name, however long it is
            for s in range(progress[i]):
                screen.blit(star_img, (330 + name_surf.get_width() + 24 + s * 34, row_y + 8))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % len(mode["levels"])
                    sounds.play("menu_move")
                if event.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % len(mode["levels"])
                    sounds.play("menu_move")
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    # A locked level refuses with the hurt buzz instead of
                    # the confirm click
                    if unlocked[selected]:
                        sounds.play("menu_select")
                        level_index = selected
                        newRound()
                        return "instructions"
                    sounds.play("hurt")
                if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    sounds.play("menu_move")
                    return "start"


def runInstructions():
    while True:
        pygame.display.flip()
        screen.fill((0, 0, 0))
        heading = title_font.render(mode["name"], True, (199, 199, 199))
        screen.blit(heading, (500 - heading.get_width() // 2, 15))
        if mode["player_count"] == 1:
            # Solo layout: level name, the player's UFO and how to move, all
            # centred down the middle; the legend keeps the side columns
            name = instruction_font.render(level["name"] or mode["tagline"],
                                           True, (224, 185, 9) if level["name"] else (97, 8, 207))
            # A level can carry a flag icon (e.g. the UK's Union Jack) shown
            # beside its name, as a centred pair
            flag = loadImage(level["flag"]) if level.get("flag") else None
            if flag:
                row_width = flag.get_width() + 10 + name.get_width()
                row_x = 500 - row_width // 2
                row_h = max(flag.get_height(), name.get_height())
                screen.blit(flag, (row_x, 130 + (row_h - flag.get_height()) // 2))
                screen.blit(name, (row_x + flag.get_width() + 10, 130 + (row_h - name.get_height()) // 2))
            else:
                screen.blit(name, (500 - name.get_width() // 2, 130))
            screen.blit(pygame.transform.smoothscale(players[0].img, (128, 128)), (436, 195))
            move = space_font.render(players[0].controls_text + " to move", True, (199, 199, 199))
            screen.blit(move, (500 - move.get_width() // 2, 340))
            if level.get("landmark"):
                # Sits in the one gap free of both the legend (which claims
                # the shield's spot right below "to move") and the
                # highscore table on the right - short wording is load
                # bearing, there isn't width to spare between them
                finish = points_font.render("Fly over " + level["landmark_name"] + " to finish!",
                                            True, (199, 199, 199))
                screen.blit(finish, (500 - finish.get_width() // 2, 470))
        else:
            screen.blit(instruction_font.render("Collect the animals to score points", True, (97, 8, 207)), (220, 130))
            screen.blit(instruction_font.render("Avoid the hazards", True, (97, 8, 207)), (220, 180))
            # Third line: the level name when the level has one (Adventure's
            # countries), otherwise the mode tagline
            third_line = level["name"] or mode["tagline"]
            third_surf = instruction_font.render(third_line, True, (224, 185, 9) if level["name"] else (97, 8, 207))
            if level.get("flag"):
                flag = loadImage(level["flag"])
                screen.blit(flag, (220 - flag.get_width() - 10, 230 - (flag.get_height() - third_surf.get_height()) // 2))
            screen.blit(third_surf, (220, 230))
            # Controls, one entry per seat, so this screen matches the mode
            controls = "   ".join("P" + str(p.number) + ": " + p.controls_text for p in players)
            screen.blit(space_font.render(controls, True, (199, 199, 199)), (220, 280))
        prompt = points_font.render("Enter to start, ESC to go back", True, (199, 199, 199))
        screen.blit(prompt, (500 - prompt.get_width() // 2, 550))
        # Highscore - shown only in modes that keep a table. Stored ascending
        # either way; points ranks best-first by reading it back to front
        # (highest is best), time by reading it as stored (lowest is best)
        if mode["saves_highscore"]:
            ranked = list(reversed(scores)) if mode["score_type"] == "points" else scores
            # Sits high enough that the fifth row clears the bottom prompt
            screen.blit(space_font.render("High Scores:", True, (224, 185, 9)), (720, 250))
            for i in range(0, 5):
                value = int(ranked[i]) if mode["score_type"] == "points" else ranked[i]
                screen.blit(space_font.render(str(i + 1) + "   " + str(value), True, (224, 185, 9)), (720, 305 + i * 45))
        # Animal pictures, labelled from the level's animals table so the
        # legend cannot drift out of step with what the animals are worth
        for legend_name, image_at, label_at in level["legend_layout"]:
            screen.blit(loadImage(legend_name), image_at)
            screen.blit(points_font.render(level["animals"][legend_name]["legend"], True, (199, 199, 199)), label_at)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    sounds.play("menu_select")
                    return "game"
                # Step back one screen, e.g. after picking by accident -
                # to level select for campaign modes, else the start screen
                if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    sounds.play("menu_move")
                    return "levels" if len(mode["levels"]) > 1 else "start"


def runGame():
    global current_time, last_time

    temp = pygame.time.get_ticks()
    paused = False
    # The engine hum runs for exactly as long as this screen does - every
    # return below stops it
    sounds.start_hum()
    while True:
        # Some modes end the instant the goal is hit (Speed Run's race);
        # others let the player keep scoring against it (Adventure's chase)
        if mode["ends_on_goal"] and any(p.score >= level["point_goal"] for p in players):
            sounds.stop_hum()
            return "end"
        # Out of lives ends the round too - but only after the explosion has
        # played out, so the player sees the blast before the end screen.
        # A landmark crash sets lives to 0 and plays the same explosion, so
        # it ends the round through this same check - no separate case needed
        if any(p.lives is not None and p.lives <= 0 and p.explosion_timer <= 0 for p in players):
            sounds.stop_hum()
            return "end"
        # A level can cap the round length; running out is also game over -
        # unless it has a landmark, in which case reaching *that* ends the
        # round instead (checked next), not the clock directly
        if level.get("time_limit") is not None and level.get("landmark") is None \
                and current_time / 1000 >= level["time_limit"]:
            sounds.stop_hum()
            return "end"
        if landmark_cleared:
            sounds.stop_hum()
            return "end"
        pygame.display.flip()
        screen.fill(chosen_color)
        # The landmark is scenery, not a gameplay element - drawn first so
        # animals and the UFO both fly over it, never under it
        if landmark:
            landmark.draw(screen)
        if paused:
            # A frozen field gets a silent engine too
            sounds.set_hum_level("paused")
            # Freeze the round: slide the timer's start point forward so
            # paused time never counts, and keep last_time fresh so dt does
            # not jump on resume. The field still draws, it just never moves
            temp = pygame.time.get_ticks() - current_time
            last_time = time.time()
        else:
            dt = time.time() - last_time
            dt *= 60
            last_time = time.time()
            # Slow game on first frames
            if dt > 2:
                dt = 1.9
            current_time = (pygame.time.get_ticks() - temp)
        # vsync paces the loop (flip blocks until the refresh); this cap never
        # engages alongside it and only bounds the loop if vsync is unavailable.
        # Don't pace with tick(60) instead: its sleep drifts against the real
        # refresh rate and skips a frame about once a second, a visible lurch
        clock.tick(240)
        # Rounded to one decimal (not two) so the display updates 10x less
        # often - at hundredths it re-renders every frame and looks flashy,
        # especially once centred, since the digit change also shifts width
        live_time = "{:.1f}".format(current_time / 1000)
        # Solo shows just the number, small and at the very top, to match
        # the slim score/lives bar; with a time limit it reads elapsed/limit
        # so the player can see how much of it is left. Two-player keeps the
        # big labelled timer, uncapped, as before
        # Once the landmark appears, the timer's job is done - it hands off
        # to a prompt naming the actual thing to reach
        if landmark:
            live_time = "Fly over " + level["landmark_name"] + "!"
        elif level.get("time_limit") is not None:
            live_time += "/" + str(level["time_limit"])
        timer_color = level.get("timer_color", (0, 0, 0))
        if mode["player_count"] == 1:
            t = space_font.render(live_time, True, timer_color)
            # A level's flag (e.g. the UK's Union Jack) sits beside its
            # timer too, as a centred pair
            if level.get("flag"):
                flag = loadImage(level["flag"])
                row_width = flag.get_width() + 10 + t.get_width()
                row_x = 500 - row_width // 2
                row_h = max(flag.get_height(), t.get_height())
                screen.blit(flag, (row_x, 5 + (row_h - flag.get_height()) // 2))
                screen.blit(t, (row_x + flag.get_width() + 10, 5 + (row_h - t.get_height()) // 2))
            else:
                screen.blit(t, (500 - t.get_width() // 2, 5))
        else:
            time_surf = timer_font.render(("" if landmark else "Time: ") + live_time, True, timer_color)
            if level.get("flag"):
                flag = loadImage(level["flag"])
                screen.blit(flag, (320 - flag.get_width() - 10, 30 - (flag.get_height() - time_surf.get_height()) // 2))
            screen.blit(time_surf, (320, 30))
        for p in players:
            p.draw_hud(screen)
        # Draw players; player 1 blits last, on top
        for p in reversed(players):
            p.draw(screen)
        if not paused:
            # Read the keyboard here, then hand the sim nothing but intents
            pressed = pygame.key.get_pressed()
            all_intents = [keyboardIntents(pressed, p.controls) for p in players]
            # The engine swells while any UFO is under thrust
            sounds.set_hum_level("moving" if any(any(i.values()) for i in all_intents) else "idle")
            updateGame(all_intents, dt)
            # Play whatever the sim step emitted - sound stays out of the sim
            for name in sound_events:
                sounds.play(name)
            sound_events.clear()
        for animal in animals:
            animal.draw(screen)
        if paused:
            banner = space_font.render("PAUSED - press P to resume, ESC for main menu", True, (199, 199, 199))
            screen.blit(banner, (500 - banner.get_width() // 2, 280))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sounds.stop_hum()
                time.sleep(0.2)
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_p:
                    paused = not paused
                    sounds.play("menu_move")
                # ESC returns to the main menu, but only from the pause
                # screen so a stray keypress mid-game cannot end the round
                if event.key == pygame.K_ESCAPE and paused:
                    sounds.stop_hum()
                    return "start"


def runEndScreen():
    global scores, trophy, level_index

    # The round is over, so its outcome is fixed - compute it once, not per
    # frame. Reaching the level's point goal is "success" everywhere: Speed
    # Run's race can only end this way, so this is always true there;
    # Adventure's round can end via lives or the clock without ever
    # crossing the goal, so this is the real win/lose split. Crashing into
    # the landmark overrides all of that - it's an automatic fail no matter
    # the score, the same way "hitting" rather than "flying over" was meant
    # to. Likewise, running out of lives after already crossing the goal
    # (Adventure keeps the round going past point_goal) is still a fail.
    reached_goal = not landmark_crashed and any(
        p.score >= level["point_goal"] and (p.lives is None or p.lives > 0)
        for p in players
    )
    next_index = level_index + 1
    has_next = next_index < len(mode["levels"])

    # Star rating: 1 for reaching the goal, 2 for reaching two_star_score,
    # 3 for reaching three_star_score without losing a life. two_star_score
    # defaults to double the goal so a level that doesn't set it still gets
    # a sensible threshold; three_star_score defaults to two_star_score.
    # UK and France set them explicitly to 150 and 175
    stars = 0
    if mode["player_count"] == 1 and reached_goal:
        stars = 1
        two_star_score = level.get("two_star_score", 2 * level["point_goal"])
        three_star_score = level.get("three_star_score", two_star_score)
        if players[0].score >= two_star_score:
            stars = 2
            if players[0].score >= three_star_score and players[0].lives == mode["lives"]:
                stars = 3

    # A better rating than the stored one is remembered forever - one star
    # is what unlocks the next level on the level select screen
    if mode.get("progress_file") and stars > 0:
        progress = loadProgress(mode)
        if stars > progress[level_index]:
            progress[level_index] = stars
            saveProgress(mode, progress)

    played_jingle = False
    while True:
        pygame.display.flip()
        screen.fill((0, 0, 0))
        # Stored ascending either way; points ranks best-first by reading it
        # back to front (highest is best), time as stored (lowest is best)
        ranked = list(reversed(scores)) if mode["score_type"] == "points" else scores

        # Highscores, saved once per round rather than on every frame. The
        # metric and the direction that counts as "better" both come from
        # the mode: Speed Run's time is better low, Adventure's score is
        # better high, so the "worst kept record" sits at opposite ends of
        # the sorted list (index 4 for time, index 0 for points)
        if mode["score_type"] == "points":
            result_value = players[0].score
            beats_worst = result_value > scores[0]
        else:
            result_value = round(current_time / 1000, 2)
            beats_worst = result_value < scores[4]
        if mode["saves_highscore"] and not trophy and beats_worst:
            trophy = True
            if mode["score_type"] == "points":
                scores = sorted(scores[1:] + [result_value])
            else:
                scores = sorted(scores[:4] + [result_value])
            saveScores(mode["highscore_file"], scores)

        if mode["player_count"] == 1:
            # Every row is centred and stacked from a running cursor, using
            # each surface's real rendered height rather than a guessed
            # constant (impact's glyphs run much taller than their point
            # size suggests) - so an optional row (the failure reason, the
            # trophy) can't leave the rows below it overlapping
            cursor = 15
            banner_color = (224, 185, 9) if reached_goal else (207, 41, 41)
            banner = title_font.render("SUCCESS!" if reached_goal else "FAILED", True, banner_color)
            screen.blit(banner, (500 - banner.get_width() // 2, cursor))
            cursor += banner.get_height() + 8
            # A failure needs a reason; a success is self-explanatory from
            # the score alone, so it gets no subtitle
            if not reached_goal:
                if landmark_crashed:
                    reason = "Crashed into " + level["landmark_name"] + "!"
                elif players[0].lives is not None and players[0].lives <= 0:
                    reason = "Out of lives!"
                else:
                    reason = "Time's up!"
                sub = points_font.render(reason, True, (199, 199, 199))
                screen.blit(sub, (500 - sub.get_width() // 2, cursor))
                cursor += sub.get_height() + 10
            # The score is the headline: big, centred, in the player's colour
            score_surf = score_font.render(str(players[0].score),
                                           True, level.get("score_color", players[0].score_color))
            screen.blit(score_surf, (500 - score_surf.get_width() // 2, cursor))
            cursor += score_surf.get_height() + 10
            # The star rating: earned stars bright, the rest ghosted, so
            # the player can see what was left on the table
            if stars > 0:
                star_full = pygame.transform.smoothscale(loadImage("images/001-star.png"), (44, 44))
                star_dim = star_full.copy()
                star_dim.set_alpha(50)
                row_x = 500 - (3 * 44 + 2 * 14) // 2
                for s in range(3):
                    screen.blit(star_full if s < stars else star_dim, (row_x + s * 58, cursor))
                cursor += 44 + 12
            # The next-country line is always shown - what changes is
            # whether it names an unlocked destination or one still to earn
            if has_next:
                next_name = mode["levels"][next_index]["name"]
                if reached_goal:
                    next_text = "Next: " + next_name
                    next_color = (224, 185, 9)
                else:
                    next_text = "Reach " + str(level["point_goal"]) + " points to unlock " + next_name
                    next_color = (150, 150, 150)
            else:
                next_text = "More countries coming soon!"
                next_color = (224, 185, 9) if reached_goal else (150, 150, 150)
            next_surf = space_font.render(next_text, True, next_color)
            screen.blit(next_surf, (500 - next_surf.get_width() // 2, cursor))
            cursor += next_surf.get_height() + 15
            if trophy:
                # Icon and caption sit side by side as one row, not stacked -
                # there isn't vertical room to spare for a second trophy row
                icon = loadImage("images/001-trophy.png")
                trophy_surf = space_font.render("New High Score!", True, (224, 185, 9))
                row_width = icon.get_width() + 10 + trophy_surf.get_width()
                row_x = 500 - row_width // 2
                screen.blit(icon, (row_x, cursor))
                screen.blit(trophy_surf, (row_x + icon.get_width() + 10, cursor + (icon.get_height() - trophy_surf.get_height()) // 2))
                cursor += icon.get_height() + 12
            # One compact line rather than a label plus a five-row list -
            # there just isn't room for both alongside everything above
            scores_text = "High Scores:  " + "   ".join(
                str(i + 1) + ": " + str(int(v) if mode["score_type"] == "points" else v)
                for i, v in enumerate(ranked))
            scores_surf = space_font.render(scores_text, True, (224, 185, 9))
            screen.blit(scores_surf, (500 - scores_surf.get_width() // 2, cursor))
            cursor += scores_surf.get_height() + 12
            controls = "R: Play Again    "
            if reached_goal and has_next:
                controls += "N: Next Level    "
            controls += "M: Menu    Q: Quit"
            controls_surf = points_font.render(controls, True, (220, 220, 220))
            screen.blit(controls_surf, (500 - controls_surf.get_width() // 2, cursor))
        else:
            screen.blit(space_font.render("High Scores:", True, (224, 185, 9)), (775, 280))
            for i in range(0, 5):
                value = int(ranked[i]) if mode["score_type"] == "points" else ranked[i]
                screen.blit(space_font.render(str(i + 1) + "   " + str(value), True, (224, 185, 9)), (775, 340 + i * 50))
            screen.blit(points_font.render("Press R to play again, M for main menu, Q to quit", True, (220, 220, 220)), (10, 550))
            screen.blit(timer_font.render("Time: " + str(round(current_time/1000, 2)), True, (199, 199, 199)), (350, 10))
            screen.blit(title_font.render("GAME OVER!", True, (199, 199, 199)), (270, 230))
            for p, corner in zip(players, ((30, 30), (880, 30))):
                screen.blit(space_font.render("P" + str(p.number) + ": " + str(p.score), True, p.color), corner)
            # Display winner. Tested against the level's point goal, the same
            # thing that ended the game, so changing the goal cannot leave
            # the winner unnamed
            for p in players:
                if mode["ends_on_goal"] and p.score >= level["point_goal"]:
                    screen.blit(space_font.render(p.label + " WINS!", True, p.color), (355, 100))
                    screen.blit(p.img, (440, 150))
                # A round can end in defeat instead: the UFO ran out of lives
                elif p.lives is not None and p.lives <= 0:
                    screen.blit(space_font.render("OUT OF LIVES!", True, p.color), (355, 100))
                    screen.blit(loadImage("images/explosion.png"), (440, 150))
                # Or a level's time limit could have run out first
                elif level.get("time_limit") is not None and current_time / 1000 >= level["time_limit"]:
                    screen.blit(space_font.render("TIME'S UP!", True, p.color), (355, 100))
                    screen.blit(p.img, (440, 150))
            if trophy:
                screen.blit(space_font.render("New High Score!", True, (224, 185, 9)), (355, 380))
                screen.blit(loadImage("images/001-trophy.png"), (440, 430))
        # One jingle as the screen appears, chosen after the trophy check
        # just above so a record run gets the fanfare instead of the plain
        # win jingle; not reaching the goal gets the sad one
        if not played_jingle:
            played_jingle = True
            if trophy:
                sounds.play("trophy")
            elif not reached_goal:
                sounds.play("jingle_lose")
            else:
                sounds.play("jingle_win")
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                # R jumps straight back to the level's instructions screen -
                # same mode, same level, fresh round - skipping the start
                # screen entirely
                if event.key == pygame.K_r:
                    sounds.play("menu_select")
                    newRound()
                    return "instructions"
                # N advances the campaign - only live when the goal was
                # actually reached and there is somewhere further to go
                if event.key == pygame.K_n and reached_goal and has_next:
                    sounds.play("menu_select")
                    level_index = next_index
                    newRound()
                    return "instructions"
                # M leaves the round behind for the title screen; the mode
                # gets rebuilt fresh once a mode is chosen there again
                if event.key == pygame.K_m:
                    sounds.play("menu_select")
                    return "start"
                if event.key == pygame.K_q:
                    return "quit"


newRound()

# Screen state machine: run one screen at a time until one of them quits
screen_name = "start"
while screen_name != "quit":
    if screen_name == "start":
        screen_name = runStartScreen()
    elif screen_name == "levels":
        screen_name = runLevelSelect()
    elif screen_name == "instructions":
        screen_name = runInstructions()
    elif screen_name == "game":
        screen_name = runGame()
    elif screen_name == "end":
        screen_name = runEndScreen()
