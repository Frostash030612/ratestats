# AI_Compare/tavily

[Tavily AI Search](https://tavily.com/) 独立流水线。

Tavily 专门为 LLM/Agent 设计：把搜索结果做了清洗，token 紧凑，特别适合做"链接发现"。

## 申请 API Key（3 分钟）

1. 打开 <https://tavily.com/> → **Get Free API Key**。
2. 用 Google / GitHub 登录。
3. 进 Dashboard → 复制顶部 **API Key**（以 `tvly-` 开头）。
4. 免费额度：**1000 次/月**，不需信用卡。

## 设置环境变量

```powershell
$env:TAVILY_API_KEY = "tvly-xxxxxxxx"
$env:TAVILY_DEPTH = "basic"   # basic 或 advanced，advanced 更深更慢但更准
```

## 怎么跑

```powershell
cd AI_Compare\tavily

python test_tavily_search.py
python tavily_url_discovery.py
```
