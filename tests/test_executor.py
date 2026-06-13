"""The Executor turns cleared opportunities into real deliverables."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sarah.models import Opportunity, Category, Legitimacy, AutomationRisk
from sarah.guardrails import SpendingGuardrail
from sarah.gates import Gatekeeper
from sarah.executor import Executor


def opp(oid, **kw) -> Opportunity:
    base = dict(
        id=oid, title=f"title-{oid}", category=Category.OPEN_SOURCE_BOUNTY,
        source="Algora", url="u", legitimacy=Legitimacy.REPUTABLE,
        automation_risk=AutomationRisk.SAFE,
    )
    base.update(kw)
    return Opportunity(**base)


class TestExecutor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        gk = Gatekeeper(SpendingGuardrail(ledger_path=os.path.join(self.tmp, "a.jsonl")))
        self.exec = Executor(gk, out_dir=os.path.join(self.tmp, "work"), max_auto_per_run=5)

    def test_auto_produces_a_real_file(self):
        result = self.exec.run([opp("o1", category=Category.OPEN_SOURCE_BOUNTY)])
        self.assertEqual(len(result.produced), 1)
        self.assertTrue(os.path.exists(result.produced[0].path))
        self.assertTrue(os.path.getsize(result.produced[0].path) > 0)

    def test_ban_risk_is_refused_not_produced(self):
        result = self.exec.run([opp("o2", category=Category.GPT_ADS_SURVEYS,
                                     automation_risk=AutomationRisk.HIGH)])
        self.assertEqual(len(result.produced), 0)
        self.assertEqual(len(result.refused), 1)

    def test_spend_required_is_gated(self):
        result = self.exec.run([opp("o3", category=Category.CONTENT_AFFILIATE,
                                     requires_payment_to_start=True)])
        self.assertEqual(len(result.gated_spend), 1)
        self.assertEqual(len(result.produced), 0)

    def test_human_required_is_routed(self):
        result = self.exec.run([opp("o4", category=Category.BUG_BOUNTY,
                                     automation_risk=AutomationRisk.LOW)])
        self.assertEqual(len(result.human_required), 1)
        self.assertEqual(len(result.produced), 0)

    def test_work_budget_is_respected(self):
        opps = [opp(f"b{i}", category=Category.CONTENT_AFFILIATE) for i in range(8)]
        result = self.exec.run(opps)
        self.assertEqual(len(result.produced), 5)            # capped
        self.assertEqual(len(result.human_required), 3)      # overflow queued

    def test_mixed_batch_sorts_correctly(self):
        opps = [
            opp("auto", category=Category.FREELANCE),
            opp("ban", category=Category.GPT_ADS_SURVEYS, automation_risk=AutomationRisk.HIGH),
            opp("spend", category=Category.OPEN_SOURCE_BOUNTY, requires_payment_to_start=True),
            opp("human", category=Category.EXPERT_NETWORK),
        ]
        result = self.exec.run(opps)
        self.assertEqual(len(result.produced), 1)
        self.assertEqual(len(result.refused), 1)
        self.assertEqual(len(result.gated_spend), 1)
        self.assertEqual(len(result.human_required), 1)


if __name__ == "__main__":
    unittest.main()
