'use strict';
// Roadster POV meme clip — deterministic canvas renderer.
// window.renderFrame(t) draws the frame at time t (seconds). Timeline is mirrored in audio.py.

const W = 1080, H = 1350, CAP = 300;            // caption bar height
const SCX = W / 2, SCY = CAP + (H - CAP) / 2;    // scene centre on screen
const DUR = 15.5;
const cv = document.getElementById('c');
const ctx = cv.getContext('2d');

// ---------- utils ----------
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const lerp = (a, b, t) => a + (b - a) * t;
const seg = (t, a, b) => clamp((t - a) / (b - a), 0, 1);
const eio = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
const eo = t => 1 - Math.pow(1 - t, 3);
const ei = t => t * t * t;
const eob = t => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); };
const hash = n => { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
const wob = (t, f, s) => Math.sin(t * f + s) * .6 + Math.sin(t * f * 2.13 + s * 1.7) * .3 + Math.sin(t * f * 3.7 + s * .3) * .1;
function rng(seed) { return function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function hex2rgb(h) { const n = parseInt(h.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
function mix(a, b, k) { const A = hex2rgb(a), B = hex2rgb(b); return `rgb(${A.map((v, i) => Math.round(lerp(v, B[i], k))).join(',')})`; }

function rrPoly(pts, rad) {
  const n = pts.length; ctx.beginPath();
  for (let i = 0; i < n; i++) {
    const p0 = pts[(i - 1 + n) % n], p1 = pts[i], p2 = pts[(i + 1) % n];
    if (i === 0) ctx.moveTo((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2);
    ctx.arcTo(p1[0], p1[1], (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2, rad);
  }
  ctx.closePath();
}
function poly(pts) { ctx.beginPath(); pts.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])); ctx.closePath(); }
function rrect(x, y, w, h, r) { ctx.beginPath(); ctx.roundRect(x, y, w, h, r); }
function circ(x, y, r) { ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); }

// soft puff sprites
function sprite(fn) { const c = document.createElement('canvas'); c.width = c.height = 128; fn(c.getContext('2d')); return c; }
const PUFF = sprite(g => { const r = g.createRadialGradient(64, 64, 0, 64, 64, 64); r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(.45, 'rgba(235,246,255,.75)'); r.addColorStop(1, 'rgba(220,235,255,0)'); g.fillStyle = r; g.fillRect(0, 0, 128, 128); });
const CLOUD = sprite(g => { const r = g.createRadialGradient(56, 52, 0, 64, 64, 64); r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(.62, 'rgba(244,240,255,.95)'); r.addColorStop(.85, 'rgba(225,215,245,.5)'); r.addColorStop(1, 'rgba(220,210,240,0)'); g.fillStyle = r; g.fillRect(0, 0, 128, 128); });

// ---------- roadster motion ----------
function roadVel(t) {
  if (t < 6.8) return 0;
  if (t < 8.2) return 30;
  if (t < 9.0) return lerp(30, 1100, eio(seg(t, 8.2, 9.0)));
  if (t < 11.3) return 1100;
  return lerp(1100, 6500, ei(seg(t, 11.3, 11.9)));
}
const XT = []; (function () { let x = 0; const dt = 1 / 600; for (let i = 0; i <= DUR * 600 + 2; i++) { XT.push(x); x += roadVel(i * dt) * dt; } })();
function roadX(t) { const i = clamp(t * 600, 0, XT.length - 2), i0 = Math.floor(i); return lerp(XT[i0], XT[i0 + 1], i - i0); }

function rState(t) {
  const s = { x: roadX(t), y: 0, rot: 0, dep: seg(t, 4.6, 5.0), down: 0, rear: 0, vib: 0 };
  if (t >= 5.0 && t < 5.6) { s.y = -7 * eio(seg(t, 5.0, 5.6)); s.down = .25 + .35 * seg(t, 5.0, 5.6); s.vib = 1.2 + 2.2 * seg(t, 5.0, 5.6); }
  else if (t >= 5.6 && t < 6.9) { const p = seg(t, 5.6, 6.9); s.y = lerp(-7, -420, eob(p)); s.down = 1.0; s.rot = -.07 * Math.sin(Math.PI * p); s.vib = 1.2; }
  else if (t >= 6.9) {
    s.y = -420 + Math.sin((t - 6.9) * 3.2) * 9; s.down = .55;
    if (t >= 8.2) {
      s.down = .35; s.rear = seg(t, 8.2, 8.7); s.rot = -.06 * Math.sin(Math.PI * seg(t, 8.2, 9.3));
      const fp = seg(t, 9.4, 10.1);
      if (fp > 0 && fp < 1) { s.rot += -Math.PI * 2 * eio(fp); s.y -= 70 * Math.sin(Math.PI * fp); }
      if (t > 11.3) { s.rear = 1.5; s.rot = .04; }
    }
  }
  return s;
}
const NOZ = [-104, -36, 36, 104];
const HEAD = [-2, -71, 17];

// ---------- camera ----------
function camera(t) {
  let x = 0, y = -281, z = 1.28, sh = 0;
  if (t < 2.4) { z = 1.28 + .08 * eio(seg(t, 0, 2.4)); }
  else if (t < 4.4) {
    const p = eio(seg(t, 2.4, 2.9)); x = lerp(0, -2, p); y = lerp(-281, -98, p); z = lerp(1.36, 4.9, p) + .2 * seg(t, 2.9, 4.4);
    if (t >= 3.75) sh = 7 * Math.max(0, 1 - (t - 3.75) / .25);
  } else if (t < 5.6) {
    const p = eio(seg(t, 4.4, 4.85)); x = lerp(-2, 0, p); y = lerp(-98, -140, p); z = lerp(5.1, 1.72, p) + .05 * seg(t, 4.85, 5.6);
    sh = 1 + 5 * seg(t, 5.0, 5.6);
  } else if (t < 8.2) {
    const p = eo(seg(t, 5.6, 6.7)); x = roadX(t); y = lerp(-140, -320, p); z = lerp(1.77, 1.12, p);
    sh = 22 * Math.pow(1 - seg(t, 5.6, 6.5), 2) + 1.5;
  } else if (t < 12) {
    const p = eio(seg(t, 8.2, 9.0)); x = roadX(Math.min(t, 11.3)) + 150 * p; y = -320 + 2 * p; z = lerp(1.12, 1.08, p); sh = 1.2;
  } else {
    x = -258; y = -104; z = 2.95 + .12 * seg(t, 12, DUR);
    if (t > 13.78) sh = 9 * Math.max(0, 1 - (t - 13.78) / .3);
  }
  return { x, y, z, sx: sh ? wob(t, 47, 1.3) * sh : 0, sy: sh ? wob(t, 53, 4.1) * sh : 0 };
}
function setLayer(cam, p) {
  const zl = 1 + (cam.z - 1) * p, dy = cam.y + 330;
  ctx.setTransform(zl, 0, 0, zl, SCX + cam.sx * p - cam.x * p * zl, SCY + cam.sy * p + (330 - dy * p) * zl);
  return zl;
}

// ---------- world generation ----------
const LEN = { sedan: 240, hatch: 212, suv: 252, van: 266, pickup: 284, box: 336, bus: 440, sad: 236 };
const PAL = ['#3a86ff', '#ffbe0b', '#8338ec', '#06d6a0', '#ef476f', '#f2f2f5', '#2b2d42', '#fb5607', '#118ab2', '#9b5de5', '#00bbf9', '#ff99c8', '#7bd389', '#4361ee'];
const EXPR = ['angry', 'angry', 'annoyed', 'bored', 'sleep', 'cry', 'angry', 'annoyed', 'angry'];
const FRONT = [], BACK = [];
(function () {
  const r = rng(1234);
  const mk = (type, cx, sc) => ({ type, x: cx, len: LEN[type] * sc, color: PAL[Math.floor(r() * PAL.length)], expr: EXPR[Math.floor(r() * EXPR.length)], seed: r() * 1000 });
  const ft = ['sedan', 'suv', 'hatch', 'van', 'pickup', 'sedan', 'suv', 'box'];
  FRONT.push(Object.assign(mk('sad', -292, 1), { color: '#d8c69c', expr: 'annoyed', sad: true }));
  let e = -292 - LEN.sad / 2;
  while (e > -2800) { const ty = ft[Math.floor(r() * ft.length)]; e -= 30 + r() * 22; const c = mk(ty, e - LEN[ty] / 2, 1); FRONT.push(c); e = c.x - c.len / 2; }
  e = 140;
  while (e < 7800) { const ty = ft[Math.floor(r() * ft.length)]; e += 30 + r() * 22; const c = mk(ty, e + LEN[ty] / 2, 1); FRONT.push(c); e = c.x + c.len / 2; }
  const bt = ['sedan', 'suv', 'bus', 'van', 'hatch', 'box', 'sedan', 'pickup'];
  e = -2800;
  while (e < 7800) { const ty = bt[Math.floor(r() * bt.length)]; e += 24 + r() * 26; const c = mk(ty, e + LEN[ty] * .86 / 2, .86); c.back = true; BACK.push(c); e = c.x + c.len / 2; }
  FRONT.sort((a, b) => a.x - b.x);
  // the car right in front of the roadster is always furious
  const fr = FRONT.find(c => c.x > 0); fr.expr = 'angry';
})();
const nearest = (lane, x) => lane.reduce((b, c) => Math.abs(c.x - x) < Math.abs(b.x - x) ? c : b);
const SAD = FRONT.find(c => c.sad);

const BG = { far: [], mid: [], palms: [], clouds: [], stars: [] };
(function () {
  const r = rng(99);
  let x = -1700; while (x < 2700) { const w = 70 + r() * 110, h = 150 + r() * 300; BG.far.push({ x, w, h }); x += w + 4 + r() * 30; }
  x = -1900; while (x < 3700) { const w = 80 + r() * 120, h = 110 + r() * 250; BG.mid.push({ x, w, h, s: r() * 100, ant: r() < .3 }); x += w + r() * 40; }
  x = -2400; while (x < 5800) { BG.palms.push({ x, h: 190 + r() * 130, lean: (r() - .5) * .3, s: r() * 10 }); x += 170 + r() * 260; }
  for (let i = 0; i < 16; i++) BG.clouds.push({ x: -1300 + i * 280 + r() * 200, y: -720 - r() * 380, s: .6 + r() * .9 });
  for (let i = 0; i < 110; i++) BG.stars.push({ x: r() * W, y: CAP + r() * 460, s: .8 + r() * 2.2, ph: r() * 6.28 });
})();

// ---------- faces ----------
function face(x, y, r, expr, o) {
  o = o || {}; const lk = o.look || [0, 0], t = o.t || 0;
  ctx.save(); ctx.translate(x, y);
  const red = expr === 'angry' || expr === 'determined';
  const g = ctx.createRadialGradient(-r * .35, -r * .45, r * .05, 0, 0, r);
  if (red) { g.addColorStop(0, '#ffab76'); g.addColorStop(.6, '#ff5a3c'); g.addColorStop(1, '#d9282f'); }
  else { g.addColorStop(0, '#fff1a6'); g.addColorStop(.55, '#ffd23f'); g.addColorStop(1, '#f4a024'); }
  circ(0, 0, r); ctx.fillStyle = g; ctx.fill();
  ctx.lineWidth = Math.max(1, r * .07); ctx.strokeStyle = red ? '#8f1d1d' : '#a8650c'; ctx.stroke();
  const K = '#3a2312'; ctx.fillStyle = K; ctx.strokeStyle = K; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  const ex = r * .36, ey = -r * .1, lx = lk[0] * r * .07, ly = lk[1] * r * .07;
  const E = (cx, cy, rx, ry) => { ctx.beginPath(); ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2); ctx.fill(); };
  const L = (p, w) => { ctx.lineWidth = w; ctx.beginPath(); ctx.moveTo(p[0], p[1]); for (let i = 2; i < p.length; i += 2) ctx.lineTo(p[i], p[i + 1]); ctx.stroke(); };
  const bigEyes = (sz) => {
    for (const s of [-1, 1]) {
      ctx.fillStyle = '#fff'; E(s * ex, ey, r * .19 * sz, r * .22 * sz);
      ctx.lineWidth = r * .05; ctx.beginPath(); ctx.ellipse(s * ex, ey, r * .19 * sz, r * .22 * sz, 0, 0, Math.PI * 2); ctx.stroke();
      ctx.fillStyle = K; E(s * ex + lx * 1.4, ey + ly * 1.4, r * .08, r * .09);
      ctx.lineWidth = r * .07; ctx.beginPath(); ctx.arc(s * ex, ey - r * .28, r * .2, Math.PI * 1.2, Math.PI * 1.8); ctx.stroke();
    }
  };
  switch (expr) {
    case 'angry':
    case 'determined':
      L([-ex - r * .22, ey - r * .36, -ex + r * .16, ey - r * .18], r * .12); L([ex + r * .22, ey - r * .36, ex - r * .16, ey - r * .18], r * .12);
      E(-ex + lx, ey + ly, r * .1, r * .12); E(ex + lx, ey + ly, r * .1, r * .12);
      if (expr === 'angry') { ctx.lineWidth = r * .11; ctx.beginPath(); ctx.arc(0, r * .72, r * .34, Math.PI * 1.18, Math.PI * 1.82); ctx.stroke(); }
      else {
        ctx.fillStyle = '#fff'; rrect(-r * .42, r * .3, r * .84, r * .28, r * .08); ctx.fill(); ctx.lineWidth = r * .06; ctx.stroke();
        L([-r * .42, r * .44, r * .42, r * .44], r * .04); for (const k of [-.2, 0, .2]) L([r * k, r * .3, r * k, r * .58], r * .04);
      }
      break;
    case 'annoyed':
      for (const s of [-1, 1]) {
        ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.ellipse(s * ex, ey, r * .22, r * .14, 0, 0, Math.PI); ctx.fill();
        ctx.fillStyle = K; E(s * ex + r * .12 + lx * .3, ey + r * .06, r * .07, r * .06);
        L([s * ex - r * .24, ey, s * ex + r * .24, ey], r * .07);
      }
      L([-ex - r * .2, ey - r * .26, -ex + r * .18, ey - r * .22], r * .07); L([ex - r * .18, ey - r * .22, ex + r * .2, ey - r * .26], r * .07);
      ctx.lineWidth = r * .09; ctx.beginPath(); ctx.moveTo(-r * .28, r * .48); ctx.quadraticCurveTo(0, r * .36, r * .28, r * .5); ctx.stroke();
      break;
    case 'bored':
      E(-ex + lx, ey + ly, r * .09, r * .12); E(ex + lx, ey + ly, r * .09, r * .12); L([-r * .3, r * .42, r * .3, r * .42], r * .09);
      break;
    case 'sleep':
      for (const s of [-1, 1]) { ctx.lineWidth = r * .08; ctx.beginPath(); ctx.arc(s * ex, ey - r * .04, r * .15, Math.PI * .15, Math.PI * .85); ctx.stroke(); }
      E(0, r * .45, r * .1, r * .08);
      break;
    case 'cry':
      for (const s of [-1, 1]) {
        ctx.fillStyle = 'rgba(80,170,255,.9)'; ctx.fillRect(s * ex - r * .08, ey + r * .05, r * .16, r * .8);
        ctx.lineWidth = r * .08; ctx.beginPath(); ctx.arc(s * ex, ey + r * .06, r * .16, Math.PI * 1.15, Math.PI * 1.85); ctx.stroke();
      }
      ctx.fillStyle = K; E(0, r * .5, r * .3, r * .17);
      break;
    case 'shocked':
      bigEyes(1); ctx.fillStyle = '#5a1a1a'; E(0, r * .52, r * .19, r * .26); ctx.fillStyle = '#ff7a8a'; E(0, r * .66, r * .11, r * .08);
      break;
    case 'surprised':
      bigEyes(.95); ctx.fillStyle = K; E(0, r * .5, r * .1, r * .13);
      break;
    case 'smirk':
      E(-ex, ey, r * .08, r * .1); E(ex, ey, r * .08, r * .1);
      ctx.lineWidth = r * .1; ctx.beginPath(); ctx.moveTo(-r * .26, r * .42); ctx.quadraticCurveTo(r * .12, r * .6, r * .38, r * .28); ctx.stroke();
      break;
    case 'sadsmile': {
      L([-ex - r * .2, ey - r * .24, -ex + r * .16, ey - r * .34], r * .07); L([ex + r * .2, ey - r * .24, ex - r * .16, ey - r * .34], r * .07);
      E(-ex, ey, r * .08, r * .11); E(ex, ey, r * .08, r * .11);
      ctx.lineWidth = r * .1; ctx.beginPath(); ctx.arc(0, r * .16, r * .36, Math.PI * .2, Math.PI * .8); ctx.stroke();
      // tear
      const tp = clamp(o.tear || 0, 0, 1); const ty = ey + r * .14 + tp * r * .55, tr = r * (.07 + .05 * Math.min(1, tp * 3));
      ctx.fillStyle = '#5ab8ff'; ctx.beginPath(); ctx.moveTo(ex + r * .06, ty - tr * 2.2); ctx.quadraticCurveTo(ex + r * .06 + tr * 1.3, ty, ex + r * .06, ty + tr); ctx.quadraticCurveTo(ex + r * .06 - tr * 1.3, ty, ex + r * .06, ty - tr * 2.2); ctx.fill();
      ctx.fillStyle = 'rgba(120,200,255,.55)'; E(ex, ey + r * .12, r * .16, r * .05);
      break;
    }
    case 'cool': {
      ctx.lineWidth = r * .1; ctx.beginPath(); ctx.moveTo(-r * .36, r * .38); ctx.quadraticCurveTo(0, r * .66, r * .36, r * .38); ctx.stroke();
      ctx.fillStyle = '#16161c';
      ctx.beginPath(); ctx.moveTo(-r * .92, -r * .32); ctx.lineTo(r * .92, -r * .32); ctx.lineTo(r * .9, -r * .2);
      ctx.quadraticCurveTo(r * .82, r * .2, r * .48, r * .18); ctx.quadraticCurveTo(r * .14, r * .16, r * .1, -r * .12);
      ctx.lineTo(-r * .1, -r * .12); ctx.quadraticCurveTo(-r * .14, r * .16, -r * .48, r * .18); ctx.quadraticCurveTo(-r * .82, r * .2, -r * .9, -r * .2); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,.55)'; ctx.lineWidth = r * .06;
      L([-r * .7, -r * .18, -r * .52, -r * .02], r * .06); L([r * .3, -r * .18, r * .48, -r * .02], r * .06);
      break;
    }
  }
  ctx.restore();
}

