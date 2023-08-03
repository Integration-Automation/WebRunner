import logging
import sys

web_runner_logger = logging.getLogger("WEBRunner")
web_runner_logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s')
# Stream handler
stream_handler = logging.StreamHandler(stream=sys.stderr)
stream_handler.setFormatter(formatter)
stream_handler.setLevel(logging.WARNING)
web_runner_logger.addHandler(stream_handler)
# File handler
file_handler = logging.FileHandler(filename="WEBRunner.log", mode="w")
file_handler.setFormatter(formatter)
web_runner_logger.addHandler(file_handler)
