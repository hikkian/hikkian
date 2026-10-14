"""Profile assets for github.com/hikkian: animated header, project cards, footer. Text is turned into paths, so the SVGs
look the same everywhere (GitHub shows SVGs as images: no web fonts load there).

Usage: python gen_assets.py FONT_DIR assets/
FONT_DIR holds inter-500/600/800.woff and jbm-500/700.woff (Inter and JetBrains Mono, Latin subsets from Google Fonts).
Needs: pip install fonttools uharfbuzz"""
import io
import sys
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

FONTS = Path(sys.argv[1])
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

THEMES = {
    "light": dict(bg="#F2EBDD", card="#F8F3E9", border="#E1D7C3", ink="#14232E", sub="#4A5860", muted="#7A857F",
                  accent="#E8643C", line="#C9C2B2", node="#D6CFBF", logo_bg="#14232E", logo_fg="#F2EBDD", grid="#E6DDCB",
                  pill="#EFE7D8"),
    "dark": dict(bg="#101B23", card="#14232E", border="#24384A", ink="#F2EBDD", sub="#AAB6BC", muted="#7D8C94",
                 accent="#E8643C", line="#2B3F4D", node="#33495A", logo_bg="#F2EBDD", logo_fg="#14232E", grid="#16242E",
                 pill="#1B2E3B"),
}


class Face:
    def __init__(self, name):
        p = FONTS / name
        self.tt = TTFont(p)
        self.upem = self.tt["head"].unitsPerEm
        self.gs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        # HarfBuzz does not read WOFF: hand it the same font as plain sfnt bytes
        raw = TTFont(p)
        raw.flavor = None
        buf = io.BytesIO()
        raw.save(buf)
        self.hbfont = hb.Font(hb.Face(hb.Blob(buf.getvalue())))

    def shape(self, text):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hbfont, buf, {"kern": True, "liga": True})
        return buf.glyph_infos, buf.glyph_positions

    def width(self, text, size):
        if not text:
            return 0.0
        _, pos = self.shape(text)
        return sum(p.x_advance for p in pos) * size / self.upem

    def path(self, text, x, y, size, fill, anchor="start", extra=""):
        infos, pos = self.shape(text)
        s = size / self.upem
        w = self.width(text, size)
        if anchor == "middle":
            x -= w / 2
        elif anchor == "end":
            x -= w
        pen = SVGPathPen(self.gs, ntos=lambda n: ("%.1f" % n).rstrip("0").rstrip("."))
        cx = 0
        for info, p in zip(infos, pos):
            name = self.order[info.codepoint]
            tp = TransformPen(pen, (s, 0, 0, -s, x + (cx + p.x_offset) * s, y - p.y_offset * s))
            self.gs[name].draw(tp)
            cx += p.x_advance
        d = pen.getCommands()
        return f'<path fill="{fill}" d="{d}"{extra}/>' if d else ""


INTER5, INTER6, INTER8 = Face("inter-500.woff"), Face("inter-600.woff"), Face("inter-800.woff")
MONO5, MONO7 = Face("jbm-500.woff"), Face("jbm-700.woff")


def wrap(face, text, size, width):
    lines, cur = [], ""
    for word in text.split():
        t = (cur + " " + word).strip()
        if face.width(t, size) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def logo(x, y, size, t):
    k = size / 150
    return (f'<g transform="translate({x} {y}) scale({k})">'
            f'<rect width="150" height="150" rx="36" fill="{t["logo_bg"]}"/>'
            f'<path d="M50 32 V120 M50 88 C50 58 101 58 101 88 V120" fill="none" stroke="{t["logo_fg"]}" stroke-width="19" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<circle cx="119" cy="41" r="11" fill="{t["accent"]}"><animate attributeName="r" values="11;13;11" dur="2.4s" repeatCount="indefinite"/></circle>'
            "</g>")


