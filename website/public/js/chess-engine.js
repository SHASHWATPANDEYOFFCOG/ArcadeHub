// Chess rules engine (ES module). Ported from the perft-verified Python version.
// Board: 8x8 array, row 0 = rank 8 (top). Pieces are 2-char strings like 'wP', or null.

const START = [
  ['bR','bN','bB','bQ','bK','bB','bN','bR'],
  ['bP','bP','bP','bP','bP','bP','bP','bP'],
  [null,null,null,null,null,null,null,null],
  [null,null,null,null,null,null,null,null],
  [null,null,null,null,null,null,null,null],
  [null,null,null,null,null,null,null,null],
  ['wP','wP','wP','wP','wP','wP','wP','wP'],
  ['wR','wN','wB','wQ','wK','wB','wN','wR'],
];

export const VALUE = { P:100, N:320, B:330, R:500, Q:900, K:20000 };

export function newState() {
  return {
    board: START.map(row => row.slice()),
    turn: 'w',
    ep: null,                              // "r,c" string or null
    castle: new Set(['wK','wQ','bK','bQ']),
  };
}

const inB = (r,c) => r>=0 && r<8 && c>=0 && c<8;
export const enemy = (col) => col === 'w' ? 'b' : 'w';

export function findKing(board, color) {
  const t = color + 'K';
  for (let r=0;r<8;r++) for (let c=0;c<8;c++) if (board[r][c]===t) return [r,c];
  return null;
}

export function isAttacked(board, r, c, by) {
  // pawns: a square is attacked by a 'by' pawn sitting one row toward 'by' home
  const pd = by === 'w' ? 1 : -1;
  for (const dc of [-1,1]) {
    const pr=r+pd, pc=c+dc;
    if (inB(pr,pc) && board[pr][pc] === by+'P') return true;
  }
  const kn = [[-2,-1],[-2,1],[-1,-2],[-1,2],[1,-2],[1,2],[2,-1],[2,1]];
  for (const [dr,dc] of kn) { const nr=r+dr,nc=c+dc; if (inB(nr,nc)&&board[nr][nc]===by+'N') return true; }
  for (let dr=-1;dr<=1;dr++) for (let dc=-1;dc<=1;dc++) {
    if (dr||dc){const nr=r+dr,nc=c+dc; if (inB(nr,nc)&&board[nr][nc]===by+'K') return true;}
  }
  const slides = [[-1,0,'RQ'],[1,0,'RQ'],[0,-1,'RQ'],[0,1,'RQ'],
                  [-1,-1,'BQ'],[-1,1,'BQ'],[1,-1,'BQ'],[1,1,'BQ']];
  for (const [dr,dc,kinds] of slides) {
    let nr=r+dr,nc=c+dc;
    while (inB(nr,nc)) {
      const p=board[nr][nc];
      if (p) { if (p[0]===by && kinds.includes(p[1])) return true; break; }
      nr+=dr; nc+=dc;
    }
  }
  return false;
}

function tryStep(board,r,c,dr,dc,color,moves){
  const nr=r+dr,nc=c+dc;
  if (inB(nr,nc)){ const q=board[nr][nc]; if (!q||q[0]!==color) moves.push([r,c,nr,nc,null]); }
}

function pawnMoves(state,r,c,color,moves){
  const b=state.board;
  const d = color==='w' ? -1 : 1;
  const startRow = color==='w' ? 6 : 1;
  const promo = color==='w' ? 0 : 7;
  if (inB(r+d,c) && !b[r+d][c]) {
    moves.push([r,c,r+d,c, r+d===promo ? 'promo' : null]);
    if (r===startRow && !b[r+2*d][c]) moves.push([r,c,r+2*d,c,'double']);
  }
  for (const dc of [-1,1]) {
    const nr=r+d,nc=c+dc;
    if (!inB(nr,nc)) continue;
    const q=b[nr][nc];
    if (q && q[0]!==color) moves.push([r,c,nr,nc, nr===promo?'promo':null]);
    else if (state.ep === `${nr},${nc}`) moves.push([r,c,nr,nc,'ep']);
  }
}

function castleMoves(state,r,c,color,moves){
  const b=state.board;
  if (isAttacked(b,r,c,enemy(color))) return;
  const back = color==='w' ? 7 : 0;
  if (r!==back || c!==4) return;
  if (state.castle.has(color+'K')) {
    if (!b[back][5] && !b[back][6] && b[back][7]===color+'R'
        && !isAttacked(b,back,5,enemy(color)) && !isAttacked(b,back,6,enemy(color)))
      moves.push([r,c,back,6,'castleK']);
  }
  if (state.castle.has(color+'Q')) {
    if (!b[back][1] && !b[back][2] && !b[back][3] && b[back][0]===color+'R'
        && !isAttacked(b,back,3,enemy(color)) && !isAttacked(b,back,2,enemy(color)))
      moves.push([r,c,back,2,'castleQ']);
  }
}