const PG = ['111111111111111111111111', '012211111110011221111110', '011221111110011122111110', '001111111100001111111100', '000111111000000111111000'];
function pixelGlasses(cx, cy, w) {
  const px = w / 24;
  for (let r = 0; r < PG.length; r++) for (let c = 0; c < 24; c++) {
    const v = PG[r][c]; if (v === '0') continue;
    ctx.fillStyle = v === '1' ? '#0b0b0b' : '#ffffff';
    ctx.fillRect(cx - w / 2 + c * px - .3, cy + r * px - .3, px + .6, px + .6);
  }
}

// ---------- car shapes ----------
const SH = {
  sedan: { body: [[-118, -16], [-121, -52], [-84, -57], [-58, -90], [22, -92], [58, -58], [113, -50], [121, -30], [118, -14], [-112, -14]], rad: 8,
    wins: [[[-74, -59], [-54, -84], [-12, -86], [-12, -59]], [[-4, -59], [-4, -86], [19, -87], [48, -59]]], head: [18, -70, 14], wheels: [[-72, 24], [74, 24]] },
  hatch: { body: [[-102, -16], [-105, -64], [-84, -92], [16, -94], [50, -60], [99, -52], [106, -32], [103, -14], [-98, -14]], rad: 8,
    wins: [[[-92, -64], [-76, -86], [-22, -88], [-22, -64]], [[-14, -64], [-14, -88], [14, -89], [42, -64]]], head: [14, -74, 14], wheels: [[-64, 22], [66, 22]] },
  suv: { body: [[-124, -18], [-126, -104], [-112, -113], [30, -114], [66, -72], [118, -62], [126, -40], [123, -16], [-120, -16]], rad: 9,
    wins: [[[-114, -72], [-114, -104], [-52, -105], [-52, -72]], [[-44, -72], [-44, -105], [-4, -105], [-4, -72]], [[4, -72], [4, -105], [26, -105], [56, -73]]], head: [26, -86, 15], wheels: [[-78, 27], [80, 27]] },
  van: { body: [[-131, -16], [-133, -122], [-118, -130], [70, -130], [116, -76], [130, -62], [134, -32], [130, -16], [-126, -16]], rad: 10,
    wins: [[[-122, -84], [-122, -118], [-62, -119], [-62, -84]], [[-52, -84], [-52, -119], [8, -119], [8, -84]], [[18, -82], [18, -119], [66, -119], [100, -82]]], head: [50, -98, 15], wheels: [[-86, 25], [86, 25]] },
  pickup: { body: [[-140, -16], [-142, -66], [-22, -66], [-18, -108], [46, -110], [78, -70], [132, -62], [141, -40], [138, -16], [-134, -16]], rad: 7,
    wins: [[[-8, -72], [-8, -102], [42, -103], [66, -72]]], head: [28, -86, 15], wheels: [[-94, 28], [92, 28]] },
  box: { body: [[60, -22], [60, -132], [118, -134], [148, -94], [166, -82], [168, -30], [164, -18], [60, -18]], rad: 8,
    cargo: [[-168, -24], [-168, -178], [56, -178], [56, -24]],
    wins: [[[76, -94], [76, -124], [114, -125], [140, -94]]], head: [104, -106, 15], wheels: [[-120, 28], [-62, 28], [118, 28]] },
  bus: { body: [[-218, -18], [-220, -160], [-204, -170], [200, -170], [216, -152], [220, -30], [216, -18], [-212, -16]], rad: 12,
    wins: [[[160, -150], [206, -150], [212, -100], [160, -100]]], head: [184, -122, 15], wheels: [[-150, 28], [150, 28]], bus: true },
  sad: { body: [[-116, -18], [-119, -56], [-86, -60], [-62, -92], [18, -94], [52, -62], [111, -55], [118, -33], [115, -14], [-110, -14]], rad: 6,
    wins: [[[-78, -62], [-58, -87], [-14, -89], [-14, -62]], [[-6, -62], [-6, -89], [14, -90], [44, -62]]], head: [14, -74, 15], wheels: [[-70, 24], [72, 24]] },
};
for (let i = 0; i < 6; i++) { const x = -198 + i * 56; SH.bus.wins.push([[x, -146], [x + 44, -146], [x + 44, -104], [x, -104]]); }

