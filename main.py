# main.py — Deterministic Gambit

import sys, os, threading, time, pickle
import pygame
from lobby         import Lobby, SAVE_FILE
from game          import Game
from renderer      import Renderer
from sound_manager import SoundManager

SQ       = 72
PANEL_W  = 294
WINDOW_W = 52 + 8*SQ + PANEL_W + 24
WINDOW_H = 36 + 8*SQ + 44

AI_EVENT  = pygame.USEREVENT + 1
PROMO_MS  = 2000
AI_DELAY  = 2.0
KEY_DELAY = 380
KEY_RATE  =  75

_ESC_R = {}   # in-game menu rects, rebuilt every draw
_NG_R  = {}   # new-game confirm rects

def _load_match_count():
    try:
        from statistics_manager import StatisticsManager
        return [len(StatisticsManager.load_game_data())]
    except Exception:
        return [0]

_GAME_COUNT = _load_match_count()


def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Deterministic Gambit")
    clock  = pygame.time.Clock()
    sound  = SoundManager()
    print("=" * 55)
    print("  Deterministic Gambit — starting")
    print("=" * 55)
    try:
        while True:
            _run_once(screen, clock, sound)
    except KeyboardInterrupt:
        pass
    finally:
        pygame.quit(); sys.exit()


def _run_once(screen, clock, sound):
    lobby    = Lobby(screen, clock, sound)
    settings = lobby.run()

    is_continue = settings.get('continue_save') and os.path.exists(SAVE_FILE)
    if not is_continue:
        _GAME_COUNT[0] += 1

    if is_continue:
        game = _load_game(settings)
        print(f"[Load] Continuing saved game as Match #{_GAME_COUNT[0]}.")
    else:
        if os.path.exists(SAVE_FILE): os.remove(SAVE_FILE)
        game = Game(ai_skill=settings['skill'], ai_depth=settings['depth'],
                    player_color=settings['player_color'],
                    time_limit=settings['time_limit'])
        sound.play('start')
        print("[Game] New game started.")

    print(f"\n{'─'*55}")
    print(f"  Match #{_GAME_COUNT[0]}  skill={game.ai.skill_level} "
          f"color={game.player_color} time={game.time_limit}")
    print(f"{'─'*55}")

    from lobby import LEVELS
    elo_str = next((e for s,n,d,e in LEVELS if s==settings['skill']), '?')

    renderer = Renderer(screen, sq_size=SQ,
                        flip_board=(game.player_color=='black'))

    sel          = None; legal = []
    last_move    = set(); ai_thinking = False
    promo_banner = None; promo_until  = 0
    drag_piece   = None; drag_pos     = None
    # Pre-move (single): None or (from_pos, to_pos)
    pm_from      = None; pm_to = None
    pm_sel       = None   # square selected while queuing pre-move click
    pm_legal     = []     # legal moves for pm_sel piece (shown as green dots)
    show_esc     = False
    esc_hover    = None
    ng_confirm   = False
    warned_10s   = False
    arrow_held   = None; arrow_held_t = 0; arrow_last_t = 0
    # When player holds a drag into their own turn, convert to normal move
    drag_held_into_turn = False

    if game.player_color == 'black' and not game.game_over:
        ai_thinking = True; _fire_ai(game)
    game.start_turn_clock(game.current_player)

    while True:
        now = pygame.time.get_ticks()

        if promo_banner and now > promo_until: promo_banner = None

        # Player clock — runs always (not frozen by ESC popup; ESC saves+returns)
        if game.is_player_turn() and not ai_thinking:
            if game.tick_clock():
                sound.play('end'); print("[Game] Player flagged.")
            if (game.player_time_left is not None
                    and game.player_time_left <= 10 and not warned_10s):
                sound.play('tenseconds'); warned_10s = True

        # Arrow hold-repeat
        if arrow_held is not None:
            if now-arrow_held_t > KEY_DELAY and now-arrow_last_t > KEY_RATE:
                _browse(game, arrow_held==pygame.K_LEFT, sound, renderer)
                sel=None; legal=[]; arrow_last_t=now

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                if game.game_over: return
                if show_esc: sound.play('illegal')
                else: show_esc = True
                continue

            elif event.type == AI_EVENT:
                ai_thinking = False
                fp,tp = event.from_pos, event.to_pos
                if fp and tp:
                    print(f"[AI]  {_pos_str(fp)} → {_pos_str(tp)}")
                    last_move = {fp,tp}
                    landed = game.board.get_piece(*tp)
                    key = (game.ai_color, landed.piece_type if landed else 'pawn')
                    renderer.start_animation(key, fp, tp)
                    _play_sound(sound, game, is_player=False)
                    if game.last_promotion:
                        promo_banner=game.last_promotion; promo_until=now+PROMO_MS

                # If player was holding a drag during AI turn → convert to normal
                if drag_held_into_turn and drag_piece is not None:
                    # Don't lose the piece; keep drag_piece, transition to normal
                    drag_held_into_turn = False
                    pm_sel = None; pm_legal = []; pm_from = None; pm_to = None
                    game.clear_premove()
                    # Re-compute legal moves for this piece
                    p = game.board.get_piece(*drag_piece[2])
                    if p and p.color == game.player_color:
                        sel   = drag_piece[2]
                        legal = game.get_legal_moves_for(p)
                    else:
                        drag_piece = None; drag_pos = None
                        sel=None; legal=[]
                else:
                    # If piece was click-selected for pre-move but destination not yet clicked,
                    # carry over that selection as a normal sel+legal so player can move immediately
                    if pm_sel is not None and pm_from is None and not game.game_over:
                        p = game.board.get_piece(*pm_sel)
                        if p and p.color == game.player_color:
                            sel = pm_sel
                            legal = game.get_legal_moves_for(p)
                    pm_sel = None; pm_legal = []
                    # Execute queued pre-move
                    if not game.game_over and pm_from is not None and pm_to is not None:
                        piece = game.board.get_piece(*pm_from)
                        if piece and piece.color == game.player_color:
                            if pm_to in game.board.get_legal_moves(piece):
                                p_key = (piece.color, piece.piece_type)
                                img   = renderer.piece_images.get(p_key)
                                lm,pb,pbu = _do_move(game,renderer,sound,
                                                      pm_from,pm_to,now)
                                last_move=lm; promo_banner=pb; promo_until=pbu
                                sel=None; legal=[]
                                print("[Game] Pre-move executed.")
                                if not game.game_over:
                                    ai_thinking=True; _fire_ai(game)
                            else:
                                sound.play('illegal')
                                print("[Game] Pre-move was illegal — discarded.")
                        pm_from=None; pm_to=None; pm_legal=[]

            elif event.type == pygame.KEYDOWN:
                if show_esc:
                    if event.key in (pygame.K_ESCAPE, pygame.K_n):
                        show_esc=False; esc_hover=None
                    elif event.key == pygame.K_y:
                        _save_and_return(game); return
                    elif event.key == pygame.K_r:
                        game.resign(); sound.play('end')
                        _save_and_return(game,discard=True); return
                elif ng_confirm:
                    if event.key == pygame.K_y:
                        game.resign(); sound.play('end')
                        if os.path.exists(SAVE_FILE): os.remove(SAVE_FILE)
                        return
                    elif event.key in (pygame.K_n, pygame.K_ESCAPE):
                        ng_confirm=False
                else:
                    if event.key == pygame.K_LEFT:
                        renderer._user_scrolled = False
                        _browse(game, True, sound, renderer); sel=None; legal=[]
                        arrow_held=pygame.K_LEFT; arrow_held_t=arrow_last_t=now
                    elif event.key == pygame.K_RIGHT:
                        renderer._user_scrolled = False
                        _browse(game, False, sound, renderer); sel=None; legal=[]
                        arrow_held=pygame.K_RIGHT; arrow_held_t=arrow_last_t=now
                    elif event.key == pygame.K_ESCAPE:
                        if game.game_over: return
                        show_esc = True

            elif event.type == pygame.KEYUP:
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    arrow_held=None

            elif event.type == pygame.MOUSEMOTION:
                if drag_piece and not show_esc and not ng_confirm:
                    drag_pos = event.pos
                if show_esc:   esc_hover = _esc_hit(event.pos)

            elif event.type == pygame.MOUSEWHEEL:
                if not show_esc and not ng_confirm:
                    if renderer.is_over_log(*pygame.mouse.get_pos()):
                        renderer.scroll_log(-1 if event.y > 0 else 1)
                        renderer._user_scrolled = True

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx,my = event.pos

                # Right-click: cancel everything
                if event.button == 3:
                    drag_piece=None; drag_pos=None
                    sel=None; legal=[]
                    pm_sel=None; pm_legal=[]; pm_from=None; pm_to=None
                    drag_held_into_turn=False
                    game.clear_premove()
                    continue

                if event.button != 1: continue

                # ── Pop-ups block all behind them ─────────────────────
                if show_esc:
                    btn=_esc_hit((mx,my))
                    if   btn=='return_menu': _save_and_return(game); return
                    elif btn=='resign': game.resign(); sound.play('end'); \
                         _save_and_return(game,discard=True); return
                    elif btn=='resume': show_esc=False; esc_hover=None
                    else: sound.play('illegal')
                    continue

                if ng_confirm:
                    btn=_ng_hit((mx,my))
                    if   btn=='yes':
                        game.resign(); sound.play('end')
                        if os.path.exists(SAVE_FILE): os.remove(SAVE_FILE)
                        return
                    elif btn=='no': ng_confirm=False
                    else:           sound.play('illegal')
                    continue

                # ── Panel buttons ─────────────────────────────────────
                btn=renderer.get_button(mx,my)
                if btn=='Statistics':
                    _open_stats(); continue
                elif btn=='New Game' and game.game_over:
                    if os.path.exists(SAVE_FILE): os.remove(SAVE_FILE)
                    return
                elif btn=='New Game' and not game.game_over:
                    ng_confirm=True; continue
                elif btn=='Resign' and not game.game_over:
                    game.resign(); sound.play('end')
                    print("[Game] Player resigned."); continue

                # ── Log click ─────────────────────────────────────────
                log_idx=renderer.get_log_click(mx,my)
                if log_idx is not None:
                    if ai_thinking and not game.game_over:
                        sound.play('illegal')
                    else:
                        prev_vi = game.view_index
                        # (start) row log_idx=-1 → opening = view_index=0
                        # row i → show board AFTER move i = view_index=i+1
                        if log_idx == -1:
                            target = 0
                        else:
                            target = log_idx + 1  # i+1 shows board after move i
                        game.browse_to(target); sel=None; legal=[]
                        vi = game.view_index
                        # animate the move at log_idx (if valid)
                        go_back = (log_idx < (prev_vi - 1)) if prev_vi > 0 else (prev_vi != -1)
                        if log_idx >= 0 and log_idx < len(game.move_history):
                            mv = game.move_history[log_idx]
                            _play_log_sound(sound, mv, game.player_color)
                            renderer.animate_history_move(mv, go_back=go_back)
                    continue

                # ── Board click ───────────────────────────────────────
                pos=renderer.pixel_to_board(mx,my)
                if pos is None: sel=None; legal=[]; continue

                if game.is_player_turn() and not ai_thinking:
                    piece=game.board.get_piece(*pos)
                    if piece and piece.color==game.player_color:
                        drag_piece=(piece.color,piece.piece_type,pos)
                        drag_pos=(mx,my); drag_held_into_turn=False
                        sel=pos; legal=game.get_legal_moves_for(piece)
                        pm_from=None; pm_to=None; pm_sel=None
                    elif sel and pos in legal:
                        lm,pb,pbu=_do_move(game,renderer,sound,sel,pos,now)
                        last_move=lm; promo_banner=pb; promo_until=pbu
                        sel=None; legal=[]; drag_piece=None; drag_pos=None
                        if not game.game_over:
                            ai_thinking=True; _fire_ai(game)
                    else:
                        sel=None; legal=[]; sound.play('illegal')

                elif ai_thinking and not game.game_over:
                    # Pre-move: click piece to select, click destination to queue
                    piece=game.board.get_piece(*pos)
                    is_own = piece is not None and piece.color == game.player_color
                    if pm_from is not None:
                        # Pre-move already queued — don't allow replacing it
                        sound.play('illegal')
                    elif pm_sel is None:
                        if is_own:
                            pm_sel=pos
                            pm_legal=game.board.get_legal_moves(piece)
                            drag_piece=(piece.color,piece.piece_type,pos)
                            drag_pos=(mx,my)
                        else:
                            sound.play('illegal')
                    elif pos == pm_sel:
                        # Clicked same square — deselect
                        pm_sel=None; pm_legal=[]; drag_piece=None; drag_pos=None
                    elif is_own:
                        # Clicked another own piece — switch selection
                        pm_sel=pos
                        pm_legal=game.board.get_legal_moves(piece)
                        drag_piece=(piece.color,piece.piece_type,pos)
                        drag_pos=(mx,my)
                    else:
                        # Clicked destination — queue pre-move
                        pm_from=pm_sel; pm_to=pos
                        game.set_premove(pm_from,pm_to)
                        print(f"[Game] Pre-move: {_pos_str(pm_from)} → {_pos_str(pm_to)}")
                        sound.play('premove')
                        pm_sel=None; pm_legal=[]; drag_piece=None; drag_pos=None
                else:
                    if game.view_index != -1:
                        sound.play('illegal')

            elif event.type == pygame.MOUSEBUTTONUP and event.button==1:
                if drag_piece and drag_pos:
                    pos  = renderer.pixel_to_board(*drag_pos)
                    orig = drag_piece[2]

                    if game.is_player_turn() and not ai_thinking:
                        if pos and pos in legal and pos!=orig:
                            img=renderer.piece_images.get(
                                (drag_piece[0],drag_piece[1]))
                            from_px=None
                            if img:
                                from_px=(drag_pos[0]-img.get_width()//2,
                                         drag_pos[1]-img.get_height()//2)
                            lm,pb,pbu=_do_move(game,renderer,sound,orig,pos,now,
                                               anim_from_px=from_px)
                            last_move=lm; promo_banner=pb; promo_until=pbu
                            sel=None; legal=[]
                            if not game.game_over:
                                ai_thinking=True; _fire_ai(game)
                        elif pos and pos!=orig:
                            sound.play('illegal')
                            sel=orig   # keep piece selected

                    elif ai_thinking and not game.game_over:
                        if drag_held_into_turn:
                            # Piece held from player's own turn — just convert to selection
                            drag_held_into_turn = False
                            if pos and pos == orig:
                                # Stayed on same square — keep as pm_sel
                                pm_sel = orig
                            # else: dragged away while own turn became AI turn — ignore
                        elif pos and pos != orig:
                            # Drag pre-move to a different square
                            pm_from=orig; pm_to=pos
                            game.set_premove(pm_from,pm_to)
                            print(f"[Game] Pre-move: {_pos_str(orig)} → {_pos_str(pos)}")
                            sound.play('premove')
                            pm_sel=None; pm_legal=[]
                        # If pos==orig: was a simple click — pm_sel stays set from MOUSEDOWN

                drag_piece=None; drag_pos=None

        # ── Render ──────────────────────────────────────────────────────
        renderer.draw(
            game,
            selected_pos      = sel if not show_esc and not ng_confirm else None,
            legal_moves       = legal if not show_esc and not ng_confirm else [],
            last_move         = last_move,
            promotion_pending = promo_banner,
            ai_thinking       = ai_thinking,
            drag_piece        = drag_piece,
            drag_pos          = drag_pos,
            premove_from      = pm_from,
            premove_to        = pm_to,
            premove_sel       = pm_sel,
            premove_legal     = pm_legal,
            display_score     = game.get_display_piece_score(),
            elo_str           = elo_str,
            hover_blocked     = show_esc or ng_confirm,
        )

        if show_esc:   _draw_esc_dialog(screen, esc_hover)
        if ng_confirm: _draw_ng_confirm(screen)

        pygame.display.flip()
        clock.tick(60)


# ── Pop-ups ───────────────────────────────────────────────────────────────────

def _esc_hit(pos):
    for k,r in _ESC_R.items():
        if r.collidepoint(pos): return k
    return None

def _ng_hit(pos):
    for k,r in _NG_R.items():
        if r.collidepoint(pos): return k
    return None

def _draw_esc_dialog(screen, hover=None):
    W,H=screen.get_size()
    ov=pygame.Surface((W,H),pygame.SRCALPHA); ov.fill((0,0,0,175))
    screen.blit(ov,(0,0))
    dw,dh=400,110; dx=W//2-dw//2; dy=H//2-dh//2
    pygame.draw.rect(screen,(20,20,30),(dx,dy,dw,dh),border_radius=12)
    pygame.draw.rect(screen,(212,175,55),(dx,dy,dw,dh),2,border_radius=12)
    ft=pygame.font.SysFont('consolas',15,bold=True)
    fb=pygame.font.SysFont('consolas',13)
    t=ft.render("Return to Menu?",True,(238,238,238))
    screen.blit(t,(dx+dw//2-t.get_width()//2,dy+14))
    btns=[('resume',"Stay (N/Esc)",(106,168,79)),
          ('return_menu',"Return (Y)",(212,175,55)),
          ('resign',"Resign (R)",(210,70,70))]
    bw=108; gap=10; total_w=len(btns)*bw+(len(btns)-1)*gap
    bsx=dx+dw//2-total_w//2; by=dy+50
    _ESC_R.clear()
    mx,my=pygame.mouse.get_pos()
    for i,(key,label,col) in enumerate(btns):
        r=pygame.Rect(bsx+i*(bw+gap),by,bw,36)
        hov=r.collidepoint(mx,my)
        bg=tuple(min(255,c+35) for c in (38,38,50)) if hov else (38,38,50)
        pygame.draw.rect(screen,bg,r,border_radius=7)
        pygame.draw.rect(screen,col,r,2 if hov else 1,border_radius=7)
        ls=fb.render(label,True,col)
        screen.blit(ls,(r.centerx-ls.get_width()//2,r.centery-ls.get_height()//2))
        _ESC_R[key]=r

def _draw_ng_confirm(screen):
    W,H=screen.get_size()
    ov=pygame.Surface((W,H),pygame.SRCALPHA); ov.fill((0,0,0,175))
    screen.blit(ov,(0,0))
    dw,dh=360,100; dx=W//2-dw//2; dy=H//2-dh//2
    pygame.draw.rect(screen,(20,20,30),(dx,dy,dw,dh),border_radius=12)
    pygame.draw.rect(screen,(210,70,70),(dx,dy,dw,dh),2,border_radius=12)
    ft=pygame.font.SysFont('consolas',14,bold=True)
    fb=pygame.font.SysFont('consolas',13)
    t=ft.render("Resign current game?",True,(238,238,238))
    screen.blit(t,(dx+dw//2-t.get_width()//2,dy+14))
    bw=148; gap=16; bsx=dx+dw//2-(2*bw+gap)//2; by=dy+50
    _NG_R.clear()
    mx,my=pygame.mouse.get_pos()
    for i,(key,lbl,col) in enumerate([
            ('yes',"Yes, Resign (Y)",(210,70,70)),
            ('no', "Keep Playing (N/Esc)",(106,168,79))]):
        r=pygame.Rect(bsx+i*(bw+gap),by,bw,36)
        hov=r.collidepoint(mx,my)
        bg=tuple(min(255,c+35) for c in (38,38,50)) if hov else (38,38,50)
        pygame.draw.rect(screen,bg,r,border_radius=7)
        pygame.draw.rect(screen,col,r,2 if hov else 1,border_radius=7)
        ls=fb.render(lbl,True,col)
        screen.blit(ls,(r.centerx-ls.get_width()//2,r.centery-ls.get_height()//2))
        _NG_R[key]=r


# ── Save / Load ───────────────────────────────────────────────────────────────

def _save_and_return(game, discard=False):
    os.makedirs(os.path.dirname(SAVE_FILE), exist_ok=True)
    if not discard and not game.game_over:
        try:
            with open(SAVE_FILE,'wb') as f: f.write(game.save_state())
            print(f"[Save] Saved to {SAVE_FILE}")
        except Exception as e: print(f"[Save] Failed: {e}")
    else:
        if os.path.exists(SAVE_FILE): os.remove(SAVE_FILE)
        print("[Save] Discarded.")
    game.ai.quit()


def _load_game(settings):
    import copy
    try:
        with open(SAVE_FILE,'rb') as f: data=pickle.loads(f.read())
        g=Game(ai_skill=data.get('ai_skill',settings['skill']),
               ai_depth=data.get('ai_depth',settings['depth']),
               player_color=data.get('player_color',settings['player_color']),
               time_limit=data.get('time_limit',settings['time_limit']))
        moves=data.get('moves_to_replay',[])
        saved_hist=data.get('move_history',[])
        for i,(fp,tp) in enumerate(moves):
            p=g.board.get_piece(*fp)
            if p:
                snap=copy.deepcopy(g.board)
                g.board.move_piece(fp,tp)
                meta=dict(saved_hist[i]) if i<len(saved_hist) else {}
                meta['board_snapshot']=snap
                meta['from_pos']=fp; meta['to_pos']=tp
                g.move_history.append(meta)
        g.fullmove=data.get('fullmove',1)
        g.halfmove_clock=data.get('halfmove_clock',0)
        g.result=data.get('result'); g.game_over=data.get('game_over',False)
        g.piece_score=data.get('piece_score',0)

        # Restore clocks — use actual saved values (not None)
        saved_ptl = data.get('player_time_left')
        saved_atl = data.get('ai_time_left')
        saved_tlimit = data.get('time_limit')
        if saved_tlimit:
            g.player_time_left = saved_ptl if saved_ptl is not None else float(saved_tlimit)
            g.ai_time_left     = saved_atl if saved_atl is not None else float(saved_tlimit)
            print(f"[Load] Clock restored: player={g.player_time_left:.1f}s AI={g.ai_time_left:.1f}s")
        else:
            g.player_time_left = None; g.ai_time_left = None

        g.is_continued=True
        if g.move_history:
            last_c=g.move_history[-1].get('color','white')
            g.current_player='black' if last_c=='white' else 'white'

        os.remove(SAVE_FILE)
        # Restore move_start_time so duration counts from before the game was saved
        saved_mst = data.get('move_start_time')
        if saved_mst is not None:
            g.stats.move_start_time = saved_mst
        else:
            g.stats.move_start_time = time.time()
        g.start_turn_clock(g.current_player)
        print("[Load] Restored successfully.")
        return g
    except Exception as e:
        print(f"[Load] Failed: {e} — starting fresh.")
        return Game(ai_skill=settings['skill'],ai_depth=settings['depth'],
                    player_color=settings['player_color'],
                    time_limit=settings['time_limit'])


# ── Move helpers ──────────────────────────────────────────────────────────────

def _do_move(game, renderer, sound, from_pos, to_pos, now, anim_from_px=None):
    piece=game.board.get_piece(*from_pos)
    key=(piece.color,piece.piece_type) if piece else None
    ok=game.make_human_move(from_pos,to_pos)
    if not ok: sound.play('illegal'); return set(),None,0
    print(f"[You] {_pos_str(from_pos)} → {_pos_str(to_pos)}")
    if key:
        renderer.start_animation(key, from_pos, to_pos, from_px=anim_from_px)
    _play_sound(sound,game,is_player=True)
    pb,pbu=None,0
    if game.last_promotion:
        sound.play('promote'); pb=game.last_promotion; pbu=now+PROMO_MS
        print(f"[Game] Promoted to {game.last_promotion}.")
    return {from_pos,to_pos},pb,pbu


def _browse(game, go_back, sound, renderer=None):
    if go_back:
        result = game.browse_back()
        if result is None: return  # already at turn 0 — stop, no sound
    else:
        if game.view_index == -1: return  # already live — stop, no sound
        game.browse_forward()
    vi = game.view_index
    hist = game.move_history
    if go_back:
        # Animate the move being UNDONE = move[vi] (we just stepped back over it)
        sound_idx = vi if vi >= 0 else len(hist) - 1
    else:
        # Going forward: vi=-1 means we arrived at live; animate the last move
        sound_idx = vi - 1 if vi >= 0 else len(hist) - 1
    if sound_idx >= 0 and sound_idx < len(hist):
        mv = hist[sound_idx]
        _play_log_sound(sound, mv, game.player_color)
        if renderer:
            renderer.animate_history_move(mv, go_back=go_back)


def _play_log_sound(sound, mv, player_color=None):
    pt = mv.get('piece_type','')
    if pt == '(end)': return
    is_player = (player_color is None) or (mv.get('color') == player_color)
    if mv.get('promotion'):
        sound.play('promote')
    elif mv.get('last_was_castle'):
        sound.play('castle')
    elif mv.get('last_was_capture') and mv.get('in_check'):
        sound.play('capture'); sound.play('check')
    elif mv.get('in_check'):
        sound.play('check')
    elif mv.get('last_was_capture'):
        sound.play('capture')
    else:
        sound.play('move_self' if is_player else 'move_opponent')


def _fire_ai(game):
    def _run():
        try:
            time.sleep(AI_DELAY); fp,tp=game.make_ai_move()
        except Exception as e:
            print(f"[AI] Error: {e}"); fp=tp=None
        pygame.event.post(pygame.event.Event(AI_EVENT,{'from_pos':fp,'to_pos':tp}))
    threading.Thread(target=_run,daemon=True).start()


def _play_sound(sound, game, is_player=True):
    if game.game_over:
        if game.is_checkmate:
            if game.last_was_capture: sound.play('capture')
            sound.play('check'); sound.play('end')
        elif game.is_stalemate:
            sound.play('move_self' if is_player else 'move_opponent')
            sound.play('end')
        else:
            sound.play('end')
        print(f"[Sound] Game ended: {game.result}")
        return
    # Build up combined effects — order: move/castle base, then capture, then check
    if game.last_was_castle:
        sound.play('castle')
    elif game.last_was_capture:
        sound.play('capture')
    else:
        sound.play('move_self' if is_player else 'move_opponent')
    if game.in_check:
        sound.play('check')


def _open_stats():
    import subprocess, sys
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stats_window.py')
    try:
        subprocess.Popen([sys.executable, script],
                         creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess,'CREATE_NO_WINDOW') else 0)
        print("[Stats] Window opened in subprocess.")
    except Exception as e:
        print(f"[Stats] Error: {e}")


def _pos_str(pos):
    if not pos: return '??'
    r,c=pos; return 'abcdefgh'[c]+str(8-r)


if __name__ == '__main__':
    main()
