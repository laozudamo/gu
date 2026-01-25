import streamlit as st
import pandas as pd
import time
from datetime import datetime
from streamlit_echarts import st_pyecharts
from charts.stock import draw_pro_kline
from utils.locale import t
from utils.stock_data import (
    get_market_snapshot, 
    get_all_stock_list,
    load_stock_pool, 
    add_to_pool, 
    remove_from_pool,
    move_to_watching_pool,
    update_stock_note,
    get_stock_history,
    get_stock_financials,
    get_realtime_price,
    get_market_status,
    get_pool_financials
)
from utils.cache_manager import get_cache_manager

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

@dialog("交易面板 / Transaction Panel", width="small")
def transaction_dialog(code: str, name: str, price: float):
    st.markdown(f"### {name} ({code})")
    st.markdown(f"当前价格: **{price}**")
    
    tab1, tab2 = st.tabs(["买入", "卖出"])
    
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            buy_price = st.number_input("买入价格", value=float(price) if price != "-" else 0.0, step=0.01, key=f"buy_p_{code}")
        with col2:
            buy_vol = st.number_input("买入数量", value=100, step=100, key=f"buy_v_{code}")
        
        if st.button("🔴 买入 / Buy", type="primary", use_container_width=True, key=f"btn_buy_{code}"):
            st.toast(f"模拟买入: {name} {buy_vol}股 @ {buy_price}", icon="💸")
            time.sleep(1)
            st.rerun()

    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            sell_price = st.number_input("卖出价格", value=float(price) if price != "-" else 0.0, step=0.01, key=f"sell_p_{code}")
        with col2:
            sell_vol = st.number_input("卖出数量", value=100, step=100, key=f"sell_v_{code}")
            
        if st.button("🟢 卖出 / Sell", type="primary", use_container_width=True, key=f"btn_sell_{code}"):
            st.toast(f"模拟卖出: {name} {sell_vol}股 @ {sell_price}", icon="💰")
            time.sleep(1)
            st.rerun()

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



def render_stock_table(pool: list, market_data: pd.DataFrame):
    if not pool:
        st.info("选股池为空，请搜索添加股票。")
        return

    # Task 2: Data Update Timestamp & Latest Data Check
    update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    st.caption(f"📅 数据更新时间: {update_time} | 默认展示最近交易日数据")

    # Table Header
    # Layout: Code(1.2) | Name(1.5) | Price(1.2) | Change(1.2) | PE(1.0) | Operations(3.0)
    header_cols = st.columns([1.2, 1.5, 1.2, 1.2, 1.0, 3.0])
    headers = ["代码", "名称", "最新价", "涨跌幅", "市盈率", "操作"]
    for col, h in zip(header_cols, headers):
        col.markdown(f"**{h}**")
        
    st.divider()

    # Rows
    for s in pool:
        code = s['code']
        name = s['name']
        
        # Market Data Logic
        price = "-"
        change = 0.0
        pe = "-"
        pb = "-"
        volume = 0
        
        if not market_data.empty:
            matches = market_data[market_data['代码'] == code]
            if not matches.empty:
                row = matches.iloc[0]
                price = row.get('最新价', '-')
                change = row.get('涨跌幅', 0)
                pe = row.get('市盈率-动态', '-')
                pb = row.get('市净率', '-')
                volume = row.get('成交量', 0)
        
        # Fallback
        if price == "-" or price is None or pd.isna(price):
            realtime = get_realtime_price(code)
            if realtime:
                price = realtime.get('latest', '-')
                change = realtime.get('change', 0)
        
        # Sanitize
        if pd.isna(price): price = "-"
        if pd.isna(change): change = 0.0
        if pd.isna(pe): pe = "-"
        
        # Task 2: Abnormal Data Mark (Suspended/Stop)
        is_suspended = False
        if volume == 0 and (price == "-" or price == 0):
             is_suspended = True
        
        # Render Row
        with st.container():
            c1, c2, c3, c4, c5, c6 = st.columns([1.2, 1.5, 1.2, 1.2, 1.0, 3.0])
            
            c1.write(f"`{code}`")
            
            # Name with Badge if suspended
            if is_suspended:
                c2.markdown(f"{name} <span style='background-color:#fed7d7; color:#c53030; padding:2px 6px; border-radius:4px; font-size:0.8em'>停牌</span>", unsafe_allow_html=True)
            else:
                c2.write(name)
                
            c3.write(f"**{price}**")
            
            # Colorized Change
            color = "red" if change > 0 else "green" if change < 0 else "gray"
            arrow = "📈" if change > 0 else "📉" if change < 0 else ""
            c4.markdown(f":{color}[{change:.2f}%] {arrow}")
            
            c5.write(f"{pe}")
            
            # Task 3: Operation Buttons Group
            with c6:
                # Use small columns for icons
                # 📊 Details | 💸 Trade | 👁️ Watch | 🗑️ Delete
                b1, b2, b3, b4 = st.columns([1, 1, 1, 1])
                
                with b1:
                    if st.button("📊", key=f"btn_det_{code}", help="详情分析", use_container_width=True):
                         snapshot_metrics = {"pe": pe, "pb": pb}
                         show_stock_details_dialog(code, name, snapshot_metrics)
                
                with b2:
                    if st.button("�", key=f"btn_trd_{code}", help="交易面板", use_container_width=True):
                         transaction_dialog(code, name, price)
                
                with b3:
                    if st.button("👁️", key=f"btn_watch_{code}", help="移入观察池", use_container_width=True):
                        success, msg = move_to_watching_pool(code)
                        if success:
                            st.toast(msg, icon="✅")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.toast(msg, icon="⚠️")
                            
                with b4:
                    if st.button("🗑️", key=f"btn_del_{code}", help="删除", type="primary", use_container_width=True):
                        success, msg = remove_from_pool(code)
                        st.toast(msg, icon="🗑️")
                        time.sleep(0.5)
                        st.rerun()
            
        st.divider()

def stock_picking_pool():
    render_header_search()
    st.divider()
    
    pool = load_stock_pool()
    with st.spinner("更新行情数据..."):
        market_data = get_market_snapshot()
        
    render_stock_table(pool, market_data)
