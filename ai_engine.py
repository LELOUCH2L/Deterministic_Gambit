# ai_engine.py — Stockfish AI Engine wrapper

import subprocess
import os
import sys


class AIEngine:
    """
    Handles communication with the Stockfish chess engine via UCI protocol.

    Stockfish is bundled in the project folder so GitHub users get it
    automatically. The engine is searched in this order:
      1. Inside the project folder (any common Stockfish filename)
      2. Common system-wide install locations
      3. Falls back to random-move AI if nothing is found
    """

    # Project folder = same directory as this file
    PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

    # All common Stockfish binary names across platforms
    # Put these inside your project folder and it will be found automatically
    PROJECT_FILENAMES = [
        'stockfish.exe',            # Windows (most common)
        'stockfish',                # Linux / macOS
        'stockfish-windows-x86-64-avx2.exe',   # Stockfish 16/17 Windows download name
        'stockfish-windows-x86-64.exe',
        'stockfish-windows-x86-64-bmi2.exe',
        'stockfish-ubuntu-x86-64-avx2',        # Stockfish 16/17 Linux download name
        'stockfish-ubuntu-x86-64',
        'stockfish-macos-x86-64-avx2',         # Stockfish 16/17 macOS download name
        'stockfish-macos-x86-64',
        'stockfish-macos-m1-apple-silicon',
    ]

    # Fallback: common system-wide locations
    SYSTEM_PATHS = [
        'stockfish',                            # on PATH
        '/usr/bin/stockfish',                   # Linux apt install
        '/usr/local/bin/stockfish',
        '/opt/homebrew/bin/stockfish',          # macOS Homebrew
        r'C:\stockfish\stockfish.exe',
        r'C:\Program Files\stockfish\stockfish.exe',
    ]

    def __init__(self, engine_path=None, skill_level=10, depth=15):
        """
        engine_path : explicit path override (leave None to auto-detect).
        skill_level : 0 (easiest) – 20 (hardest).
        depth       : search depth per move.
        """
        self.skill_level = skill_level
        self.depth       = depth
        self._process    = None
        self.available   = False

        self.engine_path = engine_path or self._find_stockfish()

        if self.engine_path:
            try:
                self._start()
                self.available = True
                print(f"[AIEngine] Stockfish ready: {os.path.basename(self.engine_path)}")
            except Exception as e:
                print(f"[AIEngine] Found Stockfish but could not start it: {e}")
                print(f"[AIEngine] Path tried: {self.engine_path}")
        else:
            print("[AIEngine] Stockfish not found — using random-move fallback AI.")
            print("[AIEngine] Put stockfish.exe (Windows) or stockfish (Mac/Linux)")
            print(f"[AIEngine] inside your project folder: {self.PROJECT_DIR}")

    # ------------------------------------------------------------------ #
    #  Engine discovery                                                    #
    # ------------------------------------------------------------------ #

    def _find_stockfish(self):
        """
        Search for the Stockfish binary.
        Checks the project folder first so bundled copies are always used.
        """
        # 1. Look inside the project folder
        for filename in self.PROJECT_FILENAMES:
            path = os.path.join(self.PROJECT_DIR, filename)
            if os.path.isfile(path):
                # On Mac/Linux make sure it's executable
                if sys.platform != 'win32':
                    os.chmod(path, 0o755)
                if self._test_binary(path):
                    return path

        # 2. Check common system locations
        for path in self.SYSTEM_PATHS:
            if self._test_binary(path):
                return path

        return None

    def _test_binary(self, path):
        """Return True if the path runs successfully as a Stockfish binary."""
        try:
            result = subprocess.run(
                [path], input='quit\n',
                capture_output=True, text=True, timeout=3
            )
            return True     # any response = it works
        except (FileNotFoundError, subprocess.TimeoutExpired,
                OSError, PermissionError):
            return False

    # ------------------------------------------------------------------ #
    #  Process management                                                  #
    # ------------------------------------------------------------------ #

    def _start(self):
        self._process = subprocess.Popen(
            [self.engine_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1
        )
        self._send('uci')
        self._wait_for('uciok')
        self._send('isready')
        self._wait_for('readyok')
        self._send(f'setoption name Skill Level value {self.skill_level}')

    def _send(self, command):
        if self._process and self._process.stdin:
            self._process.stdin.write(command + '\n')
            self._process.stdin.flush()

    def _wait_for(self, token, timeout=5):
        import time
        start = time.time()
        while time.time() - start < timeout:
            line = self._process.stdout.readline().strip()
            if token in line:
                return line
        return ''

    def _read_until_bestmove(self, timeout=10):
        import time
        start = time.time()
        while time.time() - start < timeout:
            line = self._process.stdout.readline().strip()
            if line.startswith('bestmove'):
                parts = line.split()
                if len(parts) >= 2 and parts[1] != '(none)':
                    return parts[1]
                break
        return None

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def send_position(self, fen):
        if self._process:
            self._send(f'position fen {fen}')

    def get_best_move(self, fen):
        """
        Returns the best move in UCI format (e.g. 'e2e4'), or None if
        Stockfish is unavailable.
        """
        if not self.available or self._process is None:
            return None
        self.send_position(fen)
        self._send(f'go depth {self.depth}')
        return self._read_until_bestmove()

    def receive_move(self, uci_move):
        """
        Converts a UCI move string (e.g. 'e2e4') to board coordinates.
        Returns ((from_row, from_col), (to_row, to_col)) or (None, None).
        """
        if not uci_move or len(uci_move) < 4:
            return None, None
        files = 'abcdefgh'
        try:
            fc = files.index(uci_move[0])
            fr = 8 - int(uci_move[1])
            tc = files.index(uci_move[2])
            tr = 8 - int(uci_move[3])
            return (fr, fc), (tr, tc)
        except (ValueError, IndexError):
            return None, None

    def get_evaluation(self, fen):
        """
        Returns centipawn score for the side to move (positive = advantage).
        Returns 0.0 if Stockfish is unavailable.
        """
        if not self.available or self._process is None:
            return 0.0
        self.send_position(fen)
        self._send('go depth 10')
        score = 0.0
        import time
        start = time.time()
        while time.time() - start < 8:
            line = self._process.stdout.readline().strip()
            if 'score cp' in line:
                parts = line.split()
                idx   = parts.index('cp')
                score = int(parts[idx + 1]) / 100.0
            elif 'score mate' in line:
                parts   = line.split()
                idx     = parts.index('mate')
                mate_in = int(parts[idx + 1])
                score   = 999.0 if mate_in > 0 else -999.0
            elif line.startswith('bestmove'):
                break
        return score

    def quit(self):
        if self._process:
            try:
                self._send('quit')
                self._process.wait(timeout=2)
            except Exception:
                self._process.kill()
            self._process = None
