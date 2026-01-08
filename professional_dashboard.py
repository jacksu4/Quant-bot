"""
专业级量化交易Dashboard

功能：
1. 实时监控策略性能
2. 风险指标可视化
3. 持仓分析
4. 交易历史
5. 多因子得分展示
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import json
import os

# 导入策略模块
try:
    from professional_strategy import ProfessionalStrategy
    from risk_manager import RiskManager
    from multi_factor_engine import MultiFactorEngine
    from exchange import BinanceClient
except ImportError as e:
    st.error(f"模块导入失败: {e}")
    st.stop()


# 页面配置
st.set_page_config(
    page_title="专业级量化交易系统",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 标题
st.title("📈 专业级量化交易系统")
st.markdown("---")


@st.cache_resource
def get_client():
    """获取交易所客户端（缓存）"""
    return BinanceClient()


@st.cache_resource
def get_strategy():
    """获取策略实例（缓存）"""
    return ProfessionalStrategy()


def load_equity_history():
    """加载权益历史"""
    history_file = 'data/equity_history.json'
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r') as f:
                return json.load(f)
        except:
            return []
    return []


def plot_equity_curve(history):
    """绘制权益曲线"""
    if not history:
        st.info("暂无历史数据")
        return

    df = pd.DataFrame(history)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['total_value'],
        mode='lines',
        name='总资产',
        line=dict(color='#00D9FF', width=2),
        fill='tozeroy',
        fillcolor='rgba(0, 217, 255, 0.1)'
    ))

    # 添加初始资金线
    initial_value = df['total_value'].iloc[0] if len(df) > 0 else 10000
    fig.add_hline(y=initial_value, line_dash="dash", line_color="gray",
                  annotation_text="初始资金")

    fig.update_layout(
        title="权益曲线",
        xaxis_title="时间",
        yaxis_title="资产价值 (USDT)",
        hovermode='x unified',
        template='plotly_dark'
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_factor_scores(scores_dict):
    """绘制因子得分雷达图"""
    symbols = list(scores_dict.keys())[:5]  # 只显示前5个
    if not symbols:
        return

    factors = ['Momentum', 'SharpeRatio', 'RelativeStrength', 'Liquidity', 'MeanReversion', 'Technical']

    fig = go.Figure()

    for symbol in symbols:
        scores = scores_dict[symbol]
        values = [scores.get(f, 0) for f in factors]

        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=factors,
            name=symbol,
            fill='toself'
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[-3, 3])
        ),
        showlegend=True,
        title="多因子得分对比"
    )

    st.plotly_chart(fig, use_container_width=True)


# 侧边栏
with st.sidebar:
    st.header("⚙️ 控制面板")

    # 运行策略按钮
    if st.button("🚀 运行策略", use_container_width=True):
        with st.spinner("策略运行中..."):
            try:
                strategy = get_strategy()
                strategy.run_once()
                st.success("✅ 策略运行完成！")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 策略运行失败: {e}")

    st.markdown("---")

    # 刷新按钮
    if st.button("🔄 刷新数据", use_container_width=True):
        st.cache_resource.clear()
        st.rerun()

    st.markdown("---")

    # 系统信息
    st.subheader("系统信息")
    client = get_client()
    st.write(f"**模式**: {client.get_mode_str()}")
    st.write(f"**时间**: {datetime.now().strftime('%H:%M:%S')}")


# 主要内容
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 概览", "💼 持仓", "📈 策略", "⚠️ 风险", "📜 历史"])

# Tab 1: 概览
with tab1:
    st.header("系统概览")

    try:
        client = get_client()
        balance = client.get_balance()
        total_value = client.calculate_total_value_usdt()
        usdt_free = client.get_usdt_balance()
        positions = client.get_all_positions()

        # KPI指标
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("总资产", f"${total_value:.2f}")

        with col2:
            st.metric("USDT余额", f"${usdt_free:.2f}")

        with col3:
            st.metric("持仓数量", len(positions))

        with col4:
            crypto_ratio = (total_value - usdt_free) / total_value * 100 if total_value > 0 else 0
            st.metric("加密货币占比", f"{crypto_ratio:.1f}%")

        st.markdown("---")

        # 权益曲线
        col_left, col_right = st.columns([2, 1])

        with col_left:
            history = load_equity_history()
            plot_equity_curve(history)

        with col_right:
            st.subheader("账户余额")

            if balance:
                for currency, info in balance.items():
                    with st.expander(f"{currency}: {info['total']:.6f}"):
                        st.write(f"可用: {info['free']:.6f}")
                        st.write(f"冻结: {info['used']:.6f}")
            else:
                st.info("无余额数据")

    except Exception as e:
        st.error(f"加载数据失败: {e}")


# Tab 2: 持仓
with tab2:
    st.header("当前持仓")

    try:
        client = get_client()
        positions = client.get_all_positions()

        if positions:
            # 持仓表格
            pos_data = []
            for pos in positions:
                pos_data.append({
                    '币种': pos['symbol'],
                    '数量': f"{pos['amount']:.6f}",
                    '成本': f"${pos['avg_price']:.2f}",
                    '当前价': f"${pos['current_price']:.2f}",
                    '市值': f"${pos['current_value']:.2f}",
                    '盈亏': f"${pos['pnl']:.2f}",
                    '盈亏率': f"{pos['pnl_percent']:+.2f}%",
                })

            df = pd.DataFrame(pos_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # 持仓饼图
            st.subheader("持仓分布")

            fig = go.Figure(data=[go.Pie(
                labels=[p['symbol'] for p in positions],
                values=[p['current_value'] for p in positions],
                hole=.3
            )])

            fig.update_layout(
                title="持仓市值分布",
                template='plotly_dark'
            )

            st.plotly_chart(fig, use_container_width=True)

        else:
            st.info("当前无持仓")

    except Exception as e:
        st.error(f"加载持仓失败: {e}")


# Tab 3: 策略
with tab3:
    st.header("策略分析")

    try:
        strategy = get_strategy()
        multi_factor = strategy.multi_factor

        # 运行多因子选币
        with st.spinner("计算多因子得分..."):
            selected = multi_factor.select_coins(top_n=5)

        if selected:
            st.subheader("多因子选币结果")

            # 选币表格
            coin_data = []
            for symbol, score, factors in selected:
                coin_data.append({
                    '币种': symbol,
                    '总分': f"{score:.2f}",
                    '动量': f"{factors.get('Momentum', 0):.2f}",
                    '夏普': f"{factors.get('SharpeRatio', 0):.2f}",
                    '相对强度': f"{factors.get('RelativeStrength', 0):.2f}",
                    '流动性': f"{factors.get('Liquidity', 0):.2f}",
                })

            df_coins = pd.DataFrame(coin_data)
            st.dataframe(df_coins, use_container_width=True, hide_index=True)

            # 因子得分雷达图
            st.subheader("因子得分可视化")
            scores_dict = {symbol: factors for symbol, _, factors in selected}
            plot_factor_scores(scores_dict)

            # 建议权重
            st.subheader("建议权重")
            weights = multi_factor.calculate_optimal_weights(selected)

            weight_data = []
            for symbol, weight in weights.items():
                weight_data.append({
                    '币种': symbol,
                    '权重': f"{weight*100:.1f}%",
                    '建议金额': f"${weight * client.calculate_total_value_usdt():.2f}"
                })

            df_weights = pd.DataFrame(weight_data)
            st.dataframe(df_weights, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"策略分析失败: {e}")


# Tab 4: 风险
with tab4:
    st.header("风险管理")

    try:
        risk_manager = RiskManager(client)

        # 生成风险报告
        report = risk_manager.generate_risk_report()

        if report:
            # 风险等级
            risk_level = report.get('risk_level', 'NORMAL')
            risk_colors = {
                'NORMAL': 'green',
                'CAUTIOUS': 'orange',
                'DEFENSIVE': 'red'
            }

            st.markdown(f"### 风险等级: :{risk_colors.get(risk_level, 'gray')}[{risk_level}]")

            # 风险指标
            col1, col2, col3 = st.columns(3)

            with col1:
                current_dd = report.get('current_drawdown', 0) * 100
                dd_color = 'red' if current_dd > 10 else 'orange' if current_dd > 5 else 'green'
                st.metric("当前回撤", f"{current_dd:.2f}%", delta=None)

            with col2:
                sharpe = report.get('sharpe_ratio', 0)
                st.metric("夏普比率", f"{sharpe:.2f}")

            with col3:
                var_99 = report.get('var_99', 0) * 100
                st.metric("VaR (99%)", f"{var_99:.2f}%")

            st.markdown("---")

            # 详细指标
            col_a, col_b = st.columns(2)

            with col_a:
                st.subheader("回撤指标")
                st.write(f"当前回撤: {report.get('current_drawdown', 0)*100:.2f}%")
                st.write(f"历史最大回撤: {report.get('max_drawdown', 0)*100:.2f}%")
                st.write(f"回撤限制: 15.00%")

            with col_b:
                st.subheader("收益指标")
                st.write(f"当日盈亏: {report.get('daily_pnl', 0)*100:+.2f}%")
                st.write(f"索提诺比率: {report.get('sortino_ratio', 0):.2f}")
                st.write(f"卡尔玛比率: {report.get('max_drawdown', 0) / report.get('annualized_return', 1) if report.get('annualized_return', 0) != 0 else 0:.2f}")

            # 仓位调整建议
            st.markdown("---")
            st.subheader("仓位调整")

            position_multiplier = risk_manager.get_position_size_multiplier()
            st.progress(position_multiplier)
            st.write(f"建议仓位: {position_multiplier * 100:.0f}%")

    except Exception as e:
        st.error(f"风险分析失败: {e}")


# Tab 5: 历史
with tab5:
    st.header("交易历史")

    try:
        # 加载策略日志
        log_file = 'data/professional_strategy_log.json'
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                logs = json.load(f)

            if logs:
                st.write(f"共 {len(logs)} 条记录")

                # 显示最近20条
                recent_logs = logs[-20:]
                for log in reversed(recent_logs):
                    timestamp = log.get('timestamp', 'N/A')
                    action = log.get('action', 'N/A')
                    details = log.get('details', {})

                    with st.expander(f"{timestamp} - {action}"):
                        st.json(details)
            else:
                st.info("暂无历史记录")
        else:
            st.info("日志文件不存在")

    except Exception as e:
        st.error(f"加载历史失败: {e}")


# 底部信息
st.markdown("---")
st.caption("🤖 专业级量化交易系统 | Powered by Claude Code")
