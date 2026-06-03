#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发送 Market + 彩虹表结果邮件（配置来自日志文件）。"""

from __future__ import annotations

import argparse
import os
import smtplib
import sys
import traceback
from email.message import EmailMessage

try:
    from smtplib import SMTPAuthenticationError
except ImportError:
    SMTPAuthenticationError = OSError  # type: ignore[misc,assignment]
from typing import Dict, List


def _parse_bool(v: str) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def load_kv_log(path: str) -> Dict[str, str]:
    """
    读取 key=value 日志配置，支持注释：
    - 以 # 或 ; 开头的行为注释
    - 空行忽略
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"配置文件不存在: {path}")
    out: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def _split_emails(v: str) -> List[str]:
    parts = []
    for x in (v or "").replace(";", ",").split(","):
        t = x.strip()
        if t:
            parts.append(t)
    return parts


def build_message(
    sender: str,
    to_addrs: List[str],
    cc_addrs: List[str],
    subject: str,
    body: str,
    attachments: List[str],
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(to_addrs)
    if cc_addrs:
        msg["Cc"] = ", ".join(cc_addrs)
    msg["Subject"] = subject
    msg.set_content(body)

    for p in attachments:
        if not os.path.exists(p):
            print(f"[MAIL] 警告：附件不存在，已跳过：{p}", file=sys.stderr)
            continue
        with open(p, "rb") as f:
            data = f.read()
        msg.add_attachment(
            data,
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=os.path.basename(p),
        )
    return msg


def _rainbow_zh_path(out_dir: str, run_tag: str) -> str:
    "与 generate_rainbow_from_bank / 03 批处理一致的中文彩虹表路径（在 Python 内拼接，避免 cmd 乱码）。"
    return os.path.join(os.path.abspath(out_dir), f"彩虹表_按MarketRateData更新_{run_tag}.xlsx")


def main() -> int:
    ap = argparse.ArgumentParser(description="发送每日利率结果邮件")
    ap.add_argument("--config-log", required=True, help="邮件参数日志文件（key=value）")
    ap.add_argument("--market", required=True, help="MarketRateData 文件路径")
    ap.add_argument("--rainbow", default=None, help="彩虹表文件路径")
    ap.add_argument(
        "--rainbow-dir-zh",
        default=None,
        metavar="DIR",
        help="与 --rainbow-tag 同时给出时，在 Python 内拼中文名彩虹表路径（不经 cmd 传中文）。",
    )
    ap.add_argument(
        "--rainbow-tag",
        default=None,
        metavar="TAG",
        help="与 --rainbow-dir-zh 搭配，例如 20260514_16.24",
    )
    ap.add_argument("--date-tag", required=True, help="日期标签 YYYYMMDD")
    ap.add_argument(
        "--market-ai",
        default=None,
        help="可选：Vertex AI 流程生成的 MarketRateData_*_AISearch.xlsx",
    )
    args = ap.parse_args()

    if args.rainbow_dir_zh and args.rainbow_tag:
        if args.rainbow:
            ap.error("不要同时使用 --rainbow 与 --rainbow-dir-zh/--rainbow-tag")
        args.rainbow = _rainbow_zh_path(args.rainbow_dir_zh, args.rainbow_tag)
    elif args.rainbow_dir_zh or args.rainbow_tag:
        ap.error("--rainbow-dir-zh 与 --rainbow-tag 须同时提供")
    elif not args.rainbow:
        ap.error("请提供 --rainbow，或同时提供 --rainbow-dir-zh 与 --rainbow-tag")

    try:
        return _main_send(args)
    except SMTPAuthenticationError as e:
        print(f"[MAIL] 发送失败：{e}", file=sys.stderr)
        _print_smtp_auth_help(e)
        print(traceback.format_exc(), file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[MAIL] 发送失败：{e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1


def _print_smtp_auth_help(exc: Exception) -> None:
    """Microsoft 365 常见 535：已关闭 SMTP 基本身份验证。"""
    msg = str(exc).lower()
    if "basic authentication is disabled" in msg or "5.7.139" in msg:
        print(
            "[MAIL] 说明：当前邮箱在 Microsoft 365 / Exchange Online 上已禁止「SMTP 基本身份验证」"
            "（用户名+密码直连 smtp.office365.com）。这不是脚本写错，而是租户策略。",
            file=sys.stderr,
        )
        print(
            "[MAIL] 可行做法（选一）：请学校/单位 IT 为该邮箱开启「SMTP AUTH / Authenticated SMTP」；"
            "或改用仍允许基本验证的邮箱发信；或后续再接入 OAuth2（需单独开发）。",
            file=sys.stderr,
        )
        print(
            "[MAIL] 参考："
            "https://learn.microsoft.com/exchange/clients-and-mobile-in-exchange-online/"
            "authenticated-client-smtp-submission",
            file=sys.stderr,
        )


def _main_send(args: argparse.Namespace) -> int:
    cfg = load_kv_log(args.config_log)
    enabled = _parse_bool(cfg.get("email_enabled", "true"))
    if not enabled:
        print("[MAIL] email_enabled=false，已跳过发送。")
        return 0

    smtp_host = cfg.get("smtp_host", "")
    smtp_port = int(cfg.get("smtp_port", "465") or "465")
    smtp_user = cfg.get("smtp_user", "")
    smtp_password = cfg.get("smtp_password", "")
    smtp_ssl = _parse_bool(cfg.get("smtp_ssl", "true"))
    sender = cfg.get("from_email", "") or smtp_user
    to_addrs = _split_emails(cfg.get("to_emails", ""))
    cc_addrs = _split_emails(cfg.get("cc_emails", ""))

    if not smtp_host:
        raise ValueError("配置缺失: smtp_host")
    if not sender:
        raise ValueError("配置缺失: from_email（或 smtp_user）")
    if not to_addrs:
        raise ValueError("配置缺失: to_emails")

    subject_tpl = cfg.get("subject_template", "每日利率结果 {date}")
    body_tpl = cfg.get(
        "body_template",
        "您好，\n\n附件为 {date} 的 MarketRateData 与彩虹表。\n\n"
        "- Market: {market_name}\n"
        "- Rainbow: {rainbow_name}\n"
        "- Market (AI): {market_ai_name}\n",
    )
    market_ai_name = os.path.basename(args.market_ai) if args.market_ai else ""
    subject = subject_tpl.replace("{date}", args.date_tag)
    body = (
        body_tpl.replace("{date}", args.date_tag)
        .replace("{market_name}", os.path.basename(args.market))
        .replace("{rainbow_name}", os.path.basename(args.rainbow))
        .replace("{market_ai_name}", market_ai_name or "（本次未生成）")
    )

    required = [(args.market, "Market"), (args.rainbow, "Rainbow")]
    if args.market_ai:
        required.append((args.market_ai, "Market (AI)"))
    for path, label in required:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"{label} 文件不存在: {path}")

    attachments = [args.market, args.rainbow]
    if args.market_ai:
        attachments.append(args.market_ai)

    msg = build_message(
        sender=sender,
        to_addrs=to_addrs,
        cc_addrs=cc_addrs,
        subject=subject,
        body=body,
        attachments=attachments,
    )

    all_rcpt = list(to_addrs) + list(cc_addrs)
    if smtp_ssl:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as s:
            if smtp_user:
                s.login(smtp_user, smtp_password)
            s.send_message(msg, from_addr=sender, to_addrs=all_rcpt)
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            if smtp_user:
                s.login(smtp_user, smtp_password)
            s.send_message(msg, from_addr=sender, to_addrs=all_rcpt)

    print(f"[MAIL] 发送成功 -> to={','.join(to_addrs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

