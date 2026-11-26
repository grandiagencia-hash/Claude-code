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
    (0.00, 2.95, 1.60, 380, 1290, "Gancho: resultado lado a lado no iPad"),
    (3.12, 9.62, 1.00, 540, 960, "Passo 1: toxina botulínica levantou o olhar"),
    (9.92, 13.15, 1.25, 840, 560, "Efeito lifting do Botox (punch-in no rosto)"),
    (21.50, 28.40, 1.70, 273, 1265, "Linhas de expressão: zoom na foto sorrindo"),
    (29.95, 34.02, 1.00, 540, 960, "Passo 2: ultrassom microfocado"),
    (34.42, 45.20, 1.15, 420, 1150, "Diagnóstico: rosto pesando e flacidez"),
    (46.36, 53.22, 1.25, 840, 520, "O que é o ultrassom microfocado"),
    (59.94, 64.70, 1.80, 252, 1210, "Antes: 'dessa face, mais arredondadinha'"),
    (65.30, 66.10, 1.80, 252, 1210, "Revelação: troca de foto no iPad"),
    (67.60, 68.85, 1.80, 252, 1210, "'para essa face'"),
    (69.00, 74.60, 1.80, 252, 1210, "Face mais fininha"),
    (129.76, 132.85, 1.80, 252, 1283, "Queixo mais aparente"),
    (139.95, 146.86, 1.00, 540, 960, "Comparando antes e depois"),
    (146.86, 151.95, 1.60, 291, 1300, "Fecho: sem perder a naturalidade"),
]
SEGMENTS = [(snap(a), snap(b), z, cx, cy, n) for a, b, z, cx, cy, n in SEGMENTS]

def crop_filter(z, cx, cy):
    if z == 1.0:
        return f"scale={W}:{H}:flags=lanczos"
    cw, ch = round(W / z / 2) * 2, round(H / z / 2) * 2
    x0 = min(max(0, cx - cw // 2), W - cw)
    y0 = min(max(0, cy - ch // 2), H - ch)
    return f"crop={cw}:{ch}:{x0}:{y0},scale={W}:{H}:flags=lanczos"

def run(cmd):
    subprocess.run(cmd, check=True)

# ---------- 1. Cortes de vídeo + áudio por segmento ----------
seg_files, offsets, t = [], [], 0.0
for i, (a, b, z, cx, cy, _) in enumerate(SEGMENTS):
    f = f"{OUT}/seg{i:02d}.mp4"
    d = b - a
    if not os.path.exists(f.replace(".mp4", ".mov")): run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.4f}", "-i", SRC, "-t", f"{d:.4f}",
         "-vf", crop_filter(z, cx, cy) + ",fps=30,format=yuv420p",
         "-af", f"afade=t=in:d=0.015,afade=t=out:st={d-0.02:.3f}:d=0.02,aresample=48000",
         "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2",
         f.replace(".mp4", ".mov")])
    seg_files.append(f.replace(".mp4", ".mov"))
    offsets.append(t)
    t += d
TOTAL = t
with open(f"{OUT}/concat.txt", "w") as fh:
    fh.writelines(f"file '{os.path.basename(s)}'\n" for s in seg_files)
run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{OUT}/concat.txt", "-c", "copy", f"{OUT}/cut.mov"])

def out_time(src_t):
    for (a, b, *_), off in zip(SEGMENTS, offsets):
        if a - 1e-6 <= src_t <= b + 1e-6:
            return off + (src_t - a)
    return None

# ---------- 2. Efeitos sonoros sintetizados (sem direitos autorais) ----------
SR = 48000
def save(name, x):
    x = np.clip(x, -1, 1)
    st = np.stack([x, x], 1)
    with wave.open(f"{OUT}/{name}.wav", "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((st * 32767).astype(np.int16).tobytes())

def whoosh(dur=0.5, f0=300, f1=4000):
    n = int(SR * dur); rng = np.random.default_rng(7); noise = rng.standard_normal(n)
    out = np.zeros(n); y1 = y2 = 0.0; x1 = x2 = 0.0
    for i in range(n):
        p = i / n
        fc = f0 * (f1 / f0) ** math.sin(math.pi * p * 0.5 + 0.0) if p < 1 else f1
        w0 = 2 * math.pi * fc / SR; q = 1.2; al = math.sin(w0) / (2 * q)
        b0, b2, a0, a1, a2 = al, -al, 1 + al, -2 * math.cos(w0), 1 - al
        x0 = noise[i]
        y0 = (b0 * x0 + b2 * x2 - a1 * y1 - a2 * y2) / a0
        x2, x1, y2, y1 = x1, x0, y1, y0
        out[i] = y0
    env = np.sin(np.linspace(0, math.pi, n)) ** 1.6
    out = out * env
    return out / np.max(np.abs(out)) * 0.9

def impact(dur=0.7):
    n = int(SR * dur); tt = np.arange(n) / SR
    f = 70 * np.exp(-tt * 6) + 42
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 6.5)
    click = np.random.default_rng(3).standard_normal(n) * np.exp(-tt * 90) * 0.35
    x = body + click
    return x / np.max(np.abs(x)) * 0.95

def pop(dur=0.09):
    n = int(SR * dur); tt = np.arange(n) / SR
    f = 1500 * np.exp(-tt * 18) + 600
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 45)
    return x / np.max(np.abs(x)) * 0.8

