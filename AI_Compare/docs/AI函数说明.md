# AI 脚本函数说明手册

> 已在源码中为各函数补充中文 docstring；本文档为速查索引。  
> 更新日期：2026-05-21

---

## 一、RateStats_Portable（发现 + 选链 + Vertex 单跑）

### `url_discovery_config.py` — 全局模式

| 函数 | 作用 |
|------|------|
| `get_intent_mode()` | 读 `RATESTATS_INTENT_MODE`，返回 `relaxed` 或 `strict` |
| `is_relaxed_mode()` | 是否为宽松模式（默认，利于银行改版） |

### `url_discovery_pick.py` — 选链核心（四家 AI 共用）

| 函数 | 作用 |
|------|------|
| `score_url(url, dest, reference_url=...)` | 对候选 URL 综合打分（域名、路径、促销/挂牌词、ICBC 页 ID、意图软加分等） |
| `pick_best_url(candidates, dest, fallback)` | 从搜索返回链接中选最终 URL；返回 `(url, source_tag)` |

### `url_host_rules.py` — 银行域名

| 函数 | 作用 |
|------|------|
| `host_fragments_for_dest(dest)` | 该 dest 允许的域名片段 |
| `url_matches_dest(dest, url)` | URL 是否属于目标银行（含 BOC/SCB 的 /sg/ 校验） |
| `filter_urls_for_dest(dest, urls)` | 过滤出合法银行域名的 URL 列表 |
| `assert_all_dests_have_host_rules()` | 启动校验：每个 dest 必须有域名规则 |

### `url_path_rules.py` — 路径加减分

| 函数 | 作用 |
|------|------|
| `path_score_adjustment(dest, url)` | 按银行/产品页路径加减分（Maybank JSP、OCBC 个人页、DBS API 等） |

### `url_dest_intent.py` — 路径意图

| 函数 | 作用 |
|------|------|
| `_norm(url)` | URL 转小写 |
| `url_meets_dest_intent(dest, url)` | strict：路径必须满足意图；relaxed：仅排除硬拒绝 |
| `filter_by_intent(dest, urls)` | 过滤满足意图的 URL |
| `_path_tokens(url)` | 提取路径 token，用于与手动 URL 比对相似度 |
| `url_hard_reject(dest, url)` | 宽松模式下仍一票否决的错页 |
| `intent_score_adjustment(dest, url, reference_url=...)` | 宽松模式软加分/减分（参考 fallback URL） |

### `url_pick_refinement.py` — 候选精炼

| 函数 | 作用 |
|------|------|
| `refine_ranked_candidates_strict(...)` | 严格：过滤不符合意图；特殊 dest 强制 API/JSP/zh-sg 等 |
| `refine_ranked_candidates_relaxed(...)` | 宽松：仅去掉硬拒绝项 |
| `refine_ranked_candidates(...)` | 按当前模式分发到 strict/relaxed |

### `url_fallback_resolver.py` — 回退 URL

| 函数 | 作用 |
|------|------|
| `_code_defaults()` | 代码内 `DEFAULT_*` URL 表 |
| `build_fallback_map(manual_xlsx=...)` | 优先 `url_params.xlsx`，未配置 dest 用代码默认 |

### `vertex_search_client.py` — Vertex API

| 函数 | 作用 |
|------|------|
| `_key_file()` | 服务账号 JSON 路径 |
| `get_access_token()` | OAuth2 token |
| `search_url(query, page_size=8)` | 调用 Discovery Engine 搜索 |
| `extract_links(payload)` | 从 JSON 响应解析 http 链接 |

### `vertex_url_discovery.py` — Vertex 全量发现

| 类/函数 | 作用 |
|---------|------|
| `DiscoverResult` | 单条发现结果 dataclass |
| `_canonical_friendly_keys()` | dest → Excel 列名 key |
| `pick_best_url(...)` | 封装共享选链，source `ai`→`vertex` |
| `discover_all(...)` | 遍历全部 dest：搜索→选链 |
| `write_url_params_xlsx(...)` | 写 `url_params_ai.xlsx` |
| `write_discovery_report(...)` | 写发现明细报告 |
| `run_discovery(...)` | 一键发现 + 写文件 |

### `run_market_rate_ai_search.py` — Vertex 生产入口

| 函数 | 作用 |
|------|------|
| `_sync_ai_json()` | xlsx → `url_params_ai.json` |
| `_run_fetch(market_out)` | 用 AI 配置抓取 Market |
| `main()` | CLI：发现（可选）→ 同步 → 抓取 |

### `sync_url_params_ai_to_json.py`

| 函数 | 作用 |
|------|------|
| `main()` | `assets/url_params_ai.xlsx` → `.json` |

---

## 二、AI_Compare（四家对比 + 评测）

### `_discovery_common.py` — 共享发现

| 类/函数 | 作用 |
|---------|------|
| `DiscoverResult` | 发现结果结构 |
| `canonical_friendly_keys()` | dest → key |
| `discover_all(search_fn, source_tag, ...)` | 对每个 dest 调 `search_fn(query)` 再 `pick_best_url` |
| `write_url_params_xlsx(...)` | 写 AI 配置 xlsx |
| `write_discovery_report(...)` | 写发现报告 |
| `default_output_paths(provider_dir)` | 默认输出路径 |
| `run_provider_discovery(...)` | 发现 + 写两份 xlsx |

