"""
WebRunner CLI 進入點。
WebRunner CLI entry point.
"""
import sys

from je_web_runner.utils.cli.cli_main import main

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(repr(error), file=sys.stderr)
        sys.exit(1)
