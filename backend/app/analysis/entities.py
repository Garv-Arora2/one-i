"""Lightweight entity detection.

A deliberately simple, explainable heuristic: sequences of capitalised words
that are not ordinary sentence-initial words. No statistical NER model is used,
so behaviour is fully deterministic and inspectable.
"""

from __future__ import annotations

import re
from collections import Counter

from app.analysis.textutils import STOPWORDS, clean_text, split_sentences

_CAPITALISED_RUN = re.compile(
    r"\b([A-Z][a-zA-Z'&.\-]+(?:\s+(?:of|for|and|the|de|van)\s+[A-Z][a-zA-Z'&.\-]+|\s+[A-Z][a-zA-Z'&.\-]+)*)"
)
_LOCATION_PREPOSITION = re.compile(
    r"\b(?:in|at|near|from|across|outside|around)\s+([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+){0,2})"
)

# Words that start sentences but are not entities.
_COMMON_SENTENCE_STARTERS = frozenset(
    """
the a an this that these those it he she they we i but and or however meanwhile after before
when while during since although though because if as on in at for from by with about over
under between more most many some several few no not there here who what which why how
""".split()
)

_ENTITY_STOPWORDS = frozenset(
    """
monday tuesday wednesday thursday friday saturday sunday january february march april may june
july august september october november december reuters ap afp update breaking
""".split()
)

_WEAK_TRAILING = frozenset({"of", "for", "and", "the", "de", "van"})


def _clean_candidate(candidate: str) -> str:
    words = candidate.split()
    while words and words[-1].lower() in _WEAK_TRAILING:
        words.pop()
    return " ".join(words).strip(" .,'-")


def extract_entities(text: str, *, min_length: int = 3) -> Counter[str]:
    """Count candidate named entities in a block of text."""
    counts: Counter[str] = Counter()
    for sentence in split_sentences(text):
        for index, match in enumerate(_CAPITALISED_RUN.finditer(sentence)):
            candidate = _clean_candidate(match.group(1))
            if len(candidate) < min_length:
                continue
            lowered = candidate.lower()
            if lowered in _ENTITY_STOPWORDS:
                continue
            single_word = " " not in candidate
            # A single capitalised word at the very start of a sentence is
            # usually just sentence case, not an entity.
            if single_word and match.start() == 0 and lowered in _COMMON_SENTENCE_STARTERS:
                continue
            if single_word and (lowered in STOPWORDS or lowered in _COMMON_SENTENCE_STARTERS):
                continue
            counts[candidate] += 1
            _ = index
    return counts


def entity_set(text: str) -> set[str]:
    """Lower-cased entity strings, useful for overlap comparisons."""
    return {entity.lower() for entity in extract_entities(text)}


def top_entities(text: str, limit: int = 5) -> list[str]:
    counts = extract_entities(text)
    return [entity for entity, _ in counts.most_common(limit)]


def detect_locations(text: str, *, min_mentions: int = 1) -> list[str]:
    """Candidate places, found through prepositions ("in X", "near X")."""
    counts: Counter[str] = Counter()
    for match in _LOCATION_PREPOSITION.finditer(clean_text(text)):
        candidate = _clean_candidate(match.group(1))
        if len(candidate) < 3 or candidate.lower() in _ENTITY_STOPWORDS:
            continue
        counts[candidate] += 1
    return [name for name, count in counts.most_common() if count >= min_mentions]
