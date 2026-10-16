"""Synthesised soundtrack for the Roadster POV clip (all original, no samples).
Timeline mirrors scene.js. Output: 48 kHz stereo WAV."""
import sys
import wave
import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000
DUR = 15.5
N = int(DUR * SR)
rng = np.random.default_rng(7)
L = np.zeros(N)
R = np.zeros(N)


def tt(d):
    return np.arange(int(d * SR)) / SR


def add(sig, t0, gain=1.0, pan=0.0):
    i0 = int(t0 * SR)
    if i0 >= N:
        return
    s = sig[: N - i0] * gain
    L[i0:i0 + len(s)] += s * np.sqrt((1 - pan) / 2) * 1.414
    R[i0:i0 + len(s)] += s * np.sqrt((1 + pan) / 2) * 1.414


def filt(x, kind, f, order=2):
    sos = butter(order, f, btype=kind, fs=SR, output='sos')
    return sosfilt(sos, x)


def env_adsr(n, a=0.005, r=0.05):
    e = np.ones(n)
    na, nr = max(1, int(a * SR)), max(1, int(r * SR))
    e[:na] = np.linspace(0, 1, na)
    e[-nr:] *= np.linspace(1, 0, nr)
    return e


def osc(freq, d, kind='sin'):
    f = np.broadcast_to(np.asarray(freq, dtype=float), (int(d * SR),))
    ph = 2 * np.pi * np.cumsum(f) / SR
    if kind == 'sin':
        return np.sin(ph)
    if kind == 'saw':
        return 2 * ((ph / (2 * np.pi)) % 1) - 1
    if kind == 'sq':
        return np.sign(np.sin(ph))
    raise ValueError(kind)


def noise(d):
    return rng.standard_normal(int(d * SR))


# ---------- sound designers ----------
def horn(f1, f2, d, bright=2500):
    x = osc(f1, d, 'saw') + osc(f2, d, 'saw') * .8 + osc(f1 * 2, d, 'sq') * .15
    x = filt(x, 'lowpass', bright)
    return np.tanh(x * 1.4) * env_adsr(len(x), .01, .06) * .5


def honk_double(f1, f2, d):
    a = horn(f1, f2, d)
    gap = np.zeros(int(.07 * SR))
    return np.concatenate([a, gap, a])


def whoosh(d, f0, f1, gain=1.0):
    n = noise(d)
    out = np.zeros_like(n)
    blocks = 40
    edges = np.linspace(0, len(n), blocks + 1).astype(int)
    for b in range(blocks):
        p = b / blocks
        fc = f0 * (f1 / f0) ** p
        lo, hi = max(40, fc * .6), min(20000, fc * 1.6)
        seg = filt(n, 'bandpass', [lo, hi])[edges[b]:edges[b + 1]]
        out[edges[b]:edges[b + 1]] = seg
    e = np.sin(np.pi * np.linspace(0, 1, len(n))) ** 1.5
    return out * e * gain


def ding(f=1318.5, d=1.2):
    t = tt(d)
    x = np.sin(2 * np.pi * f * t) + .5 * np.sin(2 * np.pi * f * 2.01 * t) + .25 * np.sin(2 * np.pi * f * 3.02 * t)
    return x * np.exp(-t * 4) * .35


def kick808(f_end=49, d=.55, punch=2.6, drive=2.5):
    t = tt(d)
    f = f_end * (1 + (punch - 1) * np.exp(-t * 38))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR)
    x *= np.exp(-t * (1.0 / d) * 2.2)
    x = np.tanh(x * drive) / np.tanh(drive)
    click = filt(noise(.01), 'highpass', 3000) * np.linspace(1, 0, int(.01 * SR)) * .3
    x[:len(click)] += click
    return x * env_adsr(len(x), .001, .03)


def clap():
    d = .25
    n = filt(noise(d), 'bandpass', [900, 4000])
    t = tt(d)
    e = np.exp(-t * 18)
    for k in (0, .012, .024):
        e += np.exp(-np.clip(t - k, 0, None) * 120) * (t >= k) * .8
    return n * e * .35


def hat(d=.05):
    n = filt(noise(d), 'highpass', 7000)
    return n * np.exp(-tt(d) * 70) * .22


def cowbell(f, d=.22):
    x = osc(f, d, 'sq') + osc(f * 1.48, d, 'sq')
    x = filt(x, 'bandpass', [f * .9, f * 3.2])
    t = tt(d)
    return x * (np.exp(-t * 16) * .8 + .2 * np.exp(-t * 4)) * .3


def clunk():
    t = tt(.45)
    x = np.sin(2 * np.pi * 70 * t) * np.exp(-t * 14)
    m = filt(noise(.45), 'bandpass', [1800, 2600]) * np.exp(-t * 9) * .5
    m += sum(np.sin(2 * np.pi * f * t) * np.exp(-t * 7) * .15 for f in (1210, 1985, 2730))
    return (x + m) * .7


