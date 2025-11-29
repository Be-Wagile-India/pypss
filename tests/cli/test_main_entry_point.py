import subprocess
import sys


def test_cli_main_entry_point():
    # Run the cli.py as a script to hit the __main__ block
    result = subprocess.run(
        [sys.executable, "-m", "pypss.cli.cli"],
        capture_output=True,
        text=True,
        check=False,
    )

    # Check for help message or a default output, indicating it ran
    assert (
        result.returncode == 0 or result.returncode == 2
    )  # Can be 0 for help or 2 for no command
    assert "Usage:" in result.stderr
    assert "[OPTIONS] COMMAND" in result.stderr
