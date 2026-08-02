#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RateStats 可视化配置：邮件 + 定时任务（无需手改 .log）。"""
from __future__ import annotations

import platform
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path

from assets_kv import load_kv, upsert_kv
from project_paths import ASSETS_DIR, BIN_MAC_DIR, PACKAGE_DIR

EMAIL_PATH = ASSETS_DIR / "email_params.log"
SCHEDULE_PATH = ASSETS_DIR / "schedule_params.log"

WEEKDAY_OPTS = [
    ("sun", "周日"),
    ("mon", "周一"),
    ("tue", "周二"),
    ("wed", "周三"),
    ("thu", "周四"),
    ("fri", "周五"),
    ("sat", "周六"),
]


def _bool_from_cfg(v: str, default: bool = True) -> bool:
    if v is None or str(v).strip() == "":
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


class ConfigApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("RateStats 配置中心")
        self.geometry("720x580")
        self.minsize(640, 520)

        note = ttk.Label(
            self,
            text="在下方修改后点「保存」。定时任务保存后还可一键注册到系统（Mac）。",
            wraplength=680,
        )
        note.pack(fill="x", padx=12, pady=(10, 4))

        path_lbl = ttk.Label(self, text=f"配置目录：{ASSETS_DIR}", foreground="#555")
        path_lbl.pack(fill="x", padx=12, pady=(0, 8))

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=12, pady=4)

        self.email_tab = ttk.Frame(nb)
        self.sched_tab = ttk.Frame(nb)
        nb.add(self.email_tab, text="邮件设置")
        nb.add(self.sched_tab, text="定时任务")

        self._build_email_tab()
        self._build_sched_tab()
        self.reload_all()

    def _entry(self, parent, row: int, label: str, show: str | None = None) -> ttk.Entry:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="e", padx=8, pady=6)
        e = ttk.Entry(parent, width=52, show=show or "")
        e.grid(row=row, column=1, sticky="we", padx=8, pady=6)
        return e

    def _build_email_tab(self) -> None:
        f = self.email_tab
        f.columnconfigure(1, weight=1)

        self.var_email_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="启用发送邮件", variable=self.var_email_enabled).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=8, pady=8
        )

        self.e_smtp_host = self._entry(f, 1, "SMTP 服务器")
        self.e_smtp_port = self._entry(f, 2, "SMTP 端口")
        self.var_smtp_ssl = tk.BooleanVar(value=True)
        ttk.Label(f, text="使用 SSL").grid(row=3, column=0, sticky="e", padx=8, pady=6)
        ttk.Checkbutton(f, variable=self.var_smtp_ssl).grid(row=3, column=1, sticky="w", padx=8)

        self.e_smtp_user = self._entry(f, 4, "登录账号")
        self.e_smtp_password = self._entry(f, 5, "登录密码 / 应用密码", show="*")
        self.e_from = self._entry(f, 6, "发件人")
        self.e_to = self._entry(f, 7, "收件人（逗号分隔）")
        self.e_cc = self._entry(f, 8, "抄送（可空）")
        self.e_subject = self._entry(f, 9, "邮件标题模板")

        ttk.Label(f, text="正文模板").grid(row=10, column=0, sticky="ne", padx=8, pady=6)
        self.t_body = tk.Text(f, height=6, width=52, wrap="word")
        self.t_body.grid(row=10, column=1, sticky="nsew", padx=8, pady=6)
        f.rowconfigure(10, weight=1)

        hint = ttk.Label(
            f,
            text="提示：QQ/公司邮箱密码栏填「授权码/应用密码」，一般不是网页登录密码。",
            foreground="#666",
            wraplength=520,
        )
        hint.grid(row=11, column=0, columnspan=2, sticky="w", padx=8, pady=4)

        btns = ttk.Frame(f)
        btns.grid(row=12, column=0, columnspan=2, pady=12)
        ttk.Button(btns, text="重新加载", command=self.load_email).pack(side="left", padx=6)
        ttk.Button(btns, text="保存邮件设置", command=self.save_email).pack(side="left", padx=6)

    def _build_sched_tab(self) -> None:
        f = self.sched_tab
        f.columnconfigure(1, weight=1)

        self.var_sched_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="启用定时任务", variable=self.var_sched_enabled).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=8, pady=8
        )

        ttk.Label(f, text="每周运行日（可多选）").grid(row=1, column=0, sticky="ne", padx=8, pady=6)
        days_f = ttk.Frame(f)
        days_f.grid(row=1, column=1, sticky="w", padx=8, pady=6)
        self.day_vars: dict[str, tk.BooleanVar] = {}
        for i, (code, name) in enumerate(WEEKDAY_OPTS):
            var = tk.BooleanVar(value=False)
            self.day_vars[code] = var
            ttk.Checkbutton(days_f, text=name, variable=var).grid(row=i // 4, column=i % 4, sticky="w", padx=4)

        presets = ttk.Frame(f)
        presets.grid(row=2, column=1, sticky="w", padx=8)
        ttk.Button(presets, text="工作日", command=self._preset_weekdays).pack(side="left", padx=2)
        ttk.Button(presets, text="每天", command=self._preset_daily).pack(side="left", padx=2)
        ttk.Button(presets, text="清空", command=self._preset_clear_days).pack(side="left", padx=2)

        ttk.Label(f, text="运行时间").grid(row=3, column=0, sticky="e", padx=8, pady=6)
        time_f = ttk.Frame(f)
        time_f.grid(row=3, column=1, sticky="w", padx=8, pady=6)
        self.sp_hour = tk.Spinbox(time_f, from_=0, to=23, width=4)
        self.sp_minute = tk.Spinbox(time_f, from_=0, to=59, width=4)
        self.sp_hour.pack(side="left")
        ttk.Label(time_f, text=" : ").pack(side="left")
        self.sp_minute.pack(side="left")
        ttk.Label(time_f, text="  （24 小时制）").pack(side="left")

        ttk.Label(f, text="额外时刻（可选）").grid(row=4, column=0, sticky="e", padx=8, pady=6)
        self.e_times = ttk.Entry(f, width=52)
        self.e_times.grid(row=4, column=1, sticky="we", padx=8, pady=6)
        ttk.Label(
            f,
            text="可空。若填写则按多个时刻运行，例如：09:00,17:55（此时上面单个时间只作参考）",
            foreground="#666",
            wraplength=480,
        ).grid(row=5, column=1, sticky="w", padx=8)

        self.e_label = self._entry(f, 6, "任务名称（一般不改）")

        tip = ttk.Label(
            f,
            text="保存后请点「注册到系统」才会按新时间执行。电脑睡眠时到点可能跳过。",
            foreground="#666",
            wraplength=520,
        )
        tip.grid(row=7, column=0, columnspan=2, sticky="w", padx=8, pady=8)

        btns = ttk.Frame(f)
        btns.grid(row=8, column=0, columnspan=2, pady=10)
        ttk.Button(btns, text="重新加载", command=self.load_sched).pack(side="left", padx=6)
        ttk.Button(btns, text="保存定时设置", command=self.save_sched).pack(side="left", padx=6)
        ttk.Button(btns, text="注册到系统", command=self.register_sched).pack(side="left", padx=6)
        ttk.Button(btns, text="卸载定时", command=self.unregister_sched).pack(side="left", padx=6)
        ttk.Button(btns, text="立即试跑一次", command=self.run_once).pack(side="left", padx=6)

        if platform.system() != "Darwin":
            ttk.Label(
                f,
                text="当前不是 macOS：可保存参数，但「注册到系统」需在 Mac 上操作。",
                foreground="#a60",
            ).grid(row=9, column=0, columnspan=2, sticky="w", padx=8, pady=4)

    def _preset_weekdays(self) -> None:
        for code, var in self.day_vars.items():
            var.set(code in {"mon", "tue", "wed", "thu", "fri"})

    def _preset_daily(self) -> None:
        for var in self.day_vars.values():
            var.set(True)

    def _preset_clear_days(self) -> None:
        for var in self.day_vars.values():
            var.set(False)

    def reload_all(self) -> None:
        self.load_email()
        self.load_sched()

    def load_email(self) -> None:
        cfg = load_kv(EMAIL_PATH)
        self.var_email_enabled.set(_bool_from_cfg(cfg.get("email_enabled", "true")))
        self.e_smtp_host.delete(0, "end")
        self.e_smtp_host.insert(0, cfg.get("smtp_host", ""))
        self.e_smtp_port.delete(0, "end")
        self.e_smtp_port.insert(0, cfg.get("smtp_port", "465"))
        self.var_smtp_ssl.set(_bool_from_cfg(cfg.get("smtp_ssl", "true")))
        self.e_smtp_user.delete(0, "end")
        self.e_smtp_user.insert(0, cfg.get("smtp_user", ""))
        self.e_smtp_password.delete(0, "end")
        self.e_smtp_password.insert(0, cfg.get("smtp_password", ""))
        self.e_from.delete(0, "end")
        self.e_from.insert(0, cfg.get("from_email", ""))
        self.e_to.delete(0, "end")
        self.e_to.insert(0, cfg.get("to_emails", ""))
        self.e_cc.delete(0, "end")
        self.e_cc.insert(0, cfg.get("cc_emails", ""))
        self.e_subject.delete(0, "end")
        self.e_subject.insert(0, cfg.get("subject_template", "每日利率结果 {date}"))
        body = cfg.get("body_template", "").replace("\\n", "\n")
        self.t_body.delete("1.0", "end")
        self.t_body.insert("1.0", body)

    def save_email(self) -> None:
        body = self.t_body.get("1.0", "end").rstrip("\n")
        body_stored = body.replace("\n", "\\n")
        updates = {
            "email_enabled": "true" if self.var_email_enabled.get() else "false",
            "smtp_host": self.e_smtp_host.get().strip(),
            "smtp_port": self.e_smtp_port.get().strip() or "465",
            "smtp_ssl": "true" if self.var_smtp_ssl.get() else "false",
            "smtp_user": self.e_smtp_user.get().strip(),
            "smtp_password": self.e_smtp_password.get(),
            "from_email": self.e_from.get().strip(),
            "to_emails": self.e_to.get().strip(),
            "cc_emails": self.e_cc.get().strip(),
            "subject_template": self.e_subject.get().strip(),
            "body_template": body_stored,
        }
        if not updates["smtp_host"] or not updates["to_emails"]:
            messagebox.showerror("缺少必填项", "请填写 SMTP 服务器和收件人。")
            return
        try:
            upsert_kv(EMAIL_PATH, updates)
        except Exception as e:
            messagebox.showerror("保存失败", str(e))
            return
        messagebox.showinfo("已保存", f"邮件设置已写入：\n{EMAIL_PATH}")

    def load_sched(self) -> None:
        cfg = load_kv(SCHEDULE_PATH)
        self.var_sched_enabled.set(_bool_from_cfg(cfg.get("schedule_enabled", "true")))
        raw = (cfg.get("weekday") or "wed").strip().lower()
        selected: set[str] = set()
        if raw in {"daily", "every", "*"}:
            selected = {c for c, _ in WEEKDAY_OPTS}
        elif raw in {"weekdays", "workday", "workdays"}:
            selected = {"mon", "tue", "wed", "thu", "fri"}
        else:
            for part in raw.replace(";", ",").split(","):
                p = part.strip()
                if p in self.day_vars:
                    selected.add(p)
                elif p.isdigit() and 0 <= int(p) <= 6:
                    selected.add(WEEKDAY_OPTS[int(p)][0])
        for code, var in self.day_vars.items():
            var.set(code in selected)

        self.sp_hour.delete(0, "end")
        self.sp_hour.insert(0, f"{int(cfg.get('hour', '17')):02d}")
        self.sp_minute.delete(0, "end")
        self.sp_minute.insert(0, f"{int(cfg.get('minute', '55')):02d}")
        self.e_times.delete(0, "end")
        self.e_times.insert(0, cfg.get("times", "") or "")
        self.e_label.delete(0, "end")
        self.e_label.insert(0, cfg.get("label", "com.ratestats.fullpipeline"))

    def _weekday_value(self) -> str:
        chosen = [code for code, var in self.day_vars.items() if var.get()]
        if len(chosen) == 7:
            return "daily"
        if chosen == ["mon", "tue", "wed", "thu", "fri"]:
            return "weekdays"
        if not chosen:
            raise ValueError("请至少选择一个运行日")
        return ",".join(chosen)

    def save_sched(self) -> None:
        try:
            weekday = self._weekday_value()
            hour = int(self.sp_hour.get())
            minute = int(self.sp_minute.get())
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("时间不合法")
        except Exception as e:
            messagebox.showerror("输入有误", str(e))
            return
        updates = {
            "schedule_enabled": "true" if self.var_sched_enabled.get() else "false",
            "weekday": weekday,
            "hour": str(hour),
            "minute": str(minute),
            "times": self.e_times.get().strip(),
            "label": self.e_label.get().strip() or "com.ratestats.fullpipeline",
            "run_script": "sh/run_scheduled_full_pipeline.sh",
        }
        try:
            upsert_kv(SCHEDULE_PATH, updates)
        except Exception as e:
            messagebox.showerror("保存失败", str(e))
            return
        messagebox.showinfo(
            "已保存",
            f"定时设置已写入：\n{SCHEDULE_PATH}\n\n若要生效，请再点「注册到系统」。",
        )

    def _run_py(self, *args: str) -> tuple[int, str]:
        src = PACKAGE_DIR / "src"
        py = sys.executable
        cmd = [py, str(src / args[0]), *args[1:]]
        p = subprocess.run(cmd, cwd=str(src), capture_output=True, text=True)
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode, out

    def register_sched(self) -> None:
        self.save_sched()
        if platform.system() != "Darwin":
            messagebox.showwarning("仅限 Mac", "定时注册使用 macOS LaunchAgent，请在 Mac 上操作。")
            return
        code, out = self._run_py("register_mac_schedule.py", "--config", str(SCHEDULE_PATH))
        if code == 0:
            messagebox.showinfo("注册成功", out or "已注册到系统。")
        else:
            messagebox.showerror("注册失败", out or f"exit={code}")

    def unregister_sched(self) -> None:
        if platform.system() != "Darwin":
            messagebox.showwarning("仅限 Mac", "请在 Mac 上卸载。")
            return
        code, out = self._run_py(
            "register_mac_schedule.py", "--config", str(SCHEDULE_PATH), "--unregister"
        )
        if code == 0:
            messagebox.showinfo("已卸载", out or "定时任务已卸载。")
        else:
            messagebox.showerror("卸载失败", out or f"exit={code}")

    def run_once(self) -> None:
        script = BIN_MAC_DIR / "sh" / "run_scheduled_full_pipeline.sh"
        if platform.system() == "Darwin" and script.is_file():
            try:
                subprocess.Popen(["/bin/bash", str(script)], cwd=str(script.parent))
                messagebox.showinfo("已开始", "已在后台启动完整流程，日志见 runs/ 目录。")
            except Exception as e:
                messagebox.showerror("启动失败", str(e))
            return
        bat = PACKAGE_DIR / "bin" / "run_scheduled_full_pipeline.bat"
        if bat.is_file():
            try:
                subprocess.Popen(["cmd", "/c", str(bat)], cwd=str(bat.parent))
                messagebox.showinfo("已开始", "已启动完整流程。")
            except Exception as e:
                messagebox.showerror("启动失败", str(e))
            return
        messagebox.showerror("找不到脚本", f"未找到：\n{script}\n或\n{bat}")


def main() -> int:
    app = ConfigApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
