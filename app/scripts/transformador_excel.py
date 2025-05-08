# services/transformador_excel.py
import pandas as pd
import re
import numpy as np
from io import BytesIO
from datetime import datetime



def transformar_excel(file_bytes: bytes, hoja: str):
    # Cargar el archivo Excel
    excel_file = pd.ExcelFile(BytesIO(file_bytes))
    
    # Verificar si la hoja existe
    if hoja not in excel_file.sheet_names:
        hojas_disponibles = ", \n".join(excel_file.sheet_names)  # Construir la lista de hojas con saltos de línea
        raise ValueError(f"La hoja '{hoja}' no existe en el archivo.\n\nHojas disponibles: \n{hojas_disponibles}")
    
    # Cargar la hoja especificada
    df = pd.read_excel(excel_file, sheet_name=hoja, header=None)
    
    # Número esperado de columnas
    NUM_COLUMNAS_ESPERADAS = 24

    # Verificar si faltan columnas
    num_columnas_actual = df.shape[1]
    if num_columnas_actual < NUM_COLUMNAS_ESPERADAS:
        # Agregar columnas vacías
        for i in range(num_columnas_actual, NUM_COLUMNAS_ESPERADAS):
            df[f"col_{i}"] = np.nan

    json_result = {
        "total_poa": {},
        "actividades": []
    }
    # Validar las columnas según el formato
    validar_columnas(df)


    fecha_headers = df.iloc[7, 11:23].tolist()

    current_actividad = None
    actividad_total = None
    actividad_actual_obj = None

    for i in range(7, len(df)):
        fila = df.iloc[i]
        texto_col3 = str(fila[3]) if not pd.isna(fila[3]) else ""

        if "TOTAL PRESUPUESTO" in texto_col3.upper():
            total_poa_val = fila[10]
            if pd.notna(total_poa_val) and float(total_poa_val) != 0:
                ejec = {}
                for idx, val in enumerate(fila[11:23]):
                    if pd.notna(val) and str(val).strip() not in ["", "0", "0.0", "0.00"]:
                        fecha = fecha_headers[idx]
                        ejec[str(fecha)] = float(val)
                json_result["total_poa"] = {
                    "descripcion": texto_col3.strip(),
                    "total": float(total_poa_val),
                    "programacion_ejecucion": ejec
                }
            break

        if re.match(r"\(\d+\)", texto_col3.strip()):
            actividad_total = fila[10]
            if pd.notna(actividad_total) and float(actividad_total) != 0:
                current_actividad = texto_col3.strip()
                actividad_actual_obj = {
                    "descripcion_actividad": current_actividad,
                    "total_por_actividad": float(actividad_total),
                    "tareas": []
                }
                json_result["actividades"].append(actividad_actual_obj)
            else:
                current_actividad = None
                actividad_actual_obj = None
            continue

        if current_actividad and actividad_actual_obj:
            nombre = fila[3]
            detalle = fila[4]
            item_presupuestario = fila[6]
            cantidad = fila[7]
            precio = fila[8]
            total = fila[9]

            if pd.isna(nombre) or pd.isna(total) or total == 0.0:
                continue

            try:
                total_val = float(total)
            except:
                continue

            programacion = {}
            for idx, val in enumerate(fila[11:23]):
                if pd.notna(val) and str(val).strip() != "" :
                    if es_numero(val):
                        fecha = fecha_headers[idx]
                        programacion[str(fecha)] = float(val)
                    else:
                        raise ValueError(f"No se guardo nada en la base de datos.\nError en la fila {i+1}: valor no válido en {chr(11 + idx + 65)}{i+1} (se esperaba un número).")

                        

            programacion["suman"] = float(fila[23]) if pd.notna(fila[23]) else 0.0

            tarea = {
                "nombre": str(nombre).strip(),
                "detalle_descripcion": str(detalle).strip() if pd.notna(detalle) else "",
                "item_presupuestario": str(item_presupuestario).strip() if pd.notna(item_presupuestario) else "",
                "cantidad": float(cantidad) if pd.notna(cantidad) else None,
                "precio_unitario": float(precio) if pd.notna(precio) else None,
                "total": float(total),
                "programacion_ejecucion": programacion
            }

            actividad_actual_obj["tareas"].append(tarea)

    return json_result

def es_numero(val):
    try:
        float(val)
        return True
    except ValueError:
        return False
    
def validar_columnas(df):
    errores = []

    # Validar [7,4] - DESCRIPCIÓN O DETALLE
    if str(df.iloc[7, 4]).strip().upper() != "DESCRIPCIÓN O DETALLE":
        errores.append("no se encontró 'DESCRIPCIÓN O DETALLE' en E8.")

    # # Validar [7,6] - ITEM PRESUPUESTARIO
    if str(df.iloc[7, 6]).strip().upper() != "ITEM PRESUPUESTARIO":
        errores.append("no se encontró 'ITEM PRESUPUESTARIO' en G8.")

    # Validar [7,7] - CANTIDAD
    if not str(df.iloc[7, 7]).strip().upper().startswith("CANTIDAD"):
        errores.append("no se encontró 'CANTIDAD (Meses de contrato)' en H8.")

    # Validar [7,8] - PRECIO UNITARIO
    if str(df.iloc[7, 8]).strip().upper() != "PRECIO UNITARIO":
        errores.append("no se encontró 'PRECIO UNITARIO' en I8.")

    # Validar [7,9] - TOTAL
    if str(df.iloc[7, 9]).strip().upper() != "TOTAL":
        errores.append("no se encontró 'TOTAL' en J8.")

    # Validar [6,10] - TOTAL POR ACTIVIDAD
    if str(df.iloc[6, 10]).strip().upper() != "TOTAL POR ACTIVIDAD":
        errores.append("no se encontró 'TOTAL POR ACTIVIDAD' en K7.")

    # Validar [7,11:23] - Fechas
    for idx, val in enumerate(df.iloc[7, 11:23]):
        if pd.isna(val) or not es_fecha(val):
            errores.append(f"valor no válido en {chr(11 + idx + 65)}8 (se esperaba una fecha).")

    # Validar [7,23] - SUMAN
    if str(df.iloc[7, 23]).strip().upper() != "SUMAN":
        errores.append("no se encontró 'SUMAN' en X8.")

    # Si hay errores, lanzar excepción
    if errores:
        #agregar "Formato no coincide: solo una vez al rpincipio
        errores.insert(0, "Formato no coincide:")
        raise ValueError("\n\n".join(errores))
        # Intenta convertir el valor a una fecha en diferentes formatos "%Y-%m-%d" y "%d/%m/%Y"

def es_fecha(valor):
    """Verifica si un valor es una fecha válida en formatos esperados."""
    formatos_validos = ["%Y-%m-%d", "%d/%m/%Y" ,"%Y-%m-%d %H:%M:%S",  "%d/%m/%Y %H:%M:%S"] # Formatos aceptados
    for formato in formatos_validos:
        try:
            datetime.strptime(str(valor), formato)  # Intenta convertir al formato actual
            return True
        except ValueError:
            continue
    return False