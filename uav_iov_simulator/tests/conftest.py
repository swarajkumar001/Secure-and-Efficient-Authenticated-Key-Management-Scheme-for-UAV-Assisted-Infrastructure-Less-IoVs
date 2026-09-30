"""
Make the tests runnable from anywhere.

Without this, `pytest` only works when the current directory is the one
CONTAINING `uav_iov_simulator/`, because the tests import the package by name.
Running from inside the package folder - which is the natural thing to do -
failed with ModuleNotFoundError.

Adding the package's parent to sys.path here means all of these work:

    cd "RIS PROJECT"              &&  python -m pytest uav_iov_simulator/tests
    cd "RIS PROJECT/uav_iov_simulator" &&  python -m pytest tests
    cd anywhere                   &&  python -m pytest <full path to tests>
"""

from __future__ import annotations

import sys
from pathlib import Path

# tests/ -> uav_iov_simulator/ -> the folder that contains the package
PACKAGE_PARENT = Path(__file__).resolve().parent.parent.parent

if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))