def boing(d=.5):
    t = tt(d)
    f = 180 + 220 * (t / d) + 60 * np.sin(2 * np.pi * 14 * t) * np.exp(-t * 3)
    return osc(f, d) * np.exp(-t * 3) * .45


def sad_trombone(notes, durs):
    out = []
    for i, (f, d) in enumerate(zip(notes, durs)):
        t = tt(d)
        vib = 1 + (.012 * np.sin(2 * np.pi * 5.5 * t) * np.clip((t - .15) / .2, 0, 1) if i == len(notes) - 1 else 0)
        x = osc(f * vib, d, 'saw') + .4 * osc(f * 2 * vib, d, 'saw')
        # 'wah' -> lowpass opening then closing per note
        blocks = 24
        y = np.zeros_like(x)
        edges = np.linspace(0, len(x), blocks + 1).astype(int)
        for b in range(blocks):
            p = b / blocks
            fc = 500 + 1600 * np.sin(np.pi * min(1, p * 1.4)) if i < len(notes) - 1 else 500 + 1500 * np.exp(-p * 2.5)
            y[edges[b]:edges[b + 1]] = filt(x, 'lowpass', fc)[edges[b]:edges[b + 1]]
        y *= env_adsr(len(y), .03, .08 if i < len(notes) - 1 else .35)
        out.append(y)
    return np.concatenate(out) * .45


def sparkle(d=.5):
    t = tt(d)
    x = np.zeros_like(t)
    for k, f in enumerate((2093, 2637, 3136, 4186)):
        tk = np.clip(t - k * .05, 0, None)
        x += np.sin(2 * np.pi * f * tk) * np.exp(-tk * 9) * (t >= k * .05)
    return x * .18


# ---------- timeline ----------
# traffic ambience (rumble + distant engines)
amb = filt(noise(DUR), 'lowpass', 220) * .5 + filt(noise(DUR), 'bandpass', [300, 1200]) * .06
idle = np.sin(2 * np.pi * 38 * tt(DUR)) * (.5 + .5 * np.sin(2 * np.pi * 1.3 * tt(DUR))) * .15
amb = amb + idle
ta = tt(DUR)
amb_env = np.where(ta < 5.6, 1.0, np.where(ta < 6.2, 1 - (ta - 5.6) / .6, 0.0))
amb_env *= np.where((ta > 2.4) & (ta < 4.6), .55, 1.0)
amb_env = np.where(ta >= 12.0, .8, amb_env)
add(amb * amb_env, 0, .5)

# honks synced with the bubbles
add(horn(415, 523, .45), .12, .9, .25)
add(horn(590, 740, .4, 3500), .55, .7, -.35)
add(horn(330, 415, .55), 1.0, .9, -.5)
add(honk_double(660, 830, .16), 1.45, .65, .2)
add(horn(220, 277, .7, 1800), 1.85, 1.0, .3)

# realisation
add(whoosh(.5, 300, 3000), 2.38, .5)
add(ding(), 3.0, 1.0)
fall = osc(np.linspace(1800, 520, int(.4 * SR)), .4) * .18 * env_adsr(int(.4 * SR), .01, .05)
add(fall, 3.35, 1.0)
add(clunk(), 3.75, .55)
add(kick808(55, .5, 3, 2), 3.75, .6)

# hover mode deploy + spool up
add(whoosh(.45, 2500, 250), 4.4, .45)
for k, t0 in enumerate((4.62, 4.75, 4.88)):
    t = tt(.08)
    add(filt(noise(.08), 'bandpass', [1500, 5000]) * np.exp(-t * 60) * .5 + np.sin(2 * np.pi * (900 + 150 * k) * t) * np.exp(-t * 50) * .2, t0, .8)
servo = osc(np.linspace(400, 900, int(.4 * SR)), .4, 'sq')
add(filt(servo, 'lowpass', 1500) * .05 * env_adsr(len(servo), .02, .05), 4.6, 1.0)
riser_d = .52
rn = whoosh(riser_d, 400, 9000, 1.0) * np.linspace(.2, 1, int(riser_d * SR))
rt = osc(np.linspace(200, 1400, int(riser_d * SR)), riser_d, 'saw')
add(rn * .9 + filt(rt, 'lowpass', 3000) * .12 * np.linspace(0, 1, len(rt)), 5.0, .8)