def shimmer(dur=1.4):
    n = int(SR * dur); tt = np.arange(n) / SR; x = np.zeros(n)
    for k, fr in enumerate([1318.5, 1568.0, 1975.5, 2637.0]):
        d = int(SR * 0.07 * k); seg = tt[: n - d]
        x[d:] += np.sin(2 * np.pi * fr * seg) * np.exp(-seg * 3.2) * (0.6 if k else 1)
    return x / np.max(np.abs(x)) * 0.7

save("sfx_whoosh", whoosh()); save("sfx_whoosh_short", whoosh(0.32, 500, 5000))
save("sfx_impact", impact()); save("sfx_pop", pop()); save("sfx_shimmer", shimmer())

# Momentos (no tempo FINAL) e volume em dB abaixo da fala
seg_start = lambda i: offsets[i]
SFX = [
    ("sfx_impact", 0.00, -17),                    # gancho
    ("sfx_pop", seg_start(1) + 0.05, -20),         # selo PASSO 1
    ("sfx_whoosh_short", seg_start(3) - 0.16, -22), # entra o zoom nas linhas de expressão
    ("sfx_pop", seg_start(4) + 0.05, -20),         # selo PASSO 2
    ("sfx_whoosh_short", seg_start(7) - 0.16, -22), # entra o zoom no iPad
    ("sfx_whoosh", seg_start(8) + 0.05, -16),      # troca de foto antes → depois
    ("sfx_whoosh_short", seg_start(13) - 0.16, -22),# zoom final
    ("sfx_shimmer", out_time(150.28), -21),        # "sem perder a naturalidade"
    ("sfx_pop", TOTAL - 0.1, -19),                 # entra o card final
]
CARD, XF = 3.2, 0.5
FINAL = TOTAL + CARD - XF

# ---------- 3. Mixagem de áudio ----------
inputs = ["-i", f"{OUT}/cut.mov"]
fc = [f"[0:a]highpass=f=80,acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=2,loudnorm=I=-14:TP=-1.5:LRA=9,apad=whole_dur={FINAL:.3f}[voz]"]
mix = ["[voz]"]
for k, (name, at, db) in enumerate(SFX):
    inputs += ["-i", f"{OUT}/{name}.wav"]
    ms = max(0, int(at * 1000))
    fc.append(f"[{k+1}:a]volume={db}dB,adelay={ms}|{ms}[s{k}]")
    mix.append(f"[s{k}]")
fc.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0:duration=first,alimiter=limit=0.89[a]")

# ---------- 4. Legendas e títulos (ASS) ----------
words = []
for s in json.load(open("transcript.json")):
    for w in s["words"]:
        txt = w["w"].strip()
        txt = txt.replace("TIE", "Tiê").replace("botolínica", "botulínica")
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
inputs += ["-loop", "1", "-framerate", "30", "-t", f"{CARD:.3f}", "-i", f"{OUT}/gfx/end.png"]
fc.append(f"[0:v]ass={OUT}/legendas.ass:fontsdir=fonts,format=yuva420p[v0]")
prev = "v0"
for k, (name, x, y, a, b2) in enumerate(GFX):
    idx = nA + k; fi = 0.0 if a == 0 else 0.25
    fc.append(f"[{idx}:v]format=rgba,fade=t=in:st={a:.3f}:d={max(fi,0.01):.2f}:alpha=1,fade=t=out:st={b2-0.25:.3f}:d=0.25:alpha=1[g{k}]")
    fc.append(f"[{prev}][g{k}]overlay={x}:{y}:enable='between(t,{a:.3f},{b2:.3f})'[v{k+1}]")
    prev = f"v{k+1}"
fc.append(f"[{prev}]format=yuv420p,fps=30,settb=AVTB[main]")
fc.append(f"[{nA + len(GFX)}:v]format=yuv420p,fps=30,settb=AVTB[card]")
fc.append(f"[main][card]xfade=transition=fade:duration={XF}:offset={TOTAL - XF:.3f}[v]")
# áudio: estender para o card final + pop quando o card entra
run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
     "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-profile:v", "high", "-pix_fmt", "yuv420p",
     "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-r", "30",
     "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{FINAL:.3f}", "-movflags", "+faststart", f"{OUT}/final.mp4"])
json.dump({"total": FINAL, "offsets": offsets, "segments": SEGMENTS, "sfx": SFX}, open(f"{OUT}/edl.json", "w"), indent=1, ensure_ascii=False)
print(f"OK  duração final {FINAL:.2f}s  ({len(SEGMENTS)} trechos, {len(chunks)} legendas)")