export function genPseudo(state, color) {
  const b=state.board, moves=[];
  for (let r=0;r<8;r++) for (let c=0;c<8;c++) {
    const p=b[r][c];
    if (!p || p[0]!==color) continue;
    const k=p[1];
    if (k==='P') pawnMoves(state,r,c,color,moves);
    else if (k==='N') for (const [dr,dc] of [[-2,-1],[-2,1],[-1,-2],[-1,2],[1,-2],[1,2],[2,-1],[2,1]]) tryStep(b,r,c,dr,dc,color,moves);
    else if (k==='K') {
      for (let dr=-1;dr<=1;dr++) for (let dc=-1;dc<=1;dc++) if (dr||dc) tryStep(b,r,c,dr,dc,color,moves);
      castleMoves(state,r,c,color,moves);
    } else {
      const dirs = k==='R' ? [[-1,0],[1,0],[0,-1],[0,1]]
                 : k==='B' ? [[-1,-1],[-1,1],[1,-1],[1,1]]
                 : [[-1,0],[1,0],[0,-1],[0,1],[-1,-1],[-1,1],[1,-1],[1,1]];
      for (const [dr,dc] of dirs) {
        let nr=r+dr,nc=c+dc;
        while (inB(nr,nc)) {
          const q=b[nr][nc];
          if (!q) moves.push([r,c,nr,nc,null]);
          else { if (q[0]!==color) moves.push([r,c,nr,nc,null]); break; }
          nr+=dr; nc+=dc;
        }
      }
    }
  }
  return moves;
}

export function applyMove(state, move) {
  const s = { board: state.board.map(row=>row.slice()), turn: enemy(state.turn), ep:null, castle: new Set(state.castle) };
  const b=s.board;
  const [fr,fc,tr,tc,flag]=move;
  const piece=b[fr][fc], color=piece[0];
  b[fr][fc]=null; b[tr][tc]=piece;

  if (flag==='double') s.ep = `${(fr+tr)/2},${fc}`;
  else if (flag==='ep') b[fr][tc]=null;
  else if (flag==='promo') b[tr][tc]=color+'Q';
  else if (flag==='castleK') { b[tr][7]=null; b[tr][5]=color+'R'; }
  else if (flag==='castleQ') { b[tr][0]=null; b[tr][3]=color+'R'; }

  if (piece[1]==='K') { s.castle.delete(color+'K'); s.castle.delete(color+'Q'); }
  if (piece[1]==='R') {
    const back = color==='w'?7:0;
    if (fr===back && fc===0) s.castle.delete(color+'Q');
    else if (fr===back && fc===7) s.castle.delete(color+'K');
  }
  for (const col of ['w','b']) {
    const back = col==='w'?7:0;
    if (b[back][0]!==col+'R') s.castle.delete(col+'Q');
    if (b[back][7]!==col+'R') s.castle.delete(col+'K');
  }
  return s;
}

export function legalMoves(state, color=state.turn) {
  const out=[];
  for (const mv of genPseudo(state,color)) {
    const ns=applyMove(state,mv);
    const [kr,kc]=findKing(ns.board,color);
    if (!isAttacked(ns.board,kr,kc,enemy(color))) out.push(mv);
  }
  return out;
}

export function inCheck(state,color){ const [r,c]=findKing(state.board,color); return isAttacked(state.board,r,c,enemy(color)); }

export function gameStatus(state){
  if (legalMoves(state).length) return 'play';
  return inCheck(state, state.turn) ? 'checkmate' : 'stalemate';
}

// ---- AI: negamax + alpha-beta ----
function evaluate(state,color){
  let s=0;
  for (const row of state.board) for (const p of row) if (p) s += (p[0]===color?VALUE[p[1]]:-VALUE[p[1]]);
  return s;
}
function order(state,moves){
  const b=state.board;
  return moves.slice().sort((a,bm)=> (b[bm[2]][bm[3]]?1:0) - (b[a[2]][a[3]]?1:0));
}
function negamax(state,depth,alpha,beta,color){
  const moves=legalMoves(state,color);
  if (!moves.length) return inCheck(state,color) ? [-100000-depth,null] : [0,null];
  if (depth===0) return [evaluate(state,color),null];
  let best=-1e9, bestMove=null;
  for (const mv of order(state,moves)) {
    const [v]=negamax(applyMove(state,mv),depth-1,-beta,-alpha,enemy(color));
    const val=-v;
    if (val>best){best=val;bestMove=mv;}
    if (val>alpha) alpha=val;
    if (alpha>=beta) break;
  }
  return [best,bestMove];
}
export function aiMove(state, depth=3){
  return negamax(state,depth,-1e9,1e9,state.turn)[1];
}
