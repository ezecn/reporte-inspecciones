import streamlit as st
import pandas as pd
import json
import re

def limpiar_json(texto):
    # Elimina las comillas dobles repetidas que vienen del CSV de Oracle
    if pd.isna(texto) or texto == "": return []
    texto_limpio = texto.replace('""', '"')
    try:
        return json.loads(texto_limpio)
    except:
        return "ERROR_FORMATO"

def procesar_inspeccion(actas_list):
    if actas_list == "ERROR_FORMATO":
        return {"modalidad": "ERROR JSON", "validaciones": ["Cadena corrupta"]}
    
    res = {
        "total": len(actas_list),
        "ZGA1": 0, "ZGA2": 0, "ZGA3": 0, "ZGA4": 0,
        "signals": set(),
        "data_actas": [],
        "validaciones": []
    }

    for i, acta in enumerate(actas_list):
        tipo = acta.get("gochu_tipo_acta", "")
        nro = str(acta.get("gochu_nro_acta", ""))
        largo = len(nro)
        
        # Conteo y Clasificación de Modalidad
        modalidad_acta = "DESCONOCIDO"
        validacion_acta = "OK"

        if tipo == "ZGA1":
            res["ZGA1"] += 1
            if nro.startswith("400") and largo == 9: modalidad_acta = "PAPEL"
            elif not nro.startswith("400") and largo == 9: modalidad_acta = "DIGITAL"
            else: validacion_acta = "REVISAR LONGITUD"
            
        elif tipo == "ZGA2":
            res["ZGA2"] += 1
            if largo == 6: modalidad_acta = "PAPEL"
            elif largo == 9: modalidad_acta = "DIGITAL"
            else: validacion_acta = "REVISAR LONGITUD"
            
        elif tipo == "ZGA3":
            res["ZGA3"] += 1
            modalidad_acta = "PAPEL"
            if largo != 3: validacion_acta = "REVISAR LONGITUD"

        elif tipo == "ZGA4":
            res["ZGA4"] += 1
            modalidad_acta = "PAPEL"
            if largo != 5: validacion_acta = "REVISAR LONGITUD"

        res["signals"].add(modalidad_acta)
        res["data_actas"].append((tipo, nro))
        res["validaciones"].append(f"Acta {i+1}: {validacion_acta}")

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

# --- INTERFAZ DE STREAMLIT ---
st.title("🚀 Procesador de Inspecciones - Oracle a Excel")

archivo = st.file_uploader("Sube tu archivo .csv exportado de Oracle", type=["csv"])

if archivo:
try:
        # Primero intentamos con el estándar moderno
        df = pd.read_csv(archivo, sep=None, engine='python', encoding='utf-8')
    except UnicodeDecodeError:
        # Si falla, probamos con el estándar de Excel/Windows en español
        archivo.seek(0) # Volvemos al inicio del archivo para reintentar
        df = pd.read_csv(archivo, sep=None, engine='python', encoding='latin-1')

    # El parámetro sep=None + engine='python' hace que Pandas detecte 
    # solo si usas coma o punto y coma.
    
    st.success("¡Archivo cargado con éxito!")
    
    # El resto del código sigue igual...
    col_json = st.selectbox("Selecciona la columna que tiene las actas (JSON)", df.columns)
    # ...

    if st.button("Procesar Datos"):
        resultados = []
        for index, row in df.iterrows():
            datos_actas = limpiar_json(row[col_json])
            info = procesar_inspeccion(datos_actas)
            
            # Construir fila para el Excel
            fila = {
                "id_visita": row[col_id],
                "total_actas": info.get("total", 0),
                "cant_ZGA3_circunstanciada": info.get("ZGA3", 0),
                "cant_ZGA1_comprobacion": info.get("ZGA1", 0),
                "cant_ZGA2_intimacion": info.get("ZGA2", 0),
                "cant_ZGA4_secuestro": info.get("ZGA4", 0),
            }
            
            # Columnas Dinámicas (hasta 4 actas)
            actas_extraidas = info.get("data_actas", [])
            for i in range(1, 5):
                if i <= len(actas_extraidas):
                    fila[f"tipo_acta_{i}"] = actas_extraidas[i-1][0]
                    fila[f"numero_acta_{i}"] = actas_extraidas[i-1][1]
                else:
                    fila[f"tipo_acta_{i}"] = ""
                    fila[f"numero_acta_{i}"] = ""
            
            fila["MODALIDAD"] = info.get("modalidad_final")
            fila["VALIDACIONES"] = " | ".join(info.get("validaciones", []))
            resultados.append(fila)

        df_final = pd.DataFrame(resultados)
        st.dataframe(df_final.head())
        
        # Botón de Descarga
        @st.cache_data
        def convert_df(df):
            return df.to_csv(index=False).encode('utf-8-sig')

        csv_download = convert_df(df_final)
        st.download_button("📥 Descargar Reporte en CSV (Abrir en Excel)", data=csv_download, file_name="reporte_procesado.csv")