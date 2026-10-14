"""Translation coverage check for Open Bx.

    python3 check_i18n.py                     # UI strings (static/i18n/*.json + index.html)
    DATABASE_URL=... python3 check_i18n.py --db   # + location content in the database

1. Every language file has every key in en.json (and no extra keys), with the
   same {placeholders}, and no empty strings.
2. Every key used in index.html (data-i18n*, t('...')) exists in en.json.
3. index.html has no user-visible text outside data-i18n elements (except an
   allowlist: brand name, emoji, language names written in their own language).
4. --db: which location fields have no translation (they fall back to English).
Exit code 1 if anything in 1-3 is missing.
"""
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
LANGS = ["en", "es", "vi", "zh", "ar"]
ALLOW_TEXT = {"Open Bx", "✕", "English", "Español", "Tiếng Việt", "中文", "العربية",
              "🌐 English (US)", "🌐 Español (Spanish)", "🌐 Tiếng Việt (Vietnamese)",
              "🌐 中文 (Chinese)", "🌐 العربية (Arabic)", "(", ")", "1"}


def flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        else:
            out[key] = v
    return out


class TextScan(HTMLParser):
    VOID = {"input", "br", "img", "meta", "link", "hr", "source"}

    def __init__(self):
        super().__init__()
        self.stack, self.problems = [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("translate") == "no":
            a = {}
        for attr in ("placeholder", "title", "aria-label", "alt"):
            if a.get(attr) and f"data-i18n-{attr}" not in a:
                self.problems.append(f"<{tag}> {attr}={a[attr]!r} has no data-i18n-{attr}")
        if tag not in self.VOID:
            self.stack.append((tag, "data-i18n" in a))

    def handle_endtag(self, tag):
        while self.stack:
            t, _ = self.stack.pop()
            if t == tag:
                break

    def handle_data(self, data):
        text = data.strip()
        if not text or any(t in ("script", "style", "svg", "title") for t, _ in self.stack):
            return
        if any(flag for _, flag in self.stack):
            return
        if text in ALLOW_TEXT or not re.search(r"[A-Za-zÀ-ɏ؀-ۿ一-鿿]", text):
            return
        self.problems.append(f"untranslated text: {text[:70]!r}")


def main():
    dicts = {l: json.loads((HERE / "static" / "i18n" / f"{l}.json").read_text(encoding="utf-8")) for l in LANGS}
    flat = {l: flatten(d) for l, d in dicts.items()}
    en = flat["en"]
    problems = []
    for l in LANGS[1:]:
        missing = sorted(set(en) - set(flat[l]))
        extra = sorted(set(flat[l]) - set(en))
        problems += [f"{l}: missing key {k}" for k in missing]
        problems += [f"{l}: extra key {k}" for k in extra]
        for k, v in flat[l].items():
            if k not in en:
                continue
            if isinstance(v, str):
                if not v.strip():
                    problems.append(f"{l}: empty {k}")
                if set(re.findall(r"\{\w+\}", v)) != set(re.findall(r"\{\w+\}", en[k])):
                    problems.append(f"{l}: placeholders differ in {k}")
                same_ok = ("NYC Open Data", "you@example.com", "(718)", "Bronx, NY", "Fordham", "English",
                           "Español", "Tiếng Việt", "中文", "العربية", "Email", "Error")
                if v == en[k] and not any(x in v for x in same_ok):
                    problems.append(f"{l}: {k} is identical to English: {v!r}")

    html = (HERE / "index.html").read_text(encoding="utf-8")
    used = set(re.findall(r'data-i18n(?:-[a-z-]+)?="([^"]+)"', html))
    used |= set(re.findall(r"\bt\('([a-zA-Z0-9_]+\.[a-zA-Z0-9_.]+)'", html))
    used = {k for k in used if not k.endswith(("_", "."))}  # prefixes of dynamic keys
    for k in sorted(used):
        if k not in en and not any(e.startswith(k + ".") for e in en):
            problems.append(f"index.html uses unknown key {k}")
    scan = TextScan()
    scan.feed(html)
    problems += ["index.html: " + p for p in scan.problems]

    print(f"{len(en)} UI strings x {len(LANGS)} languages; {len(used)} keys referenced in index.html")
    for p in problems:
        print("  " + p)
    print("UI check:", "OK" if not problems else f"{len(problems)} problem(s)")

    if "--db" in sys.argv:
        import psycopg
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            rows = conn.execute("SELECT id, source, name, ai_summary, services, open_status FROM resources WHERE active").fetchall()
        print(f"\nlocation content ({len(rows)} active locations): rows missing a language fall back to English")
        for field_i, field in enumerate(["name", "ai_summary", "services", "open_status"], start=2):
            for l in LANGS[1:]:
                miss = [r for r in rows if r[field_i] and r[field_i].get("en") and not r[field_i].get(l)]
                by_src = {}
                for r in miss:
                    by_src[r[1]] = by_src.get(r[1], 0) + 1
                print(f"  {field:<12} {l}: {len(miss):>3} untranslated {by_src if by_src else ''}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