function wheel(x, y, r, ang, hubcap) {
  circ(x, y, r); ctx.fillStyle = '#1b1a22'; ctx.fill(); ctx.lineWidth = 2.5; ctx.strokeStyle = '#0c0b10'; ctx.stroke();
  if (!hubcap) { circ(x, y, r * .35); ctx.fillStyle = '#4b4a55'; ctx.fill(); return; }
  circ(x, y, r * .62); ctx.fillStyle = '#cfd3dc'; ctx.fill();
  ctx.strokeStyle = '#8c91a0'; ctx.lineWidth = r * .1;
  for (let k = 0; k < 5; k++) { const a = ang + k * Math.PI * 2 / 5; ctx.beginPath(); ctx.moveTo(x + Math.cos(a) * r * .15, y + Math.sin(a) * r * .15); ctx.lineTo(x + Math.cos(a) * r * .58, y + Math.sin(a) * r * .58); ctx.stroke(); }
  circ(x, y, r * .16); ctx.fillStyle = '#7d8290'; ctx.fill();
}

function bodyFill(pts, rad, color, outline) {
  rrPoly(pts, rad); ctx.fillStyle = color; ctx.fill();
  ctx.save(); ctx.clip();
  let ymin = 1e9, ymax = -1e9; for (const p of pts) { ymin = Math.min(ymin, p[1]); ymax = Math.max(ymax, p[1]); }
  const g = ctx.createLinearGradient(0, ymin, 0, ymax);
  g.addColorStop(0, 'rgba(255,255,255,.32)'); g.addColorStop(.35, 'rgba(255,255,255,.04)'); g.addColorStop(.7, 'rgba(0,0,0,.06)'); g.addColorStop(1, 'rgba(20,0,40,.38)');
  ctx.fillStyle = g; ctx.fillRect(-400, ymin - 5, 800, ymax - ymin + 10);
  ctx.restore();
  rrPoly(pts, rad); ctx.lineWidth = 3; ctx.strokeStyle = outline || '#1a1028'; ctx.lineJoin = 'round'; ctx.stroke();
}

function exprFor(c, t) {
  if (c.sad && t >= 12) return null;
  const rx = t < 12 ? roadX(t) : 0;
  if (t >= 5.6 && t < 8.2) { const d = Math.abs(c.x); if (t >= 5.62 + d / 3000 && d < 1300) return 'shocked'; }
  if (t >= 8.2 && t < 12 && rx > c.x - 260 && rx < c.x + 1800) return 'shocked';
  if (t >= 5.0 && t < 5.6 && Math.abs(c.x) < 700) return 'surprised';
  return c.expr;
}
function lookFor(c, t) {
  if (t >= 4.9 && t < 12) { const s = rState(t); const dx = s.x - c.x, dy = (s.y - 60) - (c.back ? -170 : -90); const m = Math.hypot(dx, dy) || 1; return [dx / m * 1.4, dy / m * 1.4]; }
  return [0, 0];
}

