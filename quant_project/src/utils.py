import logging
import re
import time
from pathlib import Path

import pandas as pd


logger = logging.getLogger("quant_project")


def configure_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def standardize_stock_code(value):
    value = str(value).strip().upper()
    match = re.fullmatch(r"(?:(SH|SZ|BJ)\.)?(\d{6})(?:\.(SH|SZ|BJ))?", value)
    if not match:
        raise ValueError(f"Invalid stock code: {value}")
    prefix, symbol, suffix = match.groups()
    if prefix and suffix and prefix != suffix:
        raise ValueError(f"Conflicting exchange: {value}")
    market = prefix or suffix
    if not market:
        market = "SH" if symbol.startswith(("6", "9")) else "BJ" if symbol.startswith(("4", "8")) else "SZ"
    return f"{symbol}.{market}"


def to_baostock_code(code):
    symbol, market = standardize_stock_code(code).split(".")
    return f"{market.lower()}.{symbol}"


def query_rows(query, attempts=3):
    """Retry a BaoStock query and reject partial or failed responses."""
    last = None
    for attempt in range(attempts):
        try:
            rs = query()
            if rs.error_code != "0":
                raise RuntimeError(f"BaoStock {rs.error_code}: {rs.error_msg}")
            rows = []
            while rs.next():
                rows.append(rs.get_row_data())
            if rs.error_code != "0":
                raise RuntimeError(f"BaoStock {rs.error_code}: {rs.error_msg}")
            return pd.DataFrame(rows, columns=rs.fields)
        except Exception as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(min(2**attempt, 4))
    raise RuntimeError(f"BaoStock query failed after {attempts} attempts") from last


def ensure_dirs(*paths: Path):
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
