RateStats_Portable 便携包目录说明
================================

本目录为 Windows / 共享源码部分：

  bin/        Windows 批处理（.bat）
  src/        Python 源码（一般无需手动改）
  docs/       说明文档与 requirements.txt

macOS 双击入口已提到项目根目录（与 assets 同级）：

  ../bin_mac/*.command
  ../bin_mac/sh/*.sh

手动配置：

  ../assets/          与 RateStats_Portable 同级
    url_params.xlsx
    email_params.log
    MarketRateData_template.xlsx
    ratestatsearch-*.json

运行产物：

  ../runs/YYYYMMDD/

新电脑（Windows）：
  1. 安装 Python 3.10+（勾选 Add to PATH）
  2. 双击 bin\01_首次安装依赖.bat
  3. 按需双击 bin\03_… / bin\06_…

详细说明见 docs\README_使用说明.txt

配置界面：
  邮件 / 定时：
    Windows: bin\打开配置界面.bat
    macOS:   双击 ../bin_mac/打开配置界面.command
  API Key：
    Windows: bin\打开API钥匙设置.bat
    macOS:   双击 ../bin_mac/打开API钥匙设置.command

macOS：
  chmod +x ../bin_mac/*.command ../bin_mac/sh/*.sh
  然后只双击 ../bin_mac 下的 *.command
