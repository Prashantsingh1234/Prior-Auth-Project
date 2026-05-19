"""Healthcare-aware semantic chunking for policy documents.

Goals:
- Preserve meaningful sections (headings, criteria lists, related CPT/ICD blocks)
- Avoid random fixed-size chopping
- Support overlap for retrieval continuity
"""

from __future__ import annotations

import re
from dataclasses import dataclass


_HEADING_RE = re.compile(r"^(?:[A-Z][A-Z0-9 /&()-]{5,}|\d+(?:\.\d+)*\s+.+)$")
_BULLET_RE = re.compile(r"^\s*(?:[-*]|\d+\.|\([a-zA-Z0-9]+\))\s+")


def _normalize_ws(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@dataclass(frozen=True)
class PolicyChunk:
    index: int
    text: str
    overlap: int

    @property
    def length(self) -> int:
        return len(self.text)


class PolicySemanticChunker:
    def __init__(
        self,
        *,
        target_chars: int = 1800,
        max_chars: int = 2600,
        overlap_chars: int = 220,
    ) -> None:
        self._target = target_chars
        self._max = max_chars
        self._overlap = max(0, overlap_chars)

    def chunk(self, text: str) -> list[PolicyChunk]:
        text = _normalize_ws(text)
        if not text:
            return []

        sections = self._split_into_sections(text)
        raw_chunks: list[str] = []
        for section in sections:
            raw_chunks.extend(self._pack_section(section))

        # Add overlap
        out: list[PolicyChunk] = []
        prev = ""
        for i, chunk_text in enumerate(raw_chunks):
            if i == 0 or self._overlap == 0:
                out.append(PolicyChunk(index=i, text=chunk_text, overlap=0))
            else:
                overlap_text = prev[-self._overlap :]
                merged = (overlap_text + "\n\n" + chunk_text).strip()
                out.append(PolicyChunk(index=i, text=merged, overlap=len(overlap_text)))
            prev = chunk_text

        return out

    def _split_into_sections(self, text: str) -> list[str]:
        lines = text.split("\n")
        blocks: list[list[str]] = []
        cur: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if cur and cur[-1] != "":
                    cur.append("")
                continue

            if _HEADING_RE.match(stripped) and len(cur) >= 3:
                blocks.append(cur)
                cur = [stripped]
            else:
                cur.append(stripped)
        if cur:
            blocks.append(cur)

        return ["\n".join(b).strip() for b in blocks if "\n".join(b).strip()]

    def _pack_section(self, section: str) -> list[str]:
        # First split into paragraphs, but keep bullet lists cohesive
        paras = [p.strip() for p in section.split("\n\n") if p.strip()]
        packed: list[str] = []
        buf: list[str] = []
        buf_len = 0

        def flush():
            nonlocal buf, buf_len
            if buf:
                packed.append("\n\n".join(buf).strip())
                buf = []
                buf_len = 0

        for p in paras:
            p2 = self._maybe_group_bullets(p)
            if not p2:
                continue

            candidate_len = buf_len + len(p2) + (2 if buf else 0)
            if candidate_len <= self._target:
                buf.append(p2)
                buf_len = candidate_len
                continue

            # If buffer already has content, flush and start new
            if buf:
                flush()

            # Large paragraph/list: split softly on sentences
            if len(p2) > self._max:
                packed.extend(self._split_large(p2))
            else:
                buf.append(p2)
                buf_len = len(p2)

        flush()
        return packed

    def _maybe_group_bullets(self, paragraph: str) -> str:
        # If this is a bullet list spread across newlines, keep as-is.
        lines = paragraph.split("\n")
        bullet_lines = sum(1 for l in lines if _BULLET_RE.match(l.strip()))
        if bullet_lines >= 2:
            return "\n".join(l.rstrip() for l in lines).strip()
        return paragraph.strip()

    def _split_large(self, text: str) -> list[str]:
        # Prefer splitting on blank lines/sentence boundaries while keeping length bounded.
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(])", text)
        out: list[str] = []
        cur: list[str] = []
        cur_len = 0
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            cand = cur_len + len(s) + (1 if cur else 0)
            if cand <= self._max:
                cur.append(s)
                cur_len = cand
            else:
                if cur:
                    out.append(" ".join(cur).strip())
                cur = [s]
                cur_len = len(s)
        if cur:
            out.append(" ".join(cur).strip())
        return out

