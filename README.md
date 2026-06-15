# Sarah — Autonomous Income-Opportunity Agent Team

Sarah is a small team of cooperating agents whose job is to **find, vet, score, and
report legitimate ways to earn money online** — every day, on its own.

It is built around one firm rule you set:

> **Nothing that costs money happens without your explicit approval.**

Everything else (researching opportunities, scoring them, drafting a daily digest,
preparing account sign-ups for your review) runs without you in the loop.

---

## What this is — and what it deliberately is *not*

### What it does
- Runs a **team of agents** (`Researcher → Analyst → Executor → Reporter`, coordinated
  by an `Orchestrator`) that brainstorm and gather income opportunities from a curated
  set of real, reputable platforms, plus optional live feeds.
- **Vets every opportunity**: rejects scams/MLMs/pay-to-play, flags anything that
  requires spending, and honestly classifies how automatable each one is.
- **Does the legitimately-automatable work autonomously**: an `Executor` + worker
  agents produce real deliverables with no human input — open-source bounty solution
  plans, complete article drafts, tailored freelance proposals — gated only by spending
  and account-ban risk. See [`POLICY.md`](POLICY.md) for the exact boundary.
- **Scores opportunities** by *estimated dollars-per-hour*, legitimacy, skill needed,
  and automation risk — so you chase real money, not pennies.
- Produces a **daily digest** ranked by expected value, with separated sections for
  "produced autonomously," "needs your approval (costs money)," "refused (ban risk),"
  and "needs a human."

### What it does NOT do, and why
This system will not build or run bots that **auto-watch ads, auto-complete surveys,
or mass-create/operate accounts to farm micro-rewards.** That isn't a money machine —
it's an account-ban machine:

- Every paid-to-click / survey / "get-paid-to" platform **prohibits automation** in
  its Terms and uses bot detection. Detected automation = **account banned + balance
  forfeited.**
- Submitting automated survey/research answers (Prolific, MTurk, UserTesting) is
  **data fraud**, not earning. It corrupts the data the requester paid for and can get
  your identity blocked across platforms.
- The payouts are **fractions of a cent**; even for a human these sites pay well below
  minimum wage. Automated, the expected value is *negative* (you lose the account).

So Sarah treats that whole category as **NOT_RECOMMENDED** and tells you so, instead of
quietly burning your reputation. The honest path to real money is the legitimate
categories below.

---

## The opportunity categories Sarah tracks (ranked by realistic upside)

| Category | Realistic pay | Automatable? | Notes |
|---|---|---|---|
| **Bug bounties** | $0–$$$$ per valid bug | Research only; testing is human | Highest skilled upside. **Only authorized, in-scope targets.** |
| **Expert networks / consulting** | $100–$1000+/hr | No (human calls) | If you have niche professional expertise. |
| **B2B paid research** | $50–$200+/study | No (human) | Respondent, Wynter, User Interviews — for qualified professionals. |
| **Freelance / dev work** | $30–$200+/hr | Partly (you do the work) | Upwork, Contra, Toptal, Pangea. |
| **Open-source bounties** | $20–$2000+/issue | You write the code | Algora, IssueHunt — real money for merged PRs. |
| **Content / affiliate** | Slow ramp, $/mo | Partly; spam = banned | Legit but takes weeks/months and effort. |
| **Surveys / ads / GPT sites** | Pennies | **No — ban on automation** | Tracked only to warn you off. |

> Pay figures are **estimates** to rank opportunities, not guarantees.

---

## The honest bottom line on "fully autonomous daily income"

There is **no legal, no-skill, no-spend machine that prints money while you sleep.** If
there were, it would already be arbitraged to zero. What *is* real:

- Sarah can **autonomously do the finding, vetting, and prioritizing** — saving you the
  hours of searching and scam-dodging.
- The **execution** of the high-value work (writing a bug report, taking a research
  call, shipping a bounty PR) still needs you. That's exactly where the real money is,
  and exactly what can't be faked.

Sarah's value is pointing your limited human time at the **highest expected-value,
legitimate** opportunities each day.

---

## Architecture

