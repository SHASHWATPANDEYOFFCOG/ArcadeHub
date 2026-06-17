"""
3D Rubik's Cube Game
====================
A fully interactive 3D Rubik's cube you can turn, scramble, and auto-solve.

Built with pygame (window/input) + PyOpenGL (3D rendering).

Controls
--------
  Turn the UP    (top)    face :  U      (hold SHIFT for reverse)
  Turn the DOWN  (bottom) face :  D      (hold SHIFT for reverse)
  Turn the LEFT          face :  L      (hold SHIFT for reverse)
  Turn the RIGHT         face :  R      (hold SHIFT for reverse)
  Turn the FRONT         face :  F      (hold SHIFT for reverse)
  Turn the BACK          face :  B      (hold SHIFT for reverse)

  Rotate the whole view        :  drag LEFT mouse button, or arrow keys
  Scramble the cube            :  S
  Solve (undo every move)      :  ENTER
  Reset to a solved cube       :  BACKSPACE
  Quit                         :  ESC

A face turn rotates only that one layer 90 degrees: pressing the key alone
goes clockwise (viewed from outside that face); holding SHIFT goes the
opposite way. The "Solve" button replays the inverse of every move you've
made (scramble included) in reverse order, so the cube always returns solved.
"""

import sys
import random

import numpy as np
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *

# ---------------------------------------------------------------------------
# Colors (RGB, 0..1)
# ---------------------------------------------------------------------------
WHITE  = (1.0, 1.0, 1.0)
YELLOW = (1.0, 0.9, 0.0)
GREEN  = (0.0, 0.6, 0.2)
BLUE   = (0.0, 0.25, 0.85)
RED    = (0.8, 0.05, 0.05)
ORANGE = (1.0, 0.45, 0.0)
DARK   = (0.08, 0.08, 0.08)   # interior / hidden faces

# Which sticker color belongs on each outward face normal of the whole cube
FACE_COLOR = {
    (1, 0, 0):  RED,      # +X  right
    (-1, 0, 0): ORANGE,   # -X  left
    (0, 1, 0):  WHITE,    # +Y  up
    (0, -1, 0): YELLOW,   # -Y  down
    (0, 0, 1):  GREEN,    # +Z  front
    (0, 0, -1): BLUE,     # -Z  back
}

# Move -> (axis, layer-coordinate, direction)
# direction is the sign used for the right-hand-rule rotation about +axis.
MOVES = {
    'U': ('y',  1, -1),
    'D': ('y', -1,  1),
    'R': ('x',  1, -1),
    'L': ('x', -1,  1),
    'F': ('z',  1, -1),
    'B': ('z', -1,  1),
}

AXIS_INDEX = {'x': 0, 'y': 1, 'z': 2}
AXIS_VEC   = {'x': (1, 0, 0), 'y': (0, 1, 0), 'z': (0, 0, 1)}

SPACING    = 2.05    # distance between cubie centers
HALF       = 0.95    # half edge length of a single cubie
ANIM_SPEED = 9.0     # degrees of layer turn per frame


def rotate90(v, axis, d):
    """Rotate an integer vector v by +/-90 degrees about an axis (right-hand rule)."""
    x, y, z = v
    if axis == 'x':
        return (x, -d * z, d * y)
    if axis == 'y':
        return (d * z, y, -d * x)
    # axis == 'z'
    return (-d * y, d * x, z)


class Cubie:
    """One of the 27 small cubes. Tracks its grid position and sticker colors."""

    def __init__(self, pos):
        self.pos = pos  # (x, y, z), each in {-1, 0, 1}
        # Map outward face-normal -> sticker color, only for exterior faces.
        self.colors = {}
        for axis, idx in AXIS_INDEX.items():
            for sign in (1, -1):
                if pos[idx] == sign:
                    normal = tuple(sign if i == idx else 0 for i in range(3))
                    self.colors[normal] = FACE_COLOR[normal]

    def apply(self, axis, d):
        """Permanently rotate this cubie's position and stickers by a 90 turn."""
        self.pos = rotate90(self.pos, axis, d)
        self.colors = {rotate90(n, axis, d): c for n, c in self.colors.items()}


