# game.py — Deterministic Gambit game logic

import time, random, copy
from board  import Board
from pieces import Pawn
from ai_engine import AIEngine
from statistics_manager import StatisticsManager

PIECE_VALUES = {'queen':9,'rook':5,'bishop':3,'knight':3,'pawn':1,'king':0}

# Skill → (movetime_ms, depth) — properly calibrated
# Low levels use random/weak moves, higher levels get more depth + time
SKILL_PARAMS = {
    1:  (50,   1),   # Beginner  — nearly random (depth 1 only)
    3:  (100,  2),   # Easy      — very shallow
    7:  (200,  4),   # Medium    — moderate
    12: (500,  8),   # Hard      — decent strength
    17: (1000,12),   # Expert    — strong
    20: (2000,18),   # Master    — near full strength
}

EVAL_ANCHOR = 1500   # centipawns — ±15.0 for graph


class Game:
    def __init__(self, ai_path=None, ai_skill=10, ai_depth=15,
                 player_color='white', time_limit=None):
        self.board          = Board()
        self.player_color   = player_color
        self.ai_color       = 'black' if player_color=='white' else 'white'
        self.current_player = 'white'
        self.game_over      = False
        self.result         = None
        self.in_check       = False
        self.is_checkmate   = False
        self.is_stalemate   = False
        self.last_promotion = None
        self.last_was_capture = False
        self.last_was_castle  = False

        self.move_history = []
        self.view_index   = -1

        self.fullmove       = 1
        self.halfmove_clock = 0
        self.last_eval      = 0.0
        self.piece_score    = 0

        # Time control — each side has its own pool; only the active side's
        # pool counts down. reset _turn_start each time a turn begins.
        self.time_limit         = time_limit
        self.player_time_left   = float(time_limit) if time_limit else None
        self.ai_time_left       = float(time_limit) if time_limit else None
        self._turn_start        = time.time()
        self._active_clock      = player_color   # whose clock is ticking now
        self.time_warning_fired = False

        # Pre-move storage: (from_pos, to_pos) or None
        self.premove = None

        # Grab real depth from calibration
        _, depth = SKILL_PARAMS.get(ai_skill, (500, ai_depth))

        self.stats = StatisticsManager()
        self.ai    = AIEngine(engine_path=ai_path,
                              skill_level=ai_skill,
                              depth=depth)
        self.stats.start_move_timer()
        self.is_continued = False

    # ------------------------------------------------------------------ #
    #  Clock                                                               #
    # ------------------------------------------------------------------ #

    def start_turn_clock(self, color):
        """Call when a new turn begins for `color`."""
        self._active_clock  = color
        self._turn_start    = time.time()
        self.time_warning_fired = False

    def tick_clock(self):
        """Call each frame. Returns True if the active side has flagged."""
        if self.time_limit is None or self.game_over:
            return False
        elapsed = time.time() - self._turn_start
        if self._active_clock == self.player_color:
            self.player_time_left = max(0.0,
                (self.player_time_left or self.time_limit) - elapsed)
            # reset baseline so next tick measures from now
            self._turn_start = time.time()
            if self.player_time_left <= 0:
                self.game_over = True
                self.result    = 'AI Win'
                self.stats.save_game_data(self.result, self.player_color)
                self.ai.quit()
                return True
        # AI clock ticks in _execute_move
        return False

    def deduct_move_time(self, color):
        """Deduct the time used for this move from the side's pool."""
        used = time.time() - self._turn_start
        if color == self.player_color and self.player_time_left is not None:
            self.player_time_left = max(0.0, self.player_time_left - used)
        elif color == self.ai_color and self.ai_time_left is not None:
            self.ai_time_left = max(0.0, self.ai_time_left - used)

    def player_time_display(self):
        t = self.player_time_left if self.player_time_left is not None else 0
        return int(t)//60, int(t)%60

    # ------------------------------------------------------------------ #
    #  Turns                                                               #
    # ------------------------------------------------------------------ #

    def switch_turn(self):
        self.current_player = ('black' if self.current_player=='white'
                               else 'white')
        if self.current_player == 'white':
            self.fullmove += 1
        self.stats.start_move_timer()
        self.start_turn_clock(self.current_player)

    def is_player_turn(self):
        return (self.current_player == self.player_color
                and not self.game_over
                and self.view_index == -1)

    def get_legal_moves_for(self, piece):
        return self.board.get_legal_moves(piece)

    # ------------------------------------------------------------------ #
    #  Piece score                                                         #
    # ------------------------------------------------------------------ #

    def _compute_piece_score(self):
        score = 0
        for p in self.board.piece_list:
            v = PIECE_VALUES.get(p.piece_type, 0)
            score += v if p.color == self.player_color else -v
        self.piece_score = score

    # ------------------------------------------------------------------ #
    #  Pre-move                                                            #
    # ------------------------------------------------------------------ #

    def set_premove(self, from_pos, to_pos):
        self.premove = (from_pos, to_pos)

    def clear_premove(self):
        self.premove = None

    def try_premove(self):
        """Attempt the stored pre-move. Returns True if executed."""
        if not self.premove:
            return False
        fp, tp = self.premove
        self.premove = None
        piece = self.board.get_piece(*fp)
        if piece and piece.color == self.player_color:
            if tp in self.board.get_legal_moves(piece):
                self._execute_move(fp, tp, self.player_color, piece)
                return True
        return False

    # ------------------------------------------------------------------ #
    #  Moves                                                               #
    # ------------------------------------------------------------------ #

    def make_human_move(self, from_pos, to_pos):
        piece = self.board.get_piece(*from_pos)
        if piece is None or piece.color != self.player_color:
            return False
        if to_pos not in self.board.get_legal_moves(piece):
            return False
        self.deduct_move_time(self.player_color)
        self._execute_move(from_pos, to_pos, self.player_color, piece)
        return True

    def make_ai_move(self):
        if self.game_over:
            return None, None
        active   = 'w' if self.current_player=='white' else 'b'
        fen      = self.board.to_fen(active_color=active,
                                     halfmove=self.halfmove_clock,
                                     fullmove=self.fullmove)
        movetime, _ = SKILL_PARAMS.get(self.ai.skill_level, (500, 10))
        uci_move = self.ai.get_best_move(fen)
        if uci_move:
            from_pos, to_pos = self.ai.receive_move(uci_move)
        else:
            from_pos, to_pos = self._random_legal_move(self.ai_color)
        if from_pos is None:
            return None, None
        piece = self.board.get_piece(*from_pos)
        if piece is None:
            return None, None
        self.deduct_move_time(self.ai_color)
        self._execute_move(from_pos, to_pos, self.ai_color, piece)
        return from_pos, to_pos

    def _execute_move(self, from_pos, to_pos, player, piece):
        piece_type = piece.piece_type
        target     = self.board.get_piece(*to_pos)
        self.last_was_capture = target is not None
        self.last_was_castle  = (piece_type=='king'
                                 and abs(from_pos[1]-to_pos[1])==2)

        # Eval is always from WHITE's perspective, positive = white better
        active = 'w' if player=='white' else 'b'
        fen    = self.board.to_fen(active_color=active,
                                   halfmove=self.halfmove_clock,
                                   fullmove=self.fullmove)
        raw_eval = self.ai.get_evaluation(fen) if self.ai.available else 0.0
        # Stockfish get_evaluation returns score for side to move.
        # Convert to always-white-positive:
        eval_score = raw_eval if player=='white' else -raw_eval
        eval_score = max(-EVAL_ANCHOR/100, min(EVAL_ANCHOR/100, eval_score))
        self.last_eval = eval_score

        board_snapshot  = copy.deepcopy(self.board)
        promotion_type  = self.board.move_piece(from_pos, to_pos)
        self.last_promotion = promotion_type

        notation      = self._build_notation(piece_type, from_pos, to_pos,
                                             self.last_was_capture, promotion_type)
        move_duration = round(time.time()-self.stats.move_start_time, 1)

        self.move_history.append({
            'from_pos':        from_pos,
            'to_pos':          to_pos,
            'piece_type':      piece_type,
            'color':           player,
            'notation':        notation,
            'eval':            eval_score,
            'promotion':       promotion_type,
            'board_snapshot':  board_snapshot,
            'duration':        move_duration if player==self.player_color else None,
            'piece_score':     self.piece_score,
            'last_was_capture':self.last_was_capture,
            'last_was_castle': self.last_was_castle,
        })
        self.view_index = -1

        if piece_type=='pawn' or self.last_was_capture:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        self._compute_piece_score()
        self.stats.record_move(player=player, piece_type=piece_type,
                               from_pos=from_pos, to_pos=to_pos,
                               eval_score=eval_score,
                               promotion_piece=promotion_type)
        self.check_game_end()
        if not self.game_over:
            self.switch_turn()
        else:
            self._fetch_final_eval()

    def _fetch_final_eval(self):
        if not self.ai.available:
            return
        active = 'w' if self.current_player=='white' else 'b'
        fen    = self.board.to_fen(active_color=active,
                                   halfmove=self.halfmove_clock,
                                   fullmove=self.fullmove)
        raw   = self.ai.get_evaluation(fen)
        score = raw if self.current_player=='white' else -raw
        score = max(-EVAL_ANCHOR/100, min(EVAL_ANCHOR/100, score))
        self.last_eval = score
        self.stats.record_move(player=self.current_player,
                               piece_type='(end)',
                               from_pos=None, to_pos=None,
                               eval_score=score, promotion_piece=None)

    # ------------------------------------------------------------------ #
    #  History browsing                                                    #
    # ------------------------------------------------------------------ #

    def browse_to(self, index):
        """Jump directly to a history index (-1 = live)."""
        if index < 0 or index >= len(self.move_history):
            self.view_index = -1
        else:
            self.view_index = index

    def browse_back(self):
        if not self.move_history: return None
        if self.view_index == -1:
            self.view_index = len(self.move_history)-1
        elif self.view_index > 0:
            self.view_index -= 1
        else:
            return None   # already at turn 0, cannot go further back
        return self.move_history[self.view_index]['board_snapshot']

    def browse_forward(self):
        if self.view_index == -1: return None
        self.view_index += 1
        if self.view_index >= len(self.move_history):
            self.view_index = -1; return None
        return self.move_history[self.view_index]['board_snapshot']

    def get_display_board(self):
        if self.view_index == -1: return self.board
        return self.move_history[self.view_index]['board_snapshot']

    def get_history_highlight(self):
        if self.view_index == -1 or not self.move_history:
            return None, None
        # Board at view_index shows state BEFORE move[view_index].
        # The last played move is move[view_index-1].
        prev = self.view_index - 1
        if prev < 0:
            return None, None
        m = self.move_history[prev]
        return m['from_pos'], m['to_pos']

    def get_display_piece_score(self):
        """Piece score for the currently viewed board position."""
        if self.view_index == -1 or not self.move_history:
            return self.piece_score
        return self.move_history[self.view_index].get('piece_score', 0)

    # ------------------------------------------------------------------ #
    #  End detection                                                       #
    # ------------------------------------------------------------------ #

    def check_game_end(self):
        opponent      = 'black' if self.current_player=='white' else 'white'
        self.in_check = self.board.is_in_check(opponent)
        no_moves      = not self.board.has_any_legal_moves(opponent)
        if no_moves:
            self.game_over    = True
            self.is_checkmate = self.in_check
            self.is_stalemate = not self.in_check
            if self.in_check:
                self.result = ('Player Win' if opponent==self.ai_color
                               else 'AI Win')
            else:
                self.result = 'Draw'
            self.stats.save_game_data(self.result, self.player_color)
            self.ai.quit()
        elif self.halfmove_clock >= 100 or self._is_insufficient_material():
            self.game_over = True; self.result = 'Draw'
            self.stats.save_game_data(self.result, self.player_color)
            self.ai.quit()

    def _is_insufficient_material(self):
        types = [p.piece_type for p in self.board.piece_list]
        if set(types)=={'king'}: return True
        if len(self.board.piece_list)==3 and set(types)<=({'king','bishop'}
            | {'king','knight'}): return True
        return False

    # ------------------------------------------------------------------ #
    #  Save / restore                                                      #
    # ------------------------------------------------------------------ #

    def save_state(self):
        import pickle
        # Strip board_snapshot from history for smaller file, restore on load
        hist_stripped = []
        for m in self.move_history:
            mc = {k:v for k,v in m.items() if k != 'board_snapshot'}
            hist_stripped.append(mc)
        return pickle.dumps({
            'player_color':    self.player_color,
            'move_history':    hist_stripped,
            'fullmove':        self.fullmove,
            'halfmove_clock':  self.halfmove_clock,
            'result':          self.result,
            'game_over':       self.game_over,
            'piece_score':     self.piece_score,
            'player_time_left':self.player_time_left,
            'ai_time_left':    self.ai_time_left,
            'time_limit':      self.time_limit,
            'ai_skill':        self.ai.skill_level,
            'ai_depth':        self.ai.depth,
            'move_start_time':  self.stats.move_start_time,
            # Rebuild board by replaying moves on load
            'moves_to_replay': [(m['from_pos'],m['to_pos'])
                                for m in self.move_history
                                if m.get('from_pos') and m.get('to_pos')],
        })

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _random_legal_move(self, color):
        pieces = [p for p in self.board.piece_list if p.color==color]
        random.shuffle(pieces)
        for p in pieces:
            moves = self.board.get_legal_moves(p)
            if moves: return p.position, random.choice(moves)
        return None, None

    def _build_notation(self, piece_type, from_pos, to_pos,
                        is_capture, promotion):
        if piece_type == 'king' and abs(from_pos[1] - to_pos[1]) == 2:
            return 'O-O' if to_pos[1] == 6 else 'O-O-O'
        files = 'abcdefgh'
        pc = {'king':'K','queen':'Q','rook':'R',
              'bishop':'B','knight':'N','pawn':''}.get(piece_type,'?')
        fp = files[from_pos[1]]+str(8-from_pos[0])
        tp = files[to_pos[1]] +str(8-to_pos[0])
        base = f"{pc}{fp}{'x' if is_capture else '-'}{tp}"
        if promotion:
            base += '='+{'queen':'Q','rook':'R',
                         'bishop':'B','knight':'N'}.get(promotion,'?')
        return base

    def resign(self):
        self.game_over = True; self.result = 'AI Win'
        self.stats.save_game_data(self.result, self.player_color)
        self.ai.quit()
