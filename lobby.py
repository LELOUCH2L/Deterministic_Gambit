# lobby.py — Deterministic Gambit lobby

import pygame, os, threading

BG      = ( 18,  18,  24); PANEL  = ( 26,  26,  34)
ACCENT  = (212, 175,  55); GREEN  = (106, 168,  79)
RED     = (210,  70,  70); TEXT   = (235, 235, 235)
MUTED   = (185, 185, 200); BRIGHT = (225, 225, 238)
BORDER  = ( 55,  55,  70); HOVER  = ( 42,  42,  55)
SEL_BG  = ( 45,  58,  35); SEL_B  = (106, 168,  79)
DIM     = (115, 115, 130)
RED_BG  = ( 38,  18,  18)   # locked-continue background tint
RED_BOR = (180,  50,  50)   # locked-continue border

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),'assets')
SAVE_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)),'data','saved_game.pkl')

LEVELS = [
    (1,  "Beginner","Random moves",         "~400"),
    (3,  "Easy",    "Basic tactics",         "~800"),
    (7,  "Medium",  "Thinks ahead",          "~1200"),
    (12, "Hard",    "Strong positional play","~1800"),
    (17, "Expert",  "Very difficult",        "~2400"),
    (20, "Master",  "Real Stockfish",        "~3200"),
]
TIME_OPTIONS = [
    (60,  "1 min","Bullet"),(180,"3 min","Blitz"),
    (300, "5 min","Blitz"),(600,"10 min","Rapid"),
    (1800,"30 min","Rapid"),(None,"No limit",""),
]
PAGES = ["Play","Rules","Controls"]

RULES_TEXT = [
    ("Deterministic Gambit — Rules", True),("", False),
    ("File-Based Pawn Promotion", True),
    ("  When a pawn reaches the last rank, the piece", False),
    ("  it promotes to is fixed by the FILE (column)", False),
    ("  where the pawn started — not the player's", False),
    ("  choice.", False),("", False),
    ("Promotion Map:", True),
    ("  File a / h  →  Rook", False),
    ("  File b / g  →  Knight", False),
    ("  File c / f  →  Bishop", False),
    ("  File d / e  →  Queen", False),("", False),
    ("All standard chess rules also apply:", True),
    ("  Checkmate, stalemate, 50-move draw,", False),
    ("  en passant, and castling are all included.", False),("", False),
    ("Strategy Tip:", True),
    ("  Pawn structure matters far more here than in", False),
    ("  standard chess — since promotions are fixed,", False),
    ("  every pawn's starting file has real value!", False),
]

CONTROLS_TEXT = [
    ("Moving Pieces", True),
    ("  Click a piece to select it (green dots appear)", False),
    ("  Click a green dot to move there", False),
    ("  Drag and drop also works", False),
    ("  Right-click  Cancel selection or drag", False),("", False),
    ("Pre-Move  (queue a move while AI is thinking)", True),
    ("  Click a piece, then click destination", False),
    ("  Or drag and drop while AI is thinking", False),
    ("  Red squares = pre-move queued", False),
    ("  Pre-move executes automatically when AI moves", False),
    ("  Right-click = cancel the queued pre-move", False),
    ("  Only 1 pre-move allowed per turn", False),("", False),
    ("Move History", True),
    ("  ← / →          Browse history (hold to repeat)", False),
    ("  Click a row    Jump to that move in history", False),
    ("  (start) row    Jump to opening position", False),
    ("  Scroll wheel   Scroll the move log", False),("", False),
    ("Escape Menu", True),
    ("  Press Escape during a game to open menu", False),
    ("  Stay           N or Esc  (keep playing)", False),
    ("  Return         Y         (save and go to lobby)", False),
    ("  Resign         R         (forfeit, no save)", False),("", False),
    ("Panel Buttons", True),
    ("  Statistics     Open data analysis dashboard", False),
    ("  Resign         Forfeit current game", False),
    ("  New Game       Only shown when game has ended", False),
    ("                 While live: asks to resign first", False),("", False),
    ("Lobby", True),
    ("  Continue       Shown when a saved game exists", False),
    ("  New Game       Link below Continue to discard save", False),
    ("  Escape         Opens quit dialog", False),
]

# Pre-compute scroll max for text pages
def _text_height(lines):
    h = 0
    for _,is_head in lines: h += 26 if is_head else 21
    return h


