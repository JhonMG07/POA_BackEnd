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
    
    json_result = {
        "total_poa": {},
        "actividades": []
    }
    # Detectar dónde comienza el encabezado
    fila_inicio, col_inicio = detectar_inicio(df)

    # Detectar la columna de "TOTAL POR ACTIVIDAD"
    col_total_por_actividad = detectar_total_por_actividad(df, fila_inicio-1)
    # Validar encabezados
    columnas_encontradas = validar_fila_encabezados(df, fila_inicio, col_inicio, col_total_por_actividad)

    fechas_col = sorted(
        [(k, v) for k, v in columnas_encontradas.items() if es_fecha(k)],
        key=lambda x: x[1]
    )
    fecha_headers = [k for k, v in fechas_col]
    fecha_indices = [v for k, v in fechas_col]

    # Columnas base
    col_desc = columnas_encontradas["DESCRIPCIÓN O DETALLE"]
    col_item = columnas_encontradas["ITEM PRESUPUESTARIO"]
    col_cant = columnas_encontradas["CANTIDAD"]
    col_precio = columnas_encontradas["PRECIO UNITARIO"]
    col_total = columnas_encontradas["TOTAL"]
    col_suman = columnas_encontradas["SUMAN"]


    actividad_total = None
    actividad_actual_obj = None
    actividad_esperada = 1  # Comienza esperando (1)

    for i in range(fila_inicio, len(df)):
        fila = df.iloc[i]
        texto_col3 = str(fila[col_inicio]) if not pd.isna(fila[col_inicio]) else ""

        # Detectar línea de TOTAL PRESUPUESTO
        if "TOTAL PRESUPUESTO" in texto_col3.upper():
            total_poa_val = fila[col_total_por_actividad]
            if pd.notna(total_poa_val) and float(total_poa_val) != 0:
                ejec = {}
                for idx, col_idx in enumerate(fecha_indices):
                    val = fila[col_idx]
                    if pd.notna(val) and str(val).strip() != "" and str(val) not in ["0", "0.0", "0.00"]:
                        fecha = fecha_headers[idx]
                        ejec[str(fecha)] = float(val)
                ejec["suman"] = float(fila[col_suman]) if pd.notna(fila[col_suman]) else 0.0
                json_result["total_poa"] = {
                    "descripcion": texto_col3.strip(),
                    "total": float(total_poa_val),
                    "programacion_ejecucion": ejec
                }
            break

        # Validar que las actividades estén en orden (1), (2), (3), ...
        match = re.match(r"\((\d+)\)", texto_col3.strip())
        if match:
            num_actividad = int(match.group(1))
            if num_actividad != actividad_esperada:
                raise ValueError(
                    f"No se encontró la actividad ({actividad_esperada}) después de la actividad : {actividad_actual_obj['descripcion_actividad']}.\n"
                )
            actividad_esperada += 1  # Esperar la siguiente en la próxima iteración
        
            actividad_total = fila[col_total_por_actividad]
            try:
                actividad_total = float(actividad_total)
            except:
                raise ValueError(f"Error en la fila {i+1}: valor no válido en {chr(65 + col_total_por_actividad)}{i+1} (se esperaba un número).")

            if pd.notna(actividad_total) and float(actividad_total) != 0:
                actividad_total = float(actividad_total)
            else:
                actividad_total = 0.0

            actividad_actual_obj = {
                "descripcion_actividad": texto_col3.strip(),
                "total_por_actividad": float(actividad_total),
                "tareas": []
            }
            json_result["actividades"].append(actividad_actual_obj)
            continue

        nombre = fila[col_inicio]
        detalle = fila[col_desc]
        item_presupuestario = fila[col_item]
        cantidad = fila[col_cant]
        precio = fila[col_precio]
        total = fila[col_total]

        if pd.isna(nombre):
            continue

        try:
            total_val = float(total)
        except:
            raise ValueError(f"Error en la fila {i+1}: valor no válido en {chr(65 + col_total)}{i+1} (se esperaba un número).")

        try:
            cantidad_val = float(cantidad)
        except:
            raise ValueError(f"Error en la fila {i+1}: valor no válido en {chr(65 + col_cant)}{i+1} (se esperaba un número).")
        try:
            precio_val = float(precio)
        except:
            raise ValueError(f"Error en la fila {i+1}: valor no válido en {chr(65 + col_precio)}{i+1} (se esperaba un número).")
        if pd.isna(item_presupuestario):
            raise ValueError(f"Error en la fila {i+1}: No puede estar vacia la celda {chr(65 + col_item)}{i+1} (se esperaba el item presupuestario).")
        try:
            item_presupuestario_val = int(item_presupuestario)
        except:
            raise ValueError(f"Error en la fila {i+1}: valor no válido en {chr(65 + col_item)}{i+1} (se esperaba el item presupuestario).")
        # Armamos programación ejecución
        programacion = {}
        for idx, col_idx in enumerate(fecha_indices):
            val = fila[col_idx]
            if pd.notna(val) and str(val).strip() != "" :
                if es_numero(val):
                    fecha = fecha_headers[idx]
                    programacion[str(fecha)] = float(val)
                else:
                    raise ValueError(f"No se guardo nada en la base de datos.\nError en la fila {i+1}: valor no válido en {chr(65 + col_idx)}{i+1} (se esperaba un número).")

        
        # Suman               
        suman_val = fila[col_suman] if pd.notna(fila[col_suman]) else 0.0
        try:
            suman_val = float(suman_val)
        except:
            raise ValueError(f"Error en la fila {i+1}: valor no válido en {chr(65 + col_suman)}{i+1} (se esperaba un número).")
        programacion["suman"] = suman_val

        # Validar que el total sea igual a la suma de cantidad * precio
        tarea = {
            "nombre": str(nombre).strip(),
            "detalle_descripcion": str(detalle).strip() if pd.notna(detalle) else "",
            "item_presupuestario": str(item_presupuestario).strip(),
            "cantidad": float(cantidad) if pd.notna(cantidad) else 0.0,
            "precio_unitario": float(precio) if pd.notna(precio) else 0.0,
            "total": float(total) if pd.notna(total) else 0.0,
            "programacion_ejecucion": programacion
        }

        actividad_actual_obj["tareas"].append(tarea)
    return json_result

