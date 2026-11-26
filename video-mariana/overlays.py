"""Gera as artes da identidade Mariana Brumatti (PNG com transparência) para sobrepor no vídeo."""
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1920
BROWN = (58, 44, 42)
BLUSH = (232, 213, 206)
TAUPE = (148, 139, 133)
CREAM = (247, 240, 236)
F = "fonts/"

def font(name, size, wght):
    f = ImageFont.truetype(F + name, size)
    try:
        f.set_variation_by_axes([wght])
    except Exception:
        pass
    return f

MONT = lambda s, w=500: font("Montserrat[wght].ttf", s, w)
LORA = lambda s, w=400: font("Lora[wght].ttf", s, w)
LORA_I = lambda s, w=400: font("Lora-Italic[wght].ttf", s, w)

def tracked_width(d, text, f, track):
    return sum(d.textlength(ch, font=f) for ch in text) + track * (len(text) - 1)

def draw_tracked(d, xy, text, f, fill, track):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + track
    return x

def runs_width(d, runs, gap=0):
    return sum(tracked_width(d, t, f, tr) for t, f, _, tr in runs) + gap * (len(runs) - 1)

def soft_shadow(img, radius=14, opacity=150, offset=(0, 4)):
    a = img.split()[3]
    sh = Image.new("RGBA", img.size, BROWN + (0,))
    sh.putalpha(a.point(lambda v: v * opacity // 255))
    sh = sh.filter(ImageFilter.GaussianBlur(radius))
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.alpha_composite(sh, offset)
    out.alpha_composite(img)
    return out

def symbol(size, color):
    """Símbolo aproximado (8 raios, centro vazado). Substituir pelo logo oficial quando houver."""
    S = 4; R = size * S / 2
    im = Image.new("RGBA", (size * S, size * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    c = R; wdt = R * 0.115
    for k in range(8):
        ang = math.radians(k * 45)
        r0, r1 = (0.26, 1.0) if k in (0, 4) else (0.26, 0.74)
        x0, y0 = c + math.cos(ang) * R * r0, c + math.sin(ang) * R * r0
        x1, y1 = c + math.cos(ang) * R * r1 * 0.96, c + math.sin(ang) * R * r1 * 0.96
        d.line([(x0, y0), (x1, y1)], fill=color, width=int(wdt))
        for (x, y) in ((x0, y0), (x1, y1)):
            d.ellipse([x - wdt / 2, y - wdt / 2, x + wdt / 2, y + wdt / 2], fill=color)
    return im.resize((size, size), Image.LANCZOS)

def wordmark(d, cx, y, size, color):
    fi, fr = LORA_I(size, 420), LORA(size, 420)
    w1, w2, gap = d.textlength("Mariana", font=fi), d.textlength("Brumatti", font=fr), size * 0.18
    x = cx - (w1 + gap + w2) / 2
    d.text((x, y), "Mariana", font=fi, fill=color)
    d.text((x + w1 + gap, y), "Brumatti", font=fr, fill=color)

def pill(runs, path, pad_x=34, height=74, fill=BROWN + (150,), stroke=BLUSH + (230,)):
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    gap = 14
    tw = runs_width(tmp, runs, gap)
    w = int(tw + pad_x * 2); im = Image.new("RGBA", (w + 8, height + 8), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([4, 4, w + 3, height + 3], radius=height // 2, fill=fill, outline=stroke, width=2)
    x = 4 + pad_x
    for t, f, col, tr in runs:
        bb = d.textbbox((0, 0), "A", font=f)
        y = 4 + (height - (bb[3] - bb[1])) / 2 - bb[1]
        x = draw_tracked(d, (x, y), t, f, col, tr) + gap
    im.save(path)
    return im.size

def selo(path, a, b):
    return pill([(a, MONT(27, 500), CREAM, 5.5), (b, MONT(27, 700), CREAM, 5.5)], path)

def hook_title(path):
    im = Image.new("RGBA", (W, 420), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    f1, f2 = MONT(70, 600), LORA_I(96, 450)
    t1, t2 = "Botox + ultrassom", "microfocado"
    d.text(((W - d.textlength(t1, font=f1)) / 2, 40), t1, font=f1, fill=CREAM)
    d.text(((W - d.textlength(t2, font=f2)) / 2, 112), t2, font=f2, fill=CREAM)
    f3 = MONT(26, 600); t3 = "ANTES E DEPOIS"; tw = tracked_width(d, t3, f3, 7)
    d.line([(W / 2 - tw / 2 - 70, 268), (W / 2 - tw / 2 - 22, 268)], fill=BLUSH, width=2)
    d.line([(W / 2 + tw / 2 + 22, 268), (W / 2 + tw / 2 + 70, 268)], fill=BLUSH, width=2)
    draw_tracked(d, ((W - tw) / 2, 252), t3, f3, CREAM, 7)
    soft_shadow(im, 16, 170).save(path)

def lower_third(path):
    im = Image.new("RGBA", (760, 190), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.line([(20, 30), (88, 30)], fill=BLUSH, width=4)
    d.text((20, 48), "Mariana Brumatti", font=MONT(56, 600), fill=CREAM)
    draw_tracked(d, (22, 128), "BIOMÉDICA · HARMONIZAÇÃO FACIAL", MONT(22, 600), CREAM, 5.2)
    soft_shadow(im, 12, 190).save(path)

def end_card(path):
    im = Image.new("RGB", (W, H), BROWN); d = ImageDraw.Draw(im)
    sym = symbol(150, CREAM + (255,)); im.paste(sym, ((W - 150) // 2, 610), sym)
    wordmark(d, W / 2, 790, 82, CREAM)
    f_l, f_i, f_b = MONT(54, 300), LORA_I(62, 420), MONT(58, 600)
    a, b = "Cada rosto pede um ", "olhar"
    wa, wb = d.textlength(a, font=f_l), d.textlength(b, font=f_i)
    x = (W - wa - wb) / 2
    d.text((x, 975), a, font=f_l, fill=CREAM); d.text((x + wa, 966), b, font=f_i, fill=CREAM)
    c = "individual."; d.text(((W - d.textlength(c, font=f_b)) / 2, 1048), c, font=f_b, fill=(255, 255, 255))
    pim = Image.open(path.replace(".png", "_pill.png")) if False else None
    tmp = Image.new("RGBA", (10, 10)); pill([("ME MANDA", MONT(25, 500), CREAM, 7), ("AVALIAÇÃO", MONT(25, 700), (255, 255, 255), 7), ("NO DIRECT", MONT(25, 500), CREAM, 7)],
                                           "/tmp/_pill.png", pad_x=44, height=82, fill=BROWN + (255,), stroke=CREAM + (170,))
    p = Image.open("/tmp/_pill.png"); im.paste(p, ((W - p.width) // 2, 1185), p)
    draw_tracked(d, ((W - tracked_width(d, "HARMONIZAÇÃO FACIAL · BURITIS", MONT(22, 500), 6)) / 2, 1330), "HARMONIZAÇÃO FACIAL · BURITIS", MONT(22, 500), TAUPE, 6)
    im.save(path)

if __name__ == "__main__":
    import os; os.makedirs("out/gfx", exist_ok=True)
    hook_title("out/gfx/hook.png")
    print("selo1", selo("out/gfx/selo1.png", "PASSO 1 ·", "TOXINA BOTULÍNICA"))
    print("selo2", selo("out/gfx/selo2.png", "PASSO 2 ·", "ULTRASSOM MICROFOCADO"))
    print("selo3", selo("out/gfx/selo3.png", "ANTES E", "DEPOIS"))
    lower_third("out/gfx/lower.png")
    end_card("out/gfx/end.png")
