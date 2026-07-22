#!/usr/bin/env python3
"""Sample weather tool for ask CLI testing."""

import sys
import json


# @tool: get_weather | Gets weather for a city | {"city": "string"}
def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No arguments provided"}))
        sys.exit(1)

    try:
        args = json.loads(sys.argv[1])
        city = args.get("city", "Unknown")

        result = {
            "city": city,
            "temperature": 72,
            "unit": "fahrenheit",
            "condition": "sunny",
            "humidity": 45
        }
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
