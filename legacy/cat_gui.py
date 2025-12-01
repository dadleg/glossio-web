import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, ttk
import os
import threading
import traceback
import re
import webbrowser
# Importamos backend y la lista de idiomas
import catv5_core
from catv5_core import ProjectManager, Utils, LANGUAGES


# --- Tooltip Class ---
class CreateToolTip(object):
    def __init__(self, widget, text='widget info'):
        self.wait_time = 500
        self.wrap_length = 180
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule(); self.hidetip()

    def schedule(self):
        self.unschedule(); self.id = self.widget.after(self.wait_time, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id: self.widget.after_cancel(id)

    def showtip(self, event=None):
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(self.tw, text=self.text, justify='left', background="#ffffe0", relief='solid', borderwidth=1,
                         font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw = None
        if tw: tw.destroy()


# --- Main APP ---
class CATApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CAT beta 1.0 - Configuración Inicial")
        self.geometry("1200x780")

        self.project = ProjectManager()
        self.current_state = None

        self.loading_thread = None
        self.loading_result = None
        self.ignore_tree_event = False

        self.setup_styles()
        self.setup_menu_bar()
        self.setup_ui()
        self.setup_shortcuts()

        # INITAL STATUS: LOCK EVERYTHING EXCEPT LANGUAGE SELECTION
        self.toggle_app_state("disabled")

    def safe_config(self, widget, **kwargs):
        try:
            widget.config(**kwargs)
        except (tk.TclError, AttributeError):
            pass

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        self.tag_colors = {
            'translated': ('#e6fffa', 'black'),
            'active': ('#0078D7', 'white'),
            'fuzzy': ('#fffbe6', 'black'),
            'empty': ('white', 'black'),
            'has_note': ('#fff0f5', 'purple')  # <--- Color rosado/letra morada para notas
        }

    def setup_ui(self):
        # Layout Principal
        main_layout = tk.Frame(self)
        main_layout.pack(fill=tk.BOTH, expand=True)

        # --- 0. PANEL DE CONFIGURACIÓN DE IDIOMA (TOP) ---
        # 🟢 CAMBIO CRUCIAL: Asignar directamente a self.config_frame
        self.config_frame = ttk.LabelFrame(main_layout, text="1. Configuración del Proyecto", padding=10)
        self.config_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        # Contenedor interno para alinear combos
        # 🟢 NOTA: Ahora usamos self.config_frame como padre
        f_lang = tk.Frame(self.config_frame)
        f_lang.pack(fill=tk.X)

        # Selector FUENTE (Limitado a Inglés por ahora, pero preparado para más)
        tk.Label(f_lang, text="Idioma Fuente (Original):").pack(side=tk.LEFT, padx=5)
        self.cbo_source = ttk.Combobox(f_lang, values=["English", "English (US)", "English (UK)"], state="readonly",
                                       width=20)
        self.cbo_source.current(0)  # Seleccionar el primero por defecto
        self.cbo_source.pack(side=tk.LEFT, padx=5)

        # 📚 Botón para cargar glosario (ya existente)
        self.btn_load_glossary = ttk.Button(f_lang, text="📚 Cargar Glosario (.csv)", command=self.on_load_glossary)
        self.btn_load_glossary.pack(side=tk.LEFT, padx=(5, 10))

        # 🧠 NUEVO: Botón para cargar TM
        self.btn_load_tm = ttk.Button(f_lang, text="🧠 Cargar Memoria (.json)", command=self.on_load_tm)
        self.btn_load_tm.pack(side=tk.LEFT, padx=5)

        # Separador visual
        tk.Label(f_lang, text="➡").pack(side=tk.LEFT, padx=10)

        # Selector DESTINO (Todos los idiomas)
        tk.Label(f_lang, text="Idioma Destino (Traducción):").pack(side=tk.LEFT, padx=5)
        sorted_langs = sorted(LANGUAGES.keys())
        self.cbo_target = ttk.Combobox(f_lang, values=sorted_langs, state="readonly", width=20)
        self.cbo_target.set("Spanish")  # Default
        self.cbo_target.pack(side=tk.LEFT, padx=5)

        # Botón CONFIRMAR
        self.btn_confirm_lang = ttk.Button(f_lang, text="✅ Confirmar Idiomas", command=self.on_confirm_languages)
        self.btn_confirm_lang.pack(side=tk.LEFT, padx=20)

        # --- FIN PANEL CONFIG ---

        # Panel dividido (Splitter)
        main_paned = tk.PanedWindow(main_layout, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        # --- 1. PANEL DE NAVEGACIÓN (IZQUIERDA) ---
        self.nav_frame = ttk.Frame(main_paned, width=250, relief=tk.SUNKEN)
        main_paned.add(self.nav_frame, stretch="never")

        ttk.Label(self.nav_frame, text="2. Navegador de Segmentos", font=("Arial", 10, "bold")).pack(pady=5)

        self.tree = ttk.Treeview(self.nav_frame, columns=("id", "source"), show="headings", selectmode="browse")
        self.tree.heading("id", text="#")
        self.tree.heading("source", text="Texto Fuente")
        self.tree.column("id", width=40, anchor="center", stretch=False)
        self.tree.column("source", width=200)

        for tag, (bg, fg) in self.tag_colors.items():
            self.tree.tag_configure(tag, background=bg, foreground=fg)

        tree_scroll = ttk.Scrollbar(self.nav_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # --- 2. PANEL DE EDITOR (DERECHA) ---
        editor_frame = ttk.Frame(main_paned)
        main_paned.add(editor_frame, stretch="always")

        # TOOLBAR (Contenedor de botones de acción)
        self.toolbar = ttk.Frame(editor_frame, padding=5)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        # Botones principales
        self.create_tool_button(self.toolbar, "📂 Abrir DOCX", self.load_project, "Cargar documento (Ctrl+O)")
        self.create_tool_button(self.toolbar, "💾 Guardar/Salir", self.exit_app, "Guardar y Salir (Ctrl+E)")
        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        self.create_tool_button(self.toolbar, "⬅ Anterior", self.on_prev_segment, "Ctrl+B")
        self.btn_next = self.create_tool_button(self.toolbar, "Siguiente ➡", self.on_next_segment, "Ctrl+N")
        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        self.create_tool_button(self.toolbar, "📋 Copiar", self.copy_source_to_target, "Ctrl+I")
        self.create_tool_button(self.toolbar, "🤖 TM", self.use_tm_suggestion, "Ctrl+T")
        self.create_tool_button(self.toolbar, "🔍 Buscar", self.open_concordance, "Ctrl+F")

        self.create_tool_button(self.toolbar, "📋 Copiar", self.copy_source_to_target, "Ctrl+I")
        self.create_tool_button(self.toolbar, "🔗 Unir", self.merge_segment, "Unir con anterior (Ctrl+J)")  # <--- NUEVO
        self.create_tool_button(self.toolbar, "🤖 TM", self.use_tm_suggestion, "Ctrl+T")

        self.btn_mt = ttk.Button(self.toolbar, text="🤖 Traducir (MT)", command=self.translate_mt)
        self.btn_mt.pack(side=tk.LEFT, padx=5)
        CreateToolTip(self.btn_mt, "Envía a DeepL (Requiere API Key)")

        self.progress_bar = ttk.Progressbar(self.toolbar, orient='horizontal', mode='indeterminate', length=150)
        self.progress_bar.pack(side=tk.LEFT, padx=5)

        self.lbl_tm = tk.Label(self.toolbar, text="TM: ...", fg="gray")
        self.lbl_tm.pack(side=tk.LEFT, padx=10)

        # INFO FRAME (Debajo toolbar)
        self.info_frame = tk.Frame(editor_frame)
        self.info_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(5, 0))

        self.lbl_link = tk.Label(self.info_frame, text="", fg="blue", cursor="hand2", font=("Arial", 9, "underline"))
        self.lbl_link.pack(anchor="w", side=tk.LEFT, padx=(5, 10))
        self.lbl_glossary = tk.Label(self.info_frame, text="", fg="#d9534f", font=("Arial", 9, "bold"))
        self.lbl_glossary.pack(anchor="w", side=tk.LEFT)

        # EDITORES DE TEXTO
        text_paned = tk.PanedWindow(editor_frame, orient=tk.VERTICAL)
        text_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        f_source = ttk.LabelFrame(text_paned, text="Texto Original", padding=5)
        text_paned.add(f_source, height=200)
        self.txt_source = scrolledtext.ScrolledText(f_source, wrap=tk.WORD, font=("Consolas", 11), bg="#f4f4f4",
                                                    state='disabled')
        self.txt_source.pack(fill=tk.BOTH, expand=True)
        self.txt_source.tag_config("active_segment", background="#fffacd", foreground="black", borderwidth=1,
                                   relief="solid")
        self.txt_source.tag_config("glossary_term", foreground="#d9534f", font=("Consolas", 11, "bold", "underline"))

        f_target = ttk.LabelFrame(text_paned, text="Traducción", padding=5)
        text_paned.add(f_target, height=200)
        self.txt_target = scrolledtext.ScrolledText(f_target, wrap=tk.WORD, font=("Consolas", 11))
        self.txt_target.pack(fill=tk.BOTH, expand=True)
        self.txt_target.bind("<KeyRelease>", self.run_live_qa)

        # --- NUEVO PANEL DE NOTAS (Debajo de Traducción) ---
        f_notes = ttk.LabelFrame(text_paned, text="📝 Notas", padding=5)
        text_paned.add(f_notes, height=80)
        self.txt_notes = tk.Text(f_notes, height=4, font=("Arial", 10), wrap=tk.WORD)
        self.txt_notes.pack(fill=tk.BOTH, expand=True)
        # Guardar al salir del cuadro
        self.txt_notes.bind("<FocusOut>", self.save_current_note)

        self.lbl_status = tk.Label(editor_frame, text="Esperando confirmación de idioma...", relief=tk.SUNKEN,
                                   anchor="w", bg="#fff3cd")
        self.lbl_status.pack(side=tk.BOTTOM, fill=tk.X)

    def export_current_docx(self):
        """Exporta el documento traducido y muestra un mensaje."""
        if not self.project.docx_path:
            messagebox.showwarning("Aviso", "No hay proyecto cargado para exportar.")
            return

        try:
            output_path = self.project.export_docx()
            messagebox.showinfo("Éxito", f"Documento exportado correctamente a:\n{output_path}")
        except Exception as e:
            messagebox.showerror("Error de Exportación", f"No se pudo exportar el archivo: {str(e)}")

    def setup_menu_bar(self):
        """Crea y configura la barra de menú principal."""

        menubar = tk.Menu(self)
        self.config(menu=menubar)

        # 1. Menú Archivo
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Archivo", menu=file_menu)
        file_menu.add_command(label="📂 Abrir DOCX (Ctrl+O)", command=self.load_project)
        file_menu.add_command(label="💾 Guardar Progreso", command=self.project.save_progress)
        file_menu.add_command(label="📤 Exportar DOCX", command=self.export_current_docx)
        file_menu.add_separator()
        file_menu.add_command(label="❌ Guardar y Salir (Ctrl+E)", command=self.exit_app)

        # 2. Menú Editar ...
        edit_menu = tk.Menu(menubar, tearoff=0)  # Puedes cambiar nombre de Configuración a Editar o crear uno nuevo
        menubar.add_cascade(label="Editar", menu=edit_menu)
        edit_menu.add_command(label="🔗 Unir con Anterior (Ctrl+J)", command=self.merge_segment)
        edit_menu.add_command(label="📝 Editar Notas", command=lambda: self.txt_notes.focus_set())

        # 3. Menú Configuración (Edición/Control de Calidad)
        config_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Configuración", menu=config_menu)
        config_menu.add_command(label="📚 Cargar Glosario (.csv)", command=self.on_load_glossary)
        config_menu.add_command(label="🧠 Cargar Memoria TM (.json)", command=self.on_load_tm)  # 📌 Nuevo
        config_menu.add_separator()
        config_menu.add_command(label="🛠️ Ajustes (placeholder)", command=lambda: messagebox.showinfo("Ajustes",
                                                                                                      "Próximamente: Configuración de API, Versión de Biblia, y otros."))

        # 4. Menú Navegación
        nav_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Navegar", menu=nav_menu)
        nav_menu.add_command(label="⬅ Segmento Anterior (Ctrl+B)", command=self.on_prev_segment)
        nav_menu.add_command(label="➡ Segmento Siguiente (Ctrl+N)", command=self.on_next_segment)
        nav_menu.add_command(label="🔍 Búsqueda Concordancia (Ctrl+F)", command=self.open_concordance)
        nav_menu.add_command(label="🔢 Ir a Segmento... (Ctrl+G)", command=self.ask_goto_segment)
        nav_menu.add_command(label="🔎 Buscar en Proyecto... (Ctrl+Shift+F)", command=self.open_project_search)

        # 5. Menú Traducción
        trans_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Traducción", menu=trans_menu)
        trans_menu.add_command(label="📋 Copiar Fuente (Ctrl+I)", command=self.copy_source_to_target)
        trans_menu.add_command(label="🤖 Usar Sugerencia TM (Ctrl+T)", command=self.use_tm_suggestion)
        trans_menu.add_command(label="🌐 Traducir con MT", command=self.translate_mt)

        # 6. Menú Ayuda
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ayuda", menu=help_menu)
        help_menu.add_command(label="Acerca de CAT beta 1.0", command=lambda: messagebox.showinfo("Acerca de",
                                                                                                  "CAT beta 1.0\nHerramienta de Traducción Asistida por Computadora."))

    def create_tool_button(self, parent, text, command, tooltip_text):
        btn = ttk.Button(parent, text=text, command=command)
        btn.pack(side=tk.LEFT, padx=2)
        CreateToolTip(btn, tooltip_text)
        return btn

    def setup_shortcuts(self):
        self.bind('<Control-o>', lambda e: self.load_project())
        self.bind('<Control-e>', lambda e: self.exit_app())
        self.bind('<Control-n>', lambda e: self.on_next_segment())
        self.bind('<Control-b>', lambda e: self.on_prev_segment())
        self.bind('<Control-i>', lambda e: self.copy_source_to_target())
        self.bind('<Control-t>', lambda e: self.use_tm_suggestion())
        self.bind('<Control-f>', lambda e: self.open_concordance())
        self.bind('<Control-j>', lambda e: self.merge_segment())
        self.bind('<Control-g>', lambda e: self.ask_goto_segment())
        self.bind('<Control-F>', lambda e: self.open_project_search())  # Shift+F o Ctrl+Shift+F según prefieras
        self.tree.bind('<Up>', lambda e: self.on_prev_segment())
        self.tree.bind('<Down>', lambda e: self.on_next_segment())

    def on_load_glossary(self):
            """Permite al usuario seleccionar y cargar un nuevo archivo de glosario CSV."""
            file_path = filedialog.askopenfilename(
                title="Seleccionar archivo de Glosario (terminos.csv)",
                filetypes=[("Archivos CSV", "*.csv")]
            )
            if not file_path:
                return

            # Llamar al nuevo método del backend
            success = self.project.glossary.load_new_glossary(file_path)

            if success:
                term_count = len(self.project.glossary.data)
                self.safe_config(self.lbl_status,
                                 text=f"📚 Glosario cargado: {os.path.basename(file_path)} ({term_count} términos).",
                                 bg="#d4edda")

                # Reejecutar el QA y refrescar la vista para actualizar el resaltado en el segmento actual
                if self.current_state:
                    self.run_live_qa()
                    self.refresh_view()
            else:
                self.safe_config(self.lbl_status, text=f"❌ Error al cargar el glosario.", bg="#f8d7da")
                messagebox.showerror("Error de Glosario",
                                     "No se pudo cargar el archivo CSV. Verifique que el formato sean dos columnas (fuente, destino).")

    def on_load_tm(self):
            """Permite al usuario seleccionar y cargar un nuevo archivo JSON de Memoria de Traducción (TM)."""
            file_path = filedialog.askopenfilename(
                title="Seleccionar archivo de Memoria de Traducción (.json)",
                filetypes=[("Archivos JSON", "*.json")]
            )
            if not file_path:
                return

            success = self.project.tm.load_new_tm(file_path)

            if success:
                term_count = len(self.project.tm.data)
                self.safe_config(self.lbl_status,
                                 text=f"🧠 Memoria de Traducción cargada: {os.path.basename(file_path)} ({term_count} segmentos).",
                                 bg="#d4edda")

                # Recalcula el TM match en el segmento actual
                if self.current_state:
                    self.refresh_view()
            else:
                self.safe_config(self.lbl_status, text=f"❌ Error al cargar la Memoria de Traducción.", bg="#f8d7da")
                messagebox.showerror("Error de TM",
                                     "No se pudo cargar el archivo JSON. Verifique que sea un formato de diccionario {fuente: destino}.")

            # 1. FUNCIÓN UNIR (JOIN)

    def merge_segment(self):
        if not self.current_state: return
        if self.current_state["s_idx"] == 0:
            messagebox.showwarning("Unir", "No se puede unir el primer segmento.")
            return

        # Guardar antes de unir
        self.save_current_segment()

        if messagebox.askyesno("Unir", "¿Unir con el anterior?"):
            if self.project.merge_with_previous():
                self.rebuild_treeview()  # CRUCIAL: Actualizar lista visual
                self.refresh_view()

    # --- FUNCIÓN GUARDAR NOTA ---
    def save_current_note(self, event=None):
        if not self.current_state:
            return
        # "end-1c" evita guardar saltos de línea extra
        note_text = self.txt_notes.get("1.0", "end-1c").strip()
        p_idx, s_idx = self.current_state["p_idx"], self.current_state["s_idx"]

        self.project.save_note(note_text)

        # Actualizar indicador visual (opcional)
        self.update_treeview_status()

    # --- FUNCIÓN RECONSTRUIR ÁRBOL (Necesaria para Unir) ---
    def rebuild_treeview(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        if not self.project.structure: return

        # Lógica simplificada de reconstrucción
        for i, p_data in enumerate(self.project.structure):
            for j, s_data in enumerate(p_data.get("sentences", [])):
                status = "translated" if s_data.get("trad", "").strip() else "empty"
                if s_data.get("note"): status = "has_note"  # Prioridad visual a notas

                node_id = f"{i}-{j}"
                display_id = f"{i + 1}.{j + 1}"
                preview = s_data["orig"][:50] + "..."
                self.tree.insert("", "end", iid=node_id, values=(display_id, preview), tags=(status,))

        # Restaurar selección
        try:
            curr = f"{self.project.p_idx}-{self.project.s_idx}"
            self.tree.selection_set(curr)
            self.tree.see(curr)
        except:
            pass

    def update_treeview_status(self):
        """Actualiza el estado visual del segmento actual en el treeview (ej. si tiene nota)."""
        if not self.current_state:
            return

        p_idx, s_idx = self.current_state['p_idx'], self.current_state['s_idx']
        node_id = f"{p_idx}-{s_idx}"

        if not self.tree.exists(node_id):
            return

        try:
            # 1. Obtener los datos del segmento del backend usando la estructura
            segment_data = self.project.structure[p_idx]["sentences"][s_idx]

            # 2. Determinar si tiene nota
            has_note = segment_data.get('note', '').strip() != ""

            # 3. Obtener los tags actuales del nodo
            current_tags = list(self.tree.item(node_id, 'tags'))

            # 4. Modificar la lista de tags (Añadir o Quitar 'has_note')
            if 'has_note' in current_tags and not has_note:
                current_tags.remove('has_note')
            elif has_note and 'has_note' not in current_tags:
                current_tags.append('has_note')

            # 5. Aplicar la nueva lista de tags al nodo
            self.tree.item(node_id, tags=tuple(current_tags))

        except IndexError:
            # Esto puede ocurrir si los índices están fuera de rango
            print(f"Error: Índices {p_idx}-{s_idx} fuera de rango al actualizar el Treeview.")
        except tk.TclError:
            pass  # Ignorar errores menores de Treeview

    # --- FUNCIÓN BÚSQUEDA ---
    def open_project_search(self):
        win = tk.Toplevel(self)
        win.title("Buscar en Proyecto")

        entry = tk.Entry(win, width=40)
        entry.pack(padx=5, pady=5)
        entry.focus()

        listbox = tk.Listbox(win, width=60, height=15)
        listbox.pack(padx=5, pady=5)

        def do_search(e=None):
            listbox.delete(0, tk.END)
            # Busca en ORIGEN por defecto
            res = self.project.search_in_project(entry.get(), "source")
            for p, s, txt in res:
                listbox.insert(tk.END, f"[{p + 1}.{s + 1}] {txt}")

        def goto_res(e):
            sel = listbox.curselection()
            if not sel: return
            txt = listbox.get(sel[0])
            # Extraer índices con Regex
            m = re.match(r'\[(\d+)\.(\d+)\]', txt)
            if m:
                self.save_current_segment()
                self.project.goto_segment(int(m.group(1)) - 1, int(m.group(2)) - 1)
                self.refresh_view()
                win.destroy()

        entry.bind("<Return>", do_search)
        listbox.bind("<Double-Button-1>", goto_res)
    # --------------------------------------------------------------------------

    # --- GESTIÓN DE ESTADO (BLOQUEO/DESBLOQUEO) ---
    def toggle_app_state(self, state="normal"):
        """Habilita o deshabilita todos los controles principales."""
        # 1. Botones del Toolbar
        for child in self.toolbar.winfo_children():
            try:
                child.configure(state=state)
            except:
                pass

        # 2. Editores
        # El editor fuente siempre es disabled excepto para updates internos
        self.txt_target.config(state=state)

        # 3. Mensaje de estado
        if state == "disabled":
            self.safe_config(self.lbl_status, text="⚠️ Seleccione idiomas y haga clic en 'Confirmar' para iniciar.",
                             bg="#fff3cd")
        else:
            self.safe_config(self.lbl_status, text="Listo para cargar documento.", bg="#d4edda")

    def on_confirm_languages(self):
        src_name = self.cbo_source.get()
        tgt_name = self.cbo_target.get()

        if src_name == tgt_name:
            messagebox.showwarning("Aviso", "El idioma fuente y destino no pueden ser iguales.")
            return

        # Mapear nombres a códigos (El resto se mantiene igual)
        src_code = "EN" if "English" in src_name else "EN" # Fallback seguro
        tgt_code = catv5_core.LANGUAGES.get(tgt_name, "ES")

        # Configurar el proyecto
        self.project.set_languages(target_code=tgt_code, source_code=src_code)

        # Desbloquear interfaz
        self.toggle_app_state("normal")

        # Bloquear selectores y botón
        self.cbo_source.config(state="disabled")
        self.cbo_target.config(state="disabled")
        self.btn_confirm_lang.config(state="disabled", text="Idiomas Fijados")

        # 💥 DESTRUIR EL PANEL DE CONFIGURACIÓN
        # Asegúrate de que 'config_frame' exista y sea la variable correcta que contiene los combos.
        self.config_frame.destroy()

        self.safe_config(self.lbl_status, text=f"Configurado: {src_code} ➡ {tgt_code}. Ahora puede abrir un documento.", bg="#d4edda")

    # --- THREADING CARGA ---
    def load_project(self):
        # Verificación extra por seguridad
        if str(self.btn_next['state']) == 'disabled': return

        file_path = filedialog.askopenfilename(filetypes=[("Word", "*.docx")])
        if not file_path: return

        self.loading_thread = None
        self.loading_result = None

        # Bloqueo temporal durante carga
        self.toggle_app_state("disabled")

        tgt_code = self.project.target_lang
        self.safe_config(self.lbl_status, text=f"Cargando '{os.path.basename(file_path)}'...", bg="#e2e6ea")
        self.progress_bar.pack(side=tk.LEFT, padx=5)
        self.progress_bar.start(15)

        self.loading_thread = threading.Thread(target=self._worker_load_project, args=(file_path,), daemon=True)
        self.loading_thread.start()
        self.after(100, self._check_worker_status)

    def _worker_load_project(self, file_path, resume=True):
        try:
            file_path = os.path.abspath(file_path)
            try:
                with open(file_path, 'a'):
                    pass
            except PermissionError:
                self.loading_result = ("error", "Archivo bloqueado.")
                return
            if self.project.docx_path and file_path != os.path.abspath(self.project.docx_path):
                resume = False
            loaded = self.project.load_project(file_path, resume)
            if loaded:
                self.loading_result = ("success", f"Cargado: {os.path.basename(file_path)}")
            else:
                self.loading_result = ("warning", "Sin segmentos válidos.")
        except Exception as e:
            self.loading_result = ("critical_error", str(e), traceback.format_exc())

    def _check_worker_status(self):
        if self.loading_thread and self.loading_thread.is_alive():
            self.after(100, self._check_worker_status)
            return

        self.progress_bar.stop()
        self.progress_bar.pack_forget()

        if not self.loading_result:
            self.toggle_app_state("normal")
            return

        result_type, message, *extras = self.loading_result

        if result_type == "success":
            self.toggle_app_state("normal")  # Re-enable everything
            self.safe_config(self.lbl_status, text=message, bg="#f0f0f0")
            self.rebuild_treeview()
            self.refresh_view()
        else:
            self.toggle_app_state("normal")  # Reactivar aunque falle para reintentar
            if result_type == "warning":
                messagebox.showwarning("Aviso", message)
            elif result_type == "error":
                messagebox.showerror("Error", message)
            elif result_type == "critical_error":
                messagebox.showerror("Error Crítico", f"{message}\n\n{extras[0]}")

        self.loading_thread = None
        self.loading_result = None

    # --- MT FUNCTION ---
    def translate_mt(self):
        if not self.current_state or not self.current_state["sentence"]["orig"]: return

        target_lang = self.project.target_lang
        self.btn_mt.config(state=tk.DISABLED)
        self.safe_config(self.lbl_status, text=f"🤖 Solicitando a DeepL ({target_lang})...", fg="orange")

        text = self.current_state["sentence"]["orig"]
        threading.Thread(target=self._run_mt_thread, args=(text, target_lang)).start()

    def _run_mt_thread(self, text, lang):
        try:
            res = Utils.get_mt_translation(text, lang)
            self.after(0, lambda: self._mt_done(res))
        except Exception as e:
            self.after(0, lambda: self._mt_error(str(e)))

    def _mt_done(self, result):
        self.txt_target.delete("1.0", tk.END)
        self.txt_target.insert("1.0", result)
        self.btn_mt.config(state=tk.NORMAL)
        self.safe_config(self.lbl_status, text="Traducción recibida.", fg="blue")

    def _mt_error(self, msg):
        self.btn_mt.config(state=tk.NORMAL)
        self.safe_config(self.lbl_status, text=f"Error MT: {msg}", fg="red")

    # --- LÓGICA GUI GENERAL ---
    def rebuild_treeview(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        if not self.project.structure: return
        for i, p_data in enumerate(self.project.structure):
            for j, s_data in enumerate(p_data.get("sentences", [])):
                status = "translated" if s_data.get("trad", "").strip() else "empty"
                node_id = f"{i}-{j}"
                display_id = f"{i + 1}.{j + 1}"
                preview = (s_data["orig"][:50] + '...') if len(s_data["orig"]) > 50 else s_data["orig"]
                self.tree.insert("", "end", iid=node_id, values=(display_id, preview), tags=(status,))
        try:
            current_node = f"{self.project.p_idx}-{self.project.s_idx}"
            self.ignore_tree_event = True
            self.tree.selection_set(current_node)
            self.tree.see(current_node)
            self.ignore_tree_event = False
        except tk.TclError:
            if self.tree.get_children(): self.tree.selection_set(self.tree.get_children()[0])

    def refresh_view(self):
        if self.loading_thread and self.loading_thread.is_alive(): return
        self.current_state = self.project.get_current_state()
        if not self.current_state:

            self.txt_source.config(state='normal');
            self.txt_source.delete('1.0', tk.END);
            self.txt_source.config(state='disabled')
            self.txt_target.delete('1.0', tk.END)
            self.safe_config(self.lbl_tm, text="TM: ...", fg="gray")
            self.safe_config(self.lbl_link, text="")
            self.safe_config(self.lbl_glossary, text="", fg="gray")
            self.txt_notes.delete("1.0", tk.END)
            self.txt_notes.insert("1.0", self.current_state.get("note", ""))

            return

        st = self.current_state
        current_sent = st["sentence"]

        current_iid = f"{st['p_idx']}-{st['s_idx']}"
        for item in self.tree.get_children():
            try:
                tags = list(self.tree.item(item, 'tags'))
                if 'active' in tags:
                    tags.remove('active')
                    self.tree.item(item, tags=tuple(tags))
            except tk.TclError:
                continue

        if self.tree.exists(current_iid):
            try:
                self.ignore_tree_event = True
                self.tree.selection_set(current_iid)
                self.tree.see(current_iid)
                self.ignore_tree_event = False
                current_tags = list(self.tree.item(current_iid, 'tags'))
                if 'active' not in current_tags:
                    current_tags.append('active')
                self.tree.item(current_iid, tags=tuple(current_tags))
            except tk.TclError:
                pass

        self.txt_source.config(state='normal')
        self.txt_source.delete('1.0', tk.END)
        self.txt_source.insert(tk.END, st["paragraph_context"])

        active_text = current_sent["orig"].strip()
        full_text = self.txt_source.get("1.0", tk.END)
        norm_full = re.sub(r'\s+', ' ', full_text)
        norm_active = re.sub(r'\s+', ' ', active_text)
        start_idx = norm_full.find(norm_active)

        if start_idx != -1:
            start_pos = f"1.0 + {start_idx} chars"
            end_pos = f"{start_pos} + {len(active_text)} chars"
            self.txt_source.tag_add("active_segment", start_pos, end_pos)
            self.txt_source.see(start_pos)

        for term, _ in st.get("glossary_matches", []):
            start_g = st["paragraph_context"].lower().find(term.lower())
            if start_g != -1:
                sp = f"1.0 + {start_g} chars"
                ep = f"{sp} + {len(term)} chars"
                self.txt_source.tag_add("glossary_term", sp, ep)

        self.txt_source.config(state='disabled')

        self.txt_target.delete('1.0', tk.END)
        self.txt_target.insert(tk.END, current_sent.get("trad", ""))
        self.txt_target.focus()

        tm_match = st.get("tm_exact")
        tm_fuzzy = st.get("tm_fuzzy", (None, 0.0))
        if tm_match:
            self.safe_config(self.lbl_tm, text=f"★ TM 100%: {tm_match}", fg="green")
        elif tm_fuzzy[0]:
            self.safe_config(self.lbl_tm, text=f"⚠ TM {int(tm_fuzzy[1] * 100)}%: {tm_fuzzy[0]}", fg="#e6b800")
        else:
            self.safe_config(self.lbl_tm, text="TM: Sin coincidencias", fg="gray")

        egw_data = Utils.get_egw_url(st["orig_text"])
        bible_data = st.get("bible_data")  # Obtenemos el nuevo dato del estado

        link_data = None
        text_label = ""
        color = ""

        if bible_data and bible_data["en"]:
            link_data = bible_data
            text_label = "✝️ Ver Cita Bíblica (RVR60)"
            color = "green"
        elif egw_data["en"]:
            link_data = egw_data
            if egw_data.get("type") == "google":
                text_label = "🔍 Buscar en Google (Libro EGW no listado)"
                color = "purple"
            else:
                text_label = "📖 Ver en EGW Writings [EN]"
                color = "blue"

        if link_data:
            self.safe_config(self.lbl_link, text=text_label, fg=color)
            self.lbl_link.bind("<Button-1>", lambda e: webbrowser.open(link_data["en"]))
        else:
            # Si no hay cita detectada, limpiamos el enlace
            self.safe_config(self.lbl_link, text="")
            self.lbl_link.unbind("<Button-1>")

        if st.get("glossary_matches"):
            self.safe_config(self.lbl_glossary, text="Glosario encontrado", fg="#d9534f")
        else:
            self.safe_config(self.lbl_glossary, text="", fg="gray")

        if hasattr(self, 'txt_notes'):  # Seguridad por si el widget no existe aún
            self.txt_notes.delete("1.0", tk.END)
            self.txt_notes.insert("1.0", st.get("note", ""))

    def save_current_segment(self):
        if not self.current_state: return

        # 1. Leer el texto de la traducción solo una vez
        translation_text = self.txt_target.get("1.0", tk.END).strip()

        # 2. Guardar la traducción en el backend (FIX del TypeError anterior)
        # Solo pasamos el texto, ya que el ProjectManager tiene los índices internos.
        self.project.update_translation(translation_text)

        # 3. Forzar el guardado de la nota (FIX de persistencia)
        self.save_current_note()

        # --- Actualización del Treeview ---
        node_id = f"{self.current_state['p_idx']}-{self.current_state['s_idx']}"
        tag = "translated" if translation_text else "empty"

        # 4. Actualizar el estado visual de "tiene nota" y "traducido"
        self.update_treeview_status()

        # 5. Actualizar la etiqueta 'translated' o 'empty' si el nodo existe
        if self.tree.exists(node_id):
            try:
                current_tags = list(self.tree.item(node_id, 'tags'))

                # Limpiar etiquetas de estado anteriores
                if 'translated' in current_tags: current_tags.remove('translated')
                if 'empty' in current_tags: current_tags.remove('empty')

                # Insertar la nueva etiqueta de estado al inicio
                current_tags.insert(0, tag)
                self.tree.item(node_id, tags=tuple(current_tags))
            except tk.TclError:
                pass

    def on_tree_select(self, event):
        if self.ignore_tree_event: return
        sel = self.tree.selection()
        if not sel: return
        try:
            p_idx, s_idx = map(int, sel[0].split('-'))
            if p_idx == self.project.p_idx and s_idx == self.project.s_idx: return
            if self.current_state: self.save_current_segment()
            if self.project.goto_segment(p_idx, s_idx): self.refresh_view()
        except ValueError:
            pass

    def on_next_segment(self):
        if not self.current_state: return
        self.save_current_segment()
        st = self.current_state
        trans = self.txt_target.get("1.0", tk.END).strip()
        missing = self.project.glossary.check_qa(st["sentence"]["orig"], trans)
        if missing:
            if not messagebox.askyesno("QA", f"Faltan términos: {', '.join([m[0] for m in missing])}. ¿Seguir?"): return
        if self.project.next_segment():
            self.refresh_view()
        else:
            messagebox.showinfo("Fin", "Documento terminado.")

    def on_prev_segment(self):
        if not self.current_state: return
        self.save_current_segment()
        self.project.prev_segment()
        self.refresh_view()

    def copy_source_to_target(self):
        if self.current_state:
            src = self.current_state["sentence"]["orig"]
            self.txt_target.delete('1.0', tk.END)
            self.txt_target.insert('1.0', src)

    def use_tm_suggestion(self):
        if self.current_state:
            tm = self.current_state.get("tm_exact") or self.current_state.get("tm_fuzzy", (None,))[0]
            if tm:
                self.txt_target.delete('1.0', tk.END)
                self.txt_target.insert('1.0', tm)

    def run_live_qa(self, event=None):
        if not self.current_state: return
        trans = self.txt_target.get("1.0", tk.END).strip()
        missing = self.project.glossary.check_qa(self.current_state["sentence"]["orig"], trans)
        if missing:
            self.safe_config(self.lbl_glossary, text=f"Faltan: {len(missing)} términos", fg="red")
        else:
            self.safe_config(self.lbl_glossary, text="QA OK", fg="green")

    def open_concordance(self):
        win = tk.Toplevel(self)
        win.title("Buscar")
        tk.Label(win, text="Texto:").pack()
        e = tk.Entry(win);
        e.pack(fill=tk.X)
        t = scrolledtext.ScrolledText(win, height=10);
        t.pack()

        def search(ev=None):
            q = e.get()
            res = self.project.tm.search_concordance(q)
            t.delete('1.0', tk.END)
            if res:
                for s, tr in res: t.insert(tk.END, f"{s}\n-> {tr}\n\n")
            else:
                t.insert(tk.END, "Sin resultados.")

        e.bind("<Return>", search)

    def exit_app(self):
        self.save_current_segment()
        self.project.save_progress()
        try:
            p = self.project.export_docx()
            messagebox.showinfo("Info", f"Exportado: {p}")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.destroy()

    def ask_goto_segment(self):
        from tkinter import simpledialog
        target = simpledialog.askstring("Ir a Segmento", "Ingrese número de segmento (ej. 4.3):")
        if target:
            if self.project.go_to_segment_id(target):
                self.save_current_segment()  # Guardar antes de saltar
                self.refresh_view()
            else:
                messagebox.showwarning("Navegación", "Segmento no encontrado o formato inválido.")

    def open_project_search(self):
        # Ventana modal de búsqueda
        search_win = tk.Toplevel(self)
        search_win.title("Buscar en Proyecto")
        search_win.geometry("400x300")

        tk.Label(search_win, text="Texto a buscar:").pack(pady=5)
        entry_q = tk.Entry(search_win, width=40)
        entry_q.pack(pady=5)
        entry_q.focus_set()

        # Radio buttons para origen/destino
        var_type = tk.StringVar(value="source")
        tk.Radiobutton(search_win, text="Buscar en Origen", variable=var_type, value="source").pack()
        tk.Radiobutton(search_win, text="Buscar en Traducción", variable=var_type, value="target").pack()

        listbox = tk.Listbox(search_win, width=50, height=10)
        listbox.pack(pady=5, padx=5, fill=tk.BOTH, expand=True)

        def perform_search(event=None):
            q = entry_q.get()
            listbox.delete(0, tk.END)
            results = self.project.search_in_project(q, var_type.get())

            if not results:
                listbox.insert(tk.END, "Sin resultados.")
                return

            for p, s, text in results:
                display = f"[{p + 1}.{s + 1}] {text}"
                listbox.insert(tk.END, display)
                # Guardamos los índices como data oculta (no nativo en listbox, usamos un dict externo o parseamos)

        def on_select(event):
            sel = listbox.curselection()
            if not sel: return
            text_item = listbox.get(sel[0])
            # Extraer ID del string "[4.3] Texto..."
            match = re.match(r'\[(\d+)\.(\d+)\]', text_item)
            if match:
                self.save_current_segment()
                p_idx = int(match.group(1)) - 1
                s_idx = int(match.group(2)) - 1
                self.project.goto_segment(p_idx, s_idx)
                self.refresh_view()
                search_win.destroy()  # Cerrar al ir

        btn_search = tk.Button(search_win, text="Buscar", command=perform_search)
        btn_search.pack()

        entry_q.bind("<Return>", perform_search)
        listbox.bind("<Double-Button-1>", on_select)

if __name__ == "__main__":
    app = CATApp()
    app.mainloop()