### `load_keys.py`

| 函数 | 作用 |
|------|------|
| `_parse_line(line)` | 解析 `KEY=VALUE` 行 |
| `load_keys_from_file(path)` | 加载到环境变量 |
| `ensure_keys_loaded(...)` | 自动找 `keys.txt` / `keys.env` |
| `main()` | 命令行检查 Key 是否加载 |

### `run_all_providers_market.py` — 四家批量

| 函数 | 作用 |
|------|------|
| `_provider_configured(name)` | 是否已配置 Key/服务账号 |
| `_discover_api_provider(...)` | Serper/Brave/Tavily 发现 |
| `sync_url_json(xlsx, json)` | 单 provider 配置同步 JSON |
| `fetch_market(url_xlsx, market_out)` | 抓取 Market |
| `run_one_provider(...)` | 单家：发现→同步→抓取 |
| `main()` | CLI 循环四家 |

### 搜索客户端（结构相同）

**`serper/serper_search_client.py` / `brave/brave_search_client.py` / `tavily/tavily_search_client.py`**

| 函数 | 作用 |
|------|------|
| `_api_key()` | 读环境变量 API Key |
| `search(query, page_size)` | HTTP 搜索，返回原始 JSON |
| `extract_links(payload)` | 解析链接列表 |
| `search_urls(query)` | **发现入口**：直接返回 URL 列表 |

**单独发现脚本**：`serper_url_discovery.main()` / `brave_url_discovery.main()` / `tavily_url_discovery.main()` — 只跑发现，输出到各 `*/output/`。

---

## 三、对比与评测脚本

### `compare_market_data.py` — 手动 vs AI 数据

| 函数 | 作用 |
|------|------|
| `_pct_cols(df)` | 利率列（`*_pct`） |
| `_row_key(row, key_cols)` | 行对齐键 |
| `_norm_rate(v)` / `_rates_equal(a,b,tol)` | 利率规范化与容差比较 |
| `compare_sheet(df_m, df_a, sheet, tol)` | 单 sheet 行级对比 |
| `compare_metadata_urls(manual, ai)` | 元数据 URL 对比 |
| `run_compare(...)` | 生成 `market_data_compare_*.xlsx` |
| `main()` | CLI |

### `compare_all_providers_market.py`

| 函数 | 作用 |
|------|------|
| `_provider_label(ai_path)` | 从文件名识别 provider |
| `main()` | 批量对多家 AI 跑 `run_compare` 并汇总 |

### `compare_manual_vs_ai.py`

| 函数 | 作用 |
|------|------|
| `run(manual_xlsx, ai_xlsx, out_dir)` | 配置表 URL 逐 dest 对比 |
| `main()` | CLI |

### `audit_ai_issues.py`

| 函数 | 作用 |
|------|------|
| `audit_urls(...)` | 链接空/错域名/错行 |
| `audit_data_gaps(...)` | 缺银行、行数差 |
| `_meta_errors(xlsx)` | 元数据抓取失败 |
| `main()` | 写 `ai_issues_audit_*.xlsx` |

### `ground_truth.py` — 评测黄金答案

| 函数 | 作用 |
|------|------|
| `load_gold(path)` | 从 xlsx/json 读 dest→url |
| `find_latest_url_snapshot(...)` | 找最新 `url_YYYYMMDD.xlsx` |
| `resolve_gold_path(...)` | 解析评测用黄金路径 |

### `eval_metrics.py`

| 函数 | 作用 |
|------|------|
| `normalize_url(u)` | URL 规范化 |
| `rank_in_topn(gold, candidates)` | 黄金 URL 在候选中的 1-based 排名 |
| `hit_at_k(rank, k)` | Hit@K |
| `mrr(rank)` | MRR |
| `same_host_rank(gold, candidates)` | 同域命中排名 |

### `run_eval.py` — 仅 URL 命中率

| 函数 | 作用 |
|------|------|
| `run(providers, topn, ...)` | 各 provider 搜索 vs 黄金 URL，写 `ai_provider_compare_*.xlsx` |
| `cmd_list()` | 列出 Key 配置状态 |
| `main()` | CLI |

---

## 四、调用关系简图

```
search_urls / search_url + extract_links
        ↓
discover_all (vertex_url_discovery 或 _discovery_common)
        ↓
pick_best_url → url_discovery_pick
        ├─ score_url ← url_host_rules, url_path_rules, url_dest_intent
        └─ refine_ranked_candidates ← url_pick_refinement
        ↓
write_url_params_xlsx → bank_all_promo_rates (--url-config)
        ↓
compare_market_data / compare_all_providers_market
```

---

## 五、如何查看源码注释

在 IDE 中打开上述 `.py` 文件，鼠标悬停函数名即可看到 docstring；或运行：

```powershell
python -c "import inspect; from url_discovery_pick import pick_best_url; print(pick_best_url.__doc__)"
```

（需在 `RateStats_Portable` 目录下执行。）
