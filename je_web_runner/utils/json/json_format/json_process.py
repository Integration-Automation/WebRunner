import json.decoder
import sys
from json import dumps
from json import loads

from je_web_runner.utils.exception.exception_tag import wrong_json_data_error, cant_reformat_json_error
from je_web_runner.utils.exception.exceptions import WebRunnerJsonException


def __process_json(json_string: str, **kwargs):
    """
    :param json_string: full json str (not json type)
    :param kwargs: any another kwargs for dumps
    :return: reformat str
    """
    try:
        return dumps(loads(json_string), indent=4, sort_keys=True, **kwargs)
    except json.JSONDecodeError as error:
        print(wrong_json_data_error, file=sys.stderr)
        raise error
    except TypeError:
        try:
            return dumps(json_string, indent=4, sort_keys=True, **kwargs)
        except TypeError:
            raise WebRunnerJsonException(wrong_json_data_error)


def reformat_json(json_string: str, **kwargs):
    try:
        return __process_json(json_string, **kwargs)
    except WebRunnerJsonException:
        raise WebRunnerJsonException(cant_reformat_json_error)
