"""Fixture tests for the data-source parsers.

These cover the pure parse step of each scraper against a small sample of the
real upstream format. They run offline (no network), so CI catches upstream
format drift -- which has repeatedly broken these feeds -- instead of a zone
silently going dark in production.
"""

from datetime import datetime, timezone

from carbon_mesh.carbon_sources.aemo import region_fuel_from_oe
from carbon_mesh.carbon_sources.canada import aeso_fuel_mix, ieso_fuel_mix
from carbon_mesh.carbon_sources.entsoe_forecast import _series_by_hour
from carbon_mesh.carbon_sources.flow_tracing import _parse_flow_latest
from carbon_mesh.carbon_sources.taiwan import _fuel_of, fuel_mix_from_rows

# --- Taiwan (Taipower per-unit JSON rows) ---


def test_taiwan_fuel_mix_sums_by_fuel_and_skips_storage_load():
    rows = [
        ["<a></a><b>燃煤(Coal)</b>", "", "unitA", "1000", "800", "x"],
        ["<b>燃氣(LNG)</b>", "", "unitB", "600", "400.5", "x"],
        ["<b>太陽能(Solar)</b>", "", "unitC", "300", "100", "x"],
        ["<b>儲能負載(Energy Storage System Load)</b>", "", "unitD", "50", "-20", "x"],
        ["<b>風力(Wind)</b>", "", "unitE", "200", "0", "x"],  # zero output dropped
    ]
    mix = fuel_mix_from_rows(rows)
    assert mix == {"coal": 800.0, "natural_gas": 400.5, "solar": 100.0}


def test_taiwan_fuel_label_mapping():
    assert _fuel_of("燃煤(Coal)") == "coal"
    assert _fuel_of("汽電共生(Co-Gen)") == "natural_gas"
    assert _fuel_of("其它再生能源(Other Renewable Energy)") == "geothermal"
    assert _fuel_of("儲能負載(Energy Storage System Load)") is None


# --- Canada: IESO (XML) and AESO (HTML) ---


def test_ieso_uses_latest_hour_with_generation():
    xml = b"""<Document><DocBody><DailyData><Day>2026-06-10</Day>
      <HourlyData><Hour>1</Hour>
        <FuelTotal><Fuel>NUCLEAR</Fuel><EnergyValue><Output>9000</Output></EnergyValue></FuelTotal>
      </HourlyData>
      <HourlyData><Hour>2</Hour>
        <FuelTotal><Fuel>NUCLEAR</Fuel><EnergyValue><Output>9500</Output></EnergyValue></FuelTotal>
        <FuelTotal><Fuel>GAS</Fuel><EnergyValue><Output>2000</Output></EnergyValue></FuelTotal>
        <FuelTotal><Fuel>HYDRO</Fuel><EnergyValue><Output>3000</Output></EnergyValue></FuelTotal>
        <FuelTotal><Fuel>WIND</Fuel><EnergyValue><Output>500</Output></EnergyValue></FuelTotal>
      </HourlyData>
    </DailyData></DocBody></Document>"""
    mix = ieso_fuel_mix(xml)
    assert mix == {"nuclear": 9500.0, "natural_gas": 2000.0, "hydro": 3000.0, "wind": 500.0}


def test_aeso_reads_tng_column_and_maps_gas_plant_types():
    html = (
        "<TR><TD>COAL</TD><TD>500</TD><TD>0</TD><TD>0</TD></TR>"
        "<TR><TD>COGENERATION</TD><TD>6000</TD><TD>3900</TD><TD>20</TD></TR>"
        "<TR><TD>COMBINED CYCLE</TD><TD>4000</TD><TD>1300</TD><TD>10</TD></TR>"
        "<TR><TD>WIND</TD><TD>5000</TD><TD>2000</TD><TD>0</TD></TR>"
        "<TR><TD>HYDRO</TD><TD>900</TD><TD>300</TD><TD>200</TD></TR>"
        "<TR><TD>TOTAL</TD><TD>19900</TD><TD>7500</TD><TD>230</TD></TR>"
    )
    mix = aeso_fuel_mix(html)
    # TNG (2nd number); gas plant types fold into natural_gas; TOTAL is ignored.
    assert mix["natural_gas"] == 5200.0  # 3900 + 1300
    assert mix["wind"] == 2000.0
    assert mix["hydro"] == 300.0
    assert "TOTAL" not in mix and mix.get("coal", 0) == 0.0


# --- Australia (OpenElectricity per-region/fueltech series) ---


def test_openelectricity_latest_nonnull_per_region_and_fuel():
    data = {
        "data": [
            {
                "results": [
                    {
                        "columns": {"region": "NSW1", "fueltech_group": "coal"},
                        "data": [["t1", 4000], ["t2", 4100]],
                    },
                    {
                        "columns": {"region": "NSW1", "fueltech_group": "wind"},
                        "data": [["t1", 1000], ["t2", None]],
                    },
                    {
                        "columns": {"region": "NSW1", "fueltech_group": "battery"},
                        "data": [["t2", 50]],
                    },
                    {
                        "columns": {"region": "VIC1", "fueltech_group": "gas"},
                        "data": [["t2", 2000]],
                    },
                ]
            }
        ]
    }
    rf = region_fuel_from_oe(data, ["AU-NSW", "AU-VIC"])
    assert rf["AU-NSW"] == {"coal": 4100.0, "wind": 1000.0}  # last non-null; battery skipped
    assert rf["AU-VIC"] == {"natural_gas": 2000.0}


# --- ENTSO-E forecast (A69/A65) hourly series ---


def test_entsoe_series_by_hour_sums_psr_and_buckets_by_hour():
    xml = """<doc xmlns="urn:test">
      <TimeSeries>
        <MktPSRType><psrType>B16</psrType></MktPSRType>
        <Period>
          <timeInterval><start>2026-06-10T00:00Z</start></timeInterval>
          <resolution>PT60M</resolution>
          <Point><position>1</position><quantity>100</quantity></Point>
          <Point><position>2</position><quantity>200</quantity></Point>
        </Period>
      </TimeSeries>
      <TimeSeries>
        <MktPSRType><psrType>B19</psrType></MktPSRType>
        <Period>
          <timeInterval><start>2026-06-10T00:00Z</start></timeInterval>
          <resolution>PT60M</resolution>
          <Point><position>1</position><quantity>50</quantity></Point>
          <Point><position>2</position><quantity>60</quantity></Point>
        </Period>
      </TimeSeries>
    </doc>"""
    series = _series_by_hour(xml, {"B16", "B19"})
    h0 = datetime(2026, 6, 10, 0, tzinfo=timezone.utc)
    h1 = datetime(2026, 6, 10, 1, tzinfo=timezone.utc)
    assert series[h0] == 150.0  # B16 100 + B19 50
    assert series[h1] == 260.0  # B16 200 + B19 60


# --- ENTSO-E physical flow (A11) ---


def test_parse_flow_latest_returns_last_point():
    xml = """<doc xmlns="urn:test"><TimeSeries><Period>
      <Point><position>1</position><quantity>500</quantity></Point>
      <Point><position>2</position><quantity>650</quantity></Point>
    </Period></TimeSeries></doc>"""
    assert _parse_flow_latest(xml) == 650.0
    assert _parse_flow_latest("not xml") is None
