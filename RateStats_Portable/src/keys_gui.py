#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RateStats API Key 配置界面（独立窗口，不与邮件/定时界面合并）。"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from assets_kv import load_kv, upsert_kv
from project_paths import ASSETS_DIR, PROJECT_ROOT

AI_COMPARE = PROJECT_ROOT / "AI_Compare"
KEYS_PATH = AI_COMPARE / "keys.txt"
KEYS_EXAMPLE = AI_COMPARE / "keys.txt.example"

# 界面可编辑的搜索引擎 Key（Vertex 用 JSON 文件，单独说明）
KEY_FIELDS = [
    ("SERPER_API_KEY", "Serper API Key", "https://serper.dev"),
    ("BRAVE_API_KEY", "Brave API Key", "https://brave.com/search/api/"),
    ("TAVILY_API_KEY", "Tavily API Key", "https://tavily.com"),
    ("BING_API_KEY", "Bing API Key（可选，多数情况可空）", ""),
]

VERTEX_FIELDS = [
    ("GOOGLE_CLOUD_PROJECT", "Google Cloud 项目 ID"),
    ("VERTEX_ENGINE_ID", "Vertex 搜索引擎 ID"),
]


def ensure_keys_file() -> Path:
    AI_COMPARE.mkdir(parents=True, exist_ok=True)
    if not KEYS_PATH.is_file():
        if KEYS_EXAMPLE.is_file():
            shutil.copy2(KEYS_EXAMPLE, KEYS_PATH)
        else:
            KEYS_PATH.write_text(
                "# API Keys（勿外传）\n"
                "SERPER_API_KEY=\n"
                "BRAVE_API_KEY=\n"
                "TAVILY_API_KEY=\n"
                "# BING_API_KEY=\n",
                encoding="utf-8",
            )
    return KEYS_PATH


def _mask(value: str) -> str:
    v = (value or "").strip()
    if len(v) <= 8:
        return "（已填写）" if v else "（未填写）"
    return f"{v[:4]}…{v[-4:]}（已填写，共 {len(v)} 字符）"


class KeysApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("RateStats — API Key 设置")
        self.geometry("760x620")
        self.minsize(680, 560)

        ttk.Label(
            self,
            text="此处只改搜索引擎 API Key。邮件与定时请用「打开配置界面」。",
            wraplength=680,
        ).pack(fill="x", padx=12, pady=(10, 4))

        self.path_var = tk.StringVar()
        ttk.Label(self, textvariable=self.path_var, foreground="#555").pack(
            fill="x", padx=12, pady=(0, 8)
        )

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=12, pady=4)
        body.columnconfigure(1, weight=1)

        self.entries: dict[str, ttk.Entry] = {}
        self.status: dict[str, tk.StringVar] = {}

        row = 0
        for key, label, tip in KEY_FIELDS:
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="e", padx=8, pady=8)
            e = ttk.Entry(body, width=48, show="*")
            e.grid(row=row, column=1, sticky="we", padx=8, pady=8)
            self.entries[key] = e
            st = tk.StringVar(value="")
            self.status[key] = st
            ttk.Label(body, textvariable=st, foreground="#666").grid(
                row=row, column=2, sticky="w", padx=4
            )
            if tip:
                ttk.Label(body, text=tip, foreground="#888", font=("", 8)).grid(
                    row=row + 1, column=1, sticky="w", padx=8
                )
                row += 2
            else:
                row += 1

        sep = ttk.Separator(body)
        sep.grid(row=row, column=0, columnspan=3, sticky="ew", pady=12)
        row += 1

        ttk.Label(body, text="Vertex AI 密钥文件").grid(row=row, column=0, sticky="ne", padx=8)
        self.vertex_var = tk.StringVar()
        ttk.Label(body, textvariable=self.vertex_var, wraplength=420).grid(
            row=row, column=1, sticky="w", padx=8
        )
        vf = ttk.Frame(body)
        vf.grid(row=row, column=2, sticky="w")
        ttk.Button(vf, text="打开 assets 文件夹", command=self.open_assets).pack(side="top", pady=2)
        ttk.Button(vf, text="选择 JSON…", command=self.pick_vertex_json).pack(side="top", pady=2)
        row += 1
        ttk.Label(
            body,
            text="Vertex 一般用 assets 下的 ratestatsearch-*.json；换电脑请整份 JSON 拷进去。",
            foreground="#666",
            wraplength=520,
        ).grid(row=row, column=1, columnspan=2, sticky="w", padx=8, pady=4)
        row += 1

        self.vertex_entries: dict[str, ttk.Entry] = {}
        for key, label in VERTEX_FIELDS:
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="e", padx=8, pady=6)
            entry = ttk.Entry(body, width=48)
            entry.grid(row=row, column=1, columnspan=2, sticky="we", padx=8, pady=6)
            self.vertex_entries[key] = entry
            row += 1

        ttk.Label(
            body,
            text="项目 ID 不是项目显示名称；引擎 ID 可在 Vertex AI Search 应用详情中查看。",
            foreground="#666",
            wraplength=560,
        ).grid(row=row, column=1, columnspan=2, sticky="w", padx=8, pady=4)

        btns = ttk.Frame(self)
        btns.pack(pady=14)
        ttk.Button(btns, text="重新加载", command=self.reload).pack(side="left", padx=6)
        ttk.Button(btns, text="显示/隐藏明文", command=self.toggle_show).pack(side="left", padx=6)
        ttk.Button(btns, text="保存 API Key", command=self.save).pack(side="left", padx=6)
        ttk.Button(btns, text="打开 keys.txt 所在文件夹", command=self.open_keys_dir).pack(
            side="left", padx=6
        )

        self._show = False
        self.reload()

    def _vertex_file(self) -> Path:
        cfg = load_kv(KEYS_PATH) if KEYS_PATH.is_file() else {}
        env = (cfg.get("GOOGLE_APPLICATION_CREDENTIALS") or "").strip()
        if env:
            p = Path(env)
            if not p.is_absolute():
                p = (AI_COMPARE / p).resolve()
            return p
        for p in sorted(ASSETS_DIR.glob("ratestatsearch-*.json")):
            return p
        return ASSETS_DIR / "ratestatsearch-f5f95dab974f.json"

    def reload(self) -> None:
        ensure_keys_file()
        self.path_var.set(f"Key 文件：{KEYS_PATH}")
        cfg = load_kv(KEYS_PATH)
        for key, _, _ in KEY_FIELDS:
            e = self.entries[key]
            e.delete(0, "end")
            e.insert(0, cfg.get(key, ""))
            self.status[key].set(_mask(cfg.get(key, "")))
        for key, _ in VERTEX_FIELDS:
            entry = self.vertex_entries[key]
            entry.delete(0, "end")
            entry.insert(0, cfg.get(key, ""))
        vf = self._vertex_file()
        if vf.is_file():
            self.vertex_var.set(f"已找到：{vf}")
        else:
            self.vertex_var.set(f"未找到：{vf}")

    def toggle_show(self) -> None:
        self._show = not self._show
        for e in self.entries.values():
            e.configure(show="" if self._show else "*")

    def save(self) -> None:
        ensure_keys_file()
        updates = {key: self.entries[key].get().strip() for key, _, _ in KEY_FIELDS}
        updates.update(
            {key: self.vertex_entries[key].get().strip() for key, _ in VERTEX_FIELDS}
        )
        try:
            upsert_kv(KEYS_PATH, updates)
        except Exception as e:
            messagebox.showerror("保存失败", str(e))
            return
        self.reload()
        messagebox.showinfo("已保存", f"API Key 已写入：\n{KEYS_PATH}\n\n下次跑 AI 搜索会自动读取。")

    def open_keys_dir(self) -> None:
        ensure_keys_file()
        self._open_path(AI_COMPARE)

    def open_assets(self) -> None:
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        self._open_path(ASSETS_DIR)

    def pick_vertex_json(self) -> None:
        path = filedialog.askopenfilename(
            title="选择 Vertex 服务账号 JSON",
            filetypes=[("JSON", "*.json"), ("全部", "*.*")],
        )
        if not path:
            return
        src = Path(path)
        dest = ASSETS_DIR / src.name
        try:
            ASSETS_DIR.mkdir(parents=True, exist_ok=True)
            if src.resolve() != dest.resolve():
                shutil.copy2(src, dest)
            # 相对 AI_Compare 的路径，便于跨机器（仍建议用 assets）
            rel = Path("..") / "assets" / src.name
            upsert_kv(KEYS_PATH, {"GOOGLE_APPLICATION_CREDENTIALS": str(rel).replace("\\", "/")})
            self.reload()
            messagebox.showinfo("已更新", f"已复制到：\n{dest}\n并写入 keys.txt 路径。")
        except Exception as e:
            messagebox.showerror("失败", str(e))

    def _open_path(self, path: Path) -> None:
        path = path.resolve()
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            elif sys.platform.startswith("win"):
                subprocess.Popen(["explorer", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            messagebox.showerror("无法打开文件夹", str(e))


def main() -> int:
    app = KeysApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
