"""Run scripts/test_voice_cta_generation.py (prompt checks only, no --live API)."""

import os
import subprocess
import sys


def test_voice_cta_generation_prompt_script_exits_zero():
    root = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(root, "scripts", "test_voice_cta_generation.py")
    proc = subprocess.run(
        [sys.executable, script],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + "\n--- stderr ---\n" + proc.stderr
