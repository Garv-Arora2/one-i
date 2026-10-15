"""Wording comparison.

For a single development, find the passage each article used to describe it and
show where the descriptions genuinely differ. Differences are grouped by the
aspects that matter: responsibility, action, severity, certainty and evaluation.

The original wording is always preserved, always shown with its surrounding
sentences, and never reduced to a score. Nothing here judges an outlet.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.analysis.lexicons import ASPECT_LEXICONS, in_neutral_compound, synonym_key
from app.analysis.textutils import (
    build_tfidf_matrix,
    clean_text,
    cosine_matrix,
    normalize_title,
    split_sentences,
    tokenize,
)
from app.analysis.thresholds import WORDING, WordingConfig


@dataclass(frozen=True)
class Passage:
    article_id: int
    source_id: int
    source_name: str
    text: str
    surrounding_text: str
    similarity: float
    markers: dict[str, list[str]] = field(default_factory=dict)

    @property
    def aspects(self) -> list[str]:
        return sorted(aspect for aspect, words in self.markers.items() if words)


@dataclass
class WordingComparison:
    topic: str
    development_id: int | None
    passages: list[Passage]
    differing_aspects: list[str]

    @property
    def is_meaningful(self) -> bool:
        return bool(self.differing_aspects) and len(self.passages) >= 2


def extract_markers(text: str) -> dict[str, list[str]]:
    """Words in `text` that carry each wording aspect.

    A marker word inside a neutral compound ("strike" in "strike group")
    names a thing, it does not frame it, so it is left out.
    """
    tokens = tokenize(text)
    lowered = text.lower()
    found: dict[str, list[str]] = {}
    for aspect, lexicon in ASPECT_LEXICONS.items():
        matches = sorted(
            {
                token
                for token in tokens
                if token in lexicon and not in_neutral_compound(token, lowered)
            }
        )
        if matches:
            found[aspect] = matches
    return found


def _with_surrounding(sentences: list[str], index: int) -> str:
    start = max(0, index - 1)
    end = min(len(sentences), index + 2)
    return " ".join(sentences[start:end])


def select_passages(
    development_text: str,
    articles: list[tuple[int, int, str, str, str]],
    config: WordingConfig = WORDING,
) -> list[Passage]:
    """Best-matching passage per article.

    `articles` items are `(article_id, source_id, source_name, title, content)`.
    Articles with no sufficiently similar passage are skipped rather than
    forced into the comparison.
    """
    documents = [development_text]
    index_map: list[tuple[int, int, str, list[str], int, bool]] = []
    for article_id, source_id, source_name, title, content in articles:
        title_text = normalize_title(title)
        body = clean_text(content)
        if body.lower().startswith(title_text.lower()):
            combined = body
        else:
            combined = f"{title_text}. {body}".strip()
        # RSS items are a headline plus a short blurb. Splitting them into
        # sentences drops the framing in the title ("turns deadly") in favour
        # of the more similar body sentence, so short items stay whole.
        short_item = len(combined) <= 320
        if short_item:
            sentences = [combined] if len(combined) >= 20 else []
        else:
            sentences = [
                sentence for sentence in split_sentences(combined) if len(sentence) >= 20
            ]
        if not sentences:
            continue
        start = len(documents)
        documents.extend(sentences)
        index_map.append((article_id, source_id, source_name, sentences, start, short_item))

    matrix, _ = build_tfidf_matrix(documents)
    if matrix is None:
        return []
    similarities = cosine_matrix(matrix)
    if similarities.size == 0:
        return []

    passages: list[Passage] = []
    for article_id, source_id, source_name, sentences, start, short_item in index_map:
        best_position, best_similarity = -1, 0.0
        for offset in range(len(sentences)):
            similarity = float(similarities[0][start + offset])
            if similarity > best_similarity:
                best_position, best_similarity = offset, similarity
        floor = config.short_item_min_similarity if short_item else config.comparable_min_similarity
        if best_position < 0 or best_similarity < floor:
            continue
        text = sentences[best_position]
        passages.append(
            Passage(
                article_id=article_id,
                source_id=source_id,
                source_name=source_name,
                text=text,
                surrounding_text=_with_surrounding(sentences, best_position),
                similarity=round(best_similarity, 4),
                markers=extract_markers(text),
            )
        )
    return passages


def _aspect_differs(passages: list[Passage], aspect: str) -> bool:
    """True when sources used materially different words for this aspect.

    Synonyms collapse to one key first, so "halted" and "suspended" do not
    count as a difference.
    """
    signatures: list[frozenset[str]] = []
    for passage in passages:
        words = passage.markers.get(aspect, [])
        signatures.append(frozenset(synonym_key(word) for word in words))
    non_empty = [signature for signature in signatures if signature]
    if not non_empty:
        return False
    if len(non_empty) < len(signatures):
        # Some sources used this kind of language and others did not.
        return True
    return any(signature != non_empty[0] for signature in non_empty[1:])


def compare_wording(
    topic: str,
    passages: list[Passage],
    development_id: int | None = None,
    config: WordingConfig = WORDING,
) -> WordingComparison | None:
    """Build a wording comparison, or None when there is nothing to show."""
    distinct_sources = {passage.source_id for passage in passages}
    if len(distinct_sources) < config.min_sources_for_comparison:
        return None

    matrix, _ = build_tfidf_matrix([passage.text for passage in passages])
    similarities = cosine_matrix(matrix)
    if similarities.size:
        off_diagonal = [
            float(similarities[i][j])
            for i in range(len(passages))
            for j in range(i + 1, len(passages))
        ]
        # Near-identical passages (often syndicated wire copy) are not a
        # meaningful difference.
        if off_diagonal and min(off_diagonal) > config.identical_max_similarity:
            return None

    differing = [aspect for aspect in ASPECT_LEXICONS if _aspect_differs(passages, aspect)]
    comparison = WordingComparison(
        topic=topic,
        development_id=development_id,
        passages=sorted(passages, key=lambda passage: passage.source_name),
        differing_aspects=differing,
    )
    return comparison if comparison.is_meaningful else None
