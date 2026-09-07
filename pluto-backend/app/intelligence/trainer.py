"""Train / evaluate / persist PLUTO's local intent model.

Run from the backend dir:

    python -m app.intelligence.trainer            # train + evaluate + save
    python -m app.intelligence.trainer --show     # also print CLI report

No external AI/API involved: PLUTO learns from its own seed corpus plus any
user corrections stored in the SQLite memory.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, List

from app.core.logging import get_logger
from app.intelligence.brain import PlutoBrain
from app.intelligence.classifier import LocalIntentClassifier
from app.intelligence.dataset import build_dataset
from app.intelligence.memory import get_memory

logger = get_logger(__name__)


def _print_report(metrics: Dict[str, Any]) -> None:
    print("\n=== PLUTO Local Intent Model Report ===")
    print(f"Train samples : {metrics.get('train_samples')}")
    print(f"Test samples  : {metrics.get('test_samples')}")
    print(f"Accuracy      : {metrics.get('accuracy')}")
    print(f"F1 (macro)    : {metrics.get('f1_macro')}")
    report = metrics.get("report") or {}
    if report:
        print("\nPer-class F1 (sample):")
        for label, row in list(report.items())[:20]:
            if isinstance(row, dict):
                print(f"  {label:<32} precision={row.get('precision'):.2f} "
                      f"recall={row.get('recall'):.2f} f1={row.get('f1-score'):.2f}")
    print("=========================================\n")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Train and evaluate PLUTO's local intent model."
    )
    parser.add_argument("--show", action="store_true", help="Print the report.")
    parser.add_argument(
        "--model-path", default=None,
        help="Override the model file path (default ~/.pluto/models/...).",
    )
    args = parser.parse_args(argv)

    memory = get_memory()
    classifier = LocalIntentClassifier(model_path=args.model_path)
    brain = PlutoBrain(classifier=classifier, memory=memory)

    metrics = brain.train_and_evaluate()
    logger.info("trainer_done", metrics=metrics)

    # Quick smoke self-check on a handful of representative commands.
    smoke = [
        "take a screenshot",
        "open youtube",
        "set volume to 40",
        "create a folder called notes",
        "search for python tutorials on youtube",
    ]
    self_check = []
    for cmd in smoke:
        label, conf = classifier.predict(cmd)
        self_check.append((cmd, label, conf))
    if args.show:
        _print_report(metrics)
        print("Smoke predictions:")
        for cmd, label, conf in self_check:
            print(f"  {cmd!r:<45} -> {label} ({conf:.2f})")
        print()
    else:
        _print_report(metrics)
        print("Smoke predictions:")
        for cmd, label, conf in self_check:
            print(f"  {cmd!r:<45} -> {label} ({conf:.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
