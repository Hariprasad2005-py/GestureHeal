"""
modules/game_engine.py
Core game logic: fruit spawning, slicing, progressive difficulty, metrics.

Gesture → Game action mapping:
  raise       → cut fruits in upper zone  (shoulder flexion)
  swipe_left  → cut fruits moving left    (horizontal abduction)
  swipe_right → cut fruits moving right   (horizontal adduction)
  wrist_rot   → cut rotating fruits       (wrist rotation)
  open_hand   → pause / shield activation
  pinch       → grab / precision target
"""

import random
import math
import time
import pygame
import numpy as np


# ─── Difficulty Configuration ─────────────────────────────────────────────────
DIFFICULTY_TABLE = {
    # level: (spawn_rate, speed_mult, target_height, required_gesture)
    1: {"spawn_interval": 2.5, "speed": 180, "fruits_to_level": 8,  "gestures": ["raise"]},
    2: {"spawn_interval": 2.0, "speed": 220, "fruits_to_level": 10, "gestures": ["raise", "swipe_left", "swipe_right"]},
    3: {"spawn_interval": 1.6, "speed": 270, "fruits_to_level": 12, "gestures": ["raise", "swipe_left", "swipe_right", "wrist_rot"]},
    4: {"spawn_interval": 1.3, "speed": 320, "fruits_to_level": 15, "gestures": ["raise", "swipe_left", "swipe_right", "wrist_rot", "pinch"]},
    5: {"spawn_interval": 1.0, "speed": 370, "fruits_to_level": 20, "gestures": ["raise", "swipe_left", "swipe_right", "wrist_rot", "pinch"]},
}
MAX_LEVEL = 5
MISS_PENALTY = 3   # score deducted per missed fruit
MAX_MISSES   = 5   # lives


