# Sarah — Automation Policy

This document is the explicit, auditable boundary for what the agents do on their own.
It exists so the line is principled and visible, not arbitrary.

## The two gates and one refusal

Every opportunity the team finds is routed to exactly one outcome:

| Outcome | What happens | Trigger |
|---|---|---|
| **AUTO** | An agent produces the work product with no human input | Free + legitimate + automatable production step |
| **GATE — spend** | Held for your explicit approval; logged to the ledger | Requires upfront payment (or any cost) |
| **REFUSE — ban risk** | Not done at all; surfaced as a warning | Automating it violates ToS / is fraud → account ban |
| **HUMAN** | Surfaced and ranked for you to execute | Legitimate but genuinely needs a real person |

You set the spend gate ("nothing costs money without approval"). The **ban-risk refusal
is not optional**, because a banned account earns $0 — protecting your accounts *is*
part of making money, not a competing concern.

## What the agents do autonomously (AUTO)

- **Open-source bounties** — draft a solution plan / patch scaffold for a funded issue.
- **Content / affiliate** — draft a complete, original article (no spam, with disclosure).
- **Freelance leads** — draft a tailored, ready-to-submit proposal.

The *production* is automated. Final submission to a third party (a PR, a published
post) is left for a human glance, because volume bot-submission is itself a ban/abuse
vector — a ban-risk guard, not a spend guard.

## What the agents will NOT automate, and why (REFUSE)

- **Watching ads / paid-to-click** — ToS prohibits automation; detection = ban +
  forfeited balance. Defrauds the advertiser. Pays fractions of a cent.
- **Auto-completing surveys** — submitting bot/fake responses is **data fraud**; on
  research platforms it corrupts paid-for data and flags your identity.
- **Mass auto-creating accounts** — violates "no automated registration" clauses; an
  abuse pattern that gets emails/identities blocked across platforms.
- **Unauthorized vulnerability scanning** — testing targets you are not authorized and
  in-scope to test is **illegal** (e.g. CFAA). Bug-bounty work is supported only for
  authorized, in-scope programs with human-validated reports.

These are refused even when instructed, because they lose money and create legal/account
risk for the owner. This is a deliberate, fixed policy.

## Human-required (HUMAN)

Expert-network calls, paid B2B/UX research, usability tests, and authorized bug-bounty
testing need a real, verified human. The agents find, vet, rank, and prep — you execute.

## Local web-agency pipeline (`sarah/agency/`)

The Prospector → Auditor → Builder → Outreach team finds local service businesses with a
weak online presence, builds real demo sites, and drafts outreach. Its boundary:

| Outcome | Actions |
|---|---|
| **AUTO** | Prospect via free OpenStreetMap/seed data · audit online presence · build static demo sites locally · draft outreach emails (as drafts only). |
| **GATE — spend** | Paid data APIs (Google Places/Yelp) · custom domains · paid hosting tiers · paid ads · real-LLM API usage. All held for approval; default paths are free. |
| **HUMAN** | Sending the outreach · choosing what to deploy · finding a missing business email · closing the deal and collecting payment. |
| **REFUSE** | Scraping a source in violation of its ToS · fabricating business info or reviews · presenting a demo as the business's *live* official site (impersonation) · mass non-compliant emailing · cold SMS (TCPA). |

Compliance baked in: demo sites use only public business info, carry `noindex`, and are
clearly labeled proposals. Outreach is CAN-SPAM-formatted (truthful subject, sender
identity, postal address, opt-out) and the **owner is always the legal sender** — the
agents only prepare a draft; a human reviews and sends. Deploying to Vercel's free tier
costs nothing and is delegated to the orchestrating agent via MCP; the Python itself
never deploys, sends, or spends.
