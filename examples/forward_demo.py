"""Compute electrode voltages from a specified conductivity on the supplied mesh."""

import argparse
from pathlib import Path
import numpy as np
from eitbench import load_case
from eitbench.operators.forward import ForwardModel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data/example.npz",
    )
    parser.add_argument("--model", choices=("cem", "continuum"), default="cem")
    parser.add_argument("--out", type=Path, default=Path("artifacts/forward.npz"))
    args = parser.parse_args()
    case = load_case(args.case)
    data = case.data
    forward = ForwardModel(
        case.mesh,
        data["currents_A"],
        data["measurement_matrix"],
        float(data["thickness_m"]),
        args.model,
        data["contact_impedance_ohm_m2"],
    )
    background = float(data["background_conductivity_S_m"])
    sigma = np.full(len(case.mesh.nodes), background)
    inclusion = np.linalg.norm(case.mesh.nodes - [0.035, 0.025], axis=1) < 0.025
    sigma[inclusion] = 0.5 * background
    voltage, state, _ = forward.solve(sigma)
    if args.out.exists():
        parser.error(f"output already exists: {args.out}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.out,
        nodes=case.mesh.nodes,
        triangles=case.mesh.triangles,
        conductivity_S_m=sigma,
        voltages_V=voltage,
        potential_nodes_V=state[: forward.n],
    )
    print(f"Saved synthetic forward solution to {args.out}")


if __name__ == "__main__":
    main()
