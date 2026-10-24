#!/usr/bin/env python3
import hashlib
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

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

    # H3b-3, base64 values with "/" or "+": built from pieces so scanners do not flag the file
    K = "wJalrXUtnFEMI" + "/K7MDENG/" + "bPxRfiCYEXAMPLEKEY"
    Bv = "TgdAhWK+24tgzgXB3s" + "/jrRa3IjCWfeAfZAt+Rym0n84="

    def test_h3b3_base64_slash_plus_rejected(self):
        K, Bv, B = self.K, self.Bv, self.B
        P = K.replace("/", "+")
        for val in ("key " + K, B + "/x?secret=" + K, B + "/x?secret=" + quote(K, safe=""), "key " + P,
                    B + "/x?s=" + quote(P, safe=""), "token " + Bv, B + "/cb?sig=" + Bv,
                    "run " + K, B + "/x#" + K, B + "/x/" + P):  # line 12 is a ledger row: all sit in a cell
            with self.subTest(val=val), tempfile.TemporaryDirectory() as td:
                out = Path(td) / "out"
                r = run_build(SAMPLE.replace("tests 41/41", "see " + val), out)
                self.assertNotEqual(r.returncode, 0, val)
                self.assertIn("line 12", r.stderr)
                self.assertFalse((out / "index.html").exists())

    def test_h3b4_aiza_dash_rejected(self):
        E = "AIza" + "-Sy9kQ2xLm7Vt3Rw8-z4Hc6Nj1Ue5Ya0Fg-"
        W = "AIza" + "Sy7kQ--xLm2Vt9Rw4Pz8Hc3Nj6Ue1Ya5Fgh"
        plain = "AIza" + "Sy9kQ2xLm7Vt3Rw8z4Hc6Nj1Ue5Ya0Fg"
        for val in ("key " + E, "key " + W, "key " + plain):
            with self.subTest(val=val), tempfile.TemporaryDirectory() as td:
                out = Path(td) / "out"
                r = run_build(SAMPLE.replace("tests 41/41", val), out)
                self.assertNotEqual(r.returncode, 0, val)
                self.assertIn("line 12", r.stderr)
                self.assertFalse((out / "index.html").exists())

    def test_h3b4_aiza_longer_run_still_passes(self):
        pas53 = "AIzaAIza-AIzaAIza-" + "AIzaAIza-AIzaAIza-" + "AIzaAIza-AIzaAIza"
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            r = run_build(SAMPLE.replace("tests 41/41", "key " + pas53), out)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_h3b3_paths_and_versions_still_pass(self):
        H, B = self.H, self.B
        for val in (B + "/o/r/blob/" + H + "/README.md", "growth/h3-accepted/build.py",
                    "management/heads/community-tools/h3b2-accept/run.sh", "2026/10/20", "v3.2/v3.3",
                    "a+b=c", "commit " + H, "see board-tools/drafts/growth-share-v33-unmeasured.md",
                    B + "/o/r/compare/" + H[:12] + "..." + H[12:24], "token " + "deadbeef" * 8):
            with self.subTest(val=val), tempfile.TemporaryDirectory() as td:
                r = run_build(SAMPLE.replace("tests 41/41", "see " + val), Path(td) / "out")
                self.assertEqual(r.returncode, 0, val + " " + r.stderr)



class TestH3b5Underscore(unittest.TestCase):
    """H3b-5: uppercase sk- branch accepts underscore; optional Title-Case guard."""

    def _load_build(self):
        spec = importlib.util.spec_from_file_location("build_h3b5", BUILD)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _fixtures(self):
        P = "sk-" + "proj-"
        K = P + "Ab3dE-fG7hJ2kL9-mN4pQ8rS1-tU6vW0xY5z-Bc2D"
        L = "sk-" + "T3BlbkFJ-x9Qa2Lm7Vt4Rw8Pz-1Hc6Nj5Ue0Ya3Fg-Kd7Sb2Wq"
        R = P + "Ab3dE--fG7hJ2kL9mN4p-Q8rS1tU6vW0xY5z-Bc"
        S = P + "-x9Qa2Lm7Vt4Rw8Pz1Hc-6Nj5Ue0Ya3Fg7Kd2-"
        Q = P + "d_dnWk6ie15HsJ-Bc-gwF0N30VWXmNrOUEZZr-kQ"
        U = "https://example.com"
        rej = [f"key {K}", f"{U}/v1?key={K}", f"{U}/v1?key=" + quote(K, safe=""),
               f"| run | {L} |", f"{U}/v1#{L}", f"key {R}", f"{U}/v1/{S}/y", f"key {Q}"]
        pas = ["sk-learn", "sk-" + "proj-short",
               "sk-learn-is-short-for-scikit-learn-in-these-notes",
               "sk-2026-10-22-build-17-release-notes",
               "task-runner-v2-config", "growth/h3-accepted/build.py",
               "token " + "deadbeef" * 8,
               "see board-tools/drafts/growth-v35-accept.md"]
        return rej, pas

    def test_h3b5_rej_all_eight(self):
        b = self._load_build()
        for u in self._fixtures()[0]:
            err = b.secret(f"x {u} y", 7)
            self.assertEqual(err, "secret-like token on line 7", u)

    def test_h3b5_pas_all_eight(self):
        b = self._load_build()
        for u in self._fixtures()[1]:
            self.assertIsNone(b.secret(f"x {u} y", 7), u)

    def test_h3b5_titlecase_slug_guard(self):
        b = self._load_build()
        fp = "sk-My-Branch-Name-Is-Fine-Here-Today"
        self.assertIsNone(b.secret(f"x {fp} y", 7), fp)

    def test_h3b5_underscore_key_rejected_via_build(self):
        Q = "sk-" + "proj-" + "d_dnWk6ie15HsJ-Bc-gwF0N30VWXmNrOUEZZr-kQ"
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            r = run_build(SAMPLE.replace("tests 41/41", "key " + Q), out)
            self.assertNotEqual(r.returncode, 0, r.stderr)
            self.assertIn("line 12", r.stderr)
            self.assertFalse((out / "index.html").exists())

    def test_h3b5_slug_then_key_rejected(self):
        """Slug before a real key must not mask the second PREF match (looktwin #99494)."""
        b = self._load_build()
        slug = "sk-My-Branch-Name-Is-Fine-Here-Today"
        K = "sk-" + "abc123" * 5
        self.assertEqual(
            b.secret(f"x {slug} {K} y", 7),
            "secret-like token on line 7",
            "slug-then-key",
        )
        self.assertEqual(
            b.secret(f"x {slug} sk-" + "abc123" * 5 + " y", 7),
            "secret-like token on line 7",
            "slug-then-fake-run",
        )


