# renderer.py — Deterministic Gambit renderer

import pygame, os

# ── Colours ──────────────────────────────────────────────────────────────────
LIGHT_SQ   = (240,217,181); DARK_SQ    = (181,136, 99)
SELECTED   = (106,168, 79); LEGAL_DOT  = ( 74,140, 70,160)
LAST_MOVE  = (205,210, 86,120); CHECK_RED= (220, 50, 50,140)
PREMOVE_HL = (200, 60, 60,130)
BG         = ( 18, 18, 24); PANEL_BG   = ( 22, 22, 28)
COORD_L    = (181,136, 99); COORD_D    = (240,217,181)
T_WHITE    = (230,230,230); T_GOLD     = (212,175, 55)
T_GREEN    = (106,168, 79); T_RED      = (220, 80, 80)
MUTED      = (150,150,162); CLOCK_WARN = (220, 80, 50)

PIECE_FILE_MAP = {
    ('white','king'):'wK', ('white','queen'):'wQ', ('white','rook'):'wR',
    ('white','bishop'):'wB',('white','knight'):'wN',('white','pawn'):'wP',
    ('black','king'):'bK', ('black','queen'):'bQ', ('black','rook'):'bR',
    ('black','bishop'):'bB',('black','knight'):'bN',('black','pawn'):'bP',
}
PIECE_FALLBACK = {
    ('white','king'):'K',('white','queen'):'Q',('white','rook'):'R',
    ('white','bishop'):'B',('white','knight'):'N',('white','pawn'):'P',
    ('black','king'):'k',('black','queen'):'q',('black','rook'):'r',
    ('black','bishop'):'b',('black','knight'):'n',('black','pawn'):'p',
}
UNICODE_FILL    = {'white':(255,255,255),'black':(20,20,20)}
UNICODE_OUTLINE = {'white':(55,55,55),  'black':(215,215,215)}
UNICODE_FONTS   = [
    r'C:\Windows\Fonts\seguisym.ttf', r'C:\Windows\Fonts\segoeui.ttf',
    '/System/Library/Fonts/Apple Symbols.ttf',
    '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
    '/Library/Fonts/Arial Unicode.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSerif.ttf',
]

# Animation duration: fast, linear (no ease — requested "faster, not smooth")
ANIM_MS = 60


class Animation:
    """Fast linear slide from start_px to end_px."""
    __slots__ = ('dest_pos','hide_pos','sx','sy','ex','ey','img','t0','dur')

    def __init__(self, dest_pos, start_px, end_px, img, dur=ANIM_MS, hide_pos=None):
        self.dest_pos = dest_pos   # board (row,col) — skip static draw here
        self.hide_pos = hide_pos   # extra square to suppress (used for reverse anim)
        self.sx,self.sy = start_px
        self.ex,self.ey = end_px
        self.img = img
        self.t0  = pygame.time.get_ticks()
        self.dur = dur

    def current_px(self):
        # Linear interpolation — no easing, feels snappier
        f = min(1.0, (pygame.time.get_ticks()-self.t0)/max(1,self.dur))
        return self.sx+(self.ex-self.sx)*f, self.sy+(self.ey-self.sy)*f

    def done(self):
        return pygame.time.get_ticks() >= self.t0+self.dur


class TurnIndicator:
    """AI [elo] (left, red=active) | Player (right, green=active)"""
    FADE_MS = 280

    def __init__(self):
        self._frac = 1.0    # 1.0 = player active, 0.0 = AI active
        self._from = 1.0; self._to = 1.0; self._t0 = 0

    def set_active(self, player_active: bool):
        target = 1.0 if player_active else 0.0
        if target != self._to:
            self._from = self._frac; self._to = target
            self._t0   = pygame.time.get_ticks()

    def _tick(self):
        t = min(1.0,(pygame.time.get_ticks()-self._t0)/max(1,self.FADE_MS))
        t = t*t*(3-2*t)
        self._frac = self._from+(self._to-self._from)*t

    def draw(self, screen, font_reg, font_bold, left_x, y, elo_str):
        """AI [elo]  |  Player — left-aligned from left_x."""
        self._tick(); f = self._frac
        ai_col     = _lerp(T_RED,  MUTED, f)   # red when AI active (f=0)
        player_col = _lerp(MUTED, T_GREEN, f)  # green when player active (f=1)

        ai_s  = font_bold.render(f"AI [{elo_str}]", True, ai_col)
        sep_s = font_reg.render(" | ", True, MUTED)
        pl_s  = font_bold.render("Player",          True, player_col)

        screen.blit(ai_s,  (left_x, y))
        screen.blit(sep_s, (left_x+ai_s.get_width(), y))
        screen.blit(pl_s,  (left_x+ai_s.get_width()+sep_s.get_width(), y))


