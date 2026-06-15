"""Outreach: personalized, CAN-SPAM-compliant drafts that are never auto-sent."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sarah.agency.models import Prospect, Niche, OutreachStage
from sarah.agency.auditor import Auditor
from sarah.agency.outreach import OutreachWriter


class TestOutreach(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.writer = OutreachWriter(
            out_dir=self.tmp, owner_name="Pat Owner",
            owner_email="pat@example.com", mailing_address="1 Main St, Town, OH",
        )

    def _prospect(self, **kw):
        base = dict(id="x--town", name="GreenScape", niche=Niche.LANDSCAPING,
                    locality="Town", website="", rating=4.7, review_count=52)
        base.update(kw)
        p = Prospect(**base)
        Auditor(check_websites=False).audit(p)
        return p

    def test_draft_has_optout_and_identity(self):
        d = self.writer.draft(self._prospect(email="g@example.invalid"))
        body = d.payload.body_text.lower()
        self.assertIn("not interested", body)            # opt-out
        self.assertIn("pat owner", body)                  # sender identity
        self.assertIn("1 main st", body)                  # physical address (CAN-SPAM)

    def test_subject_is_truthful_demo_framing(self):
        d = self.writer.draft(self._prospect(email="g@example.invalid"))
        self.assertIn("demo", d.payload.subject.lower())
        self.assertNotIn("live", d.payload.subject.lower())  # never implies it's live

    def test_personalized_with_finding(self):
        d = self.writer.draft(self._prospect(email="g@example.invalid"))
        # social-only business -> the lead finding should mention the missing site
        self.assertIn("GreenScape", d.payload.body_text)
        self.assertTrue(
            "social page" in d.payload.body_text or "website" in d.payload.body_text.lower()
        )

    def test_missing_email_flags_lookup_and_blank_to(self):
        d = self.writer.draft(self._prospect(email=""))
        self.assertTrue(d.needs_contact_lookup)
        self.assertEqual(d.to, "")
        self.assertEqual(d.payload.to, "")

    def test_writes_payload_file_and_advances_stage(self):
        p = self._prospect(email="g@example.invalid")
        d = self.writer.draft(p)
        self.assertTrue(os.path.exists(d.path))
        self.assertEqual(p.outreach_stage, OutreachStage.DRAFTED.value)

    def test_email_prospect_uses_email_channel(self):
        d = self.writer.draft(self._prospect(email="g@example.invalid", phone="555-0100"))
        self.assertEqual(d.channel, "email")
        self.assertEqual(d.call_script_path, "")

    def test_phone_only_prospect_gets_call_script(self):
        d = self.writer.draft(self._prospect(email="", phone="(937) 555-0112"))
        self.assertEqual(d.channel, "phone")
        self.assertFalse(d.needs_contact_lookup)
        self.assertTrue(os.path.exists(d.call_script_path))
        with open(d.call_script_path) as fh:
            script = fh.read()
        self.assertIn("Call script", script)
        self.assertIn("(937) 555-0112", script)      # real phone in the script
        self.assertIn("not interested", script.lower())  # graceful opt-out

    def test_no_contact_at_all_is_discover(self):
        d = self.writer.draft(self._prospect(email="", phone=""))
        self.assertEqual(d.channel, "discover")
        self.assertTrue(d.needs_contact_lookup)
        self.assertEqual(d.call_script_path, "")


if __name__ == "__main__":
    unittest.main()
