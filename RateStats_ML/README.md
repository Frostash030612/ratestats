# RateStats_ML — 手动 URL 训练 + ML 选链（实验方案）

**不修改** `RateStats_Portable` / `AI_Compare` 原有流程；本目录为独立实验，用于验证：
用手动 `url_params.xlsx` 作训练集，能否提升 AI 搜索候选链接的选链准确率。

## 原理

| 步骤 | 说明 |
|------|------|
| 标签 | `assets/url_params.xlsx` 中每个 `dest` 的黄金 URL = 正样本 |
| 负样本 | 其它 dest 的黄金 URL + 路径扰动 |
| 可选增强 | `ai_search_discovered_*.xlsx` 里 `candidates_top5` 与黄金比对打 0/1 |
| 特征 | 现有 **规则分** `score_url` + 与手动链的路径相似度 + dest 类型等（见 `features.py`） |
| 模型 | `HistGradientBoostingClassifier`（sklearn，本地训练，无需 GPU） |
| 推理 | `picker.pick_best_url_ml`：规则分与 ML 概率加权融合后重排候选 |

抓取 Market 仍走 Portable 的 `bank_all_promo_rates`（与旧方案相同）。

## 快速开始

```text
1. 双击 01_训练模型.bat
2. 双击 02_评估选链准确率.bat     → output/picker_eval_*.xlsx
3. 双击 03_Vertex_ML发现并抓取.bat → output/<tag>/url_params_ai_ml.xlsx
```

或命令行：

```powershell
cd RateStats_ML
pip install -r requirements.txt
python train.py --use-discovery
python evaluate_picker.py
python run_vertex_ml_discovery.py --run-tag test --discover-only
```

## 目录

```text
RateStats_ML/
├── train.py                 # 训练
├── picker.py                # ML 选链
├── evaluate_picker.py       # 规则 vs ML 命中率
├── run_vertex_ml_discovery.py
├── compare_ml_market.py     # 与手动 Market 对比（复用 AI_Compare）
├── models/url_ranker.joblib # 训练产出
├── data/training_set_latest.csv
└── output/                  # 评估与 ML 发现输出
```

## 如何看是否提升

打开 `output/picker_eval_*.xlsx`：

| 指标 | 含义 |
|------|------|
| `baseline_hit_rate` | 原 `pick_best_url` 选对黄金链的比例 |
| `ml_hit_rate` | ML 融合后选对的比例 |
| `ml_improved_rows` | 仅 ML 选对 |
| `ml_regressed_rows` | 仅规则选对、ML 选错 |

再与 `manual_vs_ai_*` 文件夹里 Market 对比表对照（需自跑 `compare_ml_market.py`）。

## 费用

- **训练 / 推理**：本地 sklearn，**无 API 费**
- **03 批处理**：仍调用 Vertex 搜索（与旧方案相同计费）

## 局限与后续

- 当前是 **Learning to Rank 风格二分类**（候选是否为黄金链），不是大语言模型端到端。
- 若候选列表里根本没有黄金 URL，ML 无法凭空猜对（与规则相同）。
- 可扩展：加入更多发现报告、按 dest 分层模型、与 Serper 等多源搜索联合特征。

## 与旧方案关系

| 旧方案 | 本方案 |
|--------|--------|
| `url_discovery_pick.pick_best_url` | `picker.pick_best_url_ml` |
| `url_params_ai.xlsx` | `output/<tag>/url_params_ai_ml.xlsx` |
| `06_一键...bat` | 不改；可用本目录 03 单独试验 |
