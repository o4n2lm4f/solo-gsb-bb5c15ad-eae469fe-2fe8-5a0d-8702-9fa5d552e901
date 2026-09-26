"""重复测量的重复性统计：均值、样本标准差、极差、变异系数。

纯函数实现，不依赖 FastAPI；HTTP 层（``main.py``）负责请求解析、
量纲校验与单位换算。约定：

* 所有测量值由调用方统一换算到**同一目标单位**后传入；
* 算术平均值：``mean = Σx / n``；
* 样本标准差（分母 n-1）：``s = sqrt(Σ(x-mean)^2 / (n - 1))``；
* 极差：``max(x) - min(x)``；
* 变异系数：``s / |mean|``（无量纲比例）；均值为 0 时为 ``None``；
* 均值、方差、极差全程使用 :class:`fractions.Fraction` 精确计算，
  标准差含开方（一般为无理数），在输出时转 ``float``。
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

import math


@dataclass(frozen=True)
class RepeatabilityStats:
    """重复性统计结果（精确值）。"""

    count: int
    mean: Fraction
    sample_variance: Fraction
    minimum: Fraction
    maximum: Fraction

    @property
    def value_range(self) -> Fraction:
        """极差（全距）：最大值 - 最小值。"""
        return self.maximum - self.minimum

    def sample_stddev(self) -> float:
        """样本标准差（n-1）；开方结果在输出时转 float。"""
        return math.sqrt(float(self.sample_variance))

    def coefficient_of_variation(self) -> float | None:
        """变异系数 s/|mean|（无量纲比例）；均值为 0 时为 ``None``。"""
        if self.mean == 0:
            return None
        return self.sample_stddev() / abs(float(self.mean))


def repeatability(values: list[Fraction]) -> RepeatabilityStats:
    """对同一单位下的重复测量值做重复性统计。

    调用方保证 ``values`` 至少含 2 个测量值。
    """
    n = len(values)
    if n < 2:
        raise ValueError("至少需要 2 个重复测量值")

    mean = sum(values, Fraction(0)) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return RepeatabilityStats(
        count=n,
        mean=mean,
        sample_variance=variance,
        minimum=min(values),
        maximum=max(values),
    )
