# RateStats 便携包 — macOS 使用说明

## 与 Windows 版的差异

| 项目 | Windows | macOS |
|------|---------|-------|
| 用户入口 | `RateStats_Portable/bin/*.bat` | `bin_mac/*.command`（与 `assets` 同级，双击） |
| 实际脚本 | （写在 `.bat` 里） | `bin_mac/sh/*.sh` |
| Python 命令 | `python` / `py -3` | `python3`（推荐 3.11/3.12，勿用 3.14） |
| 定时任务 | 计划任务 `.bat` | LaunchAgent（见下文） |

Python 源码、`assets/` 配置、`runs/` 输出路径与 Windows 版**完全一致**。

## 一、Mac 上首次准备

### 1. 安装 Xcode 命令行工具

```bash
xcode-select --install
```

### 2. 安装 Python 3.11 或 3.12（不要用 3.14）

```bash
brew install python@3.11
```

或从 [python.org](https://www.python.org/downloads/macos/) 安装 **3.12**。

### 3. 解压便携包

例如 `~/RateStats`（路径尽量不要含空格）。

### 4. 赋予可执行权限（只需一次）

```bash
cd ~/RateStats/bin_mac
chmod +x *.command sh/*.sh
cd ~/RateStats/RateStats_ML/bin_mac
chmod +x *.sh
```

### 5. 安装依赖

在 Finder 打开 `RateStats/bin_mac/`，双击 `01_首次安装依赖.command`。

### 6. 配置

- URL：`assets/url_params.xlsx`
- 邮件 / 定时：双击 `打开配置界面.command`
- API Key：双击 `打开API钥匙设置.command`
- Vertex JSON：`assets/ratestatsearch-*.json`

## 二、常用入口

打开 **`RateStats/bin_mac/`**（与 `assets` 同级），双击：

| 文件 | 作用 |
|------|------|
| `01_首次安装依赖.command` | 安装依赖 |
| `03_一键生成Market+彩虹表.command` | 手动 Market + 彩虹表 |
| `06_一键生成Market彩虹表与AI搜索.command` | 完整流程 |
| `打开配置界面.command` | 邮件 + 定时 |
| `打开API钥匙设置.command` | API Key |
| `注册定时任务.command` | 注册 LaunchAgent |
| `立即执行完整流程.command` | 立刻跑定时同款流水线 |

进阶脚本在 `bin_mac/sh/`：

```bash
cd ~/RateStats/bin_mac/sh
./05_run_ai_search.sh
./04_一键巡检URL.sh
./查看定时配置.sh
./卸载定时任务.sh
```

ML：`RateStats_ML/bin_mac/`（仍在 ML 包内）。

输出：`RateStats/runs/YYYYMMDD/`

## 三、定时

改完 `assets/schedule_params.log` 后，再双击 **`bin_mac/注册定时任务.command`**。

`run_script` 相对 `bin_mac`，默认：`sh/run_scheduled_full_pipeline.sh`

## 四、常见问题

**Q: permission denied** → `chmod +x bin_mac/*.command bin_mac/sh/*.sh`  
**Q: 找不到入口** → 在 `RateStats/` 根目录看 `assets` 旁边的 `bin_mac`，不要再进 `RateStats_Portable/` 找。
