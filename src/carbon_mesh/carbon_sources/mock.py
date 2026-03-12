from datetime import datetime, timezone

from carbon_mesh.models.carbon import CarbonIntensity

# Realistic mock data based on typical grid carbon intensities (gCO2/kWh)
# Sources: Electricity Maps historical averages
_MOCK_DATA: dict[str, tuple[float, float]] = {
    # (carbon_intensity, renewable_pct)
    # North America — US
    "US-MIDA-PJM": (350, 15),       # Virginia/PJM — heavy gas + coal
    "US-CAL-CISO": (200, 45),       # California — significant solar
    "US-NW-BPAT": (50, 90),         # Oregon/BPA — dominated by hydro
    "US-MIDW-MISO": (400, 20),      # Midwest — coal heavy
    "US-SE-SOCO": (380, 12),        # Southeast — gas + coal
    "US-SW-NEVP": (320, 25),        # Nevada — some solar
    "US-SW-AZPS": (340, 22),        # Arizona — some solar
    "US-TEX-ERCO": (350, 28),       # Texas — gas + growing wind/solar
    # North America — Canada
    "CA-QC": (10, 99),              # Quebec — nearly 100% hydro
    "CA-ON": (30, 92),              # Ontario — hydro + nuclear
    "CA-AB": (450, 15),             # Alberta — gas + coal
    "CA-BC": (15, 97),              # British Columbia — hydro
    # UK
    "GB": (180, 55),                # UK national — offshore wind + nuclear
    "GB-1": (120, 65),              # North Scotland — wind
    "GB-2": (130, 62),              # South Scotland — wind
    "GB-16": (100, 72),             # Scotland — high wind
    # Europe
    "IE": (280, 40),                # Ireland — growing wind
    "FR": (50, 92),                 # France — nuclear + hydro
    "DE": (300, 45),                # Germany — renewables + coal
    "ES": (170, 50),                # Spain — solar + wind
    "PT": (150, 55),                # Portugal — wind + hydro
    "NL": (310, 35),                # Netherlands — gas + wind
    "BE": (150, 40),                # Belgium — nuclear + wind
    "AT": (100, 75),                # Austria — hydro + wind
    "CH": (25, 96),                 # Switzerland — hydro + nuclear
    "PL": (600, 18),                # Poland — very coal heavy
    "CZ": (400, 15),                # Czech Republic — coal + nuclear
    "DK-DK1": (120, 70),            # Denmark West — wind
    "DK-DK2": (130, 68),            # Denmark East — wind
    "FI": (80, 85),                 # Finland — nuclear + hydro + wind
    "SE-SE1": (12, 98),             # Sweden N — hydro
    "SE-SE2": (13, 98),             # Sweden mid — hydro
    "SE-SE3": (15, 98),             # Sweden Stockholm — hydro + wind + nuclear
    "SE-SE4": (18, 96),             # Sweden S — wind
    "NO-NO1": (15, 98),             # Norway Oslo — hydro
    "NO-NO2": (12, 99),             # Norway SW — hydro
    "NO-NO3": (10, 99),             # Norway mid — hydro
    "NO-NO4": (8, 99),              # Norway N — hydro
    "NO-NO5": (10, 99),             # Norway W — hydro
    "IT-NO": (250, 35),             # Italy North — gas + hydro
    "GR": (350, 30),                # Greece — gas + lignite
    "RO": (250, 40),                # Romania — hydro + nuclear + wind
    "BG": (380, 20),                # Bulgaria — coal + nuclear
    "HU": (200, 15),                # Hungary — nuclear + gas
    "SK": (130, 25),                # Slovakia — nuclear + hydro
    "HR": (150, 55),                # Croatia — hydro
    "RS": (600, 8),                 # Serbia — very coal heavy
    "SI": (200, 35),                # Slovenia — nuclear + hydro
    "EE": (400, 25),                # Estonia — oil shale
    "LV": (100, 55),                # Latvia — hydro + wind
    "LT": (120, 45),                # Lithuania — wind
    "IS": (15, 100),                # Iceland — geothermal + hydro
    # Australia
    "AU-NSW": (550, 18),             # New South Wales — coal heavy
    "AU-QLD": (600, 15),             # Queensland — coal heavy
    "AU-VIC": (650, 20),             # Victoria — brown coal
    "AU-SA": (200, 60),              # South Australia — wind + solar
    "AU-TAS": (30, 95),              # Tasmania — hydro
    # India
    "IN-NO": (650, 18),              # Northern — coal heavy
    "IN-SO": (500, 30),              # Southern — more solar
    "IN-EA": (750, 10),              # Eastern — very coal heavy
    "IN-WE": (550, 25),              # Western — mixed
    "IN-NE": (400, 40),              # North-Eastern — hydro
    # Brazil
    "BR-S": (80, 85),                # South — hydro
    "BR-SE": (120, 70),              # Southeast — hydro + thermal
    "BR-NE": (100, 75),              # Northeast — wind + hydro
    "BR-N": (60, 90),                # North — hydro
    "BR-CS": (110, 72),              # Centro-South — mixed
    # South Africa
    "ZA": (780, 8),                   # South Africa — ~85% coal
    # Asia-Pacific
    "SG": (400, 5),                   # Singapore — almost all gas
    "JP-TK": (450, 20),              # Tokyo — gas + coal
    "JP-KN": (430, 18),              # Kansai — gas + nuclear
    "KR": (420, 10),                  # South Korea — coal + gas + nuclear
    "TW": (500, 10),                  # Taiwan — coal + gas
    "HK": (450, 5),                   # Hong Kong — gas + coal
    "ID": (650, 12),                  # Indonesia — coal heavy
    "TH": (400, 10),                  # Thailand — gas + coal
    "VN": (500, 15),                  # Vietnam — coal + hydro
    "PH": (500, 15),                  # Philippines — coal + gas
    "MY": (450, 8),                   # Malaysia — gas + coal
    # Middle East
    "AE": (420, 5),                   # UAE — gas + some solar
    "SA": (500, 3),                   # Saudi Arabia — almost all oil/gas
    "IL": (400, 12),                  # Israel — gas + growing solar
    "TR": (350, 30),                  # Turkey — mixed
    # Americas
    "CL-SEN": (250, 40),             # Chile — solar + hydro
    "AR": (300, 20),                  # Argentina — gas + hydro
    "CO": (150, 70),                  # Colombia — hydro
    "MX": (400, 20),                  # Mexico — gas + oil
    "UY": (30, 95),                   # Uruguay — wind + hydro
    "PY": (10, 100),                  # Paraguay — Itaipu hydro
    "CR": (20, 98),                   # Costa Rica — hydro + geothermal
    # Oceania
    "NZ-NZN": (100, 80),             # New Zealand North — geothermal + hydro
    "NZ-NZS": (60, 90),              # New Zealand South — hydro
}


class MockCarbonSource:
    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity:
        data = _MOCK_DATA.get(grid_zone, (250, 30))
        return CarbonIntensity(
            grid_zone=grid_zone,
            carbon_intensity_gco2_kwh=data[0],
            renewable_percentage=data[1],
            timestamp=datetime.now(timezone.utc),
            source="mock",
        )

    async def get_carbon_intensity_batch(
        self, grid_zones: list[str]
    ) -> dict[str, CarbonIntensity]:
        results = {}
        for zone in grid_zones:
            results[zone] = await self.get_carbon_intensity(zone)
        return results
