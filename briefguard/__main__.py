"""Small, reproducible command-line surface."""
import argparse
import json
from pathlib import Path

from .runner import freeze, run
from .metrics import summarize, write_report
from .evidence import validate_completed_run, validate_saved_summary


def main():
    parser = argparse.ArgumentParser(prog="briefguard")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "freeze", "report", "demo", "check"):
        p = sub.add_parser(name)
        p.add_argument("--config", type=Path, default=Path("configs/study.json"))
        if name == "run":
            p.add_argument("--split", choices=("pilot", "dev", "test"), required=True)
            p.add_argument("--out", type=Path, required=True)
            p.add_argument("--frozen", type=Path, default=Path("configs/frozen.json"))
        elif name == "freeze":
            p.add_argument("--pilot", type=Path, default=Path("results/pilot"))
            p.add_argument("--out", type=Path, default=Path("configs/frozen.json"))
        else:
            p.add_argument("--run", type=Path, default=Path("results/test"))
            if name == "demo":
                p.add_argument("--out", type=Path, default=Path("demo"))
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text())
        if args.command == "run":
            print(json.dumps(run(config, args.split, args.out, args.frozen), indent=2))
        elif args.command == "freeze":
            print(json.dumps(freeze(config, args.pilot, args.out), indent=2))
        elif args.command in ("report", "check"):
            meta, rows = validate_completed_run(args.run, config)
            if args.command == "report":
                write_report(summarize(rows, config), args.run)
                print(args.run / "tables.md")
            else:
                print(json.dumps({"run_id": meta["run_id"], "validated_rows": len(rows), "complete": True}))
        else:
            from .demo_export import export_demo
            _, rows = validate_completed_run(args.run, config)
            validate_saved_summary(args.run, rows, config)
            print(json.dumps(export_demo(args.run, args.out, config), indent=2))
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        parser.exit(2, f"briefguard: {exc}\n")


if __name__ == "__main__":
    main()
