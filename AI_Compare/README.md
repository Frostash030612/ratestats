# AI_Compare

独立的「AI 搜索效果对比」工具。**不影响** `RateStats_Portable` 主流程。默认以每次跑 Market 后生成的 **`url_YYYYMMDD.xlsx`**（元数据快照）为黄金答案。

## 目录用途

| 路径 | 说明 |
|------|------|
| `queries.py` | 共享查询模板（dest -> query），所有 provider 用同一份 |
| `ground_truth.py` | 读取最新 `url_YYYYMMDD.xlsx` 或指定的 xlsx/json 作为基准 |
| `eval_metrics.py` | hit@1 / hit@3 / hit@5 / MRR / same-host / 域名清洁度 |
| `_discovery_common.py` | 各 provider 子目录共享的发现逻辑（QUERY/FALLBACK/打分/IO） |
| `providers/` | 评测框架适配器（`run_eval.py` 用，统一 `search(query, page_size) -> ProviderResult`） |
| `vertex/`、`bing/`、`serper/`、`brave/`、`tavily/` | 每家 AI 的**独立可运行流水线**：client + 全量 URL 发现 + 冒烟测试 + README |
| `run_eval.py` | 主入口：跑所有 provider，输出 Excel 报告 |
| `run_eval.bat` | Windows 双击入口 |
| `results/` | 输出 `ai_provider_compare_*.xlsx` |
| `raw_cache/` | 每家 provider 的原始返回 JSON 缓存（按 provider/key 分目录） |

## Provider 状态

| Provider | 子目录 | 状态 | 所需环境变量 |
|----------|--------|------|----------|
| Vertex AI Search | `vertex/` | ✅ 已可用，复用 RateStats_Portable 的服务账号 | `GOOGLE_APPLICATION_CREDENTIALS`（默认指向 assets 下 JSON） |
| Bing Web Search v7 | `bing/` | ⚠️ 旧 API 已退役（2025-08-11），只有旧客户能用 | `BING_API_KEY` |
| Serper（Google SERP 代理） | `serper/` | ⏳ 待填 key 即可 | `SERPER_API_KEY` |
| Brave Search | `brave/` | ⏳ 待填 key 即可 | `BRAVE_API_KEY` |
| Tavily AI Search | `tavily/` | ⏳ 待填 key 即可（LLM 时代推荐） | `TAVILY_API_KEY` |

每家子目录下的 `README.md` 写了**怎么申请 key + 怎么跑独立流水线**。

## 申请 API Key

**详细图文步骤见：[SETUP_KEYS.md](SETUP_KEYS.md)**（Serper / Brave / Tavily 三家）

## 怎么用

```powershell
cd AI_Compare
pip install -r requirements.txt

# 查看哪些 provider 已配置
python run_eval.py --list

# 自动对比（默认黄金答案 = 最新 url_YYYYMMDD.xlsx）
python run_eval.py --auto

# 指定某次 Market 目录下的快照
python run_eval.py --auto --gold ..\RateStats_Portable\20260515\url_20260518.xlsx

# 仍用手工 assets/url_params.json
python run_eval.py --auto --gold legacy

# 只指定某几家
python run_eval.py --providers vertex,serper,brave --topn 10

# 双击：自动对比全部已配置 Key
run_compare_all.bat

# 双击：默认也是 --auto；或 run_eval.bat list 只看配置状态
run_eval.bat
```

## 四家 AI 分别发现 URL + 抓取 Market（完整流水线）

除 `run_eval.py`（只比 URL 命中率）外，可用 **`run_all_providers_market.py`** 让 **Vertex / Serper / Brave / Tavily** 各自：

1. 发现链接 → `output/<tag>/url_params_ai_<provider>.xlsx`
2. 抓取利率 → `RateStats_Portable/YYYYMMDD/MarketRateData_<tag>_<Provider>.xlsx`

```powershell
cd AI_Compare
# 仅发现（约 13 分钟 / 四家）
python run_all_providers_market.py --discover-only --skip-missing-keys --also-write-portable-vertex

# 发现 + 四家分别抓取（耗时较长）
python run_all_providers_market.py --skip-missing-keys --also-write-portable-vertex

# 或双击
run_all_providers_market.bat
```

`RateStats_Portable/run_market_rate_ai_search.py` **仍只跑 Vertex**，并写 `MarketRateData_*_AISearch.xlsx`。

输出：`results\ai_provider_compare_YYYYMMDD_HH.mm.xlsx`，包含：

1. **明细表**：每个 key 在各 provider 下的 Top-N、hit@k、MRR
2. **汇总表**：各 provider 的平均 hit@1 / hit@5 / MRR / 平均耗时 / 干净度
3. **分歧表**：仅列 gold ≠ provider_top1 的行，便于人工抽查

## 不会做什么（仅 `run_eval.py`）

- `run_eval.py` 只读黄金答案、只评测 URL，不写 Market
- `run_all_providers_market.py` 会调用 Portable 抓取脚本，但使用独立的 `url_params_ai_<provider>.xlsx`
