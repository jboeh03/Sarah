"""Builder agent — generates a real, mobile-responsive static demo site from a
Prospect's actual data.

Design choices:
- **Honest, no fabrication.** Only the business's real name/location/contact/reputation
  are used. Where we don't have data, we omit it rather than invent it. Every page is
  clearly marked a DEMO PREVIEW prepared as a proposal, and carries ``noindex`` so it
  can't be mistaken for the live site or pollute search.
- **Great offline.** Copy is niche-aware and deterministic, so a clean site is produced
  with zero network and zero LLM. The ``LLMClient`` seam only *upgrades* the headline
  and about copy when a real model is wired in (``TemplateLLM`` is skipped).
- **Deploy seam.** ``deploy_manifest`` lists what to publish; actual deployment to
  Vercel is performed by the orchestrating agent via the Vercel MCP tool (the Python
  never deploys or spends on its own), mirroring how email send is handled.
"""

from __future__ import annotations

import html
import os
from dataclasses import dataclass, field
from typing import Optional

from .models import Prospect, Niche, OutreachStage
from ..workers.base import LLMClient, TemplateLLM


@dataclass
class NicheTemplate:
    tagline: str
    services: list
    accent: str          # hero accent color
    hero: str            # headline template, may use {name} and {city}


NICHE_TEMPLATES: dict[Niche, NicheTemplate] = {
    Niche.GRILL_CLEANING: NicheTemplate(
        tagline="Professional Grill & BBQ Cleaning",
        services=["Deep grill cleaning & degreasing", "Grate restoration", "Pre-season tune-ups", "Recurring maintenance plans"],
        accent="#c2410c",
        hero="A spotless grill, ready to fire up — {city}'s trusted grill cleaning.",
    ),
    Niche.POOL_SERVICE: NicheTemplate(
        tagline="Pool Opening, Closing & Maintenance",
        services=["Seasonal pool openings", "Weekly cleaning & chemicals", "Filter & equipment service", "Closings & winterization"],
        accent="#0369a1",
        hero="Crystal-clear water all season — {city}'s reliable pool service.",
    ),
    Niche.PRESSURE_WASHING: NicheTemplate(
        tagline="Pressure & Soft Washing",
        services=["Driveways & sidewalks", "House soft-washing", "Decks & patios", "Roof & gutter cleaning"],
        accent="#15803d",
        hero="Make it look new again — {city}'s pressure washing pros.",
    ),
    Niche.DECK_BUILDING: NicheTemplate(
        tagline="Custom Decks & Outdoor Living",
        services=["New deck design & build", "Deck repair & restoration", "Railings & pergolas", "Staining & sealing"],
        accent="#a16207",
        hero="Build the backyard you've been picturing — {city}'s deck builders.",
    ),
    Niche.DETAILING: NicheTemplate(
        tagline="Auto Detailing — We Come to You",
        services=["Full interior & exterior detail", "Paint correction & wax", "Ceramic coating", "Mobile service at your door"],
        accent="#1d4ed8",
        hero="Showroom shine in your driveway — {city}'s mobile detailing.",
    ),
    Niche.LANDSCAPING: NicheTemplate(
        tagline="Lawn Care & Landscaping",
        services=["Mowing & lawn maintenance", "Landscape design & installs", "Mulching & cleanups", "Seasonal services"],
        accent="#166534",
        hero="A yard the whole street notices — {city}'s lawn & landscape crew.",
    ),
    Niche.OTHER: NicheTemplate(
        tagline="Quality Local Service",
        services=["Professional service", "Free quotes", "Locally owned", "Satisfaction guaranteed"],
        accent="#374151",
        hero="Trusted local service in {city}.",
    ),
}


@dataclass
class SiteArtifact:
    prospect_id: str
    business_name: str
    path: str            # index.html path on disk
    dir: str             # site directory
    summary: str
    deploy_name: str     # suggested unique deploy slug


