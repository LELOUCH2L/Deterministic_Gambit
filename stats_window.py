# stats_window.py — tkinter statistics dashboard (fully dark, no ttk.Notebook)

import tkinter as tk
import threading

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("[Stats] matplotlib not installed — charts unavailable.")
    print("[Stats] To enable charts run:  pip install matplotlib numpy")

from statistics_manager import StatisticsManager

# Suppress tkinter PhotoImage.__del__ RuntimeError from background thread GC
try:
    import tkinter as _tk_patch
    _orig_photodel = _tk_patch.PhotoImage.__del__
    def _safe_photoimagedel(self):
        try: _orig_photodel(self)
        except RuntimeError: pass
    _tk_patch.PhotoImage.__del__ = _safe_photoimagedel
except Exception:
    pass

# ── Colour palette ────────────────────────────────────────────────────────────
BG        = '#1e1e24'
PANEL     = '#16161c'
ACCENT    = '#d4af37'
GREEN     = '#6aa84f'
RED       = '#dc5050'
TEXT      = '#e6e6e6'
MUTED     = '#888888'
CHART_BG  = '#1a1a20'
GRID_C    = '#333340'
TAB_INACT = '#2a2a32'   # unselected tab background
TAB_ACT   = '#1e1e24'   # selected tab background (matches content area)
TAB_HOVER = '#34343e'


