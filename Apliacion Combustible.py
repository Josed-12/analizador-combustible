import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import plotly.express as px

# Configuración de la página
st.set_page_config(page_title="Fuel Analysis Pro", layout="wide")

st.title("⛽ FUEL CONSUMPTION ANALYZER")
st.markdown("Please upload your telemetry CSV file to process the pump data")
st.markdown("---")

# --- BARRA LATERAL (Controles) ---
st.sidebar.header("Visualization settings")
uploaded_file = st.sidebar.file_uploader("1. Upload your CSV file", type=["csv"])

uom = st.sidebar.radio("2. Select Unit of Measure (UOM)", ["Liters (L/h)", "Gallons (gal/h)"], horizontal=True)
unit_label = "L" if "Liters" in uom else "gal"
rate_label = "L/h" if "Liters" in uom else "gal/h"
conversion_factor = 3.78541 if "Liters" in uom else 1.0

mode = st.sidebar.selectbox("3. Analysis type",
                            ["Per stage (Blocks)", "Per minute", "Consumption per pump", "HP Consumption/Performance"])

# --- LÓGICA DE SELECCIÓN DE BOMBAS ---
selected_pumps = "All"
if mode in ["Consumption per pump", "HP Consumption/Performance"] and uploaded_file is not None:
    @st.cache_data
    def get_pump_names(file):
        df_temp = pd.read_csv(file, nrows=1)
        cols = [col for col in df_temp.columns if 'consumption_rate' in col and '|UOM' not in col]
        return [col.split('|')[1] if '|' in col else col for col in cols]


    pump_labels = get_pump_names(uploaded_file)
    st.sidebar.markdown("---")
    filter_option = st.sidebar.radio("Pump Filter:", ["All pumps", "Custom selection"])
    if filter_option == "Custom selection":
        selected_pumps = st.sidebar.multiselect("Select Pump IDs:", options=pump_labels, default=pump_labels[:3])

threshold = st.sidebar.number_input(f"Stage threshold ({rate_label})", value=3500 if unit_label == "L" else 925)
gauge_max = st.sidebar.number_input(f"Gauge Max Limit ({unit_label})", value=100000 if unit_label == "L" else 26500)
plot_button = st.sidebar.button("Plot it!")

st.sidebar.markdown("---")
st.sidebar.markdown("**Powered by: Jose Gramcko**")


