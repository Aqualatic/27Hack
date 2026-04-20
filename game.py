import pygame
import math
import random

pygame.init()

WIN_W, WIN_H = 1280, 800
screen = pygame.display.set_mode((WIN_W, WIN_H))
pygame.display.set_caption("Mission Control")
clock = pygame.time.Clock()

# ── fonts ──────────────────────────────────────────────────────────────────────
font_mono_sm = pygame.font.SysFont("consolas", 13)
font_mono_md = pygame.font.SysFont("consolas", 18, bold=True)
font_mono_lg = pygame.font.SysFont("consolas", 28, bold=True)
font_mono_xl = pygame.font.SysFont("consolas", 42, bold=True)

# ── colours ────────────────────────────────────────────────────────────────────
C_ROOM_BG   = (18,  16,  22)
C_DESK      = (28,  24,  32)
C_SCREEN_RIM= (40,  80,  50)
C_GREEN     = (60,  220, 90)
C_GREEN_DIM = (30,  100, 45)
C_AMBER     = (220, 160, 40)
C_RED       = (220, 60,  60)
C_EARTH_SKY = (10,  25,  60)
C_SPACE     = (4,   4,   12)
C_MOON_SKY  = (12,  10,  18)
C_ROCKET    = (200, 200, 210)
C_FLAME     = (255, 140, 30)
C_ASTEROID  = (110, 90,  70)

# ── layout ─────────────────────────────────────────────────────────────────────
SCREEN_X  = 60
SCREEN_Y  = 40
SCREEN_W  = WIN_W - 120
SCREEN_H  = WIN_H - 220
SCREEN_RX = SCREEN_X + SCREEN_W
SCREEN_RY = SCREEN_Y + SCREEN_H

JS_CX  = WIN_W // 2
JS_CY  = WIN_H - 90
JS_R   = 55
KNOB_R = 18

# ── phases ─────────────────────────────────────────────────────────────────────
PHASE_LAUNCH = -1   # pre-launch countdown, rocket sitting still on pad
PHASE_EARTH  =  0   # ascending (moving UP through atmosphere)
PHASE_SLEEP  =  5   # operator-offline transition between zones
PHASE_SPACE  =  1   # coasting sideways through deep space
PHASE_MOON   =  2   # descending toward moon (gravity pulls DOWN)
PHASE_WIN    =  3
PHASE_DEAD   =  4

phase = PHASE_LAUNCH

# ── input queue ────────────────────────────────────────────────────────────────
input_queue = []

# ── rocket state ───────────────────────────────────────────────────────────────
rkt_x     = 0.5    # horizontal world fraction 0..1
rkt_y     = 0.5    # vertical world fraction 0..1  (used in space for dodge)
rkt_vx    = 0.0
rkt_vy    = 0.0    # positive = downward on screen
rkt_angle = 0.0    # degrees, 0 = nose pointing UP
rkt_spin  = 0.0    # deg / sec

# ── physics ────────────────────────────────────────────────────────────────────
GRAVITY_EARTH   = 25.0
GRAVITY_MOON    = 14.0
SPIN_ACCEL      = 130.0   # faster than original (was 60)
MAX_SPIN        = 130.0
SPIN_DAMPING    = 0.82
THRUST_FORCE    = 78.0
MAX_V           = 220.0

# ── progress (0 → 1 across the whole journey) ──────────────────────────────────
progress         = 0.0
EARTH_END        = 0.33
SPACE_END        = 0.66
SPACE_DRIFT_RATE = 0.015   # progress / sec auto-advance in deep space (~22 s crossing)

# ── launch state ───────────────────────────────────────────────────────────────
launch_timer = 4.0          # seconds of countdown before PHASE_EARTH begins

# ── sleep / transition state ───────────────────────────────────────────────────
sleep_timer            = 0.0
SLEEP_DURATION         = 5.0
next_phase_after_sleep = PHASE_SPACE
sleep_from_phase       = PHASE_EARTH

# ── joystick ───────────────────────────────────────────────────────────────────
js_knob_x   = float(JS_CX)
dragging_js = False
steer       = 0.0

# ── thruster — PERSISTENT so booster stays on without constant dial movement ───
thrusting        = False
effective_steer  = 0.0   # last value fired from queue; NOT reset each frame
effective_thrust = False  # last value fired from queue; NOT reset each frame
flame_flicker    = 0.0

# ═══════════════════════════════════════════════════════════════════════════════
# OBSTACLE CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

