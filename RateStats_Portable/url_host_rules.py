"""各 dest 允许的银行域名约束（Vertex / AI 选链共用）。"""
from __future__ import annotations

from urllib.parse import urlparse

from url_key_aliases import URL_PARAM_DEST_KEYS

# 工行新加坡：挂牌页与促销页为不同 page id
ICBC_BOARD_PAGE_ID = "721852523895095311"
ICBC_PROMO_PAGE_ID = "721854535525236736"

# 前缀从长到短匹配（hlf 必须在 hl 之前）
_PREFIX_HOST_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("bea_sgd_board", ("hkbea.com.sg",)),
    ("bea_fcy_board", ("hkbea.com.sg",)),
    ("bea_", ("hkbea.com.sg",)),
    ("maybank_", ("maybank",)),  # maybank2u.com.sg / sslsecure.maybank.com.sg
    ("icbc_", ("singapore.icbc.com.cn",)),
    ("cimb_", ("cimb.com.sg",)),
    ("citi_", ("citibank.com.sg",)),
    ("dbs_", ("dbs.com",)),
    ("ocbc_", ("ocbc.com",)),
    ("uob_", ("uob.com.sg", "uobgroup.com")),
    ("scb_", ("sc.com",)),
    ("sbi_", ("statebank",)),
    ("sif_", ("singfinance.com.sg",)),
    ("rhb_", ("rhbgroup.com.sg", "rhbgroup.com")),
    ("hsbc_", ("hsbc.com.sg",)),
    ("boc_", ("bankofchina.com",)),
    ("hlf_", ("hlf.com.sg",)),
    ("hl_", ("hlbank.com.sg",)),
    ("icbc", ("singapore.icbc.com.cn",)),
    ("cimb", ("cimb.com.sg",)),
    ("hlf", ("hlf.com.sg",)),
    ("hsbc", ("hsbc.com.sg",)),
    ("ocbc", ("ocbc.com",)),
    ("uob", ("uob.com.sg", "uobgroup.com")),
    ("scb", ("sc.com",)),
    ("sbi", ("statebank",)),
    ("rhb", ("rhbgroup.com.sg", "rhbgroup.com")),
    ("bea", ("hkbea.com.sg",)),
    ("boc", ("bankofchina.com",)),
    ("maybank", ("maybank",)),
    ("dbs", ("dbs.com",)),
    ("citi", ("citibank.com.sg",)),
]

# 显式覆盖（与前缀推断不一致时）
_DEST_HOST_OVERRIDE: dict[str, tuple[str, ...]] = {
    "url": ("citibank.com.sg",),
}


def host_fragments_for_dest(dest: str) -> tuple[str, ...]:
    """返回该 dest 允许的域名片段（用于 host 校验与加分）。"""
    if dest in _DEST_HOST_OVERRIDE:
        return _DEST_HOST_OVERRIDE[dest]
    for prefix, frags in _PREFIX_HOST_RULES:
        if dest.startswith(prefix) or dest == prefix.rstrip("_"):
            return frags
    return ()


def url_matches_dest(dest: str, url: str) -> bool:
    """URL 的 host/path 是否属于该 dest 对应银行。"""
    if not url or not str(url).startswith("http"):
        return False
    frags = host_fragments_for_dest(dest)
    if not frags:
        return True

    p = urlparse(url)
    host = (p.netloc or "").lower()
    path = (p.path or "").lower()

    if not any(f in host for f in frags):
        return False

    if "bankofchina.com" in host and dest.startswith("boc"):
        if "/sg/" not in path:
            return False

    if "sc.com" in host and dest.startswith("scb"):
        if "/sg/" not in path:
            return False

    return True


def filter_urls_for_dest(dest: str, urls: list[str]) -> list[str]:
    """过滤出属于目标银行域名的 URL。"""
    return [u for u in urls if url_matches_dest(dest, u)]


def assert_all_dests_have_host_rules() -> None:
    """启动时校验：每个 dest 都必须能解析到域名规则，否则抛错。"""
    missing = [d for d in sorted(URL_PARAM_DEST_KEYS) if not host_fragments_for_dest(d)]
    if missing:
        raise RuntimeError(f"url_host_rules: 以下 dest 未配置域名约束: {missing}")


# 模块加载时校验，避免新增 dest 忘记加规则
assert_all_dests_have_host_rules()
