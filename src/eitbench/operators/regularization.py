"""Smoothed isotropic P1 FEM TV from the supplied EIT submission."""

import numpy as np


def smooth_tv(mesh, m, epsilon):
    if np.iscomplexobj(m) or np.iscomplexobj(epsilon):
        raise ValueError("TV input and epsilon must be real")
    try:
        m = np.asarray(m, dtype=float)
        epsilon = np.asarray(epsilon, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("TV input and epsilon must contain real numbers") from exc
    if m.shape != (len(mesh.nodes),) or not np.isfinite(m).all():
        raise ValueError("TV input must be finite [N]")
    if epsilon.shape != () or not np.isfinite(epsilon) or epsilon <= 0:
        raise ValueError("TV epsilon must be a positive finite scalar")
    with np.errstate(over="ignore", under="ignore", invalid="ignore", divide="ignore"):
        d = np.einsum("ti,tid->td", m[mesh.triangles], mesh.grad)
        den = np.sqrt(np.sum(d * d, axis=1) + epsilon**2)
        value = np.sum(mesh.area * (den - epsilon))
        local = mesh.area[:, None] * np.einsum(
            "td,tid->ti", d / den[:, None], mesh.grad
        )
        gradient = np.bincount(
            mesh.triangles.ravel(), weights=local.ravel(), minlength=len(m)
        )
    if not np.isfinite(value) or not np.isfinite(gradient).all():
        raise FloatingPointError("nonfinite TV value or gradient")
    return float(value), gradient
