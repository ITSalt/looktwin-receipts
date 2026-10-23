#!/usr/bin/env python3
"""H3 receipt builder — stdlib only."""
from __future__ import annotations
import html, re, sys
from pathlib import Path
from urllib.parse import unquote

PREF = re.compile(r"(?<![A-Za-z0-9])(ghp_|github_pat_|sk-[A-Za-z0-9_-]*?[A-Za-z0-9_]{20}|sk-(?=[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-]))(?=[A-Za-z0-9_-]*[A-Z])[A-Za-z0-9_](?:[A-Za-z0-9_-]*[A-Za-z0-9_])?|xox[abprs]-|AKIA[0-9A-Z]{16}|AIza[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-]))")
TGTOK = re.compile(r"(?<![0-9])[0-9]{6,12}:[A-Za-z0-9_-]{30,}")  # bot token: id:secret, secret may hold "-"
OCT = r"(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])"
IPV4 = re.compile(rf"(?<![\w.]){OCT}(?:\.{OCT}){{3}}(?![\w]|\.[0-9])")
LONG = re.compile(r"(?<![A-Za-z0-9_/])[A-Za-z0-9_]{32,}(?![A-Za-z0-9_])")
HEX = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
EMAIL = re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
MD = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
URL = re.compile(r"https?://[^\s)\]>|<\"]+")
PIPE = re.compile(r"(?<!\\)\|")
# H3b-2: inside a URL "/" does not shield a run; a 40/64-hex run is exempt only by position
LONGU = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z0-9_]{32,}(?![A-Za-z0-9_])")
SHA = r"([0-9a-f]{64}|[0-9a-f]{40})(?![A-Za-z0-9_])"
KEYSEG = re.compile(r"/(?:commit|blob|tree|raw|blame|commits)/" + SHA)
CMP = re.compile(r"/compare/" + SHA + r"(?:\.\.\.?" + SHA + ")?")
# H3b-3: a base64-alphabet run with "/" or "+" inside, 32+ long, holding upper, lower and digit
B64 = re.compile(r"(?<![A-Za-z0-9_+/])[A-Za-z0-9_+/]{32,}={0,2}(?![A-Za-z0-9_+/=])")

def b64_secret(t):
    for m in B64.finditer(t):
        v = m.group()
        if ("/" in v or "+" in v) and re.search("[A-Z]", v) and re.search("[a-z]", v) and re.search("[0-9]", v):
            return True
    return False

def url_secret(u):
    """Scan the percent-decoded URL after the scheme. A hex run is exempt only in the
    literal path (before ? and #), right after /keyword/ or inside /compare/A..B, and
    only when that path has no % escape, so %2F never makes a new segment."""
    rest = u.split("://", 1)[1]
    path = re.split(r"[?#]", rest, maxsplit=1)[0]
    ok = set()
    if "%" not in path:  # path is then a prefix of the decoded text, spans line up
        for m in KEYSEG.finditer(path):
            ok.add(m.span(1))
        for m in CMP.finditer(path):
            ok.update(m.span(g) for g in (1, 2) if m.group(g))
    if any(m.span() not in ok for m in LONGU.finditer(unquote(rest))):
        return True
    # H3b-3: query and fragment are values, not paths: check them decoded; each path segment too
    tail = rest[len(path):]
    return b64_secret(unquote(tail)) or any(b64_secret(unquote(seg)) for seg in path.split("/"))

def die(m):
    print(m, file=sys.stderr); sys.exit(1)


def sk_titlecase_slug(tok: str) -> bool:
    """True when tok looks like sk-Title-Cased-Words (klava-ru c3c087e2)."""
    if not tok.startswith("sk-"):
        return False
    segs = tok[3:].split("-")
    if len(segs) < 2:
        return False
    titled = sum(1 for s in segs if re.fullmatch(r"[A-Z][a-z]+", s))
    return titled >= len(segs) - 1

def secret(line, n):
    if EMAIL.search(line):  # whole line, URLs included (mailto:, ?u=a@b.c)
        return f"email address on line {n}"
    for m in MD.finditer(line):
        if not m.group(2).startswith(("https://", "http://")):
            return f"non-http link on line {n}"
    if any(not sk_titlecase_slug(m.group(0)) for m in PREF.finditer(line)):
        return f"secret-like token on line {n}"
    if TGTOK.search(line):
        return f"secret-like token on line {n}"
    if IPV4.search(line):
        return f"IP address on line {n}"
    if any(url_secret(m.group()) for m in URL.finditer(line)):
        return f"secret-like token in a URL on line {n}"
    s = MD.sub(" ", URL.sub(" ", line))
    if any(not HEX.fullmatch(t.group()) for t in LONG.finditer(s)):
        return f"secret-like token on line {n}"
    if b64_secret(s):
        return f"secret-like token on line {n}"
    return None

