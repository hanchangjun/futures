import argparse
import os
import webbrowser
import requests
import json
import numpy as np
from datetime import datetime

from datafeed import get_bars
from datafeed.base import PriceBar, parse_timestamp
from chan.k_merge import merge_klines
from chan.fractal import find_fractals
from chan.bi import find_bi
from chan.duan import find_duan
from chan.center import find_zhongshu
from chan.indicators import calculate_macd, compute_bi_macd
from chan.common import FXType, Trend

def fetch_bars_from_api(symbol, period, limit=1000):
    url = f"http://localhost:8000/api/bars/{symbol}/{period}?limit={limit}"
    print(f"Requesting {url}...")
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        bars = []
        for d in data:
            bars.append(PriceBar(
                date=parse_timestamp(d['dt']),
                open=d['open'],
                high=d['high'],
                low=d['low'],
                close=d['close'],
                volume=d['volume']
            ))
        return bars
    except Exception as e:
        print(f"API Error: {e}")
        return []

def generate_chan_chart(args):
    print(f"Fetching data for {args.symbol}...")
    
    if args.source == 'api':
        bars = fetch_bars_from_api(args.symbol, args.period, args.count)
    else:
        bars, _ = get_bars(
            source=args.source,
            symbol=args.symbol,
            period=args.period,
            count=args.count,
            tq_symbol=args.tq_symbol,
            username=os.getenv("TQ_USERNAME"),
            password=os.getenv("TQ_PASSWORD"),
            wait_update_once=False
        )
    
    if not bars:
        print("No bars found.")
        return

    print("Processing Chan Logic...")
    
    # 0. MACD
    macd_df = calculate_macd(bars)
    
    # 1. Merge
    chan_bars = merge_klines(bars)
    print(f"Merged {len(bars)} raw bars into {len(chan_bars)} Chan bars.")
    
    # 2. Fractals
    fractals = find_fractals(chan_bars)
    print(f"Found {len(fractals)} fractals.")
    
    # 3. Bi
    bis = find_bi(chan_bars, fractals)
    print(f"Found {len(bis)} strokes (Bi).")
    
    # 4. Duan
    duans = find_duan(bis)
    print(f"Found {len(duans)} segments (Duan).")
    
    # 5. ZhongShu
    centers = find_zhongshu(bis)
    print(f"Found {len(centers)} pivots (ZhongShu).")

    # Visualization using ECharts
    render_chart(bars, bis, duans, centers, macd_df)

def render_chart(raw_bars, bis, duans, centers, macd_df):
    dates = [b.date.strftime("%Y-%m-%d %H:%M") for b in raw_bars]
    kline_data = [[b.open, b.close, b.low, b.high] for b in raw_bars]
    
    # MACD Data
    macd_data = []
    diff_data = []
    dea_data = []
    if not macd_df.empty:
        # Handle NaN
        macd_df = macd_df.fillna(0)
        macd_data = macd_df['macd'].tolist()
        diff_data = macd_df['diff'].tolist()
        dea_data = macd_df['dea'].tolist()

    # Bi Lines
    bi_lines = []
    for bi in bis:
        start_date = bi.start_fx.date.strftime("%Y-%m-%d %H:%M")
        end_date = bi.end_fx.date.strftime("%Y-%m-%d %H:%M")
        start_val = bi.start_fx.high if bi.start_fx.type == FXType.TOP else bi.start_fx.low
        end_val = bi.end_fx.high if bi.end_fx.type == FXType.TOP else bi.end_fx.low
        color = "#ff0000" if bi.direction == Trend.UP else "#00ff00"
        bi_lines.append({
            "coords": [[start_date, start_val], [end_date, end_val]],
            "lineStyle": {"color": color, "width": 1}
        })
        
    # ZhongShu Areas
    zs_areas = []
    for zs in centers:
        if zs.start_bi_index >= len(bis) or zs.end_bi_index >= len(bis):
            continue
        start_bi = bis[zs.start_bi_index]
        end_bi = bis[zs.end_bi_index]
        
        start_date = start_bi.start_fx.date.strftime("%Y-%m-%d %H:%M")
        end_date = end_bi.end_fx.date.strftime("%Y-%m-%d %H:%M")
        
        # Color: Up(Enter) -> Red, Down(Enter) -> Green? 
        # Usually Pivot Color denotes direction
        color = "rgba(135, 206, 235, 0.4)" # SkyBlue transparent
        
        zs_areas.append([
            {"xAxis": start_date, "yAxis": zs.zg, "itemStyle": {"color": color}},
            {"xAxis": end_date, "yAxis": zs.zd}
        ])

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Chan Theory Chart</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        body, html {{ height: 100%; margin: 0; }}
        #main {{ height: 100%; }}
    </style>
