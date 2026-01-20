import streamlit as st
import pandas as pd
import time
from datetime import datetime
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
    get_stock_history,
    get_stock_financials,
    get_realtime_price,
    get_market_status
)

# --- Dialogs ---

try:
    from streamlit import dialog
except ImportError:
    # Fallback if older streamlit
    def dialog(title, **kwargs):
        def decorator(func):
            def wrapper(*args, **kwargs):
                with st.expander(title, expanded=True):
                    func(*args, **kwargs)
            return wrapper
        return decorator

@dialog("编辑备注 / Edit Note", width="large")
def edit_note_dialog(code: str, name: str):
    pool = load_stock_pool()
    stock = next((s for s in pool if s['code'] == code), None)
    if not stock:
        st.error("Stock not found")
        return

    current_note = stock.get('note', {})
    # Normalize note structure
    if isinstance(current_note, str):
        current_note = {'content': current_note, 'images': [], 'updated_at': ''}
    elif not isinstance(current_note, dict):
        current_note = {'content': '', 'images': [], 'updated_at': ''}

    col1, col2 = st.columns([2, 1])
    
    with col1:
        new_content = st.text_area(
            "内容 (Markdown supported)", 
            value=current_note.get('content', ''), 
            height=300,
            help="支持加粗/斜体/列表等基础格式"
        )
    
    with col2:
        # st.markdown("#### 图片附件")
        # Image attachment feature removed as per requirements
        st.caption(f"上次更新: {current_note.get('updated_at', '-')}")

    if st.button("💾 保存 / Save", type="primary"):
        # Save logic
        note_data = {
            "content": new_content,
            # Images removed
            # "images": current_note.get('images', []), 
            "updated_at": datetime.now().isoformat()
        }
        update_stock_note(code, note_data)
        st.toast("备注已更新", icon="✅")
        time.sleep(0.5)
        st.rerun()

@dialog("股票详情分析 / Stock Details", width="large")
def show_stock_details_dialog(code: str, name: str, snapshot_metrics: dict = None):
    # CSS Hack for Wider Dialog
    st.markdown(
        """
        <style>
        div[data-testid="stDialog"] div[role="dialog"] {
            width: 90vw !important;
            max-width: 1400px !important;
        }
        </style>
        """, 
        unsafe_allow_html=True
    )
    
    # 1. Fetch Financials (Async-like)
    with st.spinner("加载财务数据..."):
        fin = get_stock_financials(code)
    
    # 2. Display Metrics
    # PE/PB/ROE/Gross Margin
    m1, m2, m3, m4, m5 = st.columns(5)
    
    roe = fin.get('ROE', 0)
    gross = fin.get('GrossMargin', 0)
    net = fin.get('NetMargin', 0)
    
    m1.metric("ROE (净资产收益率)", f"{roe:.2f}%" if roe != 0 else "-")
    m2.metric("毛利率", f"{gross:.2f}%" if gross != 0 else "-")
    m3.metric("净利率", f"{net:.2f}%" if net != 0 else "-")
    
    # Use snapshot metrics if available
    pe = snapshot_metrics.get('pe', '-') if snapshot_metrics else '-'
    pb = snapshot_metrics.get('pb', '-') if snapshot_metrics else '-'
    
    m4.metric("市盈率 (PE)", pe)
    m5.metric("市净率 (PB)", pb)
    
    st.divider()

    # 3. Period Selector & Chart
    # Remove Period Selector (Task 1: Default to Daily)
    selected_period = "daily"
    selected_period_label = "日K (1D)"
    
    with st.spinner(f"正在加载 {name} {selected_period_label} 数据..."):
        hist_df = get_stock_history(code, period=selected_period)
    
    if hist_df.empty:
        st.warning(f"暂无 {selected_period_label} 历史数据 (可能是新股或数据源连接失败)")
        return

    # Adapt columns for draw_pro_kline
    chart_df = hist_df.reset_index()
    chart_df['date'] = chart_df['date'].dt.strftime('%Y-%m-%d')
    chart_df = chart_df.rename(columns={
        "date": "日期", "open": "开盘", "close": "收盘", 
        "high": "最高", "low": "最低", "volume": "成交量"
    })
    
    try:
        # Indicator Controls
        c_ind1, c_ind2 = st.columns([1, 1])
        with c_ind1:
            main_ind = st.selectbox("主图指标", ["MA", "BOLL", "None"], index=0, key=f"main_{code}")
        with c_ind2:
            sub_ind = st.selectbox("副图指标", ["VOL", "MACD", "None"], index=0, key=f"sub_{code}")

        # Render Chart with Indicators
        kline_chart = draw_pro_kline(chart_df, main_indicator=main_ind, sub_indicator=sub_ind)
        kline_chart.width = "100%"
        
        # Interaction Hints (Task 3: Interaction Hints)
        st.caption("💡 操作提示: 鼠标滚轮可缩放图表，点击并拖拽可平移视图")
        
        # Height > 80% visual area approx 700-800px
        st_pyecharts(kline_chart, height="700px")
    except Exception as e:
        st.error(f"图表渲染失败: {e}")