class StatsWindow:
    """
    Dark-themed statistics dashboard.
    Uses a hand-built tab bar (plain tk Buttons + Frames) instead of
    ttk.Notebook so Windows cannot override the colours.
    """

    TABS = [
        "Summary",
        "Move Distribution",
        "Moves vs Duration",
        "Game Results",
        "Promotion Types",
        "Eval Score",
    ]

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Deterministic Gambit — Statistics")
        self.root.geometry("1000x660")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.minsize(960, 640)

        self.move_data = StatisticsManager.load_move_data()
        self.game_data = StatisticsManager.load_game_data()

        self._tab_buttons = {}
        self._tab_frames  = {}
        self._active_tab  = None
        self._canvases    = []

        self._build_ui()
        self._switch_tab("Summary")

    # ------------------------------------------------------------------ #
    #  UI skeleton                                                         #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────────
        header = tk.Frame(self.root, bg=PANEL, pady=10)
        header.pack(fill='x')
        tk.Label(header, text="  Deterministic Gambit — Statistics",
                 font=('Consolas', 17, 'bold'), fg=ACCENT, bg=PANEL
                 ).pack(side='left', padx=16)
        count = f"{len(self.move_data)} move records  |  {len(self.game_data)} games"
        tk.Label(header, text=count, font=('Consolas', 11),
                 fg=MUTED, bg=PANEL).pack(side='right', padx=16)

        # ── Custom tab bar — centred ─────────────────────────────────────
        tab_bar_outer = tk.Frame(self.root, bg=PANEL, pady=4)
        tab_bar_outer.pack(fill='x')
        tab_bar = tk.Frame(tab_bar_outer, bg=PANEL)
        tab_bar.pack(anchor='center')  # centre the tab row

        tk.Frame(self.root, bg=ACCENT, height=1).pack(fill='x')

        for name in self.TABS:
            btn = tk.Button(
                tab_bar, text=f"  {name}  ",
                font=('Consolas', 12, 'bold'),
                fg=MUTED, bg=TAB_INACT,
                activeforeground=TEXT, activebackground=TAB_HOVER,
                relief='flat', bd=0, padx=10, pady=7, cursor='hand2',
                command=lambda n=name: self._switch_tab(n)
            )
            btn.pack(side='left', padx=2)
            btn.bind('<Enter>', lambda e, b=btn: b.configure(bg=TAB_HOVER) if b != self._active_btn() else None)
            btn.bind('<Leave>', lambda e, b=btn, n=name: b.configure(bg=TAB_ACT if n == self._active_tab else TAB_INACT))
            self._tab_buttons[name] = btn

        # ── Content area — one Frame per tab, stacked ───────────────────
        content = tk.Frame(self.root, bg=BG)
        content.pack(fill='both', expand=True)

        for name in self.TABS:
            frame = tk.Frame(content, bg=BG)
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._tab_frames[name] = frame

        # Build content lazily — only when tab is first shown
        self._tab_built = set()
        self._chart_map = {
            "Summary":          self._build_summary_tab,
            "Move Distribution": self._build_histogram_tab,
            "Moves vs Duration": self._build_scatter_tab,
            "Game Results":      self._build_pie_tab,
            "Promotion Types":   self._build_bar_tab,
            "Eval Score":        self._build_line_tab,
        }

    def _active_btn(self):
        return self._tab_buttons.get(self._active_tab)

    def _switch_tab(self, name):
        # Build chart on first visit (lazy loading)
        if name not in self._tab_built:
            self._tab_built.add(name)
            builder = self._chart_map.get(name)
            if builder:
                if name == "Summary" or HAS_MATPLOTLIB:
                    builder(self._tab_frames[name])
                else:
                    self._build_no_matplotlib(self._tab_frames[name])

        # Lower all frames, raise selected
        for n, frame in self._tab_frames.items():
            frame.lower()
        self._tab_frames[name].lift()

        # Update button styles
        for n, btn in self._tab_buttons.items():
            if n == name:
                btn.configure(fg=ACCENT, bg=TAB_ACT,
                               font=('Consolas', 11, 'bold'))
            else:
                btn.configure(fg=MUTED, bg=TAB_INACT,
                               font=('Consolas', 11))
        self._active_tab = name

    # ------------------------------------------------------------------ #
    #  No-matplotlib placeholder                                           #
    # ------------------------------------------------------------------ #

    def _build_no_matplotlib(self, parent):
        outer = tk.Frame(parent, bg=BG)
        outer.pack(expand=True, fill='both')
        tk.Label(outer, text='', bg=BG).pack(expand=True)
        tk.Label(outer, text='Charts require matplotlib',
                 font=('Consolas', 15, 'bold'), fg=ACCENT, bg=BG).pack()
        tk.Label(outer, text='Run this command in your terminal, then restart:',
                 font=('Consolas', 11), fg=MUTED, bg=BG).pack(pady=(12, 4))
        box = tk.Frame(outer, bg='#0d0d12', padx=24, pady=12)
        box.pack()
        tk.Label(box, text='pip install matplotlib numpy',
                 font=('Consolas', 13, 'bold'), fg=GREEN, bg='#0d0d12').pack()
        tk.Label(outer, text='', bg=BG).pack(expand=True)

    # ------------------------------------------------------------------ #
    #  Summary tab                                                         #
    # ------------------------------------------------------------------ #

    def _build_summary_tab(self, parent):
        tk.Label(parent, text="Summary Statistics",
                 font=('Consolas', 14, 'bold'), fg=ACCENT, bg=BG
                 ).pack(pady=(16, 6), anchor='center')

        if not self.game_data:
            tk.Label(parent, text="No data yet — play some games first!",
                     font=('Consolas', 12), fg=MUTED, bg=BG).pack(pady=40)
            return

        # Centre the table inside the tab
        outer = tk.Frame(parent, bg=BG)
        outer.pack(expand=True, fill='both')
        frame = tk.Frame(outer, bg=BG)
        frame.place(relx=0.5, rely=0.04, anchor='n')

        headers    = ['Metric', 'Total Moves / Game', 'Duration (sec)', 'Promotions / Game']
        col_widths = [16, 20, 18, 20]

        for i, h in enumerate(headers):
            tk.Label(frame, text=h, font=('Consolas', 11, 'bold'),
                     fg=ACCENT, bg=PANEL, width=col_widths[i],
                     anchor='center', padx=8, pady=6
                     ).grid(row=0, column=i, padx=1, pady=1, sticky='ew')

        import math as _m
        _full_moves = [{'total_moves_full': _m.ceil(float(g['total_moves'])/2)}
                       for g in self.game_data if g.get('total_moves')]
        import statistics as _st2
        _mv_vals = [d['total_moves_full'] for d in _full_moves]
        if _mv_vals:
            move_stats = {'mean': round(_st2.mean(_mv_vals),2),
                          'median': round(_st2.median(_mv_vals),2),
                          'max': max(_mv_vals), 'min': min(_mv_vals),
                          'sd': round(_st2.pstdev(_mv_vals),2),
                          'count': len(_mv_vals)}
        else:
            move_stats = {'mean':0,'median':0,'max':0,'min':0,'sd':0,'count':0}
        dur_stats   = StatisticsManager.compute_summary(self.game_data, 'game_duration_sec')
        promo_stats = StatisticsManager.compute_summary(self.game_data, 'promotion_count')

        for r, (metric, key) in enumerate(
                zip(['Mean','Median','Max','Min','Std Dev','Count'],
                    ['mean','median','max','min','sd','count']), start=1):
            row_bg = BG if r % 2 == 0 else PANEL
            tk.Label(frame, text=metric, font=('Consolas', 11, 'bold'),
                     fg=TEXT, bg=row_bg, width=col_widths[0],
                     anchor='center', padx=8, pady=5
                     ).grid(row=r, column=0, padx=1, pady=1, sticky='ew')
            for ci, stats in enumerate([move_stats, dur_stats, promo_stats], start=1):
                tk.Label(frame, text=str(stats.get(key, 0)),
                         font=('Consolas', 11), fg=TEXT, bg=row_bg,
                         width=col_widths[ci], anchor='center', padx=8, pady=5
                         ).grid(row=r, column=ci, padx=1, pady=1, sticky='ew')

        # Results breakdown below table
        res_frame = tk.Frame(outer, bg=BG)
        res_frame.place(relx=0.5, rely=0.60, anchor='n')
        tk.Label(res_frame, text="Game Results Breakdown",
                 font=('Consolas', 13, 'bold'), fg=ACCENT, bg=BG
                 ).pack(pady=(0, 8))
        results = {}
        for g in self.game_data:
            r = g.get('result', 'Unknown')
            results[r] = results.get(r, 0) + 1
        total = sum(results.values())
        pills = tk.Frame(res_frame, bg=BG)
        pills.pack()
        for res, cnt in results.items():
            pct   = round(100 * cnt / total, 1)
            color = GREEN if 'Player' in res else (RED if 'AI' in res else ACCENT)
            tk.Label(pills,
                     text=f"  {res}: {cnt}  ({pct}%)  ",
                     font=('Consolas', 12), fg=color, bg=PANEL,
                     padx=12, pady=6
                     ).pack(side='left', padx=6, pady=4)

    def _on_close(self):
        for c in self._canvases:
            try: c.get_tk_widget().destroy()
            except Exception: pass
        self._canvases.clear()
        try: self.root.destroy()
        except Exception: pass

    def _make_fig_canvas(self, parent):
        fig    = Figure(figsize=(9, 5), facecolor=CHART_BG)
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.get_tk_widget().pack(fill='both', expand=True, padx=4, pady=4)
        self._canvases.append(canvas)
        return fig, canvas

    def _style_ax(self, ax, title, xlabel, ylabel):
        ax.set_facecolor(CHART_BG)
        ax.set_title(title, color=ACCENT, fontsize=13, fontweight='bold', pad=12)
        ax.set_xlabel(xlabel, color=MUTED, fontsize=10)
        ax.set_ylabel(ylabel, color=MUTED, fontsize=10)
        ax.tick_params(colors=TEXT)
        for spine in ['bottom', 'left']:
            ax.spines[spine].set_color(GRID_C)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.yaxis.grid(True, color=GRID_C, linewidth=0.5, alpha=0.6)
        ax.set_axisbelow(True)

    def _no_data(self, parent):
        tk.Label(parent,
                 text="Not enough data yet.\nPlay more games to populate this chart.",
                 font=('Consolas', 12), fg=MUTED, bg=BG, justify='center'
                 ).pack(expand=True)

    def _tab_header(self, parent, title, subtitle):
        tk.Label(parent, text=title, font=('Consolas', 13, 'bold'),
                 fg=ACCENT, bg=BG).pack(pady=(12, 2))
        tk.Label(parent, text=subtitle, font=('Consolas', 10),
                 fg=MUTED, bg=BG).pack(pady=(0, 6))

    # ------------------------------------------------------------------ #
    #  Graph 1: Histogram                                                  #
    # ------------------------------------------------------------------ #

    def _build_histogram_tab(self, parent):
        self._tab_header(parent,
            "Graph 1 – Total Moves Distribution",
            "How many moves do games typically last?")
        import math as _math, statistics as st
        raw = [int(float(g['total_moves'])) for g in self.game_data if g.get('total_moves')]
        values = [_math.ceil(v / 2) for v in raw]   # convert plies to full moves
        if not values:
            self._no_data(parent); return
        fig, canvas = self._make_fig_canvas(parent)
        ax = fig.add_subplot(111)
        self._style_ax(ax, 'Distribution of Game Lengths', 'Moves per Game', 'Frequency')
        lo = min(values); hi = max(values)
        bins = [x - 0.5 for x in range(lo, hi + 2)]  # 1 bar per integer, width=1
        ax.hist(values, bins=bins, color=ACCENT, edgecolor=CHART_BG, alpha=0.85)
        ax.xaxis.set_major_locator(__import__('matplotlib').ticker.MaxNLocator(integer=True))
        if len(values) >= 2:
            mean_v = st.mean(values)
            ax.axvline(mean_v, color=GREEN, linestyle='--', linewidth=1.5, label=f'Mean: {mean_v:.1f}')
            ax.legend(facecolor=PANEL, edgecolor=GRID_C, labelcolor=TEXT, fontsize=9)
        canvas.draw()

    # ------------------------------------------------------------------ #
    #  Graph 2: Scatter                                                    #
    # ------------------------------------------------------------------ #

    def _build_scatter_tab(self, parent):
        self._tab_header(parent,
            "Graph 2 – Moves vs Duration",
            "Do longer games (by moves) also take more time?")
        import math as _m2; moves = [_m2.ceil(float(g['total_moves'])/2) for g in self.game_data if g.get('total_moves')]
        durs  = [float(g['game_duration_sec']) for g in self.game_data if g.get('game_duration_sec')]
        pairs = list(zip(moves, durs))
        if len(pairs) < 2:
            self._no_data(parent); return
        xs, ys = zip(*pairs)
        fig, canvas = self._make_fig_canvas(parent)
        ax = fig.add_subplot(111)
        self._style_ax(ax, 'Moves vs Duration', 'Total Moves', 'Duration (seconds)')
        ax.scatter(xs, ys, color=ACCENT, alpha=0.75, edgecolors=BG, s=60)
        try:
            import numpy as np
            if len(xs) >= 3:
                z = np.polyfit(xs, ys, 1)
                p = np.poly1d(z)
                xl = sorted(xs)
                ax.plot(xl, [p(v) for v in xl], color=GREEN,
                        linestyle='--', linewidth=1.5, label='Trend')
                ax.legend(facecolor=PANEL, edgecolor=GRID_C, labelcolor=TEXT, fontsize=9)
        except ImportError:
            pass
        canvas.draw()

    # ------------------------------------------------------------------ #
    #  Graph 3: Pie                                                        #
    # ------------------------------------------------------------------ #

    def _build_pie_tab(self, parent):
        self._tab_header(parent,
            "Graph 3 – Game Results",
            "Win / Loss / Draw distribution")
        results = {}
        for g in self.game_data:
            r = g.get('result', 'Unknown')
            results[r] = results.get(r, 0) + 1
        if not results:
            self._no_data(parent); return
        labels = list(results.keys())
        sizes  = list(results.values())
        colors = [GREEN if 'Player' in l else (RED if 'AI' in l else ACCENT) for l in labels]
        fig, canvas = self._make_fig_canvas(parent)
        ax = fig.add_subplot(111)
        ax.set_facecolor(CHART_BG)
        total_games = sum(sizes)
        legend_labels = [f"{lbl}: {cnt} ({round(100*cnt/total_games,1)}%)"
                         for lbl,cnt in zip(labels,sizes)]
        wedges, _ = ax.pie(
            sizes, colors=colors, startangle=90,
            wedgeprops={'edgecolor': 'none', 'linewidth': 0}
        )
        ax.legend(wedges, legend_labels,
                  loc='center left', bbox_to_anchor=(1.05,0.5),
                  facecolor=PANEL, edgecolor=GRID_C, labelcolor=TEXT, fontsize=10)
        ax.set_title('Game Result Distribution', color=ACCENT, fontsize=13, fontweight='bold')
        canvas.draw()

    # ------------------------------------------------------------------ #
    #  Graph 4: Bar                                                        #
    # ------------------------------------------------------------------ #

    def _build_bar_tab(self, parent):
        self._tab_header(parent,
            "Graph 4 – Promotion Types",
            "Which pieces do pawns promote to most often?")
        promo_counts = {}
        for row in self.move_data:
            if row.get('is_promotion') in ('True', True) and row.get('promotion_piece'):
                p = row['promotion_piece'].strip().lower()
                if p:
                    promo_counts[p] = promo_counts.get(p, 0) + 1
        order   = ['queen', 'rook', 'bishop', 'knight']
        labels  = [p.capitalize() for p in order]
        values  = [promo_counts.get(p, 0) for p in order]
        bcolors = [ACCENT, '#5b8dd9', GREEN, RED]
        fig, canvas = self._make_fig_canvas(parent)
        ax = fig.add_subplot(111)
        self._style_ax(ax, 'Promotion Piece Frequency', 'Piece', 'Count')
        bars = ax.bar(labels, values, color=bcolors, edgecolor=CHART_BG, width=0.55)
        ymax = max(max(values) + 1, 3)
        ax.set_ylim(0, ymax)
        ax.yaxis.set_major_locator(__import__('matplotlib').ticker.MaxNLocator(integer=True))
        for bar, val in zip(bars, values):
            lbl_y = min(bar.get_height() + 0.05, ymax * 0.92)
            ax.text(bar.get_x() + bar.get_width() / 2, lbl_y, str(val),
                    ha='center', va='bottom', color=TEXT, fontsize=10)
        canvas.draw()

    # ------------------------------------------------------------------ #
    #  Graph 5: Line                                                       #
    # ------------------------------------------------------------------ #

    def _build_line_tab(self, parent):
        self._tab_header(parent,
            "Graph 5 – Evaluation Score Over Time",
            "Advantage per chess turn — last completed game (clamped ±15.0)")
        if not self.move_data:
            self._no_data(parent); return

        # Use the most recent completed game (by game_data order)
        if not self.game_data:
            self._no_data(parent); return
        latest_id = self.game_data[-1]['game_id']

        # Determine player color for this game from game_data
        player_color = 'white'
        for g in reversed(self.game_data):
            if g.get('game_id') == latest_id:
                player_color = g.get('player_color', 'white')
                break
        ai_color = 'black' if player_color == 'white' else 'white'

        # Build turns: one point per full move (0,1,2,...n) using white move evals,
        # plus a final point at n from the (end) record so the line reaches the last move.
        white_moves = [r for r in self.move_data
                       if r['game_id'] == latest_id
                       and r.get('player') == 'white'
                       and r.get('piece_moved') != '(end)']
        end_record  = next((r for r in reversed(self.move_data)
                            if r['game_id'] == latest_id
                            and r.get('piece_moved') == '(end)'), None)
        turns  = []
        scores = []
        for idx, r in enumerate(white_moves):
            try:
                score = float(r['eval_score'])
                turns.append(idx)
                scores.append(max(-15.0, min(15.0, score)))
            except (ValueError, KeyError):
                pass
        # Append final eval at turn n so line reaches the last move
        if end_record and turns:
            try:
                final_score = float(end_record['eval_score'])
                # end record player may be black; flip sign to white-positive
                if end_record.get('player') == 'black':
                    final_score = -final_score
                turns.append(len(turns))
                scores.append(max(-15.0, min(15.0, final_score)))
            except (ValueError, KeyError):
                pass

        if not turns:
            self._no_data(parent); return

        # Labels: show who is white, who is black
        white_lbl = f"White = {'Player' if player_color=='white' else 'AI'}"
        black_lbl = f"Black = {'Player' if player_color=='black' else 'AI'}"

        fig, canvas = self._make_fig_canvas(parent)
        ax = fig.add_subplot(111)
        self._style_ax(ax, f"Eval Score — Last Completed Game  ({white_lbl}, {black_lbl})",
                       'Chess Turn', 'Eval Score (clamped ±15.0)')
        ax.set_ylim(-16.0, 16.0)
        _xmax = max(turns)
        ax.set_xlim(-0.5, _xmax + 0.5)
        import matplotlib.ticker as _mticker
        ax.xaxis.set_major_locator(_mticker.FixedLocator(range(0, _xmax + 1)))

        ax.plot(turns, scores, color=ACCENT, linewidth=2.0, alpha=0.95)
        ax.axhline(0, color=MUTED, linewidth=0.9)
        ax.axhline( 5.0, color=MUTED, linewidth=0.4, linestyle=':', alpha=0.4)
        ax.axhline(-5.0, color=MUTED, linewidth=0.4, linestyle=':', alpha=0.4)
        _tx = max(turns)*0.02 if max(turns) > 0 else 0.05
        ax.text(_tx,  14.5, f"+ = White advantage ({white_lbl})",
                ha='left', va='top', color=MUTED, fontsize=8)
        ax.text(_tx, -14.5, f"- = Black advantage ({black_lbl})",
                ha='left', va='bottom', color=MUTED, fontsize=8)
        canvas.draw()

    def run(self):
        self.root.mainloop()

    @staticmethod
    def launch_standalone():
        win = StatsWindow()
        win.root.protocol("WM_DELETE_WINDOW", win._on_close)
        win.root.mainloop()


if __name__ == '__main__':
    StatsWindow.launch_standalone()


def open_stats(master=None):
    def _launch():
        win = StatsWindow(master)
        if master is None:
            win.run()
        else:
            win.root.grab_set()
    threading.Thread(target=_launch, daemon=True).start()
