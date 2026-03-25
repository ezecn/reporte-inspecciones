import streamlit as st
import pandas as pd
import json

# --- FUNCIONES DE LÓGICA ---

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
            else: val = f"ZGA1-{largo} dgt"
            
        elif tipo == "ZGA2":
            res["ZGA2"] += 1
            if largo == 6: modalidad_acta = "PAPEL"
            elif largo == 9: modalidad_acta = "DIGITAL"
            else: val = f"ZGA2-{largo} dgt"
            
        elif tipo == "ZGA3":
            res["ZGA3"] += 1
            modalidad_acta = "PAPEL"
            if largo != 3: val = f"ZGA3-{largo} dgt"

        elif tipo == "ZGA4":
            res["ZGA4"] += 1
            modalidad_acta = "PAPEL"
            if largo != 5: val = f"ZGA4-{largo} dgt"

        res["signals"].add(modalidad_acta)
        res["data_actas"].append((tipo, nro))
        if val != "OK":
            res["validaciones"].append(val)

    if "PAPEL" in res["signals"] and "DIGITAL" in res["signals"]:
        res["modalidad_final"] = "CONFLICTO"
    elif "PAPEL" in res["signals"]:
        res["modalidad_final"] = "PAPEL"
    elif "DIGITAL" in res["signals"]:
        res["modalidad_final"] = "DIGITAL"
    else:
        res["modalidad_final"] = "S/D"

    return res

def transformar_a_fila_por_acta(df_procesado):
    # Diccionario de traducción de códigos a nombres
    mapping_nombres = {
        "ZGA1": "Comprobación",
        "ZGA2": "Intimación",
        "ZGA3": "Circunstanciada",
        "ZGA4": "Secuestro"
    }
    
    filas_individuales = []
    for _, row in df_procesado.iterrows():
        for i in range(1, 5):
            t_col = f'tipo_acta_{i}'
            n_col = f'numero_acta_{i}'
            
            if t_col in df_procesado.columns and pd.notna(row[t_col]) and str(row[t_col]).strip() != "":
                codigo_original = str(row[t_col]).strip()
                # Traducimos el código. Si no está en el mapa, dejamos el original.
                nombre_acta = mapping_nombres.get(codigo_original, codigo_original)
                
                filas_individuales.append({
                    'numero_acta': row[n_col],
                    'tipo_acta': nombre_acta,
                    'MODALIDAD': row.get('MODALIDAD', 'S/D'),
                    'id_visita': row.get('id_visita', 'S/D')
                })
    
    nuevo_df = pd.DataFrame(filas_individuales)
    # Orden de columnas solicitado
    columnas_ordenadas = ['numero_acta', 'tipo_acta', 'MODALIDAD', 'id_visita']
    return nuevo_df[columnas_ordenadas] if not nuevo_df.empty else nuevo_df

# --- INTERFAZ ---

st.set_page_config(page_title="Herramientas de Inspección", layout="wide")
st.title("🛠️ Centro de Herramientas de Inspección")

tab1, tab2 = st.tabs(["1. Limpieza de Datos (Oracle)", "2. Generador de Informe (Final)"])

# --- TAB 1: PROCESADOR ---
with tab1:
    st.header("Módulo de Limpieza Original")
    st.info("Sube aquí el archivo .csv directo de Oracle.")
    
    archivo_sucio = st.file_uploader("Subir CSV de Oracle", type=["csv"], key="uploader_sucio")

    if archivo_sucio:
        try:
            df_sucio = pd.read_csv(archivo_sucio, sep=None, engine='python', encoding='utf-8')
        except UnicodeDecodeError:
            archivo_sucio.seek(0)
            df_sucio = pd.read_csv(archivo_sucio, sep=None, engine='python', encoding='latin-1')

        c1, c2 = st.columns(2)
        col_id = c1.selectbox("Columna ID:", df_sucio.columns, key="id_1")
        col_json = c2.selectbox("Columna Actas (JSON):", df_sucio.columns, key="json_1")

        if st.button("🚀 Limpiar Datos", key="btn_limpiar"):
            resultados = []
            for idx, row in df_sucio.iterrows():
                lista = limpiar_y_cargar_json(row[col_json])
                info = procesar_inspeccion(lista)
                fila = {
                    "id_visita": row[col_id],
                    "total_actas": info["total"],
                    "MODALIDAD": info["modalidad_final"],
                    "ALERTAS": " | ".join(info["validaciones"])
                }
                for i in range(1, 5):
                    if i <= len(info["data_actas"]):
                        fila[f"tipo_acta_{i}"] = info["data_actas"][i-1][0]
                        fila[f"numero_acta_{i}"] = info["data_actas"][i-1][1]
                    else:
                        fila[f"tipo_acta_{i}"], fila[f"numero_acta_{i}"] = "", ""
                resultados.append(fila)
            
            df_limpio = pd.DataFrame(resultados)
            st.dataframe(df_limpio.head())
            csv_limpio = df_limpio.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button("📥 Descargar para corregir errores", csv_limpio, "datos_para_revisar.csv", "text/csv")

# --- TAB 2: GENERADOR DE INFORME ---
with tab2:
    st.header("Generador de Informe por Acta")
    st.success("Sube aquí el archivo que ya corregiste manualmente.")
    
    archivo_corregido = st.file_uploader("Subir archivo corregido", type=["csv"], key="uploader_corregido")

    if archivo_corregido:
        try:
            df_corregido = pd.read_csv(archivo_corregido, sep=None, engine='python', encoding='utf-8')
        except UnicodeDecodeError:
            archivo_corregido.seek(0)
            df_corregido = pd.read_csv(archivo_corregido, sep=None, engine='python', encoding='latin-1')

        st.warning("Verifica que las columnas originales de actas (tipo_acta_1, etc.) no hayan sido renombradas.")
        
        if st.button("📊 Generar Informe Final", key="btn_informe"):
            df_final = transformar_a_fila_por_acta(df_corregido)
            
            if not df_final.empty:
                st.write(f"Se generaron {len(df_final)} filas con nombres de actas descriptivos.")
                st.dataframe(df_final.head(10))
                
                csv_final = df_final.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button("📥 Descargar Informe Detallado (Final)", csv_final, "informe_actas_final.csv", "text/csv")
            else:
                st.error("No se encontraron actas para procesar.")