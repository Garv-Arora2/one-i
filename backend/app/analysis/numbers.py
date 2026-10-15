"""Numerical claim extraction and comparison.

Two numbers are only ever compared when their subject, unit, value kind and
time period match. Percentages, percentage points and percentage changes are
kept strictly apart, because "30% vs 20%" is a ten *percentage point*
difference, not a ten percent one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.analysis.entities import detect_locations
from app.analysis.lexicons import CHANGE_VERBS
from app.analysis.textutils import (
    STOPWORDS,
    clean_text,
    normalize_title,
    split_sentences,
    tokenize,
)
from app.analysis.thresholds import NUMBERS, NumberConfig
from app.models.enums import ValueKind

_SCALES: dict[str, float] = {
    "thousand": 1e3,
    "k": 1e3,
    "million": 1e6,
    "m": 1e6,
    "bn": 1e9,
    "billion": 1e9,
    "trillion": 1e12,
}

_CURRENCY_SYMBOLS: dict[str, str] = {"$": "USD", "£": "GBP", "€": "EUR", "₹": "INR"}
_CURRENCY_WORDS: dict[str, str] = {
    "dollars": "USD",
    "dollar": "USD",
    "pounds": "GBP",
    "euros": "EUR",
    "rupees": "INR",
}

_COUNT_UNITS = frozenset(
    """
people person persons residents inhabitants workers employees staff patients passengers
students families households homes houses buildings schools hospitals jobs cases deaths
fatalities injuries casualties tonnes tons kilograms litres liters gallons barrels
kilometres kilometers km miles metres meters acres hectares days weeks months years hours
minutes flights vehicles trucks shops businesses
""".split()
)

# Documented normalisation so equivalent subjects group together.
SUBJECT_SYNONYMS: dict[str, str] = {
    "people": "person",
    "persons": "person",
    "residents": "person",
    "resident": "person",
    "inhabitants": "person",
    "individuals": "person",
    "evacuees": "person",
    "villagers": "person",
    "deaths": "death",
    "fatalities": "death",
    "killed": "death",
    "dead": "death",
    "injuries": "injury",
    "injured": "injury",
    "hurt": "injury",
    "wounded": "injury",
    "homes": "home",
    "houses": "home",
    "households": "home",
    "jobs": "job",
    "workers": "worker",
    "employees": "worker",
    "staff": "worker",
    "tons": "tonne",
    "tonnes": "tonne",
    "litres": "litre",
    "liters": "litre",
}

# Spelled-out numbers ("Twelve people are killed") are only kept as casualty
# counts. "One" is left out: "one of the", "one side" are rarely a count.
_WORD_UNITS: dict[str, int] = {
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_WORD_TENS: dict[str, int] = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_DIGIT_WORDS = {"one": 1, **{word: value for word, value in _WORD_UNITS.items() if value < 10}}
_SPELLED_NUMBER = (
    r"(?<![A-Za-z-])(?:(?:" + "|".join(_WORD_TENS) + r")(?:[-\s](?:" + "|".join(_DIGIT_WORDS) + r"))?"
    r"|" + "|".join(sorted(_WORD_UNITS, key=len, reverse=True)) + r")(?![A-Za-z])"
)

# Scale letters must be their own word. Without a boundary, the "k" in
# "21 killed" is read as thousands and the death count becomes 21,000.
_NUMBER_PATTERN = re.compile(
    r"(?P<currency>[$£€₹])?\s?"
    r"(?P<value>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|" + _SPELLED_NUMBER + r")\s*"
    r"(?:(?P<scale>thousand|million|billion|trillion|bn|k|m)\b)?\s*"
    r"(?P<unit>percentage\s+points?|per\s+cent|percent|%|"
    + "|".join(sorted(_CURRENCY_WORDS)) + r"|"
    + "|".join(sorted(_COUNT_UNITS)) + r")?",
    re.IGNORECASE,
)

_DEATH_MARKERS = frozenset(
    """
