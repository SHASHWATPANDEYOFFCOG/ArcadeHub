import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { mountPlayerBox, submitScore, toast } from '/js/api.js';

mountPlayerBox();

// ---- colors per outward face normal (matches game.py) ----
const COLORS = {
  '1,0,0':  0xcc1414,   // +X right  red
  '-1,0,0': 0xff7300,   // -X left   orange
  '0,1,0':  0xfafafa,   // +Y up     white
  '0,-1,0': 0xffe600,   // -Y down   yellow
  '0,0,1':  0x1aa64d,   // +Z front  green
  '0,0,-1': 0x0040d9,   // -Z back   blue
};
const DARK = 0x111418;

// Move -> [axis, layerCoord, baseDir]   (same convention as game.py)
const MOVES = {
  U: ['y', 1, -1], D: ['y', -1, 1],
  R: ['x', 1, -1], L: ['x', -1, 1],
  F: ['z', 1, -1], B: ['z', -1, 1],
};
const AXIS_INDEX = { x: 0, y: 1, z: 2 };
const AXIS_VEC = { x: new THREE.Vector3(1,0,0), y: new THREE.Vector3(0,1,0), z: new THREE.Vector3(0,0,1) };
const SP = 1.05;                  // spacing
const TURN_MS = 180;              // animation duration per quarter turn

function rotate90(v, axis, d) {
  const [x,y,z] = v;
  if (axis==='x') return [x, -d*z, d*y];
  if (axis==='y') return [d*z, y, -d*x];
  return [-d*y, d*x, z];
}
const key = (v) => v.join(',');

// ---- scene ----
const canvas = document.getElementById('rubik-canvas');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
function sizeRenderer(){ renderer.setSize(canvas.clientWidth, canvas.clientHeight, false); }
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
camera.position.set(4.2, 4.2, 5.5);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enablePan = false;
controls.minDistance = 4; controls.maxDistance = 14;
scene.add(new THREE.AmbientLight(0xffffff, 0.85));
const dl = new THREE.DirectionalLight(0xffffff, 0.6); dl.position.set(5,8,6); scene.add(dl);

// Box face material order in three.js geometry: +X,-X,+Y,-Y,+Z,-Z
const FACE_ORDER = ['1,0,0','-1,0,0','0,1,0','0,-1,0','0,0,1','0,0,-1'];

const cubies = [];   // { mesh, pos:[x,y,z], colors:{normalKey:hex} }

function makeCubie(pos) {
  const colors = {};
  for (const [axis, idx] of Object.entries(AXIS_INDEX)) {
    for (const sign of [1,-1]) {
      if (pos[idx]===sign) {
        const n = [0,0,0]; n[idx]=sign;
        colors[key(n)] = COLORS[key(n)];
      }
    }
  }
  const mats = FACE_ORDER.map(k => new THREE.MeshStandardMaterial({
    color: colors[k] ?? DARK, roughness: 0.45, metalness: 0.05,
  }));
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(0.96,0.96,0.96), mats);
  // thin black edges
  mesh.add(new THREE.LineSegments(
    new THREE.EdgesGeometry(mesh.geometry),
    new THREE.LineBasicMaterial({ color: 0x000000 })));
  scene.add(mesh);
  return { mesh, pos: pos.slice(), colors };
}

function syncMesh(cb) {
  cb.mesh.position.set(cb.pos[0]*SP, cb.pos[1]*SP, cb.pos[2]*SP);
  cb.mesh.quaternion.identity();
  cb.mesh.material.forEach((m, i) => m.color.setHex(cb.colors[FACE_ORDER[i]] ?? DARK));
}

function buildCube() {
  cubies.forEach(c => scene.remove(c.mesh));
  cubies.length = 0;
  for (const x of [-1,0,1]) for (const y of [-1,0,1]) for (const z of [-1,0,1]) {
    const cb = makeCubie([x,y,z]);
    syncMesh(cb);
    cubies.push(cb);
  }
}
buildCube();

// ---- move engine ----
let history = [];          // recorded moves [name, dir]
let queue = [];            // pending [name, dir, record]
let anim = null;
let scrambled = false;
let timerStart = 0, timerRunning = false, finished = false;

function enqueue(name, dir, record=true){ queue.push([name,dir,record]); }

function startMove(name, dir, record) {
  const [axis, coord, base] = MOVES[name];
  const d = dir * base;
  const idx = AXIS_INDEX[axis];
  const layer = cubies.filter(c => c.pos[idx]===coord);
  const pivot = new THREE.Group();
  scene.add(pivot);
  layer.forEach(c => pivot.attach(c.mesh));
  anim = { name, dir, base, axis, idx, layer, pivot, record,
           t: 0, target: d * Math.PI/2 };
}

