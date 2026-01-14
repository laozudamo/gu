import datetime

import streamlit as st

from utils.schemas import AkshareParams, BacktraderParams
from utils.locale import t


def akshare_selector_ui() -> AkshareParams:
    """akshare params

    :return: AkshareParams
    """
    st.sidebar.markdown(f"# {t('akshare_config')}")
    symbol = st.sidebar.text_input(t('symbol'))
    period_options = ["daily", "weekly", "monthly"]
    period_labels = [t('daily'), t('weekly'), t('monthly')]
    period = st.sidebar.selectbox(t('period'), period_options, format_func=lambda x: period_labels[period_options.index(x)])
    
    start_date = st.sidebar.date_input(t('start_date'), datetime.date(1970, 1, 1))
    start_date = start_date.strftime("%Y%m%d")
    end_date = st.sidebar.date_input(t('end_date'), datetime.datetime.today())
    end_date = end_date.strftime("%Y%m%d")
    adjust = st.sidebar.selectbox(t('adjust'), ("qfq", "hfq", ""))
    return AkshareParams(
        symbol=symbol,
        period=period,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
    )


def backtrader_selector_ui() -> BacktraderParams:
    """backtrader params

    :return: BacktraderParams
    """
    st.sidebar.markdown(f"# {t('backtrader_config')}")
    start_date = st.sidebar.date_input(t('backtrader_start_date'), datetime.date(2010, 1, 1))
    end_date = st.sidebar.date_input(t('backtrader_end_date'), datetime.datetime.today())
    start_cash = st.sidebar.number_input(t('start_cash'), min_value=0, value=100000, step=10000)
    commission_fee = st.sidebar.number_input(t('commission_fee'), min_value=0.0, max_value=1.0, value=0.001, step=0.0001)
    stake = st.sidebar.number_input(t('stake'), min_value=0, value=100, step=10)
    return BacktraderParams(
        start_date=start_date,
        end_date=end_date,
        start_cash=start_cash,
        commission_fee=commission_fee,
        stake=stake,
    )
