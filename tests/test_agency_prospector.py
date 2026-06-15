"""Prospector: offline seed loading, niche classification, and paid-source gating."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sarah.agency.prospector import Prospector, classify_niche
from sarah.agency.models import Niche
from sarah.guardrails import SpendingGuardrail


SEED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "agency_seed.json")


class TestProspector(unittest.TestCase):
    def test_classify_niche(self):
        self.assertEqual(classify_niche("Joe's Pressure Washing"), Niche.PRESSURE_WASHING)
        self.assertEqual(classify_niche("GreenScape Lawn Care"), Niche.LANDSCAPING)
        self.assertEqual(classify_niche("Backyard Grill Cleaning"), Niche.GRILL_CLEANING)
        self.assertEqual(classify_niche("Random Bakery"), Niche.OTHER)

    def test_offline_loads_seed(self):
        p = Prospector(seed_path=SEED, live_enabled=False)
        found = p.find()
        self.assertGreater(len(found), 0)
        self.assertTrue(all(x.name for x in found))

    def test_paid_source_is_gated_and_falls_back(self):
        guard = SpendingGuardrail(require_approval_for_spending=True, max_auto_spend_usd=0.0)
        p = Prospector(seed_path=SEED, live_enabled=False,
                       data_source="google_places", guardrail=guard)
        found = p.find()
        # Paid source must be held for approval; pipeline falls back to free data.
        self.assertEqual(p.data_source, "osm")
        self.assertTrue(any("HELD for approval" in line for line in p.log))
        self.assertGreater(len(found), 0)  # still produced results from seed

    def test_respects_max_prospects(self):
        p = Prospector(seed_path=SEED, live_enabled=False, max_prospects=3)
        self.assertLessEqual(len(p.find()), 3)

    def test_niche_filter(self):
        p = Prospector(seed_path=SEED, live_enabled=False, niches=[Niche.GRILL_CLEANING])
        found = p.find()
        self.assertTrue(found)
        self.assertTrue(all(x.niche == Niche.GRILL_CLEANING for x in found))


if __name__ == "__main__":
    unittest.main()
