"""Edita o vídeo da Mariana Brumatti: cortes, punch-ins, legendas, títulos e efeitos sonoros.
Uso: python3 build.py  (gera out/final.mp4)"""
import json, math, os, subprocess, wave
import numpy as np

SRC = "raw/original.MOV"
OUT = "out"
FPS = 30
W, H = 1080, 1920
os.makedirs(OUT, exist_ok=True)

def snap(t):
    return round(t * FPS) / FPS

# (início, fim, zoom, centro_x, centro_y, nota) — tempos do arquivo original
SEGMENTS = [
    (0.00, 2.95, 1.35, 380, 1290, "Gancho: resultado lado a lado no iPad"),
    (3.12, 9.62, 1.00, 540, 960, "Passo 1: toxina botulínica levantou o olhar"),
    (9.92, 13.15, 1.10, 840, 560, "Efeito lifting do Botox (punch-in no rosto)"),
    (21.50, 28.40, 1.40, 273, 1265, "Linhas de expressão: zoom na foto sorrindo"),
    (29.95, 34.02, 1.00, 540, 960, "Passo 2: ultrassom microfocado"),
    (34.42, 45.20, 1.06, 420, 1150, "Diagnóstico: rosto pesando e flacidez"),
    (46.36, 53.22, 1.10, 840, 520, "O que é o ultrassom microfocado"),
    (59.94, 64.70, 1.40, 252, 1210, "Antes: 'dessa face, mais arredondadinha'"),
    (65.30, 66.10, 1.40, 252, 1210, "Revelação: troca de foto no iPad"),
    (67.60, 68.85, 1.40, 252, 1210, "'para essa face'"),
    (69.00, 74.60, 1.40, 252, 1210, "Face mais fininha"),
    (129.76, 132.85, 1.40, 252, 1283, "Queixo mais aparente"),
    (139.95, 146.86, 1.00, 540, 960, "Comparando antes e depois"),
    (146.86, 151.95, 1.35, 291, 1300, "Fecho: sem perder a naturalidade"),
]
SEGMENTS = [(snap(a), snap(b), z, cx, cy, n) for a, b, z, cx, cy, n in SEGMENTS]

def run(cmd):
    subprocess.run(cmd, check=True)

# ---------- 1. Trechos com zoom animado (sem corte seco) ----------
# Cada trecho começa no enquadramento do anterior e desliza até o seu em 0,5 s (ease in-out),
# com um leve "respiro" de zoom contínuo (+3%) para a imagem nunca ficar parada.
XD = 0.20          # duração da dissolução entre trechos
EASE = 1.00        # duração do movimento de câmera entre enquadramentos
def zoom_filter(prev, cur, d):
    (zp, xp, yp), (z, cx, cy) = prev, cur
    T = EASE if (zp, xp, yp) != (z, cx, cy) else 0.001
    E = f"if(lt(t,{T}),(1-cos(PI*t/{T}))/2,1)"
    Z = f"(({zp})+(({z})-({zp}))*{E})*(1+0.02*t/{d:.3f})"
    CX = f"(({xp})+(({cx})-({xp}))*{E})"
    CY = f"(({yp})+(({cy})-({yp}))*{E})"
    return (f"scale=w='2*trunc({W}*{Z}/2)':h='2*trunc({H}*{Z}/2)':eval=frame:flags=bicubic,"
            f"crop={W}:{H}:x='clip({CX}*{Z}-{W//2},0,2*trunc({W}*{Z}/2)-{W})':y='clip({CY}*{Z}-{H//2},0,2*trunc({H}*{Z}/2)-{H})'")

seg_files, durs = [], []
prev = (1.0, 540, 960)
for i, (a, b, z, cx, cy, _) in enumerate(SEGMENTS):
    f = f"{OUT}/segz{i:02d}.mov"; d = b - a
    if not os.path.exists(f):
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.4f}", "-i", SRC, "-t", f"{d:.4f}",
             "-vf", zoom_filter(prev, (z, cx, cy), d) + ",fps=30,format=yuv420p,settb=AVTB",
             "-af", "aresample=48000", "-c:v", "libx264", "-crf", "14", "-preset", "medium",
             "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", f])
    seg_files.append(f); durs.append(d); prev = (z, cx, cy)

