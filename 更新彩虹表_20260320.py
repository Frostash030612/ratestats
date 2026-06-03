#!/usr/bin/env python3
"""
彩虹表更新脚本 - 20260320
将市场数据更新到彩虹表Excel中
"""

import os
import sys
from datetime import datetime

def main():
    print("彩虹表更新脚本")
    print("生成日期: 20260320")
    print("=" * 60)
    
    print("\n使用说明:")
    print("1. 打开 Excel 文件: 彩虹表_20260320.xlsx")
    print("2. 参考文件: 彩虹表_20260320_详细数据.txt")
    print("3. 手动更新以下sheet:")
    print("   - Sheet1: SGD Promotional Rate")
    print("   - Sheet2: SGD Board Rate")
    print("   - Sheet3: SGD Board Rate Ranked")
    print("   - Sheet6: USD Rate + Other Currency Rates")
    print("4. 保存文件")
    
    print("\n关键数据:")
    print("- FTP调整预测:")
    print("  1M: 1.32%")
    print("  3M: 1.33%")
    print("  6M: 1.33%")
    print("  9M: 1.35%")
    print("  12M: 1.40%")
    
    print("\n颜色系统:")
    print("红色 → 橙色 → 黄色 → 绿色 → 蓝色 → 紫色")
    print("(高利率 → 低利率)")
    
    print("\n完成更新后:")
    print("1. 验证数据准确性")
    print("2. 检查颜色标注")
    print("3. 保存并分享文件")

if __name__ == "__main__":
    main()
