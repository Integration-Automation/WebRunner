"""
WebRunner CLI 進入點。
WebRunner CLI entry point.
"""
import sys

from je_web_runner.utils.cli.cli_main import main

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:  # noqa: BLE001 — surface any failure as exit-1 to the shell
        print(repr(error), file=sys.stderr)
        sys.exit(1)
