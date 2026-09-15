from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def run(sample: str | None = None) -> dict:
    packages = {name: importlib.util.find_spec(name) is not None for name in ("numpy", "pandas", "scipy", "requests", "openpyxl")}
    sample_ok = Path(sample).is_file() if sample else None
    return {
        "python_supported": sys.version_info >= (3, 11),
        "packages": packages,
        "sample_file_readable": sample_ok,
        "file_mode_ready": all(packages.values()) and sys.version_info >= (3, 11),
        "panda_trade_api": "NOT_VERIFIED_REQUIRES_SERVICE_URL_TOKEN_ACCOUNT_ID",
        "tiger_api": "REQUIRES_USER_AUTHORIZED_TIGEROPEN_CLIENT",
        "eastmoney_api": "REQUIRES_USER_AUTHORIZED_CLIENT; NO OFFICIAL PUBLIC PERSONAL-TRADE ENDPOINT VERIFIED",
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="交易行为诊断启动检查")
    p.add_argument("--sample"); a = p.parse_args(); print(json.dumps(run(a.sample), ensure_ascii=False, indent=2))
