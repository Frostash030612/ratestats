# AI_Compare/vertex

Vertex AI Search 完整脚本副本（**仅用于参考 / 独立测试**，不会影响 `RateStats_Portable` 的主流程）。

## 与原版的差异

| 文件 | 与 `RateStats_Portable/` 同名脚本的区别 |
|------|------------------------------------------|
| `vertex_search_client.py` | 默认密钥路径改为 `../../RateStats_Portable/assets/ratestatsearch-*.json`，避免重复存放敏感文件 |
| `test_vertex_search.py` | 同上：密钥路径指向 RateStats_Portable/assets |

**完整 URL 发现**（选链 / 打分与 Serper 等共用 `RateStats_Portable/url_discovery_pick.py`）请用主目录脚本，勿在本子目录维护第二份逻辑：

```powershell
cd C:\Users\xuwenzhe\Desktop\RateStats\RateStats_Portable
python vertex_url_discovery.py
# 或
cd C:\Users\xuwenzhe\Desktop\RateStats\AI_Compare
python run_all_providers_market.py --providers vertex --discover-only
```

## 怎么用

### 1. 单条搜索冒烟测试

```powershell
cd C:\Users\xuwenzhe\Desktop\RateStats\AI_Compare\vertex
python test_vertex_search.py
```

## 注意

- 本目录仅保留 **API 客户端 + 冒烟测试**；发现与打分以 `RateStats_Portable` 为准。
- 后续如果要对比其他 AI（Bing / Serper / Brave），可以在 `AI_Compare/<provider>/` 下创建同样形态的子目录，互不影响。
