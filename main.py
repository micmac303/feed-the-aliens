import random
import time
import pygame

pygame.init()

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
points_font = pygame.font.SysFont("impact", 32)
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

# Highscores are player data, not source, so Highscore.txt is not in git.
# A fresh clone starts from these defaults.
default_scores = [30.0, 40.0, 50.0, 60.0, 70.0]


def saveScores(score_list):
    with open("Highscore.txt", "w") as scores_file:
        scores_file.write(" ".join(str(x) for x in score_list))


# Recreates the file if it is missing, empty, corrupt or short, so the game
# never crashes on bad data.
def loadScores():
    try:
        with open("Highscore.txt", "r") as scores_file:
            loaded = sorted(map(float, scores_file.read().split()))[:5]
        if len(loaded) < 5:
            raise ValueError("not enough scores")
        return loaded
    except (OSError, ValueError):
        saveScores(default_scores)
        return list(default_scores)


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
        "images/001-star.png": {"effect": "shield", "value": None, "legend": "Single use shield"},
        "images/001-gift.png": {"effect": "random", "value": 10, "legend": "Random +10 / -10"},
    },
    "animal_images": ["images/003-cow.png", "images/001-hen.png", "images/003-elephant.png",
                      "images/002-rabbit.png", "images/001-bomb.png", "images/002-truck.png",
                      "images/003-tiger.png"],
    "rare_animal_images": ["images/001-star.png", "images/001-eagle.png", "images/001-gift.png"],
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
        ("images/001-star.png", (340, 470), (420, 480)),
    ],
}

# Level 1 of the Adventure world tour. All art is the real UK set.
UK_LEVEL = {
    "name": "Level 1 - United Kingdom",
    "point_goal": 100,
    "time_limit": 60,
    # A fixed background instead of newRound()'s random pick - reuses one of
    # the game's existing purple tones for a mid purple that still matches
    "background_color": (120, 76, 207),
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
        "images/001-star.png": {"effect": "shield", "value": None, "legend": "Single use shield"},
    },
    "animal_images": ["images/hedgehog.png", "images/squirrel.png", "images/fox.png",
                      "images/jet.png", "images/bus.png"],
    "rare_animal_images": ["images/001-star.png", "images/swan.png"],
    "legend_layout": [
        ("images/swan.png", (30, 30), (100, 40)),
        ("images/fox.png", (30, 130), (100, 140)),
        ("images/squirrel.png", (30, 230), (100, 240)),
        ("images/hedgehog.png", (30, 330), (100, 340)),
        ("images/jet.png", (910, 30), (790, 40)),
        ("images/bus.png", (910, 130), (790, 140)),
        ("images/001-star.png", (340, 400), (420, 410)),
    ],
}

# Adventure's world tour, one country per level. France, Spain, Germany and
# friends append here; continent chapters will group lists like this one.
ADVENTURE_LEVELS = [UK_LEVEL]

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
     # No lives in a race - deadly animals only exist in Adventure levels
     "lives": None,
     "levels": [CLASSIC_LEVEL]},
    {"name": "Adventure",
     "tagline": "One player - eat your way around the world",
     "player_count": 1,
     # Solo times are not comparable with two-player races, so they stay out
     # of Highscore.txt
     "saves_highscore": False,
     "lives": 3,
     "levels": ADVENTURE_LEVELS},
]
mode = MODES[0]

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
    def __init__(self, slot=0):
        if rng.randint(1, 8) == 8:
            self.image_name = level["rare_animal_images"][rng.randint(0, len(level["rare_animal_images"]) - 1)]
        else:
            self.image_name = level["animal_images"][rng.randint(0, len(level["animal_images"]) - 1)]
        # The surface is shared between animals of the same type - it is only
        # ever blitted, never drawn into - but get_rect() gives each one its
        # own hitbox
        self.img = loadImage(self.image_name)
        self.rect = self.img.get_rect()
        # slot staggers the 27 starting animals off the left edge
        self.x = ((slot + 1) * -81) - 1000
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
            screen.blit(space_font.render(str(self.score), True, self.score_color), (20, 5))
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
        elif effect == "obstacle":
            # A shield absorbs one hit instead of the player taking the penalty
            if self.shield:
                self.shield = False
            else:
                self.score += value
        elif effect == "opponent":
            for opponent in opponents:
                opponent.score += value
        elif effect == "deadly":
            # A shield saves the life; otherwise the UFO blows up. The round
            # ends in runGame() once lives hit 0 and the explosion has played
            if self.shield:
                self.shield = False
            elif self.lives is not None:
                self.lives -= 1
                self.explosion_timer = 50
        elif effect == "shield":
            self.shield = True
        elif effect == "random":
            if rng.randint(0, 1) == 0:
                self.score -= value
            else:
                self.score += value


# Translate held keys into one player's intent dict. This is the only place
# the keyboard feeds the sim; anything that produces the same dict (a replay,
# an AI, a network packet) can drive a player instead
def keyboardIntents(pressed, controls):
    return {direction: pressed[key] for direction, key in controls.items()}


