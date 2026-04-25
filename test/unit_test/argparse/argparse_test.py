import os
import subprocess  # nosec B404
import sys

print(os.getcwd())

subprocess.run(  # nosec B603
    [sys.executable, "-m", "je_web_runner", "--execute_dir",
     r"C:\program_workspace\python\WebRunner\test\unit_test\argparse"],
    check=False,
)
