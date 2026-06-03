# URL 巡检清单（脚本版）

## 使用方式

- 双击运行：`04_一键巡检URL.bat`
- 或命令行运行：`python check_url_health.py`

## 脚本输出

- 控制台输出每个 URL 的：
  - `key`
  - `risk`（high / medium / normal）
  - `status`（HTTP 状态码）
  - `final_url`（最终跳转地址）
  - `note`（redirected / http_error / 异常信息）
- 自动生成报告文件：
  - `url_health_report_YYYYMMDD_HHMMSS.json`

## 高风险重点检查项

以下 key 被标记为 `high`，建议每日关注：

- `boc_url`
- `boc_board_url`
- `rhb_board_pdf_url`
- `rhb_fcy_board_pdf_url`

## 判定建议

- `status >= 400`：立即处理（页面失效或策略变更）
- `final_url != url`：关注跳转是否切换到新路径
- `note` 非空：作为预警信息进入人工复核
