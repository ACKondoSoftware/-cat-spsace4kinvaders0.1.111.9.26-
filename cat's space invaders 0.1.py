#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cat's space invaders 0.1  --  Team Flames
single file | files = off | 60 fps | beep boop = on | main menu = true
everything (sprites, sfx, music, bloom) is synthesized at boot.

    pip install pygame
    python "cat's space invaders 0.1.py"

keys : arrows / A-D move | SPACE fire | P pause | ESC back | ENTER select
pad  : left stick move | cross fire/select | options pause
"""
import array
import math
import random
import sys

import pygame

W, H = 960, 720
FPS = 60
SR = 22050
TAU = math.tau
PY = H - 96            # player top
GROUND = H - 56
CELL_W, CELL_H = 60, 46
COLS, ROWS = 11, 5

# --------------------------------------------------------------------------
# sprites (files = off -> strings)
# --------------------------------------------------------------------------
SQUID = [
    ["...XX...", "..XXXX..", ".XXXXXX.", "XX.XX.XX", "XXXXXXXX", "..X..X..", ".X.XX.X.", "X.X..X.X"],
    ["...XX...", "..XXXX..", ".XXXXXX.", "XX.XX.XX", "XXXXXXXX", ".X.XX.X.", "X......X", ".X....X."],
]
CRAB = [
    ["..X.....X..", "...X...X...", "..XXXXXXX..", ".XX.XXX.XX.", "XXXXXXXXXXX", "X.XXXXXXX.X", "X.X.....X.X", "...XX.XX..."],
    ["..X.....X..", "X..X...X..X", "X.XXXXXXX.X", "XXX.XXX.XXX", "XXXXXXXXXXX", ".XXXXXXXXX.", "..X.....X..", ".X.......X."],
]
OCTO = [
    ["....XXXX....", ".XXXXXXXXXX.", "XXXXXXXXXXXX", "XXX..XX..XXX", "XXXXXXXXXXXX", "...XX..XX...", "..XX.XX.XX..", "XX........XX"],
    ["....XXXX....", ".XXXXXXXXXX.", "XXXXXXXXXXXX", "XXX..XX..XXX", "XXXXXXXXXXXX", "..XXX..XXX..", ".XX..XX..XX.", "..XX....XX.."],
]
SHIP = ["......X......", ".....XXX.....", ".....XXX.....", ".XXXXXXXXXXX.",
        "XXXXXXXXXXXXX", "XXXXXXXXXXXXX", "XXXXXXXXXXXXX"]
UFO = [".....XXXXXX.....", "...XXXXXXXXXX...", "..XXXXXXXXXXXX..", ".XX.XX.XX.XX.XX.",
       "XXXXXXXXXXXXXXXX", "..XXX..XX..XXX..", "...X........X..."]

C_SQUID = (255, 80, 220)
C_CRAB = (80, 215, 255)
C_OCTO = (110, 255, 150)
C_SHIP = (120, 220, 255)
C_UFO = (255, 70, 95)
C_TEXT = (220, 240, 255)
INV_COL = (C_SQUID, C_CRAB, C_OCTO)
INV_PTS = (30, 20, 10)


def make_sprite(rows, color, px=4):
    h, w = len(rows), len(rows[0])
    s = pygame.Surface((w * px, h * px)).convert()
    s.set_colorkey((0, 0, 0))
    for y, row in enumerate(rows):
        k = 0.6 * (1.0 - y / max(1, h - 1))            # top highlight -> base color
        c = tuple(min(255, max(1, int(v + (255 - v) * k))) for v in color)
        for x, ch in enumerate(row):
            if ch == "X":
                s.fill(c, (x * px, y * px, px, px))
    return s


# --------------------------------------------------------------------------
# audio synth (files = off -> math)
# --------------------------------------------------------------------------
class NullSound:
    def play(self, *a, **k): pass
    def stop(self): pass
    def set_volume(self, v): pass
    def get_busy(self): return False


def synth(dur, fn, vol=0.5):
    n = int(SR * dur)
    a = array.array("h", bytes(2 * n))
    for i in range(n):
        v = fn(i / SR, i / n) * vol
        a[i] = int(max(-1.0, min(1.0, v)) * 32767)
    return pygame.mixer.Sound(buffer=a.tobytes())


def sweep(f0, f1, dur, wave="sq", vol=0.35, noise=0.0):
    ph = [0.0]

    def fn(t, u):
        ph[0] += (f0 + (f1 - f0) * u) / SR
        p = ph[0] % 1.0
        if wave == "sq":
            s = 1.0 if p < 0.5 else -1.0
        elif wave == "saw":
            s = 2.0 * p - 1.0
        else:
            s = math.sin(TAU * p)
        if noise:
            s = s * (1.0 - noise) + random.uniform(-1, 1) * noise
        return s * min(1.0, t * 400.0) * (1.0 - u) ** 2
    return synth(dur, fn, vol)


def boom(dur=0.4, vol=0.6):
    lp = [0.0]

    def fn(t, u):
        lp[0] += (random.uniform(-1, 1) - lp[0]) * (0.5 - 0.4 * u)
        return (lp[0] * 1.6 + 0.5 * math.sin(TAU * (90 - 50 * u) * t)) * (1.0 - u) ** 1.5
    return synth(dur, fn, vol)


def make_music():
    """16 s seamless ambient loop: overlapping pads + glass arp + wrapped echo."""
    sr = SR // 2                                   # render at half rate, upsample x2
    seg = 4.0
    chords = [(55.00, (220.00, 261.63, 329.63, 493.88)),     # Am add9
              (43.65, (174.61, 220.00, 261.63, 329.63)),     # Fmaj7
              (65.41, (196.00, 261.63, 329.63, 392.00)),     # C
              (49.00, (196.00, 246.94, 293.66, 392.00))]     # G
    n = int(sr * seg)
    total = n * len(chords)
    out = [0.0] * total
    sin = math.sin
    span = int(n * 1.5)                            # pads overlap neighbours
    for ci, (bass, notes) in enumerate(chords):
        base = ci * n - (span - n) // 2
        w = [TAU * f / sr for f in notes]
        w2 = [x * 1.006 for x in w]
        wb = TAU * bass / sr
        for i in range(span):
            e = sin(math.pi * i / span)
            e *= e
            s = 0.55 * sin(wb * i) + 0.25 * sin(wb * 2 * i)
            for a, b in zip(w, w2):
                s += 0.2 * (sin(a * i) + sin(b * i))
            out[(base + i) % total] += s * e * 0.3
    pat = (0, 2, 1, 3, 2, 1, 3, 0)
    pl = int(sr * 0.45)
    for ci, (_, notes) in enumerate(chords):
        for k in range(8):
            f = notes[pat[k]] * 2.0
            wv = TAU * f / sr
            start = ci * n + int(k * sr * 0.5)
            for i in range(pl):
                e = math.exp(-7.0 * i / pl) * min(1.0, i / 30.0)
                out[(start + i) % total] += (sin(wv * i) + 0.3 * sin(2 * wv * i)) * e * 0.11
    d = int(sr * 0.375)
    wet = [0.0] * total
    for _ in range(2):                             # 2nd pass converges across the loop seam
        for i in range(total):
            wet[i] = 0.45 * out[i - d] + 0.4 * wet[i - d]
    mix = [o + x for o, x in zip(out, wet)]
    peak = max(1e-9, max(abs(v) for v in mix))
    g = 0.8 * 32767 / peak
    a = array.array("h", bytes(4 * total))
    for i in range(total):
        v0 = mix[i]
        v1 = mix[(i + 1) % total]
        a[2 * i] = int(v0 * g)
        a[2 * i + 1] = int((v0 + v1) * 0.5 * g)
    return pygame.mixer.Sound(buffer=a.tobytes())


# --------------------------------------------------------------------------
# game
# --------------------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.mixer.pre_init(SR, -16, 1, 512)
        pygame.init()
        try:
            self.scr = pygame.display.set_mode((W, H), pygame.SCALED | pygame.RESIZABLE, vsync=1)
        except pygame.error:
            self.scr = pygame.display.set_mode((W, H))
        pygame.display.set_caption("cat's space invaders 0.1 - 60 FPS")
        self.clock = pygame.time.Clock()
        self.layer = pygame.Surface((W, H)).convert()
        self.f_big = pygame.font.Font(None, 110)
        self.f_mid = pygame.font.Font(None, 46)
        self.f_sm = pygame.font.Font(None, 28)
        self.tcache = {}

        self.scr.fill((4, 6, 16))
        self.text("SYNTHESIZING...", self.f_mid, C_TEXT, W // 2, H // 2, dst=self.scr)
        pygame.display.flip()
        pygame.event.pump()

        self.build_gfx()
        self.build_audio()

        self.pad = None
        pygame.joystick.init()
        if pygame.joystick.get_count():
            self.pad = pygame.joystick.Joystick(0)

        self.t = 0
        self.shake = 0.0
        self.parts = []
        self.pops = []
        self.state = "menu"
        self.sel = 0
        self.sfx_on = True
        self.music_on = True
        self.hi = 0
        self.new_game()
        self.state = "menu"
        self.ch_music.play(self.music, loops=-1)
        self.ch_music.set_volume(0.55)

    # ---- boot ------------------------------------------------------------
    def build_gfx(self):
        self.spr_inv = [[make_sprite(f, c) for f in frames]
                        for frames, c in ((SQUID, C_SQUID), (CRAB, C_CRAB), (OCTO, C_OCTO))]
        self.spr_ship = make_sprite(SHIP, C_SHIP)
        self.spr_life = make_sprite(SHIP, C_SHIP, 2)
        self.spr_ufo = make_sprite(UFO, C_UFO)
        # background: tiny gradient + nebula blobs, smooth-upscaled
        sw, sh = W // 10, H // 10
        small = pygame.Surface((sw, sh))
        for y in range(sh):
            u = y / sh
            small.fill((int(4 + 10 * u), int(6 + 6 * u), int(18 + 26 * u)), (0, y, sw, 1))
        rng = random.Random(7)
        blob = pygame.Surface((sw, sh))
        for _ in range(9):
            blob.fill((0, 0, 0))
            col = rng.choice(((30, 8, 46), (6, 26, 48), (8, 34, 36), (40, 10, 30)))
            pygame.draw.circle(blob, col, (rng.randrange(sw), rng.randrange(sh)), rng.randrange(8, 22))
            small.blit(blob, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        small = pygame.transform.smoothscale(small, (sw // 3, sh // 3))
        self.bg = pygame.transform.smoothscale(small, (W, H)).convert()
        self.stars = [[random.random() * W, random.random() * H, sp, br]
                      for sp, br, cnt in ((0.15, 70, 70), (0.4, 120, 50), (0.9, 200, 25))
                      for _ in range(cnt)]

    def build_audio(self):
        self.audio = pygame.mixer.get_init() is not None
        null = NullSound()
        if not self.audio:
            self.snd = {k: null for k in ("shoot", "boom", "die", "ufo", "ufohit", "blip", "ok")}
            self.snd["march"] = [null] * 4
            self.music = null
            self.ch_music = self.ch_ufo = null
            return
        pygame.mixer.set_num_channels(16)
        pygame.mixer.set_reserved(2)
        self.ch_music = pygame.mixer.Channel(0)
        self.ch_ufo = pygame.mixer.Channel(1)
        self.snd = {
            "shoot": sweep(1300, 260, 0.16, "sq", 0.22),
            "boom": boom(0.35, 0.55),
            "die": sweep(420, 40, 0.9, "saw", 0.5, noise=0.5),
            "ufo": synth(0.4, lambda t, u: math.sin(TAU * 600 * t + 6 * math.sin(TAU * 5 * t)), 0.16),
            "ufohit": sweep(300, 1600, 0.5, "sq", 0.25),
            "blip": sweep(880, 880, 0.05, "sin", 0.3),
            "ok": sweep(660, 1320, 0.16, "sin", 0.35),
            "march": [sweep(f, f * 0.8, 0.12, "sq", 0.4) for f in (98, 87, 78, 73)],
        }
        self.music = make_music()

    # ---- helpers ---------------------------------------------------------
    def play(self, s):
        if self.sfx_on:
            s.play()

    def text(self, s, font, color, x, y, anchor="c", dst=None):
        key = (s, id(font), color)
        img = self.tcache.get(key)
        if img is None:
            if len(self.tcache) > 300:
                self.tcache.clear()
            img = font.render(s, True, color)
            self.tcache[key] = img
        r = img.get_rect()
        if anchor == "c":
            r.center = (x, y)
        elif anchor == "l":
            r.midleft = (x, y)
        else:
            r.midright = (x, y)
        (dst or self.layer).blit(img, r)

    def burst(self, x, y, color, n=18, speed=4.0, life=40):
        for _ in range(n):
            a = random.random() * TAU
            v = random.random() * speed
            self.parts.append([x, y, math.cos(a) * v, math.sin(a) * v,
                               random.randint(life // 2, life), life, color, random.choice((2, 3, 4)), 0.04])
        if len(self.parts) > 700:
            del self.parts[:len(self.parts) - 700]

    def quit(self):
        pygame.quit()
        sys.exit(0)

    # ---- game state ------------------------------------------------------
    def new_game(self):
        self.score = 0
        self.lives = 3
        self.wave = 1
        self.px = W / 2
        self.inv = 0
        self.dead = 0
        self.inter = 0
        self.setup_wave()
        self.state = "play"

    def setup_wave(self):
        self.alive = [[True] * COLS for _ in range(ROWS)]
        self.count = ROWS * COLS
        self.fx = (W - ((COLS - 1) * CELL_W + 48)) // 2
        self.fy = 110 + min(self.wave - 1, 6) * 20
        self.dir = 1
        self.frame = 0
        self.step_t = 0
        self.mi = 0
        self.bullet = None
        self.bombs = []
        self.ufo = None
        self.ufo_t = random.randint(900, 1500)
        self.shields = []
        for k in range(4):
            cells = {(cx, cy) for cy in range(10) for cx in range(14)
                     if cx + cy >= 3 and (13 - cx) + cy >= 3
                     and not (cy >= 6 and 4 <= cx <= 9 and not (cy == 6 and cx in (4, 9)))}
            surf = pygame.Surface((84, 60)).convert()
            surf.set_colorkey((0, 0, 0))
            s = {"x": int(W * (k + 0.5) / 4 - 42), "y": H - 210, "cells": cells, "surf": surf}
            self.redraw_shield(s)
            self.shields.append(s)

    def redraw_shield(self, s):
        s["surf"].fill((0, 0, 0))
        for cx, cy in s["cells"]:
            s["surf"].fill((40, 255 - cy * 9, 150 + cy * 8), (cx * 6, cy * 6, 6, 6))

    def shield_hit(self, x, y):
        for s in self.shields:
            cx, cy = int((x - s["x"]) // 6), int((y - s["y"]) // 6)
            if (cx, cy) in s["cells"]:
                for dx in range(-2, 3):
                    for dy in range(-2, 3):
                        if (dx == 0 and dy == 0) or (dx * dx + dy * dy <= 4 and random.random() < 0.7):
                            s["cells"].discard((cx + dx, cy + dy))
                self.redraw_shield(s)
                self.burst(x, y, (60, 255, 170), 6, 2.0, 20)
                return True
        return False

    def irect(self, r, c):
        k = 0 if r == 0 else (1 if r < 3 else 2)
        w = self.spr_inv[k][0].get_width()
        return pygame.Rect(self.fx + c * CELL_W + (48 - w) // 2, self.fy + r * CELL_H, w, 32), k

    def stop_ufo(self):
        self.ufo = None
        self.ch_ufo.stop()

    def kill_player(self, final=False):
        self.lives = 0 if final else self.lives - 1
        self.dead = 110
        self.bullet = None
        self.bombs = []
        self.shake = 18.0
        self.burst(self.px, PY + 14, C_SHIP, 70, 7.0, 70)
        self.burst(self.px, PY + 14, (255, 180, 80), 40, 4.0, 50)
        self.play(self.snd["die"])

    def end_game(self):
        self.stop_ufo()
        self.hi = max(self.hi, self.score)
        self.state = "over"

    # ---- input -----------------------------------------------------------
    def on_event(self, e):
        act = None
        if e.type == pygame.QUIT:
            self.quit()
        elif e.type == pygame.KEYDOWN:
            act = {pygame.K_UP: "up", pygame.K_w: "up", pygame.K_DOWN: "down", pygame.K_s: "down",
                   pygame.K_RETURN: "ok", pygame.K_KP_ENTER: "ok", pygame.K_SPACE: "ok",
                   pygame.K_ESCAPE: "back", pygame.K_p: "pause"}.get(e.key)
        elif e.type == pygame.JOYBUTTONDOWN:
            act = {0: "ok", 1: "back", 6: "pause", 9: "pause", 11: "up", 12: "down"}.get(e.button)
        elif e.type == pygame.JOYHATMOTION:
            act = "up" if e.value[1] > 0 else ("down" if e.value[1] < 0 else None)
        elif e.type == pygame.JOYDEVICEADDED:
            self.pad = pygame.joystick.Joystick(e.device_index)
        elif e.type == pygame.JOYDEVICEREMOVED:
            self.pad = None
        if act:
            self.action(act)

    def action(self, act):
        st = self.state
        if st == "menu":
            if act in ("up", "down"):
                self.sel = (self.sel + (1 if act == "down" else -1)) % 4
                self.play(self.snd["blip"])
            elif act == "ok":
                if self.sel == 0:
                    self.play(self.snd["ok"])
                    self.parts.clear()
                    self.new_game()
                elif self.sel == 1:
                    self.sfx_on = not self.sfx_on
                    self.play(self.snd["ok"])
                elif self.sel == 2:
                    self.music_on = not self.music_on
                    self.ch_music.set_volume(0.55 if self.music_on else 0.0)
                    self.play(self.snd["blip"])
                else:
                    self.quit()
            elif act == "back":
                self.quit()
        elif st == "play":
            if act in ("pause", "back"):
                self.ch_ufo.stop()
                self.state = "pause"
        elif st == "pause":
            if act in ("pause", "ok"):
                if self.ufo and self.sfx_on:
                    self.ch_ufo.play(self.snd["ufo"], loops=-1)
                self.state = "play"
            elif act == "back":
                self.end_game()
                self.state = "menu"
        elif st == "over":
            if act in ("ok", "back"):
                self.parts.clear()
                self.state = "menu"

    # ---- update ----------------------------------------------------------
    def update(self):
        self.t += 1
        for s in self.stars:
            s[1] += s[2]
            if s[1] > H:
                s[1] = 0.0
                s[0] = random.random() * W
        if self.state != "pause":
            for p in self.parts:
                p[0] += p[2]
                p[1] += p[3]
                p[3] += p[8]
                p[4] -= 1
            self.parts = [p for p in self.parts if p[4] > 0]
            for p in self.pops:
                p[1] -= 0.6
                p[3] -= 1
            self.pops = [p for p in self.pops if p[3] > 0]
        self.shake *= 0.88
        if self.state == "menu":
            if self.t % 5 == 0:
                life = random.randint(300, 520)
                self.parts.append([random.random() * W, H + 30, random.uniform(-0.2, 0.2),
                                   random.uniform(-1.1, -0.3), life, life,
                                   random.choice(((14, 50, 80), (50, 16, 70), (10, 60, 60))),
                                   random.randint(10, 26), 0.0])
        elif self.state == "play":
            self.update_play()

    def update_play(self):
        if self.inter > 0:
            self.inter -= 1
            if self.inter == 0:
                self.setup_wave()
            return
        keys = pygame.key.get_pressed()
        mv = float((keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a]))
        fire = keys[pygame.K_SPACE]
        if self.pad:
            try:
                ax = self.pad.get_axis(0)
                if abs(ax) > 0.25:
                    mv = ax
                fire = fire or self.pad.get_button(0)
            except pygame.error:
                self.pad = None
        if self.dead > 0:                           # classic freeze while the ship burns
            self.dead -= 1
            if self.dead == 0:
                if self.lives <= 0:
                    self.end_game()
                else:
                    self.px = W / 2
                    self.inv = 120
            return
        self.px = max(40.0, min(W - 40.0, self.px + mv * 5.5))
        if self.inv > 0:
            self.inv -= 1
        if fire and self.bullet is None:
            self.bullet = [self.px, PY - 18.0]
            self.play(self.snd["shoot"])
        self.update_bullet()
        self.update_invaders()
        if self.dead:
            return
        self.update_bombs()
        self.update_ufo()
        if self.count == 0:
            self.score += 100 * self.wave
            self.pops.append([W / 2, H / 2 + 60, "WAVE CLEAR +%d" % (100 * self.wave), 90])
            self.wave += 1
            self.inter = 100
            self.bombs = []
            self.bullet = None
            self.stop_ufo()

    def update_bullet(self):
        b = self.bullet
        if b is None:
            return
        b[1] -= 14.0
        if self.t & 1:
            self.parts.append([b[0], b[1] + 18, 0.0, 1.0, 10, 10, (60, 160, 200), 3, 0.0])
        if b[1] < 44:
            self.burst(b[0], 48, (200, 255, 255), 6, 2.0, 16)
            self.bullet = None
            return
        if any(self.shield_hit(b[0], b[1] + o) for o in (0, 6, 12)):
            self.bullet = None
            return
        br = pygame.Rect(b[0] - 2, b[1], 4, 18)
        for bm in self.bombs:
            if br.colliderect(bm[0] - 5, bm[1] - 16, 10, 16):
                self.bombs.remove(bm)
                self.burst(bm[0], bm[1], (255, 200, 80), 10, 3.0, 24)
                self.bullet = None
                return
        if self.ufo and br.colliderect(self.ufo[0], 64, 64, 28):
            pts = random.choice((50, 100, 150, 300))
            self.score += pts
            self.pops.append([self.ufo[0] + 32, 78, str(pts), 70])
            self.burst(self.ufo[0] + 32, 78, C_UFO, 50, 6.0, 55)
            self.shake = 8.0
            self.stop_ufo()
            self.play(self.snd["ufohit"])
            self.bullet = None
            return
        for r in range(ROWS - 1, -1, -1):
            for c in range(COLS):
                if not self.alive[r][c]:
                    continue
                rect, k = self.irect(r, c)
                if br.colliderect(rect):
                    self.alive[r][c] = False
                    self.count -= 1
                    self.score += INV_PTS[k]
                    self.burst(rect.centerx, rect.centery, INV_COL[k], 26, 4.5, 42)
                    self.shake = max(self.shake, 3.0)
                    self.play(self.snd["boom"])
                    self.bullet = None
                    return

    def update_invaders(self):
        if self.count == 0:
            return
        self.step_t += 1
        if self.step_t < max(2, int(self.count * 0.95) - (self.wave - 1) * 2):
            return
        self.step_t = 0
        cols = [c for r in range(ROWS) for c in range(COLS) if self.alive[r][c]]
        left = self.fx + min(cols) * CELL_W
        right = self.fx + max(cols) * CELL_W + 48
        if (self.dir > 0 and right + 10 > W - 24) or (self.dir < 0 and left - 10 < 24):
            self.fy += 24
            self.dir = -self.dir
        else:
            self.fx += 10 * self.dir
        self.frame ^= 1
        self.play(self.snd["march"][self.mi])
        self.mi = (self.mi + 1) % 4
        sy = self.shields[0]["y"]
        invaded = False
        for r in range(ROWS):
            for c in range(COLS):
                if not self.alive[r][c]:
                    continue
                rect, _ = self.irect(r, c)
                if rect.bottom >= PY:
                    invaded = True
                if rect.bottom >= sy:
                    for s in self.shields:
                        if rect.colliderect(s["x"], s["y"], 84, 60):
                            keep = {q for q in s["cells"]
                                    if not rect.collidepoint(s["x"] + q[0] * 6 + 3, s["y"] + q[1] * 6 + 3)}
                            if len(keep) != len(s["cells"]):
                                s["cells"] = keep
                                self.redraw_shield(s)
        if invaded:
            self.kill_player(final=True)

    def update_bombs(self):
        if (self.count and len(self.bombs) < min(6, 2 + self.wave)
                and random.random() < 0.018 + self.wave * 0.004):
            c = random.choice([c for c in range(COLS) if any(self.alive[r][c] for r in range(ROWS))])
            r = max(r for r in range(ROWS) if self.alive[r][c])
            rect, _ = self.irect(r, c)
            self.bombs.append([float(rect.centerx), float(rect.bottom + 16)])
        sp = min(8.0, 3.5 + self.wave * 0.4)
        pr = pygame.Rect(self.px - 26, PY + 4, 52, 24)
        for bm in self.bombs[:]:
            bm[1] += sp
            if self.shield_hit(bm[0], bm[1]) or self.shield_hit(bm[0], bm[1] - 6):
                self.bombs.remove(bm)
            elif bm[1] >= GROUND:
                self.burst(bm[0], GROUND, (255, 200, 80), 6, 2.0, 18)
                self.bombs.remove(bm)
            elif self.inv == 0 and pr.collidepoint(bm[0], bm[1]):
                self.kill_player()
                return

    def update_ufo(self):
        if self.ufo is None:
            self.ufo_t -= 1
            if self.ufo_t <= 0 and self.count > 7 and self.fy > 96:
                d = random.choice((-1, 1))
                self.ufo = [-70.0 if d > 0 else W + 6.0, d]
                if self.sfx_on:
                    self.ch_ufo.play(self.snd["ufo"], loops=-1)
            return
        self.ufo[0] += 2.6 * self.ufo[1]
        if self.ufo[0] < -80 or self.ufo[0] > W + 16:
            self.stop_ufo()
            self.ufo_t = random.randint(900, 1500)

    # ---- draw ------------------------------------------------------------
    def draw(self):
        L = self.layer
        L.fill((0, 0, 0))
        if self.state == "menu":
            self.draw_menu()
        else:
            self.draw_play()
        for p in self.parts:
            k = p[4] / p[5]
            if p[7] > 8:                             # menu bokeh: fade in + out
                k = math.sin(math.pi * k)
                pygame.draw.circle(L, (int(p[6][0] * k), int(p[6][1] * k), int(p[6][2] * k)),
                                   (int(p[0]), int(p[1])), p[7])
            else:
                L.fill((int(p[6][0] * k), int(p[6][1] * k), int(p[6][2] * k)),
                       (int(p[0]) - p[7] // 2, int(p[1]) - p[7] // 2, p[7], p[7]))
        for x, y, s, life in self.pops:
            v = min(255, life * 6)
            self.text(s, self.f_sm, (v, v, int(v * 0.6)), int(x), int(y))

        scr = self.scr
        scr.blit(self.bg, (0, 0))
        for x, y, sp, br in self.stars:
            tw = br if sp < 0.8 else int(br * (0.7 + 0.3 * math.sin(self.t * 0.1 + x)))
            scr.fill((tw, tw, min(255, tw + 30)), (int(x), int(y), 2, 2))
        ox = oy = 0
        if self.shake > 0.5:
            ox = int(random.uniform(-self.shake, self.shake))
            oy = int(random.uniform(-self.shake, self.shake))
        # bloom: tight + wide blur of the emissive layer, added back on top
        q = pygame.transform.smoothscale(L, (W // 4, H // 4))
        e = pygame.transform.smoothscale(q, (W // 12, H // 12))
        add = pygame.BLEND_RGB_ADD
        scr.blit(pygame.transform.smoothscale(e, (W, H)), (ox, oy), special_flags=add)
        scr.blit(pygame.transform.smoothscale(q, (W, H)), (ox, oy), special_flags=add)
        scr.blit(L, (ox, oy), special_flags=add)

    def draw_menu(self):
        L = self.layer
        t = self.t
        ty = 150 + int(math.sin(t * 0.03) * 6)
        self.text("CAT'S", self.f_mid, (255, 220, 120), W // 2, ty - 68)
        self.text("SPACE", self.f_big, (120, 230, 255), W // 2, ty)
        self.text("INVADERS", self.f_big, (255, 90, 220), W // 2, ty + 84)
        self.text("0.1  -  60 FPS  -  FILES = OFF", self.f_sm, (120, 150, 190), W // 2, ty + 150)
        items = ["START",
                 "BEEP BOOP   %s" % ("ON" if self.sfx_on else "OFF"),
                 "MUSIC   %s" % ("ON" if self.music_on else "OFF"),
                 "QUIT"]
        for i, s in enumerate(items):
            y = 372 + i * 56
            if i == self.sel:
                g = 0.6 + 0.4 * math.sin(t * 0.09)
                pygame.draw.rect(L, (int(10 * g), int(55 * g), int(85 * g)),
                                 (W // 2 - 190, y - 24, 380, 48), border_radius=24)
                pygame.draw.rect(L, (int(70 * g), int(200 * g), int(255 * g)),
                                 (W // 2 - 190, y - 24, 380, 48), 2, border_radius=24)
                self.text(s, self.f_mid, (255, 255, 255), W // 2, y)
            else:
                self.text(s, self.f_mid, (110, 135, 170), W // 2, y)
        f = (t // 30) & 1
        x = W // 2 - 300
        for k in range(3):
            sp = self.spr_inv[k][f]
            L.blit(sp, (x, 622))
            self.text("= %d" % INV_PTS[k], self.f_sm, C_TEXT, x + sp.get_width() + 12, 638, "l")
            x += 160
        L.blit(self.spr_ufo, (x, 624))
        self.text("= ???", self.f_sm, C_TEXT, x + 76, 638, "l")
        self.text("HI %06d" % self.hi, self.f_sm, (255, 220, 120), W // 2, 40)
        self.text("ARROWS / A-D MOVE    SPACE FIRE    P PAUSE    ENTER SELECT",
                  self.f_sm, (90, 110, 150), W // 2, H - 24)

    def draw_play(self):
        L = self.layer
        pygame.draw.line(L, (0, 110, 140), (30, GROUND), (W - 30, GROUND), 2)
        for s in self.shields:
            L.blit(s["surf"], (s["x"], s["y"]))
        if self.inter == 0:
            for r in range(ROWS):
                for c in range(COLS):
                    if self.alive[r][c]:
                        rect, k = self.irect(r, c)
                        L.blit(self.spr_inv[k][self.frame], rect)
        else:
            self.text("WAVE %d" % self.wave, self.f_big, (120, 230, 255), W // 2, H // 2 - 40)
        if self.ufo:
            L.blit(self.spr_ufo, (int(self.ufo[0]), 64))
        if self.dead == 0 and self.state != "over" and (self.inv // 5) % 2 == 0:
            L.blit(self.spr_ship, (int(self.px) - 26, PY))
            fl = 6 + (self.t & 3) * 2                # engine flame
            L.fill((255, 150, 60), (int(self.px) - 3, PY + 28, 6, fl))
        if self.bullet:
            L.fill((210, 255, 255), (int(self.bullet[0]) - 2, int(self.bullet[1]), 4, 18))
        ph = (self.t // 4) & 1
        for bx, by in self.bombs:
            pts = [(bx + (((i + ph) & 1) * 2 - 1) * 3, by - i * 5) for i in range(4)]
            pygame.draw.lines(L, (255, 200, 80), False, pts, 3)
        self.text("SCORE %06d" % self.score, self.f_sm, C_TEXT, 30, 28, "l")
        self.text("HI %06d" % max(self.hi, self.score), self.f_sm, (255, 220, 120), W // 2, 28)
        self.text("WAVE %d" % self.wave, self.f_sm, C_TEXT, W - 30, 28, "r")
        for i in range(max(0, self.lives - 1)):
            L.blit(self.spr_life, (30 + i * 36, GROUND + 14))
        self.text("%d FPS" % round(self.clock.get_fps()), self.f_sm, (70, 90, 120), W - 30, GROUND + 22, "r")
        if self.state == "pause":
            self.text("PAUSED", self.f_big, (255, 255, 255), W // 2, H // 2 - 30)
            self.text("P RESUME    ESC MENU", self.f_sm, C_TEXT, W // 2, H // 2 + 40)
        elif self.state == "over":
            self.text("GAME OVER", self.f_big, (255, 80, 110), W // 2, H // 2 - 40)
            self.text("SCORE %06d" % self.score, self.f_mid, C_TEXT, W // 2, H // 2 + 36)
            if (self.t // 30) & 1:
                self.text("PRESS ENTER", self.f_sm, (255, 220, 120), W // 2, H // 2 + 86)

    # ---- loop ------------------------------------------------------------
    def run(self):
        while True:
            for e in pygame.event.get():
                self.on_event(e)
            self.update()
            self.draw()
            pygame.display.flip()
            self.clock.tick(FPS)


if __name__ == "__main__":
    Game().run()
