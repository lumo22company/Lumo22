#!/usr/bin/env python3
"""
SMTP RCPT TO probe — verify whether an email address is accepted by the recipient's MX.

This is the same technique mailbox-validation services use: connect to the recipient
domain's mail server, issue HELO/MAIL FROM/RCPT TO, and read the response code.
- 250 -> mailbox accepted (exists, or domain is a catch-all)
- 550 -> mailbox rejected (does not exist on a non-catch-all server)
- 4xx -> deferred / greylisted (re-try later)

Notes:
- No actual message body is sent. We QUIT before DATA.
- Some servers (catch-all, greylisting, Microsoft 365 with strict policies) won't give
  a definitive 250/550 at RCPT TO time. Use this as a strong-but-not-perfect signal.
- Run from a residential ISP with port 25 outbound allowed. Many cloud hosts block 25.

Examples:
  python3 scripts/verify_email_smtp.py susie@bathpilates.co.uk enquiries@bathpilates.co.uk
  python3 scripts/verify_email_smtp.py --csv exports/smartlead_new_only_fitness_bath_2026-05-06.csv --col email
"""

from __future__ import annotations

import argparse
import csv
import smtplib
import socket
import subprocess
import sys
from typing import Any


def get_mx(domain: str) -> list[str]:
    """Resolve MX records via the system 'dig' (no extra Python deps)."""
    try:
        out = subprocess.check_output(["dig", "+short", "MX", domain], text=True, timeout=10)
    except Exception as exc:
        return []
    rows: list[tuple[int, str]] = []
    for line in out.strip().splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit():
            rows.append((int(parts[0]), parts[1].rstrip(".")))
    rows.sort()
    return [host for _, host in rows]


def probe(addr: str, helo_host: str = "verify.lumo22.com", from_addr: str = "verify@lumo22.com") -> dict[str, Any]:
    if "@" not in addr:
        return {"address": addr, "result": "invalid_format"}
    domain = addr.rsplit("@", 1)[1]
    mxs = get_mx(domain)
    if not mxs:
        return {"address": addr, "result": "no_mx"}
    last_err: str | None = None
    for mx in mxs[:2]:
        try:
            s = smtplib.SMTP(timeout=10)
            s.connect(mx, 25)
            s.ehlo(helo_host)
            code, msg = s.mail(from_addr)
            if code >= 400:
                s.quit()
                return {
                    "address": addr,
                    "mx": mx,
                    "result": "mail_from_rejected",
                    "code": code,
                    "msg": msg.decode(errors="replace") if isinstance(msg, bytes) else str(msg),
                }
            code, msg = s.rcpt(addr)
            s.quit()
            text = msg.decode(errors="replace") if isinstance(msg, bytes) else str(msg)
            verdict = "accepted" if code < 300 else ("rejected" if code >= 500 else "deferred")
            return {"address": addr, "mx": mx, "code": code, "msg": text, "result": verdict}
        except (socket.timeout, OSError, smtplib.SMTPException) as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            continue
    return {"address": addr, "result": "unreachable", "detail": last_err}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("emails", nargs="*", help="One or more addresses to probe.")
    ap.add_argument("--csv", help="Probe every address in the given CSV column.")
    ap.add_argument("--col", default="email", help="Column name to read (default: email).")
    ap.add_argument("--helo", default="verify.lumo22.com")
    ap.add_argument("--from-addr", default="verify@lumo22.com")
    args = ap.parse_args()

    targets: list[str] = list(args.emails)
    if args.csv:
        with open(args.csv, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                v = (row.get(args.col) or "").strip()
                if v:
                    targets.append(v)

    if not targets:
        print("Provide at least one email or --csv FILE.", file=sys.stderr)
        return 2

    rejected: list[str] = []
    for addr in targets:
        result = probe(addr, helo_host=args.helo, from_addr=args.from_addr)
        verdict = result.get("result")
        code = result.get("code", "")
        msg = (result.get("msg") or "").splitlines()[0] if result.get("msg") else result.get("detail", "")
        print(f"{verdict.upper():9s} {addr:50s} {code} {msg}")
        if verdict == "rejected":
            rejected.append(addr)

    if rejected:
        print(f"\n{len(rejected)} of {len(targets)} addresses confirmed dead:", file=sys.stderr)
        for a in rejected:
            print(f"  - {a}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