# Geometry of a unit cube face: normal -> 4 corner vertices (scaled by HALF)
def _face_geometry():
    h = HALF
    return {
        (1, 0, 0):  [(h, -h, -h), (h, h, -h), (h, h, h), (h, -h, h)],
        (-1, 0, 0): [(-h, -h, -h), (-h, -h, h), (-h, h, h), (-h, h, -h)],
        (0, 1, 0):  [(-h, h, -h), (-h, h, h), (h, h, h), (h, h, -h)],
        (0, -1, 0): [(-h, -h, -h), (h, -h, -h), (h, -h, h), (-h, -h, h)],
        (0, 0, 1):  [(-h, -h, h), (h, -h, h), (h, h, h), (-h, h, h)],
        (0, 0, -1): [(-h, -h, -h), (-h, h, -h), (h, h, -h), (h, -h, -h)],
    }


FACE_GEOM = _face_geometry()


class RubiksCube:
    def __init__(self):
        self.reset()

    def reset(self):
        self.cubies = [Cubie((x, y, z))
                       for x in (-1, 0, 1)
                       for y in (-1, 0, 1)
                       for z in (-1, 0, 1)]
        self.history = []          # user/scramble moves, as (name, dir)
        self.queue = []            # pending moves: (name, dir, record)
        self.anim = None           # current animation state

    # -- move scheduling ----------------------------------------------------
    def enqueue(self, name, d, record=True):
        self.queue.append((name, d, record))

    def scramble(self, n=25):
        if self.busy():
            return
        for _ in range(n):
            name = random.choice(list(MOVES))
            d = random.choice((1, -1))
            self.enqueue(name, d, record=True)

    def solve(self):
        """Queue the inverse of the whole history, in reverse order."""
        if self.busy():
            return
        for name, d in reversed(self.history):
            self.enqueue(name, -d, record=False)
        self.history = []

    def busy(self):
        return self.anim is not None or bool(self.queue)

    # -- animation ----------------------------------------------------------
    def _start(self, name, d, record):
        axis, coord, base = MOVES[name]
        d = d * base
        idx = AXIS_INDEX[axis]
        layer = [c for c in self.cubies if c.pos[idx] == coord]
        self.anim = {
            'cubies': layer, 'axis': axis, 'idx': idx, 'd': d,
            'angle': 0.0, 'target': d * 90.0, 'record': record,
            'name': name, 'raw_d': d // abs(d),
        }
        self._anim_name = name

    def update(self):
        """Advance any running animation; pull the next queued move if idle."""
        if self.anim is None:
            if self.queue:
                name, d, record = self.queue.pop(0)
                self._start(name, d, record)
            else:
                return

        a = self.anim
        step = ANIM_SPEED if a['target'] > 0 else -ANIM_SPEED
        a['angle'] += step
        if abs(a['angle']) >= 90.0:
            # Commit the logical rotation.
            axis, d = a['axis'], a['raw_d']
            for c in a['cubies']:
                c.apply(axis, d)
            if a['record']:
                # store the user-facing move so solve() can invert it
                self.history.append((a['name'], a['raw_d'] // MOVES[a['name']][2]))
            self.anim = None

    # -- rendering ----------------------------------------------------------
    def draw(self):
        anim = self.anim
        for c in self.cubies:
            glPushMatrix()
            if anim and c in anim['cubies']:
                ax = AXIS_VEC[anim['axis']]
                glRotatef(anim['angle'], *ax)
            glTranslatef(c.pos[0] * SPACING, c.pos[1] * SPACING, c.pos[2] * SPACING)
            self._draw_cubie(c)
            glPopMatrix()

    @staticmethod
    def _draw_cubie(cubie):
        # Colored faces
        glBegin(GL_QUADS)
        for normal, verts in FACE_GEOM.items():
            glColor3fv(cubie.colors.get(normal, DARK))
            for v in verts:
                glVertex3fv(v)
        glEnd()
        # Black edges for definition
        glColor3f(0, 0, 0)
        glLineWidth(2.0)
        for verts in FACE_GEOM.values():
            glBegin(GL_LINE_LOOP)
            for v in verts:
                glVertex3fv(v)
            glEnd()


# Lines drawn in the top-left corner so the controls are always visible.
HUD_LINES = [
    "FACE TURNS  (hold SHIFT = reverse direction)",
    "   U - Up (top) face        R - Right face",
    "   D - Down (bottom) face   F - Front face",
    "   L - Left face            B - Back face",
    "",
    "VIEW    drag mouse / arrow keys to rotate",
    "S       scramble       ENTER   solve",
    "BACKSPACE  reset       ESC     quit",
]


def draw_hud(font, lines, win_w, win_h):
    """Draw 2D text overlay in screen space, on top of the 3D scene."""
    glDisable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    y = win_h - 8
    for line in lines:
        y -= 19
        if not line:
            continue
        surf = font.render(line, True, (235, 235, 245))
        data = pygame.image.tobytes(surf, "RGBA", True)
        glWindowPos2i(12, y)
        glDrawPixels(surf.get_width(), surf.get_height(),
                     GL_RGBA, GL_UNSIGNED_BYTE, data)
    glDisable(GL_BLEND)
    glEnable(GL_DEPTH_TEST)


def main():
    pygame.init()
    width, height = 900, 700
    pygame.display.set_mode((width, height), DOUBLEBUF | OPENGL)
    pygame.display.set_caption("3D Rubik's Cube  -  U D L R F B (Shift=reverse)  S=scramble  Enter=solve")
    hud_font = pygame.font.SysFont("Consolas", 15)

    glEnable(GL_DEPTH_TEST)
    glClearColor(0.12, 0.13, 0.16, 1.0)
    glMatrixMode(GL_PROJECTION)
    gluPerspective(40, width / height, 1.0, 60.0)
    glMatrixMode(GL_MODELVIEW)

    cube = RubiksCube()
    rot_x, rot_y = 25.0, -35.0
    dragging = False
    last_mouse = (0, 0)

    clock = pygame.time.Clock()
    print(__doc__)

    while True:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit(); sys.exit()

            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    pygame.quit(); sys.exit()
                elif event.key == K_s:
                    cube.scramble()
                elif event.key in (K_RETURN, K_KP_ENTER):
                    cube.solve()
                elif event.key == K_BACKSPACE:
                    cube.reset()
                else:
                    # face turns
                    keymap = {K_u: 'U', K_d: 'D', K_l: 'L',
                              K_r: 'R', K_f: 'F', K_b: 'B'}
                    if event.key in keymap and not cube.busy():
                        prime = bool(event.mod & KMOD_SHIFT)
                        cube.enqueue(keymap[event.key], -1 if prime else 1, record=True)

            elif event.type == MOUSEBUTTONDOWN and event.button == 1:
                dragging = True
                last_mouse = event.pos
            elif event.type == MOUSEBUTTONUP and event.button == 1:
                dragging = False
            elif event.type == MOUSEMOTION and dragging:
                dx = event.pos[0] - last_mouse[0]
                dy = event.pos[1] - last_mouse[1]
                rot_y += dx * 0.5
                rot_x += dy * 0.5
                last_mouse = event.pos

        # Arrow keys for view rotation
        keys = pygame.key.get_pressed()
        if keys[K_LEFT]:  rot_y -= 2
        if keys[K_RIGHT]: rot_y += 2
        if keys[K_UP]:    rot_x -= 2
        if keys[K_DOWN]:  rot_x += 2

        cube.update()

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        gluLookAt(0, 0, 16, 0, 0, 0, 0, 1, 0)
        glRotatef(rot_x, 1, 0, 0)
        glRotatef(rot_y, 0, 1, 0)
        cube.draw()
        draw_hud(hud_font, HUD_LINES, width, height)
        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