class EarthObstacle:
    """
    PLACEHOLDER shapes for atmospheric obstacles:
    balloon / kite / drone.
    Replace self.kind drawing blocks with real sprites later.
    """
    _KINDS = ('balloon', 'kite', 'drone')

    def __init__(self):
        self.kind  = random.choice(self._KINDS)
        self.x     = float(SCREEN_W + random.randint(20, 150))
        self.y     = float(random.randint(50, SCREEN_H - 50))
        self.vx    = -random.uniform(45, 105)
        self.vy    = random.uniform(-14, 14)
        self.r     = random.randint(14, 26)
        self.bob   = random.uniform(0, math.tau)
        self.bspd  = random.uniform(1.5, 3.2)
        self.color = random.choice([
            (220, 60, 60), (60, 140, 220), (80, 200, 80),
            (220, 185, 45), (200, 80, 185)])

    def update(self, dt):
        self.x   += self.vx * dt
        self.y   += self.vy * dt + math.sin(self.bob) * 18 * dt
        self.bob += self.bspd * dt

    def draw(self, surf, ox, oy):
        sx, sy = int(ox + self.x), int(oy + self.y)
        r = self.r
        # ── PLACEHOLDER drawing — swap these blocks for real sprites ──────────
        if self.kind == 'balloon':
            pygame.draw.circle(surf, self.color, (sx, sy), r)
            pygame.draw.circle(surf, (255, 255, 255), (sx, sy), r, 2)
            pygame.draw.line(surf, (190, 165, 130),
                             (sx, sy + r), (sx + 2, sy + r + 20), 1)
        elif self.kind == 'kite':
            pts = [(sx, sy - r), (sx + r, sy), (sx, sy + r), (sx - r, sy)]
            pygame.draw.polygon(surf, self.color, pts)
            pygame.draw.polygon(surf, (255, 255, 255), pts, 2)
            pygame.draw.line(surf, (190, 155, 100),
                             (sx - r, sy), (sx + r, sy), 1)
            pygame.draw.line(surf, (190, 155, 100),
                             (sx, sy - r), (sx, sy + r), 1)
        else:   # drone
            pygame.draw.rect(surf, self.color,
                             (sx - r // 2, sy - r // 2, r, r))
            for dx, dy in ((-r, 0), (r, 0), (0, -r), (0, r)):
                pygame.draw.circle(surf, (200, 200, 200),
                                   (sx + dx, sy + dy), r // 3)
                pygame.draw.circle(surf, (240, 240, 240),
                                   (sx + dx, sy + dy), r // 3, 1)

    def off_screen(self): return self.x < -90
    def hit(self, rx, ry, rr=14):
        return math.hypot(self.x - rx, self.y - ry) < self.r + rr


class SpaceObstacle:
    """Asteroid — tumbling rock in deep space."""

    def __init__(self):
        self.x     = float(SCREEN_W + random.randint(20, 130))
        self.y     = float(random.randint(30, SCREEN_H - 30))
        self.vx    = -random.uniform(60, 155)
        self.vy    = random.uniform(-28, 28)
        self.r     = random.randint(10, 28)
        self.angle = random.uniform(0, 360)
        self.spin  = random.uniform(-75, 75)
        self.pts   = []
        for i in range(8):
            a  = i / 8 * math.tau
            rr = self.r * random.uniform(0.66, 1.34)
            self.pts.append((math.cos(a) * rr, math.sin(a) * rr))

    def update(self, dt):
        self.x     += self.vx * dt
        self.y     += self.vy * dt
        self.angle += self.spin * dt

    def draw(self, surf, ox, oy):
        sx, sy = ox + self.x, oy + self.y
        rad    = math.radians(self.angle)
        ca, sa = math.cos(rad), math.sin(rad)
        world  = [(sx + px*ca - py*sa, sy + px*sa + py*ca) for px, py in self.pts]
        if len(world) >= 3:
            pygame.draw.polygon(surf, C_ASTEROID, world)
            pygame.draw.polygon(surf, (140, 120, 100), world, 2)

    def off_screen(self): return self.x < -90
    def hit(self, rx, ry, rr=14):
        return math.hypot(self.x - rx, self.y - ry) < self.r + rr


class MoonObstacle:
    """
    PLACEHOLDER shapes for lunar approach obstacles:
    moon rock / orbital debris.
    Replace drawing blocks with real sprites later.
    """
    _KINDS = ('rock', 'debris')

    def __init__(self):
        self.kind  = random.choice(self._KINDS)
        self.x     = float(SCREEN_W + random.randint(20, 130))
        self.y     = float(random.randint(30, SCREEN_H - 60))
        self.vx    = -random.uniform(50, 125)
        self.vy    = random.uniform(-20, 20)
        self.r     = random.randint(10, 23)
        self.angle = random.uniform(0, 360)
        self.spin  = random.uniform(-55, 55)
        self.color = random.choice([
            (148, 133, 118), (162, 150, 136), (125, 116, 106)])
        # pre-bake irregular rock polygon so it doesn't change each draw call
        self.pts = []
        for i in range(7):
            a  = i / 7 * math.tau
            rr = self.r * random.uniform(0.65, 1.32)
            self.pts.append((math.cos(a) * rr, math.sin(a) * rr))

    def update(self, dt):
        self.x     += self.vx * dt
        self.y     += self.vy * dt
        self.angle += self.spin * dt

    def draw(self, surf, ox, oy):
        sx, sy = int(ox + self.x), int(oy + self.y)
        r      = self.r
        rad    = math.radians(self.angle)
        ca, sa = math.cos(rad), math.sin(rad)
        # ── PLACEHOLDER drawing — swap these blocks for real sprites ──────────
        if self.kind == 'rock':
            world = [(sx + px*ca - py*sa, sy + px*sa + py*ca)
                     for px, py in self.pts]
            if len(world) >= 3:
                pygame.draw.polygon(surf, self.color, world)
                pygame.draw.polygon(surf, (205, 195, 182), world, 2)
        else:   # debris — spinning metal shard placeholder
            hw, hh = r, r // 3
            corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
            world = [(sx + cx*ca - cy*sa, sy + cx*sa + cy*ca)
                     for cx, cy in corners]
            pygame.draw.polygon(surf, self.color, world)
            pygame.draw.polygon(surf, (205, 198, 188), world, 1)

    def off_screen(self): return self.x < -90
    def hit(self, rx, ry, rr=14):
        return math.hypot(self.x - rx, self.y - ry) < self.r + rr


# ── stars (used in space / moon backgrounds) ───────────────────────────────────
stars = [(random.randint(0, SCREEN_W), random.randint(0, SCREEN_H),
          random.uniform(0.4, 1.0)) for _ in range(200)]

# ── obstacle pool ──────────────────────────────────────────────────────────────
obstacles      = []
obstacle_timer = 0.0
OBST_INTERVAL  = 1.8

# ── helpers ────────────────────────────────────────────────────────────────────
def signal_delay(prog):
    return prog * prog * 3.5

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def lerp(a, b, t):
    return a + (b - a) * t


def draw_rocket(surf, cx, cy, angle_deg, thrusting, flicker):
    rad  = math.radians(angle_deg)
    ca, sa = math.cos(rad), math.sin(rad)

    def rot(lx, ly):
        return (cx + lx*ca - ly*sa,
                cy + lx*sa + ly*ca)

    body = [rot(-10,28), rot(10,28), rot(10,-20), rot(0,-38), rot(-10,-20)]
    pygame.draw.polygon(surf, C_ROCKET, body)
    pygame.draw.polygon(surf, (160,160,170), body, 1)

    lfin = [rot(-10,28), rot(-22,38), rot(-10,10)]
    rfin = [rot( 10,28), rot( 22,38), rot( 10,10)]
    pygame.draw.polygon(surf, (160,160,175), lfin)
    pygame.draw.polygon(surf, (160,160,175), rfin)

    wx, wy = rot(0, -10)
    pygame.draw.circle(surf, (100,180,220), (int(wx), int(wy)), 6)
    pygame.draw.circle(surf, (140,210,255), (int(wx), int(wy)), 6, 1)

    if thrusting:
        flen  = 22 + flicker * 14
        fw    = 8  + flicker * 4
        flame = [rot(-fw/2, 30), rot(fw/2, 30), rot(0, 30 + flen)]
        pygame.draw.polygon(surf, (255, int(100 + flicker*80), 20), flame)
        inner = [rot(-fw/4, 30), rot(fw/4, 30), rot(0, 30 + flen*0.5)]
        pygame.draw.polygon(surf, (255, 240, 180), inner)


def draw_screen_overlay(surf):
    for y in range(0, SCREEN_H, 4):
        s = pygame.Surface((SCREEN_W, 2), pygame.SRCALPHA)
        s.fill((0, 0, 0, 30))
        surf.blit(s, (0, y))


def draw_hud(surf, prog, delay, steer_val, thrust_val, ph):
    pygame.draw.rect(surf, (0, 30, 10), (0, 0, SCREEN_W, 24))
    pname = {
        PHASE_LAUNCH: 'PRE-LAUNCH',
        PHASE_EARTH:  'EARTH (↑ ASCENDING)',
        PHASE_SPACE:  'DEEP SPACE (→ COASTING)',
        PHASE_MOON:   'LUNAR APPROACH (↓ DESCENDING)',
        PHASE_SLEEP:  '-- OPERATOR OFFLINE --',
    }.get(ph, '---')
    labels = [
        f"PHASE: {pname}",
        f"PROGRESS: {int(prog*100):3d}%",
        f"SIGNAL: {delay:.1f}s",
        f"STEER: {steer_val:+.2f}",
        f"THRUST: {'ON' if thrust_val else 'OFF'}",
    ]
    x = 8
    for lbl in labels:
        t = font_mono_sm.render(lbl, True, C_GREEN)
        surf.blit(t, (x, 5))
        x += t.get_width() + 22


# ── scene backgrounds ──────────────────────────────────────────────────────────

def draw_earth_bg(surf, prog_local):
    """Earth atmosphere — rocket travelling upward."""
    surf.fill(C_EARTH_SKY)
    # Ground fades as we rise
    ga = int(clamp((1.0 - prog_local * 3) * 255, 0, 255))
    g  = pygame.Surface((SCREEN_W, 70), pygame.SRCALPHA)
    g.fill((20, 85, 30, ga))
    surf.blit(g, (0, SCREEN_H - 70))
    # Launchpad (visible at start)
    if prog_local < 0.10:
        pygame.draw.rect(surf, (82, 82, 92),
                         (SCREEN_W//2 - 36, SCREEN_H - 68, 72, 10))
        pygame.draw.line(surf, (62, 64, 74),
                         (SCREEN_W//2 - 36, SCREEN_H - 68),
                         (SCREEN_W//2 - 50, SCREEN_H - 52), 3)
        pygame.draw.line(surf, (62, 64, 74),
                         (SCREEN_W//2 + 36, SCREEN_H - 68),
                         (SCREEN_W//2 + 50, SCREEN_H - 52), 3)
    # Clouds (fade away as altitude increases)
    random.seed(7)
    for _ in range(6):
        cx = random.randint(50, SCREEN_W - 50)
        cy = random.randint(SCREEN_H // 3, SCREEN_H * 2 // 3)
        alpha = int(clamp((1.0 - prog_local * 4) * 200, 0, 200))
        if alpha > 0:
            cs = pygame.Surface((120, 40), pygame.SRCALPHA)
            pygame.draw.ellipse(cs, (200, 210, 230, alpha), (0, 0, 120, 40))
            surf.blit(cs, (cx - 60, cy - 20))


def draw_space_bg(surf, prog_local, game_t):
    """Deep space — rocket travelling sideways; starfield scrolls right→left."""
    surf.fill(C_SPACE)
    scroll_x = int(game_t * 65) % SCREEN_W
    for sx, sy, br in stars:
        c = int(br * 195 * clamp(prog_local * 5, 0, 1))
        if c > 12:
            pygame.draw.circle(surf, (c, c, c),
                               ((sx - scroll_x) % SCREEN_W, sy), 1)
    # Faint nebula tint deepens
    nb = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    nb.fill((28, 0, 55, int(clamp(prog_local, 0, 1) * 20)))
    surf.blit(nb, (0, 0))


def draw_moon_bg(surf, prog_local):
    """Lunar approach — rocket descending; moon surface rises from below."""
    surf.fill(C_MOON_SKY)
    for sx, sy, br in stars:
        pygame.draw.circle(surf, (int(br*215),)*3, (sx, sy), 1)
    # Surface creeps upward as we descend
    surface_y = int(SCREEN_H * (1.0 - clamp(prog_local * 1.1, 0, 0.88)))
    pygame.draw.rect(surf, (142, 132, 120),
                     (0, max(SCREEN_H - 115, surface_y), SCREEN_W, 120))
    random.seed(13)
    for _ in range(10):
        cx = random.randint(0, SCREEN_W)
        cy = max(SCREEN_H - 104, surface_y) + random.randint(0, 60)
        pygame.draw.circle(surf, (112, 102, 92),
                           (cx, cy), random.randint(8, 22), 3)


def draw_sleep_overlay(surf, t_frac):
    """Black-out with 'operator offline' message during zone transitions."""
    alpha = int(clamp(t_frac * 2.2, 0, 1) * 215)
    s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    s.fill((0, 0, 0, alpha))
    surf.blit(s, (0, 0))
    if t_frac > 0.22:
        fi  = clamp((t_frac - 0.22) / 0.28, 0, 1)
        c_a = tuple(int(c * fi) for c in C_AMBER)
        c_g = tuple(int(c * fi) for c in C_GREEN)
        msg = font_mono_lg.render("OPERATOR OFFLINE", True, c_a)
        surf.blit(msg, (SCREEN_W//2 - msg.get_width()//2, SCREEN_H//2 - 52))
        sub = font_mono_md.render(
            "AUTOPILOT ENGAGED — SIGNAL RESUMING …", True, c_g)
        surf.blit(sub, (SCREEN_W//2 - sub.get_width()//2, SCREEN_H//2 + 8))
        dots = "·" * (int(t_frac * 16) % 16)
        ds   = font_mono_md.render(dots, True, c_a)
        surf.blit(ds, (SCREEN_W//2 - ds.get_width()//2, SCREEN_H//2 + 44))


def draw_launch_overlay(surf, t_frac):
    """Pre-launch countdown overlay."""
    s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    s.fill((0, 0, 0, 178))
    surf.blit(s, (0, 0))
    secs_left = max(0, int((1.0 - t_frac) * 3))
    if secs_left > 0:
        msg = font_mono_xl.render(f"T – {secs_left}", True, C_RED)
    else:
        msg = font_mono_xl.render("LAUNCH!", True, C_GREEN)
    surf.blit(msg, (SCREEN_W//2 - msg.get_width()//2, SCREEN_H//2 - 48))
    sub = font_mono_md.render("HOLD SPACE TO THRUST", True, C_AMBER)
    surf.blit(sub, (SCREEN_W//2 - sub.get_width()//2, SCREEN_H//2 + 18))


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════════════════════
game_time = 0.0
running   = True
ACTIVE    = (PHASE_EARTH, PHASE_SPACE, PHASE_MOON)

while running:
    dt        = clock.tick(60) / 1000.0
    game_time += dt

    # ── events ────────────────────────────────────────────────────────────────
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit(); raise SystemExit

        # Joystick grab — only during active flight phases
        if event.type == pygame.MOUSEBUTTONDOWN and phase in ACTIVE:
            mx, my = event.pos
            if math.hypot(mx - JS_CX, my - JS_CY) <= JS_R + 30:
                dragging_js = True

        if event.type == pygame.MOUSEBUTTONUP and dragging_js:
            dragging_js = False
            js_knob_x   = float(JS_CX)
            input_queue.append(
                (game_time + signal_delay(progress), 0.0, thrusting))

        # SPACE = thruster (no click-to-boost; that has been removed)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            if phase in ACTIVE:
                thrusting = True
                input_queue.append(
                    (game_time + signal_delay(progress), steer, True))

        if event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
            thrusting = False
            input_queue.append(
                (game_time + signal_delay(progress), steer, False))

    # ── launch countdown ──────────────────────────────────────────────────────
    if phase == PHASE_LAUNCH:
        launch_timer -= dt
        if launch_timer <= 0:
            phase  = PHASE_EARTH
            rkt_vx = 0.0
            rkt_vy = -55.0    # initial upward nudge off the pad

    # ── sleep / zone-transition ───────────────────────────────────────────────
    elif phase == PHASE_SLEEP:
        sleep_timer += dt
        if sleep_timer >= SLEEP_DURATION:
            phase       = next_phase_after_sleep
            sleep_timer = 0.0
            obstacles.clear()
            rkt_vx = 0.0
            rkt_vy = 12.0 if next_phase_after_sleep == PHASE_MOON else 0.0

    # ── joystick update ───────────────────────────────────────────────────────
    if dragging_js and phase in ACTIVE:
        raw_x     = pygame.mouse.get_pos()[0]
        js_knob_x = clamp(raw_x, JS_CX - JS_R, JS_CX + JS_R)
        steer     = (js_knob_x - JS_CX) / JS_R
        input_queue.append(
            (game_time + signal_delay(progress), steer, thrusting))
    elif phase in ACTIVE:
        js_knob_x += (JS_CX - js_knob_x) * min(1.0, dt * 14)
        steer      = 0.0

    # ── process input queue ───────────────────────────────────────────────────
    # effective_steer / effective_thrust are PERSISTENT (not reset to defaults).
    # They only change when a queued entry fires.  This fixes the bug where
    # holding Space without moving the dial would drop thrust after one frame.
    remaining = []
    for (apply_at, s, t) in input_queue:
        if game_time >= apply_at:
            effective_steer  = s
            effective_thrust = t
        else:
            remaining.append((apply_at, s, t))
    input_queue[:] = remaining

    # ── rocket physics ────────────────────────────────────────────────────────
    if phase in ACTIVE:
        # Angular control
        rkt_spin += effective_steer * SPIN_ACCEL * dt
        rkt_spin  = clamp(rkt_spin, -MAX_SPIN, MAX_SPIN)
        rkt_spin *= SPIN_DAMPING ** (dt * 60)
        rkt_angle += rkt_spin * dt
        rkt_angle  = clamp(rkt_angle, -80, 80)

        flame_flicker = lerp(flame_flicker, random.random(), 0.4)

        # Thrust in direction nose is pointing
        if effective_thrust:
            rad    = math.radians(rkt_angle)
            rkt_vx +=  math.sin(rad) * THRUST_FORCE * dt
            rkt_vy += -math.cos(rad) * THRUST_FORCE * dt

        # ── Phase-specific gravity / progress ─────────────────────────────────
        if phase == PHASE_EARTH:
            # Gravity pulls down; going UP (negative vy) earns progress
            rkt_vy   += GRAVITY_EARTH * dt
            progress -= rkt_vy * dt / (SCREEN_H * 5)
            rkt_x    += rkt_vx * dt / SCREEN_W
            rkt_x     = clamp(rkt_x, 0.05, 0.95)

        elif phase == PHASE_SPACE:
            # No gravity — ship coasts sideways automatically
            # Player can nudge up/down to dodge asteroids
            progress += SPACE_DRIFT_RATE * dt
            rkt_y    += rkt_vy * dt / SCREEN_H
            rkt_y     = clamp(rkt_y, 0.08, 0.92)
            rkt_x    += rkt_vx * dt / SCREEN_W
            rkt_x     = clamp(rkt_x, 0.08, 0.92)

        elif phase == PHASE_MOON:
            # Moon gravity pulls DOWN; descending earns progress
            rkt_vy   += GRAVITY_MOON * dt
            progress += rkt_vy * dt / (SCREEN_H * 5)
            rkt_x    += rkt_vx * dt / SCREEN_W
            rkt_x     = clamp(rkt_x, 0.05, 0.95)

        rkt_vx   = clamp(rkt_vx, -MAX_V, MAX_V)
        rkt_vy   = clamp(rkt_vy, -MAX_V, MAX_V)
        progress = clamp(progress, 0.0, 1.0)

        # ── Phase transitions (operator "goes to sleep" between zones) ─────────
        if phase == PHASE_EARTH and progress >= EARTH_END:
            phase                  = PHASE_SLEEP
            sleep_timer            = 0.0
            next_phase_after_sleep = PHASE_SPACE
            sleep_from_phase       = PHASE_EARTH
            obstacles.clear()

        elif phase == PHASE_SPACE and progress >= SPACE_END:
            phase                  = PHASE_SLEEP
            sleep_timer            = 0.0
            next_phase_after_sleep = PHASE_MOON
            sleep_from_phase       = PHASE_SPACE
            obstacles.clear()

        elif phase == PHASE_MOON and progress >= 1.0:
            phase = PHASE_WIN

        # ── Obstacles ─────────────────────────────────────────────────────────
        obstacle_timer -= dt
        if obstacle_timer <= 0 and phase in ACTIVE:
            if   phase == PHASE_EARTH: obstacles.append(EarthObstacle())
            elif phase == PHASE_SPACE: obstacles.append(SpaceObstacle())
            elif phase == PHASE_MOON:  obstacles.append(MoonObstacle())
            ivl            = OBST_INTERVAL * (0.65 if phase == PHASE_SPACE else 1.0)
            obstacle_timer = random.uniform(ivl * 0.7, ivl * 1.4)

        for obs in obstacles:
            obs.update(dt)
        obstacles[:] = [o for o in obstacles if not o.off_screen()]

        # ── Collision detection ────────────────────────────────────────────────
        if phase == PHASE_SPACE:
            rkt_sx_c = int(rkt_x * SCREEN_W)
            rkt_sy_c = int(rkt_y * SCREEN_H)
        else:
            rkt_sx_c = int(rkt_x * SCREEN_W)
            rkt_sy_c = SCREEN_H // 2

        for obs in obstacles:
            if obs.hit(rkt_sx_c, rkt_sy_c):
                phase = PHASE_DEAD

    # ═════════════════════════════════════════════════════════════════════════
    # BUILD GAME SURFACE
    # ═════════════════════════════════════════════════════════════════════════
    game_surf = pygame.Surface((SCREEN_W, SCREEN_H))

    # Background + rocket screen position
    if phase == PHASE_LAUNCH:
        draw_earth_bg(game_surf, 0.0)
        rkt_sx, rkt_sy = SCREEN_W // 2, SCREEN_H - 90
        draw_ang       = 0.0

    elif phase == PHASE_EARTH:
        lp = progress / EARTH_END
        draw_earth_bg(game_surf, lp)
        # Rocket rises from pad to centre during the first moments
        rkt_sy  = int(lerp(SCREEN_H - 90, SCREEN_H // 2,
                           clamp(lp * 14, 0, 1)))
        rkt_sx  = int(rkt_x * SCREEN_W)
        draw_ang = rkt_angle

    elif phase == PHASE_SLEEP:
        if   sleep_from_phase == PHASE_EARTH: draw_earth_bg(game_surf, 1.0)
        elif sleep_from_phase == PHASE_SPACE:
            draw_space_bg(game_surf, 1.0, game_time)
        else:
            draw_moon_bg(game_surf, 0.0)
        rkt_sx  = int(rkt_x * SCREEN_W)
        rkt_sy  = SCREEN_H // 2
        draw_ang = rkt_angle

    elif phase == PHASE_SPACE:
        lp = (progress - EARTH_END) / (SPACE_END - EARTH_END)
        draw_space_bg(game_surf, lp, game_time)
        rkt_sx  = int(rkt_x * SCREEN_W)
        rkt_sy  = int(rkt_y * SCREEN_H)
        # Rotate draw +90° so nose points right (visually flying sideways)
        draw_ang = rkt_angle + 90

    elif phase == PHASE_MOON:
        lp = (progress - SPACE_END) / (1.0 - SPACE_END)
        draw_moon_bg(game_surf, lp)
        rkt_sx  = int(rkt_x * SCREEN_W)
        rkt_sy  = SCREEN_H // 2
        draw_ang = rkt_angle

    else:   # PHASE_WIN / PHASE_DEAD
        if progress < EARTH_END:
            draw_earth_bg(game_surf, progress / EARTH_END)
        elif progress < SPACE_END:
            draw_space_bg(game_surf,
                          (progress - EARTH_END) / (SPACE_END - EARTH_END),
                          game_time)
        else:
            draw_moon_bg(game_surf,
                         (progress - SPACE_END) / (1.0 - SPACE_END))
        rkt_sx   = int(rkt_x * SCREEN_W)
        rkt_sy   = SCREEN_H // 2
        draw_ang = rkt_angle

    # Draw obstacles
    for obs in obstacles:
        obs.draw(game_surf, 0, 0)

    # Draw rocket
    draw_rocket(game_surf, rkt_sx, rkt_sy, draw_ang,
                effective_thrust, flame_flicker)

    # HUD
    draw_hud(game_surf, progress, signal_delay(progress),
             steer, effective_thrust, phase)

    # CRT scanlines
    draw_screen_overlay(game_surf)

    # Overlays
    if phase == PHASE_SLEEP:
        draw_sleep_overlay(game_surf, sleep_timer / SLEEP_DURATION)
    elif phase == PHASE_LAUNCH:
        draw_launch_overlay(game_surf, 1.0 - launch_timer / 4.0)

    if phase == PHASE_WIN:
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        s.fill((0, 0, 0, 120))
        game_surf.blit(s, (0, 0))
        msg = font_mono_xl.render("TOUCHDOWN", True, C_GREEN)
        game_surf.blit(msg, (SCREEN_W//2 - msg.get_width()//2, SCREEN_H//2 - 40))
        sub = font_mono_md.render("MISSION COMPLETE", True, C_AMBER)
        game_surf.blit(sub, (SCREEN_W//2 - sub.get_width()//2, SCREEN_H//2 + 20))

    if phase == PHASE_DEAD:
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        s.fill((40, 0, 0, 145))
        game_surf.blit(s, (0, 0))
        msg = font_mono_xl.render("SIGNAL LOST", True, C_RED)
        game_surf.blit(msg, (SCREEN_W//2 - msg.get_width()//2, SCREEN_H//2 - 40))
        sub = font_mono_md.render("MISSION FAILED", True, (200, 80, 80))
        game_surf.blit(sub, (SCREEN_W//2 - sub.get_width()//2, SCREEN_H//2 + 20))

    # ═════════════════════════════════════════════════════════════════════════
    # DRAW OPERATOR ROOM
    # ═════════════════════════════════════════════════════════════════════════
    screen.fill(C_ROOM_BG)
    pygame.draw.rect(screen, C_DESK, (0, WIN_H - 200, WIN_W, 200))
    pygame.draw.line(screen, (50, 44, 58),
                     (0, WIN_H - 200), (WIN_W, WIN_H - 200), 2)

    bezel = pygame.Rect(SCREEN_X-16, SCREEN_Y-16, SCREEN_W+32, SCREEN_H+32)
    pygame.draw.rect(screen, (30, 28, 34), bezel, border_radius=12)
    pygame.draw.rect(screen, (50, 46, 56), bezel, 3, border_radius=12)

    glow = pygame.Rect(SCREEN_X-3, SCREEN_Y-3, SCREEN_W+6, SCREEN_H+6)
    pygame.draw.rect(screen, C_SCREEN_RIM, glow, 2, border_radius=4)

    screen.blit(game_surf, (SCREEN_X, SCREEN_Y))

    # Monitor stand
    pygame.draw.rect(screen, (40,36,44), (WIN_W//2-40, SCREEN_RY+16, 80, 18))
    pygame.draw.rect(screen, (50,44,54), (WIN_W//2-70, SCREEN_RY+34, 140, 10))

    # ── Joystick ──────────────────────────────────────────────────────────────
    pygame.draw.rect(screen, (38,32,44),
                     (JS_CX-90, JS_CY-24, 180, 48), border_radius=10)
    pygame.draw.rect(screen, (55,48,62),
                     (JS_CX-90, JS_CY-24, 180, 48), 2, border_radius=10)
    pygame.draw.rect(screen, (22,18,28),
                     (JS_CX-JS_R-4, JS_CY-8, (JS_R+4)*2, 16), border_radius=8)
    pygame.draw.line(screen, (70,60,80),
                     (JS_CX, JS_CY-16), (JS_CX, JS_CY+16), 1)
    pygame.draw.circle(screen, (20,16,24),
                       (int(js_knob_x)+2, JS_CY+3), KNOB_R)
    pygame.draw.circle(screen, C_AMBER, (int(js_knob_x), JS_CY), KNOB_R)
    pygame.draw.circle(screen, (240,200,80),
                       (int(js_knob_x), JS_CY), KNOB_R, 2)
    for dy2 in (-6, 0, 6):
        pygame.draw.line(screen, (180,130,20),
                         (int(js_knob_x)-8, JS_CY+dy2),
                         (int(js_knob_x)+8, JS_CY+dy2), 1)
    lbl = font_mono_sm.render("ATTITUDE CONTROL", True, (80,70,90))
    screen.blit(lbl, (JS_CX - lbl.get_width()//2, JS_CY + KNOB_R + 8))

    # ── Side panels ───────────────────────────────────────────────────────────
    py_p = WIN_H - 185

    # Left: signal delay
    px = 30
    pygame.draw.rect(screen, (28,24,34), (px, py_p, 160, 130), border_radius=6)
    pygame.draw.rect(screen, (50,44,58), (px, py_p, 160, 130), 1, border_radius=6)
    screen.blit(font_mono_sm.render("SIGNAL DELAY", True, C_GREEN_DIM),
                (px+8, py_p+8))
    dv    = signal_delay(progress)
    bar_h = int(clamp(dv / 3.5, 0, 1) * 80)
    pygame.draw.rect(screen, (30,60,35), (px+20, py_p+30, 20, 80))
    bc    = C_GREEN if dv < 1.5 else (C_AMBER if dv < 2.5 else C_RED)
    if bar_h > 0:
        pygame.draw.rect(screen, bc, (px+20, py_p+30+(80-bar_h), 20, bar_h))
    screen.blit(font_mono_sm.render(f"{dv:.2f}s", True, bc),
                (px+50, py_p+60))

    # Right: thruster indicator 
    px2 = WIN_W - 190
    pygame.draw.rect(screen, (28,24,34), (px2, py_p, 160, 130), border_radius=6)
    pygame.draw.rect(screen, (50,44,58), (px2, py_p, 160, 130), 1, border_radius=6)
    screen.blit(font_mono_sm.render("THRUSTER", True, C_GREEN_DIM),
                (px2+8, py_p+8))
    tc = C_FLAME if effective_thrust else (40,30,20)
    pygame.draw.circle(screen, tc, (px2+80, py_p+70), 28)
    pygame.draw.circle(screen, (60,50,40), (px2+80, py_p+70), 28, 2)
    tl = font_mono_sm.render("SPACE TO THRUST", True, (60,55,70))
    screen.blit(tl, (px2+80 - tl.get_width()//2, py_p+108))

    pygame.display.flip()

pygame.quit()