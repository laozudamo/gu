import streamlit as st
import pandas as pd
import time
from datetime import datetime
from utils.stock_data import (
    get_market_snapshot, 
    get_all_stock_list,
    load_stock_pool, 
    add_to_pool, 
    get_market_status
)
from frames.components import render_stock_table_common

# --- Main Views ---

def render_market_status():
    """Display real-time market status banner."""
    status_info = get_market_status()
    color = status_info['color']
    message = status_info['message']
    next_open = status_info['next_open']
    
    # CSS for the banner
    st.markdown(
        f"""
        <div style="
            padding: 10px;
            border-radius: 5px;
            background-color: {'#e6fffa' if color == 'green' else '#fff5f5' if color == 'red' else '#fffaf0'};
            border: 1px solid {'#38b2ac' if color == 'green' else '#fc8181' if color == 'red' else '#ed8936'};
            margin-bottom: 20px;
            display: flex;
            justify_content: space-between;
            align_items: center;
            ">
            <div>
                <span style="
                    font-weight: bold; 
                    color: {color}; 
                    font-size: 1.1em;
                    margin-right: 10px;
                ">● {message}</span>
                <span style="color: #666; font-size: 0.9em;">
                    {f"下次开市: {next_open}" if next_open else ""}
                </span>
            </div>
           
        </div>
        """,
        unsafe_allow_html=True
    )

def render_header_search():
    """Top layout with Title and Search."""
    # Market Status Banner
    render_market_status()
    
    col_title, col_search = st.columns([2, 3])
        
    with col_search:
        # Optimized Layout: Search Input + Add Button + Refresh Button in one line
        # Use a container to simulate dropdown behavior
        
        # Search Box
        search_query = st.text_input(
            "Search", 
            placeholder="🔍 输入代码/名称/拼音 (回车搜索)", 
            label_visibility="collapsed",
            help="输入股票代码、名称或拼音缩写，按回车搜索"
        )
        
        # Debounce/Delay simulation (in a real async app, we'd use a timer)
        # Here we rely on Streamlit's re-run model.
        
        if search_query:
            # 1. Fetch Lightweight List (Cached)
            with st.spinner("Searching..."):
                all_stocks = get_all_stock_list()
                
            if not all_stocks.empty:
                search_query = search_query.upper()
                mask = (
                    all_stocks['代码'].astype(str).str.contains(search_query) | 
                    all_stocks['名称'].str.contains(search_query)
                )
                if 'pinyin' in all_stocks.columns:
                    mask |= all_stocks['pinyin'].str.contains(search_query)
                
                results = all_stocks[mask].head(5) # Limit to 5 results for "Dropdown" feel
                
                if not results.empty:
                    # Show results in an expander-like container or just list
                    st.markdown("---")
                    st.caption(f"找到 {len(results)} 个匹配项:")
                    
                    for _, row in results.iterrows():
                        rc1, rc2, rc3 = st.columns([4, 2, 1])
                        with rc1:
                            st.write(f"**{row['代码']}**")
                        with rc2:
                            st.write(row['名称'])
                        with rc3:
                            if st.button("➕", key=f"add_{row['代码']}", help=f"添加 {row['名称']}"):
                                success, msg = add_to_pool(row['代码'], row['名称'])
                                if success:
                                    st.toast(msg, icon="✅")
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    st.toast(msg, icon="⚠️")
                else:
                    st.warning("未找到匹配股票")
            else:
                st.error("无法加载股票列表")

def stock_picking_pool():
    render_header_search()
    st.divider()
    
    pool = load_stock_pool()
    with st.spinner("更新行情数据..."):
        market_data = get_market_snapshot()
        
    render_stock_table_common(pool, market_data, pool_type='picking')
