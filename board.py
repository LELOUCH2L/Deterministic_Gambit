# board.py — Board class

import copy
from pieces import Pawn, Rook, Knight, Bishop, Queen, King


class Board:
    """Represents the chessboard and manages piece positions."""

    def __init__(self):
        self.board_grid = [[None] * 8 for _ in range(8)]
        self.piece_list = []
        self.en_passant_target = None   # (row, col) of capturable pawn
        self.initialize_board()

    # ------------------------------------------------------------------ #
    #  Setup                                                               #
    # ------------------------------------------------------------------ #

    def initialize_board(self):
        """Place all pieces in starting positions."""
        self.board_grid = [[None] * 8 for _ in range(8)]
        self.piece_list = []

        # Back-rank order
        back_rank = [Rook, Knight, Bishop, Queen, King, Bishop, Knight, Rook]

        for col, PieceClass in enumerate(back_rank):
            # Black back rank (row 0)
            bp = PieceClass('black', (0, col))
            self.board_grid[0][col] = bp
            self.piece_list.append(bp)
            # White back rank (row 7)
            wp = PieceClass('white', (7, col))
            self.board_grid[7][col] = wp
            self.piece_list.append(wp)

        # Pawns
        for col in range(8):
            bp = Pawn('black', (1, col))
            self.board_grid[1][col] = bp
            self.piece_list.append(bp)
            wp = Pawn('white', (6, col))
            self.board_grid[6][col] = wp
            self.piece_list.append(wp)

    # ------------------------------------------------------------------ #
    #  Accessors                                                           #
    # ------------------------------------------------------------------ #

    def get_piece(self, row, col):
        return self.board_grid[row][col]

    def get_king(self, color):
        for piece in self.piece_list:
            if piece.piece_type == 'king' and piece.color == color:
                return piece
        return None

    # ------------------------------------------------------------------ #
    #  Move execution                                                      #
    # ------------------------------------------------------------------ #

    def move_piece(self, from_pos, to_pos):
        """
        Move a piece and handle special rules:
        - En passant capture
        - Castling
        - Pawn promotion (file-based)
        Returns the promoted piece type string (or None).
        """
        from_row, from_col = from_pos
        to_row, to_col = to_pos
        piece = self.board_grid[from_row][from_col]
        if piece is None:
            return None

        promotion_type = None

        # --- Clear en passant vulnerability from previous move ---
        if self.en_passant_target:
            ep_row, ep_col = self.en_passant_target
            target_pawn = self.board_grid[ep_row][ep_col]
            if target_pawn and isinstance(target_pawn, Pawn):
                target_pawn.en_passant_vulnerable = False
        self.en_passant_target = None

        # --- En passant capture ---
        if isinstance(piece, Pawn):
            if abs(from_col - to_col) == 1 and self.board_grid[to_row][to_col] is None:
                # Diagonal move to empty square → en passant
                captured_row = from_row
                captured_pawn = self.board_grid[captured_row][to_col]
                if captured_pawn:
                    self.piece_list.remove(captured_pawn)
                    self.board_grid[captured_row][to_col] = None

        # --- Capture ---
        captured = self.board_grid[to_row][to_col]
        if captured is not None:
            if captured in self.piece_list:
                self.piece_list.remove(captured)

        # --- Castling ---
        if isinstance(piece, King) and abs(from_col - to_col) == 2:
            if to_col == 6:   # Kingside
                rook = self.board_grid[from_row][7]
                self._move_on_grid(rook, (from_row, 7), (from_row, 5))
            elif to_col == 2:  # Queenside
                rook = self.board_grid[from_row][0]
                self._move_on_grid(rook, (from_row, 0), (from_row, 3))

        # --- Move the piece ---
        self._move_on_grid(piece, from_pos, to_pos)

        # --- Double pawn push: mark en passant ---
        if isinstance(piece, Pawn) and abs(from_row - to_row) == 2:
            piece.en_passant_vulnerable = True
            self.en_passant_target = (to_row, to_col)

        # --- Pawn promotion (file-based rule) ---
        if isinstance(piece, Pawn):
            promote_row = 0 if piece.color == 'white' else 7
            if to_row == promote_row:
                promotion_type = piece.promotion_piece()
                new_piece = self._create_piece(promotion_type, piece.color, to_pos)
                self.board_grid[to_row][to_col] = new_piece
                self.piece_list.remove(piece)
                self.piece_list.append(new_piece)

        piece.has_moved = True
        return promotion_type

    def _move_on_grid(self, piece, from_pos, to_pos):
        fr, fc = from_pos
        tr, tc = to_pos
        self.board_grid[fr][fc] = None
        self.board_grid[tr][tc] = piece
        piece.position = to_pos

    def _create_piece(self, piece_type, color, position):
        mapping = {
            'queen': Queen, 'rook': Rook,
            'bishop': Bishop, 'knight': Knight
        }
        return mapping[piece_type](color, position)

    # ------------------------------------------------------------------ #
    #  Legal move generation (with check filtering)                       #
    # ------------------------------------------------------------------ #

    def get_legal_moves(self, piece):
        """Returns moves that don't leave own king in check."""
        pseudo = piece.get_valid_moves(self.board_grid)
        # Add castling for king
        if isinstance(piece, King):
            pseudo += self._get_castling_moves(piece)
        legal = []
        for move in pseudo:
            if not self._move_leaves_king_in_check(piece, move):
                legal.append(move)
        return legal

    def _move_leaves_king_in_check(self, piece, to_pos):
        """Simulate move and check if own king is attacked."""
        sim = self._simulate_move(piece.position, to_pos)
        king = sim.get_king(piece.color)
        if king is None:
            return True
        return sim.is_square_attacked(king.position[0], king.position[1], piece.color)

    def _simulate_move(self, from_pos, to_pos):
        """Return a deep-copied board after applying the move."""
        sim = copy.deepcopy(self)
        sim.move_piece(from_pos, to_pos)
        return sim

    def is_square_attacked(self, row, col, by_color_excluded):
        """Returns True if (row,col) is attacked by any piece of the opposite color."""
        attacker_color = 'black' if by_color_excluded == 'white' else 'white'
        for piece in self.piece_list:
            if piece.color == attacker_color:
                moves = piece.get_valid_moves(self.board_grid)
                if (row, col) in moves:
                    return True
        return False

    def is_in_check(self, color):
        king = self.get_king(color)
        if king is None:
            return False
        return self.is_square_attacked(king.position[0], king.position[1], color)

    def has_any_legal_moves(self, color):
        for piece in self.piece_list:
            if piece.color == color:
                if self.get_legal_moves(piece):
                    return True
        return False

    # ------------------------------------------------------------------ #
    #  Castling                                                            #
    # ------------------------------------------------------------------ #

    def _get_castling_moves(self, king):
        moves = []
        if king.has_moved or self.is_in_check(king.color):
            return moves
        row = king.position[0]

        # Kingside
        rook = self.board_grid[row][7]
        if (rook and isinstance(rook, Rook) and not rook.has_moved
                and all(self.board_grid[row][c] is None for c in [5, 6])
                and not self.is_square_attacked(row, 5, king.color)
                and not self.is_square_attacked(row, 6, king.color)):
            moves.append((row, 6))

        # Queenside
        rook = self.board_grid[row][0]
        if (rook and isinstance(rook, Rook) and not rook.has_moved
                and all(self.board_grid[row][c] is None for c in [1, 2, 3])
                and not self.is_square_attacked(row, 3, king.color)
                and not self.is_square_attacked(row, 2, king.color)):
            moves.append((row, 2))

        return moves

    # ------------------------------------------------------------------ #
    #  FEN export (for Stockfish)                                          #
    # ------------------------------------------------------------------ #

    def to_fen(self, active_color='w', castling='-', en_passant='-',
               halfmove=0, fullmove=1):
        """Generate FEN string from current board state."""
        fen_rows = []
        piece_chars = {
            ('white', 'pawn'): 'P', ('white', 'rook'): 'R',
            ('white', 'knight'): 'N', ('white', 'bishop'): 'B',
            ('white', 'queen'): 'Q', ('white', 'king'): 'K',
            ('black', 'pawn'): 'p', ('black', 'rook'): 'r',
            ('black', 'knight'): 'n', ('black', 'bishop'): 'b',
            ('black', 'queen'): 'q', ('black', 'king'): 'k',
        }
        for row in range(8):
            empty = 0
            row_str = ''
            for col in range(8):
                piece = self.board_grid[row][col]
                if piece is None:
                    empty += 1
                else:
                    if empty:
                        row_str += str(empty)
                        empty = 0
                    row_str += piece_chars.get((piece.color, piece.piece_type), '?')
            if empty:
                row_str += str(empty)
            fen_rows.append(row_str)

        # Castling rights
        castling_str = ''
        wk = self.board_grid[7][4]
        wr_k = self.board_grid[7][7]
        wr_q = self.board_grid[7][0]
        bk = self.board_grid[0][4]
        br_k = self.board_grid[0][7]
        br_q = self.board_grid[0][0]
        if wk and isinstance(wk, King) and not wk.has_moved:
            if wr_k and isinstance(wr_k, Rook) and not wr_k.has_moved:
                castling_str += 'K'
            if wr_q and isinstance(wr_q, Rook) and not wr_q.has_moved:
                castling_str += 'Q'
        if bk and isinstance(bk, King) and not bk.has_moved:
            if br_k and isinstance(br_k, Rook) and not br_k.has_moved:
                castling_str += 'k'
            if br_q and isinstance(br_q, Rook) and not br_q.has_moved:
                castling_str += 'q'
        if not castling_str:
            castling_str = '-'

        # En passant
        ep_str = '-'
        if self.en_passant_target:
            er, ec = self.en_passant_target
            ep_row = er + (1 if active_color == 'w' else -1)
            files = 'abcdefgh'
            ep_str = files[ec] + str(8 - ep_row)

        return ' '.join([
            '/'.join(fen_rows),
            active_color,
            castling_str,
            ep_str,
            str(halfmove),
            str(fullmove)
        ])
