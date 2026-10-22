"""Small, reproducible command-line surface."""
import argparse
import json
from pathlib import Path

from .runner import freeze, read_rows, run
from .metrics import summarize, write_report


def main():
    parser = argparse.ArgumentParser(prog="briefguard")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "freeze", "report", "demo"):
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
    config = json.loads(args.config.read_text())
    if args.command == "run":
        print(json.dumps(run(config, args.split, args.out, args.frozen), indent=2))
    elif args.command == "freeze":
        print(json.dumps(freeze(config, args.pilot, args.out), indent=2))
    elif args.command == "report":
        meta = json.loads((args.run / "metadata.json").read_text())
        if not meta["complete"] or meta["identity"]["config"] != config:
            raise ValueError("Incomplete run or configuration mismatch")
        write_report(summarize(read_rows(args.run / "predictions.jsonl"), config), args.run)
        print(args.run / "tables.md")
    else:
        from .demo_export import export_demo
        print(json.dumps(export_demo(args.run, args.out, config), indent=2))


if __name__ == "__main__":
    main()
