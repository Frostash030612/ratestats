#!/usr/bin/env python3
from pathlib import Path

bin_dir = Path(__file__).resolve().parent.parent / "bin"
for p in bin_dir.glob("*.bat"):
    t = p.read_text(encoding="utf-8")
    t2 = t
    t2 = t2.replace('call ""%BIN%set_runs_out_dir.bat""', 'call "%BIN%set_runs_out_dir.bat"')
    t2 = t2.replace('set "EMAIL_CFG=%CD%\\%ASSETS%\\email_params.log"', 'set "EMAIL_CFG=%ASSETS%\\email_params.log"')
    t2 = t2.replace('"..\\RateStats_ML\\requirements.txt"', '"..\\..\\RateStats_ML\\requirements.txt"')
    t2 = t2.replace('"..\\AI_Compare\\requirements.txt"', '"..\\..\\AI_Compare\\requirements.txt"')
    if t2 != t:
        p.write_text(t2, encoding="utf-8")
        print("fixed", p.name)
