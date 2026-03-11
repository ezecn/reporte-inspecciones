import streamlit as st
import pandas as pd
import json

# --- FUNCIONES DE LÓGICA ---

def limpiar_y_cargar_json(texto):
    if pd.isna(texto) or str(texto).strip() == "" or str(texto).strip() == "[]":
        return []
    # Limpiamos las dobles comillas que vienen de Oracle
    texto_limpio = str(texto).replace('""', '"')
    try:
        return json.loads(texto_limpio)
    except:
        return "ERROR_FORMATO"

def procesar_inspeccion(actas_list):
    if actas_list == "ERROR_FORMATO":
        return {"modalidad_final": "ERROR JSON", "validaciones": ["Cadena corrupta"], "total": 0}
    
    res = {
        "total": len(actas_list),
        "ZGA1": 0, "ZGA2": 0, "ZGA3": 0, "ZGA4": 0,
        "signals": set(),
        "data_actas": [],
        "validaciones": []
    }

    for i, acta in enumerate(actas_list):
        tipo = acta.get("gochu_tipo_acta", "S/D")
        nro = str(acta.get("gochu_nro_acta", ""))
        largo = len(nro)
        
        modalidad_acta = "DESCONOCIDO"
        val = "OK"

        if tipo == "ZGA1":
            res["ZGA1"] += 1
            if nro.startswith("400") and largo == 9: modalidad_acta = "PAPEL"
            elif not nro.startswith("400") and largo == 9: modalidad_acta = "DIGITAL"
            else: val = f"ZGA1-{largo} dígitos (Raro)"
            
        elif tipo == "ZGA2":
            res["ZGA2"] += 1
            if largo == 6: modalidad_acta = "PAPEL"
            elif largo == 9: modalidad_acta = "DIGITAL"
            else: val = f"ZGA2-{largo} dígitos (Raro)"
            
        elif tipo == "ZGA3":
            res["ZGA3"] += 1
            modalidad_acta = "PAPEL"
            if largo != 3: val = f"ZGA3-{largo} dígitos (Raro)"

        elif tipo == "ZGA4":
            res["ZGA4"] += 1
            modalidad_acta = "PAPEL"
            if largo != 5: val = f"ZGA4-{largo} dígitos (Raro)"

        res["signals"].add(modalidad_acta)
        res["data_actas"].append((tipo, nro))
        if val != "OK":
            res["validaciones"].append(val)

    # Lógica de Modalidad General
    if "PAPEL" in res["signals"] and "DIGITAL" in res["signals"]:
        res["modalidad_final"] = "CONFLICTO - REVISAR"
    elif "PAPEL" in res["signals"]:
        res["modalidad_final"] = "PAPEL"
    elif "DIGITAL" in res["signals"]:
        res["modalidad_final"] = "DIGITAL"
    else:
        res["modalidad_final"] = "SIN ACTAS / INDETERMINADO"

    return res

# --- INTERFAZ DE USUARIO ---

st.set_page_config(page_title="Procesador de Inspecciones", layout="wide")
st.title("📋 Procesador de Reportes de Inspección")
st.markdown("Sube el CSV de Oracle para limpiar las actas y determinar la modalidad automáticamente.")

archivo = st.file_uploader("Subir archivo CSV", type=["csv"])

if archivo:
    # 1. Lectura robusta del archivo
    try:
        # Intentamos con UTF-8 primero
        df = pd.read_csv(archivo, sep=None, engine='python', encoding='utf-8')
    except UnicodeDecodeError:
        # Si falla, vamos con Latin-1 (común en Oracle/Windows)
        archivo.seek(0)
        df = pd.read_csv(archivo, sep=None, engine='python', encoding='latin-1')

    st.success(f"Archivo cargado: {len(df)} filas encontradas.")
    
    # 2. Selección de columnas
    col1, col2 = st.columns(2)
    with col1:
        col_id = st.selectbox("Columna de ID (Visita/Inspección):", df.columns)
    with col2:
        col_json = st.selectbox("Columna con las Actas (JSON):", df.columns)

    # 3. Procesamiento
    if st.button("🚀 Procesar Reporte"):
        resultados = []
        
        progress_bar = st.progress(0)
        for index, row in df.iterrows():
            # Actualizar barra de progreso cada 100 filas
            if index % 100 == 0:
                progress_bar.progress(index / len(df))
            
            lista_actas = limpiar_y_cargar_json(row[col_json])
            info = procesar_inspeccion(lista_actas)
            
            # Construir fila
            fila = {
                "id_visita": row[col_id],
                "total_actas": info["total"],
                "cant_circunstanciadas": info.get("ZGA3", 0),
                "cant_comprobacion": info.get("ZGA1", 0),
                "cant_intimacion": info.get("ZGA2", 0),
                "cant_secuestro": info.get("ZGA4", 0),
            }
            
            # Columnas de Actas (Max 4)
            actas_extraidas = info.get("data_actas", [])
            for i in range(1, 5):
                if i <= len(actas_extraidas):
                    fila[f"tipo_acta_{i}"] = actas_extraidas[i-1][0]
                    fila[f"numero_acta_{i}"] = actas_extraidas[i-1][1]
                else:
                    fila[f"tipo_acta_{i}"] = ""
                    fila[f"numero_acta_{i}"] = ""
            
            fila["MODALIDAD"] = info["modalidad_final"]
            fila["ALERTAS_LONGITUD"] = " | ".join(info["validaciones"])
            resultados.append(fila)

        progress_bar.progress(100)
        df_final = pd.DataFrame(resultados)
        
        st.subheader("Vista Previa del Resultado")
        st.dataframe(df_final.head(10))

        # 4. Descarga
        csv_data = df_final.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="📥 Descargar Reporte para Excel",
            data=csv_data,
            file_name="reporte_inspecciones_limpio.csv",
            mime="text/csv"
        )