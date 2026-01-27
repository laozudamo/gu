import streamlit as st
from utils.stock_data import load_trading_pool, get_market_snapshot
from frames.components import render_stock_table_common, render_refresh_button

def stock_trading_pool():
    # Header with Refresh
    c_fill, c_btn = st.columns([15, 1])
    with c_btn:
        render_refresh_button("trading")
    
    pool = load_trading_pool()
    
    with st.spinner("更新行情数据..."):
        market_data = get_market_snapshot()
        
    render_stock_table_common(pool, market_data, pool_type='trading')
