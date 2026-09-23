"""POST /repeatability 端到端测试（FastAPI TestClient）。"""
import math

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def m(value, unit="mm"):
    return {"value": value, "unit": unit}


def repeat(measurements, unit="mm"):
    return client.post("/repeatability",
                       json={"measurements": measurements, "unit": unit})


# ---------------------------------------------------------------------------
# 正常路径
# ---------------------------------------------------------------------------

def test_basic_repeatability_stats_same_unit():
    # 10.00, 10.02, 9.98, 10.00 mm
    r = repeat([m(10.00), m(10.02), m(9.98), m(10.00)])
    assert r.status_code == 200
    body = r.json()
    assert body["unit"] == "mm"
    assert body["count"] == 4
    assert body["dimension"] == [1, 0, 0, 0, 0, 0, 0]
    assert body["dimension_text"] == "m"
    assert body["mean"] == pytest.approx(10.00)
    # 样本方差 = (0 + 0.0004 + 0.0004 + 0) / 3
    assert body["sample_std_dev"] == pytest.approx(math.sqrt(0.0008 / 3))
    assert body["range"] == pytest.approx(0.04)
    assert body["coefficient_of_variation"] == pytest.approx(
        math.sqrt(0.0008 / 3) / 10.0)


def test_mixed_units_converted_to_target():
    # 1 m + 150 cm + 500 mm -> 目标 mm：[1000, 1500, 500]
    r = repeat([m(1, "m"), m(150, "cm"), m(500, "mm")], unit="mm")
    assert r.status_code == 200
    body = r.json()
    assert body["unit"] == "mm"
    assert body["count"] == 3
    assert body["mean"] == pytest.approx(1000.0)
    # 偏差：0, 500, -500；样本方差 = 500000/2 = 250000，s = 500
    assert body["sample_std_dev"] == pytest.approx(500.0)
    assert body["range"] == pytest.approx(1000.0)
    assert body["coefficient_of_variation"] == pytest.approx(0.5)


def test_target_unit_same_quantity_target_in_m():
    # 目标单位与输入不同但同量纲：1000 mm, 1.5 m -> m 即 [1.0, 1.5]
    r = repeat([m(1000, "mm"), m(1.5, "m")], unit="m")
    assert r.status_code == 200
    body = r.json()
    assert body["unit"] == "m"
    assert body["mean"] == pytest.approx(1.25)
    # n=2：s = |差|/sqrt(2) = 0.5/sqrt(2)
    assert body["sample_std_dev"] == pytest.approx(0.5 / math.sqrt(2))
    assert body["range"] == pytest.approx(0.5)


def test_identical_measurements_zero_spread():
    r = repeat([m(5), m(5), m(5)])
    assert r.status_code == 200
    body = r.json()
    assert body["mean"] == 5.0
    assert body["sample_std_dev"] == 0.0
    assert body["range"] == 0.0
    assert body["coefficient_of_variation"] == 0.0


def test_zero_mean_returns_null_cv():
    # -1, 0, 1 mm：均值 0 -> CV 无定义
    r = repeat([m(-1), m(0), m(1)])
    assert r.status_code == 200
    body = r.json()
    assert body["mean"] == 0.0
    assert body["range"] == 2.0
    # 样本方差 = (1 + 0 + 1)/2 = 1
    assert body["sample_std_dev"] == pytest.approx(1.0)
    assert body["coefficient_of_variation"] is None


def test_negative_mean_uses_absolute_value_for_cv():
    # -1, -3 mm：均值 -2；平方偏差和 1+1=2，样本方差 2/(2-1)=2，s = sqrt(2)
    r = repeat([m(-1), m(-3)])
    assert r.status_code == 200
    body = r.json()
    assert body["mean"] == -2.0
    assert body["sample_std_dev"] == pytest.approx(math.sqrt(2))
    # CV = s / |mean| = sqrt(2)/2（用均值绝对值）
    assert body["coefficient_of_variation"] == pytest.approx(math.sqrt(2) / 2)


def test_dimensionless_measurements():
    r = repeat([m(0.10, "%"), m(0.20, "1"), m(0.15, "1")], unit="1")
    assert r.status_code == 200
    body = r.json()
    assert body["unit"] == "1"
    assert body["dimension"] == [0, 0, 0, 0, 0, 0, 0]
    # 0.10 % = 0.001（无量纲）；[0.001, 0.2, 0.15]
    assert body["mean"] == pytest.approx((0.001 + 0.2 + 0.15) / 3)
    assert body["range"] == pytest.approx(0.2 - 0.001)


