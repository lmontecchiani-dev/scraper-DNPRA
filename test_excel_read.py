import pandas as pd
import os

file_path = r'c:\Users\analistapi\Desktop\Proyectos\scraper-DNPRA\docs\ReporteSiac\recepci02-973.xls'
try:
    # Leer las primeras 20 filas para detectar el header
    df_preview = pd.read_excel(file_path, header=None, nrows=20)
    print("Previsualización de las primeras 20 filas:")
    print(df_preview)
    
    # Intentar detectar 'Chasis'
    found = False
    for i, row in df_preview.iterrows():
        if row.astype(str).str.contains('Chasis', case=False).any():
            col_idx = row.astype(str).str.contains('Chasis', case=False).idxmax()
            print(f"\nEncabezado 'Chasis' encontrado en Fila {i}, Columna {col_idx}")
            found = True
            # Ver los datos debajo
            vins = pd.read_excel(file_path, header=i).iloc[:, col_idx].dropna().unique()
            print(f"Primeros 5 VINs encontrados: {list(vins)[:5]}")
            break
    if not found:
        print("\nNo se pudo encontrar la columna 'Chasis' en las primeras 20 filas.")
except Exception as e:
    print(f"Error al leer Excel: {e}")