function finishMove() {
  const a = anim;
  a.layer.forEach(c => scene.attach(c.mesh));   // bake world transform
  // update logical model
  const d = a.dir * a.base;
  a.layer.forEach(c => {
    c.pos = rotate90(c.pos, a.axis, d);
    const nc = {};
    for (const [k,v] of Object.entries(c.colors)) nc[key(rotate90(k.split(',').map(Number), a.axis, d))] = v;
    c.colors = nc;
    syncMesh(c);
  });
  scene.remove(a.pivot);
  if (a.record) history.push([a.name, a.dir]);
  anim = null;
  checkSolved();
}

function isSolved() {
  for (const c of cubies)
    for (const [k,v] of Object.entries(c.colors))
      if (v !== COLORS[k]) return false;
  return true;
}

function checkSolved() {
  if (scrambled && !queue.length && !anim && isSolved()) {
    scrambled = false;
    if (timerRunning && !finished) {
      timerRunning = false; finished = true;
      const secs = ((performance.now() - timerStart)/1000);
      const rounded = Math.round(secs*10)/10;
      submitScore('rubik', rounded).then(res => {
        toast(`Solved in ${rounded}s! Rank #${res.rank}`);
      }).catch(()=>{});
    }
  }
}

function doMove(name, dir) {
  if (anim || queue.length) return;     // ignore during animation/queued runs
  enqueue(name, dir, true);
}

function scramble() {
  if (anim || queue.length) return;
  buildCube(); history = [];            // reset to solved, then scramble
  const names = Object.keys(MOVES);
  for (let i=0;i<25;i++) enqueue(names[(Math.random()*6)|0], Math.random()<0.5?1:-1, true);
  // mark scrambled & start timer once the scramble finishes (handled below)
  pendingTimerStart = true;
}

function solve() {
  if (anim || queue.length) return;
  for (let i=history.length-1;i>=0;i--) enqueue(history[i][0], -history[i][1], false);
  history = [];
}

let pendingTimerStart = false;

// ---- animation loop ----
let last = performance.now();
function loop(now) {
  requestAnimationFrame(loop);
  const dt = now - last; last = now;

  if (!anim && queue.length) {
    const [name, dir, record] = queue.shift();
    startMove(name, dir, record);
  }
  if (anim) {
    const step = (dt / TURN_MS) * (Math.PI/2) * Math.sign(anim.target);
    anim.t += step;
    if (Math.abs(anim.t) >= Math.abs(anim.target)) {
      anim.pivot.rotation.set(0,0,0);
      anim.pivot.setRotationFromAxisAngle(AXIS_VEC[anim.axis], anim.target);
      finishMove();
    } else {
      anim.pivot.setRotationFromAxisAngle(AXIS_VEC[anim.axis], anim.t);
    }
  }
  // When a scramble sequence finishes, arm the timer.
  if (pendingTimerStart && !anim && !queue.length) {
    pendingTimerStart = false;
    scrambled = true; finished = false;
    timerStart = performance.now(); timerRunning = true;
  }
  if (timerRunning) {
    const s = (performance.now() - timerStart)/1000;
    timerEl.textContent = s.toFixed(1) + 's';
  }

  controls.update();
  renderer.render(scene, camera);
}

// ---- UI wiring ----
const timerEl = document.getElementById('timer');
document.querySelectorAll('[data-move]').forEach(btn => {
  btn.onclick = () => {
    const m = btn.dataset.move;     // e.g. "U" or "U'"
    const prime = m.endsWith("'");
    doMove(m[0], prime ? -1 : 1);
  };
});
document.getElementById('scramble').onclick = scramble;
document.getElementById('solve').onclick = solve;
document.getElementById('reset').onclick = () => {
  if (anim || queue.length) return;
  buildCube(); history=[]; scrambled=false; timerRunning=false; finished=false;
  timerEl.textContent = '0.0s';
};

window.addEventListener('keydown', (e) => {
  const k = e.key.toUpperCase();
  if (MOVES[k]) doMove(k, e.shiftKey ? -1 : 1);
});

function onResize(){ sizeRenderer(); const r = canvas.clientWidth/canvas.clientHeight; camera.aspect=r; camera.updateProjectionMatrix(); }
window.addEventListener('resize', onResize);
onResize();
requestAnimationFrame(loop);
