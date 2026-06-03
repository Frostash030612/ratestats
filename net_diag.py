import os
import sys
import time
from typing import Dict, List, Tuple

import requests


PROXY_ENV_KEYS = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
]


TEST_URLS = [
    "https://www.bankofchina.com/sg/cn/bocinfo/bi3/bi31/202603/t20260302_25651264.html",
    "https://www.hkbea.com.sg/html/en/index.html",
    "https://www.cimb.com.sg/en/personal/help-support/rates-charges/rates/sgd-fixed-deposit-rates.html",
    "https://www.dbs.com.sg/personal/rates-online/fixed-deposit-rate-singapore-dollar.page",
    "https://www.ocbc.com/personal-banking/deposits/fixed-deposit-account",
]


def _print_env_proxies() -> None:
    print("## Proxy env")
    for k in PROXY_ENV_KEYS:
        v = os.environ.get(k)
        if v:
            print(f"{k}={v}")
    if not any(os.environ.get(k) for k in PROXY_ENV_KEYS):
        print("(no proxy-related env vars found)")


def _requests_proxy_map(url: str) -> Dict[str, str]:
    # requests uses urllib3/requests internal resolution; this exposes what it *thinks* proxies are
    return requests.utils.get_environ_proxies(url) or {}


def _try_get(url: str, *, force_no_proxy: bool, timeout: int = 20) -> Tuple[str, int, int, str]:
    """
    Returns (mode, status_code, content_len, error_str)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        if force_no_proxy:
            r = requests.get(url, timeout=timeout, headers=headers, proxies={"http": None, "https": None})
        else:
            r = requests.get(url, timeout=timeout, headers=headers)
        return ("no_proxy" if force_no_proxy else "default", r.status_code, len(r.content or b""), "")
    except Exception as ex:
        return ("no_proxy" if force_no_proxy else "default", -1, 0, f"{type(ex).__name__}: {ex}")


def main() -> None:
    print("python", sys.version.replace("\n", " "))
    _print_env_proxies()
    print()

    print("## requests environ proxies (per URL)")
    for u in TEST_URLS:
        p = _requests_proxy_map(u)
        print(u)
        print("  proxies:", p if p else "{}")
    print()

    print("## connectivity test (default vs force no-proxy)")
    for u in TEST_URLS:
        print("\nURL:", u)
        for mode in [False, True]:
            m, code, clen, err = _try_get(u, force_no_proxy=mode)
            print(f"  {m:8s} status={code} len={clen} err={err}")
            time.sleep(0.2)


if __name__ == "__main__":
    main()

