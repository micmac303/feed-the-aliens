import random
import time
import pygame

# 29.48 31.9 33.88 34.34 34.64 (to score 200 point)
# 11.435, 13.15, 14.301, 14.58, 14.718, 14.807, 14.517, 14.562, 14.927  (to score 100 point)
# 6.52 6.8 6.88 7.04 7.13 (to score 30 point)
# 1.91 2.44 2.67 3.08 3.44 (to score 1 point)

# To do:
# flash the score
# pic of animals eaten/ counter of animals
# reward for no lorrys/ bombs 'clean run'
# combos e.g: five cows in a row +500
# sound effects, music, wipeout music
# change highscore UI

# Initialise pygame
pygame.init()

# Create the screen
screen = pygame.display.set_mode((1000, 600))
pygame.display.set_icon(pygame.image.load("images/006-ufo-1.png"))
pygame.display.set_caption("Feed The Aliens")

# Font
timer_font = pygame.font.SysFont("impact", 60)
huge_font = pygame.font.SysFont("impact", 352)
points_font = pygame.font.SysFont("impact", 32)
instruction_font = pygame.font.SysFont("ebrima", 38)
space_font = pygame.font.SysFont("impact", 40)
title_font = pygame.font.SysFont("impact", 90)

# Scores
point_goal = 100

# Timer
clock = pygame.time.Clock()

# Per-round state (the two Player objects, animals, scores, ...) is created by
# newRound() below, so each starting value is written in exactly one place.

# Random background colour
colours = [(49, 201, 235), (34, 52, 153), (50, 92, 166), (89, 125, 189), (89, 146, 189), (84, 180, 199),  # Blue
           (163, 11, 11), (207, 41, 41), (194, 39, 98), (199, 42, 94), (168, 5, 5), (189, 0, 126),  # Red
           (122, 0, 156), (145, 24, 196), (171, 34, 199), (77, 13, 181), (120, 76, 207), (96, 3, 171),  # Purple
           (171, 173, 184), (194, 197, 209), (226, 204, 227), (173, 174, 179), (204, 197, 212), (107, 90, 91),  # Gray
           ]

# Highscores are player data, not source, so Highscore.txt is not in git.
# A fresh clone starts from these defaults.
default_scores = [30.0, 40.0, 50.0, 60.0, 70.0]


# Space separated list, overwriting any existing scores
def saveScores(score_list):
    with open("Highscore.txt", "w") as scores_file:
        scores_file.write(" ".join(str(x) for x in score_list))


# Read the five best times, recreating the file if it is missing or corrupt
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


# Images are loaded from disk once and reused. The start screen redraws ten
# legend images every frame, and every animal spawn needs a surface.
image_cache = {}


def loadImage(path):
    if path not in image_cache:
        image_cache[path] = pygame.image.load(path)
    return image_cache[path]


# Player 1
player_img = loadImage("images/001-ufo.png")

# Player 2
player2_img = loadImage("images/021-ufo.png")

animals = []

EAGLE = "images/001-eagle.png"

# What each animal does when a player collects it, and how the start screen
# legend describes it. To add a new animal: add an entry here, add its image to
# one of the spawn pools below, and give it a spot in legend_layout.
#   points   - add value to the collecting player's score
#   obstacle - add value (negative) unless a shield absorbs it
#   opponent - add value (negative) to the *other* player's score
#   shield   - grant a single use shield
#   random   - plus or minus value, a coin flip
ANIMALS = {
    "images/003-cow.png": {"effect": "points", "value": 3, "legend": "+3"},
    "images/001-hen.png": {"effect": "points", "value": 1, "legend": "+1"},
    "images/003-elephant.png": {"effect": "points", "value": 5, "legend": "+5"},
    "images/002-rabbit.png": {"effect": "points", "value": 1, "legend": "+1"},
    EAGLE: {"effect": "points", "value": 8, "legend": "+8"},
    "images/002-truck.png": {"effect": "obstacle", "value": -5, "legend": "-5"},
    "images/001-bomb.png": {"effect": "obstacle", "value": -2, "legend": "-2"},
    "images/003-tiger.png": {"effect": "opponent", "value": -3, "legend": "-3 to opponent"},
    "images/001-star.png": {"effect": "shield", "value": None, "legend": "Single use shield"},
    "images/001-gift.png": {"effect": "random", "value": 10, "legend": "Random +10 / -10"},
}