function drawCar(c, t) {
  const S = SH[c.type], back = !!c.back;
  let yoff = 0, sy = 1, sx = 1;
  if (t >= 5.6 && t < 7) { const d = Math.abs(c.x) / 750; if (d < 1) yoff += Math.sin(t * 70 + c.seed) * 5 * (1 - seg(t, 5.6, 6.8)) * (1 - d); }
  let hubcap = true;
  if (c.sad && t >= 12) {
    if (t >= 13.0 && t < 13.3) yoff += Math.sin(t * 90) * 1.2;
    if (t >= 13.3 && t < 13.42) sy = lerp(1, .87, eo(seg(t, 13.3, 13.42)));
    else if (t >= 13.42 && t < 13.78) { const p = seg(t, 13.42, 13.78); yoff -= 34 * Math.sin(Math.PI * p); sy = lerp(1.08, 1, p); }
    else if (t >= 13.78 && t < 14.1) { const p = seg(t, 13.78, 14.1); sy = 1 - .1 * Math.sin(Math.PI * p) * (1 - p); }
    sx = 1 / Math.sqrt(sy);
    if (t >= 13.78) hubcap = false;
  }
  const scale = back ? .86 : 1;
  ctx.save(); ctx.translate(c.x, (back ? -80 : 0) + yoff); ctx.scale(scale * sx, scale * sy);
  const col = back ? mix(c.color, '#3b1f63', .28) : c.color;
  // wheels arches + body
  if (S.cargo) bodyFill(S.cargo, 6, back ? mix('#f4f1ea', '#3b1f63', .28) : '#f4f1ea');
  bodyFill(S.body, S.rad, col);
  if (S.cargo) {
    ctx.save(); rrPoly(S.cargo, 6); ctx.clip(); ctx.fillStyle = col; ctx.fillRect(-170, -120, 230, 26); ctx.restore();
  }
  if (c.sad) {
    ctx.save(); rrPoly(S.body, S.rad); ctx.clip();
    ctx.fillStyle = '#8e98a3'; poly([[-6, -62], [50, -62], [56, -14], [-6, -14]]); ctx.fill();
    ctx.strokeStyle = 'rgba(0,0,0,.35)'; ctx.lineWidth = 2; ctx.stroke();
    ctx.fillStyle = 'rgba(140,70,20,.55)'; circ(-92, -30, 7); ctx.fill(); circ(-80, -24, 4); ctx.fill(); circ(96, -26, 5); ctx.fill(); circ(70, -46, 3); ctx.fill();
    ctx.strokeStyle = 'rgba(0,0,0,.4)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(-50, -40); ctx.quadraticCurveTo(-40, -32, -30, -42); ctx.stroke();
    ctx.restore();
    rrPoly(S.body, S.rad); ctx.lineWidth = 3; ctx.strokeStyle = '#1a1028'; ctx.stroke();
    ctx.strokeStyle = '#444'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(-100, -57); ctx.lineTo(-112, -108); ctx.stroke();
  }
  // windows with faces
  const ex = exprFor(c, t), lk = lookFor(c, t);
  S.wins.forEach((w, i) => {
    ctx.save(); poly(w); ctx.fillStyle = back ? '#8fb3d9' : '#a9d4f5'; ctx.fill(); ctx.clip();
    if (i === S.wins.length - 1 && !S.bus) {
      const [hx, hy, hr] = S.head;
      if (c.sad && t >= 12) drawSadFace(hx, hy, hr, t); else face(hx, hy, hr, ex, { look: lk, t });
    } else if (S.bus) {
      const cx = (w[0][0] + w[2][0]) / 2; const e2 = i === 0 ? ex : (t >= 5.6 && t < 12 && ex === 'shocked' ? 'shocked' : EXPR[(i * 3 + Math.floor(c.seed)) % EXPR.length]);
      face(i === 0 ? S.head[0] : cx, i === 0 ? S.head[1] : -122, i === 0 ? S.head[2] : 13, e2, { look: lk, t });
    }
    const g = ctx.createLinearGradient(w[0][0], w[1][1], w[2][0], w[0][1]);
    g.addColorStop(0, 'rgba(255,255,255,.28)'); g.addColorStop(.5, 'rgba(255,255,255,0)'); g.addColorStop(1, 'rgba(255,255,255,.12)');
    ctx.fillStyle = g; ctx.fillRect(-300, -200, 600, 200);
    ctx.restore();
    poly(w); ctx.lineWidth = 2.5; ctx.strokeStyle = '#1a1028'; ctx.stroke();
  });
  // lights + bumper
  const fx = S.body.reduce((m, p) => Math.max(m, p[0]), -999), bx = S.body.reduce((m, p) => Math.min(m, p[0]), 999);
  ctx.fillStyle = '#fff6c8'; rrect(fx - 12, -46, 10, 10, 3); ctx.fill();
  ctx.fillStyle = '#ff2d4a'; rrect((S.cargo ? -168 : bx) + 1, -52, 7, 14, 3); ctx.fill();
  ctx.fillStyle = 'rgba(20,10,40,.55)'; ctx.fillRect(bx + 4, -22, fx - bx - 8, 5);
  // wheels
  for (const [wx, wr] of S.wheels) wheel(wx, -wr, wr, c.seed, !(c.sad && !hubcap && wx > 0));
  ctx.restore();
  // steam for angry drivers
  if (ex === 'angry' && t < 5.6) {
    const [hx, hy, hr] = S.head; const ox = c.x + hx * scale, oy = (back ? -80 : 0) + hy * scale;
    for (let k = 0; k < 2; k++) {
      const ph = (t * 1.6 + c.seed + k * .5) % 1; const a = (1 - ph) * .75;
      ctx.globalAlpha = a; const rr = hr * scale * (.35 + ph * .5);
      ctx.drawImage(PUFF, ox + (k ? 1 : -1) * hr * scale * (.6 + ph * .5) - rr, oy - hr * scale * (1.1 + ph * 1.6) - rr, rr * 2, rr * 2);
    }
    ctx.globalAlpha = 1;
  }
  if (ex === 'sleep' && t < 5.6) {
    const [hx, hy, hr] = S.head; const ox = c.x + hx * scale, oy = (back ? -80 : 0) + hy * scale;
    ctx.font = `900 ${Math.round(hr * 1.1)}px Inter`; ctx.textAlign = 'center';
    for (let k = 0; k < 2; k++) { const ph = (t * .8 + k * .5 + c.seed) % 1; ctx.fillStyle = `rgba(255,255,255,${(1 - ph)})`; ctx.fillText('z', ox + hr * (1 + ph * 1.2), oy - hr * (1 + ph * 2)); }
  }
}

function drawSadFace(hx, hy, hr, t) {
  let ex = 'shocked', lk = [.8, -1.3], tear = 0;
  if (t >= 13.0 && t < 13.78) { ex = 'determined'; lk = [1, 0]; }
  else if (t >= 13.78 && t < 13.95) { ex = 'shocked'; lk = [0, 0]; }
  else if (t >= 13.95) { ex = 'sadsmile'; tear = seg(t, 14.05, 15.2); }
  face(hx, hy, hr, ex, { look: lk, t, tear });
}

// ---------- roadster ----------
const RB = [[-139, -17], [-142, -40], [-138, -51], [-120, -55], [-62, -57], [-50, -66], [-37, -57], [44, -57], [92, -50], [130, -38], [141, -27], [137, -15], [-130, -14]];
function jetCone(nx, ny, dx, dy, thr, t, j) {
  if (thr <= .02) return;
  const fl = .85 + .15 * Math.sin(t * 90 + j * 2) + .08 * Math.sin(t * 37 + j);
  const L = (60 + 150 * Math.min(thr, 1.4)) * fl, w0 = 7, w1 = 20 + 18 * Math.min(thr, 1.4);
  ctx.save(); ctx.translate(nx, ny); ctx.rotate(Math.atan2(-dx, dy));
  const g = ctx.createLinearGradient(0, 0, 0, L);
  g.addColorStop(0, 'rgba(255,255,255,.95)'); g.addColorStop(.3, 'rgba(175,228,255,.7)'); g.addColorStop(1, 'rgba(140,200,255,0)');
  ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(-w0, 0); ctx.quadraticCurveTo(-w1 * .6, L * .5, -w1, L); ctx.lineTo(w1, L); ctx.quadraticCurveTo(w1 * .6, L * .5, w0, 0); ctx.closePath(); ctx.fill();
  ctx.globalCompositeOperation = 'lighter';
  const g2 = ctx.createLinearGradient(0, 0, 0, L * .65); g2.addColorStop(0, 'rgba(210,245,255,.95)'); g2.addColorStop(1, 'rgba(90,170,255,0)');
  ctx.fillStyle = g2; ctx.beginPath(); ctx.moveTo(-w0 * .6, 0); ctx.lineTo(-w0 * 1.3, L * .65); ctx.lineTo(w0 * 1.3, L * .65); ctx.lineTo(w0 * .6, 0); ctx.closePath(); ctx.fill();
  ctx.restore();
}

