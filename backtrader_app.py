import streamlit as st
from streamlit_echarts import st_pyecharts


from utils.load import load_strategy
from utils.logs import logger
from utils.processing import gen_stock_df, run_backtrader
from utils.schemas import StrategyBase
from utils.locale import t
from frames import callback, stock_picking_pool, stock_watching_pool, stock_trading_pool


st.set_page_config(page_title="backtrader", page_icon=":chart_with_upwards_trend:", layout="wide")

strategy_dict = load_strategy("./config/strategy.yaml")



# def about_page():
#     # st.header(t("about"))
#     st.write(t("about_content"))

def main():
    # Language selector
    if "language" not in st.session_state:
        st.session_state["language"] = "en"
    
    with st.sidebar:
        # st.sidebar.markdown(f"# {t('language')}")
        # lang = st.selectbox(
        #     t("language"),
        #     options=["en", "zh"],
        #     format_func=lambda x: "English" if x == "en" else "中文",
        #     index=0 if st.session_state["language"] == "en" else 1,
        #     key="lang_select"
        # )
        # if lang != st.session_state["language"]:
        #     st.session_state["language"] = lang
        #     st.rerun()

        # st.sidebar.markdown("---")
        
        # Page navigation
        # page = st.radio(
        #     t("page"),
        #     options=["home", "about"],
        #     format_func=lambda x: t(x)
        # )

        page = st.navigation(
            pages=[
           
                st.Page(stock_picking_pool, title=t("stock_picking_pool")),
                st.Page(stock_watching_pool, title=t("stock_watching_pool")),
                st.Page(stock_trading_pool, title=t("stock_trading_pool")),
                st.Page(callback, title=t("callback")),
            ]
        )
    
    page.run()

    # if page == "home":
        # home_page()
        # page.run()
    # elif page == "about":
        # page.run()
        # about_page()

if __name__ == "__main__":
    main()
