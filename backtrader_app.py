import streamlit as st
from streamlit_echarts import st_pyecharts


from utils.load import load_strategy
from utils.logs import logger
from utils.processing import gen_stock_df, run_backtrader
from utils.schemas import StrategyBase
from utils.locale import t
from frames import callback, stock_picking_pool, stock_watching_pool, stock_trading_pool


st.set_page_config(page_title="量化回测系统", page_icon=":chart_with_upwards_trend:", layout="wide")

strategy_dict = load_strategy("./config/strategy.yaml")

def main():
    # Deprecated: Language selector removed
    if "language" not in st.session_state:
        st.session_state["language"] = "zh"
    
    with st.sidebar:
        page = st.navigation(
            pages=[
                st.Page(stock_picking_pool, title="选股池", icon=":material/search:"),
                st.Page(stock_watching_pool, title="观察池", icon=":material/visibility:"),
                st.Page(stock_trading_pool, title="交易池", icon=":material/currency_exchange:"),
                st.Page(callback, title="回测模块", icon=":material/history:"),
            ]
        )
    
    page.run()

if __name__ == "__main__":
    main()
