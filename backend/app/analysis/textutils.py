"""Shared text handling: cleaning, tokenising, sentences, similarity.

Deliberately dependency-light: regular expressions, a fixed stopword list and
scikit-learn's TF-IDF. No language models are used anywhere in ONE I.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

STOPWORDS: frozenset[str] = frozenset(
    """
a about above after again against all also am an and any are aren as at be because been
before being below between both but by can cannot could couldn did didn do does doesn doing
don down during each few for from further had hadn has hasn have haven having he her here
hers herself him himself his how i if in into is isn it its itself just me more most must my
myself no nor not now of off on once only or other ought our ours ourselves out over own s
same shan she should shouldn so some such t than that the their theirs them themselves then
there these they this those through to too under until up very was wasn we were weren what
when where which while who whom why will with won would wouldn you your yours yourself
yourselves said says say told according reported report reports new news one two three
""".split()
)

_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")
_TOKEN = re.compile(r"[A-Za-z][A-Za-z'\-]+")
# A sentence may end inside a closing quote: `challenging." 4 dead` is two sentences.
_SENTENCE_SPLIT = re.compile(
    r"(?:(?<=[.!?])|(?<=[.!?][\"'\u201d\u2019]))\s+(?=[\"'\u201c(]?[A-Z0-9])"
)
_ABBREVIATIONS = (
    "Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "St.", "Inc.", "Ltd.", "No.", "vs.", "U.S.", "U.N.",
    # Month abbreviations: "Oct. 7" must stay one date, not end a sentence.
    "Jan.", "Feb.", "Mar.", "Apr.", "Jun.", "Jul.", "Aug.", "Sept.", "Sep.", "Oct.", "Nov.", "Dec.",
)
_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "ref",
    "cmpid",
}


def strip_html(text: str) -> str:
    return _HTML_TAG.sub(" ", text or "")


def clean_text(text: str | None) -> str:
    """Normalise unicode, strip markup and collapse whitespace."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("\u00a0", " ")
    # Invisible format characters (U+2060 word joiner, zero-width spaces) slip
    # in from CMS headlines: strip them, but keep real whitespace for now so
    # the collapse below still separates words.
    normalized = "".join(
        char
        for char in normalized
        if unicodedata.category(char) != "Cf"
        and not (unicodedata.category(char) == "Cc" and char not in " \t\n\r")
    )
    return _WHITESPACE.sub(" ", strip_html(normalized)).strip()


def normalize_title(title: str | None) -> str:
    cleaned = clean_text(title)
    # Drop a trailing " - Outlet Name" / " | Outlet Name" suffix.
    cleaned = re.sub(r"\s+[-|\u2013\u2014]\s+[^-|\u2013\u2014]{2,40}$", "", cleaned)
    # GDELT tokenises headlines: "U . S . President", "( October 2 , 2020 )".
    cleaned = re.sub(r"\s+([,.;:!?)\]])", r"\1", cleaned)
    cleaned = re.sub(r"([(\[])\s+", r"\1", cleaned)
    cleaned = re.sub(r"\b([A-Z])\. (?=[A-Z]\.)", r"\1.", cleaned)
    return cleaned.strip()


TOPIC_SEPARATOR = " › "
CRUMB_SEPARATOR = " — "


def strip_topic_breadcrumb(content: str) -> str:
    """Drop the "Section › Topic — " prefix the current-events inlet stores.

    The breadcrumb helps group related stories, but it is Wikipedia's
    filing, not the outlet's words, so it must never be quoted as reporting.
    """
    head, separator, rest = (content or "").partition(CRUMB_SEPARATOR)
    if separator and TOPIC_SEPARATOR in head and len(head) <= 300:
        return rest
    return content


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in _TOKEN.finditer(text or "")]


def content_tokens(text: str) -> list[str]:
    return [token for token in tokenize(text) if len(token) > 2 and token not in STOPWORDS]


def token_set(text: str) -> set[str]:
    return set(content_tokens(text))


def split_sentences(text: str) -> list[str]:
    """Split text into sentences, protecting a small set of abbreviations."""
    cleaned = clean_text(text)
    if not cleaned:
        return []
    guarded = cleaned
    for index, abbreviation in enumerate(_ABBREVIATIONS):
        guarded = guarded.replace(abbreviation, f"\x00{index}\x00")
    parts = _SENTENCE_SPLIT.split(guarded)
    sentences: list[str] = []
    for part in parts:
        restored = part
        for index, abbreviation in enumerate(_ABBREVIATIONS):
            restored = restored.replace(f"\x00{index}\x00", abbreviation)
        restored = restored.strip()
        if restored:
            sentences.append(restored)
    return sentences


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def overlap_ratio(needles: set[str], haystack: set[str]) -> float:
    """Share of `needles` present in `haystack` (asymmetric on purpose)."""
    if not needles:
        return 0.0
    return len(needles & haystack) / len(needles)