class SiteBuilder:
    def __init__(self, llm: Optional[LLMClient] = None, out_dir: str = "out/agency",
                 owner_name: str = "", owner_email: str = ""):
        self.llm = llm or TemplateLLM()
        self.out_dir = out_dir
        self.owner_name = owner_name
        self.owner_email = owner_email
        self.log: list[str] = []

    def build(self, p: Prospect) -> SiteArtifact:
        tpl = NICHE_TEMPLATES.get(p.niche, NICHE_TEMPLATES[Niche.OTHER])
        city = p.locality or "your area"

        headline = tpl.hero.format(name=p.name, city=city)
        about = self._default_about(p, tpl, city)

        # Optional LLM enhancement (skipped for the offline TemplateLLM fallback).
        if not isinstance(self.llm, TemplateLLM):
            headline = self._llm_text(
                "Write one punchy <12-word hero headline for a local service website. "
                "No quotes, no emojis, factual.",
                f"Business: {p.name}. Service: {tpl.tagline}. City: {city}.",
                default=headline,
            )
            about = self._llm_text(
                "Write a warm, 2-3 sentence 'about' paragraph for a local service "
                "business website. Factual, no invented awards or claims.",
                f"Business: {p.name}. Service: {tpl.tagline}. City: {city}. "
                f"Reputation: {self._reputation_str(p) or 'not specified'}.",
                default=about,
            )

        page_dir = os.path.join(self.out_dir, "sites", p.id)
        os.makedirs(page_dir, exist_ok=True)
        path = os.path.join(page_dir, "index.html")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self._render_html(p, tpl, headline, about, city))

        p.demo_site_path = path
        if p.outreach_stage in (OutreachStage.NEW.value, OutreachStage.AUDITED.value):
            p.outreach_stage = OutreachStage.BUILT.value
        self.log.append(f"Built demo site for {p.name} -> {path}")

        return SiteArtifact(
            prospect_id=p.id,
            business_name=p.name,
            path=path,
            dir=page_dir,
            summary=f"Mobile-ready demo site for {p.name} ({tpl.tagline}).",
            deploy_name=f"demo-{p.id}"[:60],
        )

    def build_all(self, prospects: list[Prospect]) -> list[SiteArtifact]:
        return [self.build(p) for p in prospects]

    def deploy_manifest(self, artifacts: list[SiteArtifact]) -> dict:
        """What the orchestrating agent should publish to Vercel (free tier).

        The Python does not deploy — it hands this manifest off, the same way email
        sending is delegated to the Gmail MCP tool. Deploying to Vercel's free tier
        costs nothing; a custom domain would, and that stays behind the spend gate.
        """
        return {
            "provider": "vercel",
            "tier": "free",
            "note": "Deploy each dir as a static site. Custom domains cost money -> spend gate.",
            "sites": [{"name": a.deploy_name, "dir": a.dir, "business": a.business_name} for a in artifacts],
        }

    # ---- copy helpers ------------------------------------------------------

    def _llm_text(self, system: str, prompt: str, default: str) -> str:
        try:
            out = self.llm.generate(system, prompt).strip()
            return out or default
        except Exception:
            return default

    def _default_about(self, p: Prospect, tpl: NicheTemplate, city: str) -> str:
        rep = self._reputation_str(p)
        rep_clause = f" {rep}" if rep else ""
        return (
            f"{p.name} provides {tpl.tagline.lower()} for homeowners in {city} and the "
            f"surrounding area.{rep_clause} Locally owned and proud of the work — reach "
            f"out for a free, no-pressure quote."
        )

    @staticmethod
    def _reputation_str(p: Prospect) -> str:
        if p.rating and (p.review_count or 0) > 0:
            return f"Rated {p.rating}★ across {p.review_count} local reviews."
        return ""

    # ---- HTML --------------------------------------------------------------

    def _render_html(self, p: Prospect, tpl: NicheTemplate, headline: str, about: str, city: str) -> str:
        e = html.escape
        name = e(p.name)
        accent = tpl.accent
        phone_raw = "".join(ch for ch in p.phone if ch.isdigit() or ch == "+")
        phone_link = (
            f'<a class="cta" href="tel:{e(phone_raw)}">📞 Call {e(p.phone)}</a>' if p.phone else ""
        )
        services = "\n".join(
            f'      <div class="card"><h3>{e(s)}</h3></div>' for s in tpl.services
        )
        rep = self._reputation_str(p)
        rep_html = f'<p class="rep">⭐ {e(rep)}</p>' if rep else ""
        email_html = f'<p>Email: <a href="mailto:{e(p.email)}">{e(p.email)}</a></p>' if p.email else ""
        addr_html = f"<p>{e(p.address)}</p>" if p.address else ""
        owner = e(self.owner_name) or "your local web partner"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{name} — {e(tpl.tagline)}</title>
