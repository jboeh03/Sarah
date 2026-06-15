"""Auditor agent — assesses a business's online presence and scores how badly they
need what we're selling.

``need_score`` (0..100) is high when the presence is weak: no real website, a broken or
non-mobile site, social-only, no reviews, not on the map. It pairs with
``Prospect.opportunity_score`` (which multiplies need by viability) so the pipeline
pursues real, reachable businesses that simply lack a web presence — the easiest sells.

Live website checks (reachable? https? mobile viewport?) are attempted only when
enabled and degrade gracefully: any failure leaves the signal as "unknown" (None)
rather than guessing.
"""

from __future__ import annotations

from typing import Optional

from .models import Prospect, AuditResult, OutreachStage


class Auditor:
    def __init__(self, check_websites: bool = False, timeout_seconds: int = 8):
        # check_websites should track live-network availability; off by default so
        # offline runs are deterministic.
        self.check_websites = check_websites
        self.timeout_seconds = timeout_seconds
        self.log: list[str] = []

    def audit(self, p: Prospect) -> AuditResult:
        signals: list[str] = []
        score = 0.0

        has_site = p.has_real_website
        reachable: Optional[bool] = None
        https: Optional[bool] = None
        mobile: Optional[bool] = None

        if not has_site and not p.has_social_presence:
            score += 50
            signals.append("No website at all — invisible to anyone searching online.")
        elif not has_site and p.has_social_presence:
            score += 25
            signals.append("Only a social page, no real website — can't rank or convert like a site.")
        else:
            # Has a real website. Optionally check its quality.
            if self.check_websites:
                reachable, https, mobile = self._check_site(p.website)
                if reachable is False:
                    score += 45
                    signals.append("Website appears broken/unreachable — worse than no site for trust.")
                elif reachable:
                    if https is False:
                        score += 12
                        signals.append("Site has no HTTPS — browsers flag it 'Not secure'.")
                    if mobile is False:
                        score += 12
                        signals.append("Site is not mobile-friendly — most local searches are on phones.")
            else:
                score += 5
                signals.append("Has a website (quality unverified offline).")

        if not p.on_google_maps:
            score += 8
            signals.append("Not found on Google Maps — missing the #1 local discovery channel.")

        review_count = p.review_count or 0
        if review_count == 0:
            score += 6
            signals.append("No visible reviews — little social proof for new customers.")
        elif review_count >= 10 and (p.rating or 0) >= 4.0:
            signals.append(
                f"Strong reputation ({p.rating}★, {review_count} reviews) but no site to "
                f"showcase it — high-value, easy win."
            )

        contactable = bool(p.phone or p.email)
        if not contactable:
            signals.append("No public phone/email found — outreach will need a contact lookup first.")

        score = min(round(score, 1), 100.0)

        result = AuditResult(
            has_website=has_site,
            website_reachable=reachable,
            website_https=https,
            mobile_viewport=mobile,
            has_reviews=review_count > 0,
            review_count=review_count,
            rating=p.rating,
            on_google_maps=p.on_google_maps,
            contactable=contactable,
            need_score=score,
            signals=signals,
        )
        p.audit = result
        if p.outreach_stage == OutreachStage.NEW.value:
            p.outreach_stage = OutreachStage.AUDITED.value
        return result

    def audit_all(self, prospects: list[Prospect]) -> list[Prospect]:
        for p in prospects:
            self.audit(p)
        ranked = sorted(prospects, key=lambda p: p.opportunity_score(), reverse=True)
        self.log.append(f"Audited {len(prospects)} businesses; ranked by opportunity score.")
        return ranked

    # ---- live site check ---------------------------------------------------

    def _check_site(self, url: str):
        """Return (reachable, https, mobile_viewport). Any of them may be None/False.

        Never raises — network failure means 'unknown', not a crash.
        """
        if not url:
            return None, None, None
        try:
            import urllib.request

            https = url.lower().startswith("https://")
            req = urllib.request.Request(url, headers={"User-Agent": "sarah-agency/0.1"})
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                final_url = resp.geturl()
                https = final_url.lower().startswith("https://")
                body = resp.read(60000).decode("utf-8", errors="replace").lower()
            mobile = 'name="viewport"' in body or "name='viewport'" in body
            return True, https, mobile
        except Exception as exc:
            self.log.append(f"Site check failed for {url} ({exc}).")
            return False, None, None
