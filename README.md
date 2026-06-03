## 利率爬虫（利率链接 → 市场利率调研矩阵）

本项目提供一个脚本 `rate_crawler.py`，用于：

- 读取 `利率链接.xlsx` 中的银行/URL 列表
- 使用 `requests + BeautifulSoup` 抓取页面利率（`BOC` 页面走专门的解析逻辑）
- 将抓取结果按 `202603011市场利率调研.xlsx` 的矩阵格式（`Bank` × `1M/3M/6M/9M/12M/18M/24M`）写入新的 Excel

> 说明：当前环境里没法实际写出 Excel 并运行抓取，但脚本结构是完整的。你在本地/你自己的环境安装依赖后即可运行。

## 依赖

安装：

```bash
pip install -r requirements.txt
```

## 运行

把脚本和 Excel 文件放在同一目录（`利率统计/`）。

最简单运行：

```bash
python rate_crawler.py
```

可选参数（都可不填）：

- `--link`：利率链接文件路径（默认自动识别 `*利率链接*.xlsx` 的那个）
- `--market`：市场利率调研模板路径（默认自动识别 `*202603011*.xlsx`）
- `--out`：输出文件路径（默认输出到 `rate_output_YYYYMMDD.xlsx`）
- `--pause`：请求间隔秒数（默认 0.2）

示例：

```bash
python rate_crawler.py --pause 0.5 --out rate_output.xlsx
```

## BOC 解析逻辑

在 `rate_crawler.py` 的 `parse_boc_rates(html)` 中：

- 遍历页面所有 `<table>`
- 选择包含“`X个月`”且同时包含“数字小数”的表
- 对表内每行：
  - 通过正则提取月份（`(\d+)\s*个?月`）
  - 取行内出现的最后一个利率小数值
  - 将月份映射到 `1M/3M/6M/9M/12M/18M/24M`
- 这样得到 `tenor -> rate(分数形式)`，写入市场矩阵

## 输出格式

输出文件基于 `202603011市场利率调研.xlsx` 修改生成：

- 每个工作表中自动定位包含 `1M/3M/6M/...` 的列
- 自动在左侧找到银行名所在行，然后把利率写入对应列

## 常见问题

- 如果某些银行页面不是“表格直出 HTML”（例如需要 JS 才渲染），通用解析可能失败。可以：
  - 在脚本里给这类 URL 改用 Selenium（脚本目前预留了方案，核心抓取仍以 requests 为主）
- 如果模板里银行名/表头文本与脚本识别规则不一致，可改进 `_extract_tenor_label_from_text()` 与 `write_to_market_matrix()` 的定位逻辑。

