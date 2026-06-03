RateStats 可迁移运行包（Portable）

一、这个目录必须保留的文件
1) market_rate_data_generator.py    主入口脚本（必须，统一命名）
2) bank_all_promo_rates.py          实际实现脚本（必须）
3) requirements.txt                 精简依赖（必须）
4) 01_首次安装依赖.bat              新电脑先运行一次
5) 02_一键生成Excel.bat            仅生成 MarketRateData
6) 03_一键生成Market+彩虹表.bat     先生成 MarketRateData 再生成彩虹表

二、在新电脑上怎么用
1) 安装 Python 3.10 或以上（安装时勾选加入 PATH）。
2) 把整个 RateStats_Portable 文件夹拷贝到新电脑任意位置。
3) 双击运行：01_首次安装依赖.bat
4) 双击运行：02_一键生成Excel.bat
5) 如需同时产出彩虹表，双击运行：03_一键生成Market+彩虹表.bat
6) 生成的 Excel 在本目录，文件名类似：
   MarketRateData_YYYYMMDD.xlsx
   彩虹表_从MarketRateData生成_YYYYMMDD.xlsx

三、命令行手动运行（可选）
在本目录打开终端后执行：
python market_rate_data_generator.py --xlsx-out .

四、常见问题
1) 提示 python 不是命令：
   - 重新安装 Python，并勾选 "Add Python to PATH"。
2) 提示缺依赖：
   - 重新运行 01_首次安装依赖.bat。
3) 某些网站临时抓取失败：
   - 稍后重试，或在脚本里更新对应 URL 参数。

五、说明
- requirements.full.txt 是当前项目完整依赖备份；运行本脚本优先用 requirements.txt 即可。
