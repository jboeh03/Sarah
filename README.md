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
- Runs a **team of agents** (`Researcher → Analyst → Reporter`, coordinated by an
  `Orchestrator`) that brainstorm and gather income opportunities from a curated set
  of real, reputable platforms, plus optional live feeds.
- **Vets every opportunity**: rejects scams/MLMs/pay-to-play, flags anything that
  requires spending, and honestly classifies how automatable each one is.
- **Scores opportunities** by *estimated dollars-per-hour*, legitimacy, skill needed,
  and automation risk — so you chase real money, not pennies.
- Produces a **daily digest** ranked by expected value, with a clearly separated
  "needs your approval (costs money)" section.

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
  guardrails.py               # SpendingGuardrail — the "no spend without approval" rule
  vetter.py                   # scam / ToS / automation-risk classification
  models.py                   # Opportunity model + honest $/hr scoring
  store.py                    # dedupe + persistence of seen opportunities
  delivery/
    digest.py                 # renders Markdown digest
    gmail.py                  # builds an email payload for Gmail-MCP delivery
data/
  opportunity_sources.json    # curated, real, verifiable platforms
config/
  settings.json               # guardrail + preferences
tests/                        # guardrail / vetter / scoring tests (stdlib unittest)
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
