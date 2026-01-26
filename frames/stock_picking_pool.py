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

from utils.cache_manager import get_cache_manager

def render_header_search():
    """Top layout with Compact Status, Search, and Refresh."""
    
    # Combined Row: Status (Left) + Search (Middle) + Refresh (Right)
    c1, c2, c3 = st.columns([1.2, 1.2, 0.4], gap="small")
    
    with c1:
        status_info = get_market_status()
        color = status_info['color']
        message = status_info['message']
        next_open = status_info['next_open']
        bg_color = '#f0fff4' if color == 'green' else '#fff5f5' if color == 'red' else '#fffaf0'
        text_color = '#2f855a' if color == 'green' else '#c53030' if color == 'red' else '#dd6b20'
        
        # Compact Status Badge
        st.markdown(
            f"""
            <div style="
                display: flex; align_items: center; 
                background-color: {bg_color}; 
                padding: 8px 12px; 
                border-radius: 8px;
                border: 1px solid {text_color}33;
                height: 42px;
                white-space: nowrap;
                overflow: hidden;
            ">
                <span style="color: {text_color}; font-weight: bold; margin-right: 8px; font-size: 0.9em;">● {message}</span>
                <span style="color: #718096; font-size: 0.8em;">{f"({next_open})" if next_open else ""}</span>
            </div>
            """, 
            unsafe_allow_html=True
        )

    with c2:
        # Search Box
        search_query = st.text_input(
            "Search", 
            placeholder="🔍 快速添加股票 (代码/名称/拼音)", 
            label_visibility="collapsed"
        )
        
    with c3:
        # Refresh Button with Visual Feedback
        if st.button("🔄", help="立即刷新行情数据", use_container_width=True):
             with st.spinner(""):
                try:
                    cm = get_cache_manager()
                    cm.update_cache(force=True)
                    st.cache_data.clear()
                    st.toast("行情数据已更新", icon="✅")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"更新失败: {e}")
        
    # Search Logic
    if search_query:
        # 1. Fetch Lightweight List (Cached)
        all_stocks = get_all_stock_list()
        
        if not all_stocks.empty:
            search_query = search_query.upper()
            mask = (
                all_stocks['代码'].astype(str).str.contains(search_query) | 
                all_stocks['名称'].str.contains(search_query)
            )
            if 'pinyin' in all_stocks.columns:
                mask |= all_stocks['pinyin'].str.contains(search_query)
            
            results = all_stocks[mask].head(5) # Limit to 5 results
            
            if not results.empty:
                with st.container():
                    st.markdown("---")
                    st.caption(f"找到 {len(results)} 个匹配项:")
                    for _, row in results.iterrows():
                        rc1, rc2, rc3 = st.columns([3, 4, 2])
                        with rc1: st.write(f"`{row['代码']}`")
                        with rc2: st.write(row['名称'])
                        with rc3:
                            if st.button("➕ 添加", key=f"add_{row['代码']}", use_container_width=True):
                                success, msg = add_to_pool(row['代码'], row['名称'])
                                if success:
                                    st.toast(msg, icon="✅")
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    st.toast(msg, icon="⚠️")
            else:
                st.warning("未找到匹配股票")

def stock_picking_pool():
    render_header_search()
    # Remove large divider, rely on spacing
    st.markdown("<div style='margin-bottom: 10px'></div>", unsafe_allow_html=True)
    
    pool = load_stock_pool()
    with st.spinner("更新行情..."):
        market_data = get_market_snapshot()
        
    render_stock_table_common(pool, market_data, pool_type='picking')
