import pandas as pd
import logging
import os
import time

class DataHandler:
    def __init__(self, excel_path):
        self.original_path = excel_path
        # Determinar la ruta del archivo "procesado" por defecto
        output_name = f"procesado_{os.path.basename(self.original_path)}"
        if not output_name.endswith('.xlsx'):
            output_name = os.path.splitext(output_name)[0] + ".xlsx"
        self.output_path = os.path.join(os.path.dirname(self.original_path), output_name)
        
        # El archivo de trabajo será el procesado si ya existe, sino el original
        self.current_path = self.output_path if os.path.exists(self.output_path) else self.original_path
        
        self.logger = logging.getLogger(__name__)
        self.df = None
        self.header_row = 0
        self.chasis_col = None

    def load_data(self):
        """Escanea las primeras 20 filas buscando 'Chasis' y carga el DataFrame."""
        try:
            self.logger.info(f"Cargando datos desde: {self.current_path}")
            # Si el archivo es .xlsx (procesado), asumimos header 0
            if self.current_path.endswith('.xlsx'):
                self.df = pd.read_excel(self.current_path)
                # Buscar la columna Chasis en el DF ya cargado
                for i, col in enumerate(self.df.columns):
                    if "chasis" in str(col).lower():
                        self.chasis_col = i
                        break
                return self.df

            # Para archivos .xls originales, buscar el header
            preview = pd.read_excel(self.current_path, header=None, nrows=20)
            
            found = False
            for i, row in preview.iterrows():
                if row.astype(str).str.contains('Chasis', case=False).any():
                    self.header_row = i
                    self.chasis_col = row.astype(str).str.contains('Chasis', case=False).idxmax()
                    self.logger.info(f"Columna 'Chasis' detectada en fila {i}, columna {self.chasis_col}")
                    found = True
                    break
            
            if not found:
                raise ValueError("No se encontró la columna 'Chasis' en las primeras 20 filas.")
            
            # Carga real con el header detectado
            self.df = pd.read_excel(self.current_path, header=self.header_row)
            return self.df
        except Exception as e:
            self.logger.error(f"Error cargando Excel: {e}")
            raise

    def get_vins(self):
        """Devuelve la lista completa de VINs."""
        if self.df is None:
            self.load_data()
        
        chasis_col_name = self.df.columns[self.chasis_col]
        return self.df[chasis_col_name].dropna().tolist()

    def get_pending_vins(self):
        """Devuelve solo los VINs que no tienen resultado aún."""
        if self.df is None:
            self.load_data()
        
        chasis_col_name = self.df.columns[self.chasis_col]
        # Si la columna no existe, todos están pendientes
        if 'Resultado DNPRA' not in self.df.columns:
            return self.get_vins()
        
        # Filtrar los que están vacíos, son NaN o son Errores previos que queremos reintentar
        mask = (
            self.df['Resultado DNPRA'].isna() | 
            (self.df['Resultado DNPRA'].astype(str).str.strip() == "") |
            (self.df['Resultado DNPRA'].astype(str).str.contains('Error|CAPTCHA_INCORRECTA', case=False, regex=True))
        )
        return self.df.loc[mask, chasis_col_name].dropna().tolist()

    def get_tipo_map(self):
        """
        Lee la columna 'Nro.Fabr.' y determina si cada VIN es Nacional o Importado.
        Regla: el 4to carácter (índice 3) del valor Nro.Fabr. indica el tipo:
          - '1' → Nacional  (value='N')
          - '2' → Importado (value='I')
        Devuelve: dict { vin (str) → 'N' o 'I' }
        """
        if self.df is None:
            self.load_data()

        chasis_col_name = self.df.columns[self.chasis_col]

        # Buscar la columna Nro.Fabr.
        fabr_col = None
        for col in self.df.columns:
            if 'fabr' in str(col).lower() or 'nro' in str(col).lower():
                fabr_col = col
                break

        if fabr_col is None:
            self.logger.warning("No se encontró la columna 'Nro.Fabr.'. Usando Nacional por defecto.")
            vins = self.df[chasis_col_name].dropna().astype(str).tolist()
            return {vin: 'N' for vin in vins}

        tipo_map = {}
        for _, row in self.df.iterrows():
            vin = str(row[chasis_col_name]).strip()
            nro_fabr = str(row[fabr_col]).strip()
            if len(nro_fabr) >= 4:
                cuarto_char = nro_fabr[3]  # índice 3 = 4to carácter (ej: TPA[2]... → '2')
                if cuarto_char == '2':
                    tipo = 'I'  # Importado
                else:
                    tipo = 'N'  # Nacional (por defecto para '1' u otros)
            else:
                tipo = 'N'
            tipo_map[vin] = tipo

        importados = sum(1 for t in tipo_map.values() if t == 'I')
        nacionales = sum(1 for t in tipo_map.values() if t == 'N')
        self.logger.info(f"Tipo mapeado: {nacionales} Nacionales, {importados} Importados.")
        return tipo_map

    def save_results(self, results_dict, dominios_dict=None):
        """
        Guarda los resultados y dominios en nuevas columnas.
        results_dict:  {vin: "Vigente/Vencido/Error"}
        dominios_dict: {vin: "AB123CD"}  (opcional)
        Si el archivo está bloqueado (abierto en Excel), reintenta y guarda backup.
        """
        chasis_col_name = self.df.columns[self.chasis_col]

        # Asegurar columnas de tipo object (string-compatible)
        for col in ['Resultado DNPRA', 'Dominio DNPRA']:
            if col not in self.df.columns:
                self.df[col] = pd.Series(dtype=object)
            else:
                self.df[col] = self.df[col].astype(object)

        for vin, res in results_dict.items():
            self.df.loc[self.df[chasis_col_name] == vin, 'Resultado DNPRA'] = res

        if dominios_dict:
            for vin, dom in dominios_dict.items():
                if dom:
                    self.df.loc[self.df[chasis_col_name] == vin, 'Dominio DNPRA'] = dom

        # Intentar guardar, con reintentos por si el archivo está abierto en Excel
        for intento in range(3):
            try:
                self.df.to_excel(self.output_path, index=False, engine='openpyxl')
                self.logger.info(f"Resultados guardados en: {self.output_path}")
                self.current_path = self.output_path
                return self.output_path
            except PermissionError:
                self.logger.warning(f"Archivo bloqueado (intento {intento+1}/3). ¿Está abierto en Excel? Esperando 5s...")
                time.sleep(5)
            except Exception as e:
                self.logger.error(f"Error guardando resultados: {e}")
                break

        # Último recurso: guardar con nombre de backup para no perder datos
        import datetime
        backup_path = self.output_path.replace('.xlsx', f'_backup_{datetime.datetime.now().strftime("%H%M%S")}.xlsx')
        try:
            self.df.to_excel(backup_path, index=False, engine='openpyxl')
            self.logger.warning(f"Guardado en backup: {backup_path} (cerrar Excel y renombrar)")
        except Exception as e:
            self.logger.error(f"Error CRÍTICO guardando backup: {e}")

