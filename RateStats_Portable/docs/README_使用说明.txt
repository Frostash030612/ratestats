RateStats 可迁移运行包（Portable）

目录结构（重组后）：
  RateStats/assets/              手动配置（url_params、email、模板、Vertex 密钥）
  RateStats_Portable/bin/        批处理入口（双击运行）
  RateStats_Portable/src/        Python 源码
  RateStats_Portable/docs/       说明与 requirements.txt
  RateStats/runs/                运行产物（自动生成）

一、在新电脑上怎么用
1) 安装 Python 3.10 或以上（安装时勾选加入 PATH）。
2) 解压整个 RateStats 文件夹到任意路径。
3) 双击运行：RateStats_Portable\bin\01_首次安装依赖.bat
4) 常用入口（均在 bin\ 下）：
   - 03_一键生成Market+彩虹表.bat        手动 url_params
   - 06_一键生成Market彩虹表与AI搜索.bat  手动 + Vertex AI + 对比 + 邮件
5) ML 选链：RateStats_ML\03_Vertex_ML发现并抓取.bat
6) 修改 URL：编辑 RateStats\assets\url_params.xlsx
7) 修改邮件：编辑 RateStats\assets\email_params.log
8) 输出目录：RateStats\runs\YYYYMMDD\

三、命令行手动运行（可选）
在本目录打开终端后执行：
python market_rate_data_generator.py --xlsx-out .
（“.” 表示写入当日 runs/YYYYMMDD/ 目录，见 project_paths.py）

四、常见问题
1) 提示 python 不是命令：
   - 重新安装 Python，并勾选 "Add Python to PATH"。
2) 提示缺依赖：
   - 重新运行 01_首次安装依赖.bat。
3) 某些网站临时抓取失败：
   - 稍后重试，或在脚本里更新对应 URL 参数。

五、说明
- requirements.full.txt 是当前项目完整依赖备份；运行本脚本优先用 requirements.txt 即可。
