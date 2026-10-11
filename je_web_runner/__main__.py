"""
WebRunner CLI 進入點。
WebRunner CLI entry point: ``python -m je_web_runner`` and the ``webrunner`` / ``web_runner`` console scripts.
"""
import sys

from je_web_runner.utils.cli.cli_main import main


def run() -> int:
    """
    CLI 的最外層：任何例外只印一行到 stderr 並回傳 1
    Run the CLI and return its exit code. An exception that escapes it is printed as one
    ``repr`` line on stderr and exits 1, the same for ``python -m je_web_runner`` and the
    console scripts.
    """
    try:
        return main()
    except Exception as error:  # the last resort: one line on stderr, exit code 1
        print(repr(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(run())
