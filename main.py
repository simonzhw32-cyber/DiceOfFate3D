#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import math
import random
import time
import sys
import os

# ============================================================
# Window & layout
# ============================================================
WIN_W, WIN_H = 1100, 700
PANEL_W = 320          # left UI panel width
SCENE_W = WIN_W - PANEL_W  # 780

# ============================================================
# Physics constants
# ============================================================
GRAVITY    = -24.5
TABLE_Y    = -1.8
DICE_R     = 1.3
CONTACT_Y  = TABLE_Y + DICE_R   # -0.5
RESTITUTION = [0.52, 0.32, 0.14]
MAX_BOUNCES = 3

# ============================================================
# Chinese strings (Unicode escaped)
# ============================================================
S_TITLE      = "骰子命运"          # 骰子命运
S_SUBTITLE   = "D20 判定系统"      # D20 判定系统
S_LABEL      = "我要做："           # 我要做：
S_PLACEHOLDER= "输入你要尝试的事情..." # 输入你要尝试的事情...
S_BUTTON     = "投骰子"                 # 投骰子
S_HISTORY    = "最近投掷"           # 最近投掷
S_ROLLING    = "投掷中..."              # 投掷中...
S_RESULT_LBL = "结果"                       # 结果
S_DISMISS    = "点击任意处关闭" # 点击任意处关闭

RESULT_DATA = {
    "cf": {
        "range": (1,  5),
        "title": "大失败",              # 大失败
        "en":    "CRITICAL FAIL",
        "color": (220, 40,  60),
        "flavors": [
            "命运女神转过脸去了！",   # 命运女神转过脸去了！
            "诸神在嘲笑你的妄想。",   # 诸神在嘲笑你的妄想。
            "不仅失败，还把事情搞糟了。", # 不仅失败，还把事情搞糟了。
        ],
    },
    "f": {
        "range": (6,  9),
        "title": "失败",                    # 失败
        "en":    "FAIL",
        "color": (200, 100, 30),
        "flavors": [
            "命运没有眷顾你这一次。", # 命运没有眷顾你这一次。
            "也许下次会更好。",                   # 也许下次会更好。
        ],
    },
    "s": {
        "range": (10, 14),
        "title": "成功",                    # 成功
        "en":    "SUCCESS",
        "color": (40,  180, 80),
        "flavors": [
            "你做到了，虽然有点勉强。", # 你做到了，虽然有点勉强。
            "命运女神对你微微点头。",       # 命运女神对你微微点头。
        ],
    },
    "gs": {
        "range": (15, 19),
        "title": "大成功",              # 大成功
        "en":    "GREAT SUCCESS",
        "color": (60,  160, 230),
        "flavors": [
            "命运之轮转向了你！",         # 命运之轮转向了你！
            "诸神微笑着祝福你！",         # 诸神微笑着祝福你！
        ],
    },
    "cs": {
        "range": (20, 20),
        "title": "必杀成功",        # 必杀成功
        "en":    "NATURAL 20",
        "color": (255, 200, 0),
        "flavors": [
            "天命所归！传说中的英雄！", # 天命所归！传说中的英雄！
            "今天你就是天选之子！",             # 今天你就是天选之子！
        ],
    },
}

def result_key(v):
    for k, d in RESULT_DATA.items():
        lo, hi = d["range"]
        if lo <= v <= hi:
            return k
    return "s"

# ============================================================
# Math helpers
# ============================================================
def axis_angle_to_matrix(axis, angle):
    c, s = math.cos(angle), math.sin(angle)
    t = 1.0 - c
    x, y, z = axis
    return np.array([
        [t*x*x+c,   t*x*y-s*z, t*x*z+s*y],
        [t*x*y+s*z, t*y*y+c,   t*y*z-s*x],
        [t*x*z-s*y, t*y*z+s*x, t*z*z+c  ],
    ], dtype=np.float64)

def orthonormalize(R):
    x = R[:, 0] / np.linalg.norm(R[:, 0])
    y = R[:, 1] - np.dot(R[:, 1], x) * x
    y = y / np.linalg.norm(y)
    z = np.cross(x, y)
    return np.column_stack([x, y, z])

def find_chinese_font():
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

# ============================================================
# Icosahedron geometry
# ============================================================
_PHI = (1.0 + math.sqrt(5.0)) / 2.0

_VERTS_RAW = np.array([
    [-1,  _PHI,  0], [ 1,  _PHI,  0], [-1, -_PHI,  0], [ 1, -_PHI,  0],
    [ 0, -1,  _PHI], [ 0,  1,  _PHI], [ 0, -1, -_PHI], [ 0,  1, -_PHI],
    [ _PHI,  0, -1], [ _PHI,  0,  1], [-_PHI,  0, -1], [-_PHI,  0,  1],
], dtype=np.float64)
_VERTS_RAW /= np.linalg.norm(_VERTS_RAW[0])

