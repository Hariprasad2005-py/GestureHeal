"""
modules/ui_renderer.py
All Pygame rendering: menu, HUD, game board, results screen.
Full Fruit Ninja style visuals with blade trail, splatter effects, bamboo dojo theme.
"""

import pygame
import math
import time
import random
import os
from modules.game_engine import MAX_MISSES

# ─── Color Palette ────────────────────────────────────────────────────────────
BG        = (8,  12,  28)
ACCENT    = (0,  240, 180)
WARN      = (255, 80,  60)
WHITE     = (240, 245, 255)
GRAY      = (80,  90, 110)
GOLD      = (255, 200, 50)
PANEL     = (15,  22,  45)
PANEL2    = (20,  30,  60)
PURPLE    = (120, 80, 220)


def load_font(size, bold=False):
    try:
        return pygame.font.SysFont("consolas", size, bold=bold)
    except:
        return pygame.font.Font(None, size)


class BladeTrail:
    """Glowing sword slash trail."""
    def __init__(self):
        self.points = []
        self.max_age = 0.22

    def add(self, x, y):
        self.points.append((x, y, time.time()))

    def update(self):
        now = time.time()
        self.points = [(x, y, t) for x, y, t in self.points if now - t < self.max_age]

    def draw(self, surface):
        if len(self.points) < 2:
            return
        now = time.time()
        for i in range(1, len(self.points)):
            x1, y1, t1 = self.points[i - 1]
            x2, y2, t2 = self.points[i]
            age  = now - t2
            frac = max(0.0, 1.0 - age / self.max_age)
            width = max(1, int(14 * frac))
            glow_c = (int(80 * frac), int(255 * frac), int(200 * frac))
            pygame.draw.line(surface, glow_c, (int(x1), int(y1)), (int(x2), int(y2)), width + 6)
            core_c = (int(200 * frac), int(255 * frac), int(240 * frac))
            pygame.draw.line(surface, core_c, (int(x1), int(y1)), (int(x2), int(y2)), max(1, width - 2))


class JuiceSplatter:
    """Juice burst when a fruit is sliced."""
    def __init__(self, x, y, color):
        self.drops = []
        for _ in range(20):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(60, 280)
            self.drops.append({
                "x": float(x), "y": float(y),
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed - 120,
                "r": random.randint(4, 11),
                "life": random.uniform(0.4, 0.9),
                "maxlife": 1.0,
                "color": color,
            })
        self.splats = [{"x": x + random.randint(-50, 50),
                        "y": y + random.randint(-40, 40),
                        "r": random.randint(3, 9),
                        "color": color} for _ in range(6)]
        self.alive = True

    def update(self, dt):
        for d in self.drops:
            d["x"]  += d["vx"] * dt
            d["y"]  += d["vy"] * dt
            d["vy"] += 420 * dt
            d["life"] -= dt
        self.drops = [d for d in self.drops if d["life"] > 0]
        if not self.drops:
            self.alive = False

    def draw(self, surface):
        for s in self.splats:
            pygame.draw.circle(surface, s["color"], (int(s["x"]), int(s["y"])), s["r"])
        for d in self.drops:
            frac = d["life"] / d["maxlife"]
            c = tuple(min(255, int(ch * frac)) for ch in d["color"])
            pygame.draw.circle(surface, c, (int(d["x"]), int(d["y"])), max(1, int(d["r"] * frac)))


