import streamlit as st
import pandas as pd
import time
from datetime import datetime
from streamlit_echarts import st_pyecharts
from charts.stock import draw_pro_kline
from utils.stock_data import (
    load_stock_pool, 
    load_watching_pool,
    load_trading_pool,
    update_stock_note,
    update_stock_tags,
    get_stock_financials,
    get_stock_history,
    get_realtime_price,
    remove_from_pool,
    remove_from_watching_pool,
    remove_from_trading_pool,
    move_to_watching_pool,
    move_to_trading_pool,
    move_from_trading_to_watching,
    move_from_watching_to_picking,
    add_transaction
)
from utils.risk_engine import calculate_risk_metrics

# --- Dialogs ---

try:
    from streamlit import dialog
except ImportError:
    def dialog(title, **kwargs):
        def decorator(func):
            def wrapper(*args, **kwargs):
                with st.expander(title, expanded=True):
                    func(*args, **kwargs)
            return wrapper
        return decorator

@dialog("编辑备注", width="large")
def edit_note_dialog(code: str, name: str, pool_type: str):
    # Load correct pool to get current note
    if pool_type == 'picking':
        pool = load_stock_pool()
    elif pool_type == 'watching':
        pool = load_watching_pool()
    elif pool_type == 'trading':
        pool = load_trading_pool()
    else:
        st.error("Invalid pool type")
        return

    stock = next((s for s in pool if s['code'] == code), None)
    if not stock:
        st.error("Stock not found")
        return

    current_note = stock.get('note', {})
    if isinstance(current_note, str):
        current_note = {'content': current_note, 'images': [], 'updated_at': ''}
    elif not isinstance(current_note, dict):
        current_note = {'content': '', 'images': [], 'updated_at': ''}

    col1, col2 = st.columns([2, 1])
    
    with col1:
        new_content = st.text_area(
            "内容 (支持 Markdown)", 
            value=current_note.get('content', ''), 
            height=300,
            help="支持加粗/斜体/列表等基础格式"
        )
    
    with col2:
        st.caption(f"上次更新: {current_note.get('updated_at', '-')}")

    if st.button("💾 保存", type="primary"):
        note_data = {
            "content": new_content,
            "updated_at": datetime.now().isoformat()
        }
        update_stock_note(code, note_data, pool_type=pool_type)
        st.toast("备注已更新", icon="✅")
        time.sleep(0.5)
        st.rerun()

@dialog("编辑标签", width="small")
def edit_tags_dialog(code: str, name: str, pool_type: str):
    # Load correct pool
    if pool_type == 'picking':
        pool = load_stock_pool()
    elif pool_type == 'watching':
        pool = load_watching_pool()
    elif pool_type == 'trading':
        pool = load_trading_pool()
    else:
        return

    stock = next((s for s in pool if s['code'] == code), None)
    if not stock:
        return

    current_tags = stock.get('tags', [])
    if not isinstance(current_tags, list):
        current_tags = []

    # Predefined tags
    PREDEFINED_TAGS = ["半导体", "新能源", "医药", "消费", "AI", "低估值", "高成长", "龙头", "短线", "长线"]
    
    selected_tags = st.multiselect("选择标签", options=list(set(PREDEFINED_TAGS + current_tags)), default=current_tags)
    
    # Custom tag input
    new_tag = st.text_input("新增自定义标签 (回车添加)")
    if new_tag and new_tag not in selected_tags:
        # This is a bit tricky in Streamlit dialogs without a button, but let's just rely on the multiselect + save
        pass

    if st.button("💾 保存标签", type="primary"):
        final_tags = selected_tags
        if new_tag and new_tag not in final_tags:
            final_tags.append(new_tag)
            
        update_stock_tags(code, final_tags, pool_type=pool_type)
        st.toast("标签已更新", icon="✅")
        time.sleep(0.5)
        st.rerun()

