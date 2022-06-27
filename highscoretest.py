new_score = input()
file = open("Highscore.txt", "r")
highscore = file.readlines()
print(highscore)
# Split string in array of score strings
split_scores = highscore[0].split()
# Append new score to list
split_scores.append(new_score)
print(split_scores)
# Convert all items to floats
scores = list(map(float, split_scores))
# Sort scores
scores.sort()
# Space separated list and overwrite scores
file = open("Highscore.txt", "w")
file.write(" ".join(str(x) for x in scores))
