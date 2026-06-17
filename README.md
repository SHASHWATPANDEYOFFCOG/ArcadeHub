# ArcadeHub

A small collection of games — two desktop Python games and a full-stack web "Arcade Hub".

## Contents

| Path | What it is |
|------|------------|
| `game.py` | 3D Rubik's Cube (Python, pygame + PyOpenGL) — turn, scramble, auto-solve |
| `chess_game.py` | Chess (Python, pygame) — full rules + threaded computer opponent with difficulty levels |
| `website/` | **Arcade Hub** — Node + Express site hosting browser versions of Chess and a 3D Rubik's Cube, with an in-memory leaderboard |

## Desktop games (Python)

Requires Python 3 with `pygame` (or `pygame-ce`), `PyOpenGL`, and `numpy`:

```bash
pip install pygame-ce PyOpenGL numpy
python game.py          # Rubik's cube
python chess_game.py    # Chess
```

## Web app (Arcade Hub)

Requires Node.js:

```bash
cd website
npm install
npm start
# open http://localhost:3000
```

- **Chess** — full rules, click-to-move, computer opponent (3 difficulties). Win to score points.
- **3D Rubik's Cube** — Three.js cube; scramble and race the timer.
- **Leaderboard** — scores kept in server memory (reset on restart).

> The cube page loads Three.js from a CDN, so the web app needs an internet connection.