def detectar_inicio(df):
    """
    Detecta la fila y columna donde comienza el encabezado basado en que empieze con '(1)'.
    Retorna la fila del encabezado y la columna donde comienza.
    """
    
    for i in range(len(df)):
        for j in range(len(df.columns)):
            if isinstance(df.iloc[i, j], str) and df.iloc[i, j].startswith("(1)"):
                return i, j
    raise ValueError("No se encontró el encabezado esperado con la primera actividad '(1) nombre de la actividad'.")

def detectar_total_por_actividad(df, fila):
    """
    Detecta todas las columnas que contienen 'TOTAL POR ACTIVIDAD' en una fila.
    Si hay más de una ocurrencia, lanza un error.
    Retorna la columna donde se encuentra la única ocurrencia.
    """
    columnas_encontradas = []

    # Recorrer todas las columnas de la fila
    for j, valor in enumerate(df.iloc[fila]):
        if str(valor).strip().upper() == "TOTAL POR ACTIVIDAD":
            columnas_encontradas.append(j)  # Registrar la columna encontrada

    # Verificar si hay más de una ocurrencia
    if len(columnas_encontradas) > 1:
        celdas = [f"{chr(65 + col)}{fila + 1}" for col in columnas_encontradas]
        raise ValueError(f"Se encontraron múltiples columnas con 'TOTAL POR ACTIVIDAD' en las celdas: {', '.join(celdas)}")
    elif len(columnas_encontradas) == 0:
        raise ValueError(f"No se encontró la columna 'TOTAL POR ACTIVIDAD'. en la fila: {fila+1}")

    # Retornar la única columna encontrada
    return columnas_encontradas[0]

