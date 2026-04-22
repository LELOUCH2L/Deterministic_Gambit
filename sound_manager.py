# sound_manager.py — Chess sound effects manager
# Place sound files in: assets/sounds/
#
# Expected filenames (your files):
#   move-self.ogg      — your own piece moves
#   move-opponent.ogg  — opponent piece moves
#   capture.ogg        — any capture
#   castle.ogg         — castling
#   move-check.ogg     — move that gives check
#   promote.ogg        — pawn promotion
#   game-end.ogg       — game over
#   game-start.ogg     — game starts
#   illegal.ogg        — illegal move attempt
#   tenseconds.ogg     — low time warning

import pygame
import os

SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'assets', 'sounds')

SOUND_FILES = {
    'move_self':     ['move-self.ogg',     'Move.ogg',     'move.ogg'],
    'move_opponent': ['move-opponent.ogg', 'Move.ogg',     'move.ogg'],
    'capture':       ['capture.ogg',       'Capture.ogg'],
    'castle':        ['castle.ogg',        'Castle.ogg'],
    'check':         ['move-check.ogg',    'Check.ogg'],
    'promote':       ['promote.ogg',       'Promote.ogg'],
    'end':           ['game-end.ogg',      'End.ogg'],
    'start':         ['game-start.ogg',    'Start.ogg'],
    'illegal':       ['illegal.ogg'],
    'tenseconds':    ['tenseconds.ogg'],
    'premove':       ['premove.ogg','Move.ogg','move.ogg'],
}


class SoundManager:
    def __init__(self):
        self.sounds  = {}
        self.enabled = True

        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init(frequency=44100, size=-16,
                                  channels=2, buffer=512)
            except Exception as e:
                print(f"[Sound] mixer init failed: {e}")
                self.enabled = False
                return

        os.makedirs(SOUNDS_DIR, exist_ok=True)
        loaded = 0
        for event, names in SOUND_FILES.items():
            for fname in names:
                path = os.path.join(SOUNDS_DIR, fname)
                if os.path.exists(path):
                    try:
                        self.sounds[event] = pygame.mixer.Sound(path)
                        loaded += 1
                        break
                    except Exception:
                        pass
        if loaded > 0:
            print(f"[Sound] {loaded}/{len(SOUND_FILES)} sound effects loaded from assets/sounds/")
        else:
            print("[Sound] No sound files found in assets/sounds/")
            print("[Sound] Download from: https://github.com/lichess-org/lila/tree/master/public/sound/standard")
            print("[Sound] Expected files: move-self.ogg  move-opponent.ogg  capture.ogg")
            print("[Sound]                 castle.ogg  move-check.ogg  promote.ogg")
            print("[Sound]                 game-end.ogg  game-start.ogg  illegal.ogg")
            print("[Sound]                 tenseconds.ogg  premove.ogg")

    def play(self, event: str):
        if not self.enabled:
            return
        s = self.sounds.get(event)
        if s:
            s.play()
