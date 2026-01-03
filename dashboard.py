import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Cipher Luxury Journal", layout="wide", page_icon="🛡️")

# Estilo CSS "Cipher Luxury"
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

# --- CONEXÃO GOOGLE SHEETS (SEGRETA) ---
def connect_to_gsheets():
    # Define o escopo de autorização
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # Carrega as credenciais dos "Segredos" da Streamlit Cloud
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    
    # Autoriza e abre a folha
    client = gspread.authorize(credentials)
    # ATENÇÃO: O nome aqui tem de ser IGUAL ao nome da sua folha no Google Drive
    return client.open("Cipher_Trading_Database").sheet1

def carregar_dados():
    try:
        sheet = connect_to_gsheets()
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=[
                "Data", "Symbol", "Direção", "Entrada", "Stop Loss", 
                "Target", "Risco($)", "Size($)", "Leverage", 
                "Saída", "PnL($)", "Status"
            ])
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erro ao conectar à Base de Dados: {e}")
        return pd.DataFrame()

def salvar_sincronizacao(df):
    try:
        sheet = connect_to_gsheets()
        # Método Brutal: Limpa a folha e escreve tudo de novo (Mais seguro para evitar erros de linha)
        sheet.clear()
        # Prepara os cabeçalhos e dados
        sheet.update([df.columns.values.tolist()] + df.values.tolist())
        return True
    except Exception as e:
        st.error(f"Erro ao gravar: {e}")
        return False

# --- INTERFACE ---
st.title("🛡️ Cipher Luxury: Cloud Command Center")

# Abas
tab1, tab2, tab3 = st.tabs(["⚡ Nova Operação", "📋 Gestão de Carteira", "📈 Analytics"])

# --- ABA 1: NOVA OPERAÇÃO ---
with tab1:
    col_input, col_metrics = st.columns([1, 2])
    
    with col_input:
        st.subheader("Radar de Mercado")
        symbol = st.text_input("Ativo", value="BTC/USDT").upper()
        direcao = st.radio("Direção", ["LONG 🟢", "SHORT 🔴"], horizontal=True)
        
        capital_total = st.number_input("Capital Banca ($)", value=1500.0, step=100.0) 
        risco_fixo = st.number_input("Risco Máximo ($)", value=60.0, step=10.0) 
        
        preco_entrada = st.number_input("Preço Entrada", value=0.0, format="%.2f")
        stop_loss = st.number_input("Preço Stop Loss", value=0.0, format="%.2f")

    if preco_entrada > 0 and stop_loss > 0 and preco_entrada != stop_loss:
        distancia_stop = abs(preco_entrada - stop_loss)
        distancia_pct = distancia_stop / preco_entrada
        tamanho_posicao = risco_fixo / distancia_pct
        alavancagem = tamanho_posicao / capital_total
        
        is_long = "LONG" in direcao
        take_profit = preco_entrada + (distancia_stop * 3) if is_long else preco_entrada - (distancia_stop * 3)

        with col_metrics:
            st.subheader("Análise Pré-Trade")
            m1, m2, m3 = st.columns(3)
            m1.metric("Alavancagem", f"{alavancagem:.1f}x")
            m2.metric("Posição Total", f"${tamanho_posicao:,.0f}")
            m3.metric("Potencial Lucro", f"${risco_fixo * 3:,.0f}")
            st.info(f"🎯 **Alvo:** ${take_profit:,.2f}")
            
            if st.button("REGISTAR TRADE NA NUVEM", type="primary"):
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
                
                if salvar_sincronizacao(df_novo):
                    st.success("Operação gravada na Google Sheet com sucesso!")
                    st.rerun()

# --- ABA 2: GESTÃO DE CARTEIRA ---
with tab2:
    st.subheader("Livro de Ordens (Sincronizado com Google Sheets)")
    df = carregar_dados()
    
    if not df.empty:
        df_editado = st.data_editor(
            df,
            column_config={
                "Saída": st.column_config.NumberColumn("Preço Saída", help="Preço de fecho"),
                "Status": st.column_config.SelectboxColumn("Estado", options=["ABERTO", "FECHADO", "CANCELADO"]),
                "PnL($)": st.column_config.NumberColumn("Lucro/Prejuízo", format="$%.2f")
            },
            disabled=["Data", "Symbol", "Direção", "Entrada"],
            num_rows="dynamic",
            use_container_width=True
        )

        if st.button("💾 SINCRONIZAR ALTERAÇÕES"):
            # Recalcular PnL antes de gravar
            for index, row in df_editado.iterrows():
                if row["Status"] == "FECHADO" and row["Saída"] > 0:
                    entrada = float(row["Entrada"])
                    saida = float(row["Saída"])
                    size = float(row["Size($)"])
                    if row["Direção"] == "LONG":
                        pnl = ((saida - entrada) / entrada) * size
                    else: 
                        pnl = ((entrada - saida) / entrada) * size
                    df_editado.at[index, "PnL($)"] = round(pnl, 2)
            
            if salvar_sincronizacao(df_editado):
                st.success("Base de dados atualizada.")
                st.rerun()
    else:
        st.info("A conectar à base de dados...")

# --- ABA 3: ANALYTICS ---
with tab3:
    st.header("📈 War Room")
    df = carregar_dados()
    if not df.empty:
        df_closed = df[df["Status"] == "FECHADO"].copy()
        if not df_closed.empty:
            total_pnl = df_closed["PnL($)"].sum()
            win_rate = (len(df_closed[df_closed["PnL($)"] > 0]) / len(df_closed)) * 100
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Net Profit", f"${total_pnl:,.2f}", delta=total_pnl)
            k2.metric("Win Rate", f"{win_rate:.1f}%")
            k3.metric("Trades Fechadas", len(df_closed))
            
            df_closed["Equity"] = df_closed["PnL($)"].cumsum()
            fig = px.line(df_closed, x="Data", y="Equity", title="Crescimento de Capital")
            fig.update_traces(line_color='#00CC96', line_width=3)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Feche trades para ver estatísticas.")