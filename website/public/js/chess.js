import * as C from '/js/chess-engine.js';
import { mountPlayerBox, submitScore, toast } from '/js/api.js';

mountPlayerBox();

const GLYPH = { K:'♚', Q:'♛', R:'♜', B:'♝', N:'♞', P:'♟' };
const DIFF = { 1: ['Easy', 2], 2: ['Medium', 3], 3: ['Hard', 4] };

let state = C.newState();
let history = [];
let selected = null;        // [r,c]
let selMoves = [];
let vsAi = false;
let aiColor = 'b';
let diff = 2;
let status = 'play';
let thinking = false;
let scored = false;         // prevent double-submitting a win

const boardEl = document.getElementById('chessboard');
const statusEl = document.getElementById('status');
const modeEl = document.getElementById('mode');

function refreshStatus() { status = C.gameStatus(state); }

function render() {
  boardEl.innerHTML = '';
  let checkSq = null;
  if (C.inCheck(state, state.turn)) checkSq = C.findKing(state.board, state.turn);

  for (let r=0;r<8;r++) for (let c=0;c<8;c++) {
    const sq = document.createElement('div');
    sq.className = 'sq ' + ((r+c)%2===0 ? 'light' : 'dark');
    if (checkSq && checkSq[0]===r && checkSq[1]===c) sq.classList.add('check');
    if (selected && selected[0]===r && selected[1]===c) sq.classList.add('sel');
    const p = state.board[r][c];
    if (p) { sq.textContent = GLYPH[p[1]]; sq.classList.add(p[0]==='w'?'wp':'bp'); }
    const mv = selMoves.find(m => m[2]===r && m[3]===c);
    if (mv) {
      const mark = document.createElement('div');
      const capture = state.board[r][c] || mv[4]==='ep';
      mark.className = capture ? 'ring' : 'dot';
      sq.appendChild(mark);
    }
    sq.addEventListener('click', () => onClick(r,c));
    boardEl.appendChild(sq);
  }

  const turnName = state.turn==='w' ? 'White' : 'Black';
  if (status==='checkmate') {
    const winner = state.turn==='w' ? 'Black' : 'White';
    statusEl.textContent = `Checkmate — ${winner} wins!`;
  } else if (status==='stalemate') {
    statusEl.textContent = 'Stalemate — draw';
  } else if (thinking) {
    statusEl.textContent = `Computer is thinking… (${DIFF[diff][0]})`;
  } else {
    statusEl.textContent = `${turnName} to move` + (checkSq ? '  — check!' : '');
  }
  modeEl.textContent = vsAi ? `vs Computer · ${DIFF[diff][0]}` : '2 players';
}

function maybeScore() {
  // Award points when the human checkmates the computer.
  if (scored || !vsAi || status!=='checkmate') return;
  const loser = state.turn;                 // side to move is mated
  const winner = C.enemy(loser);
  if (winner !== aiColor) {                  // human (not the AI) won
    scored = true;
    const pts = DIFF[diff][1] + 1;           // 3 / 4 / 5 points by difficulty
    submitScore('chess', pts).then(res => {
      toast(`You won! +${pts} pts (rank #${res.rank})`);
    }).catch(()=>{});
  }
}

function afterMove() {
  selected = null; selMoves = [];
  refreshStatus();
  render();
  maybeScore();
  if (vsAi && state.turn===aiColor && status==='play') {
    thinking = true; render();
    // Yield to the browser so "thinking…" paints before the search blocks.
    setTimeout(() => {
      const mv = C.aiMove(state, DIFF[diff][1]);
      thinking = false;
      if (mv) { history.push(state); state = C.applyMove(state, mv); }
      selected=null; selMoves=[];
      refreshStatus(); render(); maybeScore();
    }, 30);
  }
}

function onClick(r,c) {
  if (status!=='play' || thinking) return;
  if (vsAi && state.turn===aiColor) return;
  const chosen = selMoves.find(m => m[2]===r && m[3]===c);
  if (chosen) { history.push(state); state = C.applyMove(state, chosen); afterMove(); return; }
  const p = state.board[r][c];
  if (p && p[0]===state.turn) {
    selected = [r,c];
    selMoves = C.legalMoves(state).filter(m => m[0]===r && m[1]===c);
  } else { selected=null; selMoves=[]; }
  render();
}

// Controls
document.getElementById('new').onclick = () => {
  state = C.newState(); history=[]; selected=null; selMoves=[]; status='play'; scored=false; thinking=false; render();
};
document.getElementById('undo').onclick = () => {
  if (!history.length || thinking) return;
  state = history.pop();
  if (vsAi && state.turn===aiColor && history.length) state = history.pop();
  selected=null; selMoves=[]; scored=false; refreshStatus(); render();
};
document.getElementById('toggle-ai').onclick = () => {
  vsAi = !vsAi;
  aiColor = vsAi ? C.enemy(state.turn) : 'b';
  scored = false;
  render();
  if (vsAi && state.turn===aiColor && status==='play') afterMove();
};
document.querySelectorAll('[data-diff]').forEach(b => {
  b.onclick = () => { diff = Number(b.dataset.diff); render(); };
});

render();
