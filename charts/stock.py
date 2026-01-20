import pandas as pd
import pyecharts.options as opts
from pyecharts.charts import Bar, Grid, Kline, Line

from utils.locale import t


def split_data(df: pd.DataFrame) -> tuple[list[str], list[list[float]], pd.Series, list[list[float]]]:
    x_data = df["日期"].values.tolist()
    y_data = df[["开盘", "收盘", "最低", "最高"]].values.tolist()
    df_close = df["收盘"]

    df["index"] = df.index
    df["rise"] = df[["开盘", "收盘"]].apply(lambda x: 1 if x.iloc[0] > x.iloc[1] else -1, axis=1)
    y_vol = df[["index", "成交量", "rise"]].values.tolist()
    return x_data, y_data, df_close, y_vol


def calculate_ma(day_count: int, df: pd.DataFrame) -> list[float]:
    df_ma = df.rolling(day_count).mean().round(2).fillna("-")
    return df_ma.values.tolist()

def calculate_boll(df: pd.DataFrame, n=20) -> tuple[list[float], list[float], list[float]]:
    # Simple BOLL: Mid=MA20, Upper=Mid+2*std, Lower=Mid-2*std
    close = df['收盘']
    mid = close.rolling(n).mean()
    std = close.rolling(n).std()
    upper = mid + 2 * std
    lower = mid - 2 * std
    
    return (
        upper.round(2).fillna("-").tolist(),
        mid.round(2).fillna("-").tolist(),
        lower.round(2).fillna("-").tolist()
    )

def calculate_macd(df: pd.DataFrame) -> tuple[list[float], list[float], list[float]]:
    # MACD: EMA12, EMA26, DIFF, DEA, MACD
    close = df['收盘']
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    diff = ema12 - ema26
    dea = diff.ewm(span=9, adjust=False).mean()
    macd = (diff - dea) * 2
    
    return (
        diff.round(3).fillna("-").tolist(),
        dea.round(3).fillna("-").tolist(),
        macd.round(3).fillna("-").tolist()
    )

