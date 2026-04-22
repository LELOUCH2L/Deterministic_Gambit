# statistics_manager.py — Records per-move gameplay data to CSV

import csv
import os
import time
from datetime import datetime


class StatisticsManager:
    """
    Records gameplay statistics per move (as required by project spec).
    Data is saved to two CSV files:
      - move_data.csv   : per-move records (100+ rows per ~3 games)
      - game_data.csv   : per-game summary records
    """

    MOVE_CSV = 'data/move_data.csv'
    GAME_CSV = 'data/game_data.csv'

    MOVE_HEADERS = [
        'game_id', 'turn_number', 'player', 'piece_moved',
        'from_square', 'to_square', 'move_duration_sec',
        'eval_score', 'is_promotion', 'promotion_piece'
    ]
    GAME_HEADERS = [
        'game_id', 'date', 'result', 'player_color', 'total_moves',
        'game_duration_sec', 'promotion_count', 'promotion_types'
    ]

    def __init__(self):
        # --- Per-move state ---
        self.game_id = self._generate_game_id()
        self.turn_number = 0
        self.move_count = 0
        self.promotion_count = 0
        self.promotion_types = []
        self.game_result = None
        self.evaluation_history = []   # list of eval scores per turn

        # --- Timing ---
        self.game_start_time = time.time()
        self.move_start_time = time.time()
        self._paused_at = None   # set when ESC pauses
        self.game_duration = 0.0

        # Ensure data directory and CSV files exist
        os.makedirs('data', exist_ok=True)
        self._ensure_csv(self.MOVE_CSV, self.MOVE_HEADERS)
        self._ensure_csv(self.GAME_CSV, self.GAME_HEADERS)

    # ------------------------------------------------------------------ #
    #  Public API called by Game                                           #
    # ------------------------------------------------------------------ #

    def start_move_timer(self):
        """Call this when it becomes a player's turn."""
        # Don't reset if we're resuming a continued game on the very first move
        # — move_start_time will be set to now() which is wrong.
        # We set it here; callers that load a game should reset this after.
        self.move_start_time = time.time()

    def record_move(self, player, piece_type, from_pos, to_pos,
                    eval_score=0.0, promotion_piece=None):
        """
        Record a single move to move_data.csv.
        player: 'white' or 'black'
        piece_type: e.g. 'pawn', 'rook'
        from_pos / to_pos: (row, col) tuples
        eval_score: Stockfish centipawn score (float)
        promotion_piece: str like 'queen' or None
        """
        self.turn_number += 1
        self.move_count += 1
        move_duration = round(time.time() - self.move_start_time, 2)
        self.evaluation_history.append(eval_score)

        is_promotion = promotion_piece is not None
        if is_promotion:
            self.record_promotion(promotion_piece)

        row = {
            'game_id': self.game_id,
            'turn_number': self.turn_number,
            'player': player,
            'piece_moved': piece_type,
            'from_square': self._pos_to_square(from_pos),
            'to_square': self._pos_to_square(to_pos),
            'move_duration_sec': move_duration,
            'eval_score': eval_score,
            'is_promotion': is_promotion,
            'promotion_piece': promotion_piece or ''
        }
        self._append_row(self.MOVE_CSV, self.MOVE_HEADERS, row)

    def record_promotion(self, piece_type):
        """Increment promotion counter and store piece type."""
        self.promotion_count += 1
        self.promotion_types.append(piece_type)

    def save_game_data(self, result, player_color='white'):
        """
        Call at game end.
        result: 'Player Win', 'AI Win', or 'Draw'
        """
        self.game_result = result
        self.game_duration = round(time.time() - self.game_start_time, 2)

        row = {
            'game_id': self.game_id,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'result': result,
            'player_color': player_color,
            'total_moves': self.move_count,
            'game_duration_sec': self.game_duration,
            'promotion_count': self.promotion_count,
            'promotion_types': ','.join(self.promotion_types) if self.promotion_types else ''
        }
        self._append_row(self.GAME_CSV, self.GAME_HEADERS, row)

    # ------------------------------------------------------------------ #
    #  Data loading (for statistics window)                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def load_move_data():
        """Returns list of dicts from move_data.csv."""
        return StatisticsManager._load_csv(StatisticsManager.MOVE_CSV)

    @staticmethod
    def load_game_data():
        """Returns list of dicts from game_data.csv."""
        return StatisticsManager._load_csv(StatisticsManager.GAME_CSV)

    @staticmethod
    def compute_summary(data, field):
        """Compute mean, median, max, min, SD for a numeric field."""
        import statistics as st
        values = []
        for row in data:
            try:
                values.append(float(row[field]))
            except (ValueError, KeyError):
                pass
        if not values:
            return {'mean': 0, 'median': 0, 'max': 0, 'min': 0, 'sd': 0, 'count': 0}
        return {
            'mean': round(st.mean(values), 2),
            'median': round(st.median(values), 2),
            'max': round(max(values), 2),
            'min': round(min(values), 2),
            'sd': round(st.pstdev(values), 2),
            'count': len(values)
        }

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _generate_game_id():
        return datetime.now().strftime('G%Y%m%d%H%M%S')

    @staticmethod
    def _pos_to_square(pos):
        """Convert (row, col) to chess notation like 'e4'."""
        if pos is None:
            return '??'
        row, col = pos
        return 'abcdefgh'[col] + str(8 - row)

    @staticmethod
    def _ensure_csv(path, headers):
        if not os.path.exists(path):
            with open(path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()

    @staticmethod
    def _append_row(path, headers, row):
        with open(path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writerow(row)

    @staticmethod
    def _load_csv(path):
        if not os.path.exists(path):
            return []
        with open(path, 'r', newline='') as f:
            return list(csv.DictReader(f))
