"""Small CPU checks for distribution_probe's chunked full-vocabulary KL."""

import unittest

import torch
import torch.nn.functional as F

from distribution_probe import quartile_means, streamed_kl_rows


class ChunkedKLTests(unittest.TestCase):
    def test_chunked_rows_match_dense_kl_and_quartile_means(self):
        generator = torch.Generator(device="cpu").manual_seed(241)
        q0 = torch.randn((11, 257), generator=generator, dtype=torch.float32)
        qhint = q0 + 0.4 * torch.randn((11, 257), generator=generator, dtype=torch.float32)
        p = torch.randn((11, 257), generator=generator, dtype=torch.float32)

        actual = streamed_kl_rows(q0, qhint, p, torch.device("cpu"), chunk_tokens=4)
        lp0, lph, lpp = (F.log_softmax(logits, dim=-1) for logits in (q0, qhint, p))
        q0_prob, qhint_prob = lp0.exp(), lph.exp()
        expected = {
            "kl_qhint_q0": (qhint_prob * (lph - lp0)).sum(dim=-1),
            "kl_qhint_p": (qhint_prob * (lph - lpp)).sum(dim=-1),
            "kl_q0_p": (q0_prob * (lp0 - lpp)).sum(dim=-1),
        }

        for name in expected:
            torch.testing.assert_close(actual[name], expected[name], rtol=2e-6, atol=2e-6)
            actual_quartiles = quartile_means(actual[name])
            expected_quartiles = quartile_means(expected[name])
            for got, want in zip(actual_quartiles, expected_quartiles, strict=True):
                if want is None:
                    self.assertIsNone(got)
                else:
                    self.assertAlmostEqual(got, want, delta=2e-6)

    def test_identical_distributions_have_zero_kl_and_quartiles(self):
        generator = torch.Generator(device="cpu").manual_seed(997)
        logits = torch.randn((9, 73), generator=generator, dtype=torch.float32)
        actual = streamed_kl_rows(logits, logits.clone(), logits.clone(),
                                  torch.device("cpu"), chunk_tokens=3)

        for rows in actual.values():
            torch.testing.assert_close(rows, torch.zeros_like(rows), rtol=0, atol=1e-7)
            self.assertEqual(quartile_means(rows), [0.0, 0.0, 0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