def draw_pro_kline(df: pd.DataFrame, main_indicator="MA", sub_indicator="VOL") -> Grid:
    x_data, y_data, df_close, y_vol = split_data(df)
    
    # --- Main Chart (Kline) ---
    kline = (
        Kline()
        .add_xaxis(xaxis_data=x_data)
        .add_yaxis(
            series_name="日K",
            y_axis=y_data,
            itemstyle_opts=opts.ItemStyleOpts(color="#ec0000", color0="#00da3c"),
        )
        .set_global_opts(
            legend_opts=opts.LegendOpts(is_show=True, pos_bottom=10, pos_left="center"),
            datazoom_opts=[
                opts.DataZoomOpts(
                    is_show=False,
                    type_="inside",
                    xaxis_index=[0, 1],
                    range_start=95,
                    range_end=100,
                ),
                opts.DataZoomOpts(
                    is_show=True,
                    xaxis_index=[0, 1],
                    type_="slider",
                    pos_top="92%", # Moved down slightly
                    range_start=95,
                    range_end=100,
                ),
            ],
            yaxis_opts=opts.AxisOpts(
                is_scale=True,
                splitarea_opts=opts.SplitAreaOpts(is_show=True, areastyle_opts=opts.AreaStyleOpts(opacity=1)),
            ),
            tooltip_opts=opts.TooltipOpts(
                trigger="axis",
                axis_pointer_type="cross",
                background_color="rgba(245, 245, 245, 0.8)",
                border_width=1,
                border_color="#ccc",
                textstyle_opts=opts.TextStyleOpts(color="#000"),
            ),
            visualmap_opts=opts.VisualMapOpts(
                is_show=False,
                dimension=2,
                series_index=5,
                is_piecewise=True,
                pieces=[
                    {"value": 1, "color": "#00da3c"},
                    {"value": -1, "color": "#ec0000"},
                ],
            ),
            axispointer_opts=opts.AxisPointerOpts(
                is_show=True,
                link=[{"xAxisIndex": "all"}],
                label=opts.LabelOpts(background_color="#777"),
            ),
            toolbox_opts=opts.ToolboxOpts(
                is_show=True,
                feature={
                    "saveAsImage": {"show": True, "title": "Save"},
                    "dataZoom": {"show": True, "title": {"zoom": "Zoom", "back": "Reset"}},
                    "restore": {"show": True, "title": "Restore"},
                },
                pos_right="2%",
                pos_top="0%",
            ),
        )
    )

    # --- Overlays (MA / BOLL) ---
    line_main = Line().add_xaxis(xaxis_data=x_data)
    
    if main_indicator == "MA":
        ma_list = [5, 10, 20, 30]
        for d in ma_list:
            line_main.add_yaxis(
                series_name=f"MA{d}",
                y_axis=calculate_ma(d, df_close),
                is_smooth=True,
                is_hover_animation=False,
                linestyle_opts=opts.LineStyleOpts(width=1.5, opacity=0.7),
                label_opts=opts.LabelOpts(is_show=False),
            )
    elif main_indicator == "BOLL":
        upper, mid, lower = calculate_boll(df)
        line_main.add_yaxis("UPPER", upper, is_smooth=True, linestyle_opts=opts.LineStyleOpts(width=1, opacity=0.7), label_opts=opts.LabelOpts(is_show=False))
        line_main.add_yaxis("MID", mid, is_smooth=True, linestyle_opts=opts.LineStyleOpts(width=1.5, opacity=0.7, color="orange"), label_opts=opts.LabelOpts(is_show=False))
        line_main.add_yaxis("LOWER", lower, is_smooth=True, linestyle_opts=opts.LineStyleOpts(width=1, opacity=0.7), label_opts=opts.LabelOpts(is_show=False))

    line_main.set_global_opts(xaxis_opts=opts.AxisOpts(type_="category"))
    
    overlap_main = kline.overlap(line_main)

    # --- Sub Chart (VOL / MACD) ---
    sub_chart = None
    
    if sub_indicator == "VOL":
        sub_chart = (
            Bar()
            .add_xaxis(xaxis_data=x_data)
            .add_yaxis(
                series_name="成交量",
                y_axis=y_vol,
                xaxis_index=1,
                yaxis_index=1,
                label_opts=opts.LabelOpts(is_show=False),
            )
            .set_global_opts(
                xaxis_opts=opts.AxisOpts(
                    type_="category",
                    is_scale=True,
                    grid_index=1,
                    boundary_gap=True,
                    axisline_opts=opts.AxisLineOpts(is_on_zero=False),
                    axistick_opts=opts.AxisTickOpts(is_show=False),
                    splitline_opts=opts.SplitLineOpts(is_show=False),
                    axislabel_opts=opts.LabelOpts(is_show=False),
                    split_number=20,
                    min_="dataMin",
                    max_="dataMax",
                ),
                yaxis_opts=opts.AxisOpts(
                    grid_index=1,
                    is_scale=True,
                    split_number=2,
                    axislabel_opts=opts.LabelOpts(is_show=False),
                    axisline_opts=opts.AxisLineOpts(is_show=False),
                    axistick_opts=opts.AxisTickOpts(is_show=False),
                    splitline_opts=opts.SplitLineOpts(is_show=False),
                ),
                legend_opts=opts.LegendOpts(is_show=False),
            )
        )
    elif sub_indicator == "MACD":
        diff, dea, macd = calculate_macd(df)
        # Bar for MACD histogram
        bar_macd = (
            Bar()
            .add_xaxis(xaxis_data=x_data)
            .add_yaxis(
                "MACD", 
                macd, 
                xaxis_index=1, 
                yaxis_index=1,
                label_opts=opts.LabelOpts(is_show=False),
                itemstyle_opts=opts.ItemStyleOpts(
                    color=lambda x: "#ec0000" if x > 0 else "#00da3c" # Red up, Green down logic
                )
            )
        )
        # Lines for DIFF/DEA
        line_macd = (
            Line()
            .add_xaxis(xaxis_data=x_data)
            .add_yaxis("DIFF", diff, xaxis_index=1, yaxis_index=1, label_opts=opts.LabelOpts(is_show=False), is_symbol_show=False)
            .add_yaxis("DEA", dea, xaxis_index=1, yaxis_index=1, label_opts=opts.LabelOpts(is_show=False), is_symbol_show=False)
        )
        
        sub_chart = bar_macd.overlap(line_macd)
        sub_chart.set_global_opts(
             xaxis_opts=opts.AxisOpts(
                type_="category", 
                grid_index=1,
                axislabel_opts=opts.LabelOpts(is_show=False),
             ),
             yaxis_opts=opts.AxisOpts(
                grid_index=1,
                split_number=2,
             ),
             legend_opts=opts.LegendOpts(is_show=False),
        )

    # --- Grid Layout ---
    grid_chart = Grid(
        init_opts=opts.InitOpts(
            animation_opts=opts.AnimationOpts(animation=False),
            width="100%",
            height="700px"
        )
    )
    
    # Main Chart (Top 60%)
    grid_chart.add(
        overlap_main,
        grid_opts=opts.GridOpts(pos_left="10%", pos_right="8%", height="55%"),
    )
    
    # Sub Chart (Bottom 20%)
    if sub_chart:
        grid_chart.add(
            sub_chart,
            grid_opts=opts.GridOpts(pos_left="10%", pos_right="8%", pos_top="68%", height="20%"),
        )

    return grid_chart
