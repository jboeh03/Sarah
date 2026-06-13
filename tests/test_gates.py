"""The Gatekeeper decides what agents may do autonomously. These pin the boundary."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sarah.models import Opportunity, Category, Legitimacy, AutomationRisk
from sarah.guardrails import SpendingGuardrail
from sarah.gates import Gatekeeper, AUTO, GATE_SPEND, REFUSE_BAN_RISK, HUMAN_REQUIRED


def opp(**kw) -> Opportunity:
    base = dict(
        id="x", title="t", category=Category.OPEN_SOURCE_BOUNTY, source="Algora",
        url="u", legitimacy=Legitimacy.REPUTABLE, automation_risk=AutomationRisk.SAFE,
    )
    base.update(kw)
    return Opportunity(**base)


class TestGatekeeper(unittest.TestCase):
    def setUp(self):
        self.gk = Gatekeeper(SpendingGuardrail(ledger_path=None))

    def test_ban_risk_is_refused(self):
        d = self.gk.evaluate(opp(category=Category.GPT_ADS_SURVEYS, automation_risk=AutomationRisk.HIGH))
        self.assertEqual(d.verdict, REFUSE_BAN_RISK)

    def test_scam_is_refused(self):
        d = self.gk.evaluate(opp(legitimacy=Legitimacy.SCAM))
        self.assertEqual(d.verdict, REFUSE_BAN_RISK)

    def test_payment_required_is_spend_gated(self):
        d = self.gk.evaluate(opp(requires_payment_to_start=True))
        self.assertEqual(d.verdict, GATE_SPEND)

    def test_oss_bounty_is_auto(self):
        d = self.gk.evaluate(opp(category=Category.OPEN_SOURCE_BOUNTY))
        self.assertEqual(d.verdict, AUTO)

    def test_content_is_auto(self):
        d = self.gk.evaluate(opp(category=Category.CONTENT_AFFILIATE))
        self.assertEqual(d.verdict, AUTO)

    def test_freelance_is_auto(self):
        d = self.gk.evaluate(opp(category=Category.FREELANCE))
        self.assertEqual(d.verdict, AUTO)

    def test_bug_bounty_is_human_required(self):
        d = self.gk.evaluate(opp(category=Category.BUG_BOUNTY, automation_risk=AutomationRisk.LOW))
        self.assertEqual(d.verdict, HUMAN_REQUIRED)
        self.assertIn("authorized", d.reason)

    def test_paid_research_is_human_required(self):
        d = self.gk.evaluate(opp(category=Category.PAID_RESEARCH))
        self.assertEqual(d.verdict, HUMAN_REQUIRED)

    def test_spend_gate_logs_to_ledger(self):
        import tempfile
        ledger = os.path.join(tempfile.mkdtemp(), "a.jsonl")
        gk = Gatekeeper(SpendingGuardrail(ledger_path=ledger))
        gk.evaluate(opp(requires_payment_to_start=True))
        self.assertTrue(os.path.exists(ledger))


if __name__ == "__main__":
    unittest.main()
