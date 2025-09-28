import tkinter as tk
from tkinter import messagebox, ttk
import sqlite3
import qrcode
import os
import sys
import re
from datetime import datetime

# --- 1. CONFIGURACIÓN DE RUTAS Y BASE DE DATOS SQLite ---

# RUTA QR (No cambia)
QR_FOLDER = os.path.join(os.path.expanduser("~"), "Documents", "QR ASISTENCIA")

def check_qr_dir():
    """Asegura que la carpeta de destino del QR exista."""
    try:
        os.makedirs(QR_FOLDER, exist_ok=True)
        print(f"Carpeta QR lista en: {QR_FOLDER}")
    except Exception as e:
        print(f"Error al crear la carpeta QR: {e}")
        messagebox.showerror("Error de Carpeta", "No se pudo crear la carpeta 'QR ASISTENCIA'. Revise los permisos.")

def init_db():
    """Crea la tabla estudiantes si no existe usando la nueva estructura."""
    try:
        # Se conecta o crea el archivo 'asistencia.db'
        with sqlite3.connect("asistencia.db") as conn:
            cursor = conn.cursor()
            # Nueva estructura de la tabla (comentarios movidos FUERA del SQL para evitar errores de sintaxis)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS estudiantes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre_y_apellido TEXT NOT NULL,
                    id_unico_qr TEXT UNIQUE NOT NULL,
                    curso TEXT NOT NULL,
                    carrera TEXT NOT NULL,
                    fecha_de_nacimiento TEXT,
                    correo_electronico TEXT UNIQUE,
                    genero TEXT
                )
            """)
            conn.commit()
            print("Base de datos SQLite inicializada con nueva estructura.")
    except Exception as e:
        print(f"Error al inicializar la BD SQLite: {e}")
        messagebox.showerror("Error BD", f"Error al inicializar la base de datos: {e}")

# Ejecutar las comprobaciones al inicio del programa
init_db()
check_qr_dir()

# --- 2. GENERACIÓN DE QR ---

def generar_qr(id_unico, nombre_y_apellido=""):
    """Genera un código QR con el ID único y lo guarda."""
    # Sanitizamos el nombre para el archivo (reemplazamos espacios y caracteres especiales)
    nombre_archivo = f"QR_{id_unico}_{nombre_y_apellido.replace(' ', '_').replace('/', '_').replace('\\', '_')}.png"
    ruta_completa = os.path.join(QR_FOLDER, nombre_archivo)
    
    try:
        # El contenido del QR es el id_unico
        img = qrcode.make(id_unico)
        img.save(ruta_completa)
        print(f"\n--- QR GUARDADO EXITOSAMENTE en: {ruta_completa} ---")
        return True
    except Exception as e:
        messagebox.showerror("ERROR DE PERMISOS/GUARDADO", 
                             f"El QR no se pudo guardar. Causa: {e}\n\nRuta de intento: {ruta_completa}")
        print(f"!!! FALLA DE GUARDADO. ERROR: {e}")
        return False

# --- 3. VALIDACIONES AUXILIARES ---

def validar_email(correo):
    """Valida el formato básico de un email."""
    if not correo:
        return True  # Opcional
    patron = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(patron, correo) is not None

def validar_fecha(fecha):
    """Valida el formato de fecha YYYY-MM-DD."""
    if not fecha:
        return True  # Opcional
    try:
        datetime.strptime(fecha, '%Y-%m-%d')
        return True
    except ValueError:
        return False

# --- 4. GESTIÓN DE USUARIOS (CRUD: Create/Read) ---

# Variables globales para los widgets (mejoradas para evitar conflictos)
entry_nombre_apellido = None
entry_id_unico = None
entry_curso = None
entry_carrera = None
entry_fecha_nacimiento = None
entry_correo = None
var_genero = None

def guardar_usuario():
    """Guarda un nuevo estudiante en SQLite y genera su QR."""
    global entry_nombre_apellido, entry_id_unico, entry_curso, entry_carrera
    global entry_fecha_nacimiento, entry_correo, var_genero
    
    # 1. Recolección de datos
    nombre_apellido = entry_nombre_apellido.get().strip()
    id_unico = entry_id_unico.get().strip()
    curso = entry_curso.get().strip()
    carrera = entry_carrera.get().strip()
    fecha_nacimiento = entry_fecha_nacimiento.get().strip()
    correo = entry_correo.get().strip()
    genero = var_genero.get()
    
    # Validaciones básicas
    if not (nombre_apellido and id_unico and curso and carrera):
        messagebox.showerror("Error", "Los campos Nombre/Apellido, ID Único, Curso y Carrera son obligatorios.")
        return

    # Validaciones adicionales
    if correo and not validar_email(correo):
        messagebox.showerror("Error", "El formato del correo electrónico es inválido.")
        return
    if fecha_nacimiento and not validar_fecha(fecha_nacimiento):
        messagebox.showerror("Error", "La fecha de nacimiento debe estar en formato YYYY-MM-DD.")
        return

    try:
        # 1. Guardar en la base de datos SQLite
        with sqlite3.connect("asistencia.db") as conn:
            cursor = conn.cursor()
            
            # La consulta SQL debe reflejar la nueva estructura de la tabla (sin comentarios # dentro)
            sql = ("INSERT INTO estudiantes ("
                   "nombre_y_apellido, id_unico_qr, curso, carrera, fecha_de_nacimiento, correo_electronico, genero"
                   ") VALUES (?, ?, ?, ?, ?, ?, ?)")
            
            cursor.execute(sql, (
                nombre_apellido, 
                id_unico, 
                curso, 
                carrera, 
                fecha_nacimiento if fecha_nacimiento else None, 
                correo if correo else None, 
                genero
            ))
            conn.commit()
        
        # 2. Generar QR usando el id_unico_qr
        if generar_qr(id_unico, nombre_apellido):
            msg = f"Usuario {nombre_apellido} agregado correctamente.\nQR generado y guardado."
        else:
            msg = f"Usuario {nombre_apellido} agregado, pero FALLÓ la generación del QR."
            
        messagebox.showinfo("Resultado de Guardado", msg)
        
        # 3. Limpiar campos
        limpiar_campos()
        entry_nombre_apellido.focus()
            
    except sqlite3.IntegrityError:
        messagebox.showerror("Error", f"El ID Único o el Correo Electrónico ya existen y deben ser únicos.")
    except sqlite3.Error as e:
        messagebox.showerror("Error de BD", f"Ocurrió un error al guardar: {e}")

def limpiar_campos():
    """Limpia todos los campos del formulario."""
    global entry_nombre_apellido, entry_id_unico, entry_curso, entry_carrera
    global entry_fecha_nacimiento, entry_correo, var_genero
    if entry_nombre_apellido:
        entry_nombre_apellido.delete(0, tk.END)
    if entry_id_unico:
        entry_id_unico.delete(0, tk.END)
    if entry_curso:
        entry_curso.delete(0, tk.END)
    if entry_carrera:
        entry_carrera.delete(0, tk.END)
    if entry_fecha_nacimiento:
        entry_fecha_nacimiento.delete(0, tk.END)
    if entry_correo:
        entry_correo.delete(0, tk.END)
    if var_genero:
        var_genero.set('O')

def gestion_usuarios(root):
    """Crea y muestra la ventana para añadir nuevos estudiantes (el formulario)."""
    global entry_nombre_apellido, entry_id_unico, entry_curso, entry_carrera
    global entry_fecha_nacimiento, entry_correo, var_genero
    
    # Cerrar ventana anterior si es necesario, pero usamos Toplevel
    ventana = tk.Toplevel(root)
    ventana.title("Gestión de Usuarios")
    ventana.geometry("500x700")
    ventana.resizable(False, False)
    ventana.grab_set()  # Hace que esta ventana sea modal

    # Frame principal con padding
    frame = tk.Frame(ventana, padx=20, pady=20)
    frame.pack(fill=tk.BOTH, expand=True)

    # 1. Nombre y Apellido
    tk.Label(frame, text="Nombre y Apellido *:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=5)
    entry_nombre_apellido = tk.Entry(frame, width=50, font=('Arial', 10))
    entry_nombre_apellido.grid(row=1, column=0, sticky=tk.W, pady=2)

    # 2. ID Único para QR
    tk.Label(frame, text="ID Único para QR *:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky=tk.W, pady=5)
    entry_id_unico = tk.Entry(frame, width=50, font=('Arial', 10))
    entry_id_unico.grid(row=3, column=0, sticky=tk.W, pady=2)
    
    # 3. Curso
    tk.Label(frame, text="Curso *:", font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky=tk.W, pady=5)
    entry_curso = tk.Entry(frame, width=50, font=('Arial', 10))
    entry_curso.grid(row=5, column=0, sticky=tk.W, pady=2)
    
    # 4. Carrera
    tk.Label(frame, text="Carrera *:", font=('Arial', 10, 'bold')).grid(row=6, column=0, sticky=tk.W, pady=5)
    entry_carrera = tk.Entry(frame, width=50, font=('Arial', 10))
    entry_carrera.grid(row=7, column=0, sticky=tk.W, pady=2)
    
    # 5. Fecha de Nacimiento
    tk.Label(frame, text="Fecha de Nacimiento (YYYY-MM-DD):", font=('Arial', 10)).grid(row=8, column=0, sticky=tk.W, pady=5)
    entry_fecha_nacimiento = tk.Entry(frame, width=50, font=('Arial', 10))
    entry_fecha_nacimiento.grid(row=9, column=0, sticky=tk.W, pady=2)

    # 6. Correo Electrónico
    tk.Label(frame, text="Correo Electrónico:", font=('Arial', 10)).grid(row=10, column=0, sticky=tk.W, pady=5)
    entry_correo = tk.Entry(frame, width=50, font=('Arial', 10))
    entry_correo.grid(row=11, column=0, sticky=tk.W, pady=2)

    # 7. Género (Radio Buttons)
    tk.Label(frame, text="Género:", font=('Arial', 10)).grid(row=12, column=0, sticky=tk.W, pady=5)
    var_genero = tk.StringVar(value='O')
    
    frame_genero = tk.Frame(frame)
    frame_genero.grid(row=13, column=0, sticky=tk.W, pady=2)
    
    tk.Radiobutton(frame_genero, text="Masculino (M)", variable=var_genero, value="M").pack(side=tk.LEFT, padx=10)
    tk.Radiobutton(frame_genero, text="Femenino (F)", variable=var_genero, value="F").pack(side=tk.LEFT, padx=10)
    tk.Radiobutton(frame_genero, text="Otro (O)", variable=var_genero, value="O").pack(side=tk.LEFT, padx=10)

    # Botón Guardar
    tk.Button(frame,
              text="Guardar Usuario",
              command=guardar_usuario,
              bg='#3498DB',
              fg='white',
              activebackground='#2980B9',
              font=('Arial', 12, 'bold'),
              width=25,
              pady=10
              ).grid(row=14, column=0, pady=20)

    # Botón Limpiar
    tk.Button(frame,
              text="Limpiar Campos",
              command=limpiar_campos,
              bg='#95A5A6',
              fg='white',
              activebackground='#7F8C8D',
              font=('Arial', 10)
              ).grid(row=15, column=0, pady=5)

    entry_nombre_apellido.focus()

def obtener_estudiantes():
    """Recupera todos los estudiantes de la base de datos SQLite con la nueva estructura."""
    try:
        with sqlite3.connect("asistencia.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nombre_y_apellido, id_unico_qr, curso, carrera, fecha_de_nacimiento, correo_electronico, genero FROM estudiantes ORDER BY nombre_y_apellido")
            return cursor.fetchall()
    except sqlite3.Error as e:
        messagebox.showerror("Error de BD", f"Error al leer los datos: {e}")
        return []

def mostrar_usuarios(root):
    """Crea una nueva ventana para mostrar la lista de estudiantes usando Treeview."""
    estudiantes = obtener_estudiantes()
    
    ventana_lista = tk.Toplevel(root)
    ventana_lista.title("Lista de Estudiantes")
    ventana_lista.geometry("1200x600")
    ventana_lista.resizable(True, True)
    ventana_lista.grab_set()  # Modal

    # Frame principal
    frame = tk.Frame(ventana_lista)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    tk.Label(frame, text="Estudiantes Registrados", font=('Arial', 14, 'bold')).pack(pady=10)

    # Treeview para tabla
    columns = ('ID', 'Nombre y Apellido', 'ID QR', 'Curso', 'Carrera', 'Fecha Nacimiento', 'Correo Electrónico', 'Género')
    tree = ttk.Treeview(frame, columns=columns, show='headings', height=20)

    # Configurar encabezados y anchos
    tree.heading('ID', text='ID')
    tree.heading('Nombre y Apellido', text='Nombre y Apellido')
    tree.heading('ID QR', text='ID QR')
    tree.heading('Curso', text='Curso')
    tree.heading('Carrera', text='Carrera')
    tree.heading('Fecha Nacimiento', text='Fecha Nacimiento')
    tree.heading('Correo Electrónico', text='Correo Electrónico')
    tree.heading('Género', text='Género')

    # Anchos de columnas
    tree.column('ID', width=50, anchor=tk.CENTER)
    tree.column('Nombre y Apellido', width=200)
    tree.column('ID QR', width=150)
    tree.column('Curso', width=100)
    tree.column('Carrera', width=150)
    tree.column('Fecha Nacimiento', width=120)
    tree.column('Correo Electrónico', width=200)
    tree.column('Género', width=80, anchor=tk.CENTER)

    # Scrollbars
    scrollbar_y = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
    scrollbar_x = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=tree.xview)
    tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
    scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

    # Insertar datos
    if estudiantes:
        for est in estudiantes:
            # Mapear género: M->Masculino, F->Femenino, O->Otro
            genero_map = {'M': 'Masculino', 'F': 'Femenino', 'O': 'Otro'}
            genero_display = genero_map.get(est[7], est[7] or '-')
            
            tree.insert('', tk.END, values=(
                est[0],
                est[1] or '-',
                est[2] or '-',
                est[3] or '-',
                est[4] or '-',
                est[5] or '-',
                est[6] or '-',
                genero_display
            ))
    else:
        # Mensaje si no hay datos
        tree.insert('', tk.END, values=('', 'No hay estudiantes registrados.', '', '', '', '', '', ''))

# --- 5. MODO CMD ---

def cargar_usuario_cmd():
    """Carga de usuarios desde la línea de comandos (terminal)."""
    print("=== Cargar usuario desde CMD ===")
    
    nombre_apellido = input("Nombre y Apellido: ").strip()
    id_unico = input("ID Único para QR: ").strip()
    curso = input("Curso: ").strip()
    carrera = input("Carrera: ").strip()
    fecha_nacimiento = input("Fecha de Nacimiento (YYYY-MM-DD, opcional): ").strip()
    correo = input("Correo Electrónico (opcional): ").strip()
    genero_input = input("Género (M/F/O, por defecto O): ").strip() or 'O'
    
    # Validaciones básicas (similares a GUI)
    if not (nombre_apellido and id_unico and curso and carrera):
        print("Los campos obligatorios no fueron llenados.")
        return

    # Validaciones adicionales
    if correo and not validar_email(correo):
        print("Error: El formato del correo electrónico es inválido.")
        return
    if fecha_nacimiento and not validar_fecha(fecha_nacimiento):
        print("Error: La fecha de nacimiento debe estar en formato YYYY-MM-DD.")
        return

    try:
        with sqlite3.connect("asistencia.db") as conn:
            cursor = conn.cursor()
            sql = ("INSERT INTO estudiantes ("
                   "nombre_y_apellido, id_unico_qr, curso, carrera, fecha_de_nacimiento, correo_electronico, genero"
                   ") VALUES (?, ?, ?, ?, ?, ?, ?)")
            cursor.execute(sql, (
                nombre_apellido,
                id_unico,
                curso,
                carrera,
                fecha_nacimiento if fecha_nacimiento else None,
                correo if correo else None,
                genero_input.upper()[:1]  # Asegurar M/F/O
            ))
            conn.commit()
        
        if generar_qr(id_unico, nombre_apellido):
            print(f"Usuario '{nombre_apellido}' agregado. QR generado en 'QR ASISTENCIA'.")
        else:
            print(f"Usuario '{nombre_apellido}' agregado, pero FALLÓ la generación del QR.")
            
    except sqlite3.IntegrityError:
        print("Error: El ID Único o el Correo Electrónico ya existen y deben ser únicos.")
    except sqlite3.Error as e:
        print(f"Error de BD: {e}")

def listar_usuarios_cmd():
    """Lista todos los usuarios desde la línea de comandos."""
    estudiantes = obtener_estudiantes()
    
    if not estudiantes:
        print("No hay estudiantes registrados.")
        return
    
    print("\n=== LISTA DE ESTUDIANTES ===")
    print(f"{'ID':<5} {'Nombre y Apellido':<25} {'ID QR':<15} {'Curso':<12} {'Carrera':<20} {'Género':<8}")
    print("-" * 90)
    
    for est in estudiantes:
        genero_map = {'M': 'Masc.', 'F': 'Fem.', 'O': 'Otro'}
        genero_display = genero_map.get(est[7], est[7] or '-')
        
        print(f"{est[0]:<5} {(est[1] or '-')[:24]:<25} {(est[2] or '-')[:14]:<15} {(est[3] or '-')[:11]:<12} {(est[4] or '-')[:19]:<20} {genero_display:<8}")

# --- 6. INTERFAZ GRÁFICA PRINCIPAL ---

def crear_menu_principal():
    """Crea la ventana principal con los botones del menú."""
    root = tk.Tk()
    root.title("Sistema de Asistencia con QR")
    root.geometry("600x400")
    root.resizable(False, False)
    
    # Configurar el tema/color de fondo
    root.configure(bg='#ECF0F1')
    
    # Título principal
    titulo = tk.Label(root, 
                      text="Sistema de Asistencia con QR", 
                      font=('Arial', 18, 'bold'),
                      bg='#ECF0F1',
                      fg='#2C3E50',
                      pady=20)
    titulo.pack()
    
    # Frame para los botones
    frame_botones = tk.Frame(root, bg='#ECF0F1')
    frame_botones.pack(expand=True, fill=tk.BOTH, padx=50, pady=20)
    
    # Botón: Gestión de Usuarios
    btn_gestion = tk.Button(frame_botones,
                            text="Agregar Nuevo Estudiante",
                            command=lambda: gestion_usuarios(root),
                            bg='#3498DB',
                            fg='white',
                            activebackground='#2980B9',
                            font=('Arial', 14, 'bold'),
                            width=25,
                            pady=15)
    btn_gestion.pack(pady=10)
    
    # Botón: Lista de Estudiantes
    btn_lista = tk.Button(frame_botones,
                          text="Ver Lista de Estudiantes",
                          command=lambda: mostrar_usuarios(root),
                          bg='#27AE60',
                          fg='white',
                          activebackground='#229954',
                          font=('Arial', 14, 'bold'),
                          width=25,
                          pady=15)
    btn_lista.pack(pady=10)
    
    # Botón: Salir
    btn_salir = tk.Button(frame_botones,
                          text="Salir",
                          command=root.destroy,
                          bg='#E74C3C',
                          fg='white',
                          activebackground='#C0392B',
                          font=('Arial', 14, 'bold'),
                          width=25,
                          pady=15)
    btn_salir.pack(pady=10)
    
    # Información en la parte inferior
    info_label = tk.Label(root,
                          text="Los códigos QR se guardan en: Documentos/QR ASISTENCIA",
                          font=('Arial', 9),
                          bg='#ECF0F1',
                          fg='#7F8C8D')
    info_label.pack(side=tk.BOTTOM, pady=10)
    
    return root

# --- 7. FUNCIÓN PRINCIPAL ---

def main():
    """Función principal que determina si usar GUI o CMD."""
    
    # Si se ejecuta con argumentos de línea de comandos, usar modo CMD
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg == 'add' or arg == 'agregar':
            cargar_usuario_cmd()
        elif arg == 'list' or arg == 'listar':
            listar_usuarios_cmd()
        else:
            print("Uso: python app_asistencia.py [add|list]")
            print("  add/agregar: Agregar un nuevo estudiante desde CMD")
            print("  list/listar: Listar estudiantes desde CMD")
            print("  Sin argumentos: Abrir interfaz gráfica")
    else:
        # Modo GUI (por defecto)
        try:
            root = crear_menu_principal()
            root.mainloop()
        except KeyboardInterrupt:
            print("\nPrograma interrumpido por el usuario.")
        except Exception as e:
            print(f"Error en la interfaz gráfica: {e}")
            messagebox.showerror("Error Crítico", f"Error inesperado: {e}")

# --- 8. PUNTO DE ENTRADA ---

if __name__ == "__main__":
    main()