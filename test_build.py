#!/usr/bin/env python3
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build.py"

SAMPLE = """# Receipt 13–16.10.2026
## Experiment
- An AI studio ships code written by agents on getpostingboard.dev.
## Week
| Metric | Value | Source |
| --- | --- | --- |
| Merged PRs | 26 | gh pr list --state merged |
| With board code | 14 | same |
## Ledger
| Task | Promised | Done | Merged | Author | Quote |
| --- | --- | --- | --- | --- | --- |
| P1, P2 | [thread](https://getpostingboard.dev/v1/posts/bae900a1-049d-4e33-be85-06e1d7e4b358) | 13.10 | [mirror](https://github.com/ITSalt/photo-check-bot-mirror) | rosenrot | "PR 64 merged, tests 41/41" — rosenrot, 13.10 |
| X1 | [thread](https://getpostingboard.dev/v1/posts/00000000-0000-0000-0000-000000000000) | — | — tests failed | example-agent | "tests failed on gold pair 2" — example-agent, 14.10 |
"""


SPEC = """# Receipt 13–16.10.2026
## Experiment
- An AI studio ships code written by agents on getpostingboard.dev.
## Week
| Metric | Value | Source |
| Merged PRs | 26 | gh pr list --state merged |
| With board code | 14 | same |
## Ledger
| Task | Promised | Done | Merged | Author |
| P1, P2 | [thread](https://getpostingboard.dev/v1/posts/bae900a1-049d-4e33-be85-06e1d7e4b358) | 13.10 | [mirror](https://github.com/ITSalt/photo-check-bot-mirror) | rosenrot |
| X1 | [thread](https://getpostingboard.dev/v1/posts/00000000-0000-0000-0000-000000000000) | — | — tests failed | example-agent |
"""

def run_build(md: str, out: Path) -> subprocess.CompletedProcess:
    md_path = out.parent / "week.md"
    md_path.write_text(md, encoding="utf-8")
    return subprocess.run(
        ["python3", str(BUILD), str(md_path), str(out)],
        capture_output=True,
        text=True,
    )


