# Deterministic Gambit

## Project Description
- Project by: Kantinan Lertluckpreecha
- Game Genre: Strategy, Chess Variant

Deterministic Gambit is a single-player chess variant built with Python and Pygame. It introduces a unique twist on standard chess: **pawn promotion is determined by the file (column) the pawn started on**, not by the player's choice. This forces players to think carefully about pawn structure from the very first move. The game features a full AI opponent powered by Stockfish, move history browsing with animation, pre-move support, a time control system, game saving/loading, and an in-depth statistics dashboard.

---

## Installation

**Requirements:**
- Python 3.13.x (Python 3.14+ is not supported — Pygame is not compatible)
- Stockfish chess engine (see note below)

To clone this project:
```sh
git clone https://github.com/LELOUCH2L/Deterministic_Gambit.git
```

To create and run a Python environment for this project:

**Windows:**
```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**Mac:**
```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> **Stockfish** (chess engine) must also be placed in the project folder. Download from https://stockfishchess.org/download/ and place the binary (e.g. `stockfish.exe` on Windows, `stockfish` on Mac/Linux) directly in the project root. The game will detect it automatically.

---

## Running Guide

After activating the Python environment, run the game with:

**Windows:**
```bat
python main.py
```

**Mac:**
```sh
python3 main.py
```

---

## Tutorial / Usage

**Starting a game:**
1. Launch the game — the lobby appears.
2. Select a difficulty level (Beginner → Master), a time control, and your colour (White or Black).
3. Click **PLAY**.

**Moving pieces:**
- Click a piece to select it (green dots show legal moves), then click a destination — or drag and drop.
- Right-click anywhere to cancel a selection.

**Pre-move (while AI is thinking):**
- Click or drag one of your pieces to queue a move in advance.
- Red squares indicate the queued pre-move. Right-click to cancel it.
- The pre-move executes automatically when the AI finishes, if still legal.

**Browsing move history:**
- Use ← / → arrow keys or click any row in the move log to step through the game.
- Scroll the log panel with the mouse wheel.
- Click the **(start)** row to return to the opening position.

**Returning to menu / Saving:**
- Press **Esc** during a game to open the Return to Menu dialog.
- Choosing **Return (Y)** saves the game; you can continue it from the lobby later.
- Choosing **Resign (R)** ends the game immediately without saving.

**Statistics:**
- Click the **Statistics** button in the game panel or lobby to open the stats dashboard (opens as a separate window).

---

## Game Features

- **File-based pawn promotion** — promotion piece is fixed by the pawn's starting file:
  - Files a / h → Rook
  - Files b / g → Knight
  - Files c / f → Bishop
  - Files d / e → Queen
- **Stockfish AI** with six difficulty levels (Beginner ~400 ELO to Master ~3200 ELO)
- **Full chess rules** — castling, en passant, 50-move draw, insufficient material draw, stalemate, checkmate
- **Time controls** — Bullet (1 min), Blitz (3/5 min), Rapid (10/30 min), or no limit; clock runs per side
- **10-second warning** sound when time is nearly out
- **Pre-move system** — queue one move while the AI is thinking, with red highlight and cancellation support
- **Move history browser** — animated forward and backward replay with sound effects per move type
- **Game save / load** — saves mid-game state (board, clocks, history) to disk; resumes from the lobby
- **Sound effects** — distinct sounds for moves, captures, checks, castling, promotions, game end, pre-moves, illegal moves, and time warnings
- **Statistics dashboard** with five graphs:
  1. Game length distribution (full moves)
  2. Moves vs game duration scatter plot
  3. Game results pie chart
  4. Promotion piece frequency bar chart
  5. Evaluation score over time (last completed game)

---

## External Sources

Acknowledge to:

1. Stockfish chess engine, https://stockfishchess.org/ [AI engine]
2. Pygame library, https://www.pygame.org/ [game framework]
3. Matplotlib, https://matplotlib.org/ [statistics charts]
4. Chess piece SVG assets — adapted from Lichess open-source assets, https://github.com/lichess-org/lila [Chess piece SVG assets]
5. Sound effects — adapted from Lichess open-source assets, https://github.com/lichess-org/lila [sound effects]
