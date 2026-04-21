import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

# Configuración de la página
st.set_page_config(page_title="Fuel Analysis Pro", layout="wide")

st.title("FUEL CONSUMPTION ANALYZER ⛽")
st.markdown("Smart tool to calculate the HP fuel consumption per stage and totalizer")
st.markdown("HOW TO USE IT:")
st.markdown("1. Download the CSV data from Intelie, make sure you include ALL THE PUMPS.")
st.markdown("2. Upload your CSV file and choose your analysis type, threshold, and gauge max limit")
st.markdown("3. The previous parameters can be modified at any time and the changes will take effect inmediately.")
st.markdown("---")

# --- BARRA LATERAL (Controles) ---
st.sidebar.header("Visualization settings")
uploaded_file = st.sidebar.file_uploader("1. Upload your CSV file", type=["csv"])
mode = st.sidebar.selectbox("2. Analysis type", ["Per stage (Blocks)", "Per minute"])
threshold = st.sidebar.number_input("Stage threshold (L/h)", value=3500)
gauge_max = st.sidebar.number_input("Gauge Max Limit (Liters)", value=100000)
plot_button = st.sidebar.button("Plot it!")

st.sidebar.markdown("---")
st.sidebar.markdown("**Powered by: Jose Gramcko**")


# --- FUNCIONES DE PROCESAMIENTO ---
@st.cache_data
def process_data(file):
    GAL_TO_L = 3.78541
    df_raw = pd.read_csv(file, low_memory=False)
    df_raw = df_raw[df_raw['timestamp'].astype(str).str.contains('-')].copy()
    df_raw['timestamp'] = pd.to_datetime(df_raw['timestamp'], errors='coerce')
    df_raw = df_raw.dropna(subset=['timestamp']).sort_values('timestamp')

    pump_cols = [col for col in df_raw.columns if 'consumption_rate' in col and '|UOM' not in col]
    pumps_numeric = df_raw[pump_cols].apply(pd.to_numeric, errors='coerce').fillna(0)

    df = pd.DataFrame({
        'timestamp': df_raw['timestamp'],
        'Total_L_h': pumps_numeric.sum(axis=1) * GAL_TO_L
    }).reset_index(drop=True)

    # Cálculo de volumen por fila
    df['Time_Diff_H'] = df['timestamp'].diff().dt.total_seconds().fillna(0) / 3600.0
    df['Volume_L'] = df['Total_L_h'] * df['Time_Diff_H']

    return df


# --- LÓGICA PRINCIPAL ---
if uploaded_file is not None and plot_button:
    df = process_data(uploaded_file)
    total_volume = df['Volume_L'].sum()

    # 1. FIGURA DE GRÁFICAS DE TIEMPO (2 filas)
    fig_time = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=("Instant fuel consumption (L/h)", "Fuel volume consumed (L)")
    )

    # Gráfica Superior: Flujo
    fig_time.add_trace(
        go.Scatter(x=df['timestamp'], y=df['Total_L_h'], name='Flow (L/h)',
                   line=dict(color='firebrick', width=1.5), fill='tozeroy'),
        row=1, col=1
    )

    # Gráfica Inferior: Volumen (Barras)
    if mode == "Per minute":
        resampled = df.set_index('timestamp')['Total_L_h'].resample('1min').mean().to_frame()
        resampled['Volume_L'] = resampled['Total_L_h'] / 60.0
        resampled['Color'] = resampled['Total_L_h'].apply(lambda x: 'firebrick' if x > threshold else 'lightgrey')
        fig_time.add_trace(go.Bar(x=resampled.index, y=resampled['Volume_L'], marker_color=resampled['Color']), row=2,
                           col=1)
        y_title = "Liters per minute"
    else:
        df['Is_Stage'] = df['Total_L_h'] > threshold
        df['Block_ID'] = (df['Is_Stage'] != df['Is_Stage'].shift()).cumsum()
        blocks = df.groupby('Block_ID').agg(
            Start_Time=('timestamp', 'first'), End_Time=('timestamp', 'last'),
            Type=('Is_Stage', 'first'), Total_Volume_L=('Volume_L', 'sum')
        ).reset_index()
        blocks['Mid_Time'] = blocks['Start_Time'] + (blocks['End_Time'] - blocks['Start_Time']) / 2
        blocks['Width_MS'] = (blocks['End_Time'] - blocks['Start_Time']).dt.total_seconds() * 1000
        blocks['Color'] = np.where(blocks['Type'], 'firebrick', 'lightgrey')
        fig_time.add_trace(go.Bar(x=blocks['Mid_Time'], y=blocks['Total_Volume_L'], width=blocks['Width_MS'],
                                  marker_color=blocks['Color'], text=blocks['Total_Volume_L'].round(0),
                                  textposition='auto'), row=2, col=1)
        y_title = "Total Liters per block"

    fig_time.update_layout(height=600, template='plotly_white', showlegend=False)
    fig_time.update_yaxes(title_text="L/h", row=1, col=1)
    fig_time.update_yaxes(title_text=y_title, row=2, col=1)

    # Mostrar gráficas de tiempo
    st.plotly_chart(fig_time, use_container_width=True)

    # 2. FIGURA DEL TOTALIZADOR (GAUGE) POR SEPARADO
    st.markdown("---")
    st.subheader("Totalizer Summary")

    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=total_volume,
        number={'suffix': " L", 'valueformat': '.2s', 'font': {'size': 60}},
        gauge={
            'axis': {'range': [None, gauge_max], 'tickformat': '.2s'},
            'bar': {'color': "firebrick"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, gauge_max * 0.7], 'color': "lightgrey"},
                {'range': [gauge_max * 0.7, gauge_max], 'color': "darkgrey"}
            ],
            'threshold': {
                'line': {'color': "black", 'width': 4},
                'thickness': 0.75,
                'value': total_volume
            }
        }
    ))

    fig_gauge.update_layout(height=400, margin=dict(t=50, b=10, l=50, r=50))
    st.plotly_chart(fig_gauge, use_container_width=True)

    # --- EXPORTACIÓN ---
    st.subheader("📥 Export results")
    # Para el HTML, podemos combinar ambas figuras si lo deseas, o exportar la principal
    html_string = fig_time.to_html(include_plotlyjs='cdn') + fig_gauge.to_html(include_plotlyjs='cdn')
    st.download_button(label="Download report as .html", data=html_string,
                       file_name="fuel_analysis_report.html", mime="text/html")

    col1, col2 = st.columns(2)
    with col2:
        st.info(
            "💡 **PDF Tip:** For professional quality, click the camera icon (📷) on the chart menu to download a high-res PNG, or press **Ctrl + P** and 'Save as PDF'.")

elif uploaded_file is None:
    st.info("👈 Please upload a telemetry CSV file in the sidebar to start the analysis.")