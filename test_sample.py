"""
Weather service with forecasting and comparison features.
"""

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
import requests


@dataclass
class WeatherData:
    """Data class for weather information."""
    temperature: float
    humidity: int
    description: str
    timestamp: datetime
    city: str
    country: Optional[str] = None


class WeatherService:
    """Service class for fetching and processing weather data."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.openweathermap.org"):
        self.api_key = api_key
        self.base_url = base_url
    
def get_weather(self, city: str, country: Optional[str] = None) -> Optional[WeatherData]:
    """Fetch weather data for a given city."""
    location = f"{city},{country}" if country else city
try:
        f"{self.base_url}/data/2.5/weather",
        params={
            "q": location,
            "appid": self.api_key,
            "units": "metric"
        }
    )
    data = response.json()
    data = response.json()
            
            return WeatherData(
                temperature=data["main"]["temp"],
                humidity=data["main"]["humidity"],
                description=data["weather"][0]["description"],
                timestamp=datetime.fromtimestamp(data["dt"]),
                city=data["name"],
                country=data["sys"].get("country")
            )
        except requests.RequestException as e:
            print(f"Error fetching weather: {e}")
            return None
    
def get_forecast(self, city: str, days: int = 5) -> List[WeatherData]:
    """Get weather forecast for multiple days."""
    try:
            f"{self.base_url}/data/2.5/forecast",
            params={
                "q": city,
                "appid": self.api_key,
                "units": "metric"
            }
        )
        data = response.json()
            
            forecasts = []
            # Group by day (API returns 3-hour intervals)
            daily_data = {}
            for item in data["list"]:
                date = datetime.fromtimestamp(item["dt"]).date()
                if date not in daily_data:
                    daily_data[date] = item
            
            for date, item in list(daily_data.items())[:days]:
                forecasts.append(WeatherData(
                    temperature=item["main"]["temp"],
                    humidity=item["main"]["humidity"],
                    description=item["weather"][0]["description"],
                    timestamp=datetime.fromtimestamp(item["dt"]),
                    city=data["city"]["name"],
                    country=data["city"]["sys"]["country"]
                ))
            
            return forecasts
        except requests.RequestException as e:
            print(f"Error fetching forecast: {e}")
            return []
    
    def format_weather(self, data: WeatherData) -> str:
        """Format weather data for display."""
        return (
            f"Weather in {data.city} ({data.country or 'N/A'}):\n"
            f"  Time: {data.timestamp}\n"
            f"  Temperature: {data.temperature}°C\n"
            f"  Humidity: {data.humidity}%\n"
            f"  Conditions: {data.description}"
        )
    
    def compare_weather(self, weather_data_list: List[WeatherData]) -> str:
        """Compare multiple weather data points."""
        if not weather_data_list:
            return "No data to compare"
        
        avg_temp = sum(w.temperature for w in weather_data_list) / len(weather_data_list)
        max_humidity = max(w.humidity for w in weather_data_list)
        
        result = ["Weather Comparison:", "-" * 30]
        for w in weather_data_list:
            result.append(f"  {w.city}: {w.temperature}°C, {w.humidity}% humidity")
        result.append(f"\nAverage temperature: {avg_temp:.1f}°C")
        result.append(f"Peak humidity: {max_humidity}%")
        
        return "\n".join(result)


if __name__ == "__main__":
    # Example usage
    service = WeatherService(api_key="your_api_key_here")
    print("Weather service initialized")
    print("\nFeatures available:")
    print("  - get_weather(city, country=None)")
    print("  - get_forecast(city, days=5)")
    print("  - format_weather(data)")
    print("  - compare_weather(data_list)")