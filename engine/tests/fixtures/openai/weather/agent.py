"""OpenAI Agents SDK — weather assistant with function tools."""

from agents import Agent, function_tool


@function_tool
def get_weather(city: str, units: str = "celsius") -> str:
    """Get the current weather for a city.

    Args:
        city: The city to look up.
        units: Either 'celsius' or 'fahrenheit'.
    """
    return f"Sunny in {city}"


@function_tool
def get_forecast(city: str, days: int) -> str:
    """Get a multi-day forecast for a city."""
    return f"{days}-day forecast for {city}"


agent = Agent(
    name="Weather Assistant",
    instructions="You are a friendly weather assistant. Always state the units.",
    tools=[get_weather, get_forecast],
)
