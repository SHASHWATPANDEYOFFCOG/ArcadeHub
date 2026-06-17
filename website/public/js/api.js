// Small shared helpers: player name + leaderboard API.
export function getPlayerName() {
  return localStorage.getItem('playerName') || 'Anonymous';
}
export function setPlayerName(name) {
  localStorage.setItem('playerName', name);
}

export async function fetchAllBoards() {
  const r = await fetch('/api/leaderboard');
  return r.json();
}

export async function submitScore(game, score) {
  const r = await fetch(`/api/score/${game}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: getPlayerName(), score }),
  });
  return r.json();
}

export function toast(msg) {
  let el = document.querySelector('.toast');
  if (!el) {
    el = document.createElement('div');
    el.className = 'toast';
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), 2200);
}

// Renders a player-name input bound to localStorage into #player-box.
export function mountPlayerBox() {
  const box = document.getElementById('player-box');
  if (!box) return;
  box.innerHTML = `<span class="muted">Player:</span>
    <input id="player-name" maxlength="20" placeholder="Your name" />`;
  const input = box.querySelector('#player-name');
  input.value = getPlayerName() === 'Anonymous' ? '' : getPlayerName();
  input.addEventListener('change', () => setPlayerName(input.value.trim() || 'Anonymous'));
}
