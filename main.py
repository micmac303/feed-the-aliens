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
player_score = 0
player2_score = 0
point_goal = 100

# Timer
clock = pygame.time.Clock()
current_time = 0

# Frame rate
last_time = time.time()

# Random background colour
colours = [(49, 201, 235), (34, 52, 153), (50, 92, 166), (89, 125, 189), (89, 146, 189), (84, 180, 199),  # Blue
           (163, 11, 11), (207, 41, 41), (194, 39, 98), (199, 42, 94), (168, 5, 5), (189, 0, 126),  # Red
           (122, 0, 156), (145, 24, 196), (171, 34, 199), (77, 13, 181), (120, 76, 207), (96, 3, 171),  # Purple
           (171, 173, 184), (194, 197, 209), (226, 204, 227), (173, 174, 179), (204, 197, 212), (107, 90, 91),  # Gray
           ]

chosen_color = colours[random.randint(0, len(colours) - 1)]
print(chosen_color)

# Load highscores
file = open("Highscore.txt", "r")
highscore = file.readlines()
# Split string in array of score strings
split_scores = highscore[0].split()
# Convert all items to floats
scores = list(map(float, split_scores))
trophy = False

# Player 1
player_img = pygame.image.load("images/001-ufo.png")
rect = player_img.get_rect()
playerX = 200
playerY = 30
shield = False

# Player 2
player2_img = pygame.image.load("images/021-ufo.png")
rect2 = player2_img.get_rect()
player2X = 700
player2Y = 30
shield2 = False

# Animal lists
animals = []
animal_images = ["images/003-cow.png", "images/001-hen.png", "images/003-elephant.png", "images/002-rabbit.png",
                 "images/001-bomb.png", "images/002-truck.png", "images/003-tiger.png"]
rare_animal_images = ["images/001-star.png", "images/001-eagle.png", "images/001-gift.png"]


# Create an animal and add it to animals[]
def summonAnimal(i_arg):
    calculate_rare = random.randint(1, 8)
    if calculate_rare == 8:
        chosen_animal = rare_animal_images[random.randint(0, len(rare_animal_images) - 1)]
    else:
        chosen_animal = animal_images[random.randint(0, len(animal_images) - 1)]

    animal_arg = {
        "image_name": chosen_animal,
        "img": pygame.image.load(chosen_animal),
        "animal_rect": pygame.image.load(chosen_animal).get_rect(),
        "x_pos": ((i_arg + 1) * -81) - 1000,
        "y_pos": random.randint(120, 500),
        "x_velocity": 0
    }
    animals.append(animal_arg)


# Check for star, update star and score
def checkForStar(shield_active, score, obstacle):
    if shield_active:
        shield_active = False
    else:
        if obstacle == "truck":
            score -= 5
        elif obstacle == "bomb":
            score -= 2
    return shield_active, score


