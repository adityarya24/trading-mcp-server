"""PDF export: JSON report → HTML (Jinja2) → Chromium or reportlab fallback."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def _template_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def _template_name(report_type: str) -> str:
    if report_type == "morning_brief":
        return "morning_brief.html"
    if report_type == "eod_review":
        return "eod_review.html"
    raise ValueError(f"Unsupported report_type for PDF: {report_type}")


def render_html(report: dict[str, Any]) -> str:
    env = _template_env()
    template = env.get_template(_template_name(report["report_type"]))
    return template.render(report=report)


def resolve_renderer(explicit: str | None = None) -> str:
    if explicit:
        return explicit.lower()
    return os.environ.get("TRADING_PDF_RENDERER", "html").lower()


def export_report_pdf(
    report: dict[str, Any],
    output_path: Path | str,
    *,
    renderer: str | None = None,
) -> dict[str, Any]:
    """Write PDF to output_path. Returns metadata dict with path + renderer used."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    html = render_html(report)
    explicit = renderer is not None
    mode = resolve_renderer(renderer)

    if mode == "html":
        try:
            _html_to_chromium_pdf(html, out)
            return {"pdf_path": str(out), "renderer": "html", "bytes": out.stat().st_size}
        except Exception as exc:
            if explicit:
                raise
            _reportlab_pdf(report, out, note=f"Chromium unavailable ({exc}); reportlab fallback.")
            return {"pdf_path": str(out), "renderer": "reportlab", "bytes": out.stat().st_size}

    _reportlab_pdf(report, out)
    return {"pdf_path": str(out), "renderer": "reportlab", "bytes": out.stat().st_size}


def find_chromium_executable() -> str | None:
    """Resolve a Chromium binary: env var first, then well-known local installs.

    Returns None when nothing is found, in which case Playwright falls back to
    its own managed Chromium (if installed)."""
    env = os.environ.get("TRADING_CHROMIUM_EXECUTABLE")
    if env:
        return env
    import glob

    candidates = sorted(
        glob.glob(os.path.expanduser("~/.agent-browser/browsers/chrome-*/chrome")),
        reverse=True,
    )
    candidates += [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


def _html_to_chromium_pdf(html: str, output_path: Path) -> None:
    from playwright.sync_api import sync_playwright

    executable = find_chromium_executable()
    with sync_playwright() as p:
        launch_kwargs: dict[str, Any] = {"headless": True}
        if executable:
            launch_kwargs["executable_path"] = executable
        browser = p.chromium.launch(**launch_kwargs)
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="networkidle")
            page.pdf(path=str(output_path), format="A4", print_background=True)
        finally:
            browser.close()


def _reportlab_pdf(report: dict[str, Any], output_path: Path, note: str | None = None) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    story: list[Any] = []
    story.append(Paragraph(report.get("title", "Trading Report"), styles["Title"]))
    story.append(Paragraph(f"Date: {report.get('report_date')}", styles["Normal"]))
    story.append(Paragraph(f"Generated: {report.get('generated_at')}", styles["Normal"]))
    if note:
        story.append(Paragraph(note, styles["Italic"]))
    story.append(Spacer(1, 12))

    sections = report.get("sections") or {}
    for section_name, payload in sections.items():
        story.append(Paragraph(section_name.replace("_", " ").title(), styles["Heading2"]))
        if isinstance(payload, list):
            if payload and isinstance(payload[0], dict):
                keys = list(payload[0].keys())
                data = [keys] + [[str(row.get(k, "")) for k in keys] for row in payload]
                table = Table(data, repeatRows=1)
                table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                            ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ]
                    )
                )
                story.append(table)
            else:
                story.append(Paragraph(json.dumps(payload, indent=2)[:4000], styles["Code"]))
        elif isinstance(payload, dict):
            rows = [[str(k), str(v)] for k, v in payload.items()]
            if rows:
                table = Table(rows, colWidths=[140, 340])
                table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey)]))
                story.append(table)
        else:
            story.append(Paragraph(str(payload), styles["Normal"]))
        story.append(Spacer(1, 10))

    story.append(Paragraph(report.get("disclaimer", ""), styles["Italic"]))
    doc = SimpleDocTemplate(str(output_path), pagesize=A4)
    doc.build(story)