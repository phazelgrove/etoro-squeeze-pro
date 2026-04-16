import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go

st.set_page_config(page_title="eToro TTM Squeeze Pro", layout="wide", initial_sidebar_state="expanded")

# Dark Terminal Theme
st.markdown("""
<style>
    .stApp {background-color: #0a0e14; color: #c0c5d0;}
    h1, h2, h3 {color: #00ff9d;}
    .stButton>button {background: linear-gradient(135deg, #1565c0, #00d47a); color: white;}
    .stDataFrame {background-color: #11171f;}
</style>
""", unsafe_allow_html=True)

st.title("🟢 eToro TTM Squeeze Pro Terminal")
st.caption("John Carter Pro Filters • Highest Probability Breakouts")

def add_indicators(df):
    df = df.copy()
    close = df['Close']
    high = df['High']
    low = df['Low']
    vol = df['Volume']

    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    df['BB_Width'] = (bb_std * 2) / bb_mid

    atr = (high - low).rolling(20).mean() * 1.5
    kc_mid = close.rolling(20).mean()
    df['KC_Width'] = (atr * 1.5) / kc_mid
    df['Squeeze'] = (df['BB_Width'] < df['KC_Width'])

    df['Momentum'] = close - bb_mid
    df['Volume_Ratio'] = vol / vol.rolling(20).mean()

    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    tr = pd.concat([high-low, abs(high-close.shift()), abs(low-close.shift())], axis=1).max(axis=1)
    dm_plus = (high - high.shift()).where(lambda x: x > 0, 0)
    dm_minus = (low.shift() - low).where(lambda x: x > 0, 0)
    di_plus = 100 * (dm_plus.rolling(14).mean() / tr.rolling(14).mean())
    di_minus = 100 * (dm_minus.rolling(14).mean() / tr.rolling(14).mean())
    df['ADX'] = (abs(di_plus - di_minus) / (di_plus + di_minus) * 100).rolling(14).mean()

    df['EMA8'] = close.ewm(span=8).mean()
    df['EMA21'] = close.ewm(span=21).mean()

    return df

def run_pro_scan():
    with st.spinner("Scanning eToro stocks with Pro Filters..."):
        try:
            instruments = pd.read_json("https://api.etorostatic.com/sapi/instrumentsmetadata/V1.1/instruments")
            stocks = instruments[instruments['InstrumentTypeID'].str.lower() == 'stock'][['Symbol', 'Name']].head(600)
        except:
            st.error("Could not load eToro list")
            return pd.DataFrame()

        results = []
        progress = st.progress(0)

        for i, row in stocks.iterrows():
            try:
                data = yf.download(row['Symbol'], period="1y", progress=False, threads=False)
                if len(data) < 120:
                    progress.progress(int((i+1)/len(stocks)*100))
                    continue

                data = add_indicators(data)
                recent = data.iloc[-10:]

                consec = int(recent['Squeeze'].sum())
                if consec < 5:
                    progress.progress(int((i+1)/len(stocks)*100))
                    continue

                tight = data['BB_Width'].iloc[-1] < data['BB_Width'].rolling(60).quantile(0.25)
                vol_ok = data['Volume_Ratio'].iloc[-1] > 1.6
                adx_ok = data['ADX'].iloc[-1] > 22
                rsi_ok = 42 < data['RSI'].iloc[-1] < 58
                ema_ok = data['Close'].iloc[-1] > data['EMA21'].iloc[-1] and data['EMA8'].iloc[-1] > data['EMA21'].iloc[-1]

                if not (tight and vol_ok and adx_ok and rsi_ok and ema_ok):
                    progress.progress(int((i+1)/len(stocks)*100))
                    continue

                score = round(40 * (consec/10) + 25 * (1 if tight else 0) + 20 * min(data['Volume_Ratio'].iloc[-1], 5) + 15 * min(data['ADX'].iloc[-1]/50, 1), 1)

                results.append({
                    'Ticker': row['Symbol'],
                    'Name': row['Name'],
                    'Score': score,
                    'Conviction': '🔥 HIGH' if score > 78 else '✅ MED' if score > 60 else 'LOW',
                    'Consec Days': consec,
                    'Expected Move %': round(data['BB_Width'].iloc[-1] * 160, 1),
                    'Price': round(data['Close'].iloc[-1], 2)
                })
            except:
                pass
            progress.progress(int((i+1)/len(stocks)*100))

        progress.empty()
        return pd.DataFrame(results).sort_values('Score', ascending=False)

if st.button("🚀 Run Pro Scan Now", type="primary", use_container_width=True):
    st.session_state.results = run_pro_scan()

if 'results' in st.session_state and not st.session_state.results.empty:
    st.dataframe(st.session_state.results, use_container_width=True, hide_index=True)

    ticker = st.selectbox("Select Ticker to View Chart", st.session_state.results['Ticker'])
    if ticker:
        data = yf.download(ticker, period="6mo")
        fig = go.Figure(data=[go.Candlestick(x=data.index, open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'])])
        fig.update_layout(height=600)
        st.plotly_chart(fig, use_container_width=True)

st.sidebar.success("✅ App Ready")
st.sidebar.info("Tap the button above to scan")
