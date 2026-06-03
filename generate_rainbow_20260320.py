#!/usr/bin/env python3
"""
一键生成彩虹表 - 20260320
"""

import os
import subprocess
from datetime import datetime

def main():
    print("一键生成彩虹表")
    print("=" * 60)
    
    date_str = datetime.now().strftime("%Y%m%d")
    
    print(f"\n生成日期: {date_str}")
    print(f"输出文件: 彩虹表_自动生成_{date_str}.xlsx")
    
    print(f"\n步骤1: 检查文件")
    print("  - MarketRateData11.xlsx")
    print("  - 彩虹表 20260311.xlsx")
    
    print(f"\n步骤2: 提取数据")
    print(f"  运行: python3 extract_all_data_{date_str}.py")
    
    print(f"\n步骤3: 更新Excel")
    print(f"  1. 打开: 彩虹表_自动生成_{date_str}.xlsx")
    print(f"  2. 参考: rainbow_update_guide_{date_str}.txt")
    print(f"  3. 按sheet更新数据")
    
    print(f"\n步骤4: 应用颜色")
    print("  红色: ≥1.40%")
    print("  橙色: 1.30-1.39%")
    print("  黄色: 1.20-1.29%")
    print("  绿色: 1.10-1.19%")
    print("  蓝色: 0.80-1.09%")
    print("  紫色: <0.80%")
    
    print(f"\n步骤5: 保存文件")
    print(f"  保存并分享彩虹表")

if __name__ == "__main__":
    main()