kill kills killed killing dead death deaths died die dying fatalities fatality
""".split()
)
_INJURY_MARKERS = frozenset(
    """
injured injuring injures injury injuries wounded wounding wounds hurt
""".split()
)
# Who was hit is part of the claim: "30 soldiers killed" and "30 civilians
# killed" are different figures, never one disagreement.
_VICTIM_GROUPS: dict[str, str] = {
    "civilian": "civilian", "civilians": "civilian",
    "soldier": "soldier", "soldiers": "soldier", "troops": "soldier", "servicemen": "soldier",
    "militant": "militant", "militants": "militant", "fighters": "militant", "combatants": "combatant",
    "child": "child", "children": "child", "minors": "child",
    "woman": "woman", "women": "woman",
    "police": "police", "policemen": "police", "officers": "police",
    "journalists": "journalist", "hostages": "hostage", "rescuers": "rescuer",
    "medics": "medic", "paramedics": "medic", "migrants": "migrant", "refugees": "refugee",
    "prisoners": "prisoner", "students": "student", "pilgrims": "pilgrim",
}
_DURATION_WORDS = frozenset(
    "second seconds minute minutes hour hours day days week weeks month months year years".split()
)
_AGE_BEFORE = re.compile(r"\b(?:at|aged|age)\s*$", re.IGNORECASE)
_AUXILIARIES = frozenset(
    """
are were was is have has had been being reportedly confirmed also later
""".split()
)
_NEAR_NUMBER_FILLER = frozenset(
    """
at least some about over around nearly more than almost approximately
""".split()
)

_MONTHS = frozenset(
    """
