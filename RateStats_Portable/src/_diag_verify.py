import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from bs4 import BeautifulSoup
from bank_extractors import impl as _x

from project_paths import ASSETS_DIR
CFG = json.load(open(ASSETS_DIR / "url_params.json", encoding="utf-8"))

def fetch(url, timeout=40, headers=None):
    sess = _x._session(False)
    h = {**dict(sess.headers), **(headers or {})}
    r = sess.get(url, timeout=timeout, headers=h)
    r.raise_for_status()
    return r, BeautifulSoup(r.text, 'lxml')

cols = ('data_source','product_line','rate_1m_pct','rate_3m_pct','rate_6m_pct','rate_9m_pct','rate_12m_pct')

print("############ OCBC append ############")
r, soup = fetch(CFG['ocbc_url'])
ocbc = _x.extract_ocbc_sgd_promo(soup)
rows = _x.append_ocbc_sgd_rows([], ocbc)
print("rows:", len(rows))
for row in rows:
    print("  ", {k: row.get(k) for k in cols})

print("\n############ SingFinance append ############")
r, soup = fetch(CFG['sif_url'])
sif = _x.extract_sif_fd_promo(soup)
rows = _x.append_sif_sgd_rows([], sif)
print("rows:", len(rows))
for row in rows:
    print("  ", {k: row.get(k) for k in cols})