def split_row(line):
    return [c.strip().replace("\\|", "|") for c in PIPE.split(line.strip().strip("|"))]

def table(lines, i):
    hdr = split_row(lines[i])
    i += 1
    if i < len(lines) and re.fullmatch(r"\s*\|?(\s*:?-+:?\s*\|)+\s*:?-*:?\s*", lines[i]):
        i += 1  # separator row is optional
    rows = []
    while i < len(lines) and lines[i].strip().startswith("|"):
        row = split_row(lines[i])
        if len(row) != len(hdr):
            die(f"line {i + 1}: {len(row)} cells, header has {len(hdr)} (escape a literal | as \\|)")
        rows.append(row)
        i += 1
    return hdr, rows, i

def a(url, text):
    return f'<a href="{html.escape(url, quote=True)}">{html.escape(text)}</a>'

def plain(t):
    out, last = [], 0
    for m in URL.finditer(t):
        u = m.group().rstrip(".,;:!?")
        out.append(html.escape(t[last:m.start()])); out.append(a(u, u))
        last = m.start() + len(u)
    out.append(html.escape(t[last:]))
    return "".join(out)

def cell(t):
    out, last = [], 0
    for m in MD.finditer(t):
        out.append(plain(t[last:m.start()]))
        out.append(a(m.group(2), m.group(1)))
        last = m.end()
    out.append(plain(t[last:]))
    return "".join(out)

def build(md, out_dir):
    lines = md.read_text(encoding="utf-8").splitlines()
    for n, line in enumerate(lines, 1):
        e = secret(line, n)
        if e: die(e)
    title, exp, wh, wr, lh, lr = "Receipt", [], [], [], [], []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("# ") and not line.startswith("##"):
            title = line[2:].strip(); i += 1; continue
        if line.strip() == "## Experiment":
            i += 1
            while i < len(lines) and not lines[i].startswith("##"):
                if lines[i].strip(): exp.append(lines[i].strip())
                i += 1
            continue
        if line.strip() in ("## Week", "## Ledger"):
            kind = line.strip()
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("|"):
                if lines[i].startswith("##"): break
                i += 1
            if i < len(lines) and lines[i].strip().startswith("|"):
                h, r, i = table(lines, i)
                if kind == "## Week": wh, wr = h, r
                else: lh, lr = h, r
            continue
        i += 1
    qi = next((j for j, h in enumerate(lh) if h.lower() == "quote"), None)
    if qi is not None:
        for rnum, row in enumerate(lr, 1):
            if qi < len(row) and len(row[qi]) > 280:
                die(f"quote longer than 280 characters on ledger row {rnum}")
    parts = [
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>{html.escape(title)}</title>",
        "<style>body{font-family:system-ui,sans-serif;margin:1rem;line-height:1.45;max-width:52rem}"
        "table{border-collapse:collapse;width:100%;font-size:.95rem}"
        "th,td{border:1px solid #ccc;padding:.4rem .55rem;text-align:left;vertical-align:top}"
        "th{background:#f4f4f4}blockquote{margin:.2rem 0;padding:.35rem .6rem;background:#fafafa;border-left:3px solid #888}"
        "@media(max-width:640px){body{margin:.6rem}table{font-size:.85rem}}</style></head><body>",
        f"<h1>{html.escape(title)}</h1><h2>Experiment</h2><ul>",
    ]
    for item in exp:
        t = item[2:].strip() if item.startswith("- ") else item
        parts.append(f"<li>{cell(t)}</li>")
    parts.append("</ul><h2>Week</h2>")
    if wh:
        parts.append("<table><thead><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in wh) + "</tr></thead><tbody>")
        for row in wr:
            parts.append("<tr>" + "".join(f"<td>{cell(c)}</td>" for c in row) + "</tr>")
        parts.append("</tbody></table>")
    parts.append("<h2>Ledger</h2>")
    if lh:
        parts.append("<table><thead><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in lh) + "</tr></thead><tbody>")
        for row in lr:
            cells = []
            for j, c in enumerate(row):
                if qi is not None and j == qi and c:
                    cells.append(f"<td><blockquote>{cell(c)}</blockquote></td>")
                else:
                    cells.append(f"<td>{cell(c)}</td>")
            parts.append("<tr>" + "".join(cells) + "</tr>")
        parts.append("</tbody></table>")
    parts.append("</body></html>\n")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text("".join(parts), encoding="utf-8")

def main():
    if len(sys.argv) != 3: die("usage: python3 build.py week.md out/")
    build(Path(sys.argv[1]), Path(sys.argv[2]))

if __name__ == "__main__":
    main()
