"""POST /repeatability 端到端测试（FastAPI TestClient）。"""
import math

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def m(value, unit="m"):
    return {"value": value, "unit": unit}


def repeat(measurements, unit="m"):
    return client.post("/repeatability",
                       json={"measurements": measurements, "unit": unit})


# ---------------------------------------------------------------------------
# 正常路径
# ---------------------------------------------------------------------------

def test_basic_statistics_same_unit():
    r = repeat([m(1), m(2), m(3)])
    assert r.status_code == 200
    body = r.json()
    assert body["unit"] == "m"
    assert body["dimension"] == [1, 0, 0, 0, 0, 0, 0]
    assert body["dimension_text"] == "m"
    assert body["count"] == 3
    assert body["mean"] == 2.0
    assert body["sample_stddev"] == 1.0
    assert body["range"] == 2.0
    assert body["coefficient_of_variation"] == 0.5


def test_sample_stddev_uses_n_minus_one():
    # n=2：样本标准差 sqrt(((0-5)^2 + (10-5)^2) / 1) = sqrt(50)
    r = repeat([m(0), m(10)])
    assert r.status_code == 200
    body = r.json()
    assert body["mean"] == 5.0
    assert abs(body["sample_stddev"] - math.sqrt(50)) < 1e-12
    assert body["range"] == 10.0
    # 总体标准差（分母 n）会是 5，样本标准差必须不是 5
    assert body["sample_stddev"] != 5.0


def test_mixed_units_converted_to_target_unit():
    # 100 cm = 1000 mm；1.02 m = 1020 mm
    r = repeat([m(100, "cm"), m(1.02, "m")], unit="mm")
    assert r.status_code == 200
    body = r.json()
    assert body["unit"] == "mm"
    assert body["count"] == 2
    assert body["mean"] == 1010.0
    assert abs(body["sample_stddev"] - math.sqrt(200)) < 1e-9
    assert body["range"] == 20.0
    assert abs(body["coefficient_of_variation"] - math.sqrt(200) / 1010) < 1e-12


def test_results_independent_of_input_order():
    r1 = repeat([m(1), m(2), m(3)])
    r2 = repeat([m(3), m(1), m(2)])
    assert r1.json() == r2.json()


def test_equal_measurements_zero_spread():
    r = repeat([m(5, "mm"), m(5, "mm"), m(5, "mm")], unit="mm")
    assert r.status_code == 200
    body = r.json()
    assert body["mean"] == 5.0
    assert body["sample_stddev"] == 0.0
    assert body["range"] == 0.0
    assert body["coefficient_of_variation"] == 0.0


def test_zero_mean_returns_null_cv():
    r = client.post("/repeatability", json={
        "measurements": [{"value": -1, "unit": "1"}, {"value": 1, "unit": "1"}],
        "unit": "1",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["mean"] == 0.0
    assert abs(body["sample_stddev"] - math.sqrt(2)) < 1e-12
    assert body["range"] == 2.0
    assert body["coefficient_of_variation"] is None


def test_dimensionless_percent_converted_to_one():
    # 50% = 0.5，25% = 0.25
    r = client.post("/repeatability", json={
        "measurements": [{"value": 50, "unit": "%"}, {"value": 25, "unit": "%"}],
        "unit": "1",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["unit"] == "1"
    assert body["mean"] == 0.375
    assert abs(body["sample_stddev"] - math.sqrt(2) * 0.125) < 1e-12
    assert body["range"] == 0.25
    assert abs(body["coefficient_of_variation"] - math.sqrt(2) * 0.125 / 0.375) < 1e-12


def test_affine_temperature_converted_to_kelvin():
    # 0 °C 与 100 °C -> 273.15 K、373.15 K
    r = repeat([m(0, "°C"), m(100, "°C")], unit="K")
    assert r.status_code == 200
    body = r.json()
    assert body["unit"] == "K"
    assert abs(body["mean"] - 323.15) < 1e-9
    assert abs(body["sample_stddev"] - math.sqrt(5000)) < 1e-9
    assert abs(body["range"] - 100.0) < 1e-9
    assert abs(body["coefficient_of_variation"] - math.sqrt(5000) / 323.15) < 1e-9


def test_mixed_temperature_scales_same_dimension():
    # 32 °F = 0 °C = 273.15 K；100 °C = 373.15 K
    r = repeat([m(32, "°F"), m(100, "°C")], unit="K")
    assert r.status_code == 200
    body = r.json()
    assert abs(body["mean"] - 323.15) < 1e-9
    assert abs(body["range"] - 100.0) < 1e-9


def test_imperial_units_converted_to_si():
    # 1 in = 0.0254 m，1 ft = 0.3048 m
    r = repeat([m(1, "in"), m(1, "ft")], unit="m")
    assert r.status_code == 200
    body = r.json()
    assert abs(body["mean"] - (0.0254 + 0.3048) / 2) < 1e-12
    assert abs(body["range"] - (0.3048 - 0.0254)) < 1e-12


def test_root_lists_repeatability_endpoint():
    r = client.get("/")
    assert r.status_code == 200
    assert "/repeatability" in r.json()["endpoints"]


# ---------------------------------------------------------------------------
# 422：量纲 / 单位 / 数值非法（含字段定位）
# ---------------------------------------------------------------------------

def test_fewer_than_two_measurements_rejected():
    r = repeat([m(1)])
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "INVALID_REQUEST"
    assert "measurements" in err["message"]


def test_missing_required_fields():
    r = client.post("/repeatability", json={})
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
    r = repeat([m(1, "m"), m(2, "s")])
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "DIMENSION_MISMATCH"
    assert err["field"] == "measurements[1].unit"


def test_unknown_measurement_unit_rejected():
    r = repeat([m(1, "m"), m(2, "foo")])
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "UNKNOWN_UNIT"
    assert err["field"] == "measurements[1].unit"


def test_non_finite_measurement_value_rejected():
    # httpx 的 json 编码器拒绝 NaN，改用原始请求体模拟非严格 JSON 客户端
    body = '{"measurements":[{"value":NaN,"unit":"m"},{"value":2,"unit":"m"}],"unit":"m"}'
    r = client.post("/repeatability", content=body,
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "INVALID_VALUE"
    assert err["field"] == "measurements[0].value"