function drawRoadster(t) {
  const s = rState(t);
  const vy = s.vib ? wob(t, 70, 2) * s.vib : 0;
  ctx.save(); ctx.translate(s.x, s.y - 40 + vy); ctx.rotate(s.rot); ctx.translate(0, 40);
  // underglow
  if (s.down > .1) {
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    const g = ctx.createRadialGradient(0, -6, 10, 0, -6, 190); g.addColorStop(0, `rgba(90,200,255,${.5 * Math.min(1, s.down)})`); g.addColorStop(1, 'rgba(90,200,255,0)');
    ctx.fillStyle = g; ctx.beginPath(); ctx.ellipse(0, -6, 190, 60, 0, 0, Math.PI * 2); ctx.fill(); ctx.restore();
  }
  // jets + nozzles
  NOZ.forEach((nx, j) => jetCone(nx, -14 + 9 * s.dep, 0, 1, s.down, t, j));
  jetCone(-142 - 6 * s.dep, -33, -1, .12, s.rear, t, 7);
  if (s.dep > 0) {
    ctx.fillStyle = '#2a2a33'; ctx.strokeStyle = '#111'; ctx.lineWidth = 2;
    for (const nx of NOZ) { poly([[nx - 9, -18], [nx + 9, -18], [nx + 7, -14 + 9 * s.dep], [nx - 7, -14 + 9 * s.dep]]); ctx.fill(); ctx.stroke(); }
    poly([[-136, -40], [-136, -26], [-142 - 6 * s.dep, -28], [-142 - 6 * s.dep, -38]]); ctx.fill(); ctx.stroke();
  }
  // driver
  const [hx, hy, hr] = HEAD;
  let ex = 'annoyed', lk = [0, 0];
  if (t >= 3.0 && t < 3.75) { ex = 'surprised'; lk = [0, -1.5]; }
  else if (t >= 3.75) ex = 'smirk';
  face(hx, hy, hr, ex, { look: lk, t });
  if (t >= 3.35) {
    const p = seg(t, 3.35, 3.75); const fall = (1 - p * p) * -230;
    const bounce = t >= 3.75 && t < 3.92 ? -4 * Math.sin(Math.PI * seg(t, 3.75, 3.92)) : 0;
    ctx.save(); ctx.translate(hx + 1, hy - hr * .3 + fall + bounce); ctx.rotate(.25 * (1 - p)); pixelGlasses(0, 0, hr * 2.15); ctx.restore();
  }
  // body
  bodyFill(RB, 7, '#d3111f', '#2a0008');
  ctx.save(); rrPoly(RB, 7); ctx.clip();
  ctx.fillStyle = '#6a000c'; circ(-88, -27, 33); ctx.fill(); circ(92, -27, 33); ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,.55)'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(-126, -50); ctx.quadraticCurveTo(-40, -54, 40, -53); ctx.quadraticCurveTo(95, -47, 128, -36); ctx.stroke();
  ctx.fillStyle = '#2a0610'; ctx.beginPath(); ctx.moveTo(-72, -40); ctx.quadraticCurveTo(-50, -44, -34, -36); ctx.quadraticCurveTo(-52, -30, -72, -34); ctx.fill();
  ctx.strokeStyle = 'rgba(40,0,10,.6)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(-30, -56); ctx.quadraticCurveTo(-24, -36, -28, -18); ctx.stroke();
  ctx.restore();
  // windscreen + mirror
  ctx.fillStyle = 'rgba(200,240,255,.38)'; poly([[48, -57], [38, -57], [13, -86], [20, -89]]); ctx.fill(); ctx.strokeStyle = 'rgba(30,10,30,.7)'; ctx.lineWidth = 1.8; ctx.stroke();
  ctx.strokeStyle = 'rgba(255,255,255,.8)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(40, -60); ctx.lineTo(22, -82); ctx.stroke();
  ctx.fillStyle = '#b00d1a'; ctx.beginPath(); ctx.ellipse(36, -62, 7, 4.5, -.2, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
  // lights
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  const hg = ctx.createRadialGradient(132, -36, 0, 132, -36, 40); hg.addColorStop(0, 'rgba(255,250,210,.9)'); hg.addColorStop(1, 'rgba(255,250,210,0)'); ctx.fillStyle = hg; circ(132, -36, 40); ctx.fill();
  const tg = ctx.createRadialGradient(-139, -45, 0, -139, -45, 26); tg.addColorStop(0, 'rgba(255,40,60,.9)'); tg.addColorStop(1, 'rgba(255,40,60,0)'); ctx.fillStyle = tg; circ(-139, -45, 26); ctx.fill();
  ctx.restore();
  ctx.fillStyle = '#fffbe0'; ctx.beginPath(); ctx.moveTo(116, -41); ctx.lineTo(137, -33); ctx.lineTo(135, -30); ctx.lineTo(114, -38); ctx.closePath(); ctx.fill();
  ctx.fillStyle = '#ff3355'; ctx.fillRect(-142, -47, 6, 4);
  // wheels (spin while rolling, idle otherwise)
  wheel(-88, -27, 27, s.x / 27, true); wheel(92, -27, 27, s.x / 27, true);
  // lightbulb moment
  if (t >= 3.0 && t < 3.5) {
    const sc = eob(seg(t, 3.0, 3.15)), al = 1 - seg(t, 3.33, 3.5);
    bulb(hx, hy - hr - 34, 15 * sc, al, t);
  }
  ctx.restore();
}

function bulb(x, y, s, al, t) {
  if (s <= 0) return;
  ctx.save(); ctx.globalAlpha = al; ctx.translate(x, y);
  const g = ctx.createRadialGradient(0, 0, 0, 0, 0, s * 2.6); g.addColorStop(0, 'rgba(255,245,160,.85)'); g.addColorStop(1, 'rgba(255,245,160,0)');
  ctx.fillStyle = g; circ(0, 0, s * 2.6); ctx.fill();
  ctx.strokeStyle = '#ffe36b'; ctx.lineWidth = s * .14; ctx.lineCap = 'round';
  for (let k = 0; k < 8; k++) { const a = k * Math.PI / 4 + t * 1.5; ctx.beginPath(); ctx.moveTo(Math.cos(a) * s * 1.45, Math.sin(a) * s * 1.45); ctx.lineTo(Math.cos(a) * s * 1.95, Math.sin(a) * s * 1.95); ctx.stroke(); }
  circ(0, 0, s); ctx.fillStyle = '#fff59d'; ctx.fill(); ctx.strokeStyle = '#f2a900'; ctx.lineWidth = s * .1; ctx.stroke();
  ctx.fillStyle = '#9aa0ab'; ctx.fillRect(-s * .45, s * .85, s * .9, s * .55); ctx.strokeStyle = '#555'; ctx.lineWidth = s * .07; ctx.strokeRect(-s * .45, s * .85, s * .9, s * .55);
  ctx.beginPath(); ctx.moveTo(-s * .45, s * 1.12); ctx.lineTo(s * .45, s * 1.12); ctx.stroke();
  ctx.restore();
}

// ---------- particles ----------
function gasParticles(t) {
  if (t < 5.0 || t >= 12) return;
  const rate = 45, life = 1.3;
  for (let k = Math.max(Math.ceil((t - life) * rate), Math.ceil(5.0 * rate)); k <= Math.floor(t * rate); k++) {
    const te = k / rate, a = t - te, s = rState(te);
    const c = Math.cos(s.rot), sn = Math.sin(s.rot);
    const em = [];
    if (s.down > .05) for (const nx of NOZ) em.push([nx, -14 + 9 * s.dep, 0, 1, s.down]);
    if (s.rear > .05) em.push([-148, -33, -1, .12, s.rear]);
    for (let j = 0; j < em.length; j++) {
      const [lx, ly, dx, dy, thr] = em[j];
      const h1 = hash(k * 13.7 + j * 7.1), h2 = hash(k * 3.3 + j * 11.9), h3 = hash(k * 7.9 + j * 2.3);
      const wx = s.x + c * lx - sn * (ly + 40), wy = s.y - 40 + sn * lx + c * (ly + 40);
      const vx = c * dx - sn * dy, vy = sn * dx + c * dy, sp0 = (h1 - .5) * .5;
      const ux = vx - vy * sp0, uy = vy + vx * sp0;
      const sp = (520 + h2 * 380) * Math.min(thr, 1.3), kd = 2.6, d = sp * (1 - Math.exp(-kd * a)) / kd;
      let px = wx + ux * d, py = wy + uy * d - 25 * a;
      if (py > -6) { const ex = py + 6; py = -6 - ex * .15; px += (h3 < .5 ? -1 : 1) * ex * 1.1; }
      const rad = (8 + a * 95 * (.6 + h3 * .8)) * (.6 + .4 * Math.min(thr, 1));
      const al = .55 * (1 - a / life) * Math.min(1, thr * 1.3);
      if (al <= 0) continue;
      ctx.globalAlpha = al; ctx.drawImage(PUFF, px - rad, py - rad, rad * 2, rad * 2);
    }
  }
  ctx.globalAlpha = 1;
}
function liftBurst(t) {
  if (t < 5.6 || t > 8.6) return; const a = t - 5.6;
  for (let i = 0; i < 46; i++) {
    const h1 = hash(i * 1.7 + .3), h2 = hash(i * 5.1 + .9), h3 = hash(i * 9.3 + .1);
    const dir = i % 2 ? 1 : -1, sp = 250 + h1 * 900, kd = 1.8, d = sp * (1 - Math.exp(-kd * a)) / kd;
    const px = dir * (20 + d), py = -10 - h2 * 50 - a * 18 * (.5 + h3);
    const rad = 26 + a * 60 * (.6 + h3) + h2 * 20, al = .92 * Math.pow(Math.max(0, 1 - a / 3), 1.3);
    ctx.globalAlpha = al; ctx.drawImage(CLOUD, px - rad, py - rad, rad * 2, rad * 2);
  }
  ctx.globalAlpha = 1;
  if (a < .45) {
    const p = a / .45; ctx.save(); ctx.globalCompositeOperation = 'lighter';
    ctx.strokeStyle = `rgba(200,240,255,${.85 * (1 - p)})`; ctx.lineWidth = 16 * (1 - p) + 2;
    ctx.beginPath(); ctx.ellipse(0, -8, 40 + p * 720, 10 + p * 90, 0, 0, Math.PI * 2); ctx.stroke(); ctx.restore();
  }
}
function speedLines(t) {
  if (t < 8.4 || t >= 12) return; const s = rState(t), k = seg(t, 8.4, 9.0) * (t > 11.3 ? 1.6 : 1);
  ctx.strokeStyle = '#fff'; ctx.lineCap = 'round';
  for (let i = 0; i < 16; i++) {
    const ph = (t * 3.2 + hash(i)) % 1, len = (80 + hash(i * 7) * 170) * k;
    const lx = s.x - 170 - ph * 520, ly = s.y - 45 + (hash(i * 3.1) - .5) * 140;
    ctx.globalAlpha = (1 - ph) * .55 * Math.min(1, k); ctx.lineWidth = 2 + hash(i * 5) * 3;
    ctx.beginPath(); ctx.moveTo(lx, ly); ctx.lineTo(lx - len, ly); ctx.stroke();
  }
  ctx.globalAlpha = 1;
}

