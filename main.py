from typing import Literal, Optional, Dict, Union
from datetime import datetime, date
import http.client
import json
import os
from dotenv import load_dotenv
from urllib.parse import urlencode
import argparse
import readchar
import sys

def get_input(prompt: str, validator=None, allowed_chars: str = None) -> str:
    """
    Get user input with backspace support and optional validation.
    
    Args:
        prompt: Input prompt to display
        validator: Optional function to validate input
        allowed_chars: Optional string of allowed characters
        
    Returns:
        Validated user input
    """
    print(prompt, end='', flush=True)
    buffer = []
    
    while True:
        char = readchar.readchar()
        
        # Handle Enter key
        if char in ['\r', '\n']:
            if not buffer:
                continue
            result = ''.join(buffer)
            if validator and not validator(result):
                print("\nInvalid input. Please try again.")
                buffer = []
                print(f"\n{prompt}", end='', flush=True)
                continue
            print()  # New line after input
            return result
            
        # Handle backspace
        if char == '\x7f':  # Backspace character
            if buffer:
                buffer.pop()
                sys.stdout.write('\b \b')  # Erase character
                sys.stdout.flush()
            continue
            
        # Handle regular characters
        if allowed_chars and char not in allowed_chars:
            continue
            
        if char.isprintable():
            buffer.append(char)
            sys.stdout.write(char)
            sys.stdout.flush()

def validate_date(date_str: str) -> bool:
    """Validate date string format and range."""
    try:
        input_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        earliest_date = datetime.strptime("2013-01-07", "%Y-%m-%d").date()  # BTC availability date
        return earliest_date <= input_date <= date.today()
    except ValueError:
        return False

def validate_direction(direction: str) -> bool:
    """Validate conversion direction."""
    return direction.lower() in ['to', 'from']

def validate_amount(amount: str) -> bool:
    """Validate numeric amount."""
    try:
        float(amount)
        return True
    except ValueError:
        return False

def get_exchange_rate(date_str: Optional[str], direction: Literal["to_btc", "from_btc"], 
                     currency: str, verbose: bool = False) -> Optional[Dict[str, float]]:
    """
    Fetches exchange rates between BTC and specified fiat currency.
    
    Args:
        date_str: Optional date in YYYY-MM-DD format (None for current rates)
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

    conn = http.client.HTTPSConnection("api.currencyfreaks.com")
    
    params = {
        "base": "USD",
        "symbols": f"{currency},BTC",
        "apikey": api_key
    }

    # Choose endpoint based on whether we want historical or current rates
    if date_str:
        params["date"] = date_str
        endpoint = f"/v2.0/rates/historical?{urlencode(params)}"
    else:
        endpoint = f"/v2.0/rates/latest?{urlencode(params)}"
    
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
            "currency_rate": currency_rate,
            "date": data.get("date", "current")
        }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return None
    finally:
        conn.close()

def format_number(value: float) -> str:
    """Format number with custom grouping."""
    str_value = f"{value:.8f}"
    int_part, dec_part = str_value.split('.')
    
    int_groups = []
    for i in range(len(int_part)-3, -3, -3):
        if i < 0:
            int_groups.insert(0, int_part[0:i+3])
        else:
            int_groups.insert(0, int_part[i:i+3])
    grouped_int = ' '.join(filter(None, int_groups))
    
    first_dec = dec_part[:2]
    remaining_dec = dec_part[2:]
    
    dec_groups = []
    for i in range(0, len(remaining_dec), 3):
        dec_groups.append(remaining_dec[i:i+3])
    
    grouped_dec = f"{first_dec} {' '.join(dec_groups)}" if dec_groups else first_dec
    
    return f"{grouped_int}.{grouped_dec}"
def main() -> None:
    """CLI interface for getting cryptocurrency exchange rates."""
    parser = argparse.ArgumentParser(description="Get historical and current cryptocurrency exchange rates")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed API response")
    args = parser.parse_args()

    # Get conversion type (historical or current)
    rate_type = get_input("Get [h]istorical or [c]urrent rate? (h/c): ", 
                         lambda x: x.lower() in ['h', 'c'],
                         allowed_chars='hcHC').lower()

    # Get date for historical rates
    date_str = None
    if rate_type == 'h':
        date_str = get_input("Enter date (YYYY-MM-DD): ", validate_date)

    # Get other inputs with validation
    direction = get_input("Convert to BTC or from BTC? (to/from): ", validate_direction)
    currency = get_input("Enter currency (e.g., USD/EUR): ", lambda x: len(x) == 3).upper()
    amount = get_input(f"Enter amount to convert: ", validate_amount)
    
    try:
        amount = float(amount)
    except ValueError:
        print("Invalid amount. Please enter a number.")
        return
    
    direction_map = {"to": "to_btc", "from": "from_btc"}
    
    # Get current rate first if we're doing historical
    current_rate = None
    if rate_type == 'h':
        current_rate = get_exchange_rate(None, direction_map[direction.lower()], currency, args.verbose)
    
    # Get requested rate (historical or current)
    result = get_exchange_rate(date_str, direction_map[direction.lower()], currency, args.verbose)
    
    if result:
        rate = result["rate"]
        if direction.lower() == "to":
            converted_value = amount * rate  # Store raw value
            converted_str = format_number(converted_value)  # Formatted string for display
            print(f"\n{amount} {currency} = {converted_str} BTC")
            print(f"Rate used: 1 BTC = {1/result['btc_price']:,.2f} USD (from {result['date']})")
        else:
            converted_value = amount * rate  # Store raw value
            amount_str = format_number(amount)
            print(f"\n{amount_str} BTC = {converted_value:,.2f} {currency}")
            print(f"Rate used: 1 BTC = {1/result['btc_price']:,.2f} USD (from {result['date']})")
        

if __name__ == "__main__":
    main()
