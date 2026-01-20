import streamlit as st

# Deprecated: Multilingual support removed.
# This function now acts as a passthrough or returns Chinese defaults directly if used.

def t(key):
    # Mapping for any remaining keys that might be called, defaulting to Chinese directly.
    # Ideally callers should replace t("key") with "中文" directly.
    # This is a temporary compatibility layer.
    defaults = {
        "daily_k": "日K",
        "volume": "成交量",
        "stock_picking_pool": "选股池",
        "stock_watching_pool": "观察池",
        "stock_trading_pool": "交易池",
        "backtest_module": "回测模块"
    }
    return defaults.get(key, key)
