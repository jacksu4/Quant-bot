"""
量化交易可视化Dashboard
运行方式: streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from exchange import BinanceClient
from data_store import (
    add_snapshot,
    get_daily_values,
    calculate_pnl,
    load_snapshots,
)
from strategy import get_strategy_status, get_logs, RSI_OVERSOLD, RSI_OVERBOUGHT

# 页面配置
st.set_page_config(
    page_title="量化交易Dashboard",
    page_icon="📈",
    layout="wide",
)


@st.cache_resource
def get_client():
    """获取交易所客户端（缓存）"""
    return BinanceClient()


# 获取策略状态
try:
    status = get_strategy_status()
    client = get_client()
except Exception as e:
    st.error(f"❌ 连接失败: {e}")
    st.stop()

# 标题和模式指示
col_title, col_mode = st.columns([3, 1])
with col_title:
    st.title("📈 量化交易 Dashboard")
with col_mode:
    st.markdown(f"### {status['mode']}")
    if status['is_live']:
        st.warning("真实资金交易中")

# 侧边栏
with st.sidebar:
    st.header("⚙️ 控制面板")

    if st.button("🔄 刷新数据", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    # 策略配置显示
    st.subheader("📋 策略配置")
    config = status['config']
    st.info(f"""
    **RSI参数**
    - 超卖阈值: < {config['rsi_oversold']}
    - 超买阈值: > {config['rsi_overbought']}

    **风控参数**
    - 单次最大: ${config['max_position_usdt']}
    - 止损: -{config['stop_loss_pct']}%
    - 止盈: +{config['take_profit_pct']}%
    - 最大持仓: {config['max_positions']}个
    """)

    st.divider()

    st.subheader("📊 时间范围")
    time_range = st.selectbox(
        "选择查看周期",
        options=[1, 5, 7, 30, 90],
        format_func=lambda x: f"{x} 天",
        index=2,
    )

    st.divider()

    st.subheader("🚀 运行策略")
    st.code("python run_strategy.py", language="bash")
    st.caption("在终端运行上述命令启动自动交易")

# 保存快照
tickers = status['tickers']
balance = client.get_balance()
total_value = status['total_value']
add_snapshot(total_value, balance, tickers)

# ========== 第一行：关键指标 ==========
st.header("💰 账户总览")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="总资产 (USDT)",
        value=f"${total_value:,.2f}",
    )

with col2:
    st.metric(
        label="USDT可用",
        value=f"${status['usdt_free']:,.2f}",
    )

pnl_7d = calculate_pnl(total_value, 7)
pnl_30d = calculate_pnl(total_value, 30)

with col3:
    if pnl_7d['has_data']:
        st.metric(
            label="7日盈亏",
            value=f"${pnl_7d['pnl']:+,.2f}",
            delta=f"{pnl_7d['pnl_percent']:+.2f}%",
        )
    else:
        st.metric(label="7日盈亏", value="暂无数据")

with col4:
    if pnl_30d['has_data']:
        st.metric(
            label="30日盈亏",
            value=f"${pnl_30d['pnl']:+,.2f}",
            delta=f"{pnl_30d['pnl_percent']:+.2f}%",
        )
    else:
        st.metric(label="30日盈亏", value="暂无数据")

st.divider()

# ========== 第二行：RSI信号和持仓 ==========
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📊 RSI信号面板")

    signals = status['signals']
    if signals:
        signal_data = []
        for sig in signals:
            if sig['rsi'] < RSI_OVERSOLD:
                signal_text = "🟢 超卖 - 买入信号"
                color = "green"
            elif sig['rsi'] > RSI_OVERBOUGHT:
                signal_text = "🔴 超买 - 卖出信号"
                color = "red"
            else:
                signal_text = "⚪ 中性 - 观望"
                color = "gray"

            signal_data.append({
                '交易对': sig['symbol'],
                'RSI': sig['rsi'],
                '价格': sig['price'],
                '信号': signal_text,
            })

        df_signals = pd.DataFrame(signal_data)

        # RSI柱状图
        fig_rsi = go.Figure()

        colors = ['green' if r < RSI_OVERSOLD else 'red' if r > RSI_OVERBOUGHT else 'gray'
                  for r in df_signals['RSI']]

        fig_rsi.add_trace(go.Bar(
            x=df_signals['交易对'],
            y=df_signals['RSI'],
            marker_color=colors,
            text=df_signals['RSI'].round(1),
            textposition='outside',
        ))

        # 添加超卖/超买线
        fig_rsi.add_hline(y=RSI_OVERSOLD, line_dash="dash", line_color="green",
                         annotation_text=f"超卖 ({RSI_OVERSOLD})")
        fig_rsi.add_hline(y=RSI_OVERBOUGHT, line_dash="dash", line_color="red",
                         annotation_text=f"超买 ({RSI_OVERBOUGHT})")

        fig_rsi.update_layout(
            title="RSI指标 (1小时)",
            yaxis_title="RSI",
            yaxis_range=[0, 100],
            height=300,
            showlegend=False,
        )

        st.plotly_chart(fig_rsi, use_container_width=True)

        # 信号表格
        st.dataframe(
            df_signals.style.format({
                'RSI': '{:.1f}',
                '价格': '${:,.2f}',
            }),
            use_container_width=True,
            hide_index=True,
        )

with col_right:
    st.subheader("💼 当前持仓")

    positions = status['positions']
    if positions:
        pos_data = []
        for pos in positions:
            pnl_color = "🟢" if pos['pnl'] >= 0 else "🔴"
            pos_data.append({
                '币种': pos['currency'],
                '数量': pos['amount'],
                '现价': pos['current_price'],
                '市值': pos['current_value'],
                '盈亏': f"{pnl_color} ${pos['pnl']:+.2f}",
                '盈亏%': pos['pnl_percent'],
            })

        df_pos = pd.DataFrame(pos_data)

        st.dataframe(
            df_pos.style.format({
                '数量': '{:.8f}',
                '现价': '${:,.2f}',
                '市值': '${:,.2f}',
                '盈亏%': '{:+.2f}%',
            }),
            use_container_width=True,
            hide_index=True,
        )

        # 持仓分布饼图
        if len(positions) > 0:
            fig_pie = px.pie(
                df_pos,
                values='市值',
                names='币种',
                title='持仓分布',
                hole=0.4,
            )
            fig_pie.update_layout(height=250)
            st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("暂无持仓。策略会在RSI超卖时自动买入。")

    # 显示完整余额
    st.subheader("💵 账户余额")
    if balance:
        bal_data = []
        for currency, info in balance.items():
            symbol = f"{currency}/USDT"
            if currency in ['USDT', 'BUSD', 'USDC']:
                value = info['total']
            elif symbol in tickers:
                value = info['total'] * tickers[symbol]['last']
            else:
                value = 0

            bal_data.append({
                '币种': currency,
                '总量': info['total'],
                '可用': info['free'],
                '价值(USDT)': value,
            })

        df_bal = pd.DataFrame(bal_data)
        df_bal = df_bal.sort_values('价值(USDT)', ascending=False)

        st.dataframe(
            df_bal.style.format({
                '总量': '{:.8f}',
                '可用': '{:.8f}',
                '价值(USDT)': '${:,.2f}',
            }),
            use_container_width=True,
            hide_index=True,
        )

st.divider()

# ========== 第三行：资产曲线 ==========
st.subheader("📈 资产曲线")

daily_values = get_daily_values(time_range)

if len(daily_values) >= 2:
    df_curve = pd.DataFrame(daily_values)
    df_curve['date'] = pd.to_datetime(df_curve['date'])

    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(
        x=df_curve['date'],
        y=df_curve['value'],
        mode='lines+markers',
        name='总资产',
        line=dict(color='#1f77b4', width=2),
        fill='tozeroy',
        fillcolor='rgba(31, 119, 180, 0.1)',
    ))

    fig_line.update_layout(
        title=f'最近 {time_range} 天资产变化',
        xaxis_title='日期',
        yaxis_title='资产价值 (USDT)',
        hovermode='x unified',
        height=350,
    )

    st.plotly_chart(fig_line, use_container_width=True)
else:
    st.info("📌 数据积累中... 请多次刷新页面（不同时间段），收益曲线将自动显示。")

st.divider()

# ========== 第四行：策略日志 ==========
col_log, col_trade = st.columns(2)

with col_log:
    st.subheader("📜 策略日志")

    logs = status['recent_logs']
    if logs:
        log_data = []
        for log in reversed(logs[-15:]):  # 最近15条
            action = log.get('action', '')
            icon = {
                'BUY': '📈',
                'SELL': '📉',
                'STOP_LOSS': '🛑',
                'TAKE_PROFIT': '🎯',
                'HOLD': '⏳',
                'ERROR': '❌',
                'STRATEGY_START': '🚀',
                'STRATEGY_STOP': '⏹️',
            }.get(action, '📋')

            timestamp = log.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp)
                    timestamp = dt.strftime('%m-%d %H:%M')
                except:
                    pass

            details = log.get('details', {})
            detail_str = ""
            if 'symbol' in details:
                detail_str = details['symbol']
            elif 'reason' in details:
                detail_str = details['reason'][:30]

            log_data.append({
                '时间': timestamp,
                '动作': f"{icon} {action}",
                '详情': detail_str,
            })

        df_logs = pd.DataFrame(log_data)
        st.dataframe(df_logs, use_container_width=True, hide_index=True, height=400)
    else:
        st.info("暂无日志。运行策略后这里会显示交易动作。")

with col_trade:
    st.subheader("📊 最近交易")

    try:
        trades = client.get_all_trades(limit=10)
        if trades:
            trades_data = []
            for trade in trades:
                trades_data.append({
                    '时间': datetime.fromtimestamp(trade['timestamp'] / 1000).strftime('%m-%d %H:%M'),
                    '交易对': trade['symbol'],
                    '方向': '🟢买' if trade['side'] == 'buy' else '🔴卖',
                    '价格': trade['price'],
                    '数量': trade['amount'],
                    '金额': trade['cost'],
                })

            df_trades = pd.DataFrame(trades_data)
            st.dataframe(
                df_trades.style.format({
                    '价格': '${:,.2f}',
                    '数量': '{:.6f}',
                    '金额': '${:,.2f}',
                }),
                use_container_width=True,
                hide_index=True,
                height=400,
            )
        else:
            st.info("暂无交易记录。")
    except Exception as e:
        st.warning(f"获取交易记录失败: {e}")

st.divider()

# ========== 第五行：快速交易 ==========
st.subheader("⚡ 手动交易")

col_trade1, col_trade2, col_trade3 = st.columns([1, 1, 2])

with col_trade1:
    trade_symbol = st.selectbox(
        "交易对",
        options=client.whitelist,
    )

with col_trade2:
    trade_usdt = st.number_input(
        "金额 (USDT)",
        min_value=5.0,
        max_value=50.0,
        value=10.0,
        step=5.0,
    )

with col_trade3:
    st.write("")
    st.write("")
    col_buy, col_sell = st.columns(2)

    with col_buy:
        if st.button("📈 市价买入", use_container_width=True, type="primary"):
            try:
                order = client.create_market_buy_usdt(trade_symbol, trade_usdt)
                st.success(f"✅ 买入成功! 订单ID: {order['id']}")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 买入失败: {e}")

    with col_sell:
        # 获取当前持仓
        currency = trade_symbol.split('/')[0]
        if currency in balance and balance[currency]['free'] > 0:
            sell_amount = balance[currency]['free']
            if st.button(f"📉 卖出全部 ({sell_amount:.6f})", use_container_width=True):
                try:
                    order = client.create_market_sell(trade_symbol, sell_amount)
                    st.success(f"✅ 卖出成功! 订单ID: {order['id']}")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 卖出失败: {e}")
        else:
            st.button("📉 无持仓", use_container_width=True, disabled=True)

# 底部信息
st.divider()
snapshots = load_snapshots()
st.caption(f"📊 已记录 {len(snapshots)} 条资产快照 | 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
