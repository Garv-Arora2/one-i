"""Score the ONE I analysis modules against the manually reviewed set.

    python -m evaluation.run_evaluation      (from backend/)

Prints precision, recall and F1 for event grouping, coverage, number
equivalence and wording differences, plus every individual mistake so the
failure modes are visible rather than hidden behind an average.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from app.analysis.coverage import (
    ArticleForCoverage,
    DevelopmentForCoverage,
    assess_coverage,
)
from app.analysis.grouping import ArticleForGrouping, score_pairs
from app.analysis.numbers import extract_numbers, group_observations, is_internally_consistent
from app.analysis.wording import Passage, compare_wording, extract_markers
from app.core.timeutil import parse_iso
from app.ingestion.providers.demo import load_demo_dataset
from app.models.enums import CoverageStatus

DATASET_PATH = Path(__file__).with_name("dataset.json")


@dataclass
class Score:
    task: str
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0
    true_negative: int = 0
    mistakes: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.mistakes = self.mistakes or []

    def add(self, predicted: bool, expected: bool, label: str) -> None:
        if predicted and expected:
            self.true_positive += 1
        elif predicted and not expected:
            self.false_positive += 1
            self.mistakes.append(f"false positive: {label}")
        elif not predicted and expected:
            self.false_negative += 1
            self.mistakes.append(f"false negative: {label}")
        else:
            self.true_negative += 1

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else 0.0

    @property
    def f1(self) -> float:
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * self.precision * self.recall / (self.precision + self.recall)

    def report(self) -> str:
        total = self.true_positive + self.false_positive + self.false_negative + self.true_negative
        lines = [
            f"{self.task}",
            f"  items      : {total}",
            f"  precision  : {self.precision:.3f}",
            f"  recall     : {self.recall:.3f}",
            f"  f1         : {self.f1:.3f}",
            f"  tp/fp/fn/tn: {self.true_positive}/{self.false_positive}/"
            f"{self.false_negative}/{self.true_negative}",
        ]
        lines.extend(f"  {mistake}" for mistake in self.mistakes)
        return "\n".join(lines)


def evaluate_grouping(labels: dict) -> Score:
    demo = load_demo_dataset()
    by_url = {item["url"]: item for item in demo["articles"]}
    assignments = labels["article_events"]
    candidates = [
        ArticleForGrouping(
            id=index,
            title=by_url[url]["title"],
            content=by_url[url]["content"],
            published_at=parse_iso(by_url[url]["published_at"]),
        )
        for index, url in enumerate(assignments)
    ]
    urls = list(assignments)
    score = Score("Event grouping (pairwise link decision)")
    for pair in score_pairs(candidates):
        expected = assignments[urls[pair.left_id]] == assignments[urls[pair.right_id]]
        score.add(pair.linked, expected, f"{urls[pair.left_id]} <-> {urls[pair.right_id]}")
    _ = combinations
    return score


def evaluate_coverage(labels: dict) -> tuple[Score, Score, int]:
    demo = load_demo_dataset()
    by_url = {item["url"]: item for item in demo["articles"]}
    domains = {source["domain"]: index for index, source in enumerate(demo["sources"])}

    covered_score = Score("Coverage (predicting 'covered')")
    timing_score = Score("Coverage timing (predicting 'not applicable')")
    unclear_count = 0

    for probe in labels["probes"]:
        development = DevelopmentForCoverage(
            id=1,
            text=probe["text"],
            keywords=[],
            occurred_at=parse_iso(probe["occurred_at"]),
        )
        urls = list(probe["labels"])
        articles = [
            ArticleForCoverage(
                id=index,
                source_id=domains[by_url[url]["source_domain"]],
                title=by_url[url]["title"],
                content=by_url[url]["content"],
                published_at=parse_iso(by_url[url]["published_at"]),
            )
            for index, url in enumerate(urls)
        ]
        decisions = assess_coverage([development], articles)
        for decision in decisions:
            url = urls[decision.article_id]
            expected = probe["labels"][url]
            name = f"{probe['id']} / {url.split('//')[-1][:52]}"
            if decision.status is CoverageStatus.UNCLEAR:
                unclear_count += 1
            covered_score.add(
                decision.status is CoverageStatus.COVERED, expected == "covered", name
            )
            timing_score.add(
                decision.status is CoverageStatus.NOT_APPLICABLE,
                expected == "not_applicable",
                name,
            )
    return covered_score, timing_score, unclear_count


def evaluate_numbers(labels: dict) -> Score:
    score = Score("Number equivalence (predicting 'comparable')")
    for pair in labels["pairs"]:
        left = extract_numbers(1, 1, "Report", pair["left"])
        right = extract_numbers(2, 2, "Report", pair["right"])
        grouped = group_observations(left + right)
        comparable = any(
            len({observation.article_id for observation in group}) > 1
            and is_internally_consistent(group)
            for group in grouped
        )
        score.add(comparable, bool(pair["comparable"]), f"{pair['left'][:48]} | {pair['right'][:48]}")
    return score


def evaluate_wording(labels: dict) -> Score:
    score = Score("Wording difference (predicting 'meaningful')")
    for pair in labels["pairs"]:
        passages = [
            Passage(1, 1, "Source A", pair["left"], pair["left"], 1.0, extract_markers(pair["left"])),
            Passage(2, 2, "Source B", pair["right"], pair["right"], 1.0, extract_markers(pair["right"])),
        ]
        result = compare_wording("topic", passages)
        score.add(result is not None, bool(pair["meaningful"]), f"{pair['left'][:56]}")
    return score


def main() -> None:
    with DATASET_PATH.open("r", encoding="utf-8") as handle:
        dataset = json.load(handle)

    print("ONE I analysis evaluation")
    print("=" * 60)
    print(evaluate_grouping(dataset["grouping"]).report())
    print()
    covered, timing, unclear = evaluate_coverage(dataset["coverage"])
    print(covered.report())
    print(f"  unclear    : {unclear} (reported as 'coverage unclear' rather than forced)")
    print()
    print(timing.report())
    print()
    print(evaluate_numbers(dataset["number_equivalence"]).report())
    print()
    print(evaluate_wording(dataset["wording_difference"]).report())


if __name__ == "__main__":
    main()