def validar_fila_encabezados(df, fila, col_inicio, col_excluir):
    """
    Valida los encabezados en una fila específica del DataFrame.
    Lanza errores si hay encabezados duplicados, faltantes o inválidos.
    
    Parámetros:
        df (pd.DataFrame): El DataFrame que contiene los datos.
        fila (int): Índice de la fila donde están los encabezados.
        col_inicio (int): Columna desde donde se debe comenzar la validación.
        col_excluir (int): Columna que no se debe validar.
    
    Retorna:
        dict: Un diccionario con los índices de las columnas encontradas para cada encabezado.
    """
    # Encabezados requeridos
    encabezados_requeridos = {
        "DESCRIPCIÓN O DETALLE": False,
        "ITEM PRESUPUESTARIO": False,
        "CANTIDAD": False,
        "PRECIO UNITARIO": False,
        "TOTAL": False,
        "SUMAN": False  
    }
    columnas_encontradas = {}

    # Detectar la columna donde está 'SUMAN'
    col_fin = None
    for col in range(col_inicio, df.shape[1]):
        if str(df.iloc[fila, col]).strip().upper() == "SUMAN":
            col_fin = col
            break
    if col_fin is None:
        raise ValueError(f"No se encontró la columna 'SUMAN' en la fila {fila + 1}.")

    # Recorrer las columnas en el rango especificado
    for col in range(col_inicio+1, col_fin + 1):
        if col == col_excluir:  # Saltar la columna que no se debe validar
            continue

        valor = str(df.iloc[fila, col]).strip().upper()
        encabezado_valido = False
        # Validar encabezados requeridos
        for encabezado in encabezados_requeridos.keys():
            if encabezado == "CANTIDAD":
                if valor.startswith("CANTIDAD"):
                    if encabezados_requeridos[encabezado]:
                        raise ValueError(f"Columna duplicada: '{encabezado}' encontrada más de una vez en la celda {chr(65 + col)}{fila + 1}.")
                    encabezados_requeridos[encabezado] = True
                    columnas_encontradas[encabezado] = col
                    encabezado_valido = True
                    break  # Ya no es necesario seguir iterando sobre encabezados
                
            else:
                if valor == encabezado:
                    if encabezados_requeridos[encabezado]:
                        raise ValueError(f"Columna duplicada: '{encabezado}' encontrada más de una vez en la celda {chr(65 + col)}{fila + 1}.")
                    encabezados_requeridos[encabezado] = True
                    columnas_encontradas[encabezado] = col
                    encabezado_valido = True
                    break  # Ya no es necesario seguir iterando sobre encabezados
        
        if not encabezado_valido:
            if not es_fecha(valor):
                raise ValueError(f"Valor no válido en la celda {chr(65 + col)}{fila + 1}.")
            if valor in columnas_encontradas:
                raise ValueError(
                    "Hay fechas repetidas en las columnas de fechas en las celdas: "
                    f"{chr(65 + columnas_encontradas[valor])}{fila + 1} y {chr(65 + col)}{fila + 1}"
                )
            columnas_encontradas[valor] = col
    

     # --- Validación de fechas ---
    # Extraer solo las claves que son fechas
    fechas = [k for k in columnas_encontradas.keys() if es_fecha(k)]
    if len(fechas) != 12:
        raise ValueError(f"Se esperaban 12 columnas de fechas, pero se encontraron {len(fechas)}.")

    # Validar que no haya meses repetidos
    meses = [pd.to_datetime(f).month for f in fechas]
    if len(set(meses)) != 12:
        raise ValueError("Hay meses repetidos en las columnas de fechas en las celdas: " + ", ".join([f"{chr(65 + columnas_encontradas[f])}{fila + 1}" for f in fechas if meses.count(pd.to_datetime(f).month) > 1]))

    # Verificar si falta alguna columna requerida
    faltantes = [col for col, encontrada in encabezados_requeridos.items() if not encontrada]
    
    if faltantes:
        raise ValueError(f"Faltan las siguientes columnas : {', '.join(faltantes)} en la fila {fila + 1}.")

    return columnas_encontradas  # Retorna las columnas encontradas con sus índices

def es_fecha(valor):
    """Verifica si un valor es una fecha válida en formatos esperados."""
    formatos_validos = ["%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"]  # Formatos aceptados
    for formato in formatos_validos:
        try:
            datetime.strptime(str(valor), formato)  # Intenta convertir al formato actual
            return True
        except ValueError:
            continue
    return False

def es_numero(val):
    try:
        float(val)
        return True
    except ValueError:
        return False