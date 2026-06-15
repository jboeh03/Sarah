"""Auditor: presence-gap scoring and graceful offline behavior."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sarah.agency.models import Prospect, Niche, OutreachStage
from sarah.agency.auditor import Auditor


def P(**kw) -> Prospect:
    base = dict(id="x", name="X", niche=Niche.GRILL_CLEANING, locality="Town")
    base.update(kw)
    return Prospect(**base)


class TestAuditor(unittest.TestCase):
    def setUp(self):
        self.aud = Auditor(check_websites=False)

    def test_no_website_scores_highest_need(self):
        no_web = self.aud.audit(P(website="", on_google_maps=True))
        social = self.aud.audit(P(website="https://facebook.com/x", on_google_maps=True))
        has_web = self.aud.audit(P(website="https://x.example", on_google_maps=True))
        self.assertGreater(no_web.need_score, social.need_score)
        self.assertGreater(social.need_score, has_web.need_score)

    def test_offline_does_not_guess_site_quality(self):
        r = self.aud.audit(P(website="https://x.example"))
        self.assertIsNone(r.website_reachable)  # not checked offline
        self.assertIsNone(r.website_https)

    def test_not_on_maps_adds_need(self):
        on = self.aud.audit(P(website="", on_google_maps=True))
        off = self.aud.audit(P(website="", on_google_maps=False))
        self.assertGreater(off.need_score, on.need_score)

    def test_contactable_flag(self):
        self.assertTrue(self.aud.audit(P(phone="555-0100")).contactable)
        self.assertTrue(self.aud.audit(P(email="a@example.invalid")).contactable)
        self.assertFalse(self.aud.audit(P()).contactable)

    def test_signals_are_recorded(self):
        r = self.aud.audit(P(website=""))
        self.assertTrue(r.signals)
        self.assertTrue(any("No website" in s for s in r.signals))

    def test_audit_advances_stage(self):
        p = P(website="")
        self.aud.audit(p)
        self.assertEqual(p.outreach_stage, OutreachStage.AUDITED.value)

    def test_need_score_capped(self):
        r = self.aud.audit(P(website="", on_google_maps=False, review_count=0))
        self.assertLessEqual(r.need_score, 100.0)

    def test_broken_site_check_never_raises(self):
        # check a definitely-unreachable URL; must return False, not raise.
        aud = Auditor(check_websites=True, timeout_seconds=1)
        reachable, https, mobile = aud._check_site("http://nonexistent.invalid")
        self.assertFalse(reachable)


if __name__ == "__main__":
    unittest.main()
