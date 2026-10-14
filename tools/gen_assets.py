"""Draws the profile pictures (header, project cards, section titles, footer) from content.toml.

Text is turned into outlines, so the pictures look the same everywhere: GitHub shows SVGs as images, and images load no fonts.
The GitHub Action runs this on every change of content.toml; to run it by hand:

    pip install fonttools uharfbuzz
    python tools/gen_assets.py content.toml out/
"""
import html
import io
import sys
import tomllib
import urllib.request
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

# Inter and JetBrains Mono (SIL Open Font License), Latin subsets from Google Fonts
FONT_URLS = {
    "inter-500.woff": "https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuI6fAZ9hjg.woff",
    "inter-600.woff": "https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuGKYAZ9hjg.woff",
    "inter-800.woff": "https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuDyYAZ9hjg.woff",
    "jbm-500.woff": "https://fonts.gstatic.com/s/jetbrainsmono/v24/tDbY2o-flEEny0FZhsfKu5WU4zr3E_BX0PnT8RD8-qxTOlOT.woff",
    "jbm-700.woff": "https://fonts.gstatic.com/s/jetbrainsmono/v24/tDbY2o-flEEny0FZhsfKu5WU4zr3E_BX0PnT8RD8L6tTOlOT.woff",
}

THEMES = {
    "light": dict(bg="#F2EBDD", card="#F8F3E9", border="#E1D7C3", ink="#14232E", sub="#4A5860", muted="#7A857F",
                  accent="#E8643C", line="#C9C2B2", node="#D6CFBF", logo_bg="#14232E", logo_fg="#F2EBDD", grid="#E6DDCB",
                  pill="#EFE7D8"),
    "dark": dict(bg="#101B23", card="#14232E", border="#24384A", ink="#F2EBDD", sub="#AAB6BC", muted="#7D8C94",
                 accent="#E8643C", line="#2B3F4D", node="#33495A", logo_bg="#F2EBDD", logo_fg="#14232E", grid="#16242E",
                 pill="#1B2E3B"),
}

WARNINGS = []


def fonts_dir() -> Path:
    d = Path.home() / ".cache" / "profile-fonts"
    d.mkdir(parents=True, exist_ok=True)
    for name, url in FONT_URLS.items():
        if not (d / name).exists():
            (d / name).write_bytes(urllib.request.urlopen(url, timeout=30).read())
    return d


class Face:
    def __init__(self, path: Path):
        self.tt = TTFont(path)
        self.upem = self.tt["head"].unitsPerEm
        self.gs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.cmap = self.tt.getBestCmap()
        # HarfBuzz does not read WOFF: hand it the same font as plain sfnt bytes
        raw = TTFont(path)
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

    def path(self, text, x, y, size, fill, anchor="start"):
        missing = sorted({ch for ch in text if ord(ch) not in self.cmap and not ch.isspace()})
        if missing:
            WARNINGS.append(f"no letter for {''.join(missing)!r} in {text!r} (Latin letters only)")
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
            tp = TransformPen(pen, (s, 0, 0, -s, x + (cx + p.x_offset) * s, y - p.y_offset * s))
            self.gs[self.order[info.codepoint]].draw(tp)
            cx += p.x_advance
        d = pen.getCommands()
        return f'<path fill="{fill}" d="{d}"/>' if d else ""


def wrap(face, text, size, width, max_lines, where):
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
    if len(lines) > max_lines:
        WARNINGS.append(f"{where}: the text is too long and was cut after {max_lines} lines: {text!r}")
    return lines[:max_lines]


