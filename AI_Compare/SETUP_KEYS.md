# 如何获取 Serper / Brave / Tavily API Key

本文档教你为 `AI_Compare` 配置第三方搜索 Key。配置好后运行 `run_compare_all.bat` 或 `python run_eval.py --auto` 即可自动对比所有已配置的 AI。

> **不要把 Key 写进代码或提交到 Git。**

### 推荐：本机 `keys.txt`（不写进 Windows）

1. 复制 `AI_Compare\keys.txt.example` → 同目录下改名为 **`keys.txt`**
2. 打开 `keys.txt`，填入一行：
   ```text
   SERPER_API_KEY=你的key粘贴在这里
   ```
3. 保存。之后运行 `run_eval.py`、`test_serper_search.py`、`run_compare_all.bat` 时会**自动读取**，无需每次 `$env:`。

验证：

```powershell
cd AI_Compare
python load_keys.py
python run_eval.py --list
```

`keys.txt` 已在 `.gitignore` 里，不会被 Git 提交。

---

## 其他方式（可选）

- 临时：`$env:SERPER_API_KEY = "..."`（关窗口失效）
- 永久：Windows 用户环境变量（见下文第七节）

---

## 一、Serper（Google 搜索结果代理）— 最推荐先试

**官网**：<https://serper.dev/>  
**免费额度**：注册送 **2 500 次**查询（一次性），无需信用卡。

### 步骤

1. 浏览器打开 <https://serper.dev/>
2. 右上角点击 **Sign in**，用 **Google 账号** 登录（一键授权）。
3. 登录后进入 **Dashboard**，左侧或顶部会直接显示你的 **API Key**（一长串字符）。
4. 点击 **Copy** 复制。

### 配置到本机

```powershell
$env:SERPER_API_KEY = "粘贴你的key"
```

### 验证

```powershell
cd AI_Compare\serper
python test_serper_search.py
```

看到 `[OK] 返回链接` 即成功。

---

## 二、Brave Search（Brave 自有索引）

**官网**：<https://api.search.brave.com/>  
**免费额度**：**Data for AI - Free** 档约 **2 000 次/月**，限速 **1 次/秒**，无需信用卡。

### 步骤

1. 打开 <https://api.search.brave.com/>
2. 点击 **Get Started** 或 **Register**，用邮箱注册并验证邮箱。
3. 登录后进入 **Dashboard**。
4. 左侧 **Subscriptions** → 选择 **Data for AI** 下的 **Free** 计划（若未订阅则 Subscribe）。
5. 左侧 **API Keys** → 点击 **+ Add API Key** → 命名（如 `ratestats`）→ 创建。
6. 复制生成的 **Subscription Token**（即 API Key）。

### 配置到本机

```powershell
$env:BRAVE_API_KEY = "粘贴你的token"
$env:BRAVE_COUNTRY = "sg"   # 可选，默认已是 sg
```

### 验证

```powershell
cd AI_Compare\brave
python test_brave_search.py
```

> Brave 免费档限速 1 req/s，全量评测时 `run_eval.py --auto` 会自动把间隔调到至少 1.1 秒。

---

## 三、Tavily（专为 LLM/Agent 设计的搜索）

**官网**：<https://tavily.com/>  
**免费额度**：**1 000 次/月**，Key 以 `tvly-` 开头，无需信用卡。

### 步骤

1. 打开 <https://tavily.com/>
2. 点击 **Get Free API Key** 或 **Sign Up**。
3. 用 **Google** 或 **GitHub** 登录。
4. 进入 Dashboard，页面顶部或 **API Keys** 区域复制 Key（格式类似 `tvly-xxxxxxxxxxxxxxxx`）。

### 配置到本机

```powershell
$env:TAVILY_API_KEY = "tvly-xxxxxxxx"
$env:TAVILY_DEPTH = "basic"   # 可选：basic（快）或 advanced（更深更慢）
```

### 验证

```powershell
cd AI_Compare\tavily
python test_tavily_search.py
```

---

## 四、Vertex（你已有，无需新 Key）

Vertex 使用 `RateStats_Portable/assets/ratestatsearch-*.json` 服务账号，一般**不用额外操作**。  
若移动了密钥文件，可设置：

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "RateStats_Portable\assets\ratestatsearch-f5f95dab974f.json"
```

---

## 五、一次性设置多个 Key（推荐）

在**同一个 PowerShell 窗口**里执行（改为你自己的 Key）：

```powershell
$env:SERPER_API_KEY = "你的serper_key"
$env:BRAVE_API_KEY  = "你的brave_token"
$env:TAVILY_API_KEY = "tvly-你的tavily_key"

cd AI_Compare
python run_eval.py --list
```

`--list` 会显示哪些 provider 已检测到。

---

## 六、跑横向对比

### 方式 A：双击（自动检测所有已配置 Key）

双击：`AI_Compare\run_compare_all.bat`

### 方式 B：命令行

```powershell
cd AI_Compare
python run_eval.py --auto
```

报告输出：`results\ai_provider_compare_YYYYMMDD_HH.mm.xlsx`

---

## 七、永久保存环境变量（可选）

若不想每次开 PowerShell 都重新 `$env:`，可在 Windows 里：

1. **设置** → **系统** → **关于** → **高级系统设置** → **环境变量**
2. 在「用户变量」里 **新建**：
   - 变量名 `SERPER_API_KEY`，值 = 你的 key
   - 同理 `BRAVE_API_KEY`、`TAVILY_API_KEY`
3. **确定** 后**重新打开** PowerShell / 终端再运行脚本。

---

## 常见问题

| 现象 | 原因 | 处理 |
|------|------|------|
| `SERPER_API_KEY not set` | 未设环境变量或窗口关了 | 重新 `$env:SERPER_API_KEY=...` |
| Brave HTTP 429 | 超过 1 次/秒 | 用 `--auto`（已自动放慢）；或 `--sleep 1.2` |
| Serper 402 / 额度用完 | 免费 2500 次用尽 | 充值或换 Brave/Tavily |
| `--list` 只有 vertex | 另三家 Key 未设 | 按上文设 `$env:...` 后再 `--list` |

---

## 关于 Bing

微软已于 **2025-08-11** 停售 Bing Search API，新客户无法申请。若你没有旧订阅，请用 **Serper / Brave / Tavily** 对比，详见 `bing/README.md`。