class UIRenderer:
    def __init__(self, screen, W, H, game_x=0, game_w=None):
        self.screen = screen
        self.W      = W
        self.H      = H
        self.game_x = game_x
        self.game_w = game_w if game_w is not None else W
        self.game_h = H
        self.game_surface = pygame.Surface((self.game_w, self.game_h), pygame.SRCALPHA)
        self.last_level_boxes = []

        self.font_xl  = load_font(72, bold=True)
        self.font_lg  = load_font(44, bold=True)
        self.font_md  = load_font(28, bold=True)
        self.font_sm  = load_font(20)
        self.font_xs  = load_font(15)

        self._start_time  = time.time()
        self.blade        = BladeTrail()
        self.splatters    = []
        self._sliced_ids  = set()

        random.seed(7)
        self._bamboo = [(random.randint(0, W), random.randint(20, 80),
                         random.randint(8, 18), random.uniform(0.6, 1.0))
                        for _ in range(18)]

    def _elapsed(self): return time.time() - self._start_time
    def _pulse(self, freq=2.0, lo=0.7, hi=1.0):
        return lo + (hi - lo) * (0.5 + 0.5 * math.sin(2 * math.pi * freq * self._elapsed()))

    def _draw_text(self, text, font, color, cx, cy, anchor="center", surface=None):
        target = surface if surface is not None else self.screen
        surf = font.render(str(text), True, color)
        r = surf.get_rect()
        if anchor == "center": r.center = (cx, cy)
        elif anchor == "left":  r.midleft = (cx, cy)
        elif anchor == "right": r.midright = (cx, cy)
        target.blit(surf, r)

    def _draw_panel(self, rect, color=PANEL, border=ACCENT, radius=12, alpha=200, surface=None):
        target = surface if surface is not None else self.screen
        s = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
        s.fill((*color[:3], alpha))
        target.blit(s, (rect[0], rect[1]))
        pygame.draw.rect(target, border, rect, 2, border_radius=radius)

    def _draw_dojo_bg(self, surface=None, W=None, H=None):
        target = surface if surface is not None else self.screen
        W = W if W is not None else self.W
        H = H if H is not None else self.H
        target.fill((6, 9, 20))
        t = self._elapsed()
        for r in range(320, 0, -40):
            alpha = max(0, int(18 - r // 20))
            s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (0, 120, 80, alpha), (r, r), r)
            target.blit(s, (W // 2 - r, H // 2 - r))
        for bx, by, bw, speed in self._bamboo:
            sway = int(math.sin(t * speed + bx) * 4)
            pygame.draw.rect(target, (20, 45, 25), (bx + sway - bw//2, 0, bw, by + 60))
            for node_y in range(0, by + 60, 30):
                pygame.draw.line(target, (30, 60, 35),
                                 (bx + sway - bw//2, node_y), (bx + sway + bw//2, node_y), 2)
        fog = pygame.Surface((W, 80), pygame.SRCALPHA)
        for fy in range(80):
            alpha = int(40 * (1 - fy / 80))
            pygame.draw.line(fog, (0, 200, 120, alpha), (0, fy), (W, fy))
        target.blit(fog, (0, H - 80))

    # ── MENU ──────────────────────────────────────────────────────────────────
    def draw_menu(self, current_level=1):
        self._draw_dojo_bg()
        t = self._elapsed()
        slash_x = int(self.W * 0.5 + math.sin(t * 1.2) * 60)
        pygame.draw.line(self.screen, ACCENT, (slash_x - 220, 88), (slash_x + 220, 72), 3)

        pulse = self._pulse(0.8, 0.88, 1.0)
        tc = tuple(int(c * pulse) for c in ACCENT)
        self._draw_text("⚡ RehabSlash", self.font_xl, tc, self.W // 2, 110)
        self._draw_text("Vision-Based Gamified Upper-Limb Rehabilitation",
                        self.font_sm, GRAY, self.W // 2, 168)

        self._draw_panel((self.W // 2 - 310, 200, 620, 290), PANEL2, ACCENT, 16)
        legends = [
            ("↑  Raise hand above shoulder", "Shoulder Flexion",     ACCENT),
            ("←  Swipe left",               "Horizontal Abduction", GOLD),
            ("→  Swipe right",              "Horizontal Adduction", GOLD),
            ("↻  Tilt wrist",               "Wrist Rotation",       PURPLE),
            ("✦  Pinch thumb + index",       "Fine Motor / Grip",    WARN),
        ]
        for i, (gest, rehab, color) in enumerate(legends):
            y = 218 + i * 50
            self._draw_text(gest,         self.font_sm, color, self.W // 2 - 270, y, "left")
            self._draw_text(f"→ {rehab}", self.font_xs, GRAY,  self.W // 2 + 10,  y, "left")

        self._draw_panel((self.W // 2 - 190, 510, 380, 52), (30, 10, 10), WARN, 12)
        self._draw_text("🍉  FRUIT NINJA REHAB MODE  🍉", self.font_sm, WARN, self.W // 2, 536)

        blink = self._pulse(1.5, 0.3, 1.0)
        c = tuple(int(ch * blink) for ch in WHITE)
        self._draw_text("[ PRESS ENTER TO VIEW WEEK PLAN ]", self.font_md, c, self.W // 2, 600)
        self._draw_text("ESC to quit  |  Webcam required for gesture control",
                        self.font_xs, GRAY, self.W // 2, 640)
        self._draw_text("IEEE POC — RehabSlash 2025", self.font_xs, GOLD,
                        self.W - 10, self.H - 18, "right")

    # ── LEVEL SELECT ─────────────────────────────────────────────────────────
    def draw_level_select(self, progress, next_day, selected_day=None, mouse_pos=None):
        self._draw_dojo_bg()
        self._draw_text("WEEK PLAN — 7 DAYS", self.font_lg, GOLD, self.W//2, 70)
        self._draw_text("Complete each day to unlock the next", self.font_sm, GRAY, self.W//2, 110)

        # Progress bar
        done_count = sum(1 for d in progress if d)
        bar_w = 520
        bar_h = 16
        bx = (self.W - bar_w) // 2
        by = 130
        pygame.draw.rect(self.screen, (25, 35, 55), (bx, by, bar_w, bar_h), 0, border_radius=8)
        fill_w = int(bar_w * (done_count / 7.0))
        pygame.draw.rect(self.screen, ACCENT, (bx, by, fill_w, bar_h), 0, border_radius=8)
        self._draw_text(f"{done_count}/7 Days Complete", self.font_xs, GRAY, self.W//2, by + 26)

        box_w, box_h = 150, 120
        gap = 24
        start_x = (self.W - (box_w * 4 + gap * 3)) // 2
        start_y = 170

        self.last_level_boxes = []
        hover_locked = False
        for i in range(7):
            day = i + 1
            row = 0 if i < 4 else 1
            col = i if i < 4 else i - 4
            x = start_x + col * (box_w + gap)
            y = start_y + row * (box_h + gap)

            done = progress[i]
            is_next = (day == next_day)
            is_selected = (selected_day == day)
            is_locked = (not done) and (not is_next)
            is_hover = False
            if mouse_pos:
                mx, my = mouse_pos
                if x <= mx <= x + box_w and y <= my <= y + box_h:
                    is_hover = True
                    if is_locked:
                        hover_locked = True

            border = ACCENT if is_next else (GOLD if done else GRAY)
            if is_selected:
                border = GOLD
            if is_hover and not is_locked:
                border = WHITE
            fill = (20, 30, 60) if not done else (10, 40, 30)
            self._draw_panel((x, y, box_w, box_h), fill, border, 12)
            self._draw_text(f"DAY {day}", self.font_sm, WHITE, x + box_w//2, y + 34)
            if done:
                self._draw_text("✓ DONE", self.font_sm, ACCENT, x + box_w//2, y + 70)
            elif is_next:
                self._draw_text("START", self.font_sm, GOLD, x + box_w//2, y + 70)
            else:
                self._draw_text("LOCKED", self.font_xs, GRAY, x + box_w//2, y + 70)

            self.last_level_boxes.append({
                "day": day,
                "rect": (x, y, box_w, box_h),
                "done": done,
                "is_next": is_next,
            })

        if next_day is None:
            self._draw_text("WEEK COMPLETE", self.font_md, ACCENT, self.W//2, self.H - 120)
        else:
            self._draw_text("[ ENTER ] Start selected day", self.font_sm, WHITE, self.W//2, self.H - 120)
        self._draw_text("[ ESC ] Back", self.font_sm, GRAY, self.W//2, self.H - 80)

        if hover_locked:
            self._draw_panel((self.W//2 - 280, self.H - 170, 560, 36), PANEL, WARN, 8)
            self._draw_text("Day locked — complete previous day first.",
                            self.font_xs, WARN, self.W//2, self.H - 152)

    # ── GAME ──────────────────────────────────────────────────────────────────
    def draw_game(self, engine, cam_surface, hand_data, demo_mode, dt=0.016):
        # Left panel background
        self.screen.fill((6, 9, 20))
        self._draw_left_panel(cam_surface, hand_data, demo_mode)

        # Right panel (game surface)
        surf = self.game_surface
        self._draw_dojo_bg(surface=surf, W=self.game_w, H=self.game_h)

        for sp in self.splatters:
            sp.update(dt)
            sp.draw(surf)
        self.splatters = [sp for sp in self.splatters if sp.alive]

        # Spawn splatters for newly sliced fruits
        for fruit in engine.fruits:
            fid = id(fruit)
            if fruit.sliced and fid not in self._sliced_ids:
                self._sliced_ids.add(fid)
                self.splatters.append(JuiceSplatter(fruit.x, fruit.y, fruit.color))

        zone = pygame.Surface((self.game_w, 110), pygame.SRCALPHA)
        zone.fill((0, 240, 180, 8))
        surf.blit(zone, (0, 0))
        self._draw_text("▲ RAISE ZONE", self.font_xs, ACCENT, 68, 10, "left", surface=surf)

        for fruit in engine.fruits:
            self._draw_fruit(fruit, surface=surf)

        if hand_data:
            if hand_data.get("hands"):
                for h in hand_data["hands"]:
                    nx, ny = h["index_tip_norm"]
                    self.blade.add(int(nx * self.game_w), int(ny * self.game_h))
            elif hand_data.get("index_tip_norm"):
                nx, ny = hand_data["index_tip_norm"]
                self.blade.add(int(nx * self.game_w), int(ny * self.game_h))
        self.blade.update()
        self.blade.draw(surf)

        self._draw_popups(engine, surface=surf)
        self._draw_hud(engine, surface=surf)

        if engine.level_up_timer > 0:
            self._draw_level_up(engine.level, surface=surf)

        if engine.misses > 0:
            self._draw_miss_vignette(engine.misses, surface=surf)

        # Blit game to right half and draw divider
        self.screen.blit(surf, (self.game_x, 0))
        pygame.draw.line(self.screen, ACCENT, (self.game_x, 0), (self.game_x, self.H), 2)

    def _draw_fruit(self, fruit, surface=None):
        target = surface if surface is not None else self.screen
        if fruit.sliced:
            if fruit.slice_timer < 0.5:
                offset = int(fruit.slice_timer * 130)
                r = fruit.radius
                ix, iy = int(fruit.x), int(fruit.y)
                half_c = tuple(max(0, c - 40) for c in fruit.color)
                flesh  = tuple(min(255, c + 60) for c in fruit.color)
                pygame.draw.ellipse(target, half_c, (ix - r - offset, iy - r//2, r, r))
                pygame.draw.ellipse(target, half_c, (ix + offset,     iy - r//2, r, r))
                pygame.draw.ellipse(target, flesh,  (ix - r - offset + 4, iy - r//2 + 4, r - 8, r - 8))
                pygame.draw.ellipse(target, flesh,  (ix + offset + 4,     iy - r//2 + 4, r - 8, r - 8))
            return

        ix, iy = int(fruit.x), int(fruit.y)
        r = fruit.radius

        # Shadow
        shadow = pygame.Surface((r*2+10, r*2+10), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 55), (5, 10, r*2, r+10))
        target.blit(shadow, (ix - r - 2, iy - r + 5))

        # Body + shading
        pygame.draw.circle(target, fruit.color, (ix, iy), r)
        dark = tuple(max(0, c - 60) for c in fruit.color)
        pygame.draw.circle(target, dark,        (ix + r//5, iy + r//5), r - 2)
        pygame.draw.circle(target, fruit.color, (ix, iy), r - 3)

        # Highlight
        highlight = tuple(min(255, c + 90) for c in fruit.color)
        pygame.draw.ellipse(target, highlight, (ix - r//2, iy - r//2, r//2, r//3))
        pygame.draw.circle(target, (255, 255, 255), (ix - r//3, iy - r//3), max(2, r//6))

        # Gesture icon
        icons = {"raise": "↑", "swipe_left": "←", "swipe_right": "→",
                 "wrist_rot": "↻", "pinch": "✦"}
        icon = icons.get(fruit.required_gesture, "")
        font = pygame.font.SysFont("segoeui", 16, bold=True)
        txt  = font.render(icon, True, (255, 255, 255))
        target.blit(txt, (ix - txt.get_width()//2, iy - r - 20))

    def _draw_hud(self, engine, surface=None):
        target = surface if surface is not None else self.screen
        W = self.game_w if surface is not None else self.W
        H = self.game_h if surface is not None else self.H
        bar = pygame.Surface((W, 58), pygame.SRCALPHA)
        bar.fill((4, 6, 18, 210))
        target.blit(bar, (0, 0))
        pygame.draw.line(target, ACCENT, (0, 57), (W, 57), 1)

        self._draw_text(f"SCORE  {engine.score:>6}", self.font_md, GOLD,   120, 28, surface=target)
        lvl_c = WARN if engine.level >= 4 else ACCENT
        self._draw_text(f"LEVEL  {engine.level}",    self.font_md, lvl_c,  300, 28, surface=target)
        acc = engine.sliced_count / max(1, engine.total_spawned) * 100
        self._draw_text(f"ACC  {acc:>5.1f}%",        self.font_md, WHITE,  460, 28, surface=target)
        combo_c = GOLD if engine.combo > 2 else WHITE
        self._draw_text(f"COMBO  x{engine.combo}",   self.font_md, combo_c, 620, 28, surface=target)

        for i in range(MAX_MISSES):
            alive = i < (MAX_MISSES - engine.misses)
            color = WARN if alive else (35, 35, 55)
            pygame.draw.line(target, color,
                             (W - 195 + i*34, 18), (W - 185 + i*34, 38), 4)
            pygame.draw.circle(target, color, (W - 195 + i*34, 16), 5)

        bot = pygame.Surface((W, 38), pygame.SRCALPHA)
        bot.fill((4, 6, 18, 190))
        target.blit(bot, (0, H - 38))
        pygame.draw.line(target, GRAY, (0, H - 38), (W, H - 38), 1)
        stats = engine.get_stats()
        bar_txt = (f"Reps: {engine.sliced_count}  |  Time: {stats['duration_sec']:.0f}s  |  "
                   f"ROM avg: {stats['avg_rom_deg']:.1f}°  |  "
                   f"Max Combo: {engine.max_combo}  |  Misses: {engine.misses}/{MAX_MISSES}")
        self._draw_text(bar_txt, self.font_xs, GRAY, W//2, H - 19, surface=target)

    def _draw_popups(self, engine, surface=None):
        target = surface if surface is not None else self.screen
        font = self.font_md
        for x, y, t, color, txt in engine.score_popups:
            surf = font.render(txt, True, color)
            if "!" in txt:
                big = pygame.transform.scale(surf, (surf.get_width()+20, surf.get_height()+10))
                target.blit(big, (int(x) - big.get_width()//2, int(y)))
            else:
                target.blit(surf, (int(x) - surf.get_width()//2, int(y)))

    def _draw_miss_vignette(self, misses, surface=None):
        target = surface if surface is not None else self.screen
        W = self.game_w if surface is not None else self.W
        H = self.game_h if surface is not None else self.H
        intensity = min(60, misses * 12)
        vign = pygame.Surface((W, H), pygame.SRCALPHA)
        for edge in range(30):
            a = int(intensity * (1 - edge / 30))
            pygame.draw.rect(vign, (255, 40, 40, a),
                             (edge, edge, W - edge*2, H - edge*2), 1)
        target.blit(vign, (0, 0))

    def _draw_left_panel(self, cam_surface, hand_data, demo_mode):
        left_w = self.game_x if self.game_x > 0 else self.W // 2
        panel = pygame.Surface((left_w, self.H), pygame.SRCALPHA)
        panel.fill((10, 14, 28, 255))
        self.screen.blit(panel, (0, 0))

        # Camera frame
        if cam_surface:
            cw, ch = cam_surface.get_width(), cam_surface.get_height()
            scale = min(left_w / cw, (self.H - 120) / ch)
            tw, th = int(cw * scale), int(ch * scale)
            cam_scaled = pygame.transform.smoothscale(cam_surface, (tw, th))
            cx = (left_w - tw) // 2
            cy = (self.H - th) // 2
            self._draw_panel((cx - 6, cy - 26, tw + 12, th + 52), PANEL, ACCENT, 10)
            self.screen.blit(cam_scaled, (cx, cy))
            self._draw_text("CAMERA FEED", self.font_xs, ACCENT, cx, cy - 10, "left")
        elif demo_mode:
            self._draw_panel((20, self.H//2 - 40, left_w - 40, 80), PANEL, WARN, 10)
            self._draw_text("DEMO MODE — Mouse control", self.font_sm, WARN, left_w//2, self.H//2)

        # Hand status
        if hand_data:
            nh = hand_data.get("num_hands", 0)
            label = "BILATERAL" if hand_data.get("bilateral") else "SINGLE"
            status = f"Hands: {nh}  ({label})" if nh else "Hands: 0"
            self._draw_text(status, self.font_xs, GRAY, 16, 20, "left")
            if hand_data.get("gesture"):
                g   = hand_data["gesture"]
                rom = hand_data.get("rom_degrees", 0)
                self._draw_text(f"Gesture: {g}  |  ROM {rom:.1f}°",
                                self.font_xs, GOLD, 16, 44, "left")

    def _draw_demo_badge(self):
        self._draw_panel((10, self.H - 56, 280, 34), PANEL, WARN, 8)
        self._draw_text("⚠ DEMO MODE — Mouse control", self.font_xs, WARN, 150, self.H - 39)

    def _draw_level_up(self, level, surface=None):
        target = surface if surface is not None else self.screen
        W = self.game_w if surface is not None else self.W
        H = self.game_h if surface is not None else self.H
        t = self._elapsed()
        s = pygame.Surface((540, 90), pygame.SRCALPHA)
        s.fill((255, 180, 0, 25))
        target.blit(s, (W//2 - 270, H//2 - 45))
        pygame.draw.rect(target, GOLD,
                         (W//2 - 270, H//2 - 45, 540, 90), 3, border_radius=14)
        self._draw_text(f"⚔  LEVEL {level} UNLOCKED!  ⚔", self.font_lg, GOLD,
                        W//2, H//2, surface=target)

    # ── PAUSE ─────────────────────────────────────────────────────────────────
    def draw_pause(self):
        s = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        s.fill((0, 0, 0, 150))
        self.screen.blit(s, (0, 0))
        self._draw_panel((self.W//2 - 220, self.H//2 - 65, 440, 130), PANEL2, ACCENT, 18)
        self._draw_text("⏸  PAUSED", self.font_lg, WHITE, self.W//2, self.H//2 - 16)
        self._draw_text("ESC to resume", self.font_sm, GRAY, self.W//2, self.H//2 + 30)

    # ── RESULTS ───────────────────────────────────────────────────────────────
    def draw_results(self, stats, level):
        self._draw_dojo_bg()
        self._draw_text("⚔  SESSION COMPLETE  ⚔", self.font_xl, GOLD, self.W//2, 70)
        self._draw_text("Rehabilitation Outcome Summary", self.font_sm, GRAY, self.W//2, 132)

        cards = [
            ("SCORE",         str(stats["score"]),             GOLD),
            ("LEVEL REACHED", str(stats["level_reached"]),     ACCENT),
            ("ACCURACY",      f"{stats['accuracy_pct']}%",     ACCENT),
            ("REPS DONE",     str(stats["sliced"]),            WHITE),
            ("MAX COMBO",     f"x{stats['max_combo']}",        GOLD),
            ("SESSION TIME",  f"{stats['duration_sec']:.0f}s", WHITE),
            ("AVG ROM",       f"{stats['avg_rom_deg']:.1f}°",  PURPLE),
            ("MISSES",        str(stats["missed"]),            WARN),
        ]
        cols, card_w, card_h = 4, 268, 104
        sx = (self.W - cols * card_w - (cols-1)*14) // 2
        sy = 168
        for i, (label, value, color) in enumerate(cards):
            col, row = i % cols, i // cols
            x = sx + col * (card_w + 14)
            y = sy + row * (card_h + 14)
            self._draw_panel((x, y, card_w, card_h), PANEL2, color, 12)
            self._draw_text(value, self.font_lg, color, x + card_w//2, y + 40)
            self._draw_text(label, self.font_xs, GRAY,  x + card_w//2, y + 78)

        if stats.get("gesture_counts"):
            gy = sy + 2 * (card_h + 14) + 18
            self._draw_panel((self.W//2 - 400, gy, 800, 78), PANEL, ACCENT, 12)
            self._draw_text("GESTURE BREAKDOWN", self.font_xs, GRAY, self.W//2, gy + 12)
            icons = {"raise":"↑","swipe_left":"←","swipe_right":"→","wrist_rot":"↻","pinch":"✦"}
            gx = self.W//2 - 360
            for gesture, count in stats["gesture_counts"].items():
                icon = icons.get(gesture, "")
                self._draw_text(f"{icon} {gesture}: {count}", self.font_sm, ACCENT, gx, gy+50, "left")
                gx += 175

        acc = stats["accuracy_pct"]
        if acc >= 80:
            feedback, fc = "Excellent motor control! ROM targets consistently achieved.", ACCENT
        elif acc >= 60:
            feedback, fc = "Good progress. Continue daily sessions to improve ROM.", GOLD
        else:
            feedback, fc = "Keep practicing — consistency builds neuromuscular pathways.", WARN

        fy = self.H - 120
        self._draw_panel((self.W//2 - 420, fy, 840, 50), PANEL, fc, 10)
        self._draw_text(f"Clinical Note: {feedback}", self.font_xs, fc, self.W//2, fy + 25)
        self._draw_text("[ ENTER ] New Session    [ R ] Replay    [ ESC ] Quit",
                        self.font_sm, WHITE, self.W//2, self.H - 46)
        self._draw_text("[ P ] Print Report", self.font_sm, ACCENT, self.W//2, self.H - 16)