# Spawn pools: rare animals come up on a 1 in 8 roll in summonAnimal()
animal_images = ["images/003-cow.png", "images/001-hen.png", "images/003-elephant.png", "images/002-rabbit.png",
                 "images/001-bomb.png", "images/002-truck.png", "images/003-tiger.png"]
rare_animal_images = ["images/001-star.png", EAGLE, "images/001-gift.png"]

# A spawnable animal with no entry above would silently score nothing
for name in animal_images + rare_animal_images:
    assert name in ANIMALS, "no ANIMALS entry for " + name

# Where each animal sits on the start screen legend: (image, image position,
# label position). The label text itself comes from ANIMALS.
legend_layout = [
    (EAGLE, (30, 30), (100, 40)),
    ("images/003-elephant.png", (30, 130), (100, 140)),
    ("images/003-cow.png", (30, 230), (100, 240)),
    ("images/001-hen.png", (30, 330), (100, 340)),
    ("images/002-rabbit.png", (30, 430), (100, 440)),
    ("images/002-truck.png", (910, 30), (860, 40)),
    ("images/001-bomb.png", (910, 130), (860, 140)),
    ("images/001-gift.png", (340, 330), (420, 345)),
    ("images/003-tiger.png", (340, 400), (420, 410)),
    ("images/001-star.png", (340, 470), (420, 480)),
]


# Create an animal and add it to animals[]
def summonAnimal(i_arg):
    calculate_rare = random.randint(1, 8)
    if calculate_rare == 8:
        chosen_animal = rare_animal_images[random.randint(0, len(rare_animal_images) - 1)]
    else:
        chosen_animal = animal_images[random.randint(0, len(animal_images) - 1)]

    # The surface is shared between animals of the same type - it is only ever
    # blitted, never drawn into - but get_rect() gives each one its own hitbox
    animal_img = loadImage(chosen_animal)
    animal_arg = {
        "image_name": chosen_animal,
        "img": animal_img,
        "animal_rect": animal_img.get_rect(),
        "x_pos": ((i_arg + 1) * -81) - 1000,
        "y_pos": random.randint(120, 500),
        "x_velocity": 0
    }
    animals.append(animal_arg)


# One UFO: score, position, shield, plus the controls and HUD placement that
# tell the two players apart. Both players are instances of this class, so
# there is no per-player duplication; newRound() builds two fresh ones, which
# is what resets score/position/shield each round.
class Player:
    def __init__(self, img, start_x, controls, label, controls_text, color, score_color, hud_x, score_x):
        # Identity: fixed for the whole session
        self.img = img
        self.controls = controls          # {"left"/"right"/"up"/"down": key constant}
        self.label = label
        self.controls_text = controls_text
        self.color = color
        self.score_color = score_color
        self.hud_x = hud_x
        self.score_x = score_x
        # Round state: starts fresh because each round gets a fresh Player
        self.x = start_x
        self.y = 30
        self.score = 0
        self.shield = False
        self.rect = img.get_rect()

    # Movement constants are deliberately asymmetric (left 5.8, right 7.0)
    def move(self, pressed, dt):
        if pressed[self.controls["left"]] and self.x > 0:
            self.x -= 5.8 * dt
        if pressed[self.controls["right"]] and self.x < 936:
            self.x += 7 * dt
        if pressed[self.controls["up"]] and self.y > -8:
            self.y -= 5.9 * dt
        if pressed[self.controls["down"]] and self.y < 544:
            self.y += 5.9 * dt

    # The rect returned by the filled draw.rect call is the hitbox: the 32x32
    # centre of the 64x64 sprite, so a collision needs real overlap
    def draw(self, screen):
        if self.shield:
            pygame.draw.rect(screen, (66, 239, 245), (self.x, self.y, 64, 64), 6)
        self.rect = pygame.draw.rect(screen, (0, 0, 0), (self.x + 16, self.y + 16, 32, 32), 0)
        screen.blit(self.img, (self.x, self.y))

    def draw_hud(self, screen):
        screen.blit(points_font.render(self.label, True, self.color), (self.hud_x, 0))
        screen.blit(points_font.render(self.controls_text, True, self.color), (self.hud_x, 30))
        screen.blit(huge_font.render(str(self.score), True, self.score_color), (self.score_x, 150))

    # Apply one collected animal, looked up in the ANIMALS table
    def collect(self, image_name, opponent):
        animal_type = ANIMALS[image_name]
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
            opponent.score += value
        elif effect == "shield":
            self.shield = True
        elif effect == "random":
            # Coin flip on the value of the present
            if random.randint(0, 1) == 0:
                self.score -= value
            else:
                self.score += value


