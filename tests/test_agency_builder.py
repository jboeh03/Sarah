"""Builder: real HTML from real data, no fabrication, clearly a demo."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sarah.agency.models import Prospect, Niche, OutreachStage
from sarah.agency.auditor import Auditor
from sarah.agency.builder import SiteBuilder


class TestBuilder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.builder = SiteBuilder(out_dir=self.tmp, owner_name="Pat Owner")

    def _prospect(self, **kw):
        base = dict(id="bgr--town", name="Backyard Grill Revival",
                    niche=Niche.GRILL_CLEANING, locality="Town", region="OH",
                    phone="(937) 555-0112")
        base.update(kw)
        p = Prospect(**base)
        Auditor(check_websites=False).audit(p)
        return p

    @staticmethod
    def _read(path: str) -> str:
        with open(path) as fh:
            return fh.read()

    def test_build_writes_html_file(self):
        p = self._prospect()
        art = self.builder.build(p)
        self.assertTrue(os.path.exists(art.path))
        html = self._read(art.path)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("name=\"viewport\"", html)  # mobile responsive

    def test_uses_real_business_data(self):
        p = self._prospect(rating=4.8, review_count=41)
        html = self._read(self.builder.build(p).path)
        self.assertIn("Backyard Grill Revival", html)
        self.assertIn("9375550112", html)         # click-to-call uses real phone
        self.assertIn("41", html)                  # real review count shown

    def test_no_fabricated_reputation_when_absent(self):
        p = self._prospect(rating=None, review_count=0)
        html = self._read(self.builder.build(p).path)
        self.assertNotIn("★ across", html)         # no invented review line
        self.assertNotIn("Rated", html)

    def test_marked_as_demo_and_noindex(self):
        html = self._read(self.builder.build(self._prospect()).path)
        self.assertIn("noindex", html)
        self.assertIn("DEMO PREVIEW", html)

    def test_build_advances_stage(self):
        p = self._prospect()
        self.builder.build(p)
        self.assertEqual(p.outreach_stage, OutreachStage.BUILT.value)

    def test_deploy_manifest_is_free_tier(self):
        arts = [self.builder.build(self._prospect())]
        man = self.builder.deploy_manifest(arts)
        self.assertEqual(man["tier"], "free")
        self.assertEqual(len(man["sites"]), 1)


if __name__ == "__main__":
    unittest.main()
