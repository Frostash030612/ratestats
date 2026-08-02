# RateStats_ML — 手动 URL 训练 + ML 选链（实验方案）



**不修改** `RateStats_Portable` / `AI_Compare` 原有流程；本目录为独立实验，用于提升 AI 搜索候选的选链准确率。



## 推荐流程（按顺序）



| 步骤 | 批处理 / 命令 | 作用 |

|------|----------------|------|

| 1 | `01_训练模型.bat` | `train.py --use-discovery`：黄金标签 + **runs/** 发现报告 + **典型错链**负样本 + 平衡权重 |

| 2 | `02_评估选链准确率.bat` | `evaluate_picker.py`：总表 + **by_dest** + **baseline_miss_dest** |

| 3 | `04_调参融合权重.bat` | `tune_picker.py` → `models/picker_tuning.json` |

| 4 | `03_Vertex_ML发现并抓取.bat` | 使用调参后的融合逻辑生成 `runs/YYYYMMDD/` |



命令行等价：



```powershell

cd RateStats_ML

pip install -r requirements.txt

python train.py --use-discovery

python evaluate_picker.py

python tune_picker.py

python run_vertex_ml_discovery.py --run-tag 20260603 --fetch

```



进阶训练：



```powershell

# 减弱「只复制 rule_score」

python train.py --use-discovery --drop-rule-score



# 追加自定义错链：编辑 data/hard_negatives.csv（列 dest,url,note）

```



## 数据与特征



| 项目 | 说明 |

|------|------|

| 正样本 | `assets/url_params.xlsx` 各 dest 黄金 URL |

| 负样本 | 其它 dest URL、路径扰动、`hard_negatives.py` 内置错链、`data/hard_negatives.csv` |

| 发现报告 | 递归扫描 `runs/**` 的 `ai_search_discovered*.xlsx` |

| 特征 | `rule_score` + **path/intent 子项** + **错页模式**（premier/business/API 等），见 `features.py` |

| 推理 | `picker.py` 读取 `picker_tuning.json`；规则分差大时跳过 ML（`ml_skip_clear_rule_*`） |



## 评估表说明（`output/picker_eval_*.xlsx`）



| Sheet | 含义 |

|-------|------|

| `summary` | 总体 baseline / ML 命中率 |

| `by_dest` | 每个 dest 命中率，**优先改 baseline_miss_dest 里的行** |

| `baseline_miss_dest` | 规则未满分 dest |

| `by_category` | board / promo / api 分组 |



## 目录



```text

RateStats_ML/

├── train.py / tune_picker.py / evaluate_picker.py

├── hard_negatives.py / ml_discovery_dirs.py / picker_config.py

├── models/url_ranker.joblib

├── models/picker_tuning.json   # 04 调参产出

├── data/hard_negatives.csv     # 可手工追加错链

└── output/                   # 评估与调参网格结果

```



## 与旧方案关系



| 旧方案 | 本方案 |

|--------|--------|

| `pick_best_url` | `pick_best_url_ml`（融合 + 调参） |

| `url_params_ai.xlsx` | `runs/<tag>/url_params_ai_ml.xlsx` |



Market 抓取仍用 Portable `bank_all_promo_rates`。


