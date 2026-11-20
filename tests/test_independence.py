"""The standalone package must not import any of the original projects."""

import subprocess
import sys
import os
from pathlib import Path


def test_independent_import(tmp_path):
    program = """
import builtins
original = builtins.__import__
def blocked(name, *args, **kwargs):
    if name.split('.')[0] in ('usctbench', 'usct_framework', 'eit_framework',
                              'ftttbench', 'fttt_framework', 'inv_framework'):
        raise AssertionError('unexpected original-project import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = blocked
import eitbench as library
from eitbench.operators.eit import EITForwardOperator
from eitbench.solvers.tv import LBFGSBTVSolver
from eitbench.algorithms.lbfgsb_tv import LBFGSBTV
from eitbench.algorithms.calibration import calibrate
assert library.describe()['algorithm_id'] == 'lbfgsb_tv'
assert library.list_algorithms() == ['lbfgsb_tv']
assert library.prepare_config().name == 'lbfgsb_tv'
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
