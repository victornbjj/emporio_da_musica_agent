"""Split the policy manual PDF into one chunk per numbered section."""
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

HEADING_RE = re.compile(r"^(\d{1,2}(?:\.\d{1,2})?)\.?\s+(\S.*)$")
NOISE_RE = re.compile(r"^(Empório da Música Manual de Políticas.*|Página\s+\d+)$")


@dataclass(frozen=True)
class Chunk:
    section: str   # e.g. "4.1"
    title: str     # e.g. "Direito de Arrependimento (Compras Online)"
    text: str      # body text (without the heading line)
    parent: str = ""  # title of the top-level section, e.g. "Política de Frete e Entregas"


def _clean_lines(pdf_path: Path) -> list[str]:
    lines: list[str] = []
    for page in PdfReader(pdf_path).pages:
        for raw in page.extract_text(extraction_mode="layout").splitlines():
            line = re.sub(r"\s+", " ", raw).strip().replace("\u200b", "")
            if line and not NOISE_RE.match(line):
                lines.append(line)
    return lines


def _is_next_section(candidate: str, current: str | None) -> bool:
    """A heading is only valid if it follows the previous one in order.

    This rejects numbered list items (e.g. '3. Consulta:' inside section 7.2).
    """
    if current is None:
        return candidate == "1"
    major, _, minor = current.partition(".")
    expected = {str(int(major) + 1), f"{major}.{int(minor or 0) + 1}"}
    return candidate in expected


def chunk_policies(pdf_path: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    section = title = None
    body: list[str] = []

    def flush() -> None:
        if section is not None:
            chunks.append(Chunk(section, title, "\n".join(body).strip()))

    for line in _clean_lines(pdf_path):
        m = HEADING_RE.match(line)
        if m and _is_next_section(m.group(1), section):
            flush()
            section, title, body = m.group(1), m.group(2).strip(), []
        elif section is not None:
            body.append(line)
    flush()

    # Give each subsection the title of its top-level section as context, and
    # drop heading-only chunks (e.g. "5. Política de Frete" has no body of its own).
    top_titles = {c.section: c.title for c in chunks if "." not in c.section}
    return [
        Chunk(c.section, c.title, c.text,
              parent=top_titles.get(c.section.split(".")[0], "") if "." in c.section else "")
        for c in chunks
        if c.text
    ]