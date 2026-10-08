# Feed The Aliens
Control the alien craft and eat up all the animals to gain points, avoid trucks and bombs.

Chance your luck with the wrapped present surprise item.

Grab a shield to protect you from the bombs and cars.

To run the game simply execute the following command at the command prompt, navigate to feed-the-aliens/main.py

python main.py

You may have to install python first
### install python
https://www.python.org/downloads/

once python is installed...

### Install pygame

pip install pygame

Then simply run with:

python main.py

Enjoy
### Starting again from scratch

Your progress lives in a few files next to `main.py`: `AdventureProgress.txt`
(stars), `FishFound.txt` (bonus fish) and one `*Highscore.txt` per level.
Delete or move them and the game starts fresh - nothing else to set up.
`Settings.txt` (badges, fullscreen) is a preference, so leave it.

To keep an old save, move those files into a dated folder under
`save-backups/` (it is ignored by git). To bring it back, quit the game and
copy them back next to `main.py`:

    cp save-backups/2026-10-08/* .
