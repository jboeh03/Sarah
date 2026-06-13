"""Scoring must reward honest $/hr and legitimacy, and punish ban-risk and scams."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sarah.models import Opportunity, Category, Legitimacy, AutomationRisk, SkillLevel


def make(**kw) -> Opportunity:
    base = dict(id="x", title="t", category=Category.FREELANCE, source="s", url="u")
    base.update(kw)
    return Opportunity(**base)


class TestScoring(unittest.TestCase):
    def test_hourly_from_per_task(self):
        o = make(pay_model="per_task", est_pay_usd_low=10, est_pay_usd_high=10, est_time_minutes=30)
        self.assertAlmostEqual(o.est_hourly_usd, 20.0)

    def test_hourly_from_per_hour(self):
        o = make(pay_model="per_hour", est_pay_usd_low=50, est_pay_usd_high=150)
        self.assertAlmostEqual(o.est_hourly_usd, 100.0)

    def test_scam_scores_zero(self):
        o = make(legitimacy=Legitimacy.SCAM, est_pay_usd_low=100, est_pay_usd_high=100)
        self.assertEqual(o.priority_score(), 0.0)

    def test_high_automation_risk_is_penalized(self):
        good = make(legitimacy=Legitimacy.REPUTABLE, automation_risk=AutomationRisk.SAFE,
                    pay_model="per_hour", est_pay_usd_low=40, est_pay_usd_high=40)
        bannable = make(legitimacy=Legitimacy.REPUTABLE, automation_risk=AutomationRisk.HIGH,
                        pay_model="per_hour", est_pay_usd_low=40, est_pay_usd_high=40)
        self.assertGreater(good.priority_score(), bannable.priority_score())

    def test_reputable_beats_suspicious_at_equal_pay(self):
        rep = make(legitimacy=Legitimacy.REPUTABLE, automation_risk=AutomationRisk.SAFE,
                   pay_model="per_hour", est_pay_usd_low=30, est_pay_usd_high=30)
        sus = make(legitimacy=Legitimacy.SUSPICIOUS, automation_risk=AutomationRisk.SAFE,
                   pay_model="per_hour", est_pay_usd_low=30, est_pay_usd_high=30)
        self.assertGreater(rep.priority_score(), sus.priority_score())

    def test_skill_match_boosts_score(self):
        base = make(legitimacy=Legitimacy.REPUTABLE, automation_risk=AutomationRisk.SAFE,
                    pay_model="per_hour", est_pay_usd_low=50, est_pay_usd_high=50,
                    tags=["security"])
        no_match = base.priority_score(owner_skills=set())
        match = base.priority_score(owner_skills={"security"})
        self.assertGreater(match, no_match)

    def test_payment_required_is_deprioritized(self):
        free = make(legitimacy=Legitimacy.REPUTABLE, automation_risk=AutomationRisk.SAFE,
                    pay_model="per_hour", est_pay_usd_low=40, est_pay_usd_high=40)
        paid = make(legitimacy=Legitimacy.REPUTABLE, automation_risk=AutomationRisk.SAFE,
                    pay_model="per_hour", est_pay_usd_low=40, est_pay_usd_high=40,
                    requires_payment_to_start=True)
        self.assertGreater(free.priority_score(), paid.priority_score())

    def test_roundtrip_serialization(self):
        o = make(est_pay_usd_low=5, est_pay_usd_high=25, tags=["a", "b"])
        o2 = Opportunity.from_dict(o.to_dict())
        self.assertEqual(o.id, o2.id)
        self.assertEqual(o.category, o2.category)
        self.assertAlmostEqual(o.est_hourly_usd, o2.est_hourly_usd)


if __name__ == "__main__":
    unittest.main()
