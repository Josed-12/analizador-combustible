import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from io import BytesIO

# Configuración de la página
st.set_page_config(page_title="Fuel Analysis Pro", layout="wide")

st.title("⛽ Analizador Profesional de Consumo de Combustible")
st.markdown("Sube tu archivo CSV de telemetría para procesar los datos de las bombas.")

# --- BARRA LATERAL (Controles) ---
st.sidebar.header("Configuración de Visualización")
uploaded_file = st.sidebar.file_uploader("1. Sube tu archivo CSV", type=["csv"])
mode = st.sidebar.selectbox("2. Tipo de Análisis", ["Por Stage (Bloques Completos)", "Minuto a Minuto"])
threshold = st.sidebar.number_input("Umbral de Stage (L/h)", value=3500)
plot_button = st.sidebar.button("¡Graficar ahora! (Plot it!)")


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
                        subplot_titles=("Tasa de Consumo Instantánea (L/h)", "Análisis Acumulado"))

    # Gráfica Superior (Siempre flujo continuo)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['Total_L_h'], name='Flujo L/h',
                             line=dict(color='firebrick', width=1.5), fill='tozeroy'), row=1, col=1)

    if mode == "Minuto a Minuto":
        # Lógica Minuto a Minuto
        resampled = df.set_index('timestamp')['Total_L_h'].resample('1min').mean().to_frame()
        resampled['Volume_L'] = resampled['Total_L_h'] / 60.0
        resampled['Color'] = resampled['Total_L_h'].apply(lambda x: 'firebrick' if x > threshold else 'lightgrey')

        fig.add_trace(go.Bar(x=resampled.index, y=resampled['Volume_L'], marker_color=resampled['Color'],
                             name='Litros/Min'), row=2, col=1)
        y_title = "Litros por Minuto"

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
        y_title = "Litros Totales del Evento"

    # Estética del Gráfico
    fig.update_layout(height=700, template='plotly_white', showlegend=False)
    fig.update_yaxes(title_text="L/h", row=1, col=1)
    fig.update_yaxes(title_text=y_title, row=2, col=1)

    # Mostrar en la App
    st.plotly_chart(fig, use_container_width=True)

    # --- DESCARGAS CORREGIDAS ---
    st.subheader("📥 Exportar Resultados")
    col1, col2 = st.columns(2)

    # 1. Generar el HTML como texto directamente
    html_string = fig.to_html(include_plotlyjs='cdn')

    # 2. Botón de descarga de HTML
    col1.download_button(
        label="Descargar como HTML interactivo",
        data=html_string,
        file_name="analisis_combustible.html",
        mime="text/html"
    )

    # 3. Opción de PDF simplificada
    with col2:
        st.info(
            "💡 **Tip para PDF:** Para una calidad profesional, haz clic en el icono de la cámara (📷) sobre la gráfica para bajarla como imagen, o presiona `Ctrl + P` en tu teclado y selecciona 'Guardar como PDF'.")