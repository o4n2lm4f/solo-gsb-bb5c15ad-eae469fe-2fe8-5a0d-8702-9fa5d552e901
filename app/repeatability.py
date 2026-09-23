"""重复测量的重复性统计：算术平均值、样本标准差、极差、变异系数。

纯函数实现，不依赖 FastAPI；HTTP 层（``main.py``）负责请求解析、
单位量纲校验与统一换算。调用方保证：

* ``values`` 至少 2 个（标准差按 n-1 计算，需要自由度）；
* 所有数值已经换算到同一目标单位。

统计定义：

* 算术平均值 ``mean = Σx / n``；
* 样本标准差 ``s = sqrt(Σ(x - mean)² / (n - 1))``（贝塞尔校正）；
* 极差 ``range = max(x) - min(x)``（恒非负）；
* 变异系数 ``CV = s / |mean|``，无量纲比例；均值为 0 时无定义，返回 ``None``。

均值与极差全程使用 :class:`fractions.Fraction` 精确计算；
标准差含开方（一般为无理数），标准差与变异系数输出 ``float``。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class RepeatabilityStats:
    """重复性统计结果（均为目标单位下的量，CV 除外）。

    ``mean``/``range`` 为精确有理值；``std_dev`` 含开方、
    ``coefficient_of_variation`` 依赖标准差，两者为 ``float``；
    均值为零时 ``coefficient_of_variation`` 为 ``None``。
    """

    count: int
    mean: Fraction
    std_dev: float
    range: Fraction
    coefficient_of_variation: float | None


def repeatability_stats(values: list[Fraction]) -> RepeatabilityStats:
    """计算重复测量序列的重复性统计量。

    :raises ValueError: 测量少于 2 个时无法计算样本标准差。
    """
    n = len(values)
    if n < 2:
        raise ValueError("至少需要 2 个测量值才能计算样本标准差（n-1）")

    total = Fraction(0)
    for v in values:
        total += v
    mean = total / n

    squared_sum = Fraction(0)
    for v in values:
        squared_sum += (v - mean) ** 2
    # 样本方差（n-1）；标准差含开方，转 float。
    # 输入可能大到平方和超出有限 float：记为 inf，交由 HTTP 层按
    # NUMERIC_OVERFLOW 拒绝（均值/极差不超过输入量级，仍可表示）。
    try:
        variance = float(squared_sum / (n - 1))
        std_dev = math.sqrt(variance)
    except OverflowError:
        std_dev = float("inf")

    rng = max(values) - min(values)
    coefficient_of_variation: float | None = None
    if mean != 0:
        coefficient_of_variation = std_dev / abs(float(mean))

    return RepeatabilityStats(
        count=n,
        mean=mean,
        std_dev=std_dev,
        range=rng,
        coefficient_of_variation=coefficient_of_variation,
    )
