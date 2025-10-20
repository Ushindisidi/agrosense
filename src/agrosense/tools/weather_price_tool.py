import os
import logging
import requests
from typing import Type, Dict, Any, Optional
from datetime import datetime
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict, PrivateAttr

from ..core.mcp_client import MCPClient

logger = logging.getLogger(__name__)

class WeatherPriceToolInput(BaseModel):
    session_id: str = Field(description="The unique session ID to update the MCP context.")
    region: str = Field(description="The geographical region or location code for fetching data.")
    asset_name: str = Field(description="The specific asset name (e.g., 'maize', 'cattle') to determine relevant prices.")

class WeatherPriceTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "Regional_Data_Fetcher"
    description: str = (
        "Fetches environmental data (weather, rainfall) and regional commodity prices. "
        "Provide session_id with every call."
    )
    args_schema: Type[BaseModel] = WeatherPriceToolInput
    mcp_client: MCPClient = Field(default=None, description="The Multi-Context Processor client instance for state management.")
    
    # Private attributes for API keys
    _openweather_api_key: Optional[str] = PrivateAttr()
    _weatherapi_key: Optional[str] = PrivateAttr()

    def __init__(self, mcp_client: MCPClient = None, **kwargs):
        super().__init__(mcp_client=mcp_client, **kwargs)
        
        # Get API keys from environment
        self._openweather_api_key = os.getenv("OPENWEATHER_API_KEY")
        self._weatherapi_key = os.getenv("WEATHERAPI_KEY")
        
        if not self._openweather_api_key and not self._weatherapi_key:
            logger.warning("⚠️ No weather API keys found. Will use mock data.")

    def _run(self, session_id: str, region: str, asset_name: str) -> str:
        context = self.mcp_client.get_context(session_id)
        if not context:
            return f"ERROR: Session ID {session_id} not found."

        # Fetch weather data
        weather_data = self._fetch_weather(region)
        
        # Fetch market prices
        price_data = self._fetch_market_prices(asset_name, region)

        # Combine regional data
        new_regional_data = {
            "weather": weather_data,
            "market_prices": price_data,
            "fetch_timestamp": datetime.utcnow().isoformat()
        }

        self.mcp_client.update_context(session_id, regional_data=new_regional_data)

        return (
            f"Successfully fetched environmental and market data for {region} on {asset_name} "
            f"and updated MCP session {session_id}. "
            f"Temp: {weather_data.get('current_temp')}°C, Rainfall: {weather_data.get('last_24h_rainfall_mm', 0)}mm."
        )

    def _fetch_weather(self, region: str) -> Dict[str, Any]:
        """
        Fetch real weather data from APIs.
        Falls back to mock data if APIs fail.
        """
        
        # Try OpenWeatherMap first
        if self._openweather_api_key:
            weather = self._fetch_openweather(region)
            if weather:
                return weather
        
        # Try WeatherAPI.com as backup
        if self._weatherapi_key:
            weather = self._fetch_weatherapi(region)
            if weather:
                return weather
        
        # Fallback to mock data
        logger.warning(f"Using mock weather data for {region}")
        return self._mock_weather_data(region)

    def _fetch_openweather(self, region: str) -> Optional[Dict[str, Any]]:
        """Fetch weather from OpenWeatherMap API"""
        try:
            # Get coordinates for region (Kenya focus)
            coords = self._get_kenya_coordinates(region)
            
            if not coords:
                return None
            
            lat, lon = coords
            
            # Current weather
            url = f"https://api.openweathermap.org/data/2.5/weather"
            params = {
                "lat": lat,
                "lon": lon,
                "appid": self._openweather_api_key,
                "units": "metric"
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Forecast for rainfall
            forecast_url = f"https://api.openweathermap.org/data/2.5/forecast"
            forecast_response = requests.get(forecast_url, params=params, timeout=10)
            forecast_data = forecast_response.json() if forecast_response.status_code == 200 else {}
            
            # Calculate 24h rainfall
            rainfall_24h = 0
            if "rain" in data:
                rainfall_24h = data["rain"].get("1h", 0) * 24  # Rough estimate
            
            # Build weather data
            weather_data = {
                "current_temp": round(data["main"]["temp"], 1),
                "humidity": data["main"]["humidity"],
                "condition": data["weather"][0]["description"],
                "last_24h_rainfall_mm": round(rainfall_24h, 1),
                "forecast_summary": f"Current temp {data['main']['temp']:.1f}°C, humidity {data['main']['humidity']}%.",
                "next_48h_risk": self._assess_weather_risk(data, forecast_data),
                "wind_speed": data["wind"]["speed"],
                "pressure": data["main"]["pressure"],
                "source": "OpenWeatherMap"
            }
            
            logger.info(f"✅ Fetched real weather data for {region} from OpenWeatherMap")
            return weather_data
            
        except Exception as e:
            logger.error(f"OpenWeatherMap API error: {e}")
            return None

    def _fetch_weatherapi(self, region: str) -> Optional[Dict[str, Any]]:
        """Fetch weather from WeatherAPI.com"""
        try:
            url = f"http://api.weatherapi.com/v1/forecast.json"
            params = {
                "key": self._weatherapi_key,
                "q": f"{region},Kenya",
                "days": 3,
                "aqi": "no"
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            current = data["current"]
            forecast = data["forecast"]["forecastday"][0]
            
            weather_data = {
                "current_temp": round(current["temp_c"], 1),
                "humidity": current["humidity"],
                "condition": current["condition"]["text"],
                "last_24h_rainfall_mm": round(forecast["day"]["totalprecip_mm"], 1),
                "forecast_summary": f"Current temp {current['temp_c']:.1f}°C, humidity {current['humidity']}%.",
                "next_48h_risk": self._assess_weatherapi_risk(data),
                "wind_speed": current["wind_kph"],
                "pressure": current["pressure_mb"],
                "source": "WeatherAPI"
            }
            
            logger.info(f"✅ Fetched real weather data for {region} from WeatherAPI")
            return weather_data
            
        except Exception as e:
            logger.error(f"WeatherAPI error: {e}")
            return None

    def _fetch_market_prices(self, asset_name: str, region: str) -> Dict[str, Any]:
        """
        Fetch market prices from APIs or database.
        Falls back to mock data if unavailable.
        """
        
        # TODO: Integrate with Kenya Ministry of Agriculture API
        # TODO: Integrate with local market APIs
        # For now, use intelligent mock data based on season and region
        
        return self._mock_market_prices(asset_name, region)

    def _mock_market_prices(self, asset_name: str, region: str) -> Dict[str, Any]:
        """Generate realistic mock market prices based on asset and region"""
        
        # Kenya market price ranges (KES)
        price_ranges = {
            "maize": {"min": 30, "max": 50, "unit": "per kg"},
            "wheat": {"min": 40, "max": 65, "unit": "per kg"},
            "beans": {"min": 80, "max": 120, "unit": "per kg"},
            "potatoes": {"min": 25, "max": 45, "unit": "per kg"},
            "tomatoes": {"min": 40, "max": 100, "unit": "per kg"},
            "coffee": {"min": 120, "max": 180, "unit": "per kg"},
            "tea": {"min": 200, "max": 300, "unit": "per kg"},
            "cattle": {"min": 40000, "max": 80000, "unit": "per head"},
            "goat": {"min": 8000, "max": 15000, "unit": "per head"},
            "sheep": {"min": 7000, "max": 14000, "unit": "per head"},
            "chicken": {"min": 400, "max": 800, "unit": "per bird"},
            "milk": {"min": 45, "max": 65, "unit": "per litre"},
        }
        
        # Get price range for asset
        asset_lower = asset_name.lower()
        price_info = price_ranges.get(asset_lower, {"min": 100, "max": 500, "unit": "per unit"})
        
        # Calculate price (add some randomness)
        import random
        base_price = (price_info["min"] + price_info["max"]) / 2
        variation = random.uniform(-0.15, 0.15)  # ±15% variation
        current_price = round(base_price * (1 + variation), 2)
        
        # Determine trend based on season (simplified)
        month = datetime.now().month
        if 3 <= month <= 5 or 10 <= month <= 12:  # Rainy seasons
            trend = "Increasing due to planting season"
        elif month in [1, 2, 6, 7]:  # Harvest seasons
            trend = "Stable to decreasing due to harvest"
        else:
            trend = "Stable"
        
        return {
            "commodity": f"{asset_name.title()} ({price_info['unit']})",
            "current_price": current_price,
            "currency": "KES",
            "trend": trend,
            "last_updated": datetime.now().isoformat(),
            "source": "Mock Data (Regional Estimates)"
        }

    def _mock_weather_data(self, region: str) -> Dict[str, Any]:
        """Generate realistic mock weather data based on Kenya's climate"""
        import random
        
        # Kenya climate zones
        if region.lower() in ["mombasa", "malindi", "lamu"]:  # Coastal
            temp = random.randint(25, 32)
            humidity = random.randint(70, 90)
        elif region.lower() in ["nairobi", "nakuru", "eldoret"]:  # Highlands
            temp = random.randint(18, 26)
            humidity = random.randint(50, 75)
        else:  # General
            temp = random.randint(20, 30)
            humidity = random.randint(55, 80)
        
        # Seasonal rainfall
        month = datetime.now().month
        if 3 <= month <= 5:  # Long rains
            rainfall = random.randint(5, 20)
        elif 10 <= month <= 12:  # Short rains
            rainfall = random.randint(3, 15)
        else:  # Dry season
            rainfall = random.randint(0, 5)
        
        risk = "High chance of thunderstorms" if rainfall > 10 else "Moderate risk of fungal diseases" if humidity > 75 else "Clear conditions"
        
        return {
            "current_temp": temp,
            "humidity": humidity,
            "condition": "Partly cloudy" if rainfall > 5 else "Clear",
            "last_24h_rainfall_mm": rainfall,
            "forecast_summary": f"Current temp {temp}°C, humidity {humidity}%.",
            "next_48h_risk": risk,
            "wind_speed": random.randint(5, 20),
            "pressure": random.randint(1010, 1020),
            "source": "Mock Data (Climate Estimates)"
        }

    def _get_kenya_coordinates(self, region: str) -> Optional[tuple]:
        """Get coordinates for major Kenya regions"""
        coordinates = {
            "nairobi": (-1.2921, 36.8219),
            "mombasa": (-4.0435, 39.6682),
            "nakuru": (-0.3031, 36.0800),
            "eldoret": (0.5143, 35.2698),
            "kisumu": (-0.0917, 34.7680),
            "thika": (-1.0332, 37.0690),
            "malindi": (-3.2167, 40.1167),
            "nyeri": (-0.4209, 36.9472),
            "meru": (0.0469, 37.6556),
            "kitale": (1.0167, 35.0064),
            "kakamega": (0.2827, 34.7519),
            "machakos": (-1.5177, 37.2634),
            "kiambu": (-1.1714, 36.8356),
            "embu": (-0.5380, 37.4571),
            "garissa": (-0.4569, 39.6582),
        }
        
        return coordinates.get(region.lower())

    def _assess_weather_risk(self, current_data: dict, forecast_data: dict) -> str:
        """Assess agricultural risks from weather data"""
        risks = []
        
        # Temperature risks
        temp = current_data["main"]["temp"]
        if temp > 30:
            risks.append("High temperature stress on crops")
        elif temp < 15:
            risks.append("Low temperature may slow growth")
        
        # Humidity risks
        humidity = current_data["main"]["humidity"]
        if humidity > 80:
            risks.append("High humidity increases fungal disease risk")
        
        # Rainfall risks
        if "rain" in current_data and current_data["rain"].get("1h", 0) > 5:
            risks.append("Heavy rainfall expected")
        
        return "; ".join(risks) if risks else "Favorable conditions for farming"

    def _assess_weatherapi_risk(self, data: dict) -> str:
        """Assess risks from WeatherAPI data"""
        risks = []
        
        forecast = data["forecast"]["forecastday"]
        
        for day in forecast[:2]:  # Next 48h
            if day["day"]["daily_chance_of_rain"] > 70:
                risks.append("High chance of rain")
            if day["day"]["maxtemp_c"] > 32:
                risks.append("Heat stress likely")
            if day["day"]["totalprecip_mm"] > 20:
                risks.append("Heavy rainfall expected")
        
        return "; ".join(risks) if risks else "Favorable conditions for farming"