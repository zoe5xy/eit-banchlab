"""Run the original water-tank example through the standalone EIT API."""

import argparse
import json
from pathlib import Path
from eitbench import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data/example.npz",
    )
    parser.add_argument("--out", type=Path, default=Path("runs/eit_example"))
    parser.add_argument("--model", choices=["cem", "continuum"], default="cem")
    parser.add_argument("--iterations", type=int, default=30)
    args = parser.parse_args()
    result = run(
        case=args.input,
        config={
            "parameters": {"variant": args.model},
            "run_controls": {"max_iterations": args.iterations},
        },
        out=args.out,
    )
    print(
        json.dumps(
            {
                "status": result.status,
                "stop_reason": result.stopping_reason,
                "work": result.work,
                "calibration_status": result.calibration["status"],
            },
            indent=2,
        )
    )
    if result.conductivity_S_m is None:
        raise RuntimeError("No reconstruction was produced")


if __name__ == "__main__":
    main()