january february march april may june july august september october november december
jan feb mar apr jun jul aug sep sept oct nov dec
""".split()
)

# Narrative day references ("on Tuesday") are deliberately not treated as time
# periods: they say when something was reported, not what period a figure covers.
_TIME_PERIOD_PATTERNS = (
    r"year[-\s]on[-\s]year",
    r"in the (?:first|second|third|fourth) quarter(?: of \d{4})?",
    r"over the (?:past|last) \w+ (?:days|weeks|months|years)",
    r"(?:in|since|during|by) \d{4}",
    r"(?:last|this|next) (?:year|month|week|quarter|night)",
    r"per (?:day|week|month|year|hour)",
    # Figures tied to another moment ("a day after a strike killed 13", "as of
    # July 20", "the initial toll") must not be set against today's figure.
    r"(?:a|one|two|three|\d+) (?:day|week)s? (?:after|before|earlier)",
    r"the (?:previous|day before|day after)",
    r"earlier this (?:week|month)",
    r"over the weekend",
    r"before the war",
    r"initial(?:ly)?(?: toll| figure| count)?",
    r"revised (?:its|the) (?:toll|figure|count)",
    r"as of (?:" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\.? \d{1,2}",
    r"since (?:the (?:beginning|start) of )?(?:" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\b",
)
_TIME_PERIOD = re.compile("|".join(f"({pattern})" for pattern in _TIME_PERIOD_PATTERNS), re.IGNORECASE)
# A war's running total ("150,000 killed since the war began") is a different
# figure from one strike's toll. All phrasings share one label so totals only
# meet other totals.
_WAR_TOTAL = re.compile(
    r"since the (?:start of the |beginning of the )?(?:war|conflict|fighting|invasion|offensive)\b"
    r"|since (?:october 7|7 october)\b|so far in the war",
    re.IGNORECASE,
)
WAR_TOTAL_PERIOD = "since the war began"


@dataclass(frozen=True)
class NumberObservationCandidate:
    article_id: int
    source_id: int
    value: float
    unit: str | None
    value_kind: ValueKind
    subject: str
    subject_tokens: tuple[str, ...]
    time_period: str | None
    context: str
    coarse_key: str
    comparison_key: str = ""


@dataclass
class NumberComparison:
    comparison_key: str
    subject: str
    unit: str | None
    value_kind: ValueKind
    time_period: str | None
    observations: list[NumberObservationCandidate] = field(default_factory=list)
    lowest: float = 0.0
    highest: float = 0.0
    difference: float = 0.0
    difference_unit: str = ""
    relative_difference_percent: float | None = None
    sources_agree: bool = True

    @property
    def distinct_source_count(self) -> int:
        return len({observation.source_id for observation in self.observations})


def simple_stem(word: str) -> str:
    """Very small suffix stripper, enough to align plural/past-tense subjects."""
    lowered = SUBJECT_SYNONYMS.get(word.lower(), word.lower())
    if len(lowered) > 4 and lowered.endswith("ies"):
        return lowered[:-3] + "y"
    if len(lowered) > 4 and lowered.endswith("es") and not lowered.endswith("ses"):
        return lowered[:-2]
    if len(lowered) > 3 and lowered.endswith("s") and not lowered.endswith("ss"):
        return lowered[:-1]
    if len(lowered) > 5 and lowered.endswith("ed"):
        return lowered[:-2]
    if len(lowered) > 5 and lowered.endswith("ing"):
        return lowered[:-3]
    return lowered


def _is_spelled(raw_value: str) -> bool:
    return not raw_value[0].isdigit()


def _spelled_value(raw_value: str) -> int:
    parts = re.split(r"[-\s]+", raw_value.lower())
    if parts[0] in _WORD_TENS:
        return _WORD_TENS[parts[0]] + (_DIGIT_WORDS[parts[1]] if len(parts) > 1 else 0)
    return _WORD_UNITS[parts[0]]


def _parse_value(raw_value: str, scale: str | None) -> float:
    if _is_spelled(raw_value):
        value = float(_spelled_value(raw_value))
    else:
        value = float(raw_value.replace(",", ""))
    if scale:
        value *= _SCALES[scale.lower()]
    return value


def _classify(
    currency: str | None, unit: str | None, sentence_tokens: list[str], number_position: int
) -> tuple[ValueKind, str | None]:
    normalized_unit = re.sub(r"\s+", " ", unit.lower()).strip() if unit else None
    if normalized_unit and normalized_unit.startswith("percentage point"):
        return ValueKind.PERCENTAGE_POINT, "percentage points"
    if normalized_unit in {"%", "percent", "per cent"}:
        window = sentence_tokens[max(0, number_position - 5) : number_position]
        if any(token in CHANGE_VERBS for token in window):
            return ValueKind.PERCENT_CHANGE, "%"
        return ValueKind.PERCENT, "%"
    if currency:
        return ValueKind.CURRENCY, _CURRENCY_SYMBOLS[currency]
    if normalized_unit in _CURRENCY_WORDS:
        return ValueKind.CURRENCY, _CURRENCY_WORDS[normalized_unit]
    if normalized_unit in _COUNT_UNITS:
        return ValueKind.COUNT, normalized_unit
    return ValueKind.COUNT, None


def _casualty_marker(token: str) -> str | None:
    if token in _DEATH_MARKERS:
        return "death"
    if token in _INJURY_MARKERS:
        return "injury"
    return None


def _casualty_count(sentence: str, match: re.Match[str]) -> tuple[str, str] | None:
    """("death" or "injury", victim group) when the number is a casualty count.

    The words after the number decide first, so in "21 killed, 45 are
    injured" the 45 is an injury count even though "killed" precedes it.
    "21 killed", "62 combatants dead", "killing at least 20 people" and "the
    death toll rose to 22" match. "killing people from 6 displaced families"
    does not: 6 is next to neither a casualty word nor a toll.
    """
    # "died six days later" is a duration and "killed at 25" an age.
    if _AGE_BEFORE.search(sentence[: match.start("value")]):
        return None
    if (match.group("unit") or "").lower() in _DURATION_WORDS:
        return None
    skip = _NEAR_NUMBER_FILLER | _AUXILIARIES
    post = [token for token in tokenize(sentence[match.end() :]) if token not in skip][:3]
    if post and post[0] in _DURATION_WORDS:
        return None
    pre = [token for token in tokenize(sentence[: match.start()]) if token not in _NEAR_NUMBER_FILLER]

    group = _VICTIM_GROUPS.get(post[0], "person") if post else "person"
    if post and (kind := _casualty_marker(post[0])):
        return kind, "person"
    if len(post) >= 2 and post[0] not in STOPWORDS and (kind := _casualty_marker(post[1])):
        return kind, group
    if pre and (kind := _casualty_marker(pre[-1])):
        return kind, group
    # "the death toll from the attack rose to 22", "the toll stands at 30".
    if pre and pre[-1] in {"to", "at"} and "toll" in pre[-8:]:
        return "death", group
    return None


def _casualty_subject(kind: str, group: str) -> tuple[str, tuple[str, ...]]:
    label = {"person": "people", "child": "children", "woman": "women", "police": "police"}.get(
        group, f"{group}s"
    )
    verb = "killed" if kind == "death" else "injured"
    return f"{label} {verb}", (kind, group)


def _subject_for(sentence: str, match: re.Match[str], config: NumberConfig) -> tuple[str, tuple[str, ...]]:
    """Words describing what the number counts, taken after then before it."""
    after = [
        token
        for token in tokenize(sentence[match.end() :])
        if token not in STOPWORDS and len(token) > 2
    ]
    unit = match.group("unit")
    words = list(after)
    if unit:
        unit_tokens = [token for token in tokenize(unit) if token not in STOPWORDS]
        words = unit_tokens + [word for word in words if word not in unit_tokens]
    if len(words) < config.subject_key_tokens:
        before = [
            token
            for token in tokenize(sentence[: match.start()])
            if token not in STOPWORDS and len(token) > 2
        ]
        # What follows the number is what it counts, so it leads the subject;
        # earlier words only add context.
        words = words + [word for word in before[-config.subject_tokens :] if word not in words]
    selected = words[: config.subject_tokens]
    subject = " ".join(selected)
    key_tokens = tuple(sorted({simple_stem(word) for word in selected[: config.subject_key_tokens]}))
    return subject, key_tokens


def _time_period_for(sentence: str) -> str | None:
    if _WAR_TOTAL.search(sentence):
        return WAR_TOTAL_PERIOD
    match = _TIME_PERIOD.search(sentence)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(0).lower()).strip()


def _is_bare_year(match: re.Match[str], value: float) -> bool:
    return (
        match.group("currency") is None
        and match.group("scale") is None
        and match.group("unit") is None
        and value.is_integer()
        and 1900 <= value <= 2100
        and "," not in match.group("value")
        and "." not in match.group("value")
    )


def _is_clock_time(sentence: str, match: re.Match[str]) -> bool:
    """True when the digits are part of a time of day such as "05:00"."""
    if sentence[match.start() - 1 : match.start()] == ":":
        return True
    return bool(re.match(r":\d{2}", sentence[match.end() : match.end() + 3]))


def _is_calendar_date(sentence: str, match: re.Match[str]) -> bool:
    """True for "15 February" or "February 15": a date, not a measurement."""
    if match.group("currency") or match.group("scale") or match.group("unit"):
        return False
    following = tokenize(sentence[match.end() : match.end() + 20])
    if following and following[0] in _MONTHS:
        return True
    preceding = tokenize(sentence[: match.start()])
    return bool(preceding) and preceding[-1] in _MONTHS


_ORDINAL_SUFFIX = re.compile(r"(?:st|nd|rd|th)\b", re.IGNORECASE)
_SCORE_BEFORE = re.compile(r"\d\s?[–—-]\s?$")
_SCORE_AFTER = re.compile(r"^\s?[–—-]\s?\d")
# Words that turn the following number into a label, not an amount:
# "round of 32", "top 10", "Flight 370", "Article 5".
_LABEL_WORDS = frozenset(
    """
