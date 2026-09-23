import argparse
import asyncio
import json
from pathlib import Path

from .agents import ReferenceCommerceAgent, RegressionAgent
from .runner import run_suite
from .scenarios import load_scenarios


def main():
    parser = argparse.ArgumentParser(description="Evaluate a tool-using agent")
    parser.add_argument("--scenarios", default="scenarios/commerce.yaml")
    parser.add_argument("--agent", choices=["reference", "regression"], default="reference")
    parser.add_argument("--output", default="evaluation-report.json")
    parser.add_argument("--minimum-pass-rate", type=float, default=0.85)
    args = parser.parse_args()
    agent = ReferenceCommerceAgent() if args.agent == "reference" else RegressionAgent()
    summary = asyncio.run(run_suite(load_scenarios(args.scenarios), agent))
    Path(args.output).write_text(json.dumps(summary.model_dump(), indent=2))
    print(f"{summary.passed}/{summary.total} passed ({summary.pass_rate:.1%}); score={summary.average_score:.3f}")
    raise SystemExit(0 if summary.pass_rate >= args.minimum_pass_rate else 1)


if __name__ == "__main__":
    main()

