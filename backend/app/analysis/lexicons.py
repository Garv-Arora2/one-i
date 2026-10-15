"""Fixed word lists used by the deterministic analysis rules.

These lists are intentionally small, readable and auditable. They describe
*language*, not outlets: nothing here judges a publisher.
"""

from __future__ import annotations

# Verbs that usually signal something happened, used to pick out sentences that
# can become developments.
ACTION_VERBS: frozenset[str] = frozenset(
    """
announced announces announce ordered orders order evacuated evacuate evacuates closed closes
close halted halts halt suspended suspends suspend launched launches launch filed files file
arrested arrests arrest banned bans ban fined fines fine resigned resigns resign confirmed
confirms confirm denied denies deny opened opens open began begins begin started starts start
approved approves approve rejected rejects reject agreed agrees agree signed signs sign
issued issues issue released releases release recalled recalls recall investigated
investigates investigate warned warns warn admitted admits admit apologised apologized
reopened reopens reopen restored restores restore detained detains detain charged charges
charge sued sues sue voted votes vote passed passes pass blocked blocks block reduced reduces
reduce raised raises raise cut cuts rose rises fell falls dropped drops declined declines
killed killing injured died evacuating shut reported ruled rules rule found finds testified
testifies attacked attacks attack retaliated retaliates retaliate struck strike strikes
collapse collapses collapsed collapsing shot shooting intercept intercepts intercepted
sentenced frees freed pushed pushes push protested protests protest responded responds respond
""".split()
)

# Verbs that turn a number into a *change* rather than a level.
CHANGE_VERBS: frozenset[str] = frozenset(
    """
rose rise rises risen fell fall falls fallen dropped drop drops declined decline declines
increased increase increases decreased decrease decreases grew grow grows gained gain gains
lost lose loses jumped jump jumps surged surge surges slid slide slides climbed climb climbs
plunged plunge plunges up down higher lower gaining losing rising falling
""".split()
)

# Wording aspects. Each entry maps an aspect to the words that indicate it.
RESPONSIBILITY_WORDS: frozenset[str] = frozenset(
    """
admitted admits acknowledged acknowledges blamed blames responsible responsibility accountable
accountability caused causing denied denies fault negligence negligent liable liability
apologised apologized apology attributed attributes culpable
""".split()
)

ACTION_WORDS: frozenset[str] = ACTION_VERBS

SEVERITY_WORDS: frozenset[str] = frozenset(
    """
catastrophic devastating deadly fatal severe serious critical major massive widespread
significant substantial moderate limited minor small slight contained isolated
""".split()
)

CERTAINTY_WORDS: frozenset[str] = frozenset(
    """
confirmed confirms verified established alleged allegedly reportedly claimed claims apparent
apparently suspected unconfirmed possible possibly potentially may might could likely unlikely
believed thought estimated preliminary
""".split()
)

EVALUATION_WORDS: frozenset[str] = frozenset(
    """
mishandled botched failed failure inadequate insufficient chaotic slow sluggish criticised
criticized condemned praised swift prompt effective successful decisive commended reassuring
troubling alarming
""".split()
)

ASPECT_LEXICONS: dict[str, frozenset[str]] = {
    "responsibility": RESPONSIBILITY_WORDS,
    "action": ACTION_WORDS,
    "severity": SEVERITY_WORDS,
    "certainty": CERTAINTY_WORDS,
    "evaluation": EVALUATION_WORDS,
}

# Multi-word terms in which a lexicon word carries no evaluative framing.
# "Strike" in "carrier strike group" names a type of naval formation; it is
# not an outlet choosing to frame something as an attack. A marker word found
# inside one of these compounds is dropped from the wording markers.
NEUTRAL_COMPOUNDS: tuple[str, ...] = (
    "strike group",
)


def in_neutral_compound(word: str, text_lower: str) -> bool:
    """True when `word` only occurs as part of a neutral multi-word term."""
    lowered = word.lower()
    return any(
        lowered in compound.split() and compound in text_lower
        for compound in NEUTRAL_COMPOUNDS
    )


# Words treated as equivalent, so that a trivial synonym swap is not presented
# to the reader as a meaningful difference.
SYNONYM_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"said", "stated", "told"}),
    frozenset({"big", "large"}),
    frozenset({"major", "significant", "substantial"}),
    frozenset({"minor", "small", "slight"}),
    frozenset({"apologised", "apologized"}),
    frozenset({"criticised", "criticized"}),
    frozenset({"began", "started"}),
    frozenset({"halted", "suspended"}),
    frozenset({"killed", "killing"}),
    frozenset({"collapse", "collapses", "collapsed", "collapsing"}),
    frozenset({"deadly", "fatal"}),
    frozenset({"confirmed", "verified"}),
    frozenset({"allegedly", "reportedly"}),
    frozenset({"increase", "rise"}),
    frozenset({"decrease", "fall"}),
)

_SYNONYM_LOOKUP: dict[str, int] = {}
for _index, _group in enumerate(SYNONYM_GROUPS):
    for _word in _group:
        _SYNONYM_LOOKUP[_word] = _index


def synonym_key(word: str) -> str:
    """Map a word to its synonym group, so equivalent words compare equal."""
    lowered = word.lower()
    group = _SYNONYM_LOOKUP.get(lowered)
    return f"group:{group}" if group is not None else lowered
