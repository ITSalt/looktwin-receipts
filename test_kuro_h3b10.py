"""Independent synthetic H3b-10 regressions; no literal credentials or network."""
import unittest
import build


class H3b10(unittest.TestCase):
    def test_whole_run_rejects(self):
        tails = [
            'Note-' + 'q7Xk2Lm9Pz4Rt8Vw1Ys6Bn' + '-' + 'Hd3Jf5Kg7Mq2Wx',
            'Bt-' + 'q7Xk2Lm9Pz4Rt8Vw1Ys6BnHd3Jf5Kg',
            'Ab-Cd-' + 'q7Xk2Lm9Pz4Rt8Vw1Ys6Bn',
            '-' + 'a1b2-' * 7,
            'Ab-Cd-Ef-' + 'q7Xk2Lm9Pz4Rt',
        ]
        for tail in tails:
            token = 'sk-' + tail
            for text in [token, 'https://example.com/v1?key=' + token,
                         'https://example.com/v1?key=' + token.replace('sk-', 'sk%2D', 1)]:
                with self.subTest(tail=tail[:8], url=text.startswith('https')):
                    self.assertIsNotNone(build.secret('x ' + text + ' y', 7))

    def test_benign_and_pinned_boundaries(self):
        tails = ['My-Branch-Name-Is-Fine-Here-Today', 'Ab-q7Xk2Lm9Pz4R',
                 'Qwerty-Asdfgh-Zxcvbn-Qwerty-Asdfgh', 'learn', 'SK',
                 'ecdsa-sha2-nistp256', 'ssh-ed25519']
        for tail in tails:
            token = 'sk-' + tail
            for text in [token, 'https://example.com/v1?key=' + token]:
                with self.subTest(tail=tail, url=text.startswith('https')):
                    self.assertIsNone(build.secret('x ' + text + ' y', 7))

    def test_base64_32_to_39(self):
        for size in range(32, 40):
            key = 'Ab1/' + 'cD2+' * 9
            key = key[:size]
            with self.subTest(size=size):
                self.assertTrue(build.b64_secret(key))
                self.assertIsNotNone(build.secret('x ' + key + ' y', 7))


    def test_slug_rule_boundaries(self):
        # fable-terminal, weekly review 1c2c6a31 (03.11.2026): each kills one surviving mutant
        chunk = 'x9Q2w8E7r6T5'
        rejected = ['Alpha-' + chunk + '-' + 'a1B2c3D4e5F6',  # two plain segments: kills len(plain) <= 2
                    'Alpha-Bravo-' + chunk + 'z']            # 13 chars: kills len(s) <= 13
        passed = ['Intro-to-Pandas-Dataframes',               # one plain segment: kills len(plain) <= 0
                  'Alpha-Bravo-' + chunk]                     # 12 chars: kills len(s) <= 11
        for tail in rejected:
            with self.subTest(tail=tail[:12]):
                self.assertIsNotNone(build.secret('x sk-' + tail + ' y', 7))
        for tail in passed:
            with self.subTest(tail=tail[:12]):
                self.assertIsNone(build.secret('x sk-' + tail + ' y', 7))


if __name__ == '__main__':
    unittest.main()
