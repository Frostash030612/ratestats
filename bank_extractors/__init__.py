"""
`bank_extractors`：从 `bank_all_promo_rates.py` 抽离的抓取/解析/合并实现。

- 具体函数定义在 `bank_extractors.impl` 中（单文件便于保持历史顺序与依赖关系）。
- `bank_fetch_and_extract.fetch_and_extract` 应直接 `from bank_extractors import impl` 或
  `from bank_extractors.impl import ...`，不再使用 `import __main__` 运行时绑定。
"""

from __future__ import annotations

import bank_extractors.impl as impl  # noqa: F401 - 包入口便于 `from bank_extractors import impl`

__all__ = ["impl"]