offsets, acc = [], 0.0
for i, d in enumerate(durs):
    offsets.append(acc - i * XD if i else 0.0)
    acc += d
offsets = [sum(durs[:i]) - i * XD for i in range(len(durs))]
TOTAL = sum(durs) - (len(durs) - 1) * XD

if not os.path.exists(f"{OUT}/cutz.mov") or os.path.getmtime(f"{OUT}/cutz.mov") < max(os.path.getmtime(s) for s in seg_files):
    ins = sum((["-i", s] for s in seg_files), [])
    g = []; v, a_ = "0:v", "0:a"
    for i in range(1, len(seg_files)):
        g.append(f"[{v}][{i}:v]xfade=transition=fade:duration={XD}:offset={offsets[i]:.4f}[xv{i}]")
        g.append(f"[{a_}][{i}:a]acrossfade=d={XD}:c1=tri:c2=tri[xa{i}]")
        v, a_ = f"xv{i}", f"xa{i}"
    run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(g), "-map", f"[{v}]", "-map", f"[{a_}]",
         "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-c:a", "pcm_s16le", f"{OUT}/cutz.mov"])

def out_time(src_t):
    for (a, b, *_), off in zip(SEGMENTS, offsets):
        if a - 1e-6 <= src_t <= b + 1e-6:
            return off + (src_t - a)
    return None

# ---------- 2. Efeitos sonoros (sintetizados, estéreo, com ambiência) ----------
SR = 48000
RNG = np.random.default_rng(11)
def norm(x, peak=0.9):
    m = np.max(np.abs(x)); return x / m * peak if m else x