def test_affine_temperature_mixed_scales():
    # 0 °C、32 °F 都是同一温度点 273.15 K；目标 K
    r = repeat([m(0, "°C"), m(32, "°F")], unit="K")
    assert r.status_code == 200
    body = r.json()
    assert body["unit"] == "K"
    assert body["mean"] == pytest.approx(273.15)
    assert body["sample_std_dev"] == 0.0
    assert body["range"] == 0.0
    assert body["coefficient_of_variation"] == 0.0


def test_imperial_units_converted():
    # 1 in = 25.4 mm，2 in = 50.8 mm
    r = repeat([m(1, "in"), m(2, "in")], unit="mm")
    assert r.status_code == 200
    body = r.json()
    assert body["mean"] == pytest.approx(38.1)
    assert body["range"] == pytest.approx(25.4)
    assert body["sample_std_dev"] == pytest.approx(25.4 / math.sqrt(2))


def test_sample_std_dev_uses_n_minus_one():
    # 与总体标准差（除以 n）区分：[2, 4, 4, 4, 5, 5, 7, 9]
    # mean=5，平方偏差和 = 9+1+1+1+0+0+4+16 = 32
    # 样本方差 = 32/7 ≈ 4.5714，s ≈ 2.138
    r = repeat([m(2), m(4), m(4), m(4), m(5), m(5), m(7), m(9)])
    assert r.status_code == 200
    body = r.json()
    assert body["mean"] == pytest.approx(5.0)
    assert body["sample_std_dev"] == pytest.approx(math.sqrt(32 / 7))
    assert body["range"] == 7.0


def test_root_lists_repeatability_endpoint():
    r = client.get("/")
    assert r.status_code == 200
    assert "/repeatability" in r.json()["endpoints"]


# ---------------------------------------------------------------------------
# 422：量纲 / 单位 / 数值非法（含字段定位）
# ---------------------------------------------------------------------------

def test_fewer_than_two_measurements_rejected():
    r = repeat([m(10)])
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "INVALID_REQUEST"
    assert "measurements" in err["message"]

    r = repeat([])
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_REQUEST"


def test_unknown_target_unit_rejected():
    r = repeat([m(1), m(2)], unit="foo")
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "UNKNOWN_UNIT"
    assert err["field"] == "unit"


def test_target_unit_dimension_mismatch():
    r = repeat([m(1), m(2)], unit="s")
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "UNIT_DIM_MISMATCH"
    assert err["field"] == "unit"


def test_inconsistent_measurement_units_rejected():
    r = repeat([m(1, "mm"), m(2, "s")])
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "DIMENSION_MISMATCH"
    assert err["field"] == "measurements[1].unit"
    assert "measurements[0]" in err["message"]


def test_unknown_measurement_unit_rejected():
    r = repeat([m(1, "mm"), m(2, "foo")])
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "UNKNOWN_UNIT"
    assert err["field"] == "measurements[1].unit"


def test_non_finite_measurement_value_rejected():
    # httpx 的 json 编码器拒绝 NaN，改用原始请求体模拟非严格 JSON 客户端
    body = '{"measurements":[{"value":1,"unit":"mm"},{"value":NaN,"unit":"mm"}],' \
           '"unit":"mm"}'
    r = client.post("/repeatability", content=body,
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "INVALID_VALUE"
    assert err["field"] == "measurements[1].value"


def test_missing_required_fields_rejected():
    r = client.post("/repeatability", json={})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "INVALID_REQUEST"
    assert "measurements" in err["message"]
    assert "unit" in err["message"]


def test_measurement_requires_unit():
    r = client.post("/repeatability",
                    json={"measurements": [{"value": 1}, {"value": 2}],
                          "unit": "mm"})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "INVALID_REQUEST"
    assert "unit" in err["message"]


def test_huge_values_overflow_rejected_as_422():
    # 平方和超出有限 float：标准差溢出，按 NUMERIC_OVERFLOW 拒绝而非 500
    big = 1e200
    r = repeat([m(big), m(big * 1.001)])
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "NUMERIC_OVERFLOW"
    assert err["field"] == "measurements"
