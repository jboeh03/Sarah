"""Open-source bounty worker — autonomously produces a solution plan for a funded
GitHub issue (Algora, IssueHunt). This is the closest thing to "an agent that does the
earning work itself": writing code to solve a real, funded problem.

Given a specific issue (repo + issue text in ``context``), it emits a structured
solution scaffold — restated problem, approach, file-level plan, and a PR description.
With an LLMClient wired in, it drafts the actual patch. It does NOT open PRs on
third-party repos automatically: maintainers ban low-quality bot PRs, so the prepared
solution is surfaced for a human to review and submit (a deliberate ban-risk guard,
not a spend guard).
"""

from __future__ import annotations

from ..models import Opportunity, Category
from .base import Worker, Deliverable


class OSSBountyWorker(Worker):
    categories = {Category.OPEN_SOURCE_BOUNTY}

    def produce(self, opp: Opportunity, context: dict | None = None) -> Deliverable:
        context = context or {}
        repo = context.get("repo", "<target repo>")
        issue = context.get("issue_title", opp.title)
        issue_body = context.get("issue_body", opp.description)

        system = (
            "You are a senior engineer. Produce a correct, minimal solution. Match the "
            "repo's existing style. Include tests. Do not invent APIs."
        )
        plan = self.llm.generate(system, self._plan_prompt(repo, issue, issue_body))

        content = f"""# Bounty solution plan — {issue}

- **Source:** {opp.source} · **Repo:** {repo}
- **Link:** {opp.url}

{plan}

---
### Before submitting (ban-risk guard)
- Confirm the issue is still open and the bounty active.
- Run the repo's full test + lint suite locally; match its conventions exactly.
- Keep the PR focused and minimal; reference the issue. Maintainers ban spammy/AI-slop
  PRs, so a human should review this before it goes out.
"""
        path = self._write(opp, "solution-plan.md", content)
        return Deliverable(
            opportunity_id=opp.id,
            title=f"Bounty solution plan: {issue}",
            path=path,
            summary=f"Prepared a solution scaffold for a {opp.source} bounty.",
            next_step="Review the plan, finish the patch, run tests, and submit the PR for the bounty.",
        )

    def _plan_prompt(self, repo: str, issue: str, issue_body: str) -> str:
        return f"""## Problem (restated)
{issue}: {issue_body}

## Root cause / where this lives
Identify the module(s) and functions involved in `{repo}`.

## Proposed approach
The minimal change that solves it, and why it's correct.

## File-level plan
- `path/to/file.py` — what changes and why
- `tests/test_*.py` — the test that proves it

## Risks / edge cases
List what could break and how the tests cover it.

## PR description (ready to paste)
A concise summary linking the issue, what changed, and how it was verified.
"""
