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
    pilot_parser = sub.add_parser("pilot", help="Run a separately versioned exploratory VLM pilot")
    pilot_commands = pilot_parser.add_subparsers(dest="pilot_command", required=True)
    for name in ("prepare", "run", "check"):
        p = pilot_commands.add_parser(name)
        p.add_argument("--protocol", choices=("v1", "v2"), default="v1")
        if name == "prepare":
            p.add_argument("--out", type=Path, required=True)
            p.add_argument("--natural-input", type=Path)
        else:
            p.add_argument("--directory", type=Path, required=True)
            if name == "run":
                p.add_argument("--approve-openai-gpt41mini-usd050", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "pilot":
            if args.protocol == "v2":
                from . import pilot_v2 as selected_pilot
            else:
                from . import pilot as selected_pilot
            if args.pilot_command == "prepare":
                plan = selected_pilot.prepare(args.out, args.natural_input)
                result = {"protocol": args.protocol, "cases": len(plan["cases"]),
                          "logical_checks": len(plan["jobs"]), "complete_data": plan["complete_data"], "live_requests": 0}
            elif args.pilot_command == "check":
                plan = selected_pilot.validate_preparation(args.directory)
                result = {"protocol": args.protocol, "valid": True, "logical_checks": len(plan["jobs"]), "complete_data": plan["complete_data"]}
            else:
                result = selected_pilot.run(args.directory, args.approve_openai_gpt41mini_usd050)
            print(json.dumps(result, indent=2))
            return
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