```
scripts/run_daily.py          # entrypoint: runs the full daily cycle
sarah/
  agents/
    orchestrator.py           # coordinates the team, enforces guardrails
    researcher.py             # gathers opportunities (curated + live feeds)
    analyst.py                # vets + scores each opportunity
    reporter.py               # builds the ranked daily digest
  executor.py                 # action layer: runs workers, sorts the rest
  gates.py                    # Gatekeeper — auto / spend-gate / refuse / human
  workers/
    oss_bounty.py             # drafts a funded-issue solution plan
    content.py                # drafts a complete article
    freelance.py              # drafts a tailored proposal
  guardrails.py               # SpendingGuardrail — the "no spend without approval" rule
  vetter.py                   # scam / ToS / automation-risk classification
  models.py                   # Opportunity model + honest $/hr scoring
  store.py                    # dedupe + persistence of seen opportunities
  delivery/
    gmail.py                  # builds an email payload for Gmail-MCP delivery
data/
  opportunity_sources.json    # curated, real, verifiable platforms
config/
  settings.json               # guardrail + preferences
POLICY.md                     # explicit automate / gate / refuse boundary
tests/                        # guardrail / vetter / scoring / gates / executor tests
```

Pure standard library — no installs required to run.

## Run it

```bash
python3 scripts/run_daily.py            # run the daily cycle, write digest to ./out/
python3 -m unittest discover -s tests   # run the test suite
```

## Running autonomously (daily, no human input)

`.github/workflows/daily-opportunities.yml` runs the full cycle every day at 13:00 UTC
(and on-demand via "Run workflow"). Each run:
- gathers + vets + ranks opportunities,
- runs the test suite as a self-check,
- renders the digest into the **Actions run summary**, and
- uploads the digest + JSON snapshot as a **downloadable artifact** (30-day retention).

No human input is needed and nothing spends money. To also land the digest in your
inbox, see *Email / account access* below and flip `delivery.send_email` to `true`.

---

## Local web-agency pipeline (`sarah/agency/`)

A second team of agents that turns *"local service businesses with a weak online
presence"* into ready-to-send proposals. It builds **real demo websites** for businesses
that don't have one, then drafts the outreach — because pitching a finished site
(*"I built you this — want it live?"*) converts far better than offering to build one.

```
Prospector  → finds local businesses (free OpenStreetMap, paid sources gated)
Auditor     → scores online-presence gaps (no site? broken? few reviews? not on Maps?)
SiteBuilder → generates a real mobile-responsive demo site from their actual data
OutreachWriter → drafts a personalized, CAN-SPAM-compliant email (as a Gmail draft)
```

Ranking is `opportunity = need × viability`: a *great* business (proven by reviews) with
a *weak* web presence rises to the top — the easiest, highest-value sell. Realistic
value: **$500–$3,000 per site** plus recurring hosting/care.

### Run it

```bash
python3 scripts/run_agency.py --no-live    # offline, uses the seed dataset
python3 scripts/run_agency.py              # tries live OpenStreetMap, falls back to seed
```

Outputs land in `out/agency/`: the demo sites under `sites/<business>/index.html`, the
outreach drafts under `outreach/<business>.json`, and a ranked `report-latest.md`.

### Before a live run (one-time setup in `config/settings.json` → `agency`)

- **`area.locality`** — your city/town (e.g. `"Dayton"`). Offline runs use seed data; a
  live run needs this.
- **`owner_name`** and **`mailing_address`** — required in outreach before sending
  (CAN-SPAM needs a real sender identity + postal address).
- **`data_source`** — stays `"osm"` (free). Set to `"google_places"`/`"yelp"` only if you
  want richer data; that needs a paid key and is **held for your approval** automatically.

### How deploy + send work (delegated, never autonomous)

The Python builds the sites and drafts; the two outward steps are done by the
orchestrating agent through MCP, on your say-so:
- **Deploy**: each demo dir is published to **Vercel's free tier** for a shareable
  preview link (free; a custom domain would cost money → gated).
- **Send**: each draft becomes a **Gmail draft** for you to review and send — you're
  always the sender.

See [`POLICY.md`](POLICY.md) for the full AUTO / GATE / HUMAN / REFUSE boundary, including
the compliance rules (no fabricated info, demos marked as proposals, opt-out in every
email).

## Spending guardrail (your one firm rule)

Any action tagged `costs_money=True` is **never executed automatically.** It is routed
to `guardrails.SpendingGuardrail`, which raises `ApprovalRequired`, logs it to the
approval ledger, and surfaces it in the digest's **"Needs your approval"** section.
See `tests/test_guardrails.py` for the enforced behavior.

## Email / account access

Connected Gmail is used to **deliver your daily digest** and (optionally) read
opportunity-related notifications. Sarah does **not** silently auto-register you on
third-party sites: automated sign-up trips CAPTCHAs and "no automated registration"
clauses, and is the easiest way to get signed up for a scam. New-platform sign-ups are
prepared and surfaced for a one-click confirmation from you instead.