# LIFT OFF: drop + gas blast
add(kick808(42, 1.6, 4, 3.5), 5.6, 1.1)
blast_d = 2.4
bt = tt(blast_d)
blast = filt(noise(blast_d), 'lowpass', 5000) * (np.exp(-bt * 1.8) * .9 + .1) * env_adsr(len(bt), .005, .3)
add(blast, 5.6, .55, -.2)
add(filt(noise(blast_d), 'lowpass', 4800) * (np.exp(-bt * 1.8) * .9 + .1) * env_adsr(len(bt), .005, .3), 5.6, .55, .2)
hov_d = 12.0 - 5.6
hn = filt(noise(hov_d), 'bandpass', [600, 6000])
add(hn * .06 * env_adsr(len(hn), .5, .05), 5.6, 1.0)

# phonk beat 150 BPM, 4 bars from 5.6 to 12.0 (16th = 0.1 s)
STEP = .1
BASE = 392.0
mel = [12, None, 12, 10, None, 7, None, 10, 12, None, 12, 10, None, 7, 8, 7,
       5, None, 5, 3, None, 0, None, 3, 5, None, 7, None, 3, None, 0, None]
bass = {0: 0, 6: 0, 10: 3, 14: -2}
beat_start = 5.6
for bar in range(4):
    b0 = beat_start + bar * 16 * STEP
    for st in range(16):
        t0 = b0 + st * STEP
        if st in bass and not (bar == 0 and st == 0):
            f = 49.0 * 2 ** (bass[st] / 12)
            add(kick808(f, .45 if st != 14 else .3, 2.4, 2.8), t0, .7)
        if st in (4, 12):
            add(clap(), t0, .9)
        if st % 2 == 0 or (bar % 2 == 1 and st >= 13):
            add(hat(.04 if st % 2 else .06), t0, .9 if st % 4 == 2 else .55, .3)
        n = mel[(bar % 2) * 16 + st]
        if n is not None:
            add(cowbell(BASE * 2 ** (n / 12)), t0, .55, -.15 if st % 2 else .15)

# flight sfx
add(whoosh(.7, 200, 4000), 9.4, .6)
for k in range(5):
    t = tt(.09)
    add(np.sin(2 * np.pi * np.linspace(2600, 3600, len(t)) * t) * np.exp(-t * 30) * .12, 10.25 + k * .06, 1.0, (k - 2) * .3)
coins = np.concatenate([sparkle(.35), np.zeros(1)])
add(ding(1567.98, .6), 10.7, .6)
add(ding(2093.0, .9), 10.78, .6)
add(coins, 10.7, 1.0)
zoom_d = .6
zt = tt(zoom_d)
zoom = osc(np.where(zt < .35, 300 + 900 * zt / .35, 1200 - 900 * (zt - .35) / .25), zoom_d, 'saw')
add(filt(zoom, 'lowpass', 2500) * np.sin(np.pi * zt / zoom_d) * .15 + whoosh(zoom_d, 500, 8000, .7), 11.3, 1.0)

# hard cut at 12.0: silence everything after the cut except ambience + closing sfx
cut = int(12.0 * SR)
L[cut:] = 0
R[cut:] = 0
add(amb[cut:] * .8, 12.0, .5)
add(sparkle(.5), 12.1, 1.0, .5)

# the sad guy
meep = osc(np.linspace(760, 690, int(.22 * SR)), .22, 'sq')
add(filt(meep, 'lowpass', 1800) * .14 * env_adsr(len(meep), .01, .06), 13.0, 1.0)
add(boing(.5), 13.3, 1.0)
add(clunk(), 13.78, .9)
add(kick808(60, .3, 2, 2), 13.78, .5)
rattle = np.zeros(int(1.2 * SR))
for k in range(14):
    p = int((k * .075 + .02 * np.sin(k)) * SR)
    t = tt(.04)
    hit = np.sin(2 * np.pi * (2400 + 300 * np.sin(k * 3)) * t) * np.exp(-t * 80)
    rattle[p:p + len(hit)] += hit * (1 - k / 14) * .12
add(rattle, 13.82, 1.0, .4)
wob_d = .35
wt = tt(wob_d)
add(np.sin(2 * np.pi * 1900 * wt) * (np.abs(np.sin(2 * np.pi * (8 + 30 * wt) * wt))) * np.exp(-wt * 6) * .1, 14.72, 1.0, .4)
add(sad_trombone([196.0, 185.0, 174.6, 164.8], [.25, .25, .25, .8]), 13.95, 1.0)

# ---------- master ----------
mix = np.stack([L, R])
mix = filt(mix, 'highpass', 28)
mix = np.tanh(mix * 1.1)
mix /= np.max(np.abs(mix)) + 1e-9
mix *= .89
fade = int(.03 * SR)
mix[:, -fade:] *= np.linspace(1, 0, fade)
out = sys.argv[1] if len(sys.argv) > 1 else 'audio.wav'
with wave.open(out, 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((mix.T * 32767).astype(np.int16).tobytes())
print('wrote', out)