# --- Main Views ---

def render_market_status():
    """Display real-time market status banner."""
    status_info = get_market_status()
    color = status_info['color']
    status_text = status_info['status']
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
    
    # with col_title:
    #     st.header("选股池 / Stock Pool")
        
    with col_search:
        # Optimized Layout: Search Input + Add Button + Refresh Button in one line
        c1, c2, c3 = st.columns([6, 1, 1], gap="small")
        
        with c1:
            search_query = st.text_input("Search", placeholder="代码/名称/拼音 (e.g. 600519)", label_visibility="collapsed")
            
        with c3:
            if st.button("🔄", help="刷新行情", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
                
        # Handle Search Logic
        if search_query:
            market_data = get_market_snapshot()
            if not market_data.empty:
                search_query = search_query.upper()
                mask = (
                    market_data['代码'].astype(str).str.contains(search_query) | 
                    market_data['名称'].str.contains(search_query)
                )
                if 'pinyin' in market_data.columns:
                    mask |= market_data['pinyin'].str.contains(search_query)
                
                results = market_data[mask].head(1) # Get top result for quick add
                
                # Dynamic "Add" button in the middle column
                with c2:
                     if not results.empty:
                        row = results.iloc[0]
                        if st.button("➕", key=f"quick_add_{row['代码']}", help=f"添加 {row['名称']}", use_container_width=True):
                            success, msg = add_to_pool(row['代码'], row['名称'])
                            if success:
                                st.toast(msg, icon="✅")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.toast(msg, icon="⚠️")
                     else:
                        st.button("➕", disabled=True, use_container_width=True)

        else:
             with c2:
                st.button("➕", disabled=True, use_container_width=True)

@st.fragment
def render_context_menu():
    """
    Simulated Right-Click Context Menu using Streamlit's Popover logic.
    Since true right-click isn't supported, we use an Actions menu per row.
    """
    pass  # Logic integrated into the action bar below

def render_stock_table(pool: list, market_data: pd.DataFrame):
    if not pool:
        st.info("选股池为空，请搜索添加股票。")
        return

    # 1. Build DataFrame for Display
    rows = []
    for s in pool:
        code = s['code']
        name = s['name']
        
        # Market Data
        price = "-"
        change = 0.0
        pe = "-"
        pb = "-"
        
        # Try bulk market data first
        if not market_data.empty:
            matches = market_data[market_data['代码'] == code]
            if not matches.empty:
                row = matches.iloc[0]
                price = row.get('最新价', '-')
                change = row.get('涨跌幅', 0)
                pe = row.get('市盈率-动态', '-')
                pb = row.get('市净率', '-')
        
        # Fallback to individual fetch if price is missing
        if price == "-" or price is None or pd.isna(price):
            realtime = get_realtime_price(code)
            if realtime:
                price = realtime.get('latest', '-')
                change = realtime.get('change', 0)
                # PE/PB not available in history
        
        # Ensure values are not NaN before display to avoid table errors
        if pd.isna(price): price = "-"
        if pd.isna(change): change = 0.0
        if pd.isna(pe): pe = "-"
        if pd.isna(pb): pb = "-"
        
        # Note content preview
        note = s.get('note', '')
        if isinstance(note, dict):
            note = note.get('content', '')
        
        rows.append({
            "code": code,
            "name": name,
            "price": price,
            "change": change,
            "pe": pe,
            "pb": pb,
            "note": note
        })
    
    df = pd.DataFrame(rows)

    # Visualization: Trend & Color
    # 1. Trend Icon
    def get_trend(val):
        if isinstance(val, (int, float)):
            if val > 0: return "📈"
            if val < 0: return "📉"
        return "➖"
    
    df.insert(4, "trend", df['change'].apply(get_trend))

    # 2. Configure Columns
    column_config = {
        "code": st.column_config.TextColumn("代码", help="Stock Code"),
        "name": st.column_config.TextColumn("名称", help="Stock Name"),
        "price": st.column_config.NumberColumn("最新价", format="%.2f"),
        "change": st.column_config.NumberColumn("涨跌幅", format="%.2f%%"),
        "trend": st.column_config.TextColumn("趋势", width="small"),
        "pe": st.column_config.NumberColumn("市盈率(动)", format="%.2f"),
        "pb": st.column_config.NumberColumn("市净率", format="%.2f"),
        "note": st.column_config.TextColumn("备注预览", width="medium"),
    }
    
    # 3. Render Table with Selection
    st.caption("💡 提示: 选中行后点击下方按钮进行操作")
    
    # Apply Styling (China Market: Red=Up, Green=Down)
    def highlight_change(val):
        if isinstance(val, (int, float)):
            color = 'red' if val > 0 else 'green' if val < 0 else 'black'
            return f'color: {color}'
        return ''

    styled_df = df.style.map(highlight_change, subset=['change', 'price'])

    selection = st.dataframe(
        styled_df,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        key="stock_selection"
    )
    
    # 4. Context Menu / Action Bar (Simulated Right Click)
    if selection.selection.rows:
        idx = selection.selection.rows[0]
        selected_row = df.iloc[idx]
        code = selected_row['code']
        name = selected_row['name']
        
        # Enhanced Context Menu with Popover style animation
        with st.container():
            st.markdown(f"### 🎯 操作: {name} ({code})")
            
            col_menu = st.columns([1, 1, 1, 1])
            
            with col_menu[0]:
                if st.button("📊 详情分析", use_container_width=True, help="查看K线和财务指标"):
                    snapshot_metrics = {"pe": pe, "pb": pb}
                    show_stock_details_dialog(code, name, snapshot_metrics)
            
            with col_menu[1]:
                if st.button("📝 编辑备注", use_container_width=True, help="添加或修改备注"):
                    edit_note_dialog(code, name)
            
            with col_menu[2]:
                if st.button("👁️ 移入观察", use_container_width=True, help="移入观察池"):
                    success, msg = move_to_watching_pool(code)
                    if success:
                        st.toast(msg, icon="✅")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.warning(msg)

            with col_menu[3]:
                if st.button("🗑️ 删除股票", type="primary", use_container_width=True, help="移除股票"):
                    # Secondary Confirmation Logic (Simulated with toast/rerun for now)
                    success, msg = remove_from_pool(code)
                    st.toast(msg, icon="🗑️")
                    time.sleep(0.5)
                    st.rerun()

def stock_picking_pool():
    render_header_search()
    st.divider()
    
    pool = load_stock_pool()
    with st.spinner("更新行情数据..."):
        market_data = get_market_snapshot()
        
    render_stock_table(pool, market_data)
