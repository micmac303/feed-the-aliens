"""Chiptune sound effects, synthesised at startup - no audio files.

Every effect is built from square/sine waves and filtered noise using only
the stdlib (math/array/random) and handed to pygame.mixer as raw samples,
so there are no binary assets to ship and nothing to download. Swapping a
synthesised effect for a recorded file later is one line: replace its
recipe in init() with pygame.mixer.Sound("sounds/whatever.wav").

main.py calls init() once after pygame.init() and play(name) everywhere
else. If the mixer failed to start (no audio device) both are safe no-ops -
the game just runs silent.
"""

import array
import math
import random

import pygame

# Presentation-only randomness (picking between blip variants), so it never
# touches the sim's seeded rng stream
_rand = random.Random()

_rate = 44100
_sounds = {}


def _to_sound(samples):
    # The mixer wants interleaved int16 frames, one value per channel
    channels = pygame.mixer.get_init()[2]
    buf = array.array("h")
    for s in samples:
        v = int(max(-1.0, min(1.0, s)) * 32767)
        for _ in range(channels):
            buf.append(v)
    return pygame.mixer.Sound(buffer=buf.tobytes())


def _tone(freq_start, freq_end, dur, volume, shape="square"):
    # One note: linear pitch slide, a few ms of attack so it does not click,
    # squared decay so it rings briefly then dies
    n = int(_rate * dur)
    attack = max(1, int(_rate * 0.004))
    phase = 0.0
    out = []
    for i in range(n):
        t = i / n
        freq = freq_start + (freq_end - freq_start) * t
        phase += 2 * math.pi * freq / _rate
        s = math.sin(phase)
        if shape == "square":
            s = 1.0 if s >= 0 else -1.0
        out.append(s * volume * min(1.0, i / attack) * (1 - t) ** 2)
    return out


def _notes(seq, volume, shape="square"):
    # A little melody: each (freq, duration) note with its own envelope
    out = []
    for freq, dur in seq:
        out += _tone(freq, freq, dur, volume, shape)
    return out


def _noise(dur, volume, brightness):
    # Filtered white noise: brightness near 1 is a sharp crack, near 0 a
    # low rumbling boom (one-pole lowpass)
    n = int(_rate * dur)
    level = 0.0
    out = []
    for i in range(n):
        level += brightness * (_rand.uniform(-1.0, 1.0) - level)
        out.append(level * volume * (1 - i / n) ** 2)
    return out


def init():
    """Build every effect. A missing or failed mixer leaves the table empty."""
    global _rate, _sounds
    _sounds = {}
    if pygame.mixer.get_init() is None:
        return
    _rate, size, _ = pygame.mixer.get_init()
    if abs(size) != 16:  # _to_sound writes int16 frames
        return
    build = {
        # Three pitches of the same blip so constant collecting does not drone
        "collect": [_tone(600, 900, 0.09, 0.30),
                    _tone(700, 1050, 0.09, 0.30),
                    _tone(800, 1200, 0.09, 0.30)],
        # High-value animals (the swan, the eagle) get a richer two-note chime
        "collect_big": [_notes([(784, 0.07), (1046.5, 0.12)], 0.35)],
        "hurt": [_tone(320, 140, 0.2, 0.4)],
        "zap": [_tone(1300, 150, 0.15, 0.35)],  # points taken off the opponent
        "shield_up": [_notes([(523.25, 0.1), (784, 0.16)], 0.35, shape="sine")],
        "shield_break": [_noise(0.12, 0.6, 0.7)],
        "explosion": [_noise(0.7, 0.9, 0.08)],
        # Menu sounds are mechanical clicks (tiny noise bursts), not beeps:
        # a light tick to move, and a click-clack pair to confirm
        "menu_move": [_noise(0.018, 0.5, 0.85)],
        "menu_select": [_noise(0.018, 0.5, 0.85)
                        + [0.0] * int(_rate * 0.05)
                        + _noise(0.03, 0.6, 0.35)],
        "jingle_win": [_notes([(523.25, 0.14), (659.25, 0.14), (784, 0.14),
                               (1046.5, 0.4)], 0.35)],
        "jingle_lose": [_notes([(392, 0.18), (329.63, 0.18), (261.63, 0.18),
                                (220, 0.5)], 0.35)],
        "trophy": [_notes([(523.25, 0.11), (659.25, 0.11), (784, 0.11),
                           (1046.5, 0.11), (784, 0.11), (1046.5, 0.45)], 0.35)],
    }
    _sounds = {name: [_to_sound(s) for s in variants]
               for name, variants in build.items()}


def play(name):
    """Play one effect by name; unknown names and a silent mixer are no-ops."""
    variants = _sounds.get(name)
    if variants:
        _rand.choice(variants).play()
