#!/usr/bin/env python3
"""
数据提取脚本 - 20260320
从MarketRateData11.xlsx提取所有sheet数据
"""

import subprocess
import sys

def run_extraction():
    print("数据提取脚本")
    print("=" * 60)
    
    print("\n1. 查看所有sheet:")
    print('  python3 xlsx_inspect.py "MarketRateData11.xlsx"')
    
    print("\n2. 提取关键数据:")
    print("  # SGD促销 (Sheet1数据源)")
    print('  python3 xlsx_inspect.py "MarketRateData11.xlsx" --sheet 1')
    print()
    print("  # SGD挂牌 (Sheet2和Sheet3数据源)")
    print('  python3 xlsx_inspect.py "MarketRateData11.xlsx" --sheet 4')
    print()
    print("  # USD促销 (Sheet6数据源)")
    print('  python3 xlsx_inspect.py "MarketRateData11.xlsx" --sheet 2')
    print()
    print("  # 其他外币促销利率 (Sheet6数据源)")
    print('  python3 xlsx_inspect.py "MarketRateData11.xlsx" --sheet 3')
    print()
    print("  # USD挂牌 (Sheet6数据源)")
    print('  python3 xlsx_inspect.py "MarketRateData11.xlsx" --sheet 5')
    
    print("\n3. 运行提取:")
    print("  复制上面的命令到终端执行")

if __name__ == "__main__":
    run_extraction()