@dialog("股票详情", width="large")
def show_stock_details_dialog(code: str, name: str, snapshot_metrics: dict = None):
    st.markdown(f"### {name} ({code})")
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
    
    with st.spinner("加载财务数据..."):
        fin = get_stock_financials(code)
    
    m1, m2, m3, m4, m5 = st.columns(5)
    
    roe = fin.get('ROE', 0)
    gross = fin.get('GrossMargin', 0)
    net = fin.get('NetMargin', 0)
    
    m1.metric("ROE", f"{roe:.2f}%" if roe != 0 else "-")
    m2.metric("毛利率", f"{gross:.2f}%" if gross != 0 else "-")
    m3.metric("净利率", f"{net:.2f}%" if net != 0 else "-")
    
    pe = snapshot_metrics.get('pe', '-') if snapshot_metrics else '-'
    pb = snapshot_metrics.get('pb', '-') if snapshot_metrics else '-'
    
    m4.metric("PE", pe)
    m5.metric("PB", pb)
    
    st.divider()

    selected_period = "daily"
    with st.spinner(f"正在加载 {name} 日K 数据..."):
        hist_df = get_stock_history(code, period=selected_period)
    
    if hist_df.empty:
        st.warning(f"暂无历史数据")
        return

    chart_df = hist_df.reset_index()
    chart_df['date'] = chart_df['date'].dt.strftime('%Y-%m-%d')
    chart_df = chart_df.rename(columns={
        "date": "日期", "open": "开盘", "close": "收盘", 
        "high": "最高", "low": "最低", "volume": "成交量"
    })
    
    try:
        c_ind1, c_ind2 = st.columns([1, 1])
        with c_ind1:
            main_ind = st.selectbox("主图指标", ["MA", "BOLL", "None"], index=0, key=f"main_{code}")
        with c_ind2:
            sub_ind = st.selectbox("副图指标", ["VOL", "MACD", "None"], index=0, key=f"sub_{code}")

        kline_chart = draw_pro_kline(chart_df, main_indicator=main_ind, sub_indicator=sub_ind)
        kline_chart.width = "100%"
        st.caption("💡 操作提示: 鼠标滚轮可缩放图表，点击并拖拽可平移视图")
        st_pyecharts(kline_chart, height="600px")
    except Exception as e:
        st.error(f"图表渲染失败: {e}")

@dialog("交易面板", width="small")
def transaction_dialog(code: str, name: str, price: float):
    st.markdown(f"### {name} ({code})")
    
    # Handle case where price is "-"
    current_price = 0.0
    if isinstance(price, (int, float)):
        current_price = float(price)
    elif isinstance(price, str) and price.replace('.','',1).isdigit():
        current_price = float(price)
        
    st.markdown(f"当前价格: **{current_price}**")
    
    tab1, tab2 = st.tabs(["买入", "卖出"])
    
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            buy_price = st.number_input("买入价格", value=current_price, step=0.01, key=f"buy_p_{code}")
        with col2:
            buy_vol = st.number_input("买入数量", value=100, step=100, key=f"buy_v_{code}")
        
        # --- Risk Management Section ---
        with st.expander("🛡️ 交易计划与风控 (可选)", expanded=True):
            r1, r2 = st.columns(2)
            with r1:
                stop_loss = st.number_input("止损价格 (Stop Loss)", value=0.0, step=0.01, key=f"sl_{code}", help="触发止损的卖出价格")
            with r2:
                take_profit = st.number_input("止盈价格 (Take Profit)", value=0.0, step=0.01, key=f"tp_{code}", help="预期获利的卖出价格")
            
            # Real-time Calculation
            if buy_price > 0 and buy_vol > 0:
                # Only calc if SL or TP is set
                if stop_loss > 0 or take_profit > 0:
                    metrics = calculate_risk_metrics(buy_price, stop_loss, take_profit, buy_vol)
                    
                    if metrics.get('warnings'):
                        for w in metrics['warnings']:
                            st.warning(f"⚠️ {w}")
                    
                    if metrics:
                        # Display Metrics
                        m1, m2, m3 = st.columns(3)
                        
                        risk_val = metrics.get('total_risk', 0)
                        risk_pct = metrics.get('risk_pct', 0)
                        m1.metric("潜在亏损", f"{risk_val:.0f}", f"{risk_pct:.1f}%", delta_color="inverse")
                        
                        reward_val = metrics.get('total_reward', 0)
                        reward_pct = metrics.get('reward_pct', 0)
                        m2.metric("预期盈利", f"{reward_val:.0f}", f"{reward_pct:.1f}%")
                        
                        rr = metrics.get('rr_ratio', 0)
                        m3.metric("盈亏比", f"1 : {rr:.1f}")

        if st.button("🔴 买入 / Buy", type="primary", use_container_width=True, key=f"btn_buy_{code}"):
            plan = None
            if stop_loss > 0 or take_profit > 0:
                plan = {
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "expected_buy": buy_price
                }
            success, msg = add_transaction(code, 'buy', buy_price, buy_vol, plan=plan)
            if success:
                st.toast(f"买入成功: {name} {buy_vol}股 @ {buy_price}", icon="💸")
                time.sleep(1)
                st.rerun()
            else:
                st.error(msg)

    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            sell_price = st.number_input("卖出价格", value=current_price, step=0.01, key=f"sell_p_{code}")
        with col2:
            sell_vol = st.number_input("卖出数量", value=100, step=100, key=f"sell_v_{code}")
            
        if st.button("🟢 卖出 / Sell", type="primary", use_container_width=True, key=f"btn_sell_{code}"):
            success, msg = add_transaction(code, 'sell', sell_price, sell_vol)
            if success:
                st.toast(f"卖出成功: {name} {sell_vol}股 @ {sell_price}", icon="💰")
                time.sleep(1)
                st.rerun()
            else:
                st.error(msg)

