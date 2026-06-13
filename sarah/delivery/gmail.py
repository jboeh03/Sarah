"""Builds an email payload from a digest, ready to be sent via the Gmail MCP tool.

We deliberately keep *sending* out of this Python process. The orchestrating agent
(Claude, with the Gmail MCP connection) is what actually sends — and only when you've
opted in (``delivery.send_email: true``). This module just prepares a clean payload:
subject, pl-text body, and a minimal HTML body.

This separation matters: it means the autonomous loop can prepare your daily digest
without anything ever leaving your inbox until you say so.
"""

from __future__ import annotations

import datetime as _dt
import html
import re
from dataclasses import dataclass


@dataclass
class EmailPayload:
    to: str
    subject: str
    body_text: str
    body_html: str

    def to_dict(self) -> dict:
        return {
            "to": self.to,
            "subject": self.subject,
            "body_text": self.body_text,
            "body_html": self.body_html,
        }


def build_email_payload(
    digest_markdown: str,
    to: str,
    date: _dt.date | None = None,
    headline: str | None = None,
) -> EmailPayload:
    date = date or _dt.date.today()
    subject = headline or f"Sarah · {date.isoformat()} · today's vetted income opportunities"
    body_html = _markdown_to_basic_html(digest_markdown)
    return EmailPayload(
        to=to,
        subject=subject,
        body_text=digest_markdown,
        body_html=body_html,
    )


def _markdown_to_basic_html(md: str) -> str:
    """A tiny, dependency-free Markdown-to-HTML converter for the bits we emit.

    Handles headings, tables, list items, bold, links, and blockquotes — enough for
    the digest. Not a general Markdown engine.
    """
    out: list[str] = ["<div style=\"font-family:system-ui,Arial,sans-serif;max-width:760px\">"]
    in_table = False

    def inline(s: str) -> str:
        s = html.escape(s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"_([^_]+)_", r"<em>\1</em>", s)
        return s

    for raw in md.splitlines():
        line = raw.rstrip()

        # Table rows.
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):  # separator row
                continue
            if not in_table:
                out.append("<table style='border-collapse:collapse;width:100%'>")
                in_table = True
            tag = "td"
            out.append(
                "<tr>" + "".join(
                    f"<{tag} style='border:1px solid #ddd;padding:6px'>{inline(c)}</{tag}>"
                    for c in cells
                ) + "</tr>"
            )
            continue
        elif in_table:
            out.append("</table>")
            in_table = False

        if not line:
            out.append("<br/>")
        elif line.startswith("### "):
            out.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.startswith("## "):
            out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("> "):
            out.append(f"<blockquote style='color:#a33'>{inline(line[2:])}</blockquote>")
        elif line.lstrip().startswith("- "):
            indent = len(line) - len(line.lstrip())
            style = "margin-left:%dpx" % (12 + indent * 4)
            out.append(f"<div style='{style}'>• {inline(line.lstrip()[2:])}</div>")
        elif line.startswith("---"):
            out.append("<hr/>")
        else:
            out.append(f"<p>{inline(line)}</p>")

    if in_table:
        out.append("</table>")
    out.append("</div>")
    return "\n".join(out)
