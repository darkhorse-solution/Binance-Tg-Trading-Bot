import os
import json
import logging
from typing import Dict, Tuple, Optional, Any

logger = logging.getLogger('trading_bot')

class SymbolMapper:
    """
    Handles mapping between different symbol representations and applies rate adjustments.
    """
    
    def __init__(self, mapping_file: str = "symbol_mappings.json"):
        """
        Initialize the symbol mapper with mappings from a JSON file.
        
        Args:
            mapping_file (str): Path to the mapping file
        """
        self.mapping_file = mapping_file
        self.mappings = {}
        self.load_mappings()
    
    def load_mappings(self) -> None:
        """Load symbol mappings from the JSON file."""
        try:
            if os.path.exists(self.mapping_file):
                with open(self.mapping_file, "r") as f:
                    self.mappings = json.load(f)
                logger.info(f"Loaded {len(self.mappings)} symbol mappings from {self.mapping_file}")
            else:
                logger.warning(f"Mapping file {self.mapping_file} not found")
        except Exception as e:
            logger.error(f"Error loading symbol mappings: {e}")
            self.mappings = {}
    
    def get_mapped_symbol(self, symbol: str) -> Tuple[Optional[str], float]:
        """
        Get the mapped symbol and rate multiplier for a given symbol.
        
        Args:
            symbol (str): Original symbol
            
        Returns:
            tuple: (mapped_symbol, rate) - Returns (None, 1.0) if no mapping exists
        """
        # Check for exact match
        if symbol in self.mappings:
            mapping = self.mappings[symbol]
            return self._extract_mapping_data(mapping, symbol)
        
        # Check for case-insensitive match
        for key, value in self.mappings.items():
            if key.lower() == symbol.lower():
                return self._extract_mapping_data(value, symbol)
        
        # No mapping found
        return None, 1.0
    
    def _extract_mapping_data(self, mapping: Any, original_symbol: str) -> Tuple[str, float]:
        """
        Extract mapping data handling both new and legacy format.
        
        Args:
            mapping: Mapping data (either string or dict)
            original_symbol: Original symbol for logging
            
        Returns:
            tuple: (mapped_symbol, rate)
        """
        # Handle both new format (dict with symbol and rate) and legacy format (string)
        if isinstance(mapping, dict):
            mapped_symbol = mapping.get("symbol", None)
            rate = mapping.get("rate", 1.0)
            logger.info(f"Using mapped symbol with rate adjustment: {original_symbol} -> {mapped_symbol} (rate: {rate})")
            return mapped_symbol, rate
        elif isinstance(mapping, str):
            # Legacy format - just the symbol name with rate 1.0
            logger.info(f"Using mapped symbol (legacy format): {original_symbol} -> {mapping}")
            return mapping, 1.0
        else:
            logger.warning(f"Invalid mapping format for {original_symbol}")
            return None, 1.0
    
    def apply_rate_to_price(self, symbol: str, price: float) -> Tuple[Optional[str], float]:
        """
        Apply rate adjustment to a price based on symbol mapping.
        
        Args:
            symbol (str): Original symbol
            price (float): Original price
            
        Returns:
            tuple: (mapped_symbol, adjusted_price) - Returns (None, original_price) if no mapping
        """
        mapped_symbol, rate = self.get_mapped_symbol(symbol)
        if mapped_symbol:
            adjusted_price = price * rate
            return mapped_symbol, adjusted_price
        return None, price