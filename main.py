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

# Per-round state (player_score, playerX, shield, animals, ...) is created by
# newRound() below, so each starting value is written in exactly one place.

# Random background colour
colours = [(49, 201, 235), (34, 52, 153), (50, 92, 166), (89, 125, 189), (89, 146, 189), (84, 180, 199),  # Blue
           (163, 11, 11), (207, 41, 41), (194, 39, 98), (199, 42, 94), (168, 5, 5), (189, 0, 126),  # Red
           (122, 0, 156), (145, 24, 196), (171, 34, 199), (77, 13, 181), (120, 76, 207), (96, 3, 171),  # Purple
           (171, 173, 184), (194, 197, 209), (226, 204, 227), (173, 174, 179), (204, 197, 212), (107, 90, 91),  # Gray
           ]

# Highscores are player data, not source, so Highscore.txt is not in git.
# A fresh clone starts from these defaults.
default_scores = [30.0, 40.0, 50.0, 52.37, 70.0]


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


# A shield absorbs one hit instead of the player taking the penalty
def checkForStar(shield_active, score, penalty):
    if shield_active:
        shield_active = False
    else:
        score += penalty
    return shield_active, score


# Apply one collected animal to the collecting player. Returns the updated
# (score, opponent_score, shield_active) - callers must reassign all three.
def collectAnimal(image_name, score, opponent_score, shield_active):
    animal_type = ANIMALS[image_name]
    effect = animal_type["effect"]
    value = animal_type["value"]

    if effect == "points":
        score += value
    elif effect == "obstacle":
        shield_active, score = checkForStar(shield_active, score, value)
    elif effect == "opponent":
        opponent_score += value
    elif effect == "shield":
        shield_active = True
    elif effect == "random":
        # Calculate random value of present
        if random.randint(0, 1) == 0:
            score -= value
        else:
            score += value

    return score, opponent_score, shield_active


# Reset everything that belongs to a single round. Called once at startup and
# again on restart, so a starting value only ever has to be written here.
# Anything new that should start fresh each round belongs in this function.
def newRound():
    global player_score, player2_score
    global playerX, playerY, shield, rect
    global player2X, player2Y, shield2, rect2
    global scores, trophy, chosen_color
    global current_time, last_time

    # Scores
    player_score = 0
    player2_score = 0

    # Player 1
    rect = player_img.get_rect()
    playerX = 200
    playerY = 30
    shield = False

    # Player 2
    rect2 = player2_img.get_rect()
    player2X = 700
    player2Y = 30
    shield2 = False

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
        if player_score >= point_goal or player2_score >= point_goal:
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
        screen.blit(points_font.render("PLAYER 1", True, (240, 90, 26)), (100, 0))
        screen.blit(points_font.render("WASD", True, (240, 90, 26)), (100, 30))
        screen.blit(huge_font.render(str(player_score), True, (181, 91, 53)), (20, 150))
        screen.blit(points_font.render("PLAYER 2", True, (97, 8, 207)), (780, 0))
        screen.blit(points_font.render("ARROW KEYS", True, (97, 8, 207)), (780, 30))
        screen.blit(huge_font.render(str(player2_score), True, (125, 99, 171)), (530, 150))
        # Load and update hitboxes
        if shield:
            rect = pygame.draw.rect(screen, (66, 239, 245), (playerX, playerY, 64, 64), 6)
        if shield2:
            rect2 = pygame.draw.rect(screen, (66, 239, 245), (player2X, player2Y, 64, 64), 6)
        rect = pygame.draw.rect(screen, (0, 0, 0), (playerX + 16, playerY + 16, 32, 32), 0)
        rect2 = pygame.draw.rect(screen, (0, 0, 0), (player2X + 16, player2Y + 16, 32, 32), 0)
        # Load players
        screen.blit(player2_img, (player2X, player2Y))
        screen.blit(player_img, (playerX, playerY))
        # Player movement and update players and collide with edge of screen
        keys = pygame.key.get_pressed()
        if keys[pygame.K_a] and playerX > 0:
            playerX -= 5.8 * dt
        if keys[pygame.K_d] and playerX < 936:
            playerX += 7 * dt
        if keys[pygame.K_w] and playerY > -8:
            playerY -= 5.9 * dt
        if keys[pygame.K_s] and playerY < 544:
            playerY += 5.9 * dt
        if keys[pygame.K_LEFT] and player2X > 0:
            player2X -= 5.8 * dt
        if keys[pygame.K_RIGHT] and player2X < 936:
            player2X += 7 * dt
        if keys[pygame.K_UP] and player2Y > -8:
            player2Y -= 5.9 * dt
        if keys[pygame.K_DOWN] and player2Y < 544:
            player2Y += 5.9 * dt
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
            if rect.colliderect(animal["animal_rect"]):
                animal["y_pos"] = 1000
                player_score, player2_score, shield = collectAnimal(
                    animal["image_name"], player_score, player2_score, shield)
            if rect2.colliderect(animal["animal_rect"]):
                animal["y_pos"] = 1000
                player2_score, player_score, shield2 = collectAnimal(
                    animal["image_name"], player2_score, player_score, shield2)
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
        screen.blit(space_font.render("P1: " + str(player_score), True, (240, 90, 26)), (30, 30))
        screen.blit(space_font.render("P2: " + str(player2_score), True, (97, 8, 207)), (880, 30))
        # Display winner. Tested against point_goal, the same thing that ended
        # the game, so changing the goal cannot leave the winner unnamed
        if player_score >= point_goal:
            screen.blit(space_font.render("PLAYER 1 WINS!", True, (240, 90, 26)), (355, 100))
            screen.blit(player_img, (440, 150))
        if player2_score >= point_goal:
            screen.blit(space_font.render("PLAYER 2 WINS!", True, (97, 8, 207)), (355, 100))
            screen.blit(player2_img, (440, 150))
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