// ---------- bubbles ----------
const HONKS = [
  { t: .12, lane: FRONT, x: 330, text: 'HONK!', rot: -.12 },
  { t: .55, lane: BACK, x: -265, text: 'BEEEP!', rot: .1 },
  { t: 1.0, lane: FRONT, x: -560, text: 'HONK!!', rot: .08 },
  { t: 1.45, lane: BACK, x: 200, text: 'BEEP BEEP', rot: -.08 },
  { t: 1.85, lane: FRONT, x: 330, text: 'HOOONK!!', rot: .1 },
].map(h => Object.assign(h, { car: nearest(h.lane, h.x) }));
const SPEECH = [
  { t: 5.95, lane: FRONT, x: 330, text: 'BRO WHAT?!', dur: 1.6 },
  { t: 6.3, lane: BACK, x: -200, text: '?!?!', dur: 1.4 },
  { t: 6.65, lane: FRONT, x: -292, text: 'NO WAY', dur: 1.4 },
].map(h => Object.assign(h, { car: nearest(h.lane, h.x) }));

function carTop(c) { const S = SH[c.type]; let m = 0; for (const p of (S.cargo || S.body)) m = Math.min(m, p[1]); return (c.back ? -80 + m * .86 : m); }
function burst(x, y, R, text, rot, sc, al) {
  if (sc <= 0 || al <= 0) return;
  ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.scale(sc, sc); ctx.globalAlpha = al;
  ctx.font = `${Math.round(R * .62)}px Bangers`; const tw = ctx.measureText(text).width;
  const rx = Math.max(R, tw * .62 + R * .3), ry = R * .8;
  ctx.beginPath(); const n = 18;
  for (let i = 0; i <= n * 2; i++) { const a = i / (n * 2) * Math.PI * 2, k = (i % 2 ? .74 : 1) * (1 + .07 * Math.sin(i * 7.3)); const px = Math.cos(a) * rx * k, py = Math.sin(a) * ry * k; i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); }
  ctx.closePath(); ctx.fillStyle = '#ffe14d'; ctx.fill(); ctx.lineWidth = 5; ctx.strokeStyle = '#141414'; ctx.lineJoin = 'round'; ctx.stroke();
  ctx.fillStyle = '#141414'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(text, 0, R * .05);
  ctx.restore();
}
function speech(x, y, text, size, sc, al, tailX, tailY, font) {
  if (sc <= 0 || al <= 0) return;
  ctx.save(); ctx.globalAlpha = al; ctx.translate(x, y); ctx.scale(sc, sc);
  ctx.font = font || `${size}px Bangers`; const tw = ctx.measureText(text).width, w = tw + size * .9, h = size * 1.35;
  ctx.fillStyle = '#fff'; ctx.strokeStyle = '#141414'; ctx.lineWidth = 4.5; ctx.lineJoin = 'round';
  ctx.beginPath(); ctx.roundRect(-w / 2, -h / 2, w, h, h * .45);
  ctx.moveTo(-w * .12, h / 2 - 2); ctx.lineTo((tailX - x) / sc, (tailY - y) / sc); ctx.lineTo(w * .08, h / 2 - 2);
  ctx.fill(); ctx.stroke();
  ctx.fillStyle = '#fff'; ctx.fillRect(-w * .12 + 3, h / 2 - 7, w * .2 - 6, 8);
  ctx.fillStyle = '#141414'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(text, 0, size * .06);
  ctx.restore();
}
function drawBubbles(t, cam) {
  const bxMin = cam.x - (W / 2 - 170) / cam.z, bxMax = cam.x + (W / 2 - 170) / cam.z;
  for (const h of HONKS) {
    const a = t - h.t; if (a < 0 || a > .75) continue;
    const c = h.car, bx = clamp(c.x + c.len * .2, bxMin, bxMax), by = carTop(c) - 70;
    burst(bx, by + Math.sin(a * 30) * 2, 62, h.text, h.rot + Math.sin(a * 25) * .03, eob(seg(a, 0, .14)), 1 - seg(a, .6, .75));
  }
  for (const h of SPEECH) {
    const a = t - h.t; if (a < 0 || a > h.dur) continue;
    const c = h.car, S = SH[c.type], hx = c.x + S.head[0] * (c.back ? .86 : 1), hy = (c.back ? -80 : 0) + S.head[1] * (c.back ? .86 : 1);
    speech(hx + 30, carTop(c) - 80, h.text, 46, eob(seg(a, 0, .16)), 1 - seg(a, h.dur - .2, h.dur), hx + 6, hy - 18);
  }
  // the sad guy's pathetic horn
  if (t >= 13.0 && t < 13.7) { const a = t - 13.0; speech(SAD.x + 150, -168, 'meep.', 24, eob(seg(a, 0, .12)), 1 - seg(a, .55, .7), SAD.x + 112, -60, 'italic 600 24px Inter'); }
  // hover mode pill
  if (t >= 4.75 && t < 5.75) {
    const a = t - 4.75, sc = eob(seg(a, 0, .18)), al = 1 - seg(a, .85, 1);
    ctx.save(); ctx.translate(0, -205); ctx.scale(sc, sc); ctx.globalAlpha = al;
    ctx.font = '900 26px Inter'; const tw = ctx.measureText('HOVER MODE: ON').width;
    ctx.shadowColor = '#3fe6ff'; ctx.shadowBlur = 24; ctx.fillStyle = 'rgba(8,16,36,.9)'; rrect(-tw / 2 - 24, -26, tw + 48, 52, 26); ctx.fill();
    ctx.shadowBlur = 0; ctx.strokeStyle = '#3fe6ff'; ctx.lineWidth = 3; ctx.stroke();
    ctx.fillStyle = '#9ff5ff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText('HOVER MODE: ON', 0, 1);
    ctx.restore();
  }
}

