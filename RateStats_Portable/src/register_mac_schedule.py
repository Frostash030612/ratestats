#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根据 assets/schedule_params.log 注册 / 更新 / 卸载 macOS LaunchAgent。"""
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import textwrap
from pathlib import Path

from project_paths import ASSETS_DIR, BIN_MAC_DIR, get_runs_root


WEEKDAY_MAP = {
    "sun": 0,
    "sunday": 0,
    "mon": 1,
    "monday": 1,
    "tue": 2,
    "tues": 2,
    "tuesday": 2,
    "wed": 3,
    "wednesday": 3,
    "thu": 4,
    "thur": 4,
    "thurs": 4,
    "thursday": 4,
    "fri": 5,
    "friday": 5,
    "sat": 6,
    "saturday": 6,
}
WEEKDAY_NAMES = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]


def load_kv(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(f"缺少配置: {path}")
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def parse_bool(v: str) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_weekdays(raw: str) -> list[int] | None:
    """返回 weekday 列表；None 表示每天（不限制 Weekday）。"""
    s = (raw or "").strip().lower()
    if not s or s in {"daily", "every", "*"}:
        return None
    if s in {"weekdays", "workday", "workdays"}:
        return [1, 2, 3, 4, 5]
    if s in {"weekend", "weekends"}:
        return [0, 6]
    days: list[int] = []
    for part in s.replace(";", ",").split(","):
        p = part.strip()
        if not p:
            continue
        if p.isdigit():
            d = int(p)
            if d < 0 or d > 6:
                raise ValueError(f"weekday 数字应在 0–6: {p}")
            days.append(d)
        elif p in WEEKDAY_MAP:
            days.append(WEEKDAY_MAP[p])
        else:
            raise ValueError(f"无法识别的 weekday: {p}")
    # 去重保序
    seen: set[int] = set()
    uniq: list[int] = []
    for d in days:
        if d not in seen:
            seen.add(d)
            uniq.append(d)
    if not uniq:
        raise ValueError("weekday 为空")
    return uniq


def parse_times(cfg: dict[str, str]) -> list[tuple[int, int]]:
    times_raw = (cfg.get("times") or "").strip()
    if times_raw:
        out: list[tuple[int, int]] = []
        for part in times_raw.replace(";", ",").split(","):
            p = part.strip()
            if not p:
                continue
            if ":" not in p:
                raise ValueError(f"times 格式应为 HH:MM，收到: {p}")
            hs, ms = p.split(":", 1)
            h, m = int(hs), int(ms)
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError(f"非法时刻: {p}")
            out.append((h, m))
        if not out:
            raise ValueError("times 为空")
        return out
    h = int(cfg.get("hour", "17"))
    m = int(cfg.get("minute", "55"))
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"hour/minute 非法: {h}:{m}")
    return [(h, m)]


def plist_intervals(weekdays: list[int] | None, times: list[tuple[int, int]]) -> str:
    blocks: list[str] = []
    day_list = weekdays if weekdays is not None else [None]
    for d in day_list:
        for h, m in times:
            lines = ["    <dict>"]
            if d is not None:
                lines.append(f"      <key>Weekday</key><integer>{d}</integer>")
            lines.append(f"      <key>Hour</key><integer>{h}</integer>")
            lines.append(f"      <key>Minute</key><integer>{m}</integer>")
            lines.append("    </dict>")
            blocks.append("\n".join(lines))
    if len(blocks) == 1:
        return blocks[0]
    return "    <array>\n" + "\n".join(blocks) + "\n    </array>"


def describe(weekdays: list[int] | None, times: list[tuple[int, int]]) -> str:
    if weekdays is None:
        day_s = "每天"
    else:
        day_s = "、".join(WEEKDAY_NAMES[d] for d in weekdays)
    time_s = "、".join(f"{h:02d}:{m:02d}" for h, m in times)
    return f"{day_s} {time_s}"


def launchctl_unload(plist: Path, label: str) -> None:
    uid = os.getuid() if hasattr(os, "getuid") else None
    domain = f"gui/{uid}" if uid is not None else None
    if domain and plist.is_file():
        subprocess.run(
            ["launchctl", "bootout", domain, str(plist)],
            check=False,
            capture_output=True,
        )
    if plist.is_file():
        subprocess.run(["launchctl", "unload", str(plist)], check=False, capture_output=True)
    subprocess.run(["launchctl", "remove", label], check=False, capture_output=True)


