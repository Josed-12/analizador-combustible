# ⛽ Fuel Consumption Analyzer

Aplicación web interactiva para análisis de consumo de combustible a partir de datos de telemetría.

🔗 **Live App:** [https://TU-APP.streamlit.app](https://TU-APP.streamlit.app) _(actualizar después del deploy)_

---

## 📋 Características

- 📂 Carga de archivos **CSV** o **ZIP**
- 🔄 Soporte para **Litros (L/h)** y **Galones (gal/h)**
- 📊 **4 modos de análisis**:
  - Per stage (Blocks)
  - Per minute
  - Consumption per pump
  - HP Consumption/Performance
- 🎛️ Filtros personalizados de bombas
- 📈 Gráficos interactivos con Plotly
- 📥 Exportación de reporte HTML

---

## 🚀 Uso

1. Abre la aplicación en el link de arriba
2. Sube tu archivo CSV o ZIP de telemetría
3. Selecciona el modo de análisis
4. Ajusta umbrales según necesidad
5. Clic en **"Plot it!"**

---

## 🛠️ Ejecutar localmente

```bash
git clone https://github.com/TU-USUARIO/fuel-consumption-analyzer.git
cd fuel-consumption-analyzer
pip install -r requirements.txt
streamlit run app.py
```

---

## 📦 Tecnologías

- **Streamlit** — Interfaz web
- **Pandas / NumPy** — Procesamiento de datos
- **Plotly** — Visualizaciones interactivas

---

**Powered by: Jose Gramcko**