// ---------- background ----------
function drawSky(t) {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const g = ctx.createLinearGradient(0, CAP, 0, H);
  g.addColorStop(0, '#170a38'); g.addColorStop(.33, '#55207a'); g.addColorStop(.6, '#d6456f'); g.addColorStop(.8, '#ff8a4c'); g.addColorStop(1, '#ffc46b');
  ctx.fillStyle = g; ctx.fillRect(0, CAP, W, H - CAP);
  for (const s of BG.stars) { const a = (.45 + .45 * Math.sin(t * 3 + s.ph)) * (1 - (s.y - CAP) / 460); ctx.fillStyle = `rgba(255,236,255,${a})`; ctx.fillRect(s.x, s.y, s.s, s.s); }
}
function drawSun(cam) {
  setLayer(cam, .06);
  const cx = 260, cy = -360, R = 200;
  const gl = ctx.createRadialGradient(cx, cy, R * .6, cx, cy, R * 2); gl.addColorStop(0, 'rgba(255,140,120,.45)'); gl.addColorStop(1, 'rgba(255,140,120,0)');
  ctx.fillStyle = gl; circ(cx, cy, R * 2); ctx.fill();
  ctx.save(); ctx.beginPath(); ctx.rect(cx - R, cy - R, R * 2, R * 1.1);
  let y = cy + R * .1, gap = 6; while (y < cy + R) { ctx.rect(cx - R, y + gap, R * 2, 22); y += 22 + gap; gap += 3; }
  ctx.clip();
  const g = ctx.createLinearGradient(0, cy - R, 0, cy + R); g.addColorStop(0, '#fff27a'); g.addColorStop(.45, '#ff9a3c'); g.addColorStop(1, '#ff3d7f');
  ctx.fillStyle = g; circ(cx, cy, R); ctx.fill(); ctx.restore();
}
function cloudShape(x, y, s, col) {
  ctx.fillStyle = col; ctx.beginPath();
  for (const [dx, dy, r] of [[-60, 6, 34], [-22, -16, 46], [26, -10, 40], [62, 8, 30], [0, 12, 40]]) { ctx.moveTo(x + (dx + r) * s, y + dy * s); ctx.arc(x + dx * s, y + dy * s, r * s, 0, Math.PI * 2); }
  ctx.fill();
}
function drawClouds(t, cam) {
  setLayer(cam, .14);
  for (const c of BG.clouds) { const x = c.x + t * 10 * c.s; cloudShape(x, c.y + 10 * c.s, c.s * 1.6, 'rgba(120,40,120,.35)'); cloudShape(x, c.y, c.s * 1.6, 'rgba(255,170,210,.75)'); }
}
function drawSkyline(cam, t) {
  let zl = setLayer(cam, .25); let vx0 = cam.x * .25 - 700 / zl, vx1 = cam.x * .25 + 700 / zl;
  ctx.fillStyle = '#4a2475';
  for (const b of BG.far) { if (b.x > vx1 || b.x + b.w < vx0) continue; ctx.fillRect(b.x, -150 - b.h, b.w, b.h + 400); }
  zl = setLayer(cam, .5); vx0 = cam.x * .5 - 700 / zl; vx1 = cam.x * .5 + 700 / zl;
  for (const b of BG.mid) {
    if (b.x > vx1 || b.x + b.w < vx0) continue;
    ctx.fillStyle = '#2b1450'; ctx.fillRect(b.x, -150 - b.h, b.w, b.h + 400);
    if (b.ant) { ctx.fillRect(b.x + b.w / 2 - 2, -150 - b.h - 40, 4, 40); ctx.fillStyle = (Math.sin(t * 4 + b.s) > 0) ? '#ff4d6d' : '#5a1a3a'; circ(b.x + b.w / 2, -150 - b.h - 42, 5); ctx.fill(); }
    ctx.fillStyle = '#ffd27a';
    for (let wx = b.x + 10; wx < b.x + b.w - 14; wx += 18) for (let wy = -150 - b.h + 14; wy < -170; wy += 24) if (hash(wx * .37 + wy * .91 + b.s) > .62) ctx.fillRect(wx, wy, 8, 11);
  }
}
function drawPalms(cam, t) {
  const zl = setLayer(cam, .8); const vx0 = cam.x * .8 - 750 / zl, vx1 = cam.x * .8 + 750 / zl;
  ctx.strokeStyle = '#1b0b30'; ctx.fillStyle = '#1b0b30'; ctx.lineCap = 'round';
  for (const p of BG.palms) {
    if (p.x < vx0 - 200 || p.x > vx1 + 200) continue;
    const tx = p.x + p.lean * p.h, ty = -150 - p.h;
    ctx.lineWidth = 11; ctx.beginPath(); ctx.moveTo(p.x, -100); ctx.quadraticCurveTo(p.x + p.lean * p.h * .2, -150 - p.h * .5, tx, ty); ctx.stroke();
    for (let k = 0; k < 7; k++) {
      const a = -Math.PI / 2 + (k - 3) * .5 + Math.sin(t * 1.5 + p.s + k) * .04, L = 80 + (k % 2) * 18;
      const ex = tx + Math.cos(a) * L, ey = ty + Math.sin(a) * L * .55 + 34;
      ctx.lineWidth = 9; ctx.beginPath(); ctx.moveTo(tx, ty); ctx.quadraticCurveTo(tx + Math.cos(a) * L * .55, ty + Math.sin(a) * L * .6 - 16, ex, ey); ctx.stroke();
    }
    circ(tx, ty + 4, 9); ctx.fill();
  }
}

// ---------- road / world ----------
function drawRoad(cam) {
  const x0 = cam.x - 800 / cam.z, x1 = cam.x + 800 / cam.z;
  // back guard rail
  ctx.fillStyle = '#6f6a86'; ctx.fillRect(x0, -176, x1 - x0, 12);
  ctx.fillStyle = '#4b4663'; for (let x = Math.floor(x0 / 90) * 90; x < x1; x += 90) ctx.fillRect(x, -170, 7, 24);
  // asphalt
  const g = ctx.createLinearGradient(0, -150, 0, 48); g.addColorStop(0, '#2f2b42'); g.addColorStop(1, '#423d58');
  ctx.fillStyle = '#c9c3d9'; ctx.fillRect(x0, -154, x1 - x0, 6);
  ctx.fillStyle = g; ctx.fillRect(x0, -148, x1 - x0, 196);
  ctx.fillStyle = 'rgba(255,255,255,.75)'; for (let x = Math.floor(x0 / 110) * 110; x < x1; x += 110) ctx.fillRect(x, -40, 58, 6);
}
function drawFrontGround(cam, t) {
  const x0 = cam.x - 800 / cam.z, x1 = cam.x + 800 / cam.z;
  ctx.fillStyle = '#d7d1e6'; ctx.fillRect(x0, 46, x1 - x0, 10);
  ctx.fillStyle = '#8f88a6'; ctx.fillRect(x0, 56, x1 - x0, 64);
  ctx.fillStyle = 'rgba(60,50,90,.5)'; for (let x = Math.floor(x0 / 80) * 80; x < x1; x += 80) ctx.fillRect(x, 56, 3, 64);
  ctx.fillStyle = '#2d6a4f'; ctx.fillRect(x0, 120, x1 - x0, 400);
  ctx.fillStyle = '#40916c'; for (let x = Math.floor(x0 / 46) * 46; x < x1; x += 46) { circ(x + hash(x) * 20, 124, 16 + hash(x * 3) * 10); ctx.fill(); }
  // snail (faster than traffic)
  const sx = t < 12 ? -420 + 45 * t : -440 + 40 * (t - 12);
  snail(sx, t < 12 ? 112 : 72, 1);
}
function snail(x, y, s) {
  ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
  ctx.strokeStyle = 'rgba(255,255,255,.7)'; ctx.lineWidth = 2; for (const k of [0, 1]) { ctx.beginPath(); ctx.moveTo(-30 - k * 6, -6 - k * 8); ctx.lineTo(-48 - k * 8, -6 - k * 8); ctx.stroke(); }
  ctx.fillStyle = '#e9c46a'; ctx.strokeStyle = '#3a2312'; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(-26, 0); ctx.quadraticCurveTo(10, 2, 26, -4); ctx.quadraticCurveTo(30, -12, 22, -12); ctx.lineTo(-20, -6); ctx.closePath(); ctx.fill(); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(20, -10); ctx.lineTo(24, -26); ctx.moveTo(25, -10); ctx.lineTo(32, -24); ctx.stroke();
  ctx.fillStyle = '#3a2312'; circ(24, -27, 2.5); ctx.fill(); circ(32, -25, 2.5); ctx.fill();
  ctx.fillStyle = '#b5651d'; circ(-4, -18, 15); ctx.fill(); ctx.stroke();
  ctx.beginPath(); for (let a = 0; a < 9; a += .2) { const r = 13 - a * 1.35; ctx.lineTo(-4 + Math.cos(a) * r, -18 + Math.sin(a) * r); } ctx.stroke();
  ctx.restore();
}
function drawSign() {
  const x = 2700;
  ctx.fillStyle = '#5b5670'; ctx.fillRect(x - 130, -290, 10, 150); ctx.fillRect(x + 120, -290, 10, 150);
  ctx.fillStyle = '#0d7a43'; rrect(x - 175, -392, 350, 108, 12); ctx.fill(); ctx.strokeStyle = '#fff'; ctx.lineWidth = 4; rrect(x - 168, -385, 336, 94, 8); ctx.stroke();
  ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.font = '900 36px Inter'; ctx.fillText('TRAFFIC JAM', x, -352); ctx.font = '700 27px Inter'; ctx.fillText('NEXT 38 MILES', x, -312);
}
function drawBirds(t) {
  if (t < 9.6 || t >= 12) return;
  for (let i = 0; i < 4; i++) {
    let bx = 2200 + i * 75 - 160 * (t - 8.2), by = -560 - (i % 2) * 30 - i * 8, rot = 0;
    const tp = 10.25 + i * .02;
    if (t > tp) { const a = t - tp; by -= 260 * a + 160 * a * a; bx += (i % 2 ? 1 : -1) * 140 * a; if (i === 1) rot = a * 14; }
    const fl = Math.sin(t * 18 + i * 1.7) * 9;
    ctx.save(); ctx.translate(bx, by); ctx.rotate(rot); ctx.strokeStyle = '#1b0b30'; ctx.lineWidth = 4; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(-18, -fl); ctx.quadraticCurveTo(-8, -6, 0, 2); ctx.quadraticCurveTo(8, -6, 18, -fl); ctx.stroke(); ctx.restore();
  }
  if (t > 10.25) {
    for (let k = 0; k < 7; k++) {
      const a = t - 10.25, fx = 2140 - 160 * 2.05 + (hash(k) - .5) * 120 + Math.sin(a * 5 + k) * 18, fy = -560 + a * 70 + hash(k * 3) * 40;
      ctx.save(); ctx.globalAlpha = Math.max(0, 1 - a / 1.6); ctx.translate(fx, fy); ctx.rotate(Math.sin(a * 6 + k) * .8);
      ctx.fillStyle = '#f6efff'; ctx.beginPath(); ctx.ellipse(0, 0, 9, 3.5, 0, 0, Math.PI * 2); ctx.fill(); ctx.restore();
    }
  }
}

