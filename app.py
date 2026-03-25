import streamlit as st
import pandas as pd
import json

# --- FUNCIONES DE LÓGICA (SE MANTIENEN IGUAL) ---

def limpiar_y_cargar_json(texto):
    if pd.isna(texto) or str(texto).strip() == "" or str(texto).strip() == "[]":
        return []
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
            else: val = f"ZGA1-{largo} dígitos"
            
        elif tipo == "ZGA2":
            res["ZGA2"] += 1
            if largo == 6: modalidad_acta = "PAPEL"
            elif largo == 9: modalidad_acta = "DIGITAL"
            else: val = f"ZGA2-{largo} dígitos"
            
        elif tipo == "ZGA3":
            res["ZGA3"] += 1
            modalidad_acta = "PAPEL"
            if largo != 3: val = f"ZGA3-{largo} dígitos"

        elif tipo == "ZGA4":
            res["ZGA4"] += 1
            modalidad_acta = "PAPEL"
            if largo != 5: val = f"ZGA4-{largo} dígitos"

        res["signals"].add(modalidad_acta)
        res["data_actas"].append((tipo, nro))
        if val != "OK":
            res["validaciones"].append(val)

    if "PAPEL" in res["signals"] and "DIGITAL" in res["signals"]:
        res["modalidad_final"] = "CONFLICTO - REVISAR"
    elif "PAPEL" in res["signals"]:
        res["modalidad_final"] = "PAPEL"
    elif "DIGITAL" in res["signals"]:
        res["modalidad_final"] = "DIGITAL"
    else:
        res["modalidad_final"] = "SIN ACTAS / INDETERMINADO"

    return res

# --- NUEVA FUNCIÓN PARA EL INFORME DETALLADO ---

def transformar_a_fila_por_acta(df_procesado):
    filas_individuales = []
    for _, row in df_procesado.iterrows():
        # Buscamos en las columnas tipo_acta_1 hasta tipo_acta_4
        for i in range(1, 5):
            t_col = f'tipo_acta_{i}'
            n_col = f'numero_acta_{i}'
            if pd.notna(row[t_col]) and str(row[t_col]).strip() != "":
                filas_individuales.append({
                    'id_visita': row['id_visita'],
                    'MODALIDAD': row['MODALIDAD'],
                    'tipo_acta': row[t_col],
                    'numero_acta': row[n_col]
                })
    return pd.DataFrame(filas_individuales)

# --- INTERFAZ DE USUARIO ---

st.set_page_config(page_title="Procesador de Inspecciones", layout="wide")
st.title("📋 Procesador de Reportes de Inspección")

archivo = st.file_uploader("Subir archivo CSV", type=["csv"])

if archivo:
    try:
        df = pd.read_csv(archivo, sep=None, engine='python', encoding='utf-8')
    except UnicodeDecodeError:
        archivo.seek(0)
        df = pd.read_csv(archivo, sep=None, engine='python', encoding='latin-1')

    st.success(f"Archivo cargado: {len(df)} filas.")
    
    col1, col2 = st.columns(2)
    with col1:
        col_id = st.selectbox("Columna de ID:", df.columns)
    with col2:
        col_json = st.selectbox("Columna con las Actas (JSON):", df.columns)

    if st.button("🚀 Procesar Reporte"):
        resultados = []
        progress_bar = st.progress(0)
        
        for index, row in df.iterrows():
            if index % 100 == 0:
                progress_bar.progress(index / len(df))
            
            lista_actas = limpiar_y_cargar_json(row[col_json])
            info = procesar_inspeccion(lista_actas)
            
            fila = {
                "id_visita": row[col_id],
                "total_actas": info["total"],
                "cant_circunstanciadas": info.get("ZGA3", 0),
                "cant_comprobacion": info.get("ZGA1", 0),
                "cant_intimacion": info.get("ZGA2", 0),
                "cant_secuestro": info.get("ZGA4", 0),
            }
            
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
        
        # --- SECCIÓN DE DESCARGAS ---
        st.divider()
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("1. Reporte Estándar")
            st.write("Una fila por inspección (formato original).")
            csv_std = df_final.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button("📥 Descargar Estándar", csv_std, "reporte_estandar.csv", "text/csv")
            st.dataframe(df_final.head(5))

        with c2:
            st.subheader("2. Informe por Acta")
            st.write("Una fila por cada acta (para Tablas Dinámicas).")
            df_detallado = transformar_a_fila_por_acta(df_final)
            csv_det = df_detallado.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button("📥 Descargar Detallado", csv_det, "informe_detallado.csv", "text/csv")
            st.dataframe(df_detallado.head(5))