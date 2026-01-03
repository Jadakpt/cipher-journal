import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Cipher Luxury Journal", layout="wide", page_icon="🛡️")

# Estilo CSS para garantir o visual "Dark & Gold" da Cipher
st.markdown("""
<style>
    .stMetric {
        background-color: #1E1E1E;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #333;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        color: #FFFFFF;
    }
</style>
""", unsafe_allow_html=True)

ARQUIVO_DADOS = "trading_log.csv"

# --- MOTOR DE DADOS ---
def carregar_dados():
    if not os.path.exists(ARQUIVO_DADOS):
        df = pd.DataFrame(columns=[
            "Data", "Symbol", "Direção", "Entrada", "Stop Loss", 
            "Target", "Risco($)", "Size($)", "Leverage", 
            "Saída", "PnL($)", "Status"
        ])
        return df
    return pd.read_csv(ARQUIVO_DADOS)

def salvar_dados(df):
    df.to_csv(ARQUIVO_DADOS, index=False)

# --- INTERFACE ---
st.title("🛡️ Cipher Luxury: Trading Command Center")

# Criamos 3 abas agora: Operacional | Carteira | Analytics
tab1, tab2, tab3 = st.tabs(["⚡ Nova Operação", "📋 Gestão de Carteira", "📈 Analytics (War Room)"])

# --- ABA 1: NOVA OPERAÇÃO ---
with tab1:
    col_input, col_metrics = st.columns([1, 2])
    
    with col_input:
        st.subheader("Radar de Mercado")
        symbol = st.text_input("Ativo", value="BTC/USDT").upper()
        direcao = st.radio("Direção", ["LONG 🟢", "SHORT 🔴"], horizontal=True)
        
        capital_total = st.number_input("Capital Banca ($)", value=1500.0, step=100.0) # Atualizado para o seu valor
        risco_fixo = st.number_input("Risco Máximo ($)", value=60.0, step=10.0) # Atualizado para o seu valor
        
        preco_entrada = st.number_input("Preço Entrada", value=0.0, format="%.2f")
        stop_loss = st.number_input("Preço Stop Loss", value=0.0, format="%.2f")

    if preco_entrada > 0 and stop_loss > 0 and preco_entrada != stop_loss:
        distancia_stop = abs(preco_entrada - stop_loss)
        distancia_pct = distancia_stop / preco_entrada
        
        tamanho_posicao = risco_fixo / distancia_pct
        alavancagem = tamanho_posicao / capital_total
        
        is_long = "LONG" in direcao
        if is_long:
            take_profit = preco_entrada + (distancia_stop * 3)
        else:
            take_profit = preco_entrada - (distancia_stop * 3)

        with col_metrics:
            st.subheader("Análise Pré-Trade")
            m1, m2, m3 = st.columns(3)
            m1.metric("Alavancagem", f"{alavancagem:.1f}x")
            m2.metric("Posição Total", f"${tamanho_posicao:,.0f}")
            m3.metric("Potencial Lucro (3R)", f"${risco_fixo * 3:,.0f}")
            
            st.info(f"🎯 **Alvo Técnico:** ${take_profit:,.2f}")
            
            if st.button("REGISTAR TRADE", type="primary"):
                novo_registo = {
                    "Data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Symbol": symbol,
                    "Direção": "LONG" if is_long else "SHORT",
                    "Entrada": preco_entrada,
                    "Stop Loss": stop_loss,
                    "Target": round(take_profit, 2),
                    "Risco($)": risco_fixo,
                    "Size($)": round(tamanho_posicao, 2),
                    "Leverage": round(alavancagem, 1),
                    "Saída": 0.0,
                    "PnL($)": 0.0,
                    "Status": "ABERTO"
                }
                df_atual = carregar_dados()
                df_novo = pd.concat([df_atual, pd.DataFrame([novo_registo])], ignore_index=True)
                salvar_dados(df_novo)
                st.success("Ordem registada.")
                st.rerun()

# --- ABA 2: GESTÃO DE CARTEIRA ---
with tab2:
    st.subheader("Livro de Ordens Ativo")
    df = carregar_dados()
    
    if not df.empty:
        df_editado = st.data_editor(
            df,
            column_config={
                "Saída": st.column_config.NumberColumn("Preço Saída ($)", help="Preço de fecho"),
                "Status": st.column_config.SelectboxColumn("Estado", options=["ABERTO", "FECHADO", "CANCELADO"]),
                "PnL($)": st.column_config.NumberColumn("Lucro/Prejuízo", format="$%.2f")
            },
            disabled=["Data", "Symbol", "Direção", "Entrada", "Risco($)"],
            num_rows="dynamic",
            use_container_width=True
        )

        if st.button("💾 ATUALIZAR RESULTADOS"):
            for index, row in df_editado.iterrows():
                if row["Status"] == "FECHADO" and row["Saída"] > 0:
                    entrada = row["Entrada"]
                    saida = row["Saída"]
                    size = row["Size($)"]
                    
                    if row["Direção"] == "LONG":
                        pnl = ((saida - entrada) / entrada) * size
                    else: 
                        pnl = ((entrada - saida) / entrada) * size
                    
                    df_editado.at[index, "PnL($)"] = round(pnl, 2)
            
            salvar_dados(df_editado)
            st.success("Base de dados sincronizada.")
            st.rerun()
    else:
        st.info("Sem dados.")

# --- ABA 3: ANALYTICS (NOVO) ---
with tab3:
    st.header("📈 Performance Analytics")
    
    df = carregar_dados()
    # Filtrar apenas trades fechadas para estatísticas
    df_closed = df[df["Status"] == "FECHADO"].copy()
    
    if not df_closed.empty:
        # Cálculos de KPI
        total_trades = len(df_closed)
        total_pnl = df_closed["PnL($)"].sum()
        trades_win = df_closed[df_closed["PnL($)"] > 0]
        trades_loss = df_closed[df_closed["PnL($)"] <= 0]
        
        win_rate = (len(trades_win) / total_trades) * 100
        
        # Dashboard de KPIs
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Net Profit", f"${total_pnl:,.2f}", delta=total_pnl)
        kpi2.metric("Win Rate", f"{win_rate:.1f}%")
        kpi3.metric("Trades Vencedoras", len(trades_win))
        kpi4.metric("Trades Perdedoras", len(trades_loss))
        
        st.markdown("---")
        
        # GRÁFICO 1: Curva de Equity (Crescimento da Conta)
        # Cria uma coluna de acumulado
        df_closed["Equity"] = df_closed["PnL($)"].cumsum()
        
        fig_equity = px.line(df_closed, x="Data", y="Equity", title="Curva de Crescimento de Capital", markers=True)
        fig_equity.update_traces(line_color='#00CC96', line_width=3)
        st.plotly_chart(fig_equity, use_container_width=True)
        
        # GRÁFICO 2: Distribuição de Resultados
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            # Gráfico de Barras (Ganhos vs Perdas)
            fig_bar = px.bar(df_closed, x="Data", y="PnL($)", color="PnL($)", 
                             title="Resultado por Trade",
                             color_continuous_scale=["#FF4B4B", "#00CC96"])
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with col_g2:
            # Pie Chart de Ativos
            fig_pie = px.pie(df_closed, names="Symbol", values="Size($)", title="Exposição por Ativo")
            st.plotly_chart(fig_pie, use_container_width=True)

    else:
        st.warning("Precisa de fechar pelo menos uma operação (Status: FECHADO) para ver as análises.")