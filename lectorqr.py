import tkinter as tk
from tkinter import messagebox, ttk
import sqlite3
import cv2
import pandas as pd
from datetime import datetime, time
import os
import threading
from PIL import Image, ImageTk
from pyzbar import pyzbar
import time as time_module

# Importar numpy después de verificar opencv
try:
    import numpy as np
except ImportError:
    # Esto es solo un mensaje de error por si numpy no está instalado
    # El código debe tener numpy instalado para las partes de visión por computadora
    pass 

class SistemaAsistenciaQR:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Sistema de Asistencia - Lector QR")
        self.root.geometry("900x700")
        self.root.configure(bg='#ECF0F1')
        
        # Variables de control
        self.camera = None
        self.is_scanning = False
        self.video_label = None
        self.last_qr_code = ""
        self.last_scan_time = 0
        self.scan_cooldown = 3  # segundos entre escaneos del mismo QR
        
        # Configuración de horario de ingreso (puedes modificar estos valores)
        self.HORA_INICIO_INGRESO = time(7, 0)    # 7:00 AM
        self.HORA_FIN_INGRESO = time(10, 0)      # 10:00 AM
        
        # Configurar carpeta de reportes
        self.REPORTS_FOLDER = os.path.join(os.path.expanduser("~"), "Documents", "REPORTES_ASISTENCIA")
        self.check_reports_dir()
        
        # MODIFICACIÓN SOLICITADA: Inicializar la base de datos
        self.inicializar_db()  
        
        self.setup_ui()
        
    def check_reports_dir(self):
        """Asegura que la carpeta de reportes exista."""
        try:
            os.makedirs(self.REPORTS_FOLDER, exist_ok=True)
            print(f"Carpeta de reportes lista en: {self.REPORTS_FOLDER}")
        except Exception as e:
            print(f"Error al crear carpeta de reportes: {e}")

    def inicializar_db(self):
        """Inicializa la base de datos y crea las tablas si no existen."""
        try:
            with sqlite3.connect("asistencia.db") as conn:
                cursor = conn.cursor()
                
                # Tabla de Estudiantes (Debe existir para registrar asistencias)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS estudiantes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nombre_y_apellido TEXT NOT NULL,
                        id_unico_qr TEXT UNIQUE NOT NULL,
                        curso TEXT,
                        carrera TEXT,
                        fecha_de_nacimiento DATE,
                        correo_electronico TEXT,
                        genero TEXT
                    )
                """)
                
                # Tabla de Asistencia
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS asistencia (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id INTEGER NOT NULL,
                        fecha DATE NOT NULL,
                        hora_ingreso TIME NOT NULL,
                        FOREIGN KEY (student_id) REFERENCES estudiantes (id),
                        UNIQUE(student_id, fecha)
                    )
                """)
                conn.commit()
                print("Base de datos y tablas inicializadas correctamente.")
        except sqlite3.Error as e:
            messagebox.showerror("Error de DB", f"No se pudo inicializar la base de datos: {e}")
            print(f"Error al inicializar la base de datos: {e}")

    def setup_ui(self):
        """Configura la interfaz de usuario."""
        # Título
        titulo = tk.Label(self.root, 
                          text="Sistema de Asistencia - Lector QR", 
                          font=('Arial', 18, 'bold'),
                          bg='#ECF0F1',
                          fg='#2C3E50',
                          pady=20)
        titulo.pack()

        # Frame principal
        main_frame = tk.Frame(self.root, bg='#ECF0F1')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Frame izquierdo (cámara)
        camera_frame = tk.LabelFrame(main_frame, text="Cámara QR", font=('Arial', 12, 'bold'),
                                     bg='#ECF0F1', fg='#2C3E50')
        camera_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Label para mostrar video
        self.video_label = tk.Label(camera_frame, text="Cámara desactivada", 
                                     bg='black', fg='white', font=('Arial', 12))
        self.video_label.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Botones de cámara
        btn_frame = tk.Frame(camera_frame, bg='#ECF0F1')
        btn_frame.pack(pady=10)

        self.btn_start_camera = tk.Button(btn_frame, text="Iniciar Cámara",
                                         command=self.start_camera,
                                         bg='#27AE60', fg='white',
                                         font=('Arial', 11, 'bold'),
                                         width=15)
        self.btn_start_camera.pack(side=tk.LEFT, padx=5)

        self.btn_stop_camera = tk.Button(btn_frame, text="Detener Cámara",
                                        command=self.stop_camera,
                                        bg='#E74C3C', fg='white',
                                        font=('Arial', 11, 'bold'),
                                        width=15)
        self.btn_stop_camera.pack(side=tk.LEFT, padx=5)

        # Frame derecho (información)
        info_frame = tk.LabelFrame(main_frame, text="Información de Asistencia", 
                                    font=('Arial', 12, 'bold'),
                                    bg='#ECF0F1', fg='#2C3E50')
        info_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        # Información del estudiante actual
        self.info_text = tk.Text(info_frame, width=40, height=15,
                                 font=('Arial', 10), state=tk.DISABLED)
        self.info_text.pack(padx=10, pady=10)

        # Estadísticas del día
        stats_frame = tk.LabelFrame(info_frame, text="Estadísticas del Día",
                                     font=('Arial', 10, 'bold'),
                                     bg='#ECF0F1', fg='#2C3E50')
        stats_frame.pack(fill=tk.X, padx=10, pady=5)

        self.stats_label = tk.Label(stats_frame, text="Presentes: 0\nTotal estudiantes: 0",
                                     font=('Arial', 10), bg='#ECF0F1', justify=tk.LEFT)
        self.stats_label.pack(pady=5)

        # Botón para generar reporte
        self.btn_generar_reporte = tk.Button(info_frame, text="Generar Reporte Excel",
                                             command=self.generar_reporte_excel,
                                             bg='#3498DB', fg='white',
                                             font=('Arial', 11, 'bold'),
                                             width=20)
        self.btn_generar_reporte.pack(pady=10)

        # Información de horario
        horario_info = tk.Label(self.root, 
                              text=f"Horario de ingreso: {self.HORA_INICIO_INGRESO.strftime('%H:%M')} - {self.HORA_FIN_INGRESO.strftime('%H:%M')}",
                              font=('Arial', 9), bg='#ECF0F1', fg='#7F8C8D')
        horario_info.pack(side=tk.BOTTOM, pady=5)

        # Actualizar estadísticas al inicio
        self.update_stats()

    def start_camera(self):
        """Inicia la cámara y el escaneo de QR."""
        try:
            # Intentar con cámara 0 (por defecto)
            self.camera = cv2.VideoCapture(0)  
            if not self.camera.isOpened():
                 # Intentar con cámara 1 si la 0 falla
                 self.camera = cv2.VideoCapture(1)
                 if not self.camera.isOpened():
                    raise Exception("No se pudo acceder a la cámara")
            
            self.is_scanning = True
            self.btn_start_camera.configure(state=tk.DISABLED)
            self.btn_stop_camera.configure(state=tk.NORMAL)
            
            # Iniciar thread para captura de video
            self.video_thread = threading.Thread(target=self.video_loop, daemon=True)
            self.video_thread.start()
            
            self.update_info_text("Cámara iniciada. Acerca un código QR...")
            
        except Exception as e:
            messagebox.showerror("Error de Cámara", f"No se pudo iniciar la cámara: {e}")

    def stop_camera(self):
        """Detiene la cámara."""
        self.is_scanning = False
        if self.camera:
            self.camera.release()
            self.camera = None
        
        self.btn_start_camera.configure(state=tk.NORMAL)
        self.btn_stop_camera.configure(state=tk.DISABLED)
        
        # Mostrar mensaje en label de video
        self.video_label.configure(image='', text="Cámara desactivada")
        self.update_info_text("Cámara detenida.")

    def video_loop(self):
        """Loop principal de captura de video y detección de QR."""
        while self.is_scanning and self.camera:
            ret, frame = self.camera.read()
            if not ret:
                continue

            # Detectar códigos QR
            qr_codes = pyzbar.decode(frame)
            
            for qr_code in qr_codes:
                # Decodificar el contenido del QR
                qr_data = qr_code.data.decode('utf-8')
                
                # Evitar múltiples escaneos del mismo QR
                current_time = time_module.time()
                if (qr_data == self.last_qr_code and 
                    current_time - self.last_scan_time < self.scan_cooldown):
                    continue
                
                self.last_qr_code = qr_data
                self.last_scan_time = current_time
                
                # Procesar QR en el hilo principal
                self.root.after(0, self.process_qr_code, qr_data)
                
                # Dibujar rectángulo alrededor del QR detectado
                points = qr_code.polygon
                if len(points) == 4 and 'np' in globals(): # Asegurar que numpy está importado
                    pts = [(point.x, point.y) for point in points]
                    # Aquí se usa numpy (np) para la conversión de puntos
                    cv2.polylines(frame, [np.array(pts, np.int32)], True, (0, 255, 0), 3)

            # Convertir frame para mostrar en tkinter
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, (400, 300))
            
            # Convertir a imagen PIL y luego a PhotoImage
            image = Image.fromarray(frame)
            photo = ImageTk.PhotoImage(image)
            
            # Actualizar label de video en el hilo principal
            if self.is_scanning:
                self.root.after(0, self.update_video_frame, photo)

    def update_video_frame(self, photo):
        """Actualiza el frame de video en la interfaz."""
        if self.video_label and self.is_scanning:
            self.video_label.configure(image=photo, text='')
            self.video_label.image = photo  # Mantener referencia

    def process_qr_code(self, qr_data):
        """Procesa el código QR escaneado."""
        try:
            # Verificar horario de ingreso
            hora_actual = datetime.now().time()
            
            if not (self.HORA_INICIO_INGRESO <= hora_actual <= self.HORA_FIN_INGRESO):
                self.update_info_text(f"FUERA DE HORARIO\nHorario de ingreso: {self.HORA_INICIO_INGRESO.strftime('%H:%M')} - {self.HORA_FIN_INGRESO.strftime('%H:%M')}")
                return

            # Buscar estudiante en la base de datos
            estudiante = self.buscar_estudiante(qr_data)
            
            if not estudiante:
                self.update_info_text(f"QR NO RECONOCIDO\nCódigo: {qr_data}\nEste código no está registrado en el sistema.")
                return

            # Verificar si ya marcó asistencia hoy
            if self.ya_marco_asistencia_hoy(estudiante[0]):
                self.update_info_text(f"YA REGISTRADO HOY\n\nNombre: {estudiante[1]}\nID: {estudiante[2]}\nCurso: {estudiante[3]}\nCarrera: {estudiante[4]}\n\nEste estudiante ya marcó asistencia hoy.")
                return

            # Registrar asistencia
            self.registrar_asistencia(estudiante[0])
            
            # Mostrar información del estudiante
            info = (f"✅ ASISTENCIA REGISTRADA\n\n"
                    f"Nombre: {estudiante[1]}\n"
                    f"ID: {estudiante[2]}\n"
                    f"Curso: {estudiante[3]}\n"
                    f"Carrera: {estudiante[4]}\n"
                    f"Género: {self.format_genero(estudiante[7])}\n"
                    f"Hora: {datetime.now().strftime('%H:%M:%S')}\n"
                    f"Fecha: {datetime.now().strftime('%d/%m/%Y')}")
            
            self.update_info_text(info)
            self.update_stats()
            
        except Exception as e:
            self.update_info_text(f"ERROR AL PROCESAR QR\n{str(e)}")

    def buscar_estudiante(self, id_qr):
        """Busca un estudiante por su ID único de QR."""
        try:
            with sqlite3.connect("asistencia.db") as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, nombre_y_apellido, id_unico_qr, curso, carrera, 
                            fecha_de_nacimiento, correo_electronico, genero
                    FROM estudiantes 
                    WHERE id_unico_qr = ?
                """, (id_qr,))
                return cursor.fetchone()
        except sqlite3.Error as e:
            print(f"Error al buscar estudiante: {e}")
            return None

    def ya_marco_asistencia_hoy(self, student_id):
        """Verifica si el estudiante ya marcó asistencia hoy."""
        try:
            with sqlite3.connect("asistencia.db") as conn:
                cursor = conn.cursor()
                
                # Verificar si ya existe registro para hoy
                fecha_hoy = datetime.now().date()
                cursor.execute("""
                    SELECT id FROM asistencia 
                    WHERE student_id = ? AND fecha = ?
                """, (student_id, fecha_hoy))
                
                return cursor.fetchone() is not None
                
        except sqlite3.Error as e:
            print(f"Error al verificar asistencia: {e}")
            return False

    def registrar_asistencia(self, student_id):
        """Registra la asistencia del estudiante."""
        try:
            with sqlite3.connect("asistencia.db") as conn:
                cursor = conn.cursor()
                
                fecha_hoy = datetime.now().date()
                hora_actual = datetime.now().time().strftime('%H:%M:%S') # Formatear hora
                
                cursor.execute("""
                    INSERT INTO asistencia (student_id, fecha, hora_ingreso)
                    VALUES (?, ?, ?)
                """, (student_id, fecha_hoy, hora_actual))
                
                conn.commit()
                print(f"Asistencia registrada para student_id: {student_id}")
                
        except sqlite3.Error as e:
            print(f"Error al registrar asistencia: {e}")
            raise

    def update_info_text(self, text):
        """Actualiza el texto de información."""
        self.info_text.configure(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(1.0, text)
        self.info_text.configure(state=tk.DISABLED)

    def update_stats(self):
        """Actualiza las estadísticas del día."""
        try:
            with sqlite3.connect("asistencia.db") as conn:
                cursor = conn.cursor()
                
                # Total de estudiantes
                cursor.execute("SELECT COUNT(*) FROM estudiantes")
                total_estudiantes = cursor.fetchone()[0]
                
                # Presentes hoy
                fecha_hoy = datetime.now().date()
                cursor.execute("""
                    SELECT COUNT(*) FROM asistencia 
                    WHERE fecha = ?
                """, (fecha_hoy,))
                presentes_hoy = cursor.fetchone()[0]
                
                self.stats_label.configure(text=f"Presentes: {presentes_hoy}\nTotal estudiantes: {total_estudiantes}")
                
        except sqlite3.Error as e:
            print(f"Error al actualizar estadísticas: {e}")

    def format_genero(self, genero):
        """Formatea el género para mostrar."""
        genero_map = {'M': 'Masculino', 'F': 'Femenino', 'O': 'Otro'}
        return genero_map.get(genero, genero or 'No especificado')

    def generar_reporte_excel(self):
        """Genera un reporte de asistencia en Excel."""
        try:
            fecha_hoy = datetime.now().date()
            
            with sqlite3.connect("asistencia.db") as conn:
                # Query para obtener datos completos
                query = """
                    SELECT 
                        e.nombre_y_apellido,
                        e.id_unico_qr,
                        e.curso,
                        e.carrera,
                        CASE 
                            WHEN a.fecha IS NOT NULL THEN 'PRESENTE'
                            ELSE 'AUSENTE'
                        END as estado,
                        CASE 
                            WHEN a.hora_ingreso IS NOT NULL THEN a.hora_ingreso
                            ELSE ''
                        END as hora_ingreso
                    FROM estudiantes e
                    LEFT JOIN asistencia a ON e.id = a.student_id AND a.fecha = ?
                    ORDER BY e.nombre_y_apellido
                """
                
                df = pd.read_sql_query(query, conn, params=(fecha_hoy,))
            
            # Renombrar columnas para el reporte
            df.columns = ['Nombre y Apellido', 'ID QR', 'Curso', 'Carrera', 'Estado', 'Hora Ingreso']
            
            # Nombre del archivo
            nombre_archivo = f"asistencia_{fecha_hoy.strftime('%Y_%m_%d')}.xlsx"
            ruta_archivo = os.path.join(self.REPORTS_FOLDER, nombre_archivo)
            
            # Crear el archivo Excel con formato
            # Se usa 'openpyxl' como motor, el cual debe estar instalado (pip install openpyxl)
            with pd.ExcelWriter(ruta_archivo, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Asistencia')
                
                # Obtener la hoja de trabajo
                worksheet = writer.sheets['Asistencia']
                
                # Ajustar ancho de columnas
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    # Limitar el ancho para que no sea excesivamente grande
                    adjusted_width = min(max_length + 2, 50) 
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            # Mostrar estadísticas
            total = len(df)
            presentes = len(df[df['Estado'] == 'PRESENTE'])
            ausentes = total - presentes
            
            mensaje = (f"Reporte generado exitosamente!\n\n"
                      f"Archivo: {nombre_archivo}\n"
                      f"Ubicación: {self.REPORTS_FOLDER}\n\n"
                      f"Estadísticas:\n"
                      f"Total estudiantes: {total}\n"
                      f"Presentes: {presentes}\n"
                      f"Ausentes: {ausentes}")
            
            messagebox.showinfo("Reporte Generado", mensaje)
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el reporte: {e}")

    def run(self):
        """Ejecuta la aplicación."""
        try:
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            self.root.mainloop()
        except KeyboardInterrupt:
            print("\nAplicación interrumpida por el usuario.")

    def on_closing(self):
        """Maneja el cierre de la aplicación."""
        self.stop_camera()
        self.root.destroy()

def main():
    """Función principal."""
    # Verificar que numpy y pandas estén disponibles antes de iniciar
    try:
        import numpy as np 
        import pandas as pd
        
        app = SistemaAsistenciaQR()
        app.run()
        
    except ImportError as e:
        error_msg = f"Error: Falta una librería esencial. Asegúrate de instalar:\n{e}"
        print(error_msg)
        messagebox.showerror("Error de Librerías", f"Para ejecutar, necesita:\n- opencv-python\n- pyzbar\n- pandas\n- openpyxl\n- pillow\n\nInstálalas con:\npip install opencv-python pyzbar pandas openpyxl pillow")
    except Exception as e:
        print(f"Error al iniciar la aplicación: {e}")
        messagebox.showerror("Error Crítico", f"No se pudo iniciar la aplicación: {e}")

if __name__ == "__main__":
    main()