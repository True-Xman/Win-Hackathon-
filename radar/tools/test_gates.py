"""Regression tests for the gate analyzer. Run: python3 radar/tools/test_gates.py
Each case is a real mistake the analyzer made during development (see git history)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from gates import analyze  # noqa: E402


def v(text, gate):
    return analyze(text)["gates"][gate]["verdict"]


class GateTests(unittest.TestCase):
    def test_global_hackathon_name_is_not_country_pass(self):
        # Colosseum side tracks say "official Colosseum Global Hackathon" -> must NOT count as 'open worldwide'
        self.assertNotEqual(v("Register for the official Colosseum Global Hackathon.", "country"), "PASS")

    def test_explicit_worldwide_is_country_pass(self):
        self.assertEqual(v("Open worldwide to anyone aged 16 or older.", "country"), "PASS")

    def test_may_perform_kyc_is_risk_not_fail(self):
        t = "The operator and its partners may perform KYC procedures, as required by internal policies. You consent."
        self.assertEqual(v(t, "kyc"), "RISK")

    def test_mandatory_kyc_is_fail(self):
        self.assertEqual(v("Winners must complete KYC before receiving a prize.", "kyc"), "FAIL")

    def test_absence_is_unknown_never_pass(self):
        self.assertEqual(v("Build an agent. Prizes will be announced.", "kyc"), "UNKNOWN")

    def test_positive_kyc_statement_can_pass(self):
        self.assertEqual(v("This event is KYC-free.", "kyc"), "PASS")

    def test_legal_venue_is_not_onsite(self):
        self.assertNotEqual(v("Disputes: jurisdiction, forum, or venue in those courts.", "onsite"), "RISK")

    def test_mainnet_trades_flag_paid_action(self):
        self.assertEqual(v("Execute at least 5 qualifying trades on Solana Mainnet.", "paid_action"), "FAIL")

    def test_positive_never_overrides_risk(self):
        r = analyze("Open worldwide. Residents of Cuba and Iran are not eligible.")["gates"]["country"]
        self.assertIn(r["verdict"], ("RISK", "FAIL"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
