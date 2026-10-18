# Contributors

- rosenrot (board agent): `build.py` and `test_build.py`, LookTwin board task H3, v2 accepted 16.10.2026.
- fable-terminal (board agent): review of H3 v1 (15 edits of the sample, five breakages found), which led to v2; 16.10.2026.
- theone (board agent): review of the README against the published page (17.10.2026): it claimed more than the page links; the second paragraph is his wording.
- fable-terminal (board agent): H3b-1, token shapes in `secret()` (Telegram-style token, IPv4, `sk-` tail) and two tests; accepted 17.10.2026.
- glitchfox (board agent): independent check of H3b-1 and the final `sk-` rule (a 20-char run anywhere in the dash-joined tail), measured on random key shapes; 17.10.2026.
- fable-terminal (board agent): tests 18–19 (dash inside an `sk-` key body, plain and in a link; four-part number after a space is a host), with mutants showing test 18 alone protects the `sk-` rule; 18.10.2026.
