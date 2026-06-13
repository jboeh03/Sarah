"""The spending guardrail is the owner's one firm rule. These tests pin it down."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sarah.guardrails import SpendingGuardrail, Action, ApprovalRequired


class TestSpendingGuardrail(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ledger = os.path.join(self.tmp, "approvals.jsonl")
        self.guard = SpendingGuardrail(
            require_approval_for_spending=True,
            max_auto_spend_usd=0.0,
            ledger_path=self.ledger,
        )

    def test_free_action_is_authorized(self):
        action = Action(name="research", costs_money=False)
        self.assertTrue(self.guard.authorize(action))

    def test_paid_action_is_blocked(self):
        action = Action(name="buy_subscription", costs_money=True, amount_usd=9.99)
        with self.assertRaises(ApprovalRequired):
            self.guard.authorize(action)

    def test_unknown_cost_fails_closed(self):
        # Cost unknown -> must be treated as a potential spend and blocked.
        action = Action(name="sign_up", costs_money=False, cost_known=False)
        with self.assertRaises(ApprovalRequired):
            self.guard.authorize(action)
        self.assertFalse(self.guard.is_allowed(action))

    def test_blocked_action_is_logged_to_ledger(self):
        action = Action(name="pay_fee", costs_money=True, amount_usd=5.0)
        with self.assertRaises(ApprovalRequired):
            self.guard.authorize(action)
        self.assertTrue(os.path.exists(self.ledger))
        with open(self.ledger) as fh:
            lines = [l for l in fh if l.strip()]
        self.assertEqual(len(lines), 1)
        self.assertIn("pay_fee", lines[0])

    def test_pending_list_tracks_requests(self):
        for i in range(3):
            try:
                self.guard.authorize(Action(name=f"a{i}", costs_money=True, amount_usd=1))
            except ApprovalRequired:
                pass
        self.assertEqual(len(self.guard.pending), 3)

    def test_explicit_budget_allows_small_spend(self):
        # If the owner ever opts into a budget, spends under it can auto-proceed.
        guard = SpendingGuardrail(require_approval_for_spending=False, max_auto_spend_usd=10.0)
        self.assertTrue(guard.authorize(Action(name="cheap", costs_money=True, amount_usd=2.0, cost_known=True)))
        with self.assertRaises(ApprovalRequired):
            guard.authorize(Action(name="pricey", costs_money=True, amount_usd=50.0, cost_known=True))


if __name__ == "__main__":
    unittest.main()