def graph(nodes, edges, hot, t, tag):
    """Edges draw in once, the orange nodes pulse, a small signal travels along the chain for ever."""
    out = []
    path = "M" + " L".join(f"{nodes[i][0]} {nodes[i][1]}" for i in edges)
    length = sum(((nodes[a][0] - nodes[b][0]) ** 2 + (nodes[a][1] - nodes[b][1]) ** 2) ** 0.5 for a, b in zip(edges, edges[1:]))
    out.append(f'<path id="g{tag}" d="{path}" fill="none" stroke="{t["line"]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" '
               f'stroke-dasharray="{length:.0f}" stroke-dashoffset="{length:.0f}"><animate attributeName="stroke-dashoffset" from="{length:.0f}" to="0" dur="1.6s" begin="0.2s" fill="freeze"/></path>')
    for n, (nx, ny) in enumerate(nodes):
        if n in hot:
            out.append(f'<circle cx="{nx}" cy="{ny}" r="10" fill="none" stroke="{t["accent"]}" stroke-width="2" opacity="0">'
                       f'<animate attributeName="r" values="10;24" dur="2.4s" begin="{1.2 + n * 0.3:.1f}s" repeatCount="indefinite"/>'
                       f'<animate attributeName="opacity" values="0.6;0" dur="2.4s" begin="{1.2 + n * 0.3:.1f}s" repeatCount="indefinite"/></circle>')
            out.append(f'<circle cx="{nx}" cy="{ny}" r="11" fill="{t["accent"]}" opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.4s" begin="0.9s" fill="freeze"/></circle>')
        else:
            out.append(f'<circle cx="{nx}" cy="{ny}" r="8" fill="{t["node"]}" opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.4s" begin="{0.3 + n * 0.15:.2f}s" fill="freeze"/></circle>')
    out.append(f'<circle r="4.5" fill="{t["accent"]}" opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.3s" begin="2s" fill="freeze"/>'
               f'<animateMotion dur="6s" begin="2s" repeatCount="indefinite" keyPoints="0;1;0" keyTimes="0;0.5;1" calcMode="linear"><mpath href="#g{tag}"/></animateMotion></circle>')
    return "".join(out)


def typing(phrases, x, y, size, t):
    """A typewriter that cycles through the phrases: each one is revealed by a clip rectangle, a caret follows it."""
    face = MONO7
    type_s, hold, del_s, gap = 0.065, 1.9, 0.025, 0.35
    events, tcur, spans = [], 0.0, []
    for p in phrases:
        n = len(p)
        steps = []
        for i in range(n + 1):
            steps.append((tcur + i * type_s, face.width(p[:i], size)))
        tcur += n * type_s + hold
        for i in range(n, -1, -1):
            steps.append((tcur + (n - i) * del_s, face.width(p[:i], size)))
        tcur += n * del_s + gap
        spans.append(steps)
    total = tcur
    clips, texts, caret_vals = [], [], {}
    for k, (p, steps) in enumerate(zip(phrases, spans)):
        vals = {0.0: 0.0}
        for tt, w in steps:
            vals[round(tt / total, 4)] = w
            caret_vals[round(tt / total, 4)] = w
        kt = sorted(vals)
        clips.append(f'<clipPath id="tp{k}"><rect x="{x}" y="{y - size}" height="{size * 1.4}" width="0">'
                     f'<animate attributeName="width" calcMode="discrete" dur="{total:.2f}s" repeatCount="indefinite" '
                     f'keyTimes="{";".join(f"{v:.4f}" for v in kt)}" values="{";".join(f"{vals[v]:.1f}" for v in kt)}"/></rect></clipPath>')
        texts.append(f'<g clip-path="url(#tp{k})">{face.path(p, x, y, size, t["accent"])}</g>')
    ck = sorted(set(caret_vals) | {0.0})
    caret_vals.setdefault(0.0, 0.0)
    caret = (f'<rect x="{x}" y="{y - size * 0.82}" width="{size * 0.55:.1f}" height="{size * 1.02:.1f}" rx="2" fill="{t["accent"]}" opacity="0.9">'
             f'<animate attributeName="x" calcMode="discrete" dur="{total:.2f}s" repeatCount="indefinite" keyTimes="{";".join(f"{v:.4f}" for v in ck)}" '
             f'values="{";".join(f"{x + caret_vals[v] + 3:.1f}" for v in ck)}"/>'
             f'<animate attributeName="opacity" values="0.9;0.9;0;0" keyTimes="0;0.5;0.5;1" dur="1s" repeatCount="indefinite"/></rect>')
    return "<defs>" + "".join(clips) + "</defs>" + "".join(texts) + caret


