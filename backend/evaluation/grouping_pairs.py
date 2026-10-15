"""Developer helper: print every article pair score with its true label.

Used to choose the grouping threshold from evidence rather than by feel.

    python -m evaluation.grouping_pairs      (from backend/)
"""

from __future__ import annotations

from app.analysis.grouping import ArticleForGrouping, score_pairs
from app.core.timeutil import parse_iso
from app.ingestion.providers.demo import load_demo_dataset


def main() -> None:
    dataset = load_demo_dataset()
    articles = dataset["articles"]
    hints = {index: item["event_hint"] for index, item in enumerate(articles)}
    candidates = [
        ArticleForGrouping(
            id=index,
            title=item["title"],
            content=item["content"],
            published_at=parse_iso(item["published_at"]),
        )
        for index, item in enumerate(articles)
    ]
    pairs = score_pairs(candidates)
    same = sorted(
        (pair for pair in pairs if hints[pair.left_id] == hints[pair.right_id]),
        key=lambda pair: pair.score,
    )
    different = sorted(
        (pair for pair in pairs if hints[pair.left_id] != hints[pair.right_id]),
        key=lambda pair: -pair.score,
    )
    print("SAME EVENT (lowest scores first)")
    for pair in same[:14]:
        print(f"  {pair.score:.3f}  {pair.explanation()}  [{hints[pair.left_id]}]")
    print("\nDIFFERENT EVENT (highest scores first)")
    for pair in different[:10]:
        print(
            f"  {pair.score:.3f}  {pair.explanation()}  "
            f"[{hints[pair.left_id]} vs {hints[pair.right_id]}]"
        )


if __name__ == "__main__":
    main()
