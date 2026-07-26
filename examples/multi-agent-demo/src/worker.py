"""Tiny worker used by the Commons multi-agent demo smoke script."""

from __future__ import annotations

from payment_api import create_payment_intent, summarize


def run_once() -> str:
    intent = create_payment_intent("demo-intent-001", 1250)
    return summarize(intent)


if __name__ == "__main__":
    print(run_once())