# Summon initial animals
for i in range(0, 27):
    summonAnimal(i)

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
        screen.blit(pygame.image.load("images/006-ufo-1.png"), (490, -2))
        screen.blit(pygame.image.load("images/005-alien.png"), (220, 535))
        screen.blit(pygame.image.load("images/001-alien.png"), (660, 535))
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
        # Animal pictures
        screen.blit(pygame.image.load(rare_animal_images[1]), (30, 30))
        screen.blit(points_font.render("+8", True, (199, 199, 199)), (100, 40))
        screen.blit(pygame.image.load(animal_images[2]), (30, 130))
        screen.blit(points_font.render("+5", True, (199, 199, 199)), (100, 140))
        screen.blit(pygame.image.load(animal_images[0]), (30, 230))
        screen.blit(points_font.render("+3", True, (199, 199, 199)), (100, 240))
        screen.blit(pygame.image.load(animal_images[1]), (30, 330))
        screen.blit(points_font.render("+1", True, (199, 199, 199)), (100, 340))
        screen.blit(pygame.image.load(animal_images[3]), (30, 430))
        screen.blit(points_font.render("+1", True, (199, 199, 199)), (100, 440))
        screen.blit(pygame.image.load(animal_images[5]), (910, 30))
        screen.blit(points_font.render("-5", True, (199, 199, 199)), (860, 40))
        screen.blit(pygame.image.load(animal_images[4]), (910, 130))
        screen.blit(points_font.render("-2", True, (199, 199, 199)), (860, 140))
        screen.blit(pygame.image.load(rare_animal_images[2]), (340, 330))
        screen.blit(points_font.render("Random +10 / -10", True, (199, 199, 199)), (420, 345))
        screen.blit(pygame.image.load(animal_images[6]), (340, 400))
        screen.blit(points_font.render("-3 to opponent", True, (199, 199, 199)), (420, 410))
        screen.blit(pygame.image.load(rare_animal_images[0]), (340, 470))
        screen.blit(points_font.render("Single use shield", True, (199, 199, 199)), (420, 480))
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
            if animal["image_name"] == "images/001-eagle.png":
                if animal["x_pos"] > 3200:
                    summonAnimal(0)
                    animals.remove(animal)
            elif animal["x_pos"] > 1100:
                summonAnimal(0)
                animals.remove(animal)
            # Check collision and calculate points
            if rect.colliderect(animal["animal_rect"]):
                animal["y_pos"] = 1000
                if animal["image_name"] == animal_images[0]:  # cow
                    player_score += 3
                if animal["image_name"] == animal_images[1]:  # hen
                    player_score += 1
                if animal["image_name"] == animal_images[2]:  # elephant
                    player_score += 5
                if animal["image_name"] == animal_images[3]:  # rabbit
                    player_score += 1
                if animal["image_name"] == animal_images[4]:  # bomb
                    # Check for star
                    shield, player_score = checkForStar(shield, player_score, "bomb")
                if animal["image_name"] == animal_images[5]:  # truck
                    # Check for star
                    shield, player_score = checkForStar(shield, player_score, "truck")
                if animal["image_name"] == animal_images[6]:  # tiger
                    player2_score -= 3
                if animal["image_name"] == rare_animal_images[0]:  # star
                    shield = True
                if animal["image_name"] == rare_animal_images[1]:  # eagle
                    player_score += 8
                if animal["image_name"] == rare_animal_images[2]:  # present
                    # Calculate random value of present
                    lucky = random .randint(0, 1)
                    if lucky == 0:
                        player_score -= 10
                    else:
                        player_score += 10
            if rect2.colliderect(animal["animal_rect"]):
                animal["y_pos"] = 1000
                if animal["image_name"] == animal_images[0]:  # cow
                    player2_score += 3
                if animal["image_name"] == animal_images[1]:  # hen
                    player2_score += 1
                if animal["image_name"] == animal_images[2]:  # elephant
                    player2_score += 5
                if animal["image_name"] == animal_images[3]:  # rabbit
                    player2_score += 1
                if animal["image_name"] == animal_images[4]:  # bomb
                    # Check for star
                    shield2, player2_score = checkForStar(shield2, player2_score, "bomb")
                if animal["image_name"] == animal_images[5]:  # truck
                    # Check for star
                    shield2, player2_score = checkForStar(shield2, player2_score, "truck")
                if animal["image_name"] == animal_images[6]:  # tiger
                    player_score -= 3
                if animal["image_name"] == rare_animal_images[0]:  # star
                    shield2 = True
                if animal["image_name"] == rare_animal_images[1]:  # eagle
                    player2_score += 8
                if animal["image_name"] == rare_animal_images[2]:  # present
                    # Calculate random value of present
                    lucky = random .randint(0, 1)
                    if lucky == 0:
                        player2_score -= 10
                    else:
                        player2_score += 10
            # Start animal movement
            if animal["image_name"] == rare_animal_images[1] and animal["x_pos"] >= -1000:
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
        # Display winner
        if player_score >= 100:
            screen.blit(space_font.render("PLAYER 1 WINS!", True, (240, 90, 26)), (355, 100))
            screen.blit(player_img, (440, 150))
        if player2_score >= 100:
            screen.blit(space_font.render("PLAYER 2 WINS!", True, (97, 8, 207)), (355, 100))
            screen.blit(player2_img, (440, 150))
        # Highscores
        if current_time/1000 < float(split_scores[4]):
            trophy = True
            new_score = round(current_time/1000, 2)
            split_scores.remove(split_scores[4])
            # Append new score to list
            split_scores.append(str(new_score))
            # Convert all items to floats
            scores = list(map(float, split_scores))
            # Sort scores
            scores.sort()
            # Space separated list and overwrite scores
            file = open("Highscore.txt", "w")
            file.write(" ".join(str(x) for x in scores))
        if trophy:
            screen.blit(space_font.render("New High Score!", True, (224, 185, 9)), (355, 380))
            screen.blit(pygame.image.load("images/001-trophy.png"), (440, 430))
        # Exit
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                end_screen = False
                start = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    # Reset scores & coordinates & shields
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

                    start = True
                    start_screen = True
                    end_screen = False

                    animals.clear()
                    for i in range(0, 27):
                        summonAnimal(i)

                    # Load highscores
                    file = open("Highscore.txt", "r")
                    highscore = file.readlines()
                    # Split string in array of score strings
                    split_scores = highscore[0].split()
                    # Convert all items to floats
                    scores = list(map(float, split_scores))
                    trophy = False

                    chosen_color = colours[random.randint(0, len(colours) - 1)]
                    print(chosen_color)
print(current_time/1000)
