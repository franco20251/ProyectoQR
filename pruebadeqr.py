import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import sqlite3
import cv2
import pandas as pd
from datetime import datetime, time
import os
import threading
from PIL import Image, ImageTk
from pyzbar import pyzbar
import time as time_module

try:
    import numpy as np
    import openpyxl
except ImportError as e:
    print(f"Error: Falta una librería esencial. Instala las dependencias con:\npip install numpy opencv-python pyzbar pandas openpyxl pillow\nDetalle: {e}")
    exit(1)

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
        self.scan_cooldown = 3
        
        # Configuración de horario de ingreso (más permisivo para pruebas)
        self.HORA_INICIO_INGRESO = time(0, 0)    # 00:00 (medianoche)
        self.HORA_FIN_INGRESO = time(23, 59)     # 23:59
        
        # Configurar carpeta de reportes
        self.REPORTS_FOLDER = os.path.join(os.path.expanduser("~"), "Documents", "REPORTES_ASISTENCIA")
        self.check_reports_dir()
        
        # Inicializar la base de datos
        self.inicializar_db()
        
        self.setup_ui()
        
    def inicializar_db(self):
        """Asegura que las tablas necesarias en la BD existan al iniciar."""
        try:
            with sqlite3.connect("asistencia.db") as conn:
                cursor = conn.cursor()
                
                # Crear tabla de estudiantes si no existe
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estudiantes'")
                if not cursor.fetchone():
                    cursor.execute("""
                        CREATE TABLE estudiantes (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            nombre_y_apellido TEXT NOT NULL,
                            id_unico_qr TEXT NOT NULL UNIQUE,
                            curso TEXT,
                            carrera TEXT,
                            fecha_de_nacimiento TEXT,
                            correo_electronico TEXT,
                            genero TEXT
                        )
                    """)
                    print("✅ Tabla 'estudiantes' creada.")
                else:
                    print("✅ Tabla 'estudiantes' ya existe.")
                
                # Crear tabla de asistencia si no existe
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS asistencia (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id INTEGER NOT NULL,
                        fecha TEXT NOT NULL,
                        hora_ingreso TEXT NOT NULL,
                        FOREIGN KEY (student_id) REFERENCES estudiantes (id)
                    )
                """)
                
                # DIAGNÓSTICO: Verificar estructura de tablas
                print("\n🔍 DIAGNÓSTICO DE BASE DE DATOS:")
                cursor.execute("PRAGMA table_info(estudiantes)")
                print("Estructura tabla 'estudiantes':", cursor.fetchall())
                
                cursor.execute("PRAGMA table_info(asistencia)")
                print("Estructura tabla 'asistencia':", cursor.fetchall())
                
                # Mostrar datos existentes
                cursor.execute("SELECT COUNT(*) FROM estudiantes")
                total_estudiantes = cursor.fetchone()[0]
                print(f"Total estudiantes registrados: {total_estudiantes}")
                
                cursor.execute("SELECT COUNT(*) FROM asistencia")
                total_asistencias = cursor.fetchone()[0]
                print(f"Total registros de asistencia: {total_asistencias}")
                
                conn.commit()
                print("✅ Base de datos inicializada correctamente.\n")
                
        except sqlite3.Error as e:
            print(f"❌ Error al inicializar la base de datos: {e}")
            messagebox.showerror("Error de Base de Datos", f"No se pudo inicializar la base de datos: {e}")

    def check_reports_dir(self):
        """Asegura que la carpeta de reportes exista."""
        try:
            os.makedirs(self.REPORTS_FOLDER, exist_ok=True)
            print(f"✅ Carpeta de reportes lista en: {self.REPORTS_FOLDER}")
        except Exception as e:
            print(f"❌ Error al crear carpeta de reportes: {e}")

    def setup_ui(self):
        """Configura la interfaz de usuario."""
        titulo = tk.Label(self.root, text="Sistema de Asistencia - Lector QR", font=('Arial', 18, 'bold'), bg='#ECF0F1', fg='#2C3E50', pady=20)
        titulo.pack()

        main_frame = tk.Frame(self.root, bg='#ECF0F1')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        camera_frame = tk.LabelFrame(main_frame, text="Cámara QR / Visor de Imagen", font=('Arial', 12, 'bold'), bg='#ECF0F1', fg='#2C3E50')
        camera_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        self.video_label = tk.Label(camera_frame, text="Cámara desactivada", bg='black', fg='white', font=('Arial', 12))
        self.video_label.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        btn_frame = tk.Frame(camera_frame, bg='#ECF0F1')
        btn_frame.pack(pady=10)

        self.btn_start_camera = tk.Button(btn_frame, text="Iniciar Cámara", command=self.start_camera, bg='#27AE60', fg='white', font=('Arial', 11, 'bold'), width=15)
        self.btn_start_camera.pack(side=tk.LEFT, padx=5)

        self.btn_stop_camera = tk.Button(btn_frame, text="Detener Cámara", command=self.stop_camera, bg='#E74C3C', fg='white', font=('Arial', 11, 'bold'), width=15)
        self.btn_stop_camera.pack(side=tk.LEFT, padx=5)

        self.btn_load_image = tk.Button(btn_frame, text="Cargar Imagen", command=self.load_and_scan_image, bg='#F39C12', fg='white', font=('Arial', 11, 'bold'), width=15)
        self.btn_load_image.pack(side=tk.LEFT, padx=5)

        info_frame = tk.LabelFrame(main_frame, text="Información de Asistencia", font=('Arial', 12, 'bold'), bg='#ECF0F1', fg='#2C3E50')
        info_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        self.info_text = tk.Text(info_frame, width=40, height=15, font=('Arial', 10), state=tk.DISABLED, relief=tk.FLAT)
        self.info_text.pack(padx=10, pady=10)

        stats_frame = tk.LabelFrame(info_frame, text="Estadísticas del Día", font=('Arial', 10, 'bold'), bg='#ECF0F1', fg='#2C3E50')
        stats_frame.pack(fill=tk.X, padx=10, pady=5)

        self.stats_label = tk.Label(stats_frame, text="Presentes: 0\nTotal estudiantes: 0", font=('Arial', 10), bg='#ECF0F1', justify=tk.LEFT)
        self.stats_label.pack(pady=5)

        # Botones adicionales para diagnóstico
        debug_frame = tk.Frame(info_frame, bg='#ECF0F1')
        debug_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.btn_test_db = tk.Button(debug_frame, text="Test DB", command=self.test_database, bg='#9B59B6', fg='white', font=('Arial', 10, 'bold'), width=10)
        self.btn_test_db.pack(side=tk.LEFT, padx=2)
        
        self.btn_generar_reporte = tk.Button(debug_frame, text="Generar Reporte", command=self.generar_reporte_excel, bg='#3498DB', fg='white', font=('Arial', 10, 'bold'), width=15)
        self.btn_generar_reporte.pack(side=tk.RIGHT, padx=2)

        horario_info = tk.Label(self.root, text=f"Horario de ingreso: {self.HORA_INICIO_INGRESO.strftime('%H:%M')} - {self.HORA_FIN_INGRESO.strftime('%H:%M')}", font=('Arial', 9), bg='#ECF0F1', fg='#7F8C8D')
        horario_info.pack(side=tk.BOTTOM, pady=5)

        self.update_stats()

    def test_database(self):
        """Función de diagnóstico para probar la base de datos."""
        try:
            with sqlite3.connect("asistencia.db") as conn:
                cursor = conn.cursor()
                
                # Mostrar todos los estudiantes
                cursor.execute("SELECT * FROM estudiantes LIMIT 5")
                estudiantes = cursor.fetchall()
                
                # Mostrar todas las asistencias
                cursor.execute("SELECT * FROM asistencia LIMIT 10")
                asistencias = cursor.fetchall()
                
                info = f"🔍 DIAGNÓSTICO DB:\n\n"
                info += f"Estudiantes (primeros 5):\n"
                for est in estudiantes:
                    info += f"- ID: {est[0]}, Nombre: {est[1]}, QR: {est[2]}\n"
                
                info += f"\nAsistencias (últimas 10):\n"
                for asist in asistencias:
                    info += f"- Student_ID: {asist[1]}, Fecha: {asist[2]}, Hora: {asist[3]}\n"
                
                if not asistencias:
                    info += "❌ NO HAY REGISTROS DE ASISTENCIA\n"
                
                self.update_info_text(info)
                
        except Exception as e:
            self.update_info_text(f"❌ Error en diagnóstico: {e}")

    def start_camera(self):
        try:
            self.camera = cv2.VideoCapture(0)
            if not self.camera.isOpened():
                self.camera = cv2.VideoCapture(1)
                if not self.camera.isOpened():
                    raise Exception("No se pudo acceder a la cámara")
            
            self.is_scanning = True
            self.btn_start_camera.configure(state=tk.DISABLED)
            self.btn_stop_camera.configure(state=tk.NORMAL)
            
            self.video_thread = threading.Thread(target=self.video_loop, daemon=True)
            self.video_thread.start()
            
            self.update_info_text("Cámara iniciada. Acerca un código QR...")
            
        except Exception as e:
            messagebox.showerror("Error de Cámara", f"No se pudo iniciar la cámara: {e}")

    def stop_camera(self):
        self.is_scanning = False
        if self.camera:
            self.camera.release()
            self.camera = None
        
        self.btn_start_camera.configure(state=tk.NORMAL)
        self.btn_stop_camera.configure(state=tk.DISABLED)
        
        self.video_label.configure(image='', text="Cámara desactivada")
        self.update_info_text("Cámara detenida.")

    def video_loop(self):
        while self.is_scanning and self.camera:
            try:
                ret, frame = self.camera.read()
                if not ret:
                    time_module.sleep(0.1)
                    continue

                qr_codes = pyzbar.decode(frame)
                
                for qr_code in qr_codes:
                    qr_data = qr_code.data.decode('utf-8')
                    
                    current_time = time_module.time()
                    if (qr_data == self.last_qr_code and current_time - self.last_scan_time < self.scan_cooldown):
                        continue
                    
                    self.last_qr_code = qr_data
                    self.last_scan_time = current_time
                    self.root.after(0, self.process_qr_code, qr_data)
                    
                    points = qr_code.polygon
                    if len(points) == 4:
                        pts = [(point.x, point.y) for point in points]
                        cv2.polylines(frame, [np.array(pts, np.int32)], True, (0, 255, 0), 3)

                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.resize(frame, (400, 300))
                image = Image.fromarray(frame)
                photo = ImageTk.PhotoImage(image)
                
                if self.is_scanning:
                    self.root.after(0, self.update_video_frame, photo)
                    
            except Exception as e:
                print(f"Error en video_loop: {e}")
                time_module.sleep(0.1)

    def load_and_scan_image(self):
        if self.is_scanning:
            self.stop_camera()

        file_path = filedialog.askopenfilename(
            title="Seleccionar imagen con Código QR",
            filetypes=[("Archivos de imagen", "*.png *.jpg *.jpeg *.bmp"), ("Todos los archivos", "*.*")]
        )
        if not file_path:
            return

        try:
            frame = cv2.imread(file_path)
            if frame is None:
                messagebox.showerror("Error", f"No se pudo cargar la imagen desde:\n{file_path}")
                return

            self.display_static_image(frame)
            qr_codes = pyzbar.decode(frame)

            if not qr_codes:
                self.update_info_text("No se encontraron códigos QR en la imagen seleccionada.")
                return

            qr_data = qr_codes[0].data.decode('utf-8')
            self.process_qr_code(qr_data)

        except Exception as e:
            messagebox.showerror("Error al Procesar", f"Ocurrió un error al procesar la imagen: {e}")

    def display_static_image(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized_frame = cv2.resize(frame_rgb, (400, 300))
        image = Image.fromarray(resized_frame)
        photo = ImageTk.PhotoImage(image)
        if self.video_label:
            self.video_label.configure(image=photo, text='')
            self.video_label.image = photo

    def update_video_frame(self, photo):
        if self.video_label and self.is_scanning:
            self.video_label.configure(image=photo, text='')
            self.video_label.image = photo

    def process_qr_code(self, qr_data):
        """Procesar código QR con diagnósticos detallados."""
        try:
            print(f"\n🔍 PROCESANDO QR: {qr_data}")
            
            # Verificar horario (más permisivo para debugging)
            hora_actual = datetime.now().time()
            print(f"⏰ Hora actual: {hora_actual}")
            print(f"⏰ Horario permitido: {self.HORA_INICIO_INGRESO} - {self.HORA_FIN_INGRESO}")
            
            if not (self.HORA_INICIO_INGRESO <= hora_actual <= self.HORA_FIN_INGRESO):
                mensaje = f"🚫 FUERA DE HORARIO 🚫\n\nHora actual: {hora_actual.strftime('%H:%M:%S')}\nHorario permitido: {self.HORA_INICIO_INGRESO.strftime('%H:%M')} - {self.HORA_FIN_INGRESO.strftime('%H:%M')}"
                self.update_info_text(mensaje)
                print("❌ Fuera de horario")
                return

            # Buscar estudiante
            estudiante = self.buscar_estudiante(qr_data)
            print(f"👤 Estudiante encontrado: {estudiante}")
            
            if not estudiante:
                mensaje = f"❌ QR NO RECONOCIDO ❌\n\nCódigo: {qr_data}\n\nEste código no está registrado en la base de datos."
                self.update_info_text(mensaje)
                print("❌ Estudiante no encontrado")
                return

            # Verificar si ya marcó asistencia hoy
            ya_marco = self.ya_marco_asistencia_hoy(estudiante[0])
            print(f"📅 Ya marcó hoy: {ya_marco}")
            
            if ya_marco:
                mensaje = f"⚠️ YA REGISTRADO HOY ⚠️\n\nNombre: {estudiante[1]}\nID: {estudiante[2]}\n\nEste estudiante ya marcó su asistencia hoy."
                self.update_info_text(mensaje)
                print("⚠️ Ya registrado hoy")
                return

            # Registrar asistencia
            print("✅ Procediendo a registrar asistencia...")
            resultado_registro = self.registrar_asistencia(estudiante[0])
            
            if not resultado_registro:
                self.update_info_text("❌ ERROR AL REGISTRAR ASISTENCIA")
                print("❌ Error en el registro")
                return
            
            # Mostrar información completa
            nombre = estudiante[1] or "No especificado"
            id_qr = estudiante[2] or "N/A"
            curso = estudiante[3] or "No especificado"
            carrera = estudiante[4] or "No especificado"
            nacimiento = estudiante[5] or "No especificado"
            correo = estudiante[6] or "No especificado"
            genero = self.format_genero(estudiante[7])
            
            fecha_actual = datetime.now().strftime('%d/%m/%Y')
            hora_actual_str = datetime.now().strftime('%H:%M:%S')
            
            info = (f"✅ ASISTENCIA REGISTRADA ✅\n\n"
                    f"Nombre: {nombre}\n"
                    f"ID: {id_qr}\n"
                    f"Carrera: {carrera}\n"
                    f"Curso: {curso}\n"
                    f"----------------------------------\n"
                    f"Correo: {correo}\n"
                    f"Nacimiento: {nacimiento}\n"
                    f"Género: {genero}\n"
                    f"----------------------------------\n"
                    f"Hora de Ingreso: {hora_actual_str}\n"
                    f"Fecha: {fecha_actual}")
            
            self.update_info_text(info)
            self.update_stats()
            print("✅ Asistencia registrada exitosamente")
            
        except Exception as e:
            error_msg = f"ERROR AL PROCESAR QR\n{str(e)}"
            self.update_info_text(error_msg)
            print(f"❌ Error en process_qr_code: {e}")

    def buscar_estudiante(self, id_qr):
        try:
            with sqlite3.connect("asistencia.db") as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, nombre_y_apellido, id_unico_qr, curso, carrera, 
                           fecha_de_nacimiento, correo_electronico, genero
                    FROM estudiantes WHERE id_unico_qr = ?
                """, (id_qr,))
                resultado = cursor.fetchone()
                print(f"🔍 Búsqueda estudiante con QR '{id_qr}': {resultado}")
                return resultado
        except sqlite3.Error as e:
            print(f"❌ Error al buscar estudiante: {e}")
            return None

    def ya_marco_asistencia_hoy(self, student_id):
        try:
            with sqlite3.connect("asistencia.db") as conn:
                cursor = conn.cursor()
                fecha_hoy_str = str(datetime.now().date())
                print(f"🔍 Verificando asistencia para student_id {student_id} en fecha {fecha_hoy_str}")
                cursor.execute("SELECT id FROM asistencia WHERE student_id = ? AND fecha = ?", (student_id, fecha_hoy_str))
                resultado = cursor.fetchone()
                print(f"📋 Resultado verificación: {resultado}")
                return resultado is not None
        except sqlite3.Error as e:
            print(f"❌ Error al verificar asistencia: {e}")
            return False

    def registrar_asistencia(self, student_id):
        """Registrar asistencia con diagnósticos detallados."""
        try:
            print(f"📝 Iniciando registro de asistencia para student_id: {student_id}")
            
            with sqlite3.connect("asistencia.db") as conn:
                cursor = conn.cursor()
                
                fecha_hoy_str = str(datetime.now().date())
                hora_actual_str = datetime.now().time().strftime('%H:%M:%S')
                
                print(f"📅 Fecha: {fecha_hoy_str}")
                print(f"⏰ Hora: {hora_actual_str}")
                
                # Insertar registro de asistencia
                cursor.execute("""
                    INSERT INTO asistencia (student_id, fecha, hora_ingreso) 
                    VALUES (?, ?, ?)
                """, (student_id, fecha_hoy_str, hora_actual_str))
                
                conn.commit()
                
                # Verificar que se insertó correctamente
                cursor.execute("SELECT * FROM asistencia WHERE student_id = ? AND fecha = ?", (student_id, fecha_hoy_str))
                registro_insertado = cursor.fetchone()
                print(f"✅ Registro insertado: {registro_insertado}")
                
                if registro_insertado:
                    print("✅ Asistencia registrada exitosamente en la base de datos")
                    return True
                else:
                    print("❌ No se pudo verificar la inserción")
                    return False
                
        except sqlite3.Error as e:
            print(f"❌ Error SQLite al registrar asistencia: {e}")
            messagebox.showerror("Error de Base de Datos", f"No se pudo registrar la asistencia: {e}")
            return False
        except Exception as e:
            print(f"❌ Error general al registrar asistencia: {e}")
            return False

    def format_genero(self, genero):
        """Formatear el género para mostrar de forma amigable."""
        if not genero:
            return "No especificado"
        return genero.capitalize()

    def update_info_text(self, mensaje):
        """Actualiza el texto de información de manera thread-safe."""
        try:
            self.info_text.configure(state=tk.NORMAL)
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(1.0, mensaje)
            self.info_text.configure(state=tk.DISABLED)
        except Exception as e:
            print(f"Error al actualizar info_text: {e}")

    def update_stats(self):
        """Actualiza las estadísticas del día."""
        try:
            with sqlite3.connect("asistencia.db") as conn:
                cursor = conn.cursor()
                
                # Contar estudiantes presentes hoy
                fecha_hoy = str(datetime.now().date())
                cursor.execute("SELECT COUNT(*) FROM asistencia WHERE fecha = ?", (fecha_hoy,))
                presentes_hoy = cursor.fetchone()[0]
                
                # Contar total de estudiantes
                cursor.execute("SELECT COUNT(*) FROM estudiantes")
                total_estudiantes = cursor.fetchone()[0]
                
                # Actualizar la etiqueta de estadísticas
                stats_text = f"Presentes hoy: {presentes_hoy}\nTotal estudiantes: {total_estudiantes}\nFecha: {fecha_hoy}"
                self.stats_label.configure(text=stats_text)
                print(f"📊 Stats actualizadas - Presentes: {presentes_hoy}, Total: {total_estudiantes}")
                
        except sqlite3.Error as e:
            print(f"Error al actualizar estadísticas: {e}")
            self.stats_label.configure(text="Error al cargar estadísticas")

    def generar_reporte_excel(self):
        """Generar reporte de asistencia en Excel con más detalles."""
        try:
            with sqlite3.connect("asistencia.db") as conn:
                # Consulta para obtener datos completos de asistencia
                query = """
                SELECT 
                    e.nombre_y_apellido,
                    e.id_unico_qr,
                    e.carrera,
                    e.curso,
                    e.correo_electronico,
                    a.fecha,
                    a.hora_ingreso
                FROM estudiantes e
                LEFT JOIN asistencia a ON e.id = a.student_id
                ORDER BY a.fecha DESC, a.hora_ingreso DESC, e.nombre_y_apellido
                """
                
                df = pd.read_sql_query(query, conn)
                print(f"📊 Datos para reporte: {len(df)} registros")
                
                if df.empty:
                    messagebox.showwarning("Sin Datos", "No hay datos para generar el reporte.")
                    return
                
                # Renombrar columnas para el reporte
                df.columns = ['Nombre', 'ID QR', 'Carrera', 'Curso', 'Correo', 'Fecha', 'Hora Ingreso']
                
                # Crear nombre del archivo con timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"Reporte_Asistencia_{timestamp}.xlsx"
                filepath = os.path.join(self.REPORTS_FOLDER, filename)
                
                # Guardar a Excel
                with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                    # Hoja principal con todos los datos
                    df.to_excel(writer, sheet_name='Asistencia Completa', index=False)
                    
                    # Hoja solo con asistencias registradas (no NULL)
                    df_asistencias = df.dropna(subset=['Fecha', 'Hora Ingreso'])
                    if not df_asistencias.empty:
                        df_asistencias.to_excel(writer, sheet_name='Solo Asistencias', index=False)
                    
                    # Hoja de resumen por día
                    if not df['Fecha'].isna().all():
                        resumen_diario = df.dropna(subset=['Fecha']).groupby('Fecha').size().reset_index()
                        resumen_diario.columns = ['Fecha', 'Total Asistentes']
                        resumen_diario.to_excel(writer, sheet_name='Resumen por Día', index=False)
                
                messagebox.showinfo("Reporte Generado", 
                                  f"Reporte generado exitosamente:\n{filepath}\n\nTotal de registros: {len(df)}\nAsistencias válidas: {len(df.dropna(subset=['Fecha', 'Hora Ingreso']))}")
                print(f"✅ Reporte generado: {filepath}")
                
                # Abrir la carpeta de reportes
                try:
                    import subprocess
                    import platform
                    if platform.system() == 'Windows':
                        subprocess.Popen(['explorer', self.REPORTS_FOLDER])
                except:
                    pass
                    
        except Exception as e:
            print(f"❌ Error al generar reporte: {e}")
            messagebox.showerror("Error", f"No se pudo generar el reporte: {e}")

    def run(self):
        """Iniciar la aplicación."""
        try:
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            self.root.mainloop()
        except KeyboardInterrupt:
            print("Aplicación cerrada por el usuario.")
        except Exception as e:
            print(f"Error inesperado: {e}")
            messagebox.showerror("Error Crítico", f"Error inesperado: {e}")

    def on_closing(self):
        """Manejar el cierre de la aplicación."""
        if self.is_scanning:
            self.stop_camera()
        self.root.destroy()

# Ejecutar la aplicación
if __name__ == "__main__":
    try:
        app = SistemaAsistenciaQR()
        app.run()
    except Exception as e:
        print(f"Error al iniciar la aplicación: {e}")
        messagebox.showerror("Error de Inicio", f"No se pudo iniciar la aplicación: {e}")