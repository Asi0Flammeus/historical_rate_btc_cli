from typing import Literal, Optional, Dict
from datetime import datetime
import http.client
import json
import os
from dotenv import load_dotenv
from urllib.parse import urlencode
import argparse

def get_exchange_rate(date: str, direction: Literal["to_btc", "from_btc"], currency: str, verbose: bool = False) -> Optional[Dict[str, float]]:
    """
    Fetches historical exchange rates between BTC and specified fiat currency using CurrencyFreaks API.
    
    Args:
        date: Date in YYYY-MM-DD format
        direction: Conversion direction - either "to_btc" or "from_btc"
        currency: Fiat currency code (e.g. USD, EUR)
        verbose: Whether to print detailed API response info
        
    Returns:
        Dictionary containing exchange rate and BTC price or None if API call fails
    """
    load_dotenv()
    api_key = os.getenv("CURRENCY_FREAKS_API_KEY")
    
    if not api_key:
        print("Error: API key not found in .env file")
        return None

    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Invalid date format. Please use YYYY-MM-DD")

    conn = http.client.HTTPSConnection("api.currencyfreaks.com")
    
    params = {
        "date": date,
        "base": "USD",
        "symbols": f"{currency},BTC",
        "apikey": api_key
    }
    
    endpoint = f"/v2.0/rates/historical?{urlencode(params)}"
    
    try:
        conn.request("GET", endpoint)
        response = conn.getresponse()
        raw_data = response.read().decode("utf-8")
        
        if verbose:
            print(f"API Status Code: {response.status}")
            print(f"API Response Headers: {response.getheaders()}")
            print(f"API Raw Response: {raw_data}")
        
        if response.status != 200:
            print(f"Error: API returned status code {response.status}")
            return None
            
        data = json.loads(raw_data)
        
        if "rates" not in data:
            print(f"Error: Unexpected API response format: {data}")
            return None
            
        rates = data["rates"]
        
        if "BTC" not in rates or currency not in rates:
            print(f"Error: Missing required currency rates. Available rates: {rates.keys()}")
            return None
            
        btc_rate = float(rates["BTC"])
        currency_rate = float(rates[currency])
        
        # BTC is quoted in USD, so we need to convert properly
        if direction == "to_btc":
            conversion_rate = btc_rate  # USD per BTC
            if currency != "USD":
                conversion_rate = conversion_rate * currency_rate  # adjust for non-USD currency
        else:
            conversion_rate = btc_rate  # BTC to USD
            if currency != "USD":
                conversion_rate = conversion_rate / currency_rate  # adjust for non-USD currency
            
        return {
            "rate": conversion_rate,
            "btc_price": btc_rate,
            "currency_rate": currency_rate
        }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return None
    finally:
        conn.close()

def format_number(value: float) -> str:
    """
    Format a float number with custom grouping:
    Before decimal: groups of three digits
    After decimal: first two digits together, then groups of three
    
    Examples:
        123456.78901230 -> "123 456.78 901 230"

    Args:
        value: Float number to format
    
    Returns:
        Formatted string with specified spacing
    """
    # Convert to string with 8 decimal places
    str_value = f"{value:.8f}"
    
    # Split into integer and decimal parts
    int_part, dec_part = str_value.split('.')
    
    # Group integer part by 3 from right to left
    int_groups = []
    for i in range(len(int_part)-3, -3, -3):
        if i < 0:
            int_groups.insert(0, int_part[0:i+3])
        else:
            int_groups.insert(0, int_part[i:i+3])
    grouped_int = ' '.join(filter(None, int_groups))
    
    # Handle decimal part: first 2 digits, then groups of 3
    first_dec = dec_part[:2]
    remaining_dec = dec_part[2:]
    
    # Group remaining decimal part by 3
    dec_groups = []
    for i in range(0, len(remaining_dec), 3):
        dec_groups.append(remaining_dec[i:i+3])
    
    # Combine decimal groups
    grouped_dec = f"{first_dec} {' '.join(dec_groups)}" if dec_groups else first_dec
    
    return f"{grouped_int}.{grouped_dec}"

def main() -> None:
    """
    CLI interface for getting cryptocurrency exchange rates.
    """
    parser = argparse.ArgumentParser(description="Get historical cryptocurrency exchange rates")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed API response")
    args = parser.parse_args()

    date = input("Enter date (YYYY-MM-DD): ")
    direction = input("Convert to BTC or from BTC? (to/from): ")
    currency = input("Enter currency (USD/EUR/other): ").upper()
    
    try:
        amount = float(input(f"Enter amount to convert: "))
    except ValueError:
        print("Invalid amount. Please enter a number.")
        return
    
    direction_map = {"to": "to_btc", "from": "from_btc"}
    
    if direction.lower() not in direction_map:
        print("Invalid direction. Please enter 'to' or 'from'")
        return
        
    result = get_exchange_rate(date, direction_map[direction.lower()], currency, args.verbose)
    
    if result:
        rate = result["rate"]
        if direction.lower() == "to":
            converted = amount * rate
            converted = format_number(converted)
            print(f"{amount} {currency} = {converted} BTC")
        else:
            converted = amount * rate
            amount = format_number(amount)
            print(f"{amount} BTC = {converted:.2f} {currency}")

if __name__ == "__main__":
    main()