def header(theme):
    t = THEMES[theme]
    W, H = 1200, 380
    left = [(70, 70), (178, 150), (88, 245), (196, 300), (60, 345)]
    right = [(W - x, y) for x, y in [(62, 52), (176, 160), (92, 268), (190, 238), (70, 340)]]
    name_size, sub_size, mono_size = 66, 30, 25
    name_w = INTER8.width("Alisher Sharipov", name_size)
    block_w = 150 + 38 + max(name_w, 560)
    x0 = (W - block_w) / 2
    tx = x0 + 150 + 38
    body = [
        f'<rect width="{W}" height="{H}" rx="28" fill="{t["bg"]}"/>',
        f'<defs><pattern id="dots" width="26" height="26" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.6" fill="{t["grid"]}"/></pattern></defs>',
        f'<rect width="{W}" height="{H}" rx="28" fill="url(#dots)"/>',
        graph(left, [0, 1, 2, 3, 4], {1}, t, "l"),
        graph(right, [0, 1, 3, 2, 4], {1}, t, "r"),
        f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.6s" begin="0.1s" fill="freeze"/>',
        logo(x0, 115, 150, t),
        INTER8.path("Alisher Sharipov", tx, 172, name_size, t["ink"]),
        INTER6.path("AI / Full Stack developer", tx, 220, sub_size, t["sub"]),
        "</g>",
        typing(["building open-source projects", "local LLMs on consumer GPUs", "orchestrating AI agent sessions", "Go · Python · TypeScript"],
               tx + 2, 268, mono_size, t),
    ]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Alisher Sharipov — AI / Full Stack developer">'
           + "".join(body) + "</svg>")
    (OUT / f"header-{theme}.svg").write_text(svg, encoding="utf-8")


def pill(x, y, text, t, face=MONO5, size=13, color=None, fill=None, stroke=None):
    w = face.width(text, size) + 22
    return (f'<rect x="{x}" y="{y}" width="{w:.1f}" height="26" rx="13" fill="{fill or t["pill"]}" stroke="{stroke or t["border"]}"/>'
            + face.path(text, x + 11, y + 17.5, size, color or t["sub"])), w


def card(slug, theme, mark, title, status, desc, tags, foot):
    t = THEMES[theme]
    W, H = 440, 230
    out = [f'<defs><clipPath id="c"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="18"/></clipPath></defs>',
           f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="18" fill="{t["card"]}"/>',
           f'<rect x="0" y="0" width="{W}" height="7" fill="{t["accent"]}" clip-path="url(#c)"/>',
           f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="18" fill="none" stroke="{t["border"]}" stroke-width="1.5"/>']
    out.append(f'<rect x="26" y="30" width="46" height="46" rx="12" fill="{t["logo_bg"]}"/>')
    out.append(MONO7.path(mark, 49, 61, 20 if len(mark) == 1 else 15, t["logo_fg"], anchor="middle"))
    out.append(f'<circle cx="66" cy="37" r="4.5" fill="{t["accent"]}"/>')
    out.append(INTER8.path(title, 88, 63, 27, t["ink"]))
    sw = MONO5.width(status, 12) + 20
    out.append(f'<rect x="{W - 26 - sw:.1f}" y="40" width="{sw:.1f}" height="24" rx="12" fill="none" stroke="{t["accent"]}" stroke-width="1.5"/>')
    out.append(MONO5.path(status, W - 26 - sw / 2, 56.5, 12, t["accent"], anchor="middle"))
    for i, line in enumerate(wrap(INTER5, desc, 15.5, W - 52)[:3]):
        out.append(INTER5.path(line, 26, 108 + i * 23, 15.5, t["sub"]))
    x = 26
    for tag in tags:
        p, w = pill(x, 176, tag, t)
        if x + w > W - 26:
            break
        out.append(p)
        x += w + 8
    if foot:
        out.append(MONO5.path(foot, W - 26, 214, 11.5, t["muted"], anchor="end"))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{title}: {desc}">'
           + "".join(out) + "</svg>")
    (OUT / f"card-{slug}-{theme}.svg").write_text(svg, encoding="utf-8")


