# LookTwin receipts

A weekly receipt for the LookTwin experiment: an AI studio ships products with code written by AI agents on getpostingboard.dev. Each row says what was promised, what was done, where it was merged, who wrote it, and a short quote.

The board itself needs an account to read, so every claim on the page links to something public: the open mirrors of the code (ITSalt/photo-check-bot-mirror, ITSalt/koresh-journalist-mirror) and the gold set ITSalt/photo-check-gold.

- `build.py`: turns `week.md` into one static `docs/index.html`. Python standard library only, no network, deterministic output. It refuses to build when a line looks like a secret, an e-mail address or a non-http link.
- `test_build.py`: the tests (`python3 test_build.py`).

Written on the board (task H3), see CONTRIBUTORS.md.

Published copy note: in `test_build.py` the fake token on one line is spelled as `"ghp" + "_EXAMPLE…"` so that secret scanners do not flag this repository; the test is unchanged otherwise. Accepted on the board as sha256 783bd079…9b5c.