class H3b6EncodedPrefix(unittest.TestCase):
    """H3b-6 (theone): a prefix percent-encoded inside a link is still a key."""
    P = "sk-" + "proj-"
    T = P + "Ab1-" * 9 + "Cd2E"
    K = P + "Ab3dE-fG7hJ2kL9-mN4pQ8rS1-tU6vW0xY5z-Bc2D"
    G = "AIza" + "Sy3Kd-9Qm_7Vt2Lw8Pz-1Hc6Nj5Ue0Ya3Fg"
    W = "AKIA" + "Q3ZT7XK2M9WB4RJD"
    X = "xoxb" + "-" + "482915736021-" + "Hc6Nj5Ue0Ya3Fg7Kd2Sb8Wq1"
    H = "ghp" + "_" + "Ab3dEfG7hJ2kL9mN4pQ8rS1tU6vW0xY5zBc2"
    U = "https://example.com/v1?key="
    R = "https://github.com/ITSalt/looktwin-receipts"

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("build_h3b6", BUILD)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def rej(self):
        U, T, K, G, W, X, H = self.U, self.T, self.K, self.G, self.W, self.X, self.H
        return [U + T.replace("sk-", "sk%2D", 1), U + K.replace("sk-", "sk%2D", 1),
                U + G.replace("AIza", "AIz%61", 1), U + W.replace("AKIA", "AKI%41", 1),
                U + X.replace("xoxb-", "xoxb%2D", 1), U + H.replace("ghp_", "ghp%5F", 1),
                "https://example.com/v1/" + W.replace("AKIA", "%41KIA", 1) + "/y",
                "https://example.com/v1#t=" + X.replace("xoxb-", "%78oxb-", 1),
                "https://example.com/b?t=" + "123456789" + "%3A" + "Ab3dE-fG7hJ2kL9mN4pQ8rS1tU6vW0x"]

    def pas(self):
        R = self.R
        return [R + "/commit/" + "aaa6d438daa00a9d75228b0b4ddce231d2ac3789", R + "/blob/52527bb/README.md",
                R + "/compare/aaa6d43...52527bb", "https://example.com/search?q=sk%2Dlearn",
                "https://example.com/docs?page=task%2Drunner%2Dv2%2Dconfig",
                "https://example.com/?b=sk%2DMy-Branch-Name-Is-Fine-Here-Today",
                "https://example.com/wiki/AKIA%20prefix%20explained", R + "/blob/52527bb/docs/a%20b.md"]

    def test_encoded_prefix_rejected_on_line_7(self):
        for u in self.rej():
            with self.subTest(u=u[:40]):
                e = self.mod.secret(f"x {u} y", 7)
                self.assertIsNotNone(e)
                self.assertIn("line 7", e)

    def test_benign_encoded_links_pass(self):
        for u in self.pas():
            with self.subTest(u=u[:40]):
                self.assertIsNone(self.mod.secret(f"x {u} y", 7))

    def test_markdown_link_target_rejected(self):
        u = self.U + self.W.replace("AKIA", "AKI%41", 1)
        self.assertIsNotNone(self.mod.secret(f"see [docs]({u})", 3))

    def test_page_with_encoded_key_builds_nothing(self):
        u = self.rej()[0]
        md = SAMPLE.replace("[mirror](https://github.com/ITSalt/photo-check-bot-mirror)", f"[mirror]({u})")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "week.md"; p.write_text(md, encoding="utf-8")
            r = subprocess.run(["python3", str(BUILD), str(p), str(Path(d) / "out")], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("line", r.stderr)
            self.assertFalse((Path(d) / "out" / "index.html").exists())

if __name__ == "__main__":
    unittest.main()
