import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import yfinance as yf

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Cipher Luxury Journal", layout="wide", page_icon="🛡️")

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

# --- CONEXÃO GOOGLE SHEETS ---
def connect_to_gsheets():
    try:
        # Tenta conectar via Streamlit Cloud Secrets (Prioridade)
        if "gcp_service_account" in st.secrets:
            credentials = Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            )
            return gspread.authorize(credentials).open("Cipher_Trading_Database").sheet1
        
        # Tenta conectar via Ficheiro Local (Fallback para PC)
        else:
            # Procura o ficheiro na pasta .streamlit local
            import toml
            with open(".streamlit/secrets.toml", "r") as f:
                secrets = toml.load(f)
            credentials = Credentials.from_service_account_info(
                secrets["gcp_service_account"],
                scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            )
            return gspread.authorize(credentials).open("Cipher_Trading_Database").sheet1

    except Exception as e:
        return None

def carregar_dados():
    sheet = connect_to_gsheets()
    if sheet:
        data = sheet.get_all_records()
        if not data:
             return pd.DataFrame(columns=["Data", "Symbol", "Direção", "Entrada", "Stop Loss", "Target", "Risco($)", "Size($)", "Leverage", "Saída", "PnL($)", "Status"])
        return pd.DataFrame(data)
    return pd.DataFrame()

def salvar_sincronizacao(df):
    sheet = connect_to_gsheets()
    if sheet:
        sheet.clear()
        sheet.update([df.columns.values.tolist()] + df.values.tolist())
        return True
    return False

# --- FUNÇÃO DE DADOS DE MERCADO (O NOVO MOTOR) ---
def obter_preco_atual(ticker_input):
    ticker = ticker_input.upper().strip()
    
    # Dicionário inteligente para "traduzir" o que você escreve
    mapa_ativos = {
        "BTC": "BTC-USD",
        "ETH": "ETH-USD",
        "SOL": "SOL-USD",
        "XRP": "XRP-USD",
        "GOLD": "GC=F",   # Ouro Futuros
        "OURO": "GC=F",
        "SILVER": "SI=F", # Prata Futuros
        "PRATA": "SI=F",
        "SP500": "^GSPC",
        "NASDAQ": "^IXIC"
    }
    
    # Se estiver no mapa, usa o código oficial, senão tenta adicionar -USD (ex: ADA -> ADA-USD)
    simbolo_final = mapa_ativos.get(ticker, ticker)
    if simbolo_final not in mapa_ativos.values() and "-" not in simbolo_final and "=" not in simbolo_final:
        # Assume que é cripto se não tiver hífen
        simbolo_final = f"{simbolo_final}-USD"
        
    try:
        ativo = yf.Ticker(simbolo_final)
        # Tenta pegar o histórico recente (mais rápido)
        hist = ativo.history(period="1d")
        if not hist.empty:
            preco = hist['Close'].iloc[-1]
            return preco, simbolo_final
    except:
        return 0.0, ticker
        
    return 0.0, ticker

# --- INTERFACE ---
st.title("🛡️ Cipher Luxury: Cloud Command Center")

tab1, tab2, tab3 = st.tabs(["⚡ Nova Operação", "📋 Gestão de Carteira", "📈 Analytics"])

# --- ABA 1: NOVA OPERAÇÃO ---
with tab1:
    col_input, col_metrics = st.columns([1, 2])
    
    with col_input:
        st.subheader("Radar de Mercado")
        
        # O Input de Texto agora controla o preço
        symbol_input = st.text_input("Ativo (Escreva BTC, GOLD, XRP...)", value="BTC")
        
        # BUSCA AUTOMÁTICA DE PREÇO
        preco_live, simbolo_oficial = obter_preco_atual(symbol_input)
        
        if preco_live > 0:
            st.caption(f"✅ Preço em Tempo Real ({simbolo_oficial}): **${preco_live:,.2f}**")
        else:
            st.caption("⚠️ Preço não encontrado (Verifique a internet ou o símbolo)")

        direcao = st.radio("Direção", ["LONG 🟢", "SHORT 🔴"], horizontal=True)
        capital_total = st.number_input("Capital Banca ($)", value=1500.0, step=100.0) 
        risco_fixo = st.number_input("Risco Máximo ($)", value=60.0, step=10.0) 
        
        # O valor padrão do input agora é o preço live (se existir)
        val_entrada = float(preco_live) if preco_live > 0 else 0.0
        preco_entrada = st.number_input("Preço Entrada", value=val_entrada, format="%.2f")
        
        stop_loss = st.number_input("Preço Stop Loss", value=0.0, format="%.2f")

    # LÓGICA DE CÁLCULO
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
            
            st.info(f"🎯 **Alvo (1:3):** ${take_profit:,.2f}")
            
            # Botão de Registo
            if st.button("REGISTAR TRADE", type="primary"):
                novo_registo = {
                    "Data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Symbol": simbolo_oficial, # Usa o símbolo oficial (ex: BTC-USD)
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
                    st.success(f"Ordem de {simbolo_oficial} registada com sucesso!")
                    st.balloons() # Efeito visual de luxo
                    st.rerun()

# --- ABA 2: GESTÃO DE CARTEIRA ---
with tab2:
    st.subheader("Livro de Ordens Ativo")
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

        if st.button("💾 SINCRONIZAR"):
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
                st.success("Atualizado.")
                st.rerun()

# --- ABA 3: ANALYTICS ---
with tab3:
    st.header("📈 War Room")
    df = carregar_dados()
    if not df.empty:
        df_closed = df[df["Status"] == "FECHADO"].copy()
        if not df_closed.empty:
            total_pnl = df_closed["PnL($)"].sum()
            # Tratamento de erro para divisão por zero
            win_rate = 0
            if len(df_closed) > 0:
                win_rate = (len(df_closed[df_closed["PnL($)"] > 0]) / len(df_closed)) * 100
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Net Profit", f"${total_pnl:,.2f}", delta=total_pnl)
            k2.metric("Win Rate", f"{win_rate:.1f}%")
            k3.metric("Trades Fechadas", len(df_closed))
            
            df_closed["Equity"] = df_closed["PnL($)"].cumsum()
            fig = px.line(df_closed, x="Data", y="Equity", title="Crescimento de Capital")
            fig.update_traces(line_color='#00CC96', line_width=3)
            st.plotly_chart(fig, use_container_width=True)
            
            # Gráfico de Tarte Atualizado
            fig_pie = px.pie(df_closed, names="Symbol", values="Size($)", title="Exposição por Ativo", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)