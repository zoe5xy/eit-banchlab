import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import argparse
import json
from pathlib import Path
from . import bench, describe, evaluate, list_algorithms, prepare_config, run, suite


def main(argv=None):
    parser = argparse.ArgumentParser(description="EIT P1 FEM benchmark")
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", aliases=["list-algorithms"])
    listing.add_argument("--json", action="store_true")
    description = commands.add_parser("describe", aliases=["describe-algorithm"])
    description.add_argument("algorithm")
    description.add_argument("--variant", choices=("cem", "continuum"))
    validation = commands.add_parser("validate-config")
    validation.add_argument("--config", required=True, type=Path)
    validation.add_argument("--caps", default="{}")
    inspection = commands.add_parser("inspect", aliases=["inspect-case"])
    inspection.add_argument("--case", required=True, type=Path)
    execution = commands.add_parser("run")
    execution.add_argument("algorithm", choices=list_algorithms())
    execution.add_argument("--case", required=True, type=Path)
    execution.add_argument("--config", type=Path)
    execution.add_argument("--out", required=True, type=Path)
    execution.add_argument("--preview", action="store_true")
    batch = commands.add_parser("suite")
    batch.add_argument("--cases", required=True, nargs="+", type=Path)
    batch.add_argument("--config", type=Path)
    batch.add_argument("--out", required=True, type=Path)
    batch.add_argument("--preview", action="store_true")
    benchmark = commands.add_parser("bench")
    benchmark.add_argument("--suite", required=True, type=Path)
    benchmark.add_argument("--out", required=True, type=Path)
    benchmark.add_argument("--preview", action="store_true")
    evaluation = commands.add_parser("evaluate")
    evaluation.add_argument("--run", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        exit_code = 0
        if args.command in ("list", "list-algorithms"):
            value = (
                [describe(name) for name in list_algorithms()]
                if args.json
                else list_algorithms()
            )
        elif args.command in ("describe", "describe-algorithm"):
            value = describe(args.algorithm, args.variant)
        elif args.command == "validate-config":
            value = prepare_config(
                args.config, host_caps=json.loads(args.caps)
            ).model_dump()
        elif args.command in ("inspect", "inspect-case"):
            from .core.io import load_case

            case = load_case(args.case)
            value = dict(
                case_id=case.case_id,
                nodes=len(case.mesh.nodes),
                elements=len(case.mesh.triangles),
                voltage_shape=list(case.data["voltages_V"].shape),
                measurements=int(case.data["measurement_mask"].sum()),
            )
        elif args.command == "run":
            result = run(
                args.algorithm,
                case=args.case,
                config=args.config,
                out=args.out,
                preview=args.preview,
            )
            value = dict(
                status=result.status,
                stopping_reason=result.stopping_reason,
                work=result.work,
                saved_reconstruction=result.conductivity_S_m is not None,
            )
            exit_code = 2 if result.status == "numerical_error" else 0
        elif args.command == "suite":
            value = suite(
                args.cases, config=args.config, out=args.out, preview=args.preview
            )
            exit_code = 2 if any(r["status"] == "numerical_error" for r in value) else 0
        elif args.command == "bench":
            value = bench(args.suite, out=args.out, preview=args.preview)
            exit_code = 2 if any(r["status"] == "numerical_error" for r in value) else 0
        else:
            value = evaluate(args.run)
        print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
        return exit_code
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        parser.exit(1, str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
