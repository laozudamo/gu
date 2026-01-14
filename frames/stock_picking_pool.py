import streamlit as st
import pandas as pd
import time
from streamlit_echarts import st_pyecharts
from charts.stock import draw_pro_kline
from utils.locale import t
from utils.stock_data import (
    get_market_snapshot, 
    load_stock_pool, 
    add_to_pool, 
    remove_from_pool,
    move_to_watching_pool,
    update_stock_note,
    get_stock_history
)

# --- Dialog for Stock Details ---
# Using @st.dialog if available (Streamlit 1.34+), otherwise fallback to expander
try:
    from streamlit import dialog
    HAS_DIALOG = True
except ImportError:
    HAS_DIALOG = False
    # Fallback decorator
    def dialog(title, **kwargs):
        def decorator(func):
            def wrapper(*args, **kwargs):
                with st.container():
                    st.markdown(f"### {title}")
                    func(*args, **kwargs)
                    st.divider()
            return wrapper
        return decorator

@dialog("股票详情分析", width="large")
def show_stock_details_dialog(code: str, name: str):
    # 1. Period Selector
    col_p1, col_p2 = st.columns([1, 3])
    with col_p1:
        period_map = {"日K": "daily", "周K": "weekly", "月K": "monthly"}
        selected_period_label = st.selectbox("K线周期", list(period_map.keys()), index=0, key=f"period_{code}")
        selected_period = period_map[selected_period_label]
    
    # 2. Fetch Data
    with st.spinner(f"正在加载 {name} {selected_period_label} 数据..."):
        hist_df = get_stock_history(code, period=selected_period)
    
    if hist_df.empty:
        st.warning("暂无该周期历史数据")
        return

    # 3. Prepare Data for Charts
    # Adapt columns for draw_pro_kline
    chart_df = hist_df.reset_index()
    chart_df['date'] = chart_df['date'].dt.strftime('%Y-%m-%d')
    chart_df = chart_df.rename(columns={
        "date": "日期", "open": "开盘", "close": "收盘", 
        "high": "最高", "low": "最低", "volume": "成交量"
    })
    
    # 4. Render Chart
    kline_chart = draw_pro_kline(chart_df)
    st_pyecharts(kline_chart, height="500px")
    
    # 5. Close Button (Optional in dialog, but good for fallback)
    # if not HAS_DIALOG:
    #     if st.button("关闭详情", key=f"close_{code}"):
    #         st.rerun()


def render_header_search():
    """Top layout with Title and Search."""
    col_title, col_search = st.columns([2, 3])
    
    with col_title:
        st.title("选股池")
        
    with col_search:
        # Search Box with fuzzy matching
        # Using a popover or expander for results to avoid clutter
        search_query = st.text_input("🔍 搜索添加股票 (代码/名称/拼音)", placeholder="输入如 '600519' 或 '茅台'...")
        
        if search_query:
            # Perform search
            market_data = get_market_snapshot()
            if not market_data.empty:
                search_query = search_query.upper()
                mask = (
                    market_data['代码'].astype(str).str.contains(search_query) | 
                    market_data['名称'].str.contains(search_query)
                )
                if 'pinyin' in market_data.columns:
                    mask |= market_data['pinyin'].str.contains(search_query)
                
                results = market_data[mask].head(5)
                
                if not results.empty:
                    st.caption("搜索结果 (点击添加):")
                    for _, row in results.iterrows():
                        r_col1, r_col2, r_col3 = st.columns([2, 2, 1])
                        with r_col1: st.write(f"**{row['代码']}**")
                        with r_col2: st.write(row['名称'])
                        with r_col3:
                            if st.button("➕", key=f"add_search_{row['代码']}", help=f"添加 {row['名称']}"):
                                success, msg = add_to_pool(row['代码'], row['名称'])
                                if success:
                                    st.toast(msg, icon="✅")
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    st.toast(msg, icon="⚠️")
                else:
                    st.caption("未找到匹配股票")

def render_stock_table(pool: list, market_data: pd.DataFrame):
    """Render the responsive stock table."""
    if not pool:
        st.info("选股池暂无股票，请在上方搜索添加。")
        return

    # Header Row
    headers = st.columns([1.5, 1.5, 1.2, 1.2, 1.5, 2.5, 2.6])
    headers[0].markdown("**代码**")
    headers[1].markdown("**名称**")
    headers[2].markdown("**现价**")
    headers[3].markdown("**涨跌幅**")
    headers[4].markdown("**市盈率(动)**")
    headers[5].markdown("**备注 (回车保存)**")
    headers[6].markdown("**操作**")
    
    st.divider()

    # Data Rows
    for stock in pool:
        code = stock['code']
        name = stock['name']
        note = stock.get('note', '')
        
        # Get real-time data
        market_row = pd.Series()
        if not market_data.empty:
            matches = market_data[market_data['代码'] == code]
            if not matches.empty:
                market_row = matches.iloc[0]
        
        price = market_row.get('最新价', '-')
        change = market_row.get('涨跌幅', 0)
        pe = market_row.get('市盈率-动态', '-')
        
        # Color for price change
        price_color = "red" if isinstance(change, (int, float)) and change > 0 else "green" if isinstance(change, (int, float)) and change < 0 else "gray"
        
        cols = st.columns([1.5, 1.5, 1.2, 1.2, 1.5, 2.5, 2.6])
        
        # 1. Code
        cols[0].write(code)
        
        # 2. Name
        cols[1].write(name)
        
        # 3. Price
        cols[2].markdown(f"<span style='color:{price_color}'>{price}</span>", unsafe_allow_html=True)
        
        # 4. Change
        cols[3].markdown(f"<span style='color:{price_color}'>{change}%</span>", unsafe_allow_html=True)
        
        # 5. PE
        cols[4].write(pe)
        
        # 6. Note (Editable)
        new_note = cols[5].text_input(
            "note", 
            value=note, 
            key=f"note_{code}", 
            label_visibility="collapsed",
            placeholder="添加备注..."
        )
        if new_note != note:
            update_stock_note(code, new_note)
            st.toast(f"已更新 {name} 备注", icon="💾")
            # No rerun needed as value persists in UI, but data is saved
        
        # 7. Actions
        with cols[6]:
            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("📊", key=f"chart_{code}", help="查看详情图表"):
                    show_stock_details_dialog(code, name)
            with b2:
                if st.button("�", key=f"watch_{code}", help="移入观察池"):
                    success, msg = move_to_watching_pool(code)
                    if success:
                        st.toast(msg, icon="✅")
                        time.sleep(0.5)
                        st.rerun()
            with b3:
                if st.button("🗑️", key=f"del_{code}", help="删除"):
                    success, msg = remove_from_pool(code)
                    st.toast(msg, icon="🗑️")
                    time.sleep(0.5)
                    st.rerun()
        
        st.markdown("---")

def stock_picking_pool():
    # 1. Header & Search
    render_header_search()
    
    st.markdown("### 📋 我的选股池")
    
    # 2. Load Data
    pool = load_stock_pool()
    
    # 3. Market Data Snapshot (for Table)
    with st.spinner("正在刷新行情..."):
        market_data = get_market_snapshot()
        
    # 4. Render Table
    render_stock_table(pool, market_data)