# --- FUNCIONES DE PROCESAMIENTO ---
@st.cache_data
def process_data(file, factor):
    df_raw = pd.read_csv(file, low_memory=False)
    df_raw = df_raw[df_raw['timestamp'].astype(str).str.contains('-')].copy()
    df_raw['timestamp'] = pd.to_datetime(df_raw['timestamp'], errors='coerce')
    df_raw = df_raw.dropna(subset=['timestamp']).sort_values('timestamp')

    pump_ids = [col.split('|')[1] for col in df_raw.columns if 'consumption_rate' in col and '|UOM' not in col]
    data_map = {'rate': {}, 'power': {}, 'load': {}}

    for pid in pump_ids:
        r_col = [c for c in df_raw.columns if pid in c and 'consumption_rate' in c and '|UOM' not in c][0]
        data_map['rate'][pid] = pd.to_numeric(df_raw[r_col], errors='coerce').fillna(0) * factor

        p_col_list = [c for c in df_raw.columns if pid in c and 'hyd_power' in c and '|UOM' not in c]
        if p_col_list:
            data_map['power'][pid] = pd.to_numeric(df_raw[p_col_list[0]], errors='coerce').fillna(0)

        l_col_list = [c for c in df_raw.columns if pid in c and 'load_percentage' in c and '|UOM' not in c]
        if l_col_list:
            data_map['load'][pid] = pd.to_numeric(df_raw[l_col_list[0]], errors='coerce').fillna(0)

    df = pd.DataFrame({'timestamp': df_raw['timestamp']})
    time_diff = df['timestamp'].diff().dt.total_seconds().fillna(0) / 3600.0

    # Pre-calcular volumen total
    all_rates = pd.DataFrame(data_map['rate'])
    df['Total_Rate'] = all_rates.sum(axis=1)
    df['Total_Vol'] = df['Total_Rate'] * time_diff

    step = max(1, len(df) // 2500)
    return df, data_map, time_diff, df.iloc[::step].copy(), step


def human_format(num, unit):
    if abs(num) < 1000: return f"{int(num)} {unit}"
    return f"{num / 1000:.1f}K {unit}"


# --- LÓGICA DE VISUALIZACIÓN ---
if uploaded_file is not None and plot_button:
    df, data_map, time_diff, df_plot, step = process_data(uploaded_file, conversion_factor)

    pumps_to_show = list(data_map['rate'].keys()) if selected_pumps == "All" else selected_pumps
    colors = px.colors.qualitative.Dark24 + px.colors.qualitative.Alphabet

    current_total_rate = sum([data_map['rate'][p] for p in pumps_to_show])
    current_volume = sum([(data_map['rate'][p] * time_diff).sum() for p in pumps_to_show])

    if mode == "HP Consumption/Performance":
        rows, row_heights = 4, [0.25, 0.25, 0.25, 0.25]
        titles = (f"Individual Rate ({rate_label})", f"Total Rate ({rate_label})", "Hydraulic Power (HP)",
                  "Load Percentage (%)")
        v_space = 0.04
    elif mode == "Consumption per pump":
        rows, row_heights = 3, [0.33, 0.33, 0.33]
        titles = (f"Pump Rate ({rate_label})", f"Total Rate ({rate_label})", f"Ranking ({unit_label})")
        v_space = 0.07
    else:
        rows, row_heights = 2, [0.5, 0.5]
        titles = (f"Total Rate ({rate_label})", f"Fuel consumed per stage/idle ({unit_label})")
        v_space = 0.1

    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True,
                        vertical_spacing=v_space,
                        row_heights=row_heights, subplot_titles=titles)

    if mode in ["Consumption per pump", "HP Consumption/Performance"]:
        for i, pid in enumerate(pumps_to_show):
            c = colors[i % len(colors)]
            fig.add_trace(go.Scatter(x=df_plot['timestamp'], y=data_map['rate'][pid].iloc[::step],
                                     name=pid, line=dict(width=1.5, color=c)), row=1, col=1)

            if mode == "HP Consumption/Performance":
                fig.add_trace(go.Scatter(x=df_plot['timestamp'], y=data_map['power'][pid].iloc[::step],
                                         name=f"{pid} Power", line=dict(width=1.5, color=c), showlegend=False), row=3,
                              col=1)
                fig.add_trace(go.Scatter(x=df_plot['timestamp'], y=data_map['load'][pid].iloc[::step],
                                         name=f"{pid} Load", line=dict(width=1.5, color=c), showlegend=False), row=4,
                              col=1)

    total_row = 2 if mode in ["Consumption per pump", "HP Consumption/Performance"] else 1
    fig.add_trace(go.Scatter(x=df_plot['timestamp'], y=current_total_rate.iloc[::step], name='Total',
                             line=dict(color='firebrick', width=2), fill='tozeroy'), row=total_row, col=1)

    if mode == "Per minute":
        resampled = pd.DataFrame({'r': current_total_rate, 't': df['timestamp']}).set_index('t').resample('1min').mean()
        fig.add_trace(go.Bar(x=resampled.index, y=resampled['r'] / 60, marker_color='firebrick'), row=2, col=1)

    elif mode == "Per stage (Blocks)":
        # 1. Identificación de bloques
        df['Is_S'] = current_total_rate > threshold
        df['BID'] = (df['Is_S'] != df['Is_S'].shift()).cumsum()
        df['Current_Vol'] = current_total_rate * time_diff
        # 2. Agrupación por bloque
        blocks = df.groupby('BID').agg(
            S=('timestamp', 'first'),
            E=('timestamp', 'last'),
            T=('Is_S', 'first'),
            V=('Current_Vol', 'sum')
        ).reset_index()
        # Calculamos la duración en minutos
        blocks['Duration_Min'] = (blocks['E'] - blocks['S']).dt.total_seconds() / 60
        # --- FILTRADO MÁS ESTRICTO PARA EL PROMEDIO ---
        # Subimos a 10 minutos para ignorar cualquier pico o prueba corta
        significant_stages = blocks[(blocks['T'] == True) & (blocks['Duration_Min'] > 10)]
        if not significant_stages.empty:
            avg_stage_vol = significant_stages['V'].mean()
            st.subheader(f"📊 Average fuel consumed per stage: {avg_stage_vol:,.1f} {unit_label}")
            st.caption(f"Note: Only stages longer than 10 minutes are included in this average.")
        else:
            # Si no hay etapas de >10 min, bajamos el criterio a 2 min para no mostrar 0
            backup_stages = blocks[(blocks['T'] == True) & (blocks['Duration_Min'] > 2)]
            avg_val = backup_stages['V'].mean() if not backup_stages.empty else 0
            st.subheader(f"📊 Average fuel consumed per stage: {avg_val:,.1f} {unit_label}")
        # ----------------------------------------------
        fig.add_trace(go.Bar(
            x=blocks['S'] + (blocks['E'] - blocks['S']) / 2,
            y=blocks['V'],
            width=(blocks['E'] - blocks['S']).dt.total_seconds() * 1000,
            marker_color=np.where(blocks['T'], 'firebrick', 'lightgrey'),
            text=blocks['V'].round(0),
            textposition='auto'
        ), row=2, col=1)

    elif mode == "Consumption per pump":
        ranking = pd.Series({pid: (data_map['rate'][pid] * time_diff).sum() for pid in pumps_to_show}).sort_values()
        fig.add_trace(go.Bar(y=ranking.index, x=ranking.values, orientation='h',
                             marker_color='firebrick', text=ranking.values.round(1), textposition='outside'), row=3,
                      col=1)

    fig.update_layout(height=rows * 250, template='plotly_white',
                      showlegend=True if "pump" in mode.lower() or "Performance" in mode else False)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    c1, c2 = st.columns([2, 1])
    with c1:
        fig_g = go.Figure(go.Indicator(mode="gauge+number", value=current_volume,
                                       number={'suffix': f" {unit_label}", 'valueformat': '.2s'},
                                       gauge={'axis': {'range': [None, gauge_max]}, 'bar': {'color': "firebrick"}}))
        fig_g.update_layout(height=280, margin=dict(t=40, b=10))
        st.plotly_chart(fig_g, use_container_width=True)
    with c2:
        st.metric(f"Total Volume ({unit_label})", human_format(current_volume, unit_label))
        st.metric("Pumps Displayed", len(pumps_to_show))

        if mode == "HP Consumption/Performance":
            all_loads_df = pd.concat([data_map['load'][p] for p in pumps_to_show], axis=1)
            avg_load_per_second = all_loads_df.mean(axis=1)
            active_load_values = avg_load_per_second[avg_load_per_second > 20]

            if not active_load_values.empty:
                avg_l = active_load_values.mean()
                st.metric("Avg Load (>20%)", f"{avg_l:.1f} %",
                          help="Average load calculated only when fleet load is > 20%.")
            else:
                st.metric("Avg Load (>20%)", "N/A")

    st.download_button(f"📥 Download HTML Report", fig.to_html(), f"report.html", "text/html")

elif uploaded_file is None:
    st.info("👈 Please upload a telemetry CSV file to start.")