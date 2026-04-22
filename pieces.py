# pieces.py — All chess piece classes

class Piece:
    """Base class for all chess pieces."""

    # Maps starting file (0–7 = a–h) to promotion piece for WHITE pawns
    FILE_PROMOTION_MAP = {
        0: 'rook',    # a-file → Rook
        1: 'knight',  # b-file → Knight
        2: 'bishop',  # c-file → Bishop
        3: 'queen',   # d-file → Queen
        4: 'queen',   # e-file → Queen
        5: 'bishop',  # f-file → Bishop
        6: 'knight',  # g-file → Knight
        7: 'rook',    # h-file → Rook
    }

    def __init__(self, color, position):
        self.color = color          # 'white' or 'black'
        self.position = position    # (row, col) tuple
        self.piece_type = 'piece'
        self.has_moved = False

    def get_valid_moves(self, board_grid):
        """Override in subclasses. Returns list of (row, col) tuples."""
        return []

    def _in_bounds(self, row, col):
        return 0 <= row < 8 and 0 <= col < 8

    def _is_enemy(self, board_grid, row, col):
        piece = board_grid[row][col]
        return piece is not None and piece.color != self.color

    def _is_empty(self, board_grid, row, col):
        return board_grid[row][col] is None

    def __repr__(self):
        return f"{self.color[0].upper()}{self.piece_type[0].upper()}"


class Pawn(Piece):
    def __init__(self, color, position):
        super().__init__(color, position)
        self.piece_type = 'pawn'
        self.start_file = position[1]   # Column where pawn started (0–7)
        self.en_passant_vulnerable = False  # Set to True right after double push

    def promotion_piece(self):
        """Returns the piece type this pawn promotes to, based on starting file."""
        return self.FILE_PROMOTION_MAP[self.start_file]

    def get_valid_moves(self, board_grid):
        moves = []
        row, col = self.position
        direction = -1 if self.color == 'white' else 1
        start_row = 6 if self.color == 'white' else 1

        # Single step forward
        new_row = row + direction
        if self._in_bounds(new_row, col) and self._is_empty(board_grid, new_row, col):
            moves.append((new_row, col))
            # Double step from starting row
            if row == start_row:
                double_row = row + 2 * direction
                if self._is_empty(board_grid, double_row, col):
                    moves.append((double_row, col))

        # Diagonal captures
        for dc in [-1, 1]:
            new_col = col + dc
            if self._in_bounds(new_row, new_col):
                if self._is_enemy(board_grid, new_row, new_col):
                    moves.append((new_row, new_col))
                # En passant
                elif self._in_bounds(row, new_col):
                    target = board_grid[row][new_col]
                    if (target is not None and isinstance(target, Pawn)
                            and target.color != self.color
                            and target.en_passant_vulnerable):
                        moves.append((new_row, new_col))
        return moves


class Rook(Piece):
    def __init__(self, color, position):
        super().__init__(color, position)
        self.piece_type = 'rook'

    def get_valid_moves(self, board_grid):
        moves = []
        row, col = self.position
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            r, c = row + dr, col + dc
            while self._in_bounds(r, c):
                if self._is_empty(board_grid, r, c):
                    moves.append((r, c))
                elif self._is_enemy(board_grid, r, c):
                    moves.append((r, c))
                    break
                else:
                    break
                r += dr
                c += dc
        return moves


class Knight(Piece):
    def __init__(self, color, position):
        super().__init__(color, position)
        self.piece_type = 'knight'

    def get_valid_moves(self, board_grid):
        moves = []
        row, col = self.position
        for dr, dc in [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]:
            r, c = row + dr, col + dc
            if self._in_bounds(r, c) and not (
                board_grid[r][c] is not None and board_grid[r][c].color == self.color
            ):
                moves.append((r, c))
        return moves


class Bishop(Piece):
    def __init__(self, color, position):
        super().__init__(color, position)
        self.piece_type = 'bishop'

    def get_valid_moves(self, board_grid):
        moves = []
        row, col = self.position
        for dr, dc in [(-1,-1),(-1,1),(1,-1),(1,1)]:
            r, c = row + dr, col + dc
            while self._in_bounds(r, c):
                if self._is_empty(board_grid, r, c):
                    moves.append((r, c))
                elif self._is_enemy(board_grid, r, c):
                    moves.append((r, c))
                    break
                else:
                    break
                r += dr
                c += dc
        return moves


class Queen(Piece):
    def __init__(self, color, position):
        super().__init__(color, position)
        self.piece_type = 'queen'

    def get_valid_moves(self, board_grid):
        moves = []
        row, col = self.position
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
            r, c = row + dr, col + dc
            while self._in_bounds(r, c):
                if self._is_empty(board_grid, r, c):
                    moves.append((r, c))
                elif self._is_enemy(board_grid, r, c):
                    moves.append((r, c))
                    break
                else:
                    break
                r += dr
                c += dc
        return moves


class King(Piece):
    def __init__(self, color, position):
        super().__init__(color, position)
        self.piece_type = 'king'

    def get_valid_moves(self, board_grid):
        moves = []
        row, col = self.position
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                r, c = row + dr, col + dc
                if self._in_bounds(r, c) and not (
                    board_grid[r][c] is not None and board_grid[r][c].color == self.color
                ):
                    moves.append((r, c))
        return moves
