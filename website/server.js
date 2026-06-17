/*
 * Arcade Hub - Express backend
 * ----------------------------
 * Serves the static frontend and exposes a small leaderboard API.
 * Scores are kept in process memory only (no database). Restarting the
 * server clears them.
 */
const path = require('path');
const express = require('express');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// ---------------------------------------------------------------------------
// In-memory leaderboard
// ---------------------------------------------------------------------------
// Each game defines how its scores are ranked.
//   order 'asc'  -> lower is better (e.g. solve time)
//   order 'desc' -> higher is better (e.g. points)
const GAMES = {
  chess: { order: 'desc', unit: 'pts', label: 'Chess' },
  rubik: { order: 'asc', unit: 's', label: "Rubik's Cube" },
};

const MAX_ENTRIES = 10;

// Seed a few entries so the boards aren't empty on first load.
const boards = {
  chess: [
    { name: 'Garry',  score: 9, at: Date.now() },
    { name: 'Magnus', score: 6, at: Date.now() },
  ],
  rubik: [
    { name: 'SpeedCuber', score: 14.2, at: Date.now() },
    { name: 'Alex',       score: 42.7, at: Date.now() },
  ],
};

function sortBoard(game) {
  const order = GAMES[game].order;
  boards[game].sort((a, b) => (order === 'asc' ? a.score - b.score : b.score - a.score));
  boards[game] = boards[game].slice(0, MAX_ENTRIES);
}
Object.keys(boards).forEach(sortBoard);

// GET all leaderboards (with metadata)
app.get('/api/leaderboard', (req, res) => {
  res.json({ games: GAMES, boards });
});

// GET one game's leaderboard
app.get('/api/leaderboard/:game', (req, res) => {
  const { game } = req.params;
  if (!GAMES[game]) return res.status(404).json({ error: 'unknown game' });
  res.json({ game, meta: GAMES[game], board: boards[game] });
});

// POST a new score: { name, score }
app.post('/api/score/:game', (req, res) => {
  const { game } = req.params;
  if (!GAMES[game]) return res.status(404).json({ error: 'unknown game' });

  let { name, score } = req.body || {};
  score = Number(score);
  if (!Number.isFinite(score)) {
    return res.status(400).json({ error: 'score must be a number' });
  }
  name = (typeof name === 'string' && name.trim()) ? name.trim().slice(0, 20) : 'Anonymous';

  const entry = { name, score, at: Date.now() };
  boards[game].push(entry);
  sortBoard(game);

  const rank = boards[game].findIndex((e) => e === entry);
  res.json({ ok: true, board: boards[game], rank: rank >= 0 ? rank + 1 : null });
});

app.listen(PORT, () => {
  console.log(`Arcade Hub running at http://localhost:${PORT}`);
});
