# AI_Compare/serper

[Serper.dev](https://serper.dev/) 搜索 provider 的独立流水线。Serper 实际是 Google SERP 的第三方代理。

## 申请 API Key（5 分钟）

1. 打开 <https://serper.dev/> → 右上角 **Sign in** → 用 Google 账号一键登录。
2. 登录后跳到 Dashboard，左侧 **API Key** 直接显示一串密钥，复制即可。
3. 免费额度：**2 500 次查询/账号**，不需要信用卡。后续按 $0.30/1000 次起。

## 设置环境变量

```powershell
$env:SERPER_API_KEY = "<你的key>"
$env:SERPER_GL = "sg"    # 可选，默认 sg
$env:SERPER_HL = "en"    # 可选，默认 en
```

## 怎么跑

```powershell
cd C:\Users\xuwenzhe\Desktop\RateStats\AI_Compare\serper

# 1. 单条冒烟
python test_serper_search.py

# 2. 全量发现
python serper_url_discovery.py
# 输出：output/url_params_ai.xlsx, output/ai_search_discovered_*.xlsx
```

跑完之后：

```powershell
cd ..
python run_eval.py --providers vertex serper --topn 10
```

即可得到 Vertex vs Serper 的命中率/延迟对比表。
