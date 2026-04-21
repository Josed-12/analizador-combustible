import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from io import BytesIO

# Configuración de la página
st.set_page_config(page_title="Fuel Analysis Pro", layout="wide")

st.title("⛽ Professional fuel consumption analyzer | HP pumps")
st.markdown("Please upload your telemetry CSV file to process the pump data")
st.markdown("Powered by: Jose Gramcko")

# --- BARRA LATERAL (Controles) ---
st.sidebar.header("Visualization settings")
uploaded_file = st.sidebar.file_uploader("1. Upload your CSV file", type=["csv"])
mode = st.sidebar.selectbox("2. Analysis type", ["Per stage (Blocks)", "Per minute"])
threshold = st.sidebar.number_input("Stage threshold (L/h)", value=3500)
plot_button = st.sidebar.button("Plot it!")


# --- FUNCIONES DE PROCESAMIENTO ---
def process_data(file):
    GAL_TO_L = 3.78541
    df_raw = pd.read_csv(file, low_memory=False)
    # Limpiar metadatos y fechas
    df_raw = df_raw[df_raw['timestamp'] != 'Asia/Riyadh'].copy()
    df_raw['timestamp'] = pd.to_datetime(df_raw['timestamp'], errors='coerce')
    df_raw = df_raw.dropna(subset=['timestamp']).sort_values('timestamp')

    # Identificar bombas y calcular total
    pump_cols = [col for col in df_raw.columns if 'consumption_rate' in col and '|UOM' not in col]
    pumps_numeric = df_raw[pump_cols].apply(pd.to_numeric, errors='coerce').fillna(0)

    df = pd.DataFrame({
        'timestamp': df_raw['timestamp'],
        'Total_L_h': pumps_numeric.sum(axis=1) * GAL_TO_L
    })
    return df


# --- LÓGICA PRINCIPAL ---
if uploaded_file is not None and plot_button:
    df = process_data(uploaded_file)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                        subplot_titles=("Instant fuel consumption (L/h)", "Fuel volume consumed (L)"))

    # Gráfica Superior (Siempre flujo continuo)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['Total_L_h'], name='Flujo L/h',
                             line=dict(color='firebrick', width=1.5), fill='tozeroy'), row=1, col=1)

    if mode == "Per minute":
        # Lógica Minuto a Minuto
        resampled = df.set_index('timestamp')['Total_L_h'].resample('1min').mean().to_frame()
        resampled['Volume_L'] = resampled['Total_L_h'] / 60.0
        resampled['Color'] = resampled['Total_L_h'].apply(lambda x: 'firebrick' if x > threshold else 'lightgrey')

        fig.add_trace(go.Bar(x=resampled.index, y=resampled['Volume_L'], marker_color=resampled['Color'],
                             name='Litros/Min'), row=2, col=1)
        y_title = "Liters per minute"

    else:
        # Lógica Por Stage (Bloques)
        df['Is_Stage'] = df['Total_L_h'] > threshold
        df['Block_ID'] = (df['Is_Stage'] != df['Is_Stage'].shift()).cumsum()
        df['Time_Diff_H'] = df['timestamp'].diff().dt.total_seconds().fillna(0) / 3600.0
        df['Volume_L'] = df['Total_L_h'] * df['Time_Diff_H']

        blocks = df.groupby('Block_ID').agg(
            Start_Time=('timestamp', 'first'), End_Time=('timestamp', 'last'),
            Type=('Is_Stage', 'first'), Total_Volume_L=('Volume_L', 'sum')
        ).reset_index()

        blocks['Mid_Time'] = blocks['Start_Time'] + (blocks['End_Time'] - blocks['Start_Time']) / 2
        blocks['Width_MS'] = (blocks['End_Time'] - blocks['Start_Time']).dt.total_seconds() * 1000
        blocks['Color'] = np.where(blocks['Type'], 'firebrick', 'lightgrey')

        fig.add_trace(go.Bar(x=blocks['Mid_Time'], y=blocks['Total_Volume_L'], width=blocks['Width_MS'],
                             marker_color=blocks['Color'], text=blocks['Total_Volume_L'].round(0),
                             textposition='auto', name='Total Litros'), row=2, col=1)
        y_title = "Total volume consumed per stage/idle"

    # Estética del Gráfico
    fig.update_layout(height=700, template='plotly_white', showlegend=False)
    fig.update_yaxes(title_text="L/h", row=1, col=1)
    fig.update_yaxes(title_text=y_title, row=2, col=1)

    # Mostrar en la App
    st.plotly_chart(fig, use_container_width=True)

    # --- DESCARGAS CORREGIDAS ---
    st.subheader("📥 Export results")
    col1, col2 = st.columns(2)

    # 1. Generar el HTML como texto directamente
    html_string = fig.to_html(include_plotlyjs='cdn')

    # 2. Botón de descarga de HTML
    col1.download_button(
        label="Download as dynamic .html file",
        data=html_string,
        file_name="fuel_analysis.html",
        mime="text/html"
    )

    # 3. Opción de PDF simplificada
    with col2:
        st.info(
            "💡 **PDF Tip: For professional quality, click the camera icon (📷) above the chart to download it as an image, or press Ctrl + P on your keyboard and select 'Save as PDF'.")