_FACE_IDX = [
    [0,11, 5],[0, 5, 1],[0, 1, 7],[0, 7,10],[0,10,11],
    [1, 5, 9],[5,11, 4],[11,10, 2],[10, 7, 6],[7, 1, 8],
    [3, 9, 4],[3, 4, 2],[3, 2, 6],[3, 6, 8],[3, 8, 9],
    [4, 9, 5],[2, 4,11],[6, 2,10],[8, 6, 7],[9, 8, 1],
]

# Deep jewel tones — 5 groups of 4
_JEWEL_COLORS = [
    # Sapphire blue
    (0.08, 0.12, 0.45), (0.06, 0.10, 0.40), (0.10, 0.14, 0.50), (0.07, 0.11, 0.42),
    # Amethyst purple
    (0.30, 0.08, 0.45), (0.28, 0.06, 0.42), (0.32, 0.10, 0.48), (0.29, 0.07, 0.44),
    # Emerald green
    (0.05, 0.30, 0.15), (0.04, 0.28, 0.13), (0.06, 0.32, 0.17), (0.05, 0.29, 0.14),
    # Ruby red
    (0.40, 0.06, 0.08), (0.38, 0.05, 0.07), (0.42, 0.07, 0.09), (0.39, 0.06, 0.08),
    # Obsidian dark teal
    (0.05, 0.22, 0.28), (0.04, 0.20, 0.26), (0.06, 0.24, 0.30), (0.05, 0.21, 0.27),
]

class Icosahedron:
    def __init__(self, radius=DICE_R):
        self.radius = radius
        self.verts = _VERTS_RAW * radius
        self.faces = _FACE_IDX
        self.normals = self._calc_normals()
        self.edges = self._calc_edges()
        self.face_uvs = self._calc_face_uvs()
        self.colors = _JEWEL_COLORS

    def _calc_normals(self):
        normals = []
        for f in self.faces:
            v0, v1, v2 = self.verts[f[0]], self.verts[f[1]], self.verts[f[2]]
            n = np.cross(v1 - v0, v2 - v0)
            normals.append(n / np.linalg.norm(n))
        return normals

    def _calc_edges(self):
        es = set()
        for f in self.faces:
            for i in range(3):
                es.add(tuple(sorted([f[i], f[(i+1)%3]])))
        return list(es)

    def _calc_face_uvs(self):
        """Orient UV apex to the vertex most aligned with world +Y projected onto face plane."""
        uvs_all = []
        apex   = (0.5, 0.95)
        base_l = (0.05, 0.05)
        base_r = (0.95, 0.05)
        world_up = np.array([0.0, 1.0, 0.0])

        for fi, f in enumerate(self.faces):
            n = self.normals[fi]
            v0, v1, v2 = self.verts[f[0]], self.verts[f[1]], self.verts[f[2]]
            centroid = (v0 + v1 + v2) / 3.0

            # Project world up onto face plane
            up_proj = world_up - np.dot(world_up, n) * n
            if np.linalg.norm(up_proj) < 1e-6:
                up_proj = np.array([1.0, 0.0, 0.0]) - np.dot([1.0,0.0,0.0], n) * n
            up_proj /= np.linalg.norm(up_proj)

            # Which vertex is most "up" in face local space?
            scores = [np.dot(v - centroid, up_proj) for v in [v0, v1, v2]]
            top = int(np.argmax(scores))
            rest = [i for i in range(3) if i != top]

            # Determine left/right
            right = np.cross(n, up_proj)
            if np.dot(self.verts[f[rest[0]]] - centroid, right) < 0:
                uvs = [None, None, None]
                uvs[top]     = apex
                uvs[rest[0]] = base_l
                uvs[rest[1]] = base_r
            else:
                uvs = [None, None, None]
                uvs[top]     = apex
                uvs[rest[0]] = base_r
                uvs[rest[1]] = base_l
            uvs_all.append(uvs)
        return uvs_all

# ============================================================
# Number textures — 256×256 gold embossed
# ============================================================
class NumberTextures:
    def __init__(self, font_path):
        self.ids = {}
        fp = font_path or None
        try:
            font_glow = pygame.font.Font(fp, 130) if fp else pygame.font.SysFont("arial", 130, bold=True)
            font_main = pygame.font.Font(fp, 118) if fp else pygame.font.SysFont("arial", 118, bold=True)
        except Exception:
            font_glow = pygame.font.SysFont("arial", 130, bold=True)
            font_main = pygame.font.SysFont("arial", 118, bold=True)

        for n in range(1, 21):
            self.ids[n] = self._make(n, font_glow, font_main)

    def _make(self, number, font_glow, font_main):
        size = 256
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))

        cx, cy = size // 2, size // 2

        # Triangular background
        pts = [(cx, 10), (10, size-10), (size-10, size-10)]
        pygame.draw.polygon(surf, (12, 8, 28, 215), pts)
        # Inner highlight edge
        pygame.draw.polygon(surf, (60, 45, 100, 120), pts, 2)

        label = str(number)

        # Glow: render number offset in dark gold
        glow_surf = font_glow.render(label, True, (100, 70, 10))
        gx = cx - glow_surf.get_width() // 2
        gy = cy - glow_surf.get_height() // 2 + 12
        for dx in (-4, -2, 0, 2, 4):
            for dy in (-4, -2, 0, 2, 4):
                if dx != 0 or dy != 0:
                    surf.blit(glow_surf, (gx + dx, gy + dy))

        # Shadow
        shadow = font_main.render(label, True, (80, 55, 5))
        nx = cx - shadow.get_width() // 2
        ny = cy - shadow.get_height() // 2 + 12
        surf.blit(shadow, (nx + 3, ny + 3))

        # Main gold
        main = font_main.render(label, True, (255, 210, 70))
        surf.blit(main, (nx, ny))

        # Highlight (lighter gold, offset up-left)
        hi = font_main.render(label, True, (255, 245, 170))
        hi.set_alpha(90)
        surf.blit(hi, (nx - 1, ny - 1))

        raw = pygame.image.tostring(surf, "RGBA", True)
        tid = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tid)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        gluBuild2DMipmaps(GL_TEXTURE_2D, GL_RGBA, size, size, GL_RGBA, GL_UNSIGNED_BYTE, raw)
        return tid