class Lobby:
    def __init__(self, screen, clock, sound=None):
        self.screen = screen; self.clock = clock; self.sound = sound
        self.W, self.H = screen.get_size()
        self._init_fonts(); self._load_bg()
        self.page     = "Play"; self.sel_level=2; self.sel_color='white'
        self.sel_time = 5; self.hover=None; self.scroll_y=0
        self.btn_rects={}; self._show_quit=False; self._quit_rects={}
        self._scroll_max = {}  # page → max scroll_y

    def _init_fonts(self):
        self.f_title  = pygame.font.SysFont('consolas',36,bold=True)
        self.f_sub    = pygame.font.SysFont('consolas',15)
        self.f_nav    = pygame.font.SysFont('consolas',14,bold=True)
        self.f_head   = pygame.font.SysFont('consolas',15,bold=True)
        self.f_btn    = pygame.font.SysFont('consolas',14,bold=True)
        self.f_body   = pygame.font.SysFont('consolas',14)
        self.f_label  = pygame.font.SysFont('consolas',13)
        self.f_elo    = pygame.font.SysFont('consolas',12)
        self.f_dialog = pygame.font.SysFont('consolas',15,bold=True)
        self.f_hint   = pygame.font.SysFont('consolas',12)

    def _load_bg(self):
        self.bg_img = None  # plain background, no image

    def _compute_scroll_max(self, page):
        lines_map = {"Rules":RULES_TEXT,"Controls":CONTROLS_TEXT}
        if page not in lines_map: return 0
        content_h = _text_height(lines_map[page])
        visible_h = self.H - 134   # below nav bar
        return max(0, content_h - visible_h + 20)

    # ── Main loop ─────────────────────────────────────────────────────────
    def run(self):
        print("[Lobby] Opened.")
        # Pre-compute scroll limits
        for p in ["Rules","Controls"]:
            self._scroll_max[p] = self._compute_scroll_max(p)

        while True:
            self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._show_quit = True
                elif event.type == pygame.MOUSEMOTION:
                    self.hover = None if self._show_quit else self._hit(event.pos)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    r = self._click(event.pos)
                    if r is not None:
                        print(f"[Lobby] Game starting: skill={r['skill']} "
                              f"color={r['player_color']} time={r['time_limit']}")
                        return r
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self._show_quit: self._show_quit=False
                        else: self._show_quit=True
                    elif event.key == pygame.K_n and self._show_quit:
                        self._show_quit=False
                    elif event.key == pygame.K_y and self._show_quit:
                        import sys; pygame.quit(); sys.exit()
                    elif event.key == pygame.K_UP:
                        self.scroll_y=max(0,self.scroll_y-22)
                    elif event.key == pygame.K_DOWN:
                        self._scroll_down()
                elif event.type == pygame.MOUSEWHEEL:
                    if event.y > 0:
                        self.scroll_y=max(0,self.scroll_y-22)
                    else:
                        self._scroll_down()
            self._draw()

    def _scroll_down(self):
        limit = self._scroll_max.get(self.page, 9999)
        self.scroll_y = min(limit, self.scroll_y+22)

    # ── Drawing ───────────────────────────────────────────────────────────
    def _draw(self):
        self.screen.fill(BG); self.btn_rects={}
        if self.bg_img:
            self.screen.blit(self.bg_img,(0,0))

        t=self.f_title.render("Deterministic Gambit",True,ACCENT)
        self.screen.blit(t,(self.W//2-t.get_width()//2,20))
        sub=self.f_sub.render("A Chess Variant with File-Based Pawn Promotion",True,BRIGHT)
        self.screen.blit(sub,(self.W//2-sub.get_width()//2,66))

        self._draw_nav(92)
        if   self.page=="Play":     self._draw_play()
        elif self.page=="Rules":    self._draw_text(RULES_TEXT)
        elif self.page=="Controls": self._draw_text(CONTROLS_TEXT)
        if self._show_quit: self._draw_quit_dialog()
        pygame.display.flip()

    def _draw_nav(self,y):
        total_w=len(PAGES)*116+(len(PAGES)-1)*8; sx=self.W//2-total_w//2
        for page in PAGES:
            r=pygame.Rect(sx,y,116,30); active=self.page==page
            hov=self.hover==f'nav_{page}'
            bg  =PANEL if active else (HOVER if hov else BG)
            bor =ACCENT if active else (BRIGHT if hov else BORDER)
            fg  =ACCENT if active else (BRIGHT if hov else MUTED)
            pygame.draw.rect(self.screen,bg,r,border_radius=6)
            pygame.draw.rect(self.screen,bor,r,1,border_radius=6)
            s=self.f_nav.render(page,True,fg)
            self.screen.blit(s,(r.centerx-s.get_width()//2,r.centery-s.get_height()//2))
            self.btn_rects[f'nav_{page}']=r; sx+=124

    def _draw_play(self):
        has_save = os.path.exists(SAVE_FILE)
        cx=self.W//2; y=136

        if has_save:
            # ── Locked / Continue mode ────────────────────────────────
            self._draw_continue_locked(cx, y, has_save)
            return

        # ── Normal play mode ─────────────────────────────────────────

        # Difficulty
        lbl=self.f_head.render("Select Difficulty",True,BRIGHT)
        self.screen.blit(lbl,(cx-lbl.get_width()//2,y)); y+=28
        bw,bh,gap=170,54,9; cols=3
        total_w=cols*bw+(cols-1)*gap; sx=cx-total_w//2
        for idx,(skill,name,desc,elo) in enumerate(LEVELS):
            col_i=idx%cols; row_i=idx//cols
            x=sx+col_i*(bw+gap); by=y+row_i*(bh+gap)
            r=pygame.Rect(x,by,bw,bh); sel=self.sel_level==idx
            hov=self.hover==f'level_{idx}'
            bg=SEL_BG if sel else (HOVER if hov else PANEL)
            bor=SEL_B if sel else (ACCENT if hov else BORDER)
            pygame.draw.rect(self.screen,bg,r,border_radius=8)
            pygame.draw.rect(self.screen,bor,r,1+sel,border_radius=8)
            ns=self.f_btn.render(name,True,ACCENT if sel else TEXT)
            ds=self.f_label.render(desc,True,MUTED)
            es=self.f_elo.render(f"ELO {elo}",True,DIM)
            self.screen.blit(ns,(r.centerx-ns.get_width()//2,by+7))
            self.screen.blit(ds,(r.centerx-ds.get_width()//2,by+26))
            self.screen.blit(es,(r.centerx-es.get_width()//2,by+41))
            self.btn_rects[f'level_{idx}']=r
        y+=2*(bh+gap)+14

        # Time
        lbl=self.f_head.render("Time Control",True,BRIGHT)
        self.screen.blit(lbl,(cx-lbl.get_width()//2,y)); y+=28
        tw=90; tgap=8; tot=len(TIME_OPTIONS)*tw+(len(TIME_OPTIONS)-1)*tgap; tsx=cx-tot//2
        for ti,(secs,label,cat) in enumerate(TIME_OPTIONS):
            r=pygame.Rect(tsx+ti*(tw+tgap),y,tw,44); sel=self.sel_time==ti
            hov=self.hover==f'time_{ti}'
            bg=SEL_BG if sel else (HOVER if hov else PANEL)
            bor=SEL_B if sel else (ACCENT if hov else BORDER)
            pygame.draw.rect(self.screen,bg,r,border_radius=6)
            pygame.draw.rect(self.screen,bor,r,1+sel,border_radius=6)
            ls=self.f_btn.render(label,True,ACCENT if sel else TEXT)
            cs=self.f_elo.render(cat,True,DIM)
            self.screen.blit(ls,(r.centerx-ls.get_width()//2,r.y+7))
            self.screen.blit(cs,(r.centerx-cs.get_width()//2,r.y+28))
            self.btn_rects[f'time_{ti}']=r
        y+=58

        # Play As
        lbl=self.f_head.render("Play As",True,BRIGHT)
        self.screen.blit(lbl,(cx-lbl.get_width()//2,y)); y+=28
        for color,label in [('white','White'),('black','Black')]:
            ox=cx-182+(0 if color=='white' else 194)
            r=pygame.Rect(ox,y,178,46); sel=self.sel_color==color
            hov=self.hover==f'color_{color}'
            bg=SEL_BG if sel else (HOVER if hov else PANEL)
            bor=SEL_B if sel else (ACCENT if hov else BORDER)
            pygame.draw.rect(self.screen,bg,r,border_radius=8)
            pygame.draw.rect(self.screen,bor,r,1+sel,border_radius=8)
            cc=(230,230,230) if color=='white' else (25,25,25)
            pygame.draw.circle(self.screen,cc,(r.x+28,r.centery),17)
            pygame.draw.circle(self.screen,BORDER,(r.x+28,r.centery),17,1)
            ns=self.f_btn.render(label,True,ACCENT if sel else TEXT)
            self.screen.blit(ns,(r.x+54,r.centery-ns.get_height()//2))
            self.btn_rects[f'color_{color}']=r
        y+=60

        # PLAY button (green)
        pr=pygame.Rect(cx-105,y,210,48); hov=self.hover=='play'
        bg=(55,82,44) if hov else (38,62,30)
        pygame.draw.rect(self.screen,bg,pr,border_radius=10)
        pygame.draw.rect(self.screen,GREEN,pr,2,border_radius=10)
        ps=self.f_btn.render("PLAY",True,GREEN)
        self.screen.blit(ps,(pr.centerx-ps.get_width()//2,pr.centery-ps.get_height()//2))
        self.btn_rects['play']=pr

        # Stats link
        y+=60
        sr=pygame.Rect(cx-58,y,116,26); hov3=self.hover=='stats'
        bg3=HOVER if hov3 else PANEL
        pygame.draw.rect(self.screen,bg3,sr,border_radius=4)
        pygame.draw.rect(self.screen,ACCENT,sr,1,border_radius=4)
        ss=self.f_label.render("Statistics",True,ACCENT)
        self.screen.blit(ss,(sr.centerx-ss.get_width()//2,sr.centery-ss.get_height()//2))
        self.btn_rects['stats']=sr

    def _draw_continue_locked(self, cx, y, has_save):
        """Red-themed locked view when a saved game exists."""
        # Red lock banner
        banner_r = pygame.Rect(cx-220, y, 440, 54)
        pygame.draw.rect(self.screen, RED_BG, banner_r, border_radius=10)
        pygame.draw.rect(self.screen, RED_BOR, banner_r, 2, border_radius=10)
        t1 = self.f_head.render("Unfinished Game Found", True, (220,80,80))
        t2 = self.f_label.render("Continue your last game or resign it to start a new one.", True, MUTED)
        self.screen.blit(t1,(banner_r.centerx-t1.get_width()//2, y+7))
        self.screen.blit(t2,(banner_r.centerx-t2.get_width()//2, y+30))
        y += 70

        # Continue button (gold)
        cr=pygame.Rect(cx-115,y,230,52); hov=self.hover=='play'
        bg=(55,55,30) if hov else (40,38,18)
        pygame.draw.rect(self.screen,bg,cr,border_radius=10)
        pygame.draw.rect(self.screen,ACCENT,cr,2,border_radius=10)
        cs=self.f_btn.render("CONTINUE GAME",True,ACCENT)
        self.screen.blit(cs,(cr.centerx-cs.get_width()//2,cr.centery-cs.get_height()//2))
        self.btn_rects['play']=cr
        y+=62

        # Resign and start new
        rr=pygame.Rect(cx-100,y,200,38); hov2=self.hover=='newgame'
        bg2=( 55,22,22) if hov2 else (38,18,18)
        pygame.draw.rect(self.screen,bg2,rr,border_radius=8)
        pygame.draw.rect(self.screen,RED_BOR,rr,1+(1 if hov2 else 0),border_radius=8)
        rs=self.f_btn.render("Resign & New Game",True,(210,70,70))
        self.screen.blit(rs,(rr.centerx-rs.get_width()//2,rr.centery-rs.get_height()//2))
        self.btn_rects['newgame']=rr
        y+=50

        # Stats link
        sr=pygame.Rect(cx-58,y,116,26); hov3=self.hover=='stats'
        bg3=HOVER if hov3 else PANEL
        pygame.draw.rect(self.screen,bg3,sr,border_radius=4)
        pygame.draw.rect(self.screen,ACCENT,sr,1,border_radius=4)
        ss=self.f_label.render("Statistics",True,ACCENT)
        self.screen.blit(ss,(sr.centerx-ss.get_width()//2,sr.centery-ss.get_height()//2))
        self.btn_rects['stats']=sr

    def _draw_text(self, lines):
        y=134-self.scroll_y; left=self.W//2-300
        # Clip so text doesn't draw above nav bar
        clip=pygame.Rect(0,128,self.W,self.H-128)
        self.screen.set_clip(clip)
        for text,is_head in lines:
            if y>self.H: break
            if y>118:
                if is_head: s=self.f_head.render(text,True,ACCENT)
                else:       s=self.f_body.render(text,True,BRIGHT if text else DIM)
                self.screen.blit(s,(left,y))
            y+=26 if is_head else 21
        self.screen.set_clip(None)

    def _draw_quit_dialog(self):
        # Full-screen blocking overlay
        ov=pygame.Surface((self.W,self.H),pygame.SRCALPHA); ov.fill((0,0,0,175))
        self.screen.blit(ov,(0,0))
        dw,dh=340,120; dx=self.W//2-dw//2; dy=self.H//2-dh//2
        pygame.draw.rect(self.screen,(22,22,30),(dx,dy,dw,dh),border_radius=12)
        pygame.draw.rect(self.screen,RED,(dx,dy,dw,dh),2,border_radius=12)
        t=self.f_dialog.render("Quit Deterministic Gambit?",True,TEXT)
        self.screen.blit(t,(dx+dw//2-t.get_width()//2,dy+16))

        bw=140; gap=16; total=2*bw+gap; bsx=dx+dw//2-total//2; by=dy+52
        mx,my=pygame.mouse.get_pos()
        self._quit_rects={}
        for i,(key,lbl,col) in enumerate([('quit_yes','Exit (Y)',RED),
                                           ('quit_no', 'Cancel (N/Esc)',GREEN)]):
            r=pygame.Rect(bsx+i*(bw+gap),by,bw,38)
            hov=r.collidepoint(mx,my)
            bg=(58,20,20) if (hov and key=='quit_yes') else \
               (20,52,20) if (hov and key=='quit_no')  else (38,38,50)
            pygame.draw.rect(self.screen,bg,r,border_radius=7)
            pygame.draw.rect(self.screen,col,r,2 if hov else 1,border_radius=7)
            ls=self.f_btn.render(lbl,True,col)
            self.screen.blit(ls,(r.centerx-ls.get_width()//2,r.centery-ls.get_height()//2))
            self._quit_rects[key]=r

    # ── Input ─────────────────────────────────────────────────────────────
    def _hit(self,pos):
        for name,rect in self.btn_rects.items():
            if rect.collidepoint(pos): return name
        return None

    def _click(self,pos):
        # If quit dialog is open, ONLY check its own rects — block everything else
        if self._show_quit:
            for key,r in getattr(self,'_quit_rects',{}).items():
                if r.collidepoint(pos):
                    if key=='quit_yes':
                        import sys; pygame.quit(); sys.exit()
                    else:
                        self._show_quit=False
                    return None
            # Click outside dialog
            if self.sound: self.sound.play('illegal')
            return None
        hit=self._hit(pos)
        if not hit: return None
        if hit.startswith('nav_'):
            new_page=hit[4:]
            self.page=new_page; self.scroll_y=0
            return None
        if hit.startswith('level_'):
            self.sel_level=int(hit[6:]); return None
        if hit.startswith('time_'):
            self.sel_time=int(hit[5:]); return None
        if hit.startswith('color_'):
            self.sel_color=hit[6:]; return None
        if hit=='stats':
            self._open_stats(); return None
        if hit=='newgame':
            if os.path.exists(SAVE_FILE): os.remove(SAVE_FILE)
            if self.sound: self.sound.play('end')
            return None
        if hit=='play':
            skill,_,_,_=LEVELS[self.sel_level]; secs=TIME_OPTIONS[self.sel_time][0]
            return {'skill':skill,'depth':min(15,5+skill),
                    'player_color':self.sel_color,'time_limit':secs,
                    'continue_save':os.path.exists(SAVE_FILE)}
        return None

    def _open_stats(self):
        def _run():
            try:
                from stats_window import StatsWindow
                print("[Stats] Window opened.")
                win=StatsWindow()
                win.root.protocol("WM_DELETE_WINDOW",
                    lambda: (print("[Stats] Window closed."), win._on_close()))
                win.root.mainloop()
            except Exception as e: print(f"[Stats] Error: {e}")
        threading.Thread(target=_run,daemon=True).start()
