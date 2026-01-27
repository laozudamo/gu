import streamlit as st
from streamlit_echarts import st_pyecharts


from utils.load import load_strategy
from utils.logs import logger
from utils.processing import gen_stock_df, run_backtrader
from utils.schemas import StrategyBase
from utils.locale import t
from utils.cache_manager import get_cache_manager
from frames import callback, stock_picking_pool, stock_watching_pool, stock_trading_pool


st.set_page_config(page_title="量化回测系统", page_icon=":chart_with_upwards_trend:", layout="wide")
st.markdown(
    """
    <style>
    .stAppHeader { display: none; }
    div[data-testid="stHeader"] { display: none; }
    header[data-testid="stHeader"] { display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

strategy_dict = load_strategy("./config/strategy.yaml")

def main():
    # Deprecated: Language selector removed
    if "language" not in st.session_state:
        st.session_state["language"] = "zh"
    
    with st.sidebar:
        # Display success message from previous run if flag is set
        if st.session_state.get('refresh_success', False):
            st.success("✅ 刷新成功！")
            st.session_state['refresh_success'] = False
            
        page = st.navigation(
            pages=[
                st.Page(stock_picking_pool, title="选股池", icon=":material/search:"),
                st.Page(stock_watching_pool, title="观察池", icon=":material/visibility:"),
                st.Page(stock_trading_pool, title="交易池", icon=":material/currency_exchange:"),
                # st.Page(callback, title="回测模块", icon=":material/history:"),
            ]
        )
        
        # if st.button("🔄 刷新行情数据", use_container_width=True):
        #     with st.spinner("正在同步最新行情..."):
        #         try:
        #             cm = get_cache_manager()
        #             cm.update_cache(force=True)
        #             st.cache_data.clear()
        #             st.session_state['refresh_success'] = True
        #             st.rerun()
        #         except Exception as e:
        #             st.error(f"更新失败: {e}")
    
    page.run()

if __name__ == "__main__":
    main()