# Reset everything that belongs to a single round. Called once at startup and
# again on restart, so a starting value only ever has to be written here.
# Anything new that should start fresh each round belongs in this function.
def newRound():
    global player, player2
    global scores, trophy, chosen_color
    global current_time, last_time

    # Fresh Player objects reset score, position and shield; the identity
    # arguments (controls, colours, HUD spots) are what tell the two apart
    player = Player(player_img, start_x=200,
                    controls={"left": pygame.K_a, "right": pygame.K_d,
                              "up": pygame.K_w, "down": pygame.K_s},
                    label="PLAYER 1", controls_text="WASD",
                    color=(240, 90, 26), score_color=(181, 91, 53),
                    hud_x=100, score_x=20)
    player2 = Player(player2_img, start_x=700,
                     controls={"left": pygame.K_LEFT, "right": pygame.K_RIGHT,
                               "up": pygame.K_UP, "down": pygame.K_DOWN},
                     label="PLAYER 2", controls_text="ARROW KEYS",
                     color=(97, 8, 207), score_color=(125, 99, 171),
                     hud_x=780, score_x=530)

    # Animals, at their staggered starting offsets off the left edge
    animals.clear()
    for i in range(0, 27):
        summonAnimal(i)

    # Highscores
    scores = loadScores()
    trophy = False

    # Timer and frame rate
    current_time = 0
    last_time = time.time()

    # Random background colour
    chosen_color = colours[random.randint(0, len(colours) - 1)]


newRound()

running = False
start_screen = True
end_screen = False

# Game loop