# Advance the whole sim one step: player movement, animal movement, recycling,
# collisions and scoring. No drawing and no input reads - this is the function
# a headless server would run. all_intents lines up with players by index
def updateGame(all_intents, dt):
    for p, intents in zip(players, all_intents):
        p.update(intents, dt)
    for animal in animals:
        animal.update(dt)
        if animal.x > animal.recycle_x:
            animals.append(Animal())
            animals.remove(animal)
        for p in players:
            if p.rect.colliderect(animal.rect):
                animal.y = 1000
                p.collect(animal.image_name, [o for o in players if o is not p])


# Reset everything that belongs to a single round. Called once at startup and
# again on restart, so a starting value only ever has to be written here.
# Anything new that should start fresh each round belongs in this function.
def newRound(seed=None):
    global players, rng, level
    global scores, trophy, chosen_color
    global current_time, last_time

    # Every roll the sim makes (spawns, gift coin flips, background colour)
    # comes from this generator. Pass a seed to replay a round exactly - the
    # hook a future server uses to make every client roll the same spawns
    rng = random.Random(seed)

    # The active level supplies the round's content: spawn pools, animal
    # effects, legend and point goal. Always the mode's first level until
    # level progression exists - advancing will just be a bigger index. Must
    # be set before the animals below are spawned
    level = mode["levels"][0]

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
        animals.append(Animal(slot=i))

    scores = loadScores()
    trophy = False

    current_time = 0
    last_time = time.time()

    # A level can pin the background to a fixed colour; otherwise each round
    # gets a random one, same as always
    chosen_color = level.get("background_color") or colours[rng.randint(0, len(colours) - 1)]