def content_fingerprint(title: str | None, body: str | None) -> str:
    """Stable hash of the meaningful words of an article, for deduplication."""
    tokens = content_tokens(f"{normalize_title(title)} {clean_text(body)}")
    if not tokens:
        return ""
    digest_source = " ".join(tokens[:400])
    return hashlib.sha256(digest_source.encode("utf-8")).hexdigest()


def canonicalize_url(url: str | None) -> str:
    """Remove tracking parameters and normalise the host for duplicate URLs."""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    if not parts.scheme and not parts.netloc:
        return url.strip()
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=False)
        if key.lower() not in _TRACKING_PARAMS
    ]
    query_string = "&".join(f"{key}={value}" for key, value in sorted(query))
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower() or "https", host, path, query_string, ""))


def domain_of(url: str | None) -> str:
    if not url:
        return ""
    host = urlsplit(url if "//" in url else f"https://{url}").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def build_tfidf_matrix(documents: list[str], *, min_df: int = 1, ngram_max: int = 2):
    """Fit a TF-IDF matrix over the given documents.

    Returns `(matrix, vectorizer)`; the matrix is empty when there is nothing
    usable to vectorise.
    """
    usable = [document for document in documents if document.strip()]
    if not usable:
        return None, None
    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words=list(STOPWORDS),
        ngram_range=(1, ngram_max),
        min_df=min_df,
        sublinear_tf=True,
        token_pattern=r"(?u)\b[A-Za-z][A-Za-z'\-]+\b",
    )
    try:
        matrix = vectorizer.fit_transform(documents)
    except ValueError:
        return None, None
    if matrix.shape[1] == 0:
        return None, None
    return matrix, vectorizer


def cosine_matrix(matrix) -> np.ndarray:
    if matrix is None:
        return np.zeros((0, 0))
    return cosine_similarity(matrix)


def cosine_between(matrix, left_index: int, right_index: int) -> float:
    if matrix is None:
        return 0.0
    value = cosine_similarity(matrix[left_index], matrix[right_index])[0][0]
    return float(max(0.0, min(1.0, value)))


def cosine_similarity_rows(matrix, row_index: int, candidate_rows: list[int]) -> float:
    """Highest cosine similarity between one row and a set of other rows."""
    if matrix is None or not candidate_rows:
        return 0.0
    scores = cosine_similarity(matrix[row_index], matrix[candidate_rows])
    if scores.size == 0:
        return 0.0
    return float(max(0.0, min(1.0, scores.max())))


def text_similarity(left: str, right: str) -> float:
    """Cosine similarity between two standalone strings."""
    matrix, _ = build_tfidf_matrix([left, right])
    if matrix is None or matrix.shape[0] < 2:
        return 0.0
    return cosine_between(matrix, 0, 1)


def top_terms(matrix, vectorizer, row_indices: list[int], limit: int) -> list[str]:
    """Highest-weighted TF-IDF terms across the given rows."""
    if matrix is None or vectorizer is None or not row_indices:
        return []
    scores = np.asarray(matrix[row_indices].sum(axis=0)).ravel()
    if not scores.any():
        return []
    feature_names = vectorizer.get_feature_names_out()
    ranked = np.argsort(-scores)
    terms: list[str] = []
    for index in ranked:
        if scores[index] <= 0:
            break
        term = str(feature_names[index])
        if term in STOPWORDS:
            continue
        terms.append(term)
        if len(terms) >= limit:
            break
    return terms


def slugify(text: str, max_length: int = 80) -> str:
    ascii_text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")
    return slug or "event"


def truncate_words(text: str, limit: int) -> str:
    words = text.split()
    if len(words) <= limit:
        return text
    return " ".join(words[:limit]).rstrip(",;:") + "…"


def short_title(text: str, limit: int = 14) -> str:
    """One-line summary of a development for comparison views.

    The coverage grid compares rows, so a 26-word title stretches every row
    to five lines. Prefer cutting at a clause boundary (comma, semicolon,
    colon) in the second half of the window over cutting mid-phrase; the
    full title is always kept alongside for the detail views.
    """
    words = (text or "").split()
    if len(words) <= limit:
        return text
    cut = limit
    for index in range(limit - 1, max(limit // 2, 1), -1):
        if words[index].endswith((",", ";", ":")):
            cut = index + 1
            break
    return " ".join(words[:cut]).rstrip(",;:") + "…"