function focusFx(t, cam) {
  const k = Math.min(seg(t, 2.4, 2.9), 1 - seg(t, 4.4, 4.62));
  if (k <= 0) return;
  ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.fillStyle = `rgba(22,6,44,${.5 * k})`; ctx.fillRect(0, CAP, W, H - CAP);
  if (t >= 3.0 && t < 3.8) {
    const hx = SCX + (HEAD[0] - cam.x) * cam.z + cam.sx, hy = SCY + (HEAD[1] - cam.y) * cam.z + cam.sy;
    const fr = Math.floor(t * 15), al = 1 - seg(t, 3.6, 3.8);
    ctx.fillStyle = `rgba(255,255,255,${.75 * al})`;
    for (let i = 0; i < 46; i++) {
      const a = (i + hash(fr * 7 + i) * .8) / 46 * Math.PI * 2, r0 = 190 + hash(fr * 3 + i * 5) * 140, w = .006 + hash(i * 9 + fr) * .012;
      ctx.beginPath(); ctx.moveTo(hx + Math.cos(a) * r0, hy + Math.sin(a) * r0);
      ctx.lineTo(hx + Math.cos(a - w) * 1500, hy + Math.sin(a - w) * 1500); ctx.lineTo(hx + Math.cos(a + w) * 1500, hy + Math.sin(a + w) * 1500); ctx.closePath(); ctx.fill();
    }
  }
  ctx.restore();
}

// ---------- HUD / text ----------
function drawHUD(t) {
  if (t >= 12) return;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const w = 330, h = 118, x = W - 34 - w, y = CAP + 28;
  const green = t >= 10.7;
  let fy = 1; if (t >= 10.6 && t < 10.8) fy = Math.abs(Math.cos((t - 10.6) / .2 * Math.PI)) + .001;
  const pop = green ? 1 + .12 * Math.max(0, 1 - (t - 10.7) / .25) : 1;
  ctx.save(); ctx.translate(x + w / 2, y + h / 2); ctx.scale(pop, fy * pop);
  rrect(-w / 2, -h / 2, w, h, 26); ctx.fillStyle = 'rgba(14,10,30,.86)'; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = green ? 'rgba(34,197,94,.8)' : 'rgba(255,77,77,.7)'; ctx.stroke();
  const col = green ? '#22c55e' : '#ff4d4d';
  circ(-w / 2 + 56, 0, 34); ctx.fillStyle = col; ctx.fill();
  ctx.strokeStyle = '#fff'; ctx.lineWidth = 5; ctx.lineCap = 'round'; circ(-w / 2 + 56, 0, 20); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(-w / 2 + 56, -11); ctx.lineTo(-w / 2 + 56, 0); ctx.lineTo(-w / 2 + 64, 7); ctx.stroke();
  ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
  ctx.fillStyle = 'rgba(255,255,255,.7)'; ctx.font = '700 21px Inter'; ctx.fillText('ETA', -w / 2 + 106, -22);
  ctx.fillStyle = col; ctx.font = '900 48px Inter'; ctx.fillText(green ? '4 min' : (t < 2.0 ? '3h 47m' : '3h 48m'), -w / 2 + 104, 22);
  ctx.fillStyle = 'rgba(255,255,255,.75)'; ctx.font = '700 19px Inter'; ctx.fillText(green ? 'via: the sky' : 'heavy traffic', -w / 2 + 106, 47);
  ctx.restore();
}
function drawLabel(t) {
  if (t < 12) return;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const al = seg(t, 12.0, 12.15);
  ctx.save(); ctx.globalAlpha = al; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.font = '900 50px Inter';
  ctx.lineJoin = 'round'; ctx.lineWidth = 10; ctx.strokeStyle = '#000'; ctx.strokeText('meanwhile me in my 2009 sedan:', W / 2, CAP + 70);
  ctx.fillStyle = '#fff'; ctx.fillText('meanwhile me in my 2009 sedan:', W / 2, CAP + 70); ctx.restore();
  // twinkle where the roadster vanished
  if (t >= 12.1 && t < 12.6) {
    const a = seg(t, 12.1, 12.6), s = Math.sin(Math.PI * a) * 34, x = 905, y = CAP + 210;
    ctx.save(); ctx.translate(x, y); ctx.rotate(a * 3); ctx.globalCompositeOperation = 'lighter';
    const g = ctx.createRadialGradient(0, 0, 0, 0, 0, s * 2); g.addColorStop(0, 'rgba(255,250,200,.9)'); g.addColorStop(1, 'rgba(255,250,200,0)'); ctx.fillStyle = g; circ(0, 0, s * 2); ctx.fill();
    ctx.fillStyle = '#fffbe6'; ctx.beginPath();
    for (let k = 0; k < 8; k++) { const r = k % 2 ? s * .22 : s, an = k * Math.PI / 4; ctx.lineTo(Math.cos(an) * r, Math.sin(an) * r); }
    ctx.closePath(); ctx.fill(); ctx.restore();
  }
}
// hubcap rolling away after the hop
function drawHubcap(t) {
  if (t < 13.78) return;
  const a = t - 13.78, d = 190 * (1 - Math.exp(-1.6 * a)) / 1.6;
  const x = SAD.x + 72 + 14 + d, r = 15, tip = seg(t, 14.75, 15.0);
  const y = -24 - Math.abs(Math.sin(a * 9)) * 12 * Math.exp(-a * 3);
  ctx.save(); ctx.translate(x, y + tip * 8); ctx.scale(1 - tip * .75, 1); ctx.rotate(d / r);
  circ(0, 0, r); ctx.fillStyle = '#cfd3dc'; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = '#555'; ctx.stroke();
  ctx.strokeStyle = '#8c91a0'; ctx.lineWidth = 2.5; for (let k = 0; k < 5; k++) { const an = k * Math.PI * 2 / 5; ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(Math.cos(an) * r * .9, Math.sin(an) * r * .9); ctx.stroke(); }
  ctx.restore();
  // landing dust + exhaust puff
  if (a < 1.2) {
    for (let k = 0; k < 8; k++) {
      const h = hash(k * 2.3), px = SAD.x - 120 + k * 34 + (h - .5) * 20 + (k < 4 ? -1 : 1) * a * 60, rr = 12 + a * 30 * (.5 + h);
      ctx.globalAlpha = .7 * (1 - a / 1.2); ctx.drawImage(CLOUD, px - rr, -8 - rr - a * 10, rr * 2, rr * 2);
    }
    ctx.globalAlpha = 1;
  }
}

// ---------- caption ----------
const CAPTION = ['POV: you’re stuck in traffic', 'and remember you’re driving', 'a Roadster'];
let CAP_FONT = 64;
function drawCaption() {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, W, CAP);
  ctx.fillStyle = '#0f0f12'; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
  ctx.font = `800 ${CAP_FONT}px Inter`;
  const lh = CAP_FONT * 1.17, er = CAP_FONT * .5, total = lh * 3;
  const y0 = (CAP - total) / 2 + CAP_FONT * .86;
  CAPTION.forEach((ln, i) => {
    const w = ctx.measureText(ln).width + (i === 2 ? er * 2 + CAP_FONT * .28 : 0);
    const x = (W - w) / 2; ctx.fillText(ln, x, y0 + i * lh);
    if (i === 2) face(x + ctx.measureText(ln).width + CAP_FONT * .28 + er, y0 + i * lh - CAP_FONT * .36, er, 'cool', {});
  });
  ctx.fillStyle = 'rgba(0,0,0,.08)'; ctx.fillRect(0, CAP - 2, W, 2);
}

// ---------- frame ----------
function vignette() {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const g = ctx.createRadialGradient(SCX, SCY, 300, SCX, SCY, 820); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(10,0,25,.38)');
  ctx.fillStyle = g; ctx.fillRect(0, CAP, W, H - CAP);
}
window.renderFrame = function (t) {
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
  ctx.clearRect(0, 0, W, H);
  const cam = camera(t);
  ctx.save(); ctx.beginPath(); ctx.rect(0, CAP, W, H - CAP); ctx.clip();
  drawSky(t); drawSun(cam); drawClouds(t, cam); drawSkyline(cam, t); drawPalms(cam, t);
  setLayer(cam, 1);
  const vx0 = cam.x - 760 / cam.z, vx1 = cam.x + 760 / cam.z;
  drawSign(); drawRoad(cam);
  for (const c of BACK) if (c.x + c.len / 2 > vx0 && c.x - c.len / 2 < vx1) drawCar(c, t);
  for (const c of FRONT) if (c.x + c.len / 2 > vx0 && c.x - c.len / 2 < vx1) drawCar(c, t);
  drawFrontGround(cam, t);
  focusFx(t, cam);
  gasParticles(t); liftBurst(t); speedLines(t);
  if (t < 12) drawRoadster(t);
  drawHubcap(t); drawBirds(t); drawBubbles(t, cam);
  vignette(); drawHUD(t); drawLabel(t);
  ctx.restore();
  drawCaption();
};

window.READY = (async function () {
  const f = new FontFace('Bangers', 'url(Bangers-Regular.ttf)'); await f.load(); document.fonts.add(f);
  await document.fonts.load('800 64px Inter'); await document.fonts.load('900 64px Inter'); await document.fonts.load('700 20px Inter');
  ctx.font = `800 ${CAP_FONT}px Inter`;
  const maxW = Math.max(...CAPTION.map((l, i) => ctx.measureText(l).width + (i === 2 ? CAP_FONT * 1.3 : 0)));
  if (maxW > 990) CAP_FONT = Math.floor(CAP_FONT * 990 / maxW);
  window.renderFrame(0);
  return true;
})();
window.DUR = DUR;