def launchctl_load(plist: Path, label: str) -> tuple[bool, str]:
    """注册到当前用户 LaunchAgent；优先 bootstrap（macOS 13+），失败再试 load。"""
    uid = os.getuid() if hasattr(os, "getuid") else None
    errs: list[str] = []
    if uid is not None:
        domain = f"gui/{uid}"
        r = subprocess.run(
            ["launchctl", "bootstrap", domain, str(plist)],
            capture_output=True,
            text=True,
        )
        if r.returncode == 0:
            subprocess.run(
                ["launchctl", "enable", f"{domain}/{label}"],
                check=False,
                capture_output=True,
            )
            return True, "launchctl bootstrap OK"
        errs.append((r.stderr or r.stdout or "").strip() or f"bootstrap exit={r.returncode}")
        # 已加载时 bootstrap 会报错，尝试 bootout 后再 bootstrap
        subprocess.run(
            ["launchctl", "bootout", domain, str(plist)],
            check=False,
            capture_output=True,
        )
        r2 = subprocess.run(
            ["launchctl", "bootstrap", domain, str(plist)],
            capture_output=True,
            text=True,
        )
        if r2.returncode == 0:
            subprocess.run(
                ["launchctl", "enable", f"{domain}/{label}"],
                check=False,
                capture_output=True,
            )
            return True, "launchctl bootstrap OK (retry)"
        errs.append((r2.stderr or r2.stdout or "").strip() or f"bootstrap retry exit={r2.returncode}")

    r3 = subprocess.run(["launchctl", "load", str(plist)], capture_output=True, text=True)
    if r3.returncode == 0:
        return True, "launchctl load OK"
    errs.append((r3.stderr or r3.stdout or "").strip() or f"load exit={r3.returncode}")
    return False, "\n".join(e for e in errs if e)


def launchctl_is_loaded(label: str) -> bool:
    r = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    text = r.stdout or ""
    return any(label in line for line in text.splitlines())


