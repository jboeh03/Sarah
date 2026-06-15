"""ProspectStore: dedupe + cross-run outreach-stage tracking."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sarah.agency.models import Prospect, Niche, OutreachStage
from sarah.agency.store import ProspectStore


def P(pid="a--town", stage=OutreachStage.NEW.value) -> Prospect:
    return Prospect(id=pid, name="A", niche=Niche.DETAILING, locality="Town", outreach_stage=stage)


class TestProspectStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "prospects.json")

    def test_record_all_returns_only_new(self):
        s = ProspectStore(self.path)
        first = s.record_all([P("a--town"), P("b--town")])
        self.assertEqual(len(first), 2)
        again = s.record_all([P("a--town"), P("c--town")])
        self.assertEqual({p.id for p in again}, {"c--town"})  # only the new one

    def test_already_contacted_persists_across_reload(self):
        s = ProspectStore(self.path)
        s.record(P("a--town", stage=OutreachStage.DRAFTED.value))
        s.save()
        s2 = ProspectStore(self.path)
        self.assertTrue(s2.already_contacted(P("a--town")))
        self.assertFalse(s2.already_contacted(P("z--town")))

    def test_new_business_not_contacted(self):
        s = ProspectStore(self.path)
        self.assertFalse(s.already_contacted(P("fresh--town")))

    def test_first_seen_preserved_on_rerecord(self):
        s = ProspectStore(self.path)
        s.record(P("a--town"))
        first_seen = s._seen["a--town"]["first_seen"]
        s.record(P("a--town", stage=OutreachStage.BUILT.value))
        self.assertEqual(s._seen["a--town"]["first_seen"], first_seen)


if __name__ == "__main__":
    unittest.main()