start = True
while start:
    while start_screen:
        # Update display
        pygame.display.flip()
        screen.fill((0, 0, 0))
        # Image decoration
        screen.blit(loadImage("images/006-ufo-1.png"), (490, -2))
        screen.blit(loadImage("images/005-alien.png"), (220, 535))
        screen.blit(loadImage("images/001-alien.png"), (660, 535))
        # Instructions
        screen.blit(title_font.render("Feed The Aliens", True, (199, 199, 199)), (220, 15))
        screen.blit(instruction_font.render("Collect the animals to score points", True, (97, 8, 207)), (220, 130))
        screen.blit(instruction_font.render("Avoid the trucks and bombs", True, (97, 8, 207)), (220, 180))
        screen.blit(instruction_font.render("The first to 100 points wins", True, (97, 8, 207)), (220, 230))
        screen.blit(space_font.render("Press SPACE to start", True, (199, 199, 199)), (340, 550))
        # Highscore
        for i in range(0, 5):
            screen.blit(space_font.render(str(i + 1) + "   " + str(scores[i]), True, (224, 185, 9)), (720, 340 + i * 50))
        screen.blit(space_font.render("High Scores:", True, (224, 185, 9)), (720, 280))
        # Animal pictures, labelled from the ANIMALS table so the legend cannot
        # drift out of step with what the animals are actually worth
        for legend_name, image_at, label_at in legend_layout:
            screen.blit(loadImage(legend_name), image_at)
            screen.blit(points_font.render(ANIMALS[legend_name]["legend"], True, (199, 199, 199)), label_at)
        for event in pygame.event.get():
            # Quit
            if event.type == pygame.QUIT:
                start_screen = False
                start = False
                # Continue to game
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    running = True
                    start_screen = False

    # Reset timer
    temp = pygame.time.get_ticks()
    # Game loop
    while running:
        # Point limit to end game
        if player.score >= point_goal or player2.score >= point_goal:
            end_screen = True
            running = False
        # Update display
        pygame.display.flip()
        screen.fill(chosen_color)
        # Load frame rate
        dt = time.time() - last_time
        dt *= 60
        last_time = time.time()
        # Slow game on first frames
        if dt > 2:
            dt = 1.9
        # Load time
        current_time = (pygame.time.get_ticks() - temp)
        clock.tick(600)
        # Display scores and time
        screen.blit(timer_font.render("Time: " + str(round(current_time / 1000, 2)), True, (0, 0, 0)), (320, 30))
        player.draw_hud(screen)
        player2.draw_hud(screen)
        # Draw players, updating their hitboxes; player 1 blits last, on top
        player2.draw(screen)
        player.draw(screen)
        # Player movement and collide with edge of screen
        keys = pygame.key.get_pressed()
        player.move(keys, dt)
        player2.move(keys, dt)
        # Load animals individually
        for animal in animals:
            # Load hitboxes
            animal["animal_rect"].x = animal["x_pos"]
            animal["animal_rect"].y = animal["y_pos"]
            # Update positions
            animal["x_pos"] += animal["x_velocity"] * dt
            # Display animals
            screen.blit(animal["img"], (animal["x_pos"], animal["y_pos"]))
            # pygame.draw.rect(screen, (100, 100, 100), animal["animal_rect"], 4)
            # Summon new animals and delete old animals
            if animal["image_name"] == EAGLE:
                if animal["x_pos"] > 3200:
                    summonAnimal(0)
                    animals.remove(animal)
            elif animal["x_pos"] > 1100:
                summonAnimal(0)
                animals.remove(animal)
            # Check collision and calculate points
            for p, opponent in ((player, player2), (player2, player)):
                if p.rect.colliderect(animal["animal_rect"]):
                    animal["y_pos"] = 1000
                    p.collect(animal["image_name"], opponent)
            # Start animal movement
            if animal["image_name"] == EAGLE and animal["x_pos"] >= -1000:
                animal["x_velocity"] = 10
            else:
                animal["x_velocity"] = 5
        # Quit
        for event in pygame.event.get():
            if event.type == pygame.QUIT:  #or current_time/1000 > 16
                time.sleep(0.2)
                running = False
                start = False

    while end_screen:
        # Update display
        pygame.display.flip()
        # End screen
        screen.fill((0, 0, 0))
        # Highscores
        screen.blit(space_font.render("High Scores:", True, (224, 185, 9)), (775, 280))
        for i in range(0, 5):
            screen.blit(space_font.render(str(i + 1) + "   " + str(scores[i]), True, (224, 185, 9)), (775, 340 + i * 50))
        # Decoration
        screen.blit(points_font.render("Press r to restart", True, (220, 220, 220)), (10, 550))
        screen.blit(timer_font.render("Time: " + str(round(current_time/1000, 2)), True, (199, 199, 199)), (350, 10))
        screen.blit(title_font.render("GAME OVER!", True, (199, 199, 199)), (270, 230))
        screen.blit(space_font.render("P1: " + str(player.score), True, player.color), (30, 30))
        screen.blit(space_font.render("P2: " + str(player2.score), True, player2.color), (880, 30))
        # Display winner. Tested against point_goal, the same thing that ended
        # the game, so changing the goal cannot leave the winner unnamed
        for p in (player, player2):
            if p.score >= point_goal:
                screen.blit(space_font.render(p.label + " WINS!", True, p.color), (355, 100))
                screen.blit(p.img, (440, 150))
        # Highscores, saved once per round rather than on every frame
        if not trophy and current_time/1000 < scores[4]:
            trophy = True
            # Drop the slowest time and insert this one
            scores = sorted(scores[:4] + [round(current_time/1000, 2)])
            saveScores(scores)
        if trophy:
            screen.blit(space_font.render("New High Score!", True, (224, 185, 9)), (355, 380))
            screen.blit(loadImage("images/001-trophy.png"), (440, 430))
        # Exit
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                end_screen = False
                start = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    newRound()
                    # Screen flags are loop control, not round state
                    start = True
                    start_screen = True
                    end_screen = False