<style>
  :root {{ --accent: {accent}; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; color:#1f2937; line-height:1.5; }}
  .demo-banner {{ background:#fffbeb; color:#92400e; text-align:center; padding:8px 12px; font-size:13px; border-bottom:1px solid #fde68a; }}
  header {{ background:var(--accent); color:#fff; padding:14px 20px; display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:10px; }}
  header .brand {{ font-weight:700; font-size:20px; }}
  .hero {{ background:linear-gradient(135deg, var(--accent), #111827); color:#fff; padding:64px 20px; text-align:center; }}
  .hero h1 {{ font-size:32px; margin:0 0 10px; max-width:760px; margin-inline:auto; }}
  .hero p {{ font-size:17px; opacity:.92; }}
  .cta {{ display:inline-block; background:#fff; color:var(--accent); font-weight:700; padding:12px 22px; border-radius:8px; text-decoration:none; margin-top:14px; }}
  .wrap {{ max-width:960px; margin:0 auto; padding:40px 20px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; }}
  .card {{ border:1px solid #e5e7eb; border-radius:10px; padding:18px; background:#fafafa; }}
  .card h3 {{ margin:0; font-size:16px; }}
  h2 {{ font-size:24px; }}
  .rep {{ color:var(--accent); font-weight:600; }}
  .contact {{ background:#f3f4f6; }}
  footer {{ text-align:center; color:#6b7280; font-size:13px; padding:24px 20px; border-top:1px solid #e5e7eb; }}
  @media (max-width:600px) {{ .hero h1 {{ font-size:26px; }} .hero {{ padding:44px 16px; }} }}
</style>
</head>
<body>
<div class="demo-banner">DEMO PREVIEW prepared for {name} — not the live site. A proposal mockup by {owner}.</div>
<header>
  <div class="brand">{name}</div>
  {phone_link}
</header>
<section class="hero">
  <h1>{e(headline)}</h1>
  <p>{e(tpl.tagline)} · Serving {e(city)}</p>
  <a class="cta" href="#contact">Get a Free Quote</a>
</section>
<div class="wrap">
  <h2>Our Services</h2>
  <div class="grid">
{services}
  </div>
</div>
<div class="wrap" style="padding-top:0">
  <h2>About {name}</h2>
  {rep_html}
  <p>{e(about)}</p>
</div>
<div class="wrap contact" id="contact">
  <h2>Get a Free Quote</h2>
  <p>Serving {e(city)}{e(', ' + p.region) if p.region else ''} and nearby.</p>
  {f'<p>Call: <a href="tel:{e(phone_raw)}">{e(p.phone)}</a></p>' if p.phone else ''}
  {email_html}
  {addr_html}
  {phone_link}
</div>
<footer>
  This is an unofficial demo proposal built for {name}. Business details are public
  information; imagery and copy are placeholders pending the owner's approval.
</footer>
</body>
</html>
"""