def _lerp(c1,c2,t):
    return tuple(max(0,min(255,int(a+(b-a)*t))) for a,b in zip(c1,c2))


class Renderer:
    ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),'assets')
    PIECES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),'assets','pieces')

    def __init__(self, screen, sq_size=72, flip_board=False):
        self.screen   = screen
        self.sq       = sq_size
        self.flip     = flip_board
        self.ox       = 52
        self.oy       = 36
        self.panel_x  = self.ox + 8*sq_size + 14
        self.panel_w  = 278
        self.btn_rects  = {}
        self._log_rects = {}
        # Log manual scroll offset (rows); -1 = auto-follow
        self._log_scroll    = 0
        self._log_max_scroll = 0  # updated each draw
        self._user_scrolled  = False  # True when user manually scrolled

        self._anim: Animation | None = None
        self._turn_ind = TurnIndicator()

        self._init_fonts()
        self._init_surfaces()
        self.piece_images = self._load_pieces(sq_size)
        self.board_image  = self._load_board_img()

        print("[Renderer] Initialised.")
        if self.board_image: print("[Renderer] board.png loaded.")
        else:                print("[Renderer] board.png not found — coloured squares.")

    def _init_fonts(self):
        ps = int(self.sq*0.74)
        self.pf      = self._ufont(ps)
        self.f_xs    = pygame.font.SysFont('consolas',12)
        self.f_sm    = pygame.font.SysFont('consolas',14)
        self.f_smb   = pygame.font.SysFont('consolas',14,bold=True)
        self.f_md    = pygame.font.SysFont('consolas',16)
        self.f_mdb   = pygame.font.SysFont('consolas',16,bold=True)
        self.f_lg    = pygame.font.SysFont('consolas',18,bold=True)
        self.f_clk   = pygame.font.SysFont('consolas',22,bold=True)
        self.f_coord = pygame.font.SysFont('consolas',14)

    def _ufont(self,size):
        for p in UNICODE_FONTS:
            if os.path.exists(p):
                try:
                    f=pygame.font.Font(p,size)
                    if f.render('K',True,(0,0,0)).get_width()>4: return f
                except Exception: pass
        return pygame.font.SysFont(None,size)

    def _init_surfaces(self):
        sq=self.sq
        def s(c): surf=pygame.Surface((sq,sq),pygame.SRCALPHA); surf.fill(c); return surf
        self._srf_legal=pygame.Surface((sq,sq),pygame.SRCALPHA)
        self._srf_legal.fill((0,0,0,0))
        pygame.draw.circle(self._srf_legal,LEGAL_DOT,(sq//2,sq//2),sq//7)
        self._srf_check  = s(CHECK_RED)
        self._srf_lastmv = s(LAST_MOVE)
        self._srf_premov = s(PREMOVE_HL)

    def _load_pieces(self,sq_size):
        images={}; size=sq_size-6
        for d in [self.PIECES_DIR,self.ASSETS_DIR]:
            for (col,pt),stem in PIECE_FILE_MAP.items():
                if (col,pt) in images: continue
                p=os.path.join(d,stem+'.png')
                if os.path.exists(p):
                    try:
                        raw=pygame.image.load(p).convert_alpha()
                        images[(col,pt)]=pygame.transform.smoothscale(raw,(size,size))
                    except Exception as e:
                        print(f"[Renderer] Cannot load {stem}.png: {e}")
        n=len(images)
        if n==12: print("[Renderer] All 12 piece images loaded.")
        elif n>0: print(f"[Renderer] {n}/12 pieces — rest use letter fallback.")
        else:     print("[Renderer] No PNG pieces — letter fallback.")
        return images

    def _load_board_img(self):
        p=os.path.join(self.ASSETS_DIR,'board.png')
        if os.path.exists(p):
            try:
                img=pygame.image.load(p).convert()
                return pygame.transform.smoothscale(img,(self.sq*8,self.sq*8))
            except Exception as e: print(f"[Renderer] board.png error: {e}")
        return None

    # ── Animation ──────────────────────────────────────────────────────────
    def start_animation(self, key, from_pos, to_pos, from_px=None, hide_pos=None):
        img=self.piece_images.get(key)
        if not img: return
        sq=self.sq
        def sq_tl(r,c):
            dr,dc=self._flip(r,c)
            return (self.ox+dc*sq+(sq-img.get_width())//2,
                    self.oy+dr*sq+(sq-img.get_height())//2)
        start = from_px if from_px is not None else sq_tl(*from_pos)
        end   = sq_tl(*to_pos)
        self._anim = Animation(to_pos, start, end, img, hide_pos=hide_pos)

    def anim_running(self):
        if self._anim and self._anim.done(): self._anim=None
        return self._anim is not None

    def animate_history_move(self, mv, go_back=False):
        fp = mv.get('from_pos'); tp = mv.get('to_pos')
        color = mv.get('color','white'); pt = mv.get('piece_type','pawn')
        if fp and tp:
            if go_back:
                # Reverse: animate from tp back to fp.
                # Board (before move) has piece at fp — suppress it so animation
                # appears to slide the piece from tp back to fp (true Tenet reverse).
                self.start_animation((color, pt), tp, fp, hide_pos=fp)
            else:
                self.start_animation((color, pt), fp, tp)

    # ── Coord helpers ──────────────────────────────────────────────────────
    def _flip(self,r,c):
        if self.flip: return 7-r,7-c
        return r,c

    def _unflip(self,dr,dc):
        if self.flip: return 7-dr,7-dc
        return dr,dc

    # ── Scroll API ─────────────────────────────────────────────────────────
    def scroll_log(self, delta):
        """delta: +1 down (older), -1 up (newer). Clamped to valid range."""
        self._log_scroll = max(0, min(self._log_max_scroll,
                                      self._log_scroll + delta))

    def is_over_log(self, px, py):
        return any(r.collidepoint(px,py) for r in self._log_rects.values())

    # ── Master draw ────────────────────────────────────────────────────────
    def draw(self, game, selected_pos=None, legal_moves=None,
             last_move=None, promotion_pending=None,
             ai_thinking=False, drag_piece=None, drag_pos=None,
             premove_from=None, premove_to=None,
             premove_sel=None, premove_legal=None,
             display_score=0, elo_str='?', hover_blocked=False):

        display_board = game.get_display_board()
        browsing      = game.view_index != -1

        # Yellow highlight squares
        hl = set()
        if browsing:
            hf,ht = game.get_history_highlight()
            if hf: hl = {hf,ht}
        elif last_move:
            hl = set(last_move)

        if not game.game_over and not browsing:
            self._turn_ind.set_active(game.is_player_turn() and not ai_thinking)

        self.screen.fill(BG)
        self._draw_board(display_board, selected_pos, legal_moves,
                         hl, browsing, game, premove_from, premove_to,
                         premove_sel, premove_legal or [])
        self._draw_pieces(display_board, drag_piece)
        self._draw_coords()

        # Slide animation drawn on top of board
        if self._anim:
            if not self._anim.done():
                ax,ay = self._anim.current_px()
                self.screen.blit(self._anim.img,(int(ax),int(ay)))
            else:
                self._anim = None

        # Drag ghost
        if drag_piece and drag_pos:
            img=self.piece_images.get((drag_piece[0],drag_piece[1]))
            if img:
                self.screen.blit(img,(drag_pos[0]-img.get_width()//2,
                                      drag_pos[1]-img.get_height()//2))

        self._draw_panel(game,ai_thinking,browsing,display_score,elo_str,hover_blocked)

        if promotion_pending: self._draw_promo_banner(promotion_pending)
        if browsing:          self._draw_history_badge(game)

    # ── Board ──────────────────────────────────────────────────────────────
    def _draw_board(self, board, sel, legal, hl, browsing, game,
                    premove_from, premove_to, premove_sel=None, premove_legal=None):
        sq=self.sq; ox,oy=self.ox,self.oy
        legal_set=set(legal) if legal else set()
        pm_set=set()
        if premove_from: pm_set.add(premove_from)
        if premove_to:   pm_set.add(premove_to)
        pm_legal_set=set(premove_legal) if premove_legal else set()

        if self.board_image:
            self.screen.blit(self.board_image,(ox,oy))
        else:
            for r in range(8):
                for c in range(8):
                    dr,dc=self._flip(r,c)
                    col=LIGHT_SQ if (r+c)%2==0 else DARK_SQ
                    pygame.draw.rect(self.screen,col,(ox+dc*sq,oy+dr*sq,sq,sq))

        chk=None
        if not browsing and game.in_check:
            k=game.board.get_king(game.current_player)
            if k: chk=k.position

        for r in range(8):
            for c in range(8):
                dr,dc=self._flip(r,c); x,y=ox+dc*sq,oy+dr*sq; pos=(r,c)
                if pos in hl:       self.screen.blit(self._srf_lastmv,(x,y))
                if chk==pos:        self.screen.blit(self._srf_check,(x,y))
                if sel==pos:        pygame.draw.rect(self.screen,SELECTED,(x,y,sq,sq),4)
                if pos in legal_set:
                    if board.get_piece(r,c):
                        pygame.draw.rect(self.screen,SELECTED,(x+2,y+2,sq-4,sq-4),4)
                    else:
                        self.screen.blit(self._srf_legal,(x,y))
                if pos in pm_set:   self.screen.blit(self._srf_premov,(x,y))
                if premove_sel==pos: pygame.draw.rect(self.screen,PREMOVE_HL[:3],(x,y,sq,sq),4)
                if pos in pm_legal_set:
                    if board.get_piece(r,c):
                        pygame.draw.rect(self.screen,SELECTED,(x+2,y+2,sq-4,sq-4),3)
                    else:
                        self.screen.blit(self._srf_legal,(x,y))

    def _draw_coords(self):
        sq=self.sq; ox,oy=self.ox,self.oy
        files='abcdefgh'; ranks='87654321'
        if self.flip: files=files[::-1]; ranks=ranks[::-1]
        WHITE=(255,255,255)
        for i in range(8):
            fs=self.f_coord.render(files[i],True,WHITE)
            self.screen.blit(fs,(ox+i*sq+sq//2-fs.get_width()//2, oy+8*sq+4))
            rs=self.f_coord.render(ranks[i],True,WHITE)
            self.screen.blit(rs,(ox-rs.get_width()-4, oy+i*sq+sq//2-rs.get_height()//2))

    def _draw_pieces(self, board, drag_piece=None):
        sq=self.sq; ox,oy=self.ox,self.oy
        skip_drag = drag_piece[2] if drag_piece else None
        # Skip dest_pos and hide_pos of animation to prevent ghost pieces
        skip_anim  = self._anim.dest_pos if self._anim else None
        skip_anim2 = self._anim.hide_pos if self._anim else None

        for r in range(8):
            for c in range(8):
                if (r,c)==skip_drag: continue
                if (r,c)==skip_anim: continue
                if (r,c)==skip_anim2: continue
                p=board.get_piece(r,c)
                if not p: continue
                dr,dc=self._flip(r,c)
                self._blit_piece((p.color,p.piece_type),ox+dc*sq,oy+dr*sq)

    def _blit_piece(self,key,x,y):
        sq=self.sq
        if key in self.piece_images:
            img=self.piece_images[key]
            self.screen.blit(img,(x+(sq-img.get_width())//2,
                                  y+(sq-img.get_height())//2))
        else:
            color,_=key; letter=PIECE_FALLBACK.get(key,'?')
            cx,cy=x+sq//2,y+sq//2
            out=self.pf.render(letter,True,UNICODE_OUTLINE[color])
            ow,oh=out.get_width(),out.get_height()
            for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                self.screen.blit(out,(cx-ow//2+dx,cy-oh//2+dy))
            fil=self.pf.render(letter,True,UNICODE_FILL[color])
            self.screen.blit(fil,(cx-fil.get_width()//2,cy-fil.get_height()//2))

    # ── Panel ──────────────────────────────────────────────────────────────
    def _draw_panel(self, game, ai_thinking, browsing, display_score, elo_str, hover_blocked=False):
        px=self.panel_x; pw=self.panel_w
        pygame.draw.rect(self.screen,PANEL_BG,(px,0,pw+16,8*self.sq+self.oy+24))
        self.btn_rects={}
        y=self.oy+6

        # Turn indicator — AI [elo] | Player, left aligned
        if not game.game_over:
            self._turn_ind.draw(self.screen,self.f_sm,self.f_smb,px+8,y,elo_str)
        else:
            res=game.result or 'Game Over'
            col=T_GREEN if 'Player' in res else T_RED if 'AI' in res else T_GOLD
            self._t(self.f_lg,res,col,px+8,y)
        y+=28

        # Clock right-aligned
        if game.time_limit and not game.game_over:
            m,s=game.player_time_display()
            warn=game.player_time_left is not None and game.player_time_left<=10
            ts=self.f_clk.render(f"{m}:{s:02d}",True,CLOCK_WARN if warn else T_WHITE)
            self.screen.blit(ts,(px+pw-ts.get_width()-6,y))

        if game.in_check and not game.game_over and not browsing:
            self._t(self.f_mdb,"CHECK!",T_RED,px+8,y); y+=22

        sc=display_score
        scs=f"+{sc}" if sc>0 else str(sc)
        col=T_GREEN if sc>0 else (T_RED if sc<0 else MUTED)
        self._t(self.f_mdb,f"Material: {scs}",col,px+8,y); y+=24

        pygame.draw.line(self.screen,(55,55,68),(px+4,y),(px+pw,y),1); y+=8

        log_h=max(80,8*self.sq-y+self.oy-100)
        self._draw_log(game,px,y,pw,log_h,browsing)
        y+=log_h+8

        pygame.draw.line(self.screen,(55,55,68),(px+4,y),(px+pw,y),1); y+=8

        self._btn("Statistics",px+8,y,pw-16,32,T_GOLD,hover_blocked);  y+=42
        if not game.game_over:
            self._btn("Resign",  px+8,y,pw-16,32,T_RED,hover_blocked);  y+=42
        if game.game_over:
            self._btn("New Game",px+8,y,pw-16,32,T_GREEN,hover_blocked); y+=42

        hint=self.f_xs.render("← → browse   Esc=menu   R-click=cancel",True,MUTED)
        self.screen.blit(hint,(px+pw//2-hint.get_width()//2,y+4))

    def _draw_log(self, game, px, y, pw, max_h, browsing):
        history=game.move_history
        self._log_rects={}
        rh=19
        total=len(history)
        # total_items: -1(start) + 0..total-1 + one "live" row when not game over
        # Each PAIR of moves is 1 chess turn. We number by: item -1=start,
        # items 0..total-1 = individual ply (half-moves).
        # Additionally show a "live" placeholder row at the end when not browsing.
        has_live_row = False  # recent move is always visible; no extra live row needed

        # Count items: start(-1) + total moves + live row if applicable
        total_items = 1 + total + (1 if has_live_row else 0)

        visible = max_h // rh
        self._log_max_scroll = max(0, total_items - visible)

        # Auto-scroll logic
        if browsing:
            if not self._user_scrolled:
                # Arrow key browse: always follow focused row
                focus_item = max(0, game.view_index)
                desired = max(0, focus_item - visible + 2)
                self._log_scroll = max(0, min(desired, self._log_max_scroll))
            # If user scrolled manually during browsing: respect that position
        elif not self._user_scrolled:
            # Live and no manual scroll: pin to bottom
            self._log_scroll = self._log_max_scroll
        # Clamp within valid range
        self._log_scroll = max(0, min(self._log_max_scroll, self._log_scroll))

        start_item = self._log_scroll
        clip=pygame.Rect(px+4,y,pw-4,max_h)
        self.screen.set_clip(clip)

        for row_n in range(visible+2):
            item_idx = start_item + row_n
            if item_idx >= total_items: break
            row_y = y + row_n*rh
            if row_y > y+max_h: break

            # Map item_idx to move index:
            #   item 0 = "(start)" (-1)
            #   items 1..total = history[0..total-1]
            #   item total+1 = "live" row (no move yet)
            i = item_idx - 1   # -1 = start, 0..total-1 = move

            is_live_item = has_live_row and item_idx == total + 1

            # Highlight
            if browsing:
                # Board at view_index shows state BEFORE move[view_index].
                # The last played move to reach this state is move[view_index-1].
                is_cur = (i == game.view_index - 1)
            else:
                # Live: highlight the most recent move
                is_cur = (i == total - 1)

            if is_cur:
                pygame.draw.rect(self.screen,(38,50,38),(px+4,row_y,pw-4,rh-1),border_radius=3)

            if i == -1:
                ns=self.f_sm.render("0.",True,MUTED)
                self.screen.blit(ns,(px+8,row_y+2))
                ss=self.f_smb.render("(start)",True,T_GOLD if is_cur else MUTED)
                self.screen.blit(ss,(px+52,row_y+2))
                self._log_rects[-1]=pygame.Rect(px+4,row_y,pw-4,rh)

            elif is_live_item:
                # Live placeholder row — show current move number, no notation
                move_num = total//2+1
                color_label = 'w' if game.current_player=='white' else 'b'
                s=self.f_smb.render(f"{move_num}{color_label}. ...",True,T_GOLD)
                self.screen.blit(s,(px+8,row_y+2))
                # Not clickable

            else:
                if i < 0 or i >= len(history): break
                mv=history[i]; is_w=mv['color']=='white'
                # Turn number: move pair index, 1-based
                turn_num = i//2+1
                col_lbl  = 'w' if is_w else 'b'
                ns=self.f_sm.render(f"{turn_num}{col_lbl}.",True,MUTED)
                self.screen.blit(ns,(px+8,row_y+2))
                fg=T_GREEN if is_cur else (T_WHITE if is_w else (200,200,218))
                ns2=self.f_smb.render(mv.get('notation','?'),True,fg)
                self.screen.blit(ns2,(px+52,row_y+2))
                self._log_rects[i]=pygame.Rect(px+4,row_y,pw-4,rh)

        self.screen.set_clip(None)

    def _btn(self,label,x,y,w,h,color,hover_blocked=False):
        rect=pygame.Rect(x,y,w,h)
        mx,my=pygame.mouse.get_pos(); hov=rect.collidepoint(mx,my) and not hover_blocked
        bg=tuple(min(255,c+22) for c in (42,42,52)) if hov else (42,42,52)
        bw=2 if hov else 1
        pygame.draw.rect(self.screen,bg,rect,border_radius=6)
        pygame.draw.rect(self.screen,color,rect,bw,border_radius=6)
        s=self.f_mdb.render(label,True,color)
        self.screen.blit(s,(rect.centerx-s.get_width()//2,
                            rect.centery-s.get_height()//2))
        self.btn_rects[label]=rect

    def _draw_history_badge(self,game):
        if game.view_index==-1:
            msg="  Opening position  |  → to live  "
        else:
            msg=f"  Move {game.view_index}/{len(game.move_history)}  |  → live  "
        s=self.f_sm.render(msg,True,T_WHITE)
        w,h=s.get_width()+14,s.get_height()+10
        ox=self.ox; oy=self.oy+8*self.sq+4
        bg=pygame.Surface((w,h),pygame.SRCALPHA); bg.fill((18,18,40,210))
        self.screen.blit(bg,(ox,oy))
        pygame.draw.rect(self.screen,T_GOLD,(ox,oy,w,h),1,border_radius=4)
        self.screen.blit(s,(ox+7,oy+5))

    def _draw_promo_banner(self,pt):
        sq=self.sq; ox,oy=self.ox,self.oy
        w,h=300,64; x=ox+4*sq-w//2; y=oy+4*sq-h//2
        s=pygame.Surface((w,h),pygame.SRCALPHA); s.fill((14,14,24,230))
        self.screen.blit(s,(x,y))
        pygame.draw.rect(self.screen,T_GOLD,(x,y,w,h),2,border_radius=8)
        l1=self.f_mdb.render("Pawn Promoted!",True,T_GOLD)
        l2=self.f_lg.render(f"→ {pt.capitalize()}",True,T_WHITE)
        self.screen.blit(l1,(x+w//2-l1.get_width()//2,y+8))
        self.screen.blit(l2,(x+w//2-l2.get_width()//2,y+32))

    def _t(self,font,text,color,x,y):
        self.screen.blit(font.render(text,True,color),(x,y))

    def pixel_to_board(self,px,py):
        dc=(px-self.ox)//self.sq; dr=(py-self.oy)//self.sq
        if 0<=dr<8 and 0<=dc<8: return self._unflip(dr,dc)
        return None

    def get_button(self,px,py):
        for lbl,rect in self.btn_rects.items():
            if rect.collidepoint(px,py): return lbl
        return None

    def get_log_click(self,px,py):
        for idx,rect in self._log_rects.items():
            if rect.collidepoint(px,py): return idx
        return None
