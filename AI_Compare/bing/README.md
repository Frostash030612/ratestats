# AI_Compare/bing

Bing 搜索 provider 的独立流水线。

## ⚠️ 关于 Bing Search API 的现状（2026 年）

**Microsoft 已经在 2025-08-11 正式停售 Bing Search APIs**，包括：

- `Bing Web Search`
- `Bing News / Image / Video / Visual / Spell Check`
- `Bing Custom Search`

旧订阅会被逐步停用，新客户**无法**通过 Azure Marketplace 再申请到 `Ocp-Apim-Subscription-Key`。
官方公告：<https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement>

### 替代方案

| 方案 | 适合 | 用法 |
|------|------|------|
| **A. Azure AI Foundry → Grounding with Bing Search** | 想继续用 Bing 索引，能接受 Azure Agent SDK 调用 | 在 Azure AI Foundry 项目里启用「Grounding with Bing Search」，按 Azure AI Agents SDK 调用，本目录的简单 HTTP 客户端不可用 |
| **B. 第三方 SERP 代理**（Serper / SerpAPI / Brave / Tavily） | 想要一行 HTTP 请求就拿 Top-N 链接 | 见 `AI_Compare/serper`、`AI_Compare/brave`、`AI_Compare/tavily` |
| **C. 你手里已有未停用的旧 key** | 旧订阅还在运转 | 直接照下文设环境变量即可跑 |

> 如果你**没有**旧 key，建议直接跳到 Serper / Brave / Tavily 三家做对比，本目录留作"以后 Grounding 接入"的占位。

## 怎么获取 API Key（旧路径，仅旧客户可用）

1. 登录 [Azure Portal](https://portal.azure.com/)。
2. 「创建资源 → Bing Search v7」——**新订阅自 2024 年底起已被下架**。如果你的订阅历史里已经有 `Bing Search v7` 资源，仍可用。
3. 进入该资源 → **Keys and Endpoint** → 复制 KEY1 与 Endpoint。
4. 设置环境变量：

```powershell
$env:BING_API_KEY  = "<你的key>"
$env:BING_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"  # 可选
$env:BING_MKT      = "en-SG"                                       # 可选
```

## Grounding with Bing Search（推荐替代）

如果你没有旧 key，推荐走这条：

1. 登录 [Azure AI Foundry](https://ai.azure.com/) 创建一个 Project。
2. 在 Project 内 **Add tool → Grounding with Bing Search**，按 Azure Marketplace 提示开通。
3. 用 `azure-ai-projects` Python SDK 调用 Agent（不是简单的 REST GET）。
4. 由于响应结构和计费方式都和旧 v7 API 完全不同，本目录暂未实现 SDK 调用；后续如果你确认走这条，再单独建 `bing_grounding_client.py`。

## 怎么跑（拿到旧 key 之后）

```powershell
cd C:\Users\xuwenzhe\Desktop\RateStats\AI_Compare\bing

# 1. 单条冒烟测试
python test_bing_search.py

# 2. 全量 URL 发现
python bing_url_discovery.py
# 输出：output/url_params_ai.xlsx, output/ai_search_discovered_*.xlsx
```

跑完之后再用顶层 `python ../run_eval.py --providers bing --topn 10` 做命中率对比。
