"""The vetter is what keeps us from chasing scams or getting accounts banned."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sarah.models import Opportunity, Category, Legitimacy, AutomationRisk, SkillLevel
from sarah.vetter import Vetter


def make(**kw) -> Opportunity:
    base = dict(
        id="x", title="t", category=Category.FREELANCE, source="Somewhere",
        url="https://example.com", description="", skill_level=SkillLevel.MEDIUM,
    )
    base.update(kw)
    return Opportunity(**base)


class TestVetter(unittest.TestCase):
    def setUp(self):
        self.v = Vetter()

    def test_upfront_fee_is_scam(self):
        o = self.v.vet(make(description="Just pay a small registration fee to start earning"))
        self.assertEqual(o.legitimacy, Legitimacy.SCAM)

    def test_guaranteed_income_is_scam(self):
        o = self.v.vet(make(title="Guaranteed $500/day, risk-free profit"))
        self.assertEqual(o.legitimacy, Legitimacy.SCAM)

    def test_mlm_is_scam(self):
        o = self.v.vet(make(description="Recruit your downline in this multi-level system"))
        self.assertEqual(o.legitimacy, Legitimacy.SCAM)

    def test_reputable_source_is_reputable(self):
        o = self.v.vet(make(source="HackerOne", category=Category.BUG_BOUNTY))
        self.assertEqual(o.legitimacy, Legitimacy.REPUTABLE)

    def test_unknown_source_is_plausible(self):
        o = self.v.vet(make(source="RandomNewSite"))
        self.assertEqual(o.legitimacy, Legitimacy.PLAUSIBLE)

    def test_ads_surveys_category_is_high_automation_risk(self):
        o = self.v.vet(make(category=Category.GPT_ADS_SURVEYS, source="various"))
        self.assertEqual(o.automation_risk, AutomationRisk.HIGH)
        self.assertTrue(o.requires_human)
        self.assertTrue(any("NOT RECOMMENDED" in n for n in o.vetter_notes))

    def test_watch_ads_text_flags_automation_risk(self):
        o = self.v.vet(make(description="Get paid to watch ads and complete surveys"))
        self.assertEqual(o.automation_risk, AutomationRisk.HIGH)

    def test_bug_bounty_warns_authorized_only(self):
        o = self.v.vet(make(category=Category.BUG_BOUNTY, source="Bugcrowd"))
        self.assertEqual(o.automation_risk, AutomationRisk.LOW)
        self.assertTrue(any("AUTHORIZED" in n for n in o.vetter_notes))

    def test_unrecognized_paid_start_is_suspicious(self):
        o = self.v.vet(make(source="SketchyCo", requires_payment_to_start=True))
        self.assertEqual(o.legitimacy, Legitimacy.SUSPICIOUS)


if __name__ == "__main__":
    unittest.main()
