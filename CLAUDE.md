# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

骰子命运 3D (Dice of Fate 3D) — a Baldur's Gate 3-inspired 3D D20 dice roller built with Python, Pygame, and OpenGL. Renders an interactive icosahedron with physics-based rolling, a split-panel UI, and a Chinese-language result overlay.

## Running the App

```bash
python main.py
```

Dependencies: `pygame`, `PyOpenGL`, `numpy`. Install with:

```bash
pip install pygame PyOpenGL numpy
```

No build step, no tests, no linter config.

## Architecture

Everything lives in `main.py`. Module-level constants define window dimensions (`WIN_W=1100`, `WIN_H=700`, `PANEL_W=320`), physics parameters, and the `RESULT_DATA` dict mapping result keys (`"cf"`, `"f"`, `"s"`, `"gs"`, `"cs"`) to ranges, Chinese titles, English labels, colors, and flavor strings.

**Geometry & textures**

- `Icosahedron` — Generates 12 vertices (golden ratio), 20 faces, per-face jewel-tone colors, normals, edges, and UV coordinates for number placement. Vertex/face data is module-level (`_VERTS_RAW`, `_FACE_IDX`, `_JEWEL_COLORS`).
- `NumberTextures` — Creates 20 OpenGL textures (one per face) with gold-embossed numbers rendered via Pygame fonts and uploaded via `gluBuild2DMipmaps`.
- `WoodTexture` — Procedurally generates a 512×512 wood-plank texture (seeded RNG) for the table surface.

**Physics**

- `DicePhysics` — State machine: `WAITING → ROLLING → SETTLING → SETTLED`. ROLLING applies gravity, table collision with multi-bounce restitution (`RESTITUTION = [0.52, 0.32, 0.14]`), and angular damping. SETTLING smoothly rotates the target face to face up. `gl_matrix()` returns a column-major 4×4 float32 for `glMultMatrixf`.

**UI**

- `TextInput` — Single-widget text input with cursor blink, word-wrap display, and IME support (`pygame.key.start_text_input()`).
- `UIPanel` — Left 320 px panel rendered to a Pygame SRCALPHA surface each frame, uploaded as an OpenGL texture. Contains title, text input, roll button, and last-5-roll history.
- `ResultOverlay` — Full-screen animated result card (scale-in ease-out cubic) with `Particles` burst effect. Shown after dice settle; dismissed by any click or keypress.
- `Particles` / `Particle` — Simple 2D particle system drawn onto the overlay surface.

**Rendering & app**

- `Renderer` — Owns all OpenGL draw calls. Uses a split viewport: 3D scene occupies `[PANEL_W, 0, SCENE_W, WIN_H]` with scissor test; panel and overlay are drawn as 2D fullscreen quads via `_draw_fullscreen_tex`. Fixed-function pipeline (no shaders), two lights (warm key + cool fill).
- `App` — Top-level state machine: `WAITING → ROLLING → SETTLING → SHOWING_RESULT`. Owns all subsystems. `_trigger_roll()` requires non-empty text input before rolling.

## Key Details

- **Controls:** Type an action in the text input, then click "投骰子" or press Enter to roll. ESC dismisses the result overlay or quits.
- **Result bands:** 1–5 critical fail, 6–9 fail, 10–14 success, 15–19 great success, 20 critical success.
- **Chinese font:** `find_chinese_font()` probes Windows system font paths (`msyh.ttc`, `simhei.ttf`, etc.); falls back to Arial if none found.
- **Frame cap:** 60 FPS via `clock.tick(60)`; `dt` is clamped to 50 ms to prevent physics tunneling on lag spikes.
- **Rotation math:** `axis_angle_to_matrix` + `orthonormalize` keep the rotation matrix numerically stable; re-orthonormalized every 10 physics frames.