def launchd_path() -> str:
    """定时任务专用 PATH：保证能找到 Homebrew / 官网 Python。"""
    extras = [
        "/usr/local/bin",
        "/opt/homebrew/bin",
        "/usr/local/opt/python@3.11/bin",
        "/usr/local/opt/python@3.12/bin",
        "/opt/homebrew/opt/python@3.11/bin",
        "/opt/homebrew/opt/python@3.12/bin",
        "/Library/Frameworks/Python.framework/Versions/3.11/bin",
        "/Library/Frameworks/Python.framework/Versions/3.12/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    ]
    # 去重保序，并接上当前 PATH（若有）
    seen: set[str] = set()
    parts: list[str] = []
    for p in extras + os.environ.get("PATH", "").split(":"):
        p = p.strip()
        if not p or p in seen:
            continue
        seen.add(p)
        parts.append(p)
    return ":".join(parts)


def build_plist(
    *,
    label: str,
    script: Path,
    workdir: Path,
    stdout_log: Path,
    stderr_log: Path,
    weekdays: list[int] | None,
    times: list[tuple[int, int]],
) -> str:
    interval_xml = plist_intervals(weekdays, times)
    # StartCalendarInterval 若为多个 dict，需要 array；单个 dict 直接放
    if interval_xml.strip().startswith("<array>"):
        sci = f"  <key>StartCalendarInterval</key>\n{interval_xml}\n"
    else:
        sci = f"  <key>StartCalendarInterval</key>\n{interval_xml}\n"
    path_xml = launchd_path().replace("&", "&amp;")
    return textwrap.dedent(
        f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
          <key>Label</key>
          <string>{label}</string>
          <key>ProgramArguments</key>
          <array>
            <string>/bin/bash</string>
            <string>{script.as_posix()}</string>
          </array>
          <key>WorkingDirectory</key>
          <string>{workdir.as_posix()}</string>
          <key>EnvironmentVariables</key>
          <dict>
            <key>PATH</key>
            <string>{path_xml}</string>
            <key>PYTHONUTF8</key>
            <string>1</string>
          </dict>
        {sci}  <key>StandardOutPath</key>
          <string>{stdout_log.as_posix()}</string>
          <key>StandardErrorPath</key>
          <string>{stderr_log.as_posix()}</string>
          <key>RunAtLoad</key>
          <false/>
        </dict>
        </plist>
        """
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="按 assets/schedule_params.log 注册 Mac 定时任务")
    ap.add_argument(
        "--config",
        default=str(ASSETS_DIR / "schedule_params.log"),
        help="配置文件路径",
    )
    ap.add_argument("--unregister", action="store_true", help="仅卸载，不重新注册")
    ap.add_argument("--show", action="store_true", help="只打印解析后的计划，不改系统")
    args = ap.parse_args(argv)

    if platform.system() != "Darwin" and not args.show:
        print("[ERROR] 本脚本用于 macOS LaunchAgent。当前系统:", platform.system(), file=sys.stderr)
        print("        可在 Mac 上双击 bin_mac/注册定时任务.command", file=sys.stderr)
        return 1

    cfg_path = Path(args.config)
    cfg = load_kv(cfg_path)
    label = (cfg.get("label") or "com.ratestats.fullpipeline").strip()
    run_script = (cfg.get("run_script") or "sh/run_scheduled_full_pipeline.sh").strip()
    bin_mac = BIN_MAC_DIR
    script = (bin_mac / run_script).resolve()
    # 兼容旧配置：run_script=run_scheduled_full_pipeline.sh
    if not script.is_file() and "/" not in run_script and "\\" not in run_script:
        alt = (bin_mac / "sh" / run_script).resolve()
        if alt.is_file():
            script = alt
    plist = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
    log_dir = get_runs_root() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    if args.unregister or not parse_bool(cfg.get("schedule_enabled", "true")):
        launchctl_unload(plist, label)
        if plist.exists():
            plist.unlink()
        print(f"[OK] 已卸载任务: {label}")
        if not parse_bool(cfg.get("schedule_enabled", "true")):
            print("[INFO] schedule_enabled=false，如需启用请改 assets/schedule_params.log 后重新注册")
        return 0

    weekdays = parse_weekdays(cfg.get("weekday", "wed"))
    times = parse_times(cfg)
    desc = describe(weekdays, times)

    if args.show:
        print(f"config:  {cfg_path}")
        print(f"label:   {label}")
        print(f"script:  {script}")
        print(f"when:    {desc}")
        print(f"plist:   {plist}")
        return 0

    if not script.is_file():
        print(f"[ERROR] 找不到执行脚本: {script}", file=sys.stderr)
        return 1

    # Desktop/Documents 对 launchd 后台任务常被 TCC 拒绝（Operation not permitted）
    forbidden_markers = ("/Desktop/", "/Documents/", "/Downloads/")
    script_posix = script.as_posix()
    if any(m in script_posix for m in forbidden_markers):
        print("[WARN] 当前 RateStats 位于桌面/文稿/下载目录。", file=sys.stderr)
        print("       macOS 常禁止 launchd 后台访问这些位置，会表现为：", file=sys.stderr)
        print("         Operation not permitted / getcwd ... Operation not permitted", file=sys.stderr)
        print("       建议：将整个 RateStats 移到如 ~/RateStats 后重新注册；", file=sys.stderr)
        print("       或：系统设置 → 隐私与安全性 → 完全磁盘访问权限 → 添加 /bin/bash", file=sys.stderr)
        print(file=sys.stderr)

    os.chmod(script, 0o755)
    common = bin_mac / "sh" / "_common.sh"
    if common.is_file():
        os.chmod(common, 0o755)

    agents = Path.home() / "Library" / "LaunchAgents"
    agents.mkdir(parents=True, exist_ok=True)

    launchctl_unload(plist, label)
    # WorkingDirectory 不要落在 Desktop（即便脚本可用，getcwd 也会失败）
    workdir = Path.home()
    xml = build_plist(
        label=label,
        script=script,
        workdir=workdir,
        stdout_log=log_dir / "launchd_stdout.log",
        stderr_log=log_dir / "launchd_stderr.log",
        weekdays=weekdays,
        times=times,
    )
    plist.write_text(xml, encoding="utf-8")

    ok, detail = launchctl_load(plist, label)
    if not ok:
        print(detail, file=sys.stderr)
        print(f"[ERROR] launchctl 注册失败: {plist}", file=sys.stderr)
        print("提示：必须在 Mac 上运行；只保存 schedule_params.log 不会写入系统。", file=sys.stderr)
        return 1

    print("[OK] 已按 schedule_params.log 注册/更新定时任务")
    print(f"  方式: {detail}")
    print(f"  配置: {cfg_path}")
    print(f"  时间: {desc}")
    print(f"  任务: {label}")
    print(f"  脚本: {script}")
    print(f"  plist:{plist}")
    print(f"  日志: {log_dir}/launchd_*.log")
    if launchctl_is_loaded(label):
        print(f"  状态: launchctl list 已能看到 {label}")
    else:
        print(f"  状态: 警告 — launchctl list 暂未看到 {label}，请执行: launchctl list | grep ratestats")
    print()
    print("说明：这是 LaunchAgent，不会出现在「系统设置 → 登录项」里。")
    print("改时间后：编辑 assets/schedule_params.log → 再双击 bin_mac/注册定时任务.command")
    print(f"立刻试跑: launchctl start {label}")
    print("卸载: 双击或运行 bin_mac/sh/卸载定时任务.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