round last top no number game match stage group phase level grade flight route
article section chapter page episode season term category
""".split()
)
_AGE_SUFFIX = re.compile(r"[-\s]years?[-\s]old\b", re.IGNORECASE)


def _is_ordinal(sentence: str, match: re.Match[str]) -> bool:
    """"1,000th match" or "32nd" is a position in a sequence, not an amount."""
    return bool(_ORDINAL_SUFFIX.match(sentence, match.end("value")))


_INCREMENT_WORDS = frozenset({"more", "additional", "further", "extra"})
# Longer "sentences" are captions, bylines or menus glued together, and a
# quote containing a link is page furniture; neither is a citable claim.
_MAX_SENTENCE_CHARACTERS = 400


def _is_unclean_sentence(sentence: str) -> bool:
    return len(sentence) > _MAX_SENTENCE_CHARACTERS or "http" in sentence or "pic.twitter" in sentence


def _is_increment(sentence: str, match: re.Match[str]) -> bool:
    """"30 more bodies" adds to an earlier total; it is not a total itself."""
    following = tokenize(sentence[match.end() :])
    return bool(following) and following[0] in _INCREMENT_WORDS


def _is_age(sentence: str, match: re.Match[str]) -> bool:
    """"a 15-year-old" describes a person; two ages in one story are usually two people."""
    return bool(_AGE_SUFFIX.match(sentence, match.end("value")))


def _is_score_or_range(sentence: str, match: re.Match[str]) -> bool:
    """"4–3", "1-1" or "20-25": a scoreline or range, not one claimed figure."""
    start, end = match.start("value"), match.end("value")
    return bool(_SCORE_BEFORE.search(sentence[:start]) or _SCORE_AFTER.match(sentence[end:]))


def _is_label_number(sentence: str, match: re.Match[str]) -> bool:
    preceding = tokenize(sentence[: match.start()])
    if preceding and preceding[-1] in _LABEL_WORDS:
        return True
    return len(preceding) >= 2 and preceding[-2:] == ["round", "of"]


def _counts_a_following_noun(sentence: str, match: re.Match[str]) -> bool:
    """A unitless count must be directly followed by the thing it counts.

    "300 soldiers" counts soldiers. A bare "32" at the end of a clause names
    nothing, and pairing it by the words before it is how "round of 32" got
    compared with "the 1,000th World Cup match".
    """
    following = tokenize(sentence[match.end() :])
    following = [token for token in following if token not in _NEAR_NUMBER_FILLER]
    return bool(following) and following[0] not in STOPWORDS and len(following[0]) > 2


def extract_numbers(
    article_id: int,
    source_id: int,
    title: str,
    content: str,
    config: NumberConfig = NUMBERS,
) -> list[NumberObservationCandidate]:
    """Pull numerical claims out of one article, preserving their sentence."""
    text = f"{normalize_title(title)}. {clean_text(content)}"
    observations: list[NumberObservationCandidate] = []
    for sentence in split_sentences(text):
        if _is_unclean_sentence(sentence):
            continue
        sentence_tokens = tokenize(sentence)
        time_period = _time_period_for(sentence)
        for match in _NUMBER_PATTERN.finditer(sentence):
            value = _parse_value(match.group("value"), match.group("scale"))
            if (
                _is_bare_year(match, value)
                or _is_calendar_date(sentence, match)
                or _is_clock_time(sentence, match)
                or _is_ordinal(sentence, match)
                or _is_age(sentence, match)
                or _is_increment(sentence, match)
                or _is_score_or_range(sentence, match)
                or _is_label_number(sentence, match)
            ):
                continue
            prefix_tokens = tokenize(sentence[: match.start()])
            value_kind, unit = _classify(
                match.group("currency"), match.group("unit"), sentence_tokens, len(prefix_tokens)
            )
            subject, key_tokens = _subject_for(sentence, match, config)
            casualty = _casualty_count(sentence, match) if value_kind is ValueKind.COUNT else None
            if _is_spelled(match.group("value")) and casualty is None:
                continue
            if casualty:
                unit = "people"
                subject, key_tokens = _casualty_subject(*casualty)
            elif value_kind is ValueKind.COUNT and unit is None and not _counts_a_following_noun(
                sentence, match
            ):
                continue
            if not subject:
                continue
            coarse_key = f"{value_kind.value}|{unit or 'none'}|{time_period or 'unspecified'}"
            observations.append(
                NumberObservationCandidate(
                    article_id=article_id,
                    source_id=source_id,
                    value=value,
                    unit=unit,
                    value_kind=value_kind,
                    subject=subject,
                    subject_tokens=key_tokens,
                    time_period=time_period,
                    context=sentence,
                    coarse_key=coarse_key,
                )
            )
    return _dedupe_repeated_claims(observations)


def _dedupe_repeated_claims(
    observations: list[NumberObservationCandidate],
) -> list[NumberObservationCandidate]:
    """RSS items repeat the headline in the blurb; keep one claim per article."""
    unique: dict[tuple, NumberObservationCandidate] = {}
    for observation in observations:
        key = (
            observation.article_id,
            observation.value,
            observation.coarse_key,
            observation.subject_tokens,
        )
        existing = unique.get(key)
        if existing is None or len(observation.context) > len(existing.context):
            unique[key] = observation
    return list(unique.values())


def observations_about_the_event(
    observations: list[NumberObservationCandidate], documents: list[tuple[int, str]]
) -> list[NumberObservationCandidate]:
    """Drop figures whose sentence is about a place only one outlet mentions.

    Outlet pages carry other stories' headlines ("9 dead in Pennsylvania
    shooting" beside a Djibouti shipwreck). A place that a single outlet names
    is not a place this event is about. `documents` is (source_id, text).
    """
    sources_by_place: dict[str, set[int]] = {}
    for source_id, text in documents:
        for place in detect_locations(text):
            sources_by_place.setdefault(place.lower(), set()).add(source_id)

    def on_topic(observation: NumberObservationCandidate) -> bool:
        places = [place.lower() for place in detect_locations(observation.context)]
        return not places or any(len(sources_by_place.get(place, ())) >= 2 for place in places)

    return [observation for observation in observations if on_topic(observation)]


def _subject_similarity(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    left_set, right_set = set(left), set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


# Counts more than this many times apart are different quantities, not one
# disputed figure: "21 killed" in the collapse and "1,200 killed" on 7 October.
MAX_COUNT_RATIO = 3.0


def _same_magnitude(observation: NumberObservationCandidate, bucket: list[NumberObservationCandidate]) -> bool:
    if observation.value_kind not in {ValueKind.COUNT, ValueKind.CURRENCY}:
        return True
    values = [member.value for member in bucket] + [observation.value]
    low, high = min(values), max(values)
    return low > 0 and high / low <= MAX_COUNT_RATIO


def group_observations(
    observations: list[NumberObservationCandidate], min_subject_similarity: float = 0.5
) -> list[list[NumberObservationCandidate]]:
    """Cluster observations that describe the same claim.

    Same value kind, unit and time period first; then a subject-token overlap
    check so unrelated numbers never end up in the same comparison, and for
    counts a magnitude check so a background total is not read as the same
    figure.
    """
    by_coarse: dict[str, list[NumberObservationCandidate]] = {}
    for observation in observations:
        by_coarse.setdefault(observation.coarse_key, []).append(observation)

    groups: list[list[NumberObservationCandidate]] = []
    for coarse_group in by_coarse.values():
        buckets: list[list[NumberObservationCandidate]] = []
        for observation in coarse_group:
            placed = False
            for bucket in buckets:
                similarity = min(
                    _subject_similarity(observation.subject_tokens, member.subject_tokens)
                    for member in bucket
                )
                # Strictly more than half: "people rescued nepal" and "people
                # affected nepal" share two of four words but count different things.
                if similarity > min_subject_similarity and _same_magnitude(observation, bucket):
                    bucket.append(observation)
                    placed = True
                    break
            if not placed:
                buckets.append([observation])
        groups.extend(buckets)
    return groups


def _canonical_subject(group: list[NumberObservationCandidate]) -> str:
    counts: dict[str, int] = {}
    for observation in group:
        counts[observation.subject] = counts.get(observation.subject, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _difference_unit(value_kind: ValueKind, unit: str | None) -> str:
    if value_kind in {ValueKind.PERCENT, ValueKind.PERCENT_CHANGE, ValueKind.PERCENTAGE_POINT}:
        return "percentage points"
    if value_kind is ValueKind.CURRENCY:
        return unit or "currency"
    return unit or "units"


def compare_group(
    group: list[NumberObservationCandidate], config: NumberConfig = NUMBERS
) -> NumberComparison:
    """Turn one group of equivalent claims into a comparison."""
    values = [observation.value for observation in group]
    lowest, highest = min(values), max(values)
    difference = highest - lowest
    subject = _canonical_subject(group)
    first = group[0]
    tokens = "-".join(sorted({token for observation in group for token in observation.subject_tokens}))
    # The lowest value keeps two magnitude groups with the same subject apart.
    key = f"{first.coarse_key}#{tokens}@{lowest:g}"

    relative: float | None = None
    if first.value_kind in {ValueKind.COUNT, ValueKind.CURRENCY} and lowest > 0:
        relative = round(difference / lowest * 100, 2)

    tolerance = max(config.agreement_absolute_tolerance, abs(lowest) * config.agreement_relative_tolerance)
    return NumberComparison(
        comparison_key=key,
        subject=subject,
        unit=first.unit,
        value_kind=first.value_kind,
        time_period=first.time_period,
        observations=sorted(group, key=lambda observation: observation.value),
        lowest=lowest,
        highest=highest,
        difference=round(difference, 4),
        difference_unit=_difference_unit(first.value_kind, first.unit),
        relative_difference_percent=relative,
        sources_agree=difference <= tolerance,
    )


def is_internally_consistent(group: list[NumberObservationCandidate]) -> bool:
    """Reject a group where one article reports two different values.

    A single article stating "21 votes to 14" is not reporting one claim twice;
    it is reporting two different quantities, which means the grouping was
    wrong. Such a group is dropped rather than shown as a disagreement.
    """
    values_by_article: dict[int, set[float]] = {}
    for observation in group:
        values_by_article.setdefault(observation.article_id, set()).add(observation.value)
    return all(len(values) == 1 for values in values_by_article.values())


def _is_unanchored_change(group: list[NumberObservationCandidate]) -> bool:
    """"Brent gained 3%" with no stated period: each outlet may mean a different day."""
    return group[0].value_kind is ValueKind.PERCENT_CHANGE and group[0].time_period is None


def build_comparisons(
    observations: list[NumberObservationCandidate], min_sources: int = 2
) -> list[NumberComparison]:
    """All comparable claims reported by at least `min_sources` sources."""
    comparisons = [
        compare_group(group)
        for group in group_observations(observations)
        if is_internally_consistent(group) and not _is_unanchored_change(group)
    ]
    kept = [
        comparison
        for comparison in comparisons
        if comparison.distinct_source_count >= min_sources
    ]
    kept.sort(key=lambda comparison: (comparison.sources_agree, -comparison.distinct_source_count))
    return kept