# ─── Fruit Object ─────────────────────────────────────────────────────────────
class Fruit:
    TYPES = [
        {"name": "watermelon", "color": (60, 200, 80),  "radius": 38, "points": 10, "gesture": "raise"},
        {"name": "orange",     "color": (255, 150, 30), "radius": 30, "points": 15, "gesture": "swipe_right"},
        {"name": "lemon",      "color": (240, 220, 40), "radius": 26, "points": 15, "gesture": "swipe_left"},
        {"name": "cherry",     "color": (220, 40, 80),  "radius": 20, "points": 25, "gesture": "wrist_rot"},
        {"name": "star",       "color": (255, 200, 50), "radius": 24, "points": 30, "gesture": "pinch"},
    ]

    def __init__(self, x, y, vx, vy, ftype):
        self.x      = float(x)
        self.y      = float(y)
        self.vx     = float(vx)
        self.vy     = float(vy)
        self.radius = ftype["radius"]
        self.color  = ftype["color"]
        self.name   = ftype["name"]
        self.points = ftype["points"]
        self.required_gesture = ftype["gesture"]
        self.sliced = False
        self.missed = False
        self.rotation = random.uniform(0, 360)
        self.rot_speed= random.uniform(-120, 120)  # deg/sec
        self.alpha   = 255
        self.slice_timer = 0.0
        # Slice effect particles
        self.particles = []

    def update(self, dt, gravity=380):
        if self.sliced:
            self.slice_timer += dt
            self.alpha = max(0, 255 - int(self.slice_timer * 500))
            for p in self.particles:
                p["x"] += p["vx"] * dt
                p["y"] += p["vy"] * dt
                p["vy"] += gravity * 0.5 * dt
                p["life"] -= dt
            self.particles = [p for p in self.particles if p["life"] > 0]
            return

        self.x  += self.vx * dt
        self.y  += self.vy * dt
        self.vy += gravity * dt
        self.rotation += self.rot_speed * dt

    def spawn_particles(self):
        for _ in range(12):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(80, 250)
            self.particles.append({
                "x": self.x, "y": self.y,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed - 100,
                "life": random.uniform(0.3, 0.7),
                "color": self.color,
                "radius": random.randint(3, 8),
            })

    def draw(self, surface):
        if self.sliced:
            # Draw particles
            for p in self.particles:
                a = max(0, int(p["life"] * 500))
                c = (*p["color"][:3],)
                try:
                    pygame.draw.circle(surface, c, (int(p["x"]), int(p["y"])), p["radius"])
                except:
                    pass
            return

        # Draw fruit body with rotation glow
        ix, iy = int(self.x), int(self.y)
        # Shadow
        pygame.draw.circle(surface, (0,0,0,60), (ix+4, iy+4), self.radius)
        # Body
        pygame.draw.circle(surface, self.color, (ix, iy), self.radius)
        # Shine highlight
        highlight = tuple(min(255, c + 80) for c in self.color)
        pygame.draw.circle(surface, highlight, (ix - self.radius//3, iy - self.radius//3), self.radius//4)
        # Border
        pygame.draw.circle(surface, (255,255,255), (ix, iy), self.radius, 2)

        # Draw required gesture indicator (small icon)
        self._draw_gesture_icon(surface, ix, iy)

    def _draw_gesture_icon(self, surface, ix, iy):
        """Small indicator showing which gesture is needed."""
        icons = {
            "raise":       "↑",
            "swipe_left":  "←",
            "swipe_right": "→",
            "wrist_rot":   "↻",
            "pinch":       "✦",
        }
        icon = icons.get(self.required_gesture, "")
        font = pygame.font.SysFont("segoeui", 14, bold=True)
        txt  = font.render(icon, True, (255, 255, 255))
        surface.blit(txt, (ix - txt.get_width()//2, iy - self.radius - 18))


# ─── Slice Trail ──────────────────────────────────────────────────────────────
class SliceTrail:
    def __init__(self):
        self.points = []   # [(x, y, time)]
        self.duration = 0.18

    def add_point(self, x, y):
        self.points.append((x, y, time.time()))

    def update(self):
        now = time.time()
        self.points = [(x, y, t) for x, y, t in self.points if now - t < self.duration]

    def draw(self, surface):
        if len(self.points) < 2:
            return
        now = time.time()
        for i in range(1, len(self.points)):
            x1, y1, t1 = self.points[i-1]
            x2, y2, t2 = self.points[i]
            age  = now - t2
            alpha= max(0, 1 - age / self.duration)
            width= max(1, int(8 * alpha))
            color= (int(0 + 255*alpha), int(240*alpha), int(180*alpha))
            pygame.draw.line(surface, color, (int(x1), int(y1)), (int(x2), int(y2)), width)


# ─── Game Engine ──────────────────────────────────────────────────────────────
class GameEngine:
    def __init__(self, width, height):
        self.W = width
        self.H = height
        self.reset()

    def reset(self, start_level=1, lock_level=False):
        self.fruits       = []
        self.score        = 0
        self.level        = max(1, min(MAX_LEVEL, int(start_level)))
        self.lock_level   = bool(lock_level)
        self.misses       = 0
        self.sliced_count = 0
        self.total_spawned= 0
        self.session_start= time.time()
        self.spawn_timer  = 0.0
        self.slice_trail  = SliceTrail()
        self.combo        = 0
        self.max_combo    = 0
        self.rom_readings = []
        self.gestures_done= []
        self.score_popups = []   # [(x, y, text, timer, color)]
        self.level_up_timer = 0.0
        self.fruits_this_level = 0
        self._prev_hand_pos = {}
        self.slice_events = []
        self.recent_outcomes = []
        self.last_adaptive_acc = 0.0

    def update(self, dt, hands=None):
        """
        dt       : delta time in seconds
        hands    : list of dicts [{pos:(x,y), gesture:str, rom:float}]
        Returns "GAME_OVER" when lives exhausted, else None.
        """
        if hands is None:
            hands = []

        cfg = DIFFICULTY_TABLE.get(self.level, DIFFICULTY_TABLE[MAX_LEVEL])
        adaptive_factor = self._adaptive_factor()
        spawn_interval = max(0.6, cfg["spawn_interval"] / adaptive_factor)
        speed = cfg["speed"] * adaptive_factor

        # ── Spawn fruits ──
        self.spawn_timer += dt
        if self.spawn_timer >= spawn_interval:
            self.spawn_timer = 0.0
            self._spawn_fruit(cfg, speed)

        # ── Update slice trail ──
        if hands:
            px = int(hands[0]["pos"][0] * self.W)
            py = int(hands[0]["pos"][1] * self.H)
            self.slice_trail.add_point(px, py)
        self.slice_trail.update()

        # ── Update fruits ──
        for fruit in self.fruits:
            fruit.update(dt)

        # ── Collision: hand tip vs fruits ──
        for idx, h in enumerate(hands):
            if h.get("pos") and h.get("gesture"):
                self._check_slice(h["pos"], h["gesture"], h.get("rom", 0.0), hand_id=idx)

        # ── Remove off-screen fruits (missed) ──
        new_fruits = []
        for f in self.fruits:
            if not f.sliced and f.y > self.H + 60:
                self.misses += 1
                self.combo   = 0
                self._record_outcome(False)
            elif f.sliced and f.slice_timer > 1.0:
                pass  # remove
            else:
                new_fruits.append(f)
        self.fruits = new_fruits

        # ── Update popups ──
        self.score_popups = [
            (x, y - 40*dt, t, c, txt)
            for (x, y, t, c, txt) in self.score_popups
            if t - dt > 0
        ]
        self.score_popups = [(x, y, t - dt, c, txt) for x, y, t, c, txt in self.score_popups]
        self.score_popups = [p for p in self.score_popups if p[2] > 0]

        # ── Level up? ──
        if self.level_up_timer > 0:
            self.level_up_timer -= dt
        if (not self.lock_level) and self.fruits_this_level >= cfg["fruits_to_level"] and self.level < MAX_LEVEL:
            self.level += 1
            self.fruits_this_level = 0
            self.level_up_timer = 2.0

        # ── Game over? ──
        if self.misses >= MAX_MISSES:
            return "GAME_OVER"

        return None

    def _spawn_fruit(self, cfg, speed):
        """Spawn a fruit from above with downward velocity."""
        gestures_available = cfg["gestures"]

        # Pick fruit type matching one of available gestures
        matching = [f for f in Fruit.TYPES if f["gesture"] in gestures_available]
        if not matching:
            matching = Fruit.TYPES
        ftype = random.choice(matching)

        # Spawn from top with slight horizontal drift
        x  = random.randint(60, self.W - 60)
        y  = -40
        vx = random.uniform(-80, 80)
        vy = speed * random.uniform(0.7, 1.1)

        self.fruits.append(Fruit(x, y, vx, vy, ftype))
        self.total_spawned += 1

    def _check_slice(self, hand_pos, gesture, rom_deg=0.0, hand_id=0):
        """
        Fruit Ninja style: ANY swipe movement near a fruit cuts it.
        Uses both proximity AND sweep-line check for fast movement.
        """
        hx = hand_pos[0] * self.W
        hy = hand_pos[1] * self.H

        is_slashing = gesture in ("swipe_left", "swipe_right")
        for fruit in self.fruits:
            if fruit.sliced:
                continue

            # Method 1: Hand tip inside fruit + gesture active
            dist = math.dist((hx, hy), (fruit.x, fruit.y))
            if dist < fruit.radius * 2.5 and is_slashing:
                self._slice_fruit(fruit, hx, hy, gesture, rom_deg)
                continue

            # Method 2: Sweep line — swipe path crosses fruit this frame
            prev = self._prev_hand_pos.get(hand_id)
            if prev and is_slashing:
                px_prev = prev[0] * self.W
                py_prev = prev[1] * self.H
                move_dist = math.dist((px_prev, py_prev), (hx, hy))
                if move_dist > 15:
                    if self._segment_hits_fruit(px_prev, py_prev, hx, hy, fruit):
                        self._slice_fruit(fruit, hx, hy, gesture, rom_deg)

        self._prev_hand_pos[hand_id] = hand_pos

    def _segment_hits_fruit(self, x1, y1, x2, y2, fruit):
        """Check if hand sweep line passes through fruit circle."""
        fx, fy, r = fruit.x, fruit.y, fruit.radius * 2.2
        dx, dy = x2 - x1, y2 - y1
        fx1, fy1 = fx - x1, fy - y1
        seg_len_sq = dx*dx + dy*dy
        if seg_len_sq == 0:
            return math.dist((x1, y1), (fx, fy)) < r
        t = max(0.0, min(1.0, (fx1*dx + fy1*dy) / seg_len_sq))
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy
        return math.dist((closest_x, closest_y), (fx, fy)) < r

    def _slice_fruit(self, fruit, hx, hy, gesture="swipe_right", rom_deg=0.0):
        fruit.sliced = True
        fruit.spawn_particles()

        # Combo bonus
        self.combo += 1
        self.max_combo = max(self.max_combo, self.combo)
        combo_mult = 1 + (self.combo - 1) * 0.5
        points = int(fruit.points * combo_mult)

        self.score       += points
        self.sliced_count+= 1
        self.fruits_this_level += 1
        self.gestures_done.append(fruit.required_gesture)
        self.rom_readings.append(float(rom_deg))
        self._record_outcome(True)
        self.slice_events.append({
            "gesture": gesture,
            "rom_deg": float(rom_deg),
        })

        # Popup
        color = (255, 200, 50) if self.combo > 2 else (0, 240, 180)
        label = f"+{points}" if self.combo <= 1 else f"+{points} x{self.combo:.0f}!"
        self.score_popups.append((hx, hy, 1.2, color, label))

    def get_stats(self):
        duration = time.time() - self.session_start
        accuracy = (self.sliced_count / max(1, self.total_spawned)) * 100
        gesture_counts = {}
        for g in self.gestures_done:
            gesture_counts[g] = gesture_counts.get(g, 0) + 1
        avg_rom = float(np.mean(self.rom_readings)) if self.rom_readings else 0.0

        return {
            "score"          : self.score,
            "level_reached"  : self.level,
            "sliced"         : self.sliced_count,
            "missed"         : self.misses,
            "total_spawned"  : self.total_spawned,
            "accuracy_pct"   : round(accuracy, 1),
            "max_combo"      : self.max_combo,
            "duration_sec"   : round(duration, 1),
            "gesture_counts" : gesture_counts,
            "avg_rom_deg"    : round(avg_rom, 1),
        }

    def pop_slice_events(self):
        """Return and clear slice events for external logging."""
        events = self.slice_events[:]
        self.slice_events = []
        return events

    def _adaptive_factor(self):
        """Compute a gentle multiplier based on recent success rate."""
        if len(self.recent_outcomes) < 5:
            return 1.0
        acc = sum(self.recent_outcomes) / max(1, len(self.recent_outcomes))
        self.last_adaptive_acc = acc * 100.0
        factor = 1.0 + (acc - 0.6) * 0.6
        return max(0.85, min(1.2, factor))

    def _record_outcome(self, success):
        self.recent_outcomes.append(1 if success else 0)
        if len(self.recent_outcomes) > 10:
            self.recent_outcomes.pop(0)

        # Adaptive level change based on rolling success
        if (not self.lock_level) and len(self.recent_outcomes) >= 8:
            acc = sum(self.recent_outcomes) / len(self.recent_outcomes)
            if acc >= 0.85 and self.level < MAX_LEVEL:
                self.level += 1
                self.fruits_this_level = 0
                self.level_up_timer = 2.0
                self.recent_outcomes.clear()
            elif acc <= 0.45 and self.level > 1:
                self.level -= 1
                self.fruits_this_level = 0
                self.level_up_timer = 2.0
                self.recent_outcomes.clear()