def save(name, st):
    st = np.clip(st, -1, 1)
    if st.ndim == 1: st = np.stack([st, st], 1)
    with wave.open(f"{OUT}/{name}.wav", "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((st * 32767).astype(np.int16).tobytes())
def bandsweep(n, f0, f1, q=1.1, curve=0.5, seed=7):
    noise = np.random.default_rng(seed).standard_normal(n); out = np.zeros(n)
    y1 = y2 = x1 = x2 = 0.0
    for i in range(n):
        p = i / n; fc = f0 * (f1 / f0) ** (p ** curve)
        w0 = 2 * math.pi * min(fc, SR * 0.45) / SR; al = math.sin(w0) / (2 * q)
        a0 = 1 + al; x0 = noise[i]
        y0 = (al * x0 - al * x2 + 2 * math.cos(w0) * y1 - (1 - al) * y2) / a0
        x2, x1, y2, y1 = x1, x0, y1, y0; out[i] = y0
    return out
def reverb(st, wet=0.22, size=1.1):
    n = int(SR * size); tt = np.arange(n) / SR
    outs = []
    for ch, seed in ((0, 1), (1, 2)):
        ir = np.random.default_rng(seed).standard_normal(n) * np.exp(-tt * 5.5); ir /= np.sqrt(np.sum(ir ** 2))
        x = st[:, ch]; L = len(x) + n
        y = np.fft.irfft(np.fft.rfft(x, L) * np.fft.rfft(ir, L), L)
        outs.append(np.concatenate([x, np.zeros(n)]) * (1 - wet) + y * wet * 2.2)
    return np.stack(outs, 1)
def pan(x, p0, p1):
    p = np.linspace(p0, p1, len(x)); ang = (p + 1) * math.pi / 4
    return np.stack([x * np.cos(ang), x * np.sin(ang)], 1)
def whoosh(dur, f0, f1, p0=-0.7, p1=0.7, seed=7, wet=0.2):
    n = int(SR * dur); x = bandsweep(n, f0, f1, seed=seed)
    env = np.sin(np.linspace(0, math.pi, n)) ** 1.8 * np.linspace(0.6, 1, n)
    return norm(reverb(pan(norm(x * env), p0, p1), wet))
def riser(dur=1.2):
    n = int(SR * dur); tt = np.arange(n) / SR
    noise = bandsweep(n, 400, 6000, q=0.9, curve=1.4, seed=5)
    tone = np.sin(2 * np.pi * np.cumsum(220 * (4 ** (tt / dur) ** 1.5)) / SR) * 0.35
    env = (tt / dur) ** 2.2
    x = norm(noise) * env + tone * env
    return norm(reverb(pan(x, -0.3, 0.3), 0.3))
def impact(dur=1.0):
    n = int(SR * dur); tt = np.arange(n) / SR
    body = np.sin(2 * np.pi * np.cumsum(60 * np.exp(-tt * 7) + 40) / SR) * np.exp(-tt * 5)
    snap_ = RNG.standard_normal(n) * np.exp(-tt * 60) * 0.4
    return norm(reverb(np.stack([body + snap_] * 2, 1), 0.25, 1.4), 0.95)
def tick(dur=0.06):
    n = int(SR * dur); tt = np.arange(n) / SR
    x = np.sin(2 * np.pi * 2400 * tt) * np.exp(-tt * 140) + RNG.standard_normal(n) * np.exp(-tt * 400) * 0.3
    return norm(reverb(np.stack([x] * 2, 1), 0.12, 0.5), 0.8)
def sparkle(dur=1.3, base=1760.0):
    n = int(SR * dur); tt = np.arange(n) / SR; L = np.zeros(n); R = np.zeros(n)
    for k, r in enumerate([1, 1.25, 1.5, 2.0, 2.5]):
        d0 = int(SR * 0.045 * k); s = tt[: n - d0]
        tone = np.sin(2 * np.pi * base * r * s) * np.exp(-s * 4.5) * (0.9 - 0.12 * k)
        (L if k % 2 == 0 else R)[d0:] += tone; (R if k % 2 == 0 else L)[d0:] += tone * 0.5
    return norm(reverb(np.stack([L, R], 1), 0.3), 0.7)
def bell(dur=2.2, f=880.0):
    n = int(SR * dur); tt = np.arange(n) / SR; x = np.zeros(n)
    for r, a, dcy in ((1, 1, 2.2), (2.0, 0.5, 3), (2.76, 0.35, 4), (5.4, 0.15, 6)):
        x += np.sin(2 * np.pi * f * r * tt) * a * np.exp(-tt * dcy)
    x *= np.minimum(1, tt / 0.004)
    return norm(reverb(np.stack([x] * 2, 1), 0.3, 1.6), 0.75)

save("fx_impact", impact()); save("fx_tick", tick()); save("fx_riser", riser())
save("fx_whoosh_lr", whoosh(0.55, 250, 4500, -0.8, 0.8, 7)); save("fx_whoosh_rl", whoosh(0.55, 250, 4500, 0.8, -0.8, 8))
save("fx_swish_lr", whoosh(0.32, 900, 7000, -0.5, 0.5, 9, 0.12)); save("fx_swish_rl", whoosh(0.32, 900, 7000, 0.5, -0.5, 10, 0.12))
save("fx_reveal", whoosh(0.8, 150, 6000, -0.9, 0.9, 12, 0.3)); save("fx_sparkle", sparkle()); save("fx_bell", bell())

seg_start = lambda i: offsets[i]
END_CARD = False   # card final com CTA (desligado a pedido do cliente)
CARD, XF = 3.2, 0.5
FINAL = TOTAL + CARD - XF if END_CARD else TOTAL
SFX = [("fx_impact", 0.0, -15), ("fx_swish_lr", 0.0, -22), ("fx_sparkle", out_time(2.3), -24)]
REVEAL = 8
for i in range(1, len(SEGMENTS)):
    if i in (REVEAL, REVEAL + 1):
        continue
    moved = SEGMENTS[i][2:5] != SEGMENTS[i - 1][2:5]
    side = "lr" if i % 2 else "rl"
    SFX.append((f"fx_whoosh_{side}" if moved else f"fx_swish_{side}", seg_start(i) - 0.22, -21 if moved else -25))
SFX += [
    ("fx_riser", seg_start(REVEAL) - 1.15, -23),        # sobe a tensão antes da troca de foto
    ("fx_reveal", seg_start(REVEAL) + 0.05, -15),       # troca antes → depois
    ("fx_sparkle", seg_start(REVEAL) + 0.55, -21),
    ("fx_swish_rl", seg_start(REVEAL + 1) - 0.2, -26),
    ("fx_tick", seg_start(1) + 0.05, -19), ("fx_tick", seg_start(4) + 0.05, -19), ("fx_tick", seg_start(12) + 0.05, -19),
    ("fx_swish_lr", seg_start(1) + 0.3, -25),           # lower third
    ("fx_sparkle", out_time(73.6), -24),                # "fininha"
    ("fx_sparkle", out_time(132.2), -25),               # "mais aparente"
    ("fx_sparkle", out_time(150.3), -21),               # "sem perder a naturalidade"
    *([("fx_whoosh_lr", TOTAL - XF - 0.25, -19),        # entra o card final
       ("fx_bell", TOTAL - XF + 0.15, -19)] if END_CARD else []),
]
SFX = [s for s in SFX if s[1] is not None]

# ---------- 3. Mixagem de áudio ----------
inputs = ["-i", f"{OUT}/cutz.mov"]
fc = [f"[0:a]highpass=f=80,acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=2,loudnorm=I=-15.5:TP=-2:LRA=9,apad=whole_dur={FINAL:.3f}[voz]"]
mix = ["[voz]"]
for k, (name, at, db) in enumerate(SFX):
    inputs += ["-i", f"{OUT}/{name}.wav"]
    ms = max(0, int(at * 1000))
    fc.append(f"[{k+1}:a]volume={db}dB,adelay={ms}|{ms}[s{k}]")
    mix.append(f"[s{k}]")
fc.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0:duration=first,alimiter=limit=0.79:level=false[a]")

# ---------- 4. Legendas e títulos (ASS) ----------
words = []
for s in json.load(open("transcript.json")):
    for w in s["words"]:
        txt = w["w"].strip()
        txt = txt.replace("TIE", "Tay").replace("botolínica", "botulínica")
        a, b = out_time(w["s"] + 0.02), out_time(w["e"] - 0.02)
        if a is None or b is None:
            continue
        words.append([txt, a, b])
DROP_LEADING = {"Então,"}
words = [w for w in words if w[0] not in DROP_LEADING]

KEY = {"resultado.", "olhar", "lifting", "Botox.", "expressão", "ruguinha.", "segundo", "passo", "ultrassom",
       "microfocado.", "microfocado,", "flacidez", "contorno", "colágeno", "arredondadinha,", "fininha.", "queixo",
       "aparente,", "pele", "marcadinha", "naturalidade.", "toxina", "baixo"}
WEAK = {"a","o","as","os","da","de","do","dos","das","e","que","na","no","nessa","dessa","essa","esse","um","uma","para","pra","ao","é","foi","tem","ficou","até","mais","aqui","aquele","dela","nós","gente","ver"}
chunks, cur = [], []
for w in words:
    cur.append(w)
    chars = sum(len(x[0]) + 1 for x in cur)
    if w[0][-1] in ".,?!" or ((len(cur) >= 4 or chars >= 17) and w[0].lower() not in WEAK) or len(cur) >= 6:
        chunks.append(cur); cur = []
if cur: chunks.append(cur)

def ts(x):
    x = max(0, x); h = int(x // 3600); m = int(x % 3600 // 60); s = x % 60
    return f"{h}:{m:02d}:{s:05.2f}"

import sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import overlays
os.makedirs(f"{OUT}/gfx", exist_ok=True)
overlays.hook_title(f"{OUT}/gfx/hook.png")
SELOS = [overlays.selo(f"{OUT}/gfx/selo1.png", "PASSO 1 ·", "TOXINA BOTULÍNICA"),
         overlays.selo(f"{OUT}/gfx/selo2.png", "PASSO 2 ·", "ULTRASSOM MICROFOCADO"),
         overlays.selo(f"{OUT}/gfx/selo3.png", "ANTES E", "DEPOIS")]
overlays.lower_third(f"{OUT}/gfx/lower.png")
overlays.end_card(f"{OUT}/gfx/end.png")

lines = []
for i, c in enumerate(chunks):
    start = c[0][1]
    end = min(c[-1][2] + 0.25, chunks[i + 1][0][1]) if i + 1 < len(chunks) else c[-1][2] + 0.4
    used = False; parts = []
    for txt, *_ in c:
        show = txt.rstrip(".,!")
        if not used and txt in KEY:
            parts.append("{\\fnMB Lora Medium Italic\\fs88}" + show.lower() + "{\\fnMB Montserrat SemiBold\\fs76}"); used = True
        else:
            parts.append(show)
    lines.append(f"Dialogue: 1,{ts(start)},{ts(end)},Leg,,0,0,0,,{{\\fad(60,0)}}" + " ".join(parts))
ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Leg,MB Montserrat SemiBold,76,&H00ECF0F7,&H00ECF0F7,&H002A2C3A,&H782A2C3A,0,0,0,0,100,100,0.5,0,1,3.6,2.5,2,80,80,470,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(lines) + "\n"
open(f"{OUT}/legendas.ass", "w").write(ass)

# ---------- 5. Render final: legendas + artes + card final ----------
nA = len(inputs) // 2
s1, s2, s3 = seg_start(1), seg_start(4), seg_start(12)
GFX = [  # arquivo, x, y, início, fim
    ("hook.png", 0, 240, 0, s1),
    ("selo1.png", (W - SELOS[0][0]) // 2, 250, s1, s2),
    ("selo2.png", (W - SELOS[1][0]) // 2, 250, s2, s3),
    ("selo3.png", (W - SELOS[2][0]) // 2, 250, s3, TOTAL),
    ("lower.png", 30, 560, s1 + 0.35, seg_start(2) - 0.05),
]
for g in GFX:
    inputs += ["-loop", "1", "-framerate", "30", "-t", f"{TOTAL:.3f}", "-i", f"{OUT}/gfx/{g[0]}"]
if END_CARD: inputs += ["-loop", "1", "-framerate", "30", "-t", f"{CARD:.3f}", "-i", f"{OUT}/gfx/end.png"]
fc.append(f"[0:v]ass={OUT}/legendas.ass:fontsdir=fonts,format=yuva420p[v0]")
prev = "v0"
for k, (name, x, y, a, b2) in enumerate(GFX):
    idx = nA + k; fi = 0.0 if a == 0 else 0.25
    fc.append(f"[{idx}:v]format=rgba,fade=t=in:st={a:.3f}:d={max(fi,0.01):.2f}:alpha=1,fade=t=out:st={b2-0.25:.3f}:d=0.25:alpha=1[g{k}]")
    fc.append(f"[{prev}][g{k}]overlay={x}:{y}:enable='between(t,{a:.3f},{b2:.3f})'[v{k+1}]")
    prev = f"v{k+1}"
fc.append(f"[{prev}]format=yuv420p,fps=30,settb=AVTB[main]")
if END_CARD:
    fc.append(f"[{nA + len(GFX)}:v]format=yuv420p,fps=30,settb=AVTB[card]")
    fc.append(f"[main][card]xfade=transition=fade:duration={XF}:offset={TOTAL - XF:.3f}[v]")
else:
    fc.append("[main]null[v]")
# áudio: estender para o card final + pop quando o card entra
run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
     "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-profile:v", "high", "-pix_fmt", "yuv420p",
     "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-r", "30",
     "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{FINAL:.3f}", "-movflags", "+faststart", f"{OUT}/final.mp4"])
json.dump({"total": FINAL, "offsets": offsets, "segments": SEGMENTS, "sfx": SFX}, open(f"{OUT}/edl.json", "w"), indent=1, ensure_ascii=False)
print(f"OK  duração final {FINAL:.2f}s  ({len(SEGMENTS)} trechos, {len(chunks)} legendas)")
