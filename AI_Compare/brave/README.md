# AI_Compare/brave

[Brave Search API](https://api.search.brave.com/) 独立流水线。Brave 是自有索引（非 Google/Bing 转售）。

## 申请 API Key（5 分钟）

1. 打开 <https://api.search.brave.com/> → **Get Started**。
2. 用邮箱注册 → 验证邮箱。
3. 进 Dashboard → **Subscriptions** → 选 **Data for AI - Free**（或 Web Search Free），免费档：
   - 限速 1 query/sec
   - 2 000 次/月
   - 不需要信用卡
4. 进 **API Keys** → **+ Add API Key** → 复制 Subscription Token。

## 设置环境变量

```powershell
$env:BRAVE_API_KEY = "<你的token>"
$env:BRAVE_COUNTRY = "sg"   # 可选
```

## 怎么跑

```powershell
cd AI_Compare\brave

# 1. 单条冒烟
python test_brave_search.py

# 2. 全量发现（默认 sleep=1.1s 以满足 1req/s 限速）
python brave_url_discovery.py
```

跑完 ~50 个查询大概要 ~1 分钟。

## 注意

- 免费档**严格**1 req/s，超过会 429；脚本默认 `--sleep 1.1` 已留好缓冲。
- 如果升级到付费档可以 `python brave_url_discovery.py --sleep 0.2`。