</head>
<body>
    <div id="main"></div>
    <script type="text/javascript">
        var chartDom = document.getElementById('main');
        var myChart = echarts.init(chartDom);
        var option;

        var dates = {json.dumps(dates)};
        var data = {json.dumps(kline_data)};
        var biLines = {json.dumps(bi_lines)};
        var zsAreas = {json.dumps(zs_areas)};
        var macdData = {json.dumps(macd_data)};
        var diffData = {json.dumps(diff_data)};
        var deaData = {json.dumps(dea_data)};

        option = {{
            title: {{ text: 'Chan Theory Chart' }},
            tooltip: {{
                trigger: 'axis',
                axisPointer: {{ type: 'cross' }}
            }},
            legend: {{ data: ['K-Line', 'Bi', 'Diff', 'Dea'] }},
            grid: [
                {{ left: '3%', right: '3%', height: '60%' }},
                {{ left: '3%', right: '3%', top: '75%', height: '20%' }}
            ],
            xAxis: [
                {{ type: 'category', data: dates, scale: true, gridIndex: 0 }},
                {{ type: 'category', data: dates, scale: true, gridIndex: 1, show: false }}
            ],
            yAxis: [
                {{ scale: true, splitArea: {{ show: true }}, gridIndex: 0 }},
                {{ scale: true, gridIndex: 1, splitNumber: 3 }}
            ],
            dataZoom: [
                {{ type: 'inside', xAxisIndex: [0, 1] }},
                {{ type: 'slider', xAxisIndex: [0, 1] }}
            ],
            series: [
                {{
                    name: 'K-Line',
                    type: 'candlestick',
                    data: data,
                    itemStyle: {{
                        color: '#FD1050',
                        color0: '#0CF49B',
                        borderColor: '#FD1050',
                        borderColor0: '#0CF49B'
                    }},
                    markArea: {{
                        data: zsAreas
                    }}
                }},
                {{
                    name: 'Bi',
                    type: 'lines',
                    coordinateSystem: 'cartesian2d',
                    data: biLines,
                    polyline: false,
                    z: 10
                }},
                {{
                    name: 'MACD',
                    type: 'bar',
                    xAxisIndex: 1,
                    yAxisIndex: 1,
                    data: macdData,
                    itemStyle: {{
                        color: function(params) {{
                            return params.value > 0 ? '#FD1050' : '#0CF49B';
                        }}
                    }}
                }},
                {{
                    name: 'Diff',
                    type: 'line',
                    xAxisIndex: 1,
                    yAxisIndex: 1,
                    data: diffData,
                    symbol: 'none',
                    lineStyle: {{ opacity: 0.5 }}
                }},
                {{
                    name: 'Dea',
                    type: 'line',
                    xAxisIndex: 1,
                    yAxisIndex: 1,
                    data: deaData,
                    symbol: 'none',
                    lineStyle: {{ opacity: 0.5 }}
                }}
            ]
        }};

        myChart.setOption(option);
    </script>
</body>
</html>
    """
    
    with open("chan_chart.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print("Chart saved to chan_chart.html")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="KQ.m@SHFE.rb")
    parser.add_argument("--period", default="30m")
    parser.add_argument("--count", type=int, default=2000)
    parser.add_argument("--source", default="tq", help="Source: tq or api")
    parser.add_argument("--tq-symbol")
    
    args = parser.parse_args()
    generate_chan_chart(args)