def svg(w, h, label, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-label="{html.escape(label, quote=True)}">' + "".join(body) + "</svg>")


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


def typing(face, phrases, x, y, size, t):
    """A typewriter that cycles through the phrases: each one is revealed by a clip rectangle, a caret follows it."""
    type_s, hold, del_s, gap = 0.065, 1.9, 0.025, 0.35
    tcur, spans = 0.0, []
    for p in phrases:
        n = len(p)
        steps = [(tcur + i * type_s, face.width(p[:i], size)) for i in range(n + 1)]
        tcur += n * type_s + hold
        steps += [(tcur + (n - i) * del_s, face.width(p[:i], size)) for i in range(n, -1, -1)]
        tcur += n * del_s + gap
        spans.append(steps)
    total = tcur
    clips, texts, caret_vals = [], [], {0.0: 0.0}
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
    ck = sorted(caret_vals)
    caret = (f'<rect x="{x}" y="{y - size * 0.82}" width="{size * 0.55:.1f}" height="{size * 1.02:.1f}" rx="2" fill="{t["accent"]}" opacity="0.9">'
             f'<animate attributeName="x" calcMode="discrete" dur="{total:.2f}s" repeatCount="indefinite" keyTimes="{";".join(f"{v:.4f}" for v in ck)}" '
             f'values="{";".join(f"{x + caret_vals[v] + 3:.1f}" for v in ck)}"/>'
             f'<animate attributeName="opacity" values="0.9;0.9;0;0" keyTimes="0;0.5;0.5;1" dur="1s" repeatCount="indefinite"/></rect>')
    return "<defs>" + "".join(clips) + "</defs>" + "".join(texts) + caret


class Painter:
    def __init__(self, fonts: Path, out: Path):
        self.out = out
        self.inter5, self.inter6, self.inter8 = (Face(fonts / f"inter-{w}.woff") for w in (500, 600, 800))
        self.mono5, self.mono7 = Face(fonts / "jbm-500.woff"), Face(fonts / "jbm-700.woff")

    def save(self, name, text):
        (self.out / name).write_text(text, encoding="utf-8")

    def header(self, theme, h):
        t = THEMES[theme]
        W, H = 1200, 380
        left = [(70, 70), (178, 150), (88, 245), (196, 300), (60, 345)]
        right = [(W - x, y) for x, y in [(62, 52), (176, 160), (92, 268), (190, 238), (70, 340)]]
        name_w = self.inter8.width(h["name"], 66)
        if name_w > 780:
            WARNINGS.append(f"header: the name is too long to fit: {h['name']!r}")
        x0 = (W - (150 + 38 + max(name_w, 560))) / 2
        tx = x0 + 150 + 38
        body = [
            f'<rect width="{W}" height="{H}" rx="28" fill="{t["bg"]}"/>',
            f'<defs><pattern id="dots" width="26" height="26" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.6" fill="{t["grid"]}"/></pattern></defs>',
            f'<rect width="{W}" height="{H}" rx="28" fill="url(#dots)"/>',
            graph(left, [0, 1, 2, 3, 4], {1}, t, "l"),
            graph(right, [0, 1, 3, 2, 4], {1}, t, "r"),
            f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.6s" begin="0.1s" fill="freeze"/>',
            logo(x0, 115, 150, t),
            self.inter8.path(h["name"], tx, 172, 66, t["ink"]),
            self.inter6.path(h["title"], tx, 220, 30, t["sub"]),
            "</g>",
            typing(self.mono7, h["phrases"], tx + 2, 268, 25, t),
        ]
        self.save(f"header-{theme}.svg", svg(W, H, f"{h['name']}, {h['title']}", body))

    def pill(self, x, y, text, t):
        w = self.mono5.width(text, 13) + 22
        return (f'<rect x="{x}" y="{y}" width="{w:.1f}" height="26" rx="13" fill="{t["pill"]}" stroke="{t["border"]}"/>'
                + self.mono5.path(text, x + 11, y + 17.5, 13, t["sub"])), w

    def card(self, theme, c):
        t = THEMES[theme]
        W, H = 440, 230
        mark = c.get("mark") or c["title"][:1]
        out = [f'<defs><clipPath id="c"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="18"/></clipPath></defs>',
               f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="18" fill="{t["card"]}"/>',
               f'<rect x="0" y="0" width="{W}" height="7" fill="{t["accent"]}" clip-path="url(#c)"/>',
               f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="18" fill="none" stroke="{t["border"]}" stroke-width="1.5"/>',
               f'<rect x="26" y="30" width="46" height="46" rx="12" fill="{t["logo_bg"]}"/>',
               self.mono7.path(mark, 49, 61, 20 if len(mark) == 1 else 15, t["logo_fg"], anchor="middle"),
               f'<circle cx="66" cy="37" r="4.5" fill="{t["accent"]}"/>',
               self.inter8.path(c["title"], 88, 63, 27, t["ink"])]
        if c.get("status"):
            sw = self.mono5.width(c["status"], 12) + 20
            out.append(f'<rect x="{W - 26 - sw:.1f}" y="40" width="{sw:.1f}" height="24" rx="12" fill="none" stroke="{t["accent"]}" stroke-width="1.5"/>')
            out.append(self.mono5.path(c["status"], W - 26 - sw / 2, 56.5, 12, t["accent"], anchor="middle"))
        for i, line in enumerate(wrap(self.inter5, c["text"], 15.5, W - 52, 3, f"card {c['file']}")):
            out.append(self.inter5.path(line, 26, 108 + i * 23, 15.5, t["sub"]))
        x = 26
        for tag in c.get("tags", []):
            p, w = self.pill(x, 176, tag, t)
            if x + w > W - 26:
                WARNINGS.append(f"card {c['file']}: no room for the tag {tag!r}")
                break
            out.append(p)
            x += w + 8
        if c.get("footer"):
            out.append(self.mono5.path(c["footer"], W - 26, 214, 11.5, t["muted"], anchor="end"))
        self.save(f"card-{c['file']}-{theme}.svg", svg(W, H, f"{c['title']}: {c['text']}", out))

    def now(self, theme, n):
        t = THEMES[theme]
        W, H = 440, 230
        out = [f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="18" fill="{t["card"]}" stroke="{t["border"]}" stroke-width="1.5" stroke-dasharray="6 6"/>',
               f'<circle cx="38" cy="50" r="7" fill="{t["accent"]}"><animate attributeName="opacity" values="1;0.25;1" dur="1.6s" repeatCount="indefinite"/></circle>',
               self.inter8.path(n["title"], 56, 59, 25, t["ink"])]
        y = 102
        for item in n["items"]:
            out.append(f'<circle cx="34" cy="{y - 5}" r="3.5" fill="{t["accent"]}"/>')
            out.append(self.inter8.path(item["head"], 48, y, 16, t["ink"]))
            hw = self.inter8.width(item["head"], 16)
            lines = wrap(self.inter5, item["text"], 15, W - 78 - hw, 2, f"now: {item['head']}")
            for i, line in enumerate(lines):
                out.append(self.inter5.path(line, 56 + hw if i == 0 else 48, y + i * 21, 15, t["sub"]))
            last = y + 21 * (len(lines) - 1)
            y += 21 * len(lines) + 20
        if last > H - 14:
            WARNINGS.append("now: too many lines, the last ones fall off the card (keep it to three short items)")
        label = n["title"] + ": " + "; ".join(f"{i['head']} {i['text']}" for i in n["items"])
        self.save(f"card-now-{theme}.svg", svg(W, H, label, out))

    def footer(self, theme):
        t = THEMES[theme]
        nodes = [(40, 60), (200, 30), (380, 62), (560, 34), (740, 64), (920, 30), (1060, 58), (1160, 36)]
        self.save(f"footer-{theme}.svg", svg(1200, 90, "", [graph(nodes, list(range(len(nodes))), {3, 6}, t, "f")]))

    def section(self, theme, slug, text):
        """A section title in the same type as the header (a markdown heading would be GitHub's own font)."""
        t = THEMES[theme]
        w = self.inter8.width(text, 30)
        out = [f'<circle cx="12" cy="34" r="7" fill="{t["accent"]}"/>', self.inter8.path(text, 32, 45, 30, t["ink"]),
               f'<path d="M{48 + w:.0f} 34 H1196" stroke="{t["line"]}" stroke-width="2" stroke-linecap="round" stroke-dasharray="2 10"/>']
        self.save(f"title-{slug}-{theme}.svg", svg(1200, 64, text, out))


def main():
    content = tomllib.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    p = Painter(fonts_dir(), out)
    for theme in THEMES:
        p.header(theme, content["header"])
        for c in content["cards"]:
            p.card(theme, c)
        p.now(theme, content["now"])
        p.footer(theme)
        for slug, text in content["titles"].items():
            p.section(theme, slug, text)
    for w in dict.fromkeys(WARNINGS):
        print("warning:", w)
    print(f"{len(list(out.glob('*.svg')))} pictures in {out}")


if __name__ == "__main__":
    main()
