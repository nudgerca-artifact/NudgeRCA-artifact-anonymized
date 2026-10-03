#!/usr/bin/env python3
"""Table 1: top-1 component accuracy of the untrained Qwen3-4B on 55 Bank incidents, without injection and with the reasoning structure
of another incident appended as a reference procedure (same / different root-cause component, names kept or masked).
The scorer is score_masking.py (next to this file); the runs are in outputs/, the structures and targets in data/, the runner in code/.
Usage: python3 table_01.py   -> table_01.txt
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "common"))
from tables import emit, run   # noqa: E402

emit([run("score_masking.py", HERE)], HERE, "table_01")
