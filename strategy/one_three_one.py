import backtrader as bt

from .base import BaseStrategy


class OneThreeOneStrategy(BaseStrategy):
    """1-3-1 Red Green Candlestick Reversal Strategy
    Strategy:
        1. Red Candle: The candle 3 bars ago was red, and its low is the lowest among itself and the following 3 candles.
        2. Green Candles: The current candle and the previous 2 candles are all green.
        3. Higher Close: Each green candle closes higher than the previous one.
    """

    _name = "OneThreeOne"
    params = (
        ("tp_ratio", 1.0),
        ("printlog", False),
    )

    def __init__(self) -> None:
        super().__init__()
        self.order = None
        self.stop_loss_price = None
        self.take_profit_price = None

    def next(self) -> None:
        # We need at least 4 bars of data
        if len(self) < 4:
            return

        # Data aliases for readability
        # Index 0 is current, -1 is previous, etc.
        # Logic requires looking back 3 bars.
        
        # Current bar (0), Previous (-1), 2 bars ago (-2), 3 bars ago (-3)
        
        # Condition 1: Red Candle (3 bars ago)
        # close < open
        is_red_3 = self.data.close[-3] < self.data.open[-3]
        
        # Low of red candle is lowest among [-3, -2, -1, 0]
        low_3 = self.data.low[-3]
        is_lowest_low = (
            low_3 < self.data.low[-2] and
            low_3 < self.data.low[-1] and
            low_3 < self.data.low[0]
        )
        
        red_candle_condition = is_red_3 and is_lowest_low

        # Condition 2: Green Candles (last 3 bars: -2, -1, 0)
        is_green_2 = self.data.close[-2] > self.data.open[-2]
        is_green_1 = self.data.close[-1] > self.data.open[-1]
        is_green_0 = self.data.close[0] > self.data.open[0]
        
        green_candles_condition = is_green_2 and is_green_1 and is_green_0

        # Condition 3: Higher Close
        # close[0] > close[-1] > close[-2]
        higher_close_condition = (
            self.data.close[0] > self.data.close[-1] and
            self.data.close[-1] > self.data.close[-2]
        )

        # Check for Exit first if we are in the market
        if self.position:
            if self.stop_loss_price and self.data.low[0] <= self.stop_loss_price:
                self.log(f"STOP LOSS HIT, Price: {self.data.low[0]:.2f} <= {self.stop_loss_price:.2f}")
                self.close() # Close position
                self.stop_loss_price = None
                self.take_profit_price = None
            
            elif self.take_profit_price and self.data.high[0] >= self.take_profit_price:
                self.log(f"TAKE PROFIT HIT, Price: {self.data.high[0]:.2f} >= {self.take_profit_price:.2f}")
                self.close() # Close position
                self.stop_loss_price = None
                self.take_profit_price = None
            
            return

        # Check for Entry
        # Ensure no pending order
        if self.order:
            return

        if red_candle_condition and green_candles_condition and higher_close_condition:
            # Entry Signal
            self.log(f"BUY CREATE, Price: {self.data.close[0]:.2f}")
            self.order = self.buy()
            
            # Set Stop Loss and Take Profit
            self.stop_loss_price = low_3
            
            # Take Profit = Entry + (Entry - SL) * Ratio
            # Note: We use close[0] as approx entry price. 
            # In real backtest, execution might be at open of next bar, 
            # but for TP calculation based on signal, using signal close is standard in the provided script logic:
            # "takeProfitPrice := close + (close - stopLossPrice)"
            entry_price = self.data.close[0]
            risk = entry_price - self.stop_loss_price
            self.take_profit_price = entry_price + (risk * self.params.tp_ratio)
            
            self.log(f"Plan: SL={self.stop_loss_price:.2f}, TP={self.take_profit_price:.2f}")
