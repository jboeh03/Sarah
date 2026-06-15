"""Prospect model: id stability, serialization, and the need×viability score."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sarah.agency.models import Prospect, Niche, make_prospect_id
from sarah.agency.auditor import Auditor


def audited(**kw) -> Prospect:
    base = dict(id="x", name="X", niche=Niche.LANDSCAPING, locality="Town")
    base.update(kw)
    p = Prospect(**base)
    if "id" not in kw:
        p.id = make_prospect_id(p.name, p.locality)
    Auditor(check_websites=False).audit(p)
    return p


class TestProspectModel(unittest.TestCase):
    def test_stable_id(self):
        self.assertEqual(make_prospect_id("Joe's BBQ!", "Maplewood"), "joe-s-bbq--maplewood")
        self.assertEqual(
            make_prospect_id("Joe's BBQ", "Maplewood"),
            make_prospect_id("Joe's BBQ", "Maplewood"),
        )

    def test_social_is_not_a_real_website(self):
        p = Prospect(id="a", name="A", website="https://facebook.com/a")
        self.assertFalse(p.has_real_website)
        p2 = Prospect(id="b", name="B", website="https://realsite.example")
        self.assertTrue(p2.has_real_website)

    def test_proven_no_site_beats_unproven_no_site(self):
        proven = audited(name="Proven", website="", rating=4.8, review_count=41,
                         on_google_maps=True, phone="555-0100")
        unproven = audited(name="Unproven", website="", rating=None, review_count=0,
                           on_google_maps=False, phone="555-0100")
        self.assertGreater(proven.opportunity_score(), unproven.opportunity_score())
        self.assertGreater(unproven.opportunity_score(), 0)

    def test_business_with_site_ranks_below_one_without(self):
        no_site = audited(name="NoSite", website="", rating=4.7, review_count=30,
                          on_google_maps=True, phone="555-0100")
        has_site = audited(name="HasSite", website="https://hassite.example",
                           rating=4.7, review_count=30, on_google_maps=True, phone="555-0100")
        self.assertGreater(no_site.opportunity_score(), has_site.opportunity_score())

    def test_unaudited_scores_zero(self):
        p = Prospect(id="x", name="X")
        self.assertEqual(p.opportunity_score(), 0.0)

    def test_roundtrip_serialization(self):
        p = audited(name="Round Trip", website="", rating=4.5, review_count=12,
                    on_google_maps=True, phone="555-0100", email="a@example.invalid")
        p2 = Prospect.from_dict(p.to_dict())
        self.assertEqual(p.id, p2.id)
        self.assertEqual(p.niche, p2.niche)
        self.assertIsNotNone(p2.audit)
        self.assertEqual(p.audit.need_score, p2.audit.need_score)
        self.assertAlmostEqual(p.opportunity_score(), p2.opportunity_score())


if __name__ == "__main__":
    unittest.main()