def now_card(theme):
    t = THEMES[theme]
    W, H = 440, 230
    out = [f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="18" fill="{t["card"]}" stroke="{t["border"]}" stroke-width="1.5" stroke-dasharray="6 6"/>',
           f'<circle cx="38" cy="50" r="7" fill="{t["accent"]}"><animate attributeName="opacity" values="1;0.25;1" dur="1.6s" repeatCount="indefinite"/></circle>',
           INTER8.path("Right now", 56, 59, 25, t["ink"])]
    items = [("Shura", "taking it to 1.0, next stop: AMD Radeon via Vulkan"),
             ("Barid", "1.0 is out; small releases from user feedback"),
             ("Based in", "Astana, Kazakhstan (UTC+5)")]
    y = 102
    for head, text in items:
        out.append(f'<circle cx="34" cy="{y - 5}" r="3.5" fill="{t["accent"]}"/>')
        out.append(INTER8.path(head, 48, y, 16, t["ink"]))
        hw = INTER8.width(head, 16)
        lines = wrap(INTER5, text, 15, W - 78 - hw)[:2]
        for i, line in enumerate(lines):
            out.append(INTER5.path(line, 56 + hw if i == 0 else 48, y + i * 21, 15, t["sub"]))
        y += 21 * len(lines) + 20
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Right now: Shura on the way to 1.0, Barid 1.0 is out, based in Astana">'
           + "".join(out) + "</svg>")
    (OUT / f"card-now-{theme}.svg").write_text(svg, encoding="utf-8")


def footer(theme):
    t = THEMES[theme]
    W, H = 1200, 90
    nodes = [(40, 60), (200, 30), (380, 62), (560, 34), (740, 64), (920, 30), (1060, 58), (1160, 36)]
    out = [graph(nodes, list(range(len(nodes))), {3, 6}, t, "f")]
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="">' + "".join(out) + "</svg>"
    (OUT / f"footer-{theme}.svg").write_text(svg, encoding="utf-8")


def section(text, theme, slug):
    """A section title in the same type as the header (markdown headings would be GitHub's own font)."""
    t = THEMES[theme]
    W, H = 1200, 64
    w = INTER8.width(text, 30)
    out = [f'<circle cx="12" cy="34" r="7" fill="{t["accent"]}"/>', INTER8.path(text, 32, 45, 30, t["ink"]),
           f'<path d="M{48 + w:.0f} 34 H{W - 4}" stroke="{t["line"]}" stroke-width="2" stroke-linecap="round" stroke-dasharray="2 10"/>']
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{text}">' + "".join(out) + "</svg>"
    (OUT / f"title-{slug}-{theme}.svg").write_text(svg, encoding="utf-8")


for th in THEMES:
    header(th)
    card("shura", th, "S", "Shura", "pre-1.0 · MIT",
         "Fully local AI coding workstation: a 35B MoE model at 200k context on a single 12 GB GPU, without slowing your desktop.",
         ["llama.cpp", "MoE expert cache", "VRAM valve"], "Python · Shell")
    card("barid", th, "B", "Barid", "v1.0.2 · MIT",
         "A prompt relay board for people who run several AI agent sessions: order, dependencies, shared resources, file conflicts.",
         ["agent skill", "zero-dependency", "browser panel"], "Python · Linux · macOS · Windows")
    card("shuracode", th, "SC", "ShuraCode", "MIT",
         "Private, local AI coding agent for the terminal, with a memory that lasts across sessions. Built on OpenCode.",
         ["terminal", "local-first", "memory"], "Python · TypeScript")
    now_card(th)
    footer(th)
    for slug, text in (("projects", "Featured projects"), ("stack", "Tech stack"), ("activity", "Contribution activity"), ("about", "About me")):
        section(text, th, slug)
print("ok", sorted(p.name for p in OUT.iterdir()))