# Each screen below owns its loop, drawing and event handling, and returns
# the name of the next screen: "start", "modes", "instructions", "game",
# "end" or "quit". The state machine at the bottom of the file hops between
# them until one quits. The pre-game flow is three screens:
# title -> mode select -> instructions -> game.
def runStartScreen():
    title = title_font.render("Feed The Aliens", True, (199, 199, 199))
    prompt = space_font.render("Press SPACE to start", True, (199, 199, 199))
    # The two player UFOs, blown up to twice sprite size for the title screen
    ufo1 = pygame.transform.smoothscale(player_img, (128, 128))
    ufo2 = pygame.transform.smoothscale(player2_img, (128, 128))
    while True:
        pygame.display.flip()
        screen.fill((0, 0, 0))
        # Title up top, the UFOs side by side in the middle, and the prompt
        # at the bottom - everything centred on the 1000px width
        screen.blit(title, (500 - title.get_width() // 2, 100))
        screen.blit(ufo1, (500 - 128 - 24, 236))
        screen.blit(ufo2, (500 + 24, 236))
        screen.blit(prompt, (500 - prompt.get_width() // 2, 500))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    return "modes"


def runModeSelect():
    global mode

    selected = MODES.index(mode)
    while True:
        pygame.display.flip()
        screen.fill((0, 0, 0))
        heading = title_font.render("Choose a mode", True, (199, 199, 199))
        screen.blit(heading, (500 - heading.get_width() // 2, 60))
        # One row per mode - name plus tagline - with the selected one in gold
        for i, m in enumerate(MODES):
            color = (224, 185, 9) if i == selected else (120, 120, 120)
            screen.blit(space_font.render(("> " if i == selected else "   ") + m["name"], True, color), (330, 250 + i * 110))
            screen.blit(points_font.render(m["tagline"], True, color), (360, 298 + i * 110))
        screen.blit(space_font.render("UP / DOWN to choose, ENTER to select", True, (199, 199, 199)), (180, 550))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                # Both players' up/down keys move the highlight
                if event.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % len(MODES)
                if event.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % len(MODES)
                # Confirm: newRound() rebuilds the players list so the seat
                # count matches the chosen mode
                if event.key == pygame.K_RETURN:
                    mode = MODES[selected]
                    newRound()
                    return "instructions"


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
            screen.blit(name, (500 - name.get_width() // 2, 130))
            screen.blit(pygame.transform.smoothscale(players[0].img, (128, 128)), (436, 195))
            move = space_font.render(players[0].controls_text + " to move", True, (199, 199, 199))
            screen.blit(move, (500 - move.get_width() // 2, 340))
        else:
            screen.blit(instruction_font.render("Collect the animals to score points", True, (97, 8, 207)), (220, 130))
            screen.blit(instruction_font.render("Avoid the hazards", True, (97, 8, 207)), (220, 180))
            # Third line: the level name when the level has one (Adventure's
            # countries), otherwise the mode tagline
            third_line = level["name"] or mode["tagline"]
            screen.blit(instruction_font.render(third_line, True, (224, 185, 9) if level["name"] else (97, 8, 207)), (220, 230))
            # Controls, one entry per seat, so this screen matches the mode
            controls = "   ".join("P" + str(p.number) + ": " + p.controls_text for p in players)
            screen.blit(space_font.render(controls, True, (199, 199, 199)), (220, 280))
        prompt = space_font.render("Press SPACE to start, ESC to change mode", True, (199, 199, 199))
        screen.blit(prompt, (500 - prompt.get_width() // 2, 550))
        # Highscore - shown only in modes whose times go in the table
        if mode["saves_highscore"]:
            # Sits high enough that the fifth row clears the bottom prompt
            screen.blit(space_font.render("High Scores:", True, (224, 185, 9)), (720, 250))
            for i in range(0, 5):
                screen.blit(space_font.render(str(i + 1) + "   " + str(scores[i]), True, (224, 185, 9)), (720, 305 + i * 45))
        # Animal pictures, labelled from the level's animals table so the
        # legend cannot drift out of step with what the animals are worth
        for legend_name, image_at, label_at in level["legend_layout"]:
            screen.blit(loadImage(legend_name), image_at)
            screen.blit(points_font.render(level["animals"][legend_name]["legend"], True, (199, 199, 199)), label_at)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    return "game"
                # Back to mode select, e.g. after picking a mode by accident
                if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    return "modes"


def runGame():
    global current_time, last_time

    temp = pygame.time.get_ticks()
    paused = False
    while True:
        if any(p.score >= level["point_goal"] for p in players):
            return "end"
        # Out of lives ends the round too - but only after the explosion has
        # played out, so the player sees the blast before the end screen
        if any(p.lives is not None and p.lives <= 0 and p.explosion_timer <= 0 for p in players):
            return "end"
        # A level can cap the round length; running out is also game over
        if level.get("time_limit") is not None and current_time / 1000 >= level["time_limit"]:
            return "end"
        pygame.display.flip()
        screen.fill(chosen_color)
        if paused:
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
        # the slim score/lives bar; two-player keeps the big labelled timer
        if mode["player_count"] == 1:
            t = space_font.render(live_time, True, (0, 0, 0))
            screen.blit(t, (500 - t.get_width() // 2, 5))
        else:
            screen.blit(timer_font.render("Time: " + live_time, True, (0, 0, 0)), (320, 30))
        for p in players:
            p.draw_hud(screen)
        # Draw players; player 1 blits last, on top
        for p in reversed(players):
            p.draw(screen)
        if not paused:
            # Read the keyboard here, then hand the sim nothing but intents
            pressed = pygame.key.get_pressed()
            updateGame([keyboardIntents(pressed, p.controls) for p in players], dt)
        for animal in animals:
            animal.draw(screen)
        if paused:
            banner = space_font.render("PAUSED - press P to resume, ESC to quit", True, (199, 199, 199))
            screen.blit(banner, (500 - banner.get_width() // 2, 280))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                time.sleep(0.2)
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_p:
                    paused = not paused
                # ESC quits, but only from the pause screen so a stray
                # keypress mid-game cannot end the round
                if event.key == pygame.K_ESCAPE and paused:
                    return "quit"


def runEndScreen():
    global scores, trophy

    while True:
        pygame.display.flip()
        screen.fill((0, 0, 0))
        screen.blit(space_font.render("High Scores:", True, (224, 185, 9)), (775, 280))
        for i in range(0, 5):
            screen.blit(space_font.render(str(i + 1) + "   " + str(scores[i]), True, (224, 185, 9)), (775, 340 + i * 50))
        screen.blit(points_font.render("Press R to play again, M for main menu, Q to quit", True, (220, 220, 220)), (10, 550))
        screen.blit(timer_font.render("Time: " + str(round(current_time/1000, 2)), True, (199, 199, 199)), (350, 10))
        screen.blit(title_font.render("GAME OVER!", True, (199, 199, 199)), (270, 230))
        for p, corner in zip(players, ((30, 30), (880, 30))):
            screen.blit(space_font.render("P" + str(p.number) + ": " + str(p.score), True, p.color), corner)
        # Display winner. Tested against the level's point goal, the same
        # thing that ended the game, so changing the goal cannot leave the
        # winner unnamed
        for p in players:
            if p.score >= level["point_goal"]:
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
        # Highscores, saved once per round rather than on every frame, and
        # only in modes whose times belong in the table
        if mode["saves_highscore"] and not trophy and current_time/1000 < scores[4]:
            trophy = True
            scores = sorted(scores[:4] + [round(current_time/1000, 2)])
            saveScores(scores)
        if trophy:
            screen.blit(space_font.render("New High Score!", True, (224, 185, 9)), (355, 380))
            screen.blit(loadImage("images/001-trophy.png"), (440, 430))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                # R jumps straight back to the level's instructions screen -
                # same mode, fresh round - skipping the title and mode select
                if event.key == pygame.K_r:
                    newRound()
                    return "instructions"
                # M leaves the round behind for the title screen; the mode
                # gets rebuilt fresh once a mode is chosen there again
                if event.key == pygame.K_m:
                    return "start"
                if event.key == pygame.K_q:
                    return "quit"


newRound()

# Screen state machine: run one screen at a time until one of them quits
screen_name = "start"
while screen_name != "quit":
    if screen_name == "start":
        screen_name = runStartScreen()
    elif screen_name == "modes":
        screen_name = runModeSelect()
    elif screen_name == "instructions":
        screen_name = runInstructions()
    elif screen_name == "game":
        screen_name = runGame()
    elif screen_name == "end":
        screen_name = runEndScreen()