def render_stock_table_common(pool: list, market_data: pd.DataFrame, pool_type: str):
    """
    Shared table renderer for Picking, Watching, and Trading pools.
    Compact Layout Version
    """
    if not pool:
        st.info("列表为空")
        return

    update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # CSS Optimization for Compactness
    st.markdown("""
        <style>
        /* Compact columns */
        [data-testid="column"] {
            padding: 0rem 0.2rem !important;
        }
        /* Reduce spacing between elements */
        .block-container {
            padding-top: 5rem !important;
        }
        p {
            margin-bottom: 0.1rem;
            font-size: 0.95rem;
        }
        /* Compact buttons */
        button {
            height: 1.8rem !important;
            padding: 0rem 0.5rem !important;
            font-size: 0.8rem !important;
            min-height: 1.8rem !important;
        }
        /* Divider optimization */
        hr {
            margin: 0.2rem 0 !important;
        }
        /* Header bold */
        .header-text {
            font-weight: 600;
            color: #4a5568;
            font-size: 0.9rem;
        }
        </style>
    """, unsafe_allow_html=True)

    # Header Row
    if pool_type == 'trading':
        header_cols = st.columns([0.8, 1.2, 1.5, 1.2, 1.2, 1.5, 1.5, 0.5, 2.0])
        headers = ["代码", "名称", "现价/涨跌", "总市值", "流通市值", "持仓/成本", "浮动盈亏", "备注", "操作"]
    else:
        # Adjusted for new columns: Total MV, Circ MV, EPS, ROE
        header_cols = st.columns([0.9, 1.1, 1.0, 1.0, 1.1, 1.1, 0.8, 0.9, 1.2, 1.8])
        headers = ["代码", "名称", "最新价", "涨跌幅", "总市值", "流市值", "EPS", "ROE", "标签", "操作"]
        
    for col, h in zip(header_cols, headers):
        col.markdown(f"<span class='header-text'>{h}</span>", unsafe_allow_html=True)
        
    st.markdown("<hr style='border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)

    # Scrollable Container for Data Rows
    # Use a fixed height container to enable scrolling without pagination
    with st.container(height=650, border=False):
        for s in pool:
            code = s['code']
            name = s['name']
            note = s.get('note', {})
            if isinstance(note, str): note = {'content': note}
            has_note = bool(note.get('content'))
            tags = s.get('tags', [])
            
            # Market Data
            price = "-"
            change = 0.0
            pe = "-"
            pb = "-"
            volume = 0
            total_mv = 0
            circ_mv = 0
            
            if not market_data.empty:
                matches = market_data[market_data['代码'] == code]
                if not matches.empty:
                    row = matches.iloc[0]
                    price = row.get('最新价', '-')
                    change = row.get('涨跌幅', 0)
                    pe = row.get('市盈率-动态', '-')
                    pb = row.get('市净率', '-')
                    volume = row.get('成交量', 0)
                    total_mv = row.get('总市值', 0)
                    circ_mv = row.get('流通市值', 0)
            
            # Fallback
            if price == "-" or price is None or pd.isna(price):
                realtime = get_realtime_price(code)
                if realtime:
                    price = realtime.get('latest', '-')
                    change = realtime.get('change', 0)
            
            if pd.isna(price): price = "-"
            if pd.isna(change): change = 0.0
            
            # Fetch Financials (EPS, ROE)
            # This uses cache so it's efficient after first load
            fin_data = get_stock_financials(code)
            eps = fin_data.get('EPS', '-')
            roe = fin_data.get('ROE', '-')
            
            # Format Market Value
            def format_mv(val):
                try:
                    val = float(val)
                    if val > 100000000: # > 1亿
                        return f"{val/100000000:.1f}亿"
                    return "-"
                except:
                    return "-"
            
            total_mv_str = format_mv(total_mv)
            circ_mv_str = format_mv(circ_mv)

            # Ensure price is float for calc
            current_price_val = 0.0
            if isinstance(price, (int, float)):
                current_price_val = float(price)
            
            is_suspended = False
            if volume == 0 and (price == "-" or price == 0):
                 is_suspended = True

            # Row Container
            with st.container():
                if pool_type == 'trading':
                    c1, c2, c3, c4, c5, c6, c7, c8, c9 = st.columns([0.8, 1.2, 1.5, 1.2, 1.2, 1.5, 1.5, 0.5, 2.0])
                else:
                    c1, c2, c3, c4, c5, c6, c7, c8, c9, c10 = st.columns([0.9, 1.1, 1.0, 1.0, 1.1, 1.1, 0.8, 0.9, 1.2, 1.8])
                
                # 1. Code
                c1.markdown(f"<span style='font-family:monospace; font-size:0.9em'>{code}</span>", unsafe_allow_html=True)
                
                # 2. Name
                if is_suspended:
                    c2.markdown(f"<span style='color:#c53030; font-size:0.9em'>停牌</span> {name}", unsafe_allow_html=True)
                else:
                    c2.markdown(f"<span style='font-size:0.95em'>{name}</span>", unsafe_allow_html=True)
                    
                # 3. Price Info
                color = "#c53030" if change > 0 else "#2f855a" if change < 0 else "#718096"
                arrow = "↑" if change > 0 else "↓" if change < 0 else ""
                
                if pool_type == 'trading':
                    c3.markdown(f"<span style='font-weight:bold'>{price}</span> <span style='color:{color}; font-size:0.85em'>{change:.2f}%</span>", unsafe_allow_html=True)
                else:
                    c3.markdown(f"**{price}**", unsafe_allow_html=True)
                    c4.markdown(f"<span style='color:{color}'>{change:.2f}% {arrow}</span>", unsafe_allow_html=True)
                
                # 4/5. Market Value (Split Columns)
                if pool_type == 'trading':
                    c4.markdown(f"<span style='font-size:0.85em; color:#4a5568'>{total_mv_str}</span>", unsafe_allow_html=True)
                    c5.markdown(f"<span style='font-size:0.85em; color:#4a5568'>{circ_mv_str}</span>", unsafe_allow_html=True)
                else:
                    c5.markdown(f"<span style='font-size:0.85em; color:#4a5568'>{total_mv_str}</span>", unsafe_allow_html=True)
                    c6.markdown(f"<span style='font-size:0.85em; color:#4a5568'>{circ_mv_str}</span>", unsafe_allow_html=True)
                    
                    # EPS & ROE
                    eps_val = f"{eps:.2f}" if isinstance(eps, (int, float)) else "-"
                    roe_val = f"{roe:.2f}%" if isinstance(roe, (int, float)) else "-"
                    
                    c7.markdown(f"<span style='font-size:0.85em'>{eps_val}</span>", unsafe_allow_html=True)
                    c8.markdown(f"<span style='font-size:0.85em'>{roe_val}</span>", unsafe_allow_html=True)

                # 4. Trading Specifics OR Tags
                if pool_type == 'trading':
                    holdings = s.get('holdings', {})
                    vol = holdings.get('volume', 0)
                    avg = holdings.get('avg_cost', 0.0)
                    c6.markdown(f"<span style='font-size:0.9em'><b>{vol}</b> / {avg:.1f}</span>", unsafe_allow_html=True)
                    
                    # PnL
                    if vol > 0 and current_price_val > 0:
                        market_val = vol * current_price_val
                        cost_val_calc = vol * avg
                        pnl_val = market_val - cost_val_calc
                        pnl_pct = (pnl_val / cost_val_calc) * 100 if cost_val_calc > 0 else 0
                        pnl_color = "#c53030" if pnl_val > 0 else "#2f855a" if pnl_val < 0 else "#718096"
                        c7.markdown(f"<span style='color:{pnl_color}; font-weight:bold'>{pnl_val:+.0f}</span> <span style='color:{pnl_color}; font-size:0.85em'>({pnl_pct:+.1f}%)</span>", unsafe_allow_html=True)
                    else:
                        c7.write("-")
                        
                    if has_note: c8.markdown("📝", help=note.get('content')[:100])
                    else: c8.write("")
                    
                else:
                    if tags:
                        tag_html = "".join([f"<span style='background-color:#edf2f7; color:#4a5568; padding:1px 4px; border-radius:4px; font-size:0.75em; margin-right:2px;'>{t}</span>" for t in tags[:2]])
                        c9.markdown(tag_html, unsafe_allow_html=True)
                    else:
                        c9.write("-")

                    # Note column removed from header but used in tooltips? 
                    # No, I should keep it or merge.
                    # I removed the note column from picking pool to save space.
                    # But I need to handle the column count correctly.
                    # New Picking: c1..c10. 
                    # c9 is Tags. c10 is Ops.
                    # Where is Note? I removed it from headers.
                    # Maybe I can put a small note icon in the Name column or Tags column if there is a note?
                    # Or just rely on the "Edit Note" button in Ops which opens the dialog.
                    # I'll rely on the "Edit Note" button.

                # 7. Operations
                if pool_type == 'trading':
                     op_col = c9
                else:
                     op_col = c10
                     
                with op_col:
                    # Use smaller columns for buttons
                    b_cols = st.columns(6)
                    
                    with b_cols[0]:
                        if st.button("📊", key=f"d_{pool_type}_{code}", help="详情"):
                            show_stock_details_dialog(code, name, {"pe": pe, "pb": pb})
                    with b_cols[1]:
                        if st.button("✏️", key=f"n_{pool_type}_{code}", help="备注"):
                            edit_note_dialog(code, name, pool_type)
                    with b_cols[2]:
                        if st.button("🏷️", key=f"t_{pool_type}_{code}", help="标签"):
                            edit_tags_dialog(code, name, pool_type)

                    # Custom Buttons
                    if pool_type == 'picking':
                        with b_cols[3]:
                            if st.button("👁️", key=f"mv_{pool_type}_{code}", help="移入观察"):
                                success, msg = move_to_watching_pool(code)
                                if success: st.toast(msg); time.sleep(0.5); st.rerun()
                        with b_cols[4]:
                            if st.button("🗑️", key=f"rm_{pool_type}_{code}", help="删除"):
                                success, msg = remove_from_pool(code)
                                if success: st.toast(msg); time.sleep(0.5); st.rerun()

                    elif pool_type == 'watching':
                        with b_cols[3]:
                            if st.button("🤝", key=f"mv_{pool_type}_{code}", help="移入交易"):
                                success, msg = move_to_trading_pool(code)
                                if success: st.toast(msg); time.sleep(0.5); st.rerun()
                        with b_cols[4]:
                            if st.button("🔙", key=f"bk_{pool_type}_{code}", help="移回选股"):
                                success, msg = move_from_watching_to_picking(code)
                                if success: st.toast(msg); time.sleep(0.5); st.rerun()
                        with b_cols[5]:
                            if st.button("🗑️", key=f"rm_{pool_type}_{code}", help="移除"):
                                success, msg = remove_from_watching_pool(code)
                                if success: st.toast(msg); time.sleep(0.5); st.rerun()

                    elif pool_type == 'trading':
                        with b_cols[3]:
                            if st.button("🔙", key=f"mv_{pool_type}_{code}", help="移回观察"):
                                success, msg = move_from_trading_to_watching(code)
                                if success: st.toast(msg); time.sleep(0.5); st.rerun()
                        with b_cols[4]:
                            if st.button("💸", key=f"tr_{pool_type}_{code}", help="交易"):
                                 transaction_dialog(code, name, price)
                        with b_cols[5]:
                            if st.button("🗑️", key=f"rm_{pool_type}_{code}", help="删除"):
                                success, msg = remove_from_trading_pool(code)
                                if success: st.toast(msg); time.sleep(0.5); st.rerun()
                
                # Tiny divider between rows
                st.markdown("<hr style='margin: 0.1rem 0; border-top: 1px solid #f7fafc;'>", unsafe_allow_html=True)
    
    st.caption(f"共 {len(pool)} 条记录 | 更新: {update_time}")
