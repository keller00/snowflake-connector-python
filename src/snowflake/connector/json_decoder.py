#
# Copyright (c) 2012-2021 Snowflake Computing Inc. All rights reserved.
#

from __future__ import annotations

import json
from typing import Any, Callable

try:
    from snowflake.connector.constants import UNDEFINED
    from snowflake.connector.json import make_scanner as c_make_scanner
except ImportError:
    c_make_scanner = None
    UNDEFINED = None


def py_make_scanner(context: json.JSONDecoder) -> Callable[[str, int], Any]:
    # some references for the _scan_once function below
    parse_object = context.parse_object
    parse_array = context.parse_array
    parse_string = context.parse_string
    match_number = json.scanner.NUMBER_RE.match
    strict = context.strict
    parse_float = context.parse_float
    parse_int = context.parse_int
    parse_constant = context.parse_constant
    object_hook = context.object_hook
    object_pairs_hook = context.object_pairs_hook
    memo = context.memo

    # customized _scan_once
    def _scan_once(string: str, idx: int) -> Any:
        try:
            nextchar = string[idx]
        except IndexError:
            raise StopIteration(idx) from None

        # override some parse_** calls with the correct _scan_once
        if nextchar == '"':
            return parse_string(string, idx + 1, strict)
        elif nextchar == "{":
            return parse_object(
                (string, idx + 1), strict, _scan_once, object_hook, object_pairs_hook
            )
        elif nextchar == "[":
            return parse_array((string, idx + 1), _scan_once)
        elif nextchar == "u" and string[idx : idx + 9] == "undefined":
            return UNDEFINED, idx + 9
        elif nextchar == "n" and string[idx : idx + 4] == "null":
            return None, idx + 4
        elif nextchar == "t" and string[idx : idx + 4] == "true":
            return True, idx + 4
        elif nextchar == "f" and string[idx : idx + 5] == "false":
            return False, idx + 5

        m = match_number(string, idx)
        if m is not None:
            integer, frac, exp = m.groups()
            if frac or exp:
                res = parse_float(integer + (frac or "") + (exp or ""))
            else:
                res = parse_int(integer)
            return res, m.end()
        elif nextchar == "N" and string[idx : idx + 3] == "NaN":
            return parse_constant("NaN"), idx + 3
        elif nextchar == "I" and string[idx : idx + 8] == "Infinity":
            return parse_constant("Infinity"), idx + 8
        elif nextchar == "-" and string[idx : idx + 9] == "-Infinity":
            return parse_constant("-Infinity"), idx + 9
        else:
            raise StopIteration(idx)

    def scan_once(string, idx):
        try:
            return _scan_once(string, idx)
        finally:
            memo.clear()

    return scan_once


make_scanner = c_make_scanner or py_make_scanner


class SnowflakeJSONDecoder(json.JSONDecoder):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # override scanner
        self.scan_once = make_scanner(self)