class TestBuild(unittest.TestCase):
    def test_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            a, b = td / "a", td / "b"
            self.assertEqual(run_build(SAMPLE, a).returncode, 0)
            self.assertEqual(run_build(SAMPLE, b).returncode, 0)
            self.assertEqual(
                (a / "index.html").read_bytes(), (b / "index.html").read_bytes()
            )

    def test_urls_as_href(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            out = td / "out"
            self.assertEqual(run_build(SAMPLE, out).returncode, 0)
            page = (out / "index.html").read_text(encoding="utf-8")
            for url in (
                "https://getpostingboard.dev/v1/posts/bae900a1-049d-4e33-be85-06e1d7e4b358",
                "https://github.com/ITSalt/photo-check-bot-mirror",
                "https://getpostingboard.dev/v1/posts/00000000-0000-0000-0000-000000000000",
            ):
                self.assertIn(f'href="{url}"', page)

    def test_secret_rejected(self):
        bad = SAMPLE + "\nnote " + "ghp" + "_EXAMPLETOKENSHOULDFAILHERE123\n"
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            out = td / "out"
            r = run_build(bad, out)
            self.assertNotEqual(r.returncode, 0)
            self.assertTrue(r.stderr.strip())
            self.assertFalse((out / "index.html").exists())

    def test_long_token_rejected(self):
        tok = "A" * 32
        bad = SAMPLE.replace("example-agent", tok)
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            out = td / "out"
            r = run_build(bad, out)
            self.assertNotEqual(r.returncode, 0)
            self.assertFalse((out / "index.html").exists())

    def test_email_rejected_handle_ok(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            out = td / "out"
            self.assertEqual(run_build(SAMPLE, out).returncode, 0)  # @rosenrot in quote ok via handle form
            bad = SAMPLE + "\ncontact me@example.com please\n"
            r = run_build(bad, td / "out2")
            self.assertNotEqual(r.returncode, 0)

    def test_no_external_script_or_http_assets(self):
        import re
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            out = td / "out"
            self.assertEqual(run_build(SAMPLE, out).returncode, 0)
            page = (out / "index.html").read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"<script[^>]+src", page, re.I))
            self.assertIsNone(re.search(r"<link[^>]+http", page, re.I))
            for m in re.finditer(r"<style>(.*?)</style>", page, re.S | re.I):
                self.assertNotIn("http", m.group(1))

    def test_quotes_escaped(self):
        md = SAMPLE.replace(
            '"PR 64 merged, tests 41/41" — rosenrot, 13.10',
            '"said <b>no</b> & \"yes\"" — rosenrot, 13.10',
        )
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            out = td / "out"
            self.assertEqual(run_build(md, out).returncode, 0)
            page = (out / "index.html").read_text(encoding="utf-8")
            self.assertIn("&lt;b&gt;no&lt;/b&gt;", page)
            self.assertNotIn("<b>no</b>", page)
            self.assertIn("said", page)

    def test_quote_too_long(self):
        long_q = ("word " * 60).strip()  # >280 chars, no secret-like token
        assert len(long_q) > 280
        md = SAMPLE.replace(
            '"PR 64 merged, tests 41/41" — rosenrot, 13.10', long_q
        )
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            out = td / "out"
            r = run_build(md, out)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("280", r.stderr)
            self.assertFalse((out / "index.html").exists())

    def test_emdash_visible(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            out = td / "out"
            self.assertEqual(run_build(SAMPLE, out).returncode, 0)
            page = (out / "index.html").read_text(encoding="utf-8")
            self.assertIn("—", page)

    def test_spec_input_no_separator(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td); out = td / "out"
            self.assertEqual(run_build(SPEC, out).returncode, 0)
            page = (out / "index.html").read_text(encoding="utf-8")
            self.assertIn("<td>Merged PRs</td>", page)
            self.assertIn("<td>— tests failed</td>", page)

    def test_words_and_hashes_not_secrets(self):
        for frag in ("Risk-free", "desk-check", "xoxo", "OAKIAN",
                     "commit " + "a3" * 20, "sha " + "0b" * 32):
            with self.subTest(frag=frag), tempfile.TemporaryDirectory() as td:
                out = Path(td) / "out"
                md = SAMPLE.replace("tests 41/41", frag)
                self.assertEqual(run_build(md, out).returncode, 0, frag)
        with tempfile.TemporaryDirectory() as td:
            md = SAMPLE.replace("photo-check-bot-mirror", "task-runner")
            self.assertEqual(run_build(md, Path(td) / "out").returncode, 0)

    def test_real_tokens_still_fail(self):
        for frag in ("xoxb-1234-abcd", "AKIA" + "ABCDEFGHIJKLMNOP", "sk-" + "abc123" * 4,
                     "A1b2" * 9, "ab" * 20 + "x"):
            with self.subTest(frag=frag), tempfile.TemporaryDirectory() as td:
                out = Path(td) / "out"
                r = run_build(SAMPLE.replace("tests 41/41", frag), out)
                self.assertNotEqual(r.returncode, 0, frag)
                self.assertIn("line 12", r.stderr)
                self.assertFalse((out / "index.html").exists())

    def test_pipe_in_quote(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            r = run_build(SAMPLE.replace("PR 64 merged", "PR 64 | merged"), td / "a")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("line 12", r.stderr)
            self.assertFalse((td / "a" / "index.html").exists())
            self.assertEqual(run_build(SAMPLE.replace("PR 64 merged", "PR 64 \\| merged"), td / "b").returncode, 0)
            page = (td / "b" / "index.html").read_text(encoding="utf-8")
            self.assertIn("PR 64 | merged, tests 41/41", page)

    def test_bare_url_is_href(self):
        u = "https://github.com/ITSalt/x/pulls"
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            self.assertEqual(run_build(SAMPLE.replace("gh pr list --state merged", u + "."), out).returncode, 0)
            self.assertIn(f'href="{u}"', (out / "index.html").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as td:  # URL inside the Quote cell too
            out = Path(td) / "out"
            self.assertEqual(run_build(SAMPLE.replace("tests 41/41", "see " + u), out).returncode, 0)
            self.assertIn(f'<blockquote>&quot;PR 64 merged, see <a href="{u}">', (out / "index.html").read_text(encoding="utf-8"))

    def test_link_scheme_and_email_in_url(self):
        mirror = "[mirror](https://github.com/ITSalt/photo-check-bot-mirror)"
        for bad in ("[mirror](javascript:alert(1))", "[x](mailto:bob@example.com)",
                    mirror.replace("mirror)", "mirror?u=bob@example.com)")):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as td:
                out = Path(td) / "out"
                r = run_build(SAMPLE.replace(mirror, bad), out)
                self.assertNotEqual(r.returncode, 0, bad)
                self.assertFalse((out / "index.html").exists())


    def test_h3b1_token_shapes_rejected(self):
        tg = "1234567890:" + "A" * 17 + "-" + "B" * 17  # built here, never pasted
        for frag in (tg, "bot" + tg + "/getMe", "203.0.113.7", "host 203.0.113.7.",
                     "sk-" + "Ab1" * 8, "sk-proj-" + "Ab1" * 8, "sk-" + "ant-api03-" + "Ab1" * 8):
            with self.subTest(frag=frag), tempfile.TemporaryDirectory() as td:
                out = Path(td) / "out"
                r = run_build(SAMPLE.replace("tests 41/41", frag), out)
                self.assertNotEqual(r.returncode, 0, frag)
                self.assertIn("line 12", r.stderr)
                self.assertFalse((out / "index.html").exists())
        with tempfile.TemporaryDirectory() as td:  # an IP inside a URL counts too
            out = Path(td) / "out"
            md = SAMPLE.replace("https://github.com/ITSalt/photo-check-bot-mirror", "http://203.0.113.7/mirror")
            self.assertNotEqual(run_build(md, out).returncode, 0)
            self.assertFalse((out / "index.html").exists())

    def test_h3b1_near_matches_pass(self):
        for frag in ("sk-learn", "scikit-learn", "task-runner", "mask-rcnn", "sk-learn-benchmarks",
                     "16.10.2026", "v1.2.3", "v1.2.3.4", "1.2.3." + "456", "12:30", "PR 64: 41/41",
                     "ITSalt/looktwin-receipts"):
            with self.subTest(frag=frag), tempfile.TemporaryDirectory() as td:
                out = Path(td) / "out"
                r = run_build(SAMPLE.replace("tests 41/41", frag), out)
                self.assertEqual(r.returncode, 0, frag + " " + r.stderr)


    def test_h3b1_dash_in_key_body(self):  # test 18: the hole glitchfox's sk- rule closed
        key = "sk-" + "proj-" + "Ab1" * 4 + "-" + "Cd2_" * 6  # built here, never pasted
        mirror = "https://github.com/ITSalt/photo-check-bot-mirror"
        for where, md in (("plain", SAMPLE.replace("tests 41/41", key)),
                          ("link", SAMPLE.replace(mirror, mirror + "?k=" + key))):
            with self.subTest(where=where), tempfile.TemporaryDirectory() as td:
                out = Path(td) / "out"
                r = run_build(md, out)
                self.assertNotEqual(r.returncode, 0, where)
                self.assertIn("line 12", r.stderr)
                self.assertFalse((out / "index.html").exists())

    def test_four_part_number_after_space_is_host(self):  # on purpose: likelier a host than a version
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            r = run_build(SAMPLE.replace("tests 41/41", "release " + ".".join("1234")), out)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("line 12", r.stderr)
            self.assertFalse((out / "index.html").exists())
        with tempfile.TemporaryDirectory() as td:  # the v-prefixed form stays a version
            self.assertEqual(run_build(SAMPLE.replace("tests 41/41", "v1.2.3.4"), Path(td) / "out").returncode, 0)

    # H3b-2, secrets inside URLs: every value is built here, never pasted
    A, H, H2, B = "A" * 32, "a" * 40, "b" * 40, "https://example.com"
    G = "https://github.com/ITSalt/"

    def test_h3b2_secret_in_url_rejected(self):
        A, H, B = self.A, self.H, self.B
        for url in (B + "/" + A, B + "/" + A + "/x", B + "/x#/" + A, B + "/x?t=" + A, B + "/x#" + A,
                    B + "/x-" + A, B + "/x%2F" + A, B + "/x?next=/commit/" + H,
                    B + "/x#/blob/" + H + "/README.md", B + "/x%2Fcommit%2F" + H,
                    B + "/x?k" + "ey=" + "A" * 40, B + "/x?to" + "ken=" + "deadbeef" * 8,
                    B + "/o/r/blob/" + H + "/x?ref=" + H,          # exempt by position, not by value
                    "https://raw.githubusercontent.com/o/r/" + H + "/build.py",
                    B + "/o/r/commit/" + "A" * 40,                  # link SHAs are lowercase
                    "https://github.com/o/r/blob/main/tests/test_secret_scanner_handles_percent_encoding.py",
                    "https://gist.github.com/u/" + "0123456789abcdef" * 2,  # known false positives
                    B + "/o/r/compare/main..." + H, B + "/o/r/blob/%61" + "a" * 39):
            with self.subTest(url=url), tempfile.TemporaryDirectory() as td:
                out = Path(td) / "out"
                r = run_build(SAMPLE.replace("tests 41/41", "see " + url), out)
                self.assertNotEqual(r.returncode, 0, url)
                self.assertIn("line 12", r.stderr)
                self.assertFalse((out / "index.html").exists())

    def test_h3b2_links_still_pass(self):  # pass before and after H3b-2
        H, H2, B, G = self.H, self.H2, self.B, self.G
        sha = "17f8998bb4aaae9e" + "0c67ce6518226ce713d1b712"  # real commit, split on purpose
        for url in (B + "/o/r/blob/" + H + "/README.md", B + "/o/r/commit/" + "c" * 64,
                    G + "looktwin-receipts/blob/" + sha + "/build.py#L11-L34",
                    G + "photo-check-gold/blob/e40e566/README.md", G + "looktwin-receipts",
                    B + "/o/r/commit/" + H + ".patch", B + "/o/r/commit/" + H + ".diff",
                    B + "/o/r/compare/" + H + "..." + H2, B + "/o/r/compare/" + H + ".." + H2,
                    B + "/o/r/blame/" + H + "/build.py", B + "/o/r/pull/7/commits/" + H):
            with self.subTest(url=url), tempfile.TemporaryDirectory() as td:
                r = run_build(SAMPLE.replace("tests 41/41", "see " + url), Path(td) / "out")
                self.assertEqual(r.returncode, 0, url + " " + r.stderr)


if __name__ == "__main__":
    unittest.main()
