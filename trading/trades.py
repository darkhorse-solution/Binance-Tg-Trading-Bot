from binance import Client

class BinanceTrader:
    def __init__(self, api_key, api_secret):
        """
        Initialize the Binance trader with API credentials.

        Args:
            api_key (str): Binance API key
            api_secret (str): Binance API secret
        """
        self.client = Client(api_key, api_secret)

    