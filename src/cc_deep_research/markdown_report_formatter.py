"""Normalize arbitrary Markdown into the standard PDF report structure."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class FormattedMarkdownReport:
    """Formatted report ready for PDF generation."""

    title: str
    markdown: str


@dataclass(frozen=True)
class ParsedMarkdownDocument:
    """Structured view of a markdown document."""

    title: str | None
    preamble: str
    sections: list[tuple[str, str]]
    raw_body: str


class MarkdownReportFormatter:
    """Formats markdown files into a consistent report layout."""

    _SECTION_ALIASES: dict[str, tuple[str, ...]] = {
        "Executive Summary": ("executive summary", "summary", "overview", "introduction"),
        "Key Findings": ("key findings", "findings", "highlights", "takeaways"),
        "Detailed Analysis": (
            "detailed analysis",
            "analysis",
            "discussion",
            "main analysis",
            "main content",
            "body",
        ),
        "Sources": ("sources", "references", "citations", "bibliography", "links"),
        "Safety": (
            "safety",
            "safety and contraindications",
            "warnings",
            "risks",
            "risk notes",
            "cautions",
        ),
        "Research Metadata": ("research metadata", "metadata"),
    }

    _URL_PATTERN = re.compile(r"https?://[^\s)>]+")
    _LIST_ITEM_PATTERN = re.compile(r"^(?:[-*+]|\d+\.)\s+(.+)$", re.MULTILINE)

    def format_report(
        self,
        markdown_content: str,
        source_path: Path,
        title: str | None = None,
    ) -> FormattedMarkdownReport:
        """Convert arbitrary markdown into the standard report structure."""
        document = self._parse_document(markdown_content)
        report_title = title or document.title or self._title_from_filename(source_path)
        canonical_sections = self._canonicalize_sections(document.sections)
        analysis_body = self._build_analysis_body(document, canonical_sections)

        executive_summary = self._build_executive_summary(
            canonical_sections,
            document,
            analysis_body,
            source_path,
        )
        key_findings = self._build_key_findings(canonical_sections, document, analysis_body)
        detailed_analysis = analysis_body or "No detailed analysis content was provided."
        sources = self._build_sources(canonical_sections, markdown_content)
        safety = self._build_safety(canonical_sections, markdown_content)
        metadata = self._build_metadata(canonical_sections, source_path)

        sections = [
            f"# {report_title}",
            "",
            "## Executive Summary",
            "",
            executive_summary,
            "",
            "## Key Findings",
            "",
            key_findings,
            "",
            "## Detailed Analysis",
            "",
            detailed_analysis,
            "",
            "## Sources",
            "",
            sources,
            "",
            "## Safety",
            "",
            safety,
            "",
            "## Research Metadata",
            "",
            metadata,
        ]

        return FormattedMarkdownReport(
            title=report_title,
            markdown="\n".join(sections).strip() + "\n",
        )

    def _parse_document(self, markdown_content: str) -> ParsedMarkdownDocument:
        normalized = markdown_content.replace("\r\n", "\n").strip()
        title: str | None = None
        body = normalized

        lines = normalized.split("\n") if normalized else []
        if lines and lines[0].startswith("# "):
            title = lines[0][2:].strip()
            body = "\n".join(lines[1:]).lstrip()

        sections = self._split_sections(body)
        preamble = body
        if sections:
            first_header = re.search(r"^##\s+.+$", body, re.MULTILINE)
            preamble = body[: first_header.start()].strip() if first_header else body

        return ParsedMarkdownDocument(
            title=title,
            preamble=preamble.strip(),
            sections=sections,
            raw_body=body.strip(),
        )

    def _split_sections(self, body: str) -> list[tuple[str, str]]:
        matches = list(re.finditer(r"^##\s+(.+?)\s*$", body, re.MULTILINE))
        if not matches:
            return []

        sections: list[tuple[str, str]] = []
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
            sections.append((match.group(1).strip(), body[start:end].strip()))
        return sections

    def _canonicalize_sections(self, sections: list[tuple[str, str]]) -> dict[str, str]:
        canonical_sections: dict[str, str] = {}
        for header, content in sections:
            canonical_name = self._canonical_section_name(header)
            if canonical_name and canonical_name not in canonical_sections and content:
                canonical_sections[canonical_name] = content.strip()
        return canonical_sections

    def _canonical_section_name(self, header: str) -> str | None:
        normalized_header = self._normalize_header(header)
        for canonical_name, aliases in self._SECTION_ALIASES.items():
            if any(
                normalized_header == alias or normalized_header.startswith(f"{alias} ")
                for alias in aliases
            ):
                return canonical_name
        return None

    def _build_analysis_body(
        self,
        document: ParsedMarkdownDocument,
        canonical_sections: dict[str, str],
    ) -> str:
        blocks: list[str] = []

        if document.preamble:
            blocks.append(document.preamble)

        if canonical_sections.get("Detailed Analysis"):
            blocks.append(canonical_sections["Detailed Analysis"])

        excluded_sections = {
            "Executive Summary",
            "Key Findings",
            "Detailed Analysis",
            "Sources",
            "Safety",
            "Research Metadata",
        }
        for header, content in document.sections:
            canonical_name = self._canonical_section_name(header)
            if canonical_name in excluded_sections:
                continue
            blocks.append(f"### {header}\n\n{content.strip()}")

        return "\n\n".join(block for block in blocks if block.strip()).strip()

    def _build_executive_summary(
        self,
        canonical_sections: dict[str, str],
        document: ParsedMarkdownDocument,
        analysis_body: str,
        source_path: Path,
    ) -> str:
        existing = canonical_sections.get("Executive Summary")
        if existing:
            return existing

        summary_source = document.preamble or analysis_body
        paragraphs = self._extract_paragraphs(summary_source)
        if paragraphs:
            return "\n\n".join(paragraphs[:2])

        return (
            f"This report reformats `{source_path.name}` into the standard CC Deep Research "
            "PDF layout. The original markdown content is preserved in the Detailed Analysis section."
        )

    def _build_key_findings(
        self,
        canonical_sections: dict[str, str],
        document: ParsedMarkdownDocument,
        analysis_body: str,
    ) -> str:
        existing = canonical_sections.get("Key Findings")
        if existing:
            return existing

        source_text = "\n\n".join(
            block for block in [document.preamble, analysis_body, document.raw_body] if block
        )
        bullet_points = self._extract_list_items(source_text)
        findings = [item for item in bullet_points if len(item) >= 20][:5]

        if not findings:
            findings = self._sentence_candidates(source_text)[:5]

        if not findings:
            findings = [
                "The source markdown was normalized into a consistent report layout.",
                "Key analysis content is preserved under Detailed Analysis for full context.",
                "Explicit source links and safety notes are surfaced in dedicated sections when available.",
            ]

        return "\n".join(f"- {finding}" for finding in findings)

    def _build_sources(
        self,
        canonical_sections: dict[str, str],
        markdown_content: str,
    ) -> str:
        existing = canonical_sections.get("Sources")
        if existing and self._extract_urls(existing):
            return existing

        urls = self._extract_urls(markdown_content)
        if not urls:
            return "No explicit source links were detected in the source markdown."

        lines = []
        for index, url in enumerate(urls, start=1):
            lines.append(f"{index}. [{self._display_source(url)}]({url})")
        return "\n".join(lines)

    def _build_safety(
        self,
        canonical_sections: dict[str, str],
        markdown_content: str,
    ) -> str:
        existing = canonical_sections.get("Safety")
        if existing:
            return existing

        safety_notes = self._extract_safety_notes(markdown_content)
        if not safety_notes:
            return (
                "No explicit safety, risk, warning, or contraindication content was detected "
                "in the source markdown."
            )

        return "\n".join(f"- {note}" for note in safety_notes[:5])

    def _build_metadata(
        self,
        canonical_sections: dict[str, str],
        source_path: Path,
    ) -> str:
        generated_lines = [
            f"- Source file: {source_path.name}",
            f"- Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "- Formatter: markdown-report-formatter",
        ]

        existing = canonical_sections.get("Research Metadata")
        if not existing:
            return "\n".join(generated_lines)

        return f"{existing}\n\n" + "\n".join(generated_lines)

    def _extract_paragraphs(self, text: str) -> list[str]:
        blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
        paragraphs: list[str] = []

        for block in blocks:
            if block.startswith("#"):
                continue
            if self._looks_like_list(block):
                continue
            paragraphs.append(block)

        return paragraphs

    def _extract_list_items(self, text: str) -> list[str]:
        items = [match.group(1).strip() for match in self._LIST_ITEM_PATTERN.finditer(text)]
        return [item for item in items if item]

    def _sentence_candidates(self, text: str) -> list[str]:
        candidates: list[str] = []
        for paragraph in self._extract_paragraphs(text):
            sentences = re.split(r"(?<=[.!?])\s+", paragraph)
            for sentence in sentences:
                cleaned = " ".join(sentence.split()).strip()
                if len(cleaned) >= 30:
                    candidates.append(cleaned)
        return candidates

    def _extract_urls(self, text: str) -> list[str]:
        urls = self._URL_PATTERN.findall(text)
        return self._dedupe(self._strip_trailing_punctuation(url) for url in urls)

    def _extract_safety_notes(self, markdown_content: str) -> list[str]:
        keywords = ("safety", "risk", "warning", "contraindication", "caution", "side effect")
        blocks = [block.strip() for block in re.split(r"\n\s*\n", markdown_content) if block.strip()]
        notes: list[str] = []

        for block in blocks:
            lowered = block.lower()
            if any(keyword in lowered for keyword in keywords):
                cleaned = " ".join(block.split())
                if len(cleaned) >= 20:
                    notes.append(cleaned)

        return self._dedupe(notes)

    def _display_source(self, url: str) -> str:
        match = re.match(r"https?://([^/]+)", url)
        return match.group(1) if match else url

    def _title_from_filename(self, source_path: Path) -> str:
        return source_path.stem.replace("-", " ").replace("_", " ").title()

    def _normalize_header(self, header: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", " ", header.lower())
        return " ".join(normalized.split())

    def _looks_like_list(self, block: str) -> bool:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            return False
        return all(
            line.startswith(("-", "*", "+"))
            or bool(re.match(r"^\d+\.\s+", line))
            for line in lines
        )

    def _strip_trailing_punctuation(self, value: str) -> str:
        return value.rstrip(".,);]")

    def _dedupe(self, values: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        unique_values: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            unique_values.append(value)
        return unique_values


__all__ = ["FormattedMarkdownReport", "MarkdownReportFormatter"]
