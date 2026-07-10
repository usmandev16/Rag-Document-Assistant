import re


def _split_into_paragraphs(text: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in paragraphs if p.strip()]


def _split_long_paragraph(paragraph: str, chunk_size: int) -> list[str]:
    """A paragraph that alone exceeds chunk_size gets split on sentence
    boundaries instead, so we still avoid cutting a sentence in half."""
    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
    pieces: list[str] = []
    current = ""

    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            pieces.append(current)

        if len(sentence) > chunk_size:
            # A single sentence longer than chunk_size: hard-split it.
            for i in range(0, len(sentence), chunk_size):
                pieces.append(sentence[i:i + chunk_size])
            current = ""
        else:
            current = sentence

    if current:
        pieces.append(current)
    return pieces


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """Split text into ~chunk_size-character chunks.

    Paragraphs are kept whole and packed together until adding the next one
    would exceed chunk_size; only a paragraph longer than chunk_size on its
    own gets split (on sentence boundaries). Each chunk after the first is
    prefixed with the trailing `overlap` characters of the previous chunk so
    a fact split across the seam is still visible in both chunks.
    """
    paragraphs = _split_into_paragraphs(text)
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph

        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)

        if len(paragraph) > chunk_size:
            sub_pieces = _split_long_paragraph(paragraph, chunk_size)
            chunks.extend(sub_pieces[:-1])
            current = sub_pieces[-1] if sub_pieces else ""
        else:
            current = paragraph

    if current:
        chunks.append(current)

    if overlap <= 0 or len(chunks) < 2:
        return chunks

    overlapped = [chunks[0]]
    for i in range(1, len(chunks)):
        tail = chunks[i - 1][-overlap:]
        overlapped.append(f"{tail}\n\n{chunks[i]}" if tail else chunks[i])
    return overlapped