# ============================================================
# Procedural wood texture
# ============================================================
class WoodTexture:
    def __init__(self):
        self.id = self._make()

    def _make(self):
        size = 512
        surf = pygame.Surface((size, size))
        surf.fill((18, 11, 6))

        rng = random.Random(42)
        y = 0
        while y < size:
            plank_h = rng.randint(28, 48)
            # Plank separator
            pygame.draw.line(surf, (8, 5, 2), (0, y), (size, y), 2)
            # Grain lines within plank
            for _ in range(12):
                gy = y + rng.randint(2, plank_h - 2)
                shade = rng.randint(22, 32)
                pygame.draw.line(surf, (shade, shade//2, shade//3), (0, gy), (size, gy), 1)
            y += plank_h

        raw = pygame.image.tostring(surf, "RGB", True)
        tid = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tid)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        gluBuild2DMipmaps(GL_TEXTURE_2D, GL_RGB, size, size, GL_RGB, GL_UNSIGNED_BYTE, raw)
        return tid

# ============================================================
# Dice physics
# ============================================================
class DicePhysics:
    WAITING  = 0
    ROLLING  = 1
    SETTLING = 2
    SETTLED  = 3

    def __init__(self):
        self.state = self.WAITING
        self.pos   = np.array([0.0, CONTACT_Y, 0.0])
        self.vel   = np.zeros(3)
        self.rot   = np.eye(3)
        self.omega = np.zeros(3)
        self.bounce_count = 0
        self.frame = 0
        self.target_face = 0
        self.result = 1
        self._idle_angle = 0.0

    def roll(self, result):
        self.result = result
        self.target_face = result - 1
        self.state = self.ROLLING
        self.bounce_count = 0
        self.frame = 0
        self.pos   = np.array([random.uniform(-0.4, 0.4), 4.2, random.uniform(-0.2, 0.2)])
        self.vel   = np.array([random.uniform(-2.0, 2.0),
                               random.uniform(-4.5, -2.5),
                               random.uniform(-0.8, 0.8)])
        ax = np.random.randn(3); ax /= np.linalg.norm(ax)
        self.omega = ax * random.uniform(14.0, 24.0)
        self.rot   = np.eye(3)

    def update(self, dt):
        self.frame += 1

        if self.state == self.WAITING:
            self._idle_angle += dt * 0.35
            self.rot = axis_angle_to_matrix(np.array([0.0, 1.0, 0.0]), self._idle_angle)
            return

        if self.state == self.ROLLING:
            # Gravity + integrate position
            self.vel[1] += GRAVITY * dt
            self.pos    += self.vel * dt

            # Table collision
            if self.pos[1] < CONTACT_Y and self.vel[1] < -0.05:
                self.pos[1] = CONTACT_Y
                if self.bounce_count < MAX_BOUNCES:
                    bi = min(self.bounce_count, len(RESTITUTION) - 1)
                    self.vel[1] *= -RESTITUTION[bi]
                    self.vel[0] *= 0.82
                    self.vel[2] *= 0.82
                    perturb = np.random.randn(3); perturb /= np.linalg.norm(perturb)
                    self.omega += perturb * random.uniform(4.0, 8.0)
                    self.bounce_count += 1
                else:
                    # Kill vertical motion after max bounces
                    self.vel[1] = 0.0
                    self.vel[0] *= 0.70
                    self.vel[2] *= 0.70

            # Rotation integration
            speed = np.linalg.norm(self.omega)
            if speed > 1e-6:
                self.rot = axis_angle_to_matrix(self.omega / speed, speed * dt) @ self.rot
            if self.frame % 10 == 0:
                self.rot = orthonormalize(self.rot)

            # Angular damping
            self.omega *= math.exp(-2.8 * dt)

            # Transition to settling
            lin_speed = np.linalg.norm(self.vel)
            ang_speed = np.linalg.norm(self.omega)
            on_table  = abs(self.pos[1] - CONTACT_Y) < 0.05
            if lin_speed < 0.20 and ang_speed < 1.5 and self.bounce_count >= 1 and on_table:
                self.vel    = np.zeros(3)
                self.pos[1] = CONTACT_Y
                self.state  = self.SETTLING

        elif self.state == self.SETTLING:
            # Align target face normal to +Y
            world_n = self.rot @ _VERTS_RAW[_FACE_IDX[self.target_face][0]]
            # Use face centroid direction as proxy for face normal
            fc = np.mean([_VERTS_RAW[i] for i in _FACE_IDX[self.target_face]], axis=0)
            world_n = self.rot @ (fc / np.linalg.norm(fc))

            up = np.array([0.0, 1.0, 0.0])
            dot = float(np.clip(np.dot(world_n, up), -1.0, 1.0))

            if dot > 0.9998:
                self.state = self.SETTLED
                return

            axis = np.cross(world_n, up)
            an = np.linalg.norm(axis)
            if an > 1e-6:
                angle = math.acos(dot)
                step  = min(angle, 4.0 * dt)
                self.rot = axis_angle_to_matrix(axis / an, step) @ self.rot
                self.rot = orthonormalize(self.rot)

    @property
    def is_active(self):
        return self.state in (self.ROLLING, self.SETTLING)

    def gl_matrix(self):
        M = np.eye(4, dtype=np.float32)
        M[:3, :3] = self.rot.astype(np.float32)
        return M.T  # column-major for OpenGL

# ============================================================
# Particles
# ============================================================
class Particle:
    __slots__ = ("x","y","vx","vy","r","g","b","life","max_life","size")
    def __init__(self, x, y, vx, vy, color, life, size):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.r, self.g, self.b = color
        self.life = self.max_life = life
        self.size = size

class Particles:
    def __init__(self):
        self.pool = []

    def spawn(self, cx, cy, color, count=60):
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(60, 280)
            self.pool.append(Particle(
                cx, cy,
                math.cos(angle)*speed, math.sin(angle)*speed - random.uniform(0,80),
                color,
                random.uniform(0.8, 1.8),
                random.randint(3, 7),
            ))

    def update(self, dt):
        alive = []
        for p in self.pool:
            p.life -= dt
            if p.life > 0:
                p.x  += p.vx * dt
                p.y  += p.vy * dt
                p.vy += 320 * dt
                alive.append(p)
        self.pool = alive

    def draw(self, surface):
        for p in self.pool:
            a = int(255 * (p.life / p.max_life))
            r = max(1, int(p.size * p.life / p.max_life))
            pygame.draw.circle(surface, (p.r, p.g, p.b, a), (int(p.x), int(p.y)), r)


# ============================================================
# Text input widget
# ============================================================
class TextInput:
    def __init__(self, rect, font, placeholder=""):
        self.rect        = pygame.Rect(rect)
        self.font        = font
        self.placeholder = placeholder
        self.text        = ""
        self.focused     = False
        self._cursor_t   = 0.0
        self._cursor_vis = True

    def handle_event(self, event, panel_x_offset=0):
        if event.type == MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if mx < PANEL_W:
                self.focused = True   # any panel click re-focuses input
        if not self.focused:
            return None
        if event.type == KEYDOWN:
            if event.key == K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key in (K_RETURN, K_KP_ENTER):
                return "submit"
        elif event.type == pygame.TEXTINPUT:
            self.text += event.text
        return None

    def update(self, dt):
        self._cursor_t += dt
        if self._cursor_t >= 0.5:
            self._cursor_t   = 0.0
            self._cursor_vis = not self._cursor_vis

    def draw(self, surface):
        r = self.rect
        bg = (45, 35, 20) if self.focused else (30, 22, 12)
        bc = (200, 160, 50) if self.focused else (90, 70, 40)
        pygame.draw.rect(surface, bg, r, border_radius=6)
        pygame.draw.rect(surface, bc, r, 2, border_radius=6)

        display = self.text if self.text else self.placeholder
        color   = (230, 210, 140) if self.text else (100, 85, 60)
        # Wrap text to fit width
        max_w = r.width - 16
        words  = display.split()
        lines  = []
        cur    = ""
        for w in words:
            test = (cur + " " + w).strip()
            if self.font.size(test)[0] <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        if not lines:
            lines = [""]

        lh = self.font.get_linesize()
        for i, line in enumerate(lines[:4]):
            ts = self.font.render(line, True, color)
            surface.blit(ts, (r.x + 8, r.y + 8 + i * lh))

        if self.focused and self._cursor_vis:
            last_line = lines[-1] if lines else ""
            lw = self.font.size(last_line)[0]
            row = min(len(lines)-1, 3)
            cx = r.x + 8 + lw + 2
            cy = r.y + 8 + row * lh
            pygame.draw.line(surface, (230, 210, 140), (cx, cy), (cx, cy + lh - 2), 2)


# ============================================================
# Left UI panel
# ============================================================
class UIPanel:
    def __init__(self, font_path):
        self.W, self.H = PANEL_W, WIN_H
        self._dirty    = True
        self._surface  = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self._tex_id   = glGenTextures(1)
        self.history   = []   # list of (action, result_key, value)

        fp = font_path
        try:
            self.font_title  = pygame.font.Font(fp, 28)
            self.font_sub    = pygame.font.Font(fp, 14)
            self.font_label  = pygame.font.Font(fp, 16)
            self.font_input  = pygame.font.Font(fp, 15)
            self.font_btn    = pygame.font.Font(fp, 20)
            self.font_hist   = pygame.font.Font(fp, 13)
        except Exception:
            self.font_title  = pygame.font.SysFont("arial", 28, bold=True)
            self.font_sub    = pygame.font.SysFont("arial", 14)
            self.font_label  = pygame.font.SysFont("arial", 16)
            self.font_input  = pygame.font.SysFont("arial", 15)
            self.font_btn    = pygame.font.SysFont("arial", 20, bold=True)
            self.font_hist   = pygame.font.SysFont("arial", 13)

        self.input = TextInput(
            pygame.Rect(16, 160, self.W - 32, 100),
            self.font_input,
            S_PLACEHOLDER,
        )
        self.btn_rect   = pygame.Rect(16, 278, self.W - 32, 46)
        self.btn_hover  = False
        self.rolling    = False

    def handle_event(self, event):
        result = self.input.handle_event(event, panel_x_offset=0)
        if result == "submit":
            return "roll"
        if event.type == MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if mx < PANEL_W and self.btn_rect.collidepoint(mx, my) and not self.rolling:
                return "roll"
        if event.type == MOUSEMOTION:
            mx, my = event.pos
            self.btn_hover = (mx < PANEL_W and self.btn_rect.collidepoint(mx, my))
            self._dirty = True
        return None

    def update(self, dt):
        self.input.update(dt)
        self._dirty = True

    def add_history(self, action, rkey, value):
        self.history.insert(0, (action, rkey, value))
        self.history = self.history[:5]
        self._dirty = True

    def render(self):
        s = self._surface
        s.fill((0, 0, 0, 0))

        # Background
        pygame.draw.rect(s, (14, 10, 6, 240), (0, 0, self.W, self.H))
        # Right border
        pygame.draw.line(s, (80, 60, 20), (self.W-1, 0), (self.W-1, self.H), 2)

        # Title
        t = self.font_title.render(S_TITLE, True, (220, 175, 50))
        s.blit(t, (self.W//2 - t.get_width()//2, 22))
        sub = self.font_sub.render(S_SUBTITLE, True, (120, 95, 40))
        s.blit(sub, (self.W//2 - sub.get_width()//2, 58))

        # Divider
        pygame.draw.line(s, (80, 60, 20), (16, 80), (self.W-16, 80), 1)

        # Label
        lbl = self.font_label.render(S_LABEL, True, (180, 150, 80))
        s.blit(lbl, (16, 100))

        # Input box
        self.input.draw(s)

        # Roll button
        bc = (180, 140, 40) if self.btn_hover and not self.rolling else (100, 75, 20)
        bg = (50, 38, 12) if self.btn_hover and not self.rolling else (28, 20, 8)
        if self.rolling:
            bg = (20, 15, 5)
            bc = (60, 45, 15)
        pygame.draw.rect(s, bg, self.btn_rect, border_radius=8)
        pygame.draw.rect(s, bc, self.btn_rect, 2, border_radius=8)
        btn_label = S_ROLLING if self.rolling else S_BUTTON
        bt = self.font_btn.render(btn_label, True, (230, 190, 60) if not self.rolling else (120, 95, 30))
        s.blit(bt, (self.btn_rect.centerx - bt.get_width()//2,
                    self.btn_rect.centery - bt.get_height()//2))

        # History
        pygame.draw.line(s, (80, 60, 20), (16, 345), (self.W-16, 345), 1)
        ht = self.font_label.render(S_HISTORY, True, (140, 110, 50))
        s.blit(ht, (16, 352))

        for i, (act, rk, val) in enumerate(self.history):
            y = 378 + i * 56
            rd = RESULT_DATA[rk]
            rc = rd["color"]
            pygame.draw.rect(s, (20, 15, 8, 200), (12, y, self.W-24, 50), border_radius=5)
            pygame.draw.rect(s, rc, (12, y, self.W-24, 50), 1, border_radius=5)
            # Value badge
            badge = self.font_btn.render(str(val), True, rc)
            s.blit(badge, (20, y + 14))
            # Result title
            rt_surf = self.font_hist.render(rd["title"], True, rc)
            s.blit(rt_surf, (52, y + 6))
            # Action text (truncated)
            act_disp = act[:22] + "..." if len(act) > 22 else act
            at = self.font_hist.render(act_disp, True, (160, 140, 100))
            s.blit(at, (52, y + 26))

        return s

    def upload(self):
        surf = self.render()
        raw  = pygame.image.tostring(surf, "RGBA", True)
        glBindTexture(GL_TEXTURE_2D, self._tex_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.W, self.H, 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, raw)
        return self._tex_id


# ============================================================
# Result overlay
# ============================================================
class ResultOverlay:
    ANIM_DUR = 0.55

    def __init__(self, font_path):
        self.visible   = False
        self.anim_t    = 0.0
        self.rkey      = "s"
        self.value     = 10
        self.action    = ""
        self.flavor    = ""
        self.particles = Particles()
        self._tex_id   = glGenTextures(1)

        fp = font_path
        try:
            self.font_big    = pygame.font.Font(fp, 52)
            self.font_num    = pygame.font.Font(fp, 90)
            self.font_med    = pygame.font.Font(fp, 22)
            self.font_small  = pygame.font.Font(fp, 17)
            self.font_dismiss= pygame.font.Font(fp, 14)
        except Exception:
            self.font_big    = pygame.font.SysFont("arial", 52, bold=True)
            self.font_num    = pygame.font.SysFont("arial", 90, bold=True)
            self.font_med    = pygame.font.SysFont("arial", 22)
            self.font_small  = pygame.font.SysFont("arial", 17)
            self.font_dismiss= pygame.font.SysFont("arial", 14)

    def show(self, rkey, value, action):
        self.visible = True
        self.anim_t  = 0.0
        self.rkey    = rkey
        self.value   = value
        self.action  = action
        self.flavor  = random.choice(RESULT_DATA[rkey]["flavors"])
        self.particles.pool.clear()
        rc = RESULT_DATA[rkey]["color"]
        self.particles.spawn(WIN_W//2, WIN_H//2, rc, 80)

    def hide(self):
        self.visible = False

    def update(self, dt):
        if not self.visible:
            return
        self.anim_t = min(1.0, self.anim_t + dt / self.ANIM_DUR)
        self.particles.update(dt)

    def draw(self):
        if not self.visible:
            return None
        t  = self.anim_t
        rd = RESULT_DATA[self.rkey]
        rc = rd["color"]

        surf = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)

        # Dark overlay
        bg_a = int(200 * min(1.0, t * 2.5))
        surf.fill((0, 0, 0, bg_a))

        # Color tint
        tint = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        tint.fill((*rc, int(35 * min(1.0, t * 2.5))))
        surf.blit(tint, (0, 0))

        # Particles
        self.particles.draw(surf)

        # Card scale-in: ease-out cubic
        scale = 1.0 - (1.0 - t)**3 * 0.45
        cw = int(580 * scale)
        ch = int(360 * scale)
        cx = WIN_W//2 - cw//2
        cy = WIN_H//2 - ch//2

        if cw > 20 and ch > 20:
            card = pygame.Surface((cw, ch), pygame.SRCALPHA)
            pygame.draw.rect(card, (18, 12, 6, 235), (0, 0, cw, ch), border_radius=14)
            pygame.draw.rect(card, (*rc, 220), (0, 0, cw, ch), 3, border_radius=14)
            # Inner glow line
            pygame.draw.rect(card, (*rc, 60), (4, 4, cw-8, ch-8), 1, border_radius=11)
            surf.blit(card, (cx, cy))

            alpha = int(255 * min(1.0, t * 2.0))
            if alpha > 30:
                # Result title
                rt = self.font_big.render(rd["title"], True, (*rc, alpha))
                surf.blit(rt, (WIN_W//2 - rt.get_width()//2, cy + int(28*scale)))

                # Big number
                num_s = self.font_num.render(str(self.value), True, (255, 255, 255, alpha))
                surf.blit(num_s, (WIN_W//2 - num_s.get_width()//2, cy + int(85*scale)))

                # Action text
                act_disp = self.action[:40] + ("..." if len(self.action)>40 else "")
                at = self.font_med.render(act_disp, True, (200, 185, 150, alpha))
                surf.blit(at, (WIN_W//2 - at.get_width()//2, cy + int(200*scale)))

                # Flavor
                fl = self.font_small.render(self.flavor, True, (160, 145, 110, alpha))
                surf.blit(fl, (WIN_W//2 - fl.get_width()//2, cy + int(240*scale)))

                # Dismiss hint
                dm = self.font_dismiss.render(S_DISMISS, True, (100, 85, 60, alpha))
                surf.blit(dm, (WIN_W//2 - dm.get_width()//2, cy + ch - int(28*scale)))

        return surf

    def upload_and_get_tex(self):
        surf = self.draw()
        if surf is None:
            return None
        raw = pygame.image.tostring(surf, "RGBA", True)
        glBindTexture(GL_TEXTURE_2D, self._tex_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, WIN_W, WIN_H, 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, raw)
        return self._tex_id


# ============================================================
# Renderer
# ============================================================
class Renderer:
    def __init__(self):
        self._init_gl()
        self.wood = WoodTexture()
        self._panel_tex  = None
        self._overlay_tex= None

    def _init_gl(self):
        glClearColor(0.04, 0.03, 0.02, 1.0)
        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LESS)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_LIGHT1)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        glEnable(GL_RESCALE_NORMAL)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Warm key light
        glLightfv(GL_LIGHT0, GL_POSITION, [3.0, 6.0, 4.0, 1.0])
        glLightfv(GL_LIGHT0, GL_AMBIENT,  [0.12, 0.09, 0.06, 1.0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE,  [0.90, 0.82, 0.68, 1.0])
        glLightfv(GL_LIGHT0, GL_SPECULAR, [1.0,  0.95, 0.80, 1.0])

        # Cool fill light
        glLightfv(GL_LIGHT1, GL_POSITION, [-4.0, 3.0, -3.0, 1.0])
        glLightfv(GL_LIGHT1, GL_AMBIENT,  [0.0,  0.0,  0.0,  1.0])
        glLightfv(GL_LIGHT1, GL_DIFFUSE,  [0.12, 0.18, 0.30, 1.0])
        glLightfv(GL_LIGHT1, GL_SPECULAR, [0.0,  0.0,  0.0,  1.0])

        glLightModelfv(GL_LIGHT_MODEL_AMBIENT, [0.06, 0.05, 0.04, 1.0])

    def _set_3d_viewport(self):
        glViewport(PANEL_W, 0, SCENE_W, WIN_H)
        glEnable(GL_SCISSOR_TEST)
        glScissor(PANEL_W, 0, SCENE_W, WIN_H)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45.0, SCENE_W / WIN_H, 0.1, 60.0)
        glMatrixMode(GL_MODELVIEW)

    def _set_2d_viewport(self, x, y, w, h):
        glDisable(GL_SCISSOR_TEST)
        glViewport(x, y, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, w, 0, h, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)

    def _restore_3d_state(self):
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)

    def render_frame(self, physics, geo, num_textures, panel, overlay):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # ---- 3D scene ----
        self._set_3d_viewport()
        glLoadIdentity()
        gluLookAt(0, 2.5, 8.5,   0, -0.5, 0,   0, 1, 0)

        self._draw_table()
        self._draw_shadow(physics)
        self._draw_dice(physics, geo, num_textures)

        glDisable(GL_SCISSOR_TEST)

        # ---- Left panel ----
        self._set_2d_viewport(0, 0, PANEL_W, WIN_H)
        tid = panel.upload()
        self._draw_fullscreen_tex(tid, PANEL_W, WIN_H)
        self._restore_3d_state()

        # ---- Result overlay ----
        if overlay.visible:
            self._set_2d_viewport(0, 0, WIN_W, WIN_H)
            tid2 = overlay.upload_and_get_tex()
            if tid2:
                self._draw_fullscreen_tex(tid2, WIN_W, WIN_H)
            self._restore_3d_state()

    def _draw_table(self):
        glDisable(GL_LIGHTING)
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.wood.id)
        glColor4f(1.0, 1.0, 1.0, 1.0)
        s = 6.0
        y = TABLE_Y
        rep = 4.0
        glBegin(GL_QUADS)
        glTexCoord2f(0,   0);   glVertex3f(-s, y, -s)
        glTexCoord2f(rep, 0);   glVertex3f( s, y, -s)
        glTexCoord2f(rep, rep); glVertex3f( s, y,  s)
        glTexCoord2f(0,   rep); glVertex3f(-s, y,  s)
        glEnd()
        glDisable(GL_TEXTURE_2D)

        # Subtle grid
        glColor4f(0.25, 0.18, 0.10, 0.25)
        glLineWidth(1.0)
        glBegin(GL_LINES)
        for i in range(-6, 7):
            glVertex3f(i, y+0.002, -s)
            glVertex3f(i, y+0.002,  s)
            glVertex3f(-s, y+0.002, i)
            glVertex3f( s, y+0.002, i)
        glEnd()
        glEnable(GL_LIGHTING)

    def _draw_shadow(self, physics):
        glDisable(GL_LIGHTING)
        glEnable(GL_BLEND)
        px, pz = physics.pos[0], physics.pos[2]
        height = max(0.0, physics.pos[1] - CONTACT_Y)
        spread = 1.0 + height * 0.35
        alpha  = max(0.05, 0.35 - height * 0.06)
        glColor4f(0, 0, 0, alpha)
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(px, TABLE_Y + 0.003, pz)
        for a in range(0, 361, 12):
            rad = math.radians(a)
            glVertex3f(px + math.cos(rad)*DICE_R*spread,
                       TABLE_Y + 0.003,
                       pz + math.sin(rad)*DICE_R*spread*0.55)
        glEnd()
        glEnable(GL_LIGHTING)

    def _draw_dice(self, physics, geo, num_textures):
        glPushMatrix()
        glTranslatef(*physics.pos.astype(np.float32))
        glMultMatrixf(physics.gl_matrix())

        # Specular material
        glMaterialfv(GL_FRONT, GL_SPECULAR,  [0.85, 0.78, 0.55, 1.0])
        glMaterialf (GL_FRONT, GL_SHININESS, 88.0)

        # Filled faces
        glEnable(GL_POLYGON_OFFSET_FILL)
        glPolygonOffset(1.0, 1.0)

        for i, face in enumerate(geo.faces):
            c = geo.colors[i]
            # Brighten settled target face
            if physics.state == DicePhysics.SETTLED and i == physics.target_face:
                c = tuple(min(1.0, v + 0.25) for v in c)
            glColor3f(*c)
            n = geo.normals[i]
            glNormal3f(*n)
            glBegin(GL_TRIANGLES)
            for vi in face:
                glVertex3f(*geo.verts[vi])
            glEnd()

        glDisable(GL_POLYGON_OFFSET_FILL)

        # Number textures
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glDisable(GL_LIGHTING)
        glColor4f(1, 1, 1, 1)
        glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE)

        for i, face in enumerate(geo.faces):
            glBindTexture(GL_TEXTURE_2D, num_textures.ids[i+1])
            n  = geo.normals[i]
            off = np.array(n, dtype=np.float32) * 0.006
            uvs = geo.face_uvs[i]
            glBegin(GL_TRIANGLES)
            for j, vi in enumerate(face):
                glTexCoord2f(*uvs[j])
                v = geo.verts[vi] + off
                glVertex3f(*v)
            glEnd()

        glDisable(GL_TEXTURE_2D)
        glEnable(GL_LIGHTING)

        # Gold edges
        glDisable(GL_LIGHTING)
        glEnable(GL_POLYGON_OFFSET_LINE)
        glPolygonOffset(-1.0, -1.0)
        glLineWidth(2.2)
        glColor3f(1.0, 0.84, 0.0)
        glBegin(GL_LINES)
        for e in geo.edges:
            glVertex3f(*geo.verts[e[0]])
            glVertex3f(*geo.verts[e[1]])
        glEnd()
        glDisable(GL_POLYGON_OFFSET_LINE)
        glEnable(GL_LIGHTING)

        glPopMatrix()

    def _draw_fullscreen_tex(self, tex_id, w, h):
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glColor4f(1, 1, 1, 1)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(0, 0)
        glTexCoord2f(1, 0); glVertex2f(w, 0)
        glTexCoord2f(1, 1); glVertex2f(w, h)
        glTexCoord2f(0, 1); glVertex2f(0, h)
        glEnd()
        glDisable(GL_TEXTURE_2D)


# ============================================================
# App — state machine + main loop
# ============================================================
class App:
    WAITING        = 0
    ROLLING        = 1
    SETTLING       = 2
    SHOWING_RESULT = 3

    def __init__(self):
        pygame.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H), DOUBLEBUF | OPENGL)
        pygame.display.set_caption("骰子命运 3D")
        pygame.key.start_text_input()   # enable IME / unicode key events on Windows

        self.font_path = find_chinese_font()
        self.renderer  = Renderer()
        self.geo       = Icosahedron()
        self.num_tex   = NumberTextures(self.font_path)
        self.physics   = DicePhysics()
        self.panel     = UIPanel(self.font_path)
        self.overlay   = ResultOverlay(self.font_path)

        self.state     = self.WAITING
        self.clock     = pygame.time.Clock()
        self._result   = 1
        self._action   = ""
        self.panel.input.focused = True

        # Tell SDL/IME where to show the candidate window (input box area)
        inp_rect = self.panel.input.rect
        pygame.key.set_text_input_rect(pygame.Rect(inp_rect.x, inp_rect.y, inp_rect.w, inp_rect.h))

    def _trigger_roll(self):
        action = self.panel.input.text.strip()
        if not action:
            return
        self._action = action
        self._result = random.randint(1, 20)
        self.physics.roll(self._result)
        self.panel.rolling = True
        self.state = self.ROLLING

    def _handle_events(self):
        for e in pygame.event.get():
            if e.type == QUIT:
                return False
            if e.type == KEYDOWN and e.key == K_ESCAPE:
                if self.state == self.SHOWING_RESULT:
                    self.overlay.hide()
                    self.state = self.WAITING
                    self.panel.rolling = False
                    continue
                else:
                    return False

            if self.state == self.SHOWING_RESULT:
                if e.type in (MOUSEBUTTONDOWN, KEYDOWN):
                    self.overlay.hide()
                    self.state = self.WAITING
                    self.panel.rolling = False
                continue

            if self.state == self.WAITING:
                cmd = self.panel.handle_event(e)
                if cmd == "roll":
                    self._trigger_roll()
        return True

    def _update(self, dt):
        self.physics.update(dt)
        self.panel.update(dt)
        self.overlay.update(dt)

        if self.state == self.ROLLING:
            if self.physics.state == DicePhysics.SETTLING:
                self.state = self.SETTLING

        elif self.state == self.SETTLING:
            if self.physics.state == DicePhysics.SETTLED:
                rkey = result_key(self._result)
                self.panel.add_history(self._action, rkey, self._result)
                self.overlay.show(rkey, self._result, self._action)
                self.state = self.SHOWING_RESULT

    def run(self):
        last = time.time()
        running = True
        while running:
            now = time.time()
            dt  = min(now - last, 0.05)
            last = now

            running = self._handle_events()
            self._update(dt)
            self.renderer.render_frame(
                self.physics, self.geo, self.num_tex,
                self.panel, self.overlay,
            )
            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()


if __name__ == "__main__":
    App().run()
