import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import os
import re
import threading
import ctypes
import shutil
import json
import subprocess

# --- Clipboard file drop (para arrastar/colar arquivos no Windows) ---
def _set_clipboard_files(paths):
    """
    Coloca arquivos no clipboard do Windows (CF_HDROP).
    Isso permite colar (Ctrl+V) no Explorer/WhatsApp Desktop.
    """
    try:
        import tkinter as _tk
        r = _tk.Tk()
        r.withdraw()
        r.clipboard_clear()
        # Usa formato especial do Tk para lista de arquivos
        # (o Windows converte para CF_HDROP)
        r.clipboard_append(' '.join([f'{{{p}}}' for p in paths]))
        r.update()
        r.destroy()
        return True
    except Exception:
        return False

# --- CONFIGURAÇÃO PARA ÍCONE NA BARRA DE TAREFAS ---
try:
    myappid = 'triskel.gerenciador.projetos.v9'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except:
    pass

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class JanelaConfig(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Configurações de Caminhos")
        self.geometry("550x300")
        self.parent = parent
        self.after(200, lambda: self.focus_force())

        ctk.CTkLabel(self, text="EDITAR DIRETÓRIOS BASE", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=15)

        self.entries = {}
        campos = [
            ("Drive Z:", "base_path_Z"),
            ("Kickoff:", "base_path_Kickoff"),
            ("Suprimentos:", "base_path_Suprimentos"),
]

        for label_text, attr in campos:
            frame = ctk.CTkFrame(self, fg_color="transparent")
            frame.pack(fill="x", padx=20, pady=5)
            ctk.CTkLabel(frame, text=label_text, width=100).pack(side="left")
            entry = ctk.CTkEntry(frame)
            entry.insert(0, getattr(parent, attr))
            entry.pack(side="right", fill="x", expand=True, padx=5)
            self.entries[attr] = entry

        ctk.CTkButton(self, text="SALVAR", fg_color="#1e7145", command=self.salvar).pack(pady=20)

    def salvar(self):
        for attr, entry in self.entries.items():
            setattr(self.parent, attr, entry.get())
        config = {k: v.get() for k, v in self.entries.items()}
        with open("config_caminhos.json", "w") as f:
            json.dump(config, f)
        messagebox.showinfo("Sucesso", "Caminhos atualizados!")
        self.destroy()

class JanelaRevisoes(ctk.CTkToplevel):
    def __init__(self, parent, item_nome, item_path):
        super().__init__(parent)
        self.title(f"Arquivos - {item_nome}")
        self.geometry("550x480") 
        self.item_path = item_path
        self.after(200, lambda: self.focus_force())

        ctk.CTkLabel(self, text=f"ITEM: {item_nome}", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(10, 0))

        self.frame_botoes = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_botoes.pack(pady=10, padx=20, fill="x")

        self.btn_raiz = ctk.CTkButton(self.frame_botoes, text="📂 PASTA DO ITEM", 
                                      height=35, fg_color="#2c3e50", hover_color="#1a252f",
                                      command=lambda: os.startfile(self.item_path))
        self.btn_raiz.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self.btn_rev_sel = ctk.CTkButton(self.frame_botoes, text="📂 PASTA DA REVISÃO", 
                                         height=35, fg_color="#5a6a7a", hover_color="#3a4a5a",
                                         command=self.abrir_pasta_revisao_atual)
        self.btn_rev_sel.pack(side="right", expand=True, fill="x", padx=(5, 0))

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=10, pady=5)
        self.container.grid_columnconfigure(1, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        self.frame_esq = ctk.CTkFrame(self.container, width=140)
        self.frame_esq.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        
        ctk.CTkLabel(self.frame_esq, text="REVISÕES", font=ctk.CTkFont(weight="bold")).pack(pady=5)
        self.list_revs = tk.Listbox(self.frame_esq, bg="#1e1e1e", fg="white", font=("Segoe UI", 9, "bold"), borderwidth=0)
        self.list_revs.pack(fill="both", expand=True, padx=5, pady=5)
        self.list_revs.bind("<<ListboxSelect>>", self.atualizar_arquivos)

        self.frame_dir = ctk.CTkFrame(self.container)
        self.frame_dir.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        
        ctk.CTkLabel(self.frame_dir, text="CONTEÚDO DA REVISÃO", font=ctk.CTkFont(weight="bold")).pack(pady=5)
        self.scroll_arquivos = ctk.CTkScrollableFrame(self.frame_dir, fg_color="#101010")
        self.scroll_arquivos.pack(fill="both", expand=True, padx=5, pady=5)

        # Ajusta cores conforme tema atual (importante pro modo Claro)
        self.aplicar_tema(ctk.get_appearance_mode())


        self.listar_revisoes()

    def aplicar_tema(self, mode=None):
        mode = mode or ctk.get_appearance_mode()
        is_light = str(mode).lower().startswith("light")

        bg_panel = "#ffffff" if is_light else "#1e1e1e"
        fg_text = "#111827" if is_light else "white"

        try:
            self.list_revs.configure(bg=bg_panel, fg=fg_text, selectbackground="#93c5fd" if is_light else "#3b82f6", selectforeground="#111827" if is_light else "white")
        except:
            pass

        try:
            self.scroll_arquivos.configure(fg_color="#ffffff" if is_light else "#101010")
        except:
            pass

        # Pequenos ajustes nos botões (mantém layout)
        try:
            if is_light:
                self.btn_raiz.configure(fg_color="#2f80ed", hover_color="#2563eb")
                self.btn_rev_sel.configure(fg_color="#64748b", hover_color="#475569")
        except:
            pass

    def _start_drag(self, path):
        # Copia o arquivo para o clipboard como arquivo (para colar fora do app)
        _set_clipboard_files([os.path.normpath(path)])

    def _bind_drag(self, widget, path):
        # Começa "arrasto": ao mover o mouse segurando, copia pro clipboard.
        state = {"dragged": False, "x": 0, "y": 0}
        def on_press(e):
            state["dragged"] = False
            state["x"], state["y"] = e.x_root, e.y_root
        def on_motion(e):
            if state["dragged"]:
                return
            if abs(e.x_root - state["x"]) + abs(e.y_root - state["y"]) > 6:
                state["dragged"] = True
                self._start_drag(path)
        widget.bind("<ButtonPress-1>", on_press)
        widget.bind("<B1-Motion>", on_motion)

    def listar_revisoes(self):
        try:
            if os.path.exists(self.item_path):
                revs = [d for d in os.listdir(self.item_path) if os.path.isdir(os.path.join(self.item_path, d))]
                for r in sorted(revs):
                    if any(x in r.upper() for x in ["REV", "REVISAO"]):
                        self.list_revs.insert(tk.END, r.upper())
        except: pass

    def abrir_pasta_revisao_atual(self):
        selecao = self.list_revs.curselection()
        if not selecao:
            messagebox.showwarning("Aviso", "Selecione uma revisão na lista abaixo primeiro.")
            return
        rev_nome = self.list_revs.get(selecao)
        path_rev = os.path.join(self.item_path, rev_nome)
        if os.path.exists(path_rev): os.startfile(path_rev)

    def atualizar_arquivos(self, event):
        selecao = self.list_revs.curselection()
        if not selecao: return
        rev_nome = self.list_revs.get(selecao)
        path_rev = os.path.join(self.item_path, rev_nome)
        for widget in self.scroll_arquivos.winfo_children(): widget.destroy()
        threading.Thread(target=self.carregar_lista_real, args=(path_rev,), daemon=True).start()

    def carregar_lista_real(self, path_rev):
        ext_map = {
            '.dwg': ('#d35400', 'AUTOCAD'), 
            '.elk': ('#1f538d', 'EPLAN'), 
            '.xlsm': ('#1e7145', 'EXCEL/LM'), 
            '.pdf': ('#c0392b', 'PDF')
        }
        encontrados = {ext: [] for ext in ext_map}
        if os.path.exists(path_rev):
            for root, dirs, files in os.walk(path_rev):
                if root.count(os.sep) - path_rev.count(os.sep) > 3: continue
                for f in files:
                    ext = os.path.splitext(f)[1].lower() 
                    if ext in ext_map: encontrados[ext].append(os.path.join(root, f))
        self.after(0, lambda: self.exibir_na_tela(encontrados, ext_map))

    def exibir_na_tela(self, dados, ext_map):
        for ext, (cor, label_tipo) in ext_map.items():
            arquivos = dados[ext]
            lbl = ctk.CTkLabel(self.scroll_arquivos, text=f"--- {label_tipo} ---", text_color="#777777", font=ctk.CTkFont(size=10), anchor="w")
            lbl.pack(fill="x", padx=5, pady=(5,0))
            if arquivos:
                for path in arquivos:
                    btn = ctk.CTkButton(self.scroll_arquivos, text=os.path.basename(path), fg_color=cor, hover_color="#444444", anchor="w")
                    btn.pack(fill="x", pady=1, padx=5)
                    btn.bind("<Double-1>", lambda e, p=path: os.startfile(p))
                    btn.bind("<Button-3>", lambda e, p=path: subprocess.run(['explorer', '/select,', os.path.normpath(p)]))
                    self._bind_drag(btn, path)
            else:
                ctk.CTkLabel(self.scroll_arquivos, text=f"❌ Sem arquivos {label_tipo}", text_color="#444444", font=ctk.CTkFont(size=10, slant="italic")).pack()

class GerenciadorProjetos(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Gerenciador de Projetos")
        self.geometry("480x850")

        # CAMINHOS PADRÃO (CARREGADOS VIA CONFIG SE EXISTIR)
        self.base_path_Z = r"Z:\PROJETOS\4 - CASES TRISKEL"
        self.base_path_Kickoff = r"H:\Drives compartilhados\Kickoff"
        self.base_path_Suprimentos = r"H:\Drives compartilhados\Suprimentos\1 - LPC (LIBERAÇÃO PARA COMPRA)"
        # CACHES para acelerar busca em rede
        self._year_folder_name_cache = {}  # {'2022': '<pasta do ano>'}
        self._ano_cache = {}  # {'2022': {'p_ano': str, 'candidatos': [str], 'tkl_index': {}}}
        # Produção Elétrica (base padrão)
        self.base_path_ProducaoEletricaRoot = r"G:\Drives compartilhados\Projetos Elétricos (PDF)"
        self.carregar_config_inicial()

        # CONFIG (MODO DE CÓPIA - 1/2/3)
        self.copy_mode_file = "config_copia.json"
        self.copy_mode = 2
        self.carregar_modo_copia_inicial()

        self.historico_file = "historico_busca.json"
        self.projeto_path = ""
        self.current_tkl = ""
        self.current_year = ""
        self.janela_rev = None
        self.todos_itens = []

        self.bind("<Button-1>", self.clique_fora)

        # --- CABEÇALHO ---
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(self.header, text="GERENCIADOR DE PROJETOS", font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")
        self.switch_tema = ctk.CTkSwitch(self.header, text="TEMA", command=self.alternar_tema)
        self.switch_tema.pack(side="right")

        # --- BUSCA ---
        self.frame_busca_container = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_busca_container.pack(fill="x", padx=20, pady=10)

        self.frame_entry_bg = ctk.CTkFrame(self.frame_busca_container, fg_color="#333333", height=40)
        self.frame_entry_bg.pack(side="left", fill="x", expand=True)

        self.entry_id = ctk.CTkEntry(self.frame_entry_bg, placeholder_text="TKL (Ex: 0155.25) ou Ano (Ex: 25)", 
                                    height=38, border_width=0, fg_color="transparent")
        self.entry_id.pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.entry_id.bind("<Return>", lambda e: self.iniciar_busca())

        self.btn_hist = ctk.CTkOptionMenu(self.frame_entry_bg, values=["▼"], width=35, height=30, 
                                         dynamic_resizing=False, command=self.selecionar_historico,
                                         fg_color="#333333", button_color="#333333", 
                                         button_hover_color="#444444", text_color="#3498db")
        self.btn_hist.pack(side="right", padx=2)
        self.btn_hist.set("▼")
        self.carregar_historico_menu()

        self.btn_limpar_busca = ctk.CTkButton(self.frame_busca_container, text="X", width=30, height=40, fg_color="#333333", hover_color="#c0392b", command=self.reset_total_busca)
        self.btn_limpar_busca.pack(side="left", padx=(5, 0))

        ctk.CTkButton(self, text="BUSCAR / ABRIR", height=40, command=self.iniciar_busca).pack(fill="x", padx=20, pady=5)
        
        self.label_status_ver = ctk.CTkEntry(self, font=ctk.CTkFont(weight="bold"), 
                                            fg_color="transparent", border_width=0, 
                                            justify="center", height=25)
        self.label_status_ver.insert(0, "AGUARDANDO BUSCA...")
        self.label_status_ver.configure(state="readonly")
        self.label_status_ver.pack(fill="x", pady=(5, 0), padx=20)

        self.entry_path_copy = ctk.CTkEntry(self, height=25, fg_color="transparent", border_width=0, justify="center",
                                            text_color="#555555", font=ctk.CTkFont(size=10))
        self.entry_path_copy.pack(fill="x", padx=40, pady=(0, 5))
        self.entry_path_copy.configure(state="readonly")

        # --- FILTRO ---
        self.frame_filtro = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_filtro.pack(fill="x", padx=20, pady=(10, 0))

        self.entry_filtro = ctk.CTkEntry(self.frame_filtro, placeholder_text="Filtrar", height=30)
        self.entry_filtro.pack(side="left", fill="x", expand=True)
        self.entry_filtro.bind("<KeyRelease>", self.filtrar_itens)

        self.btn_limpar_filtro = ctk.CTkButton(self.frame_filtro, text="X", width=25, height=30, fg_color="#333333", hover_color="#555555", command=self.limpar_filtro)
        self.btn_limpar_filtro.pack(side="left", padx=2)

        # Menu de cópia (⋮) ao lado do "X" do filtro + indicador pequeno (1/2/3)
        self.btn_menu_copia = ctk.CTkButton(self.frame_filtro, text="⋮", width=28, height=30,
                                            fg_color="#333333", hover_color="#555555",
                                            command=self.mostrar_menu_copia)
        self.btn_menu_copia.pack(side="left", padx=(2, 0))

        self.label_modo_copia = ctk.CTkLabel(self.frame_filtro, text=str(self.copy_mode),
                                             font=ctk.CTkFont(size=12, weight="bold"),
                                             text_color="#cccccc")
        self.label_modo_copia.pack(side="left", padx=(4, 0))

        # --- LISTBOX ---
        self.frame_list = tk.Frame(self, bg="#2b2b2b")
        self.frame_list.pack(padx=20, pady=5, fill="both", expand=True)
        self.listbox = tk.Listbox(self.frame_list, bg="#1e1e1e", fg="white", selectmode="extended", 
                                  selectbackground="#1f538d", font=("Segoe UI", 11, "bold"), borderwidth=0)
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.bind("<Double-1>", self.on_item_double_click)
        self.listbox.bind("<Button-1>", self.toggle_selection)
        
        scroll = tk.Scrollbar(self.frame_list, command=self.listbox.yview)
        scroll.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scroll.set)

        # --- CÓPIA (CTRL+C e BOTÃO DIREITO) ---
        self.menu_contexto = tk.Menu(self, tearoff=0)
        self.menu_contexto.add_command(label="Copiar", command=self.copiar_selecao)
        self.listbox.bind("<Control-c>", self.on_ctrl_c)
        self.listbox.bind("<Button-3>", self.mostrar_menu_contexto)

                # --- GRADE DE BOTÕES ---
        self.frame_grid_botoes = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_grid_botoes.pack(fill="x", padx=20, pady=10)
        self.frame_grid_botoes.grid_columnconfigure((0, 1), weight=1)

        # Linha superior: PDF + botões pequenos (Config e Menu de Cópia)
        
        # Linha superior: Config acima do PDF (não ao lado)
        self.frame_pdf_top = ctk.CTkFrame(self.frame_grid_botoes, fg_color="transparent")
        self.frame_pdf_top.grid(row=0, column=0, columnspan=2, padx=0, pady=0, sticky="nsew")
        self.frame_pdf_top.grid_columnconfigure(0, weight=1)
        self.frame_pdf_top.grid_columnconfigure(1, weight=0)

        self.btn_config = ctk.CTkButton(self.frame_pdf_top, text="⚙️", width=34, height=28,
                                        fg_color="transparent", hover_color="#333333",
                                        command=lambda: JanelaConfig(self))
        self.btn_config.grid(row=0, column=0, sticky="e", pady=0)

        self.btn_pdf = ctk.CTkButton(self.frame_pdf_top, text="PDF ÚLTIMA REVISÃO", height=40,
                                     command=self.abrir_pdf_revisao, fg_color="#c0392b")
        self.btn_pdf.grid(row=1, column=0, padx=5, pady=4, sticky="nsew")


        self.btn_pasta = self.criar_botao_grid("PASTA DO PROJETO", self.abrir_pasta_projeto, row=1, col=0, cor="#1f77b4")
        self.btn_producao = self.criar_botao_grid("PRODUÇÃO ELÉTRICA", self.abrir_producao, row=1, col=1, cor="#2980b9")

        self.btn_kickoff = self.criar_botao_grid("KICKOFF", self.abrir_kickoff, row=2, col=0, cor="#2c3e50")
        self.btn_suprimentos = self.criar_botao_grid("SUPRIMENTOS", self.abrir_suprimentos, row=2, col=1, cor="#1e7145")

        self.btn_impressao = self.criar_botao_grid("IMPRESSÃO", self.preparar_impressao, row=3, col=0, cor="#e67e22")
        self.btn_copiar = self.criar_botao_grid("COPIAR PARA :", None, row=3, col=1, cor="#1f77b4")


        # Aplica tema inicial (ajusta melhor o modo Claro)
        self.aplicar_tema(ctk.get_appearance_mode())
    def carregar_config_inicial(self):
        if os.path.exists("config_caminhos.json"):
            try:
                with open("config_caminhos.json", "r") as f:
                    data = json.load(f)
                    self.base_path_Z = data.get("base_path_Z", self.base_path_Z)
                    self.base_path_Kickoff = data.get("base_path_Kickoff", self.base_path_Kickoff)
                    self.base_path_Suprimentos = data.get("base_path_Suprimentos", self.base_path_Suprimentos)
            except:
                pass

    def criar_botao_grid(self, texto, comando, row, col, cor=None):
        btn = ctk.CTkButton(self.frame_grid_botoes, text=texto, height=40, command=comando)
        if cor: btn.configure(fg_color=cor)
        btn.grid(row=row, column=col, padx=5, pady=4, sticky="nsew")
        return btn

    def carregar_modo_copia_inicial(self):
        if os.path.exists(self.copy_mode_file):
            try:
                with open(self.copy_mode_file, "r") as f:
                    data = json.load(f)
                modo = int(data.get("copy_mode", self.copy_mode))
                if modo in (1, 2, 3):
                    self.copy_mode = modo
            except:
                pass

    def salvar_modo_copia(self):
        try:
            with open(self.copy_mode_file, "w") as f:
                json.dump({"copy_mode": self.copy_mode}, f)
        except:
            pass

    def set_copy_mode(self, modo):
        if modo not in (1, 2, 3):
            return
        self.copy_mode = modo
        if hasattr(self, "label_modo_copia"):
            self.label_modo_copia.configure(text=str(modo))
        self.salvar_modo_copia()

    def mostrar_menu_copia(self):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="1  COPIAR TAG", command=lambda: self.set_copy_mode(1))
        menu.add_command(label="2  COPIAR ITEM + TAG", command=lambda: self.set_copy_mode(2))
        menu.add_command(label="3  COPIAR ITEM + TAG + REV. ATUAL", command=lambda: self.set_copy_mode(3))
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()

    def on_ctrl_c(self, event=None):
        self.copiar_selecao()
        return "break"

    def mostrar_menu_contexto(self, event):
        # Garante que o item clicado esteja selecionado (sem mudar seleção múltipla existente)
        idx = self.listbox.nearest(event.y)
        if idx >= 0 and not self.listbox.selection_includes(idx):
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(idx)
        try:
            self.menu_contexto.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu_contexto.grab_release()

    def _extrair_tag(self, nome_item):
        m = re.match(r'^\s*ITEM\s*\d+\s*-\s*(.+)\s*$', nome_item.strip(), flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return nome_item.strip()

    def _ultima_revisao_letra(self, item_path):
        # Pega a maior letra (A..Z) do final do nome das subpastas
        try:
            if not os.path.exists(item_path):
                return ""
            subdirs = [d for d in os.listdir(item_path) if os.path.isdir(os.path.join(item_path, d))]
            revisoes = []
            for d in subdirs:
                dn = d.strip()
                if re.search(r'[A-Za-z]$', dn):
                    revisoes.append(dn)
            if not revisoes:
                return ""
            letras = [r.strip()[-1].upper() for r in revisoes if r.strip()]
            letras = [l for l in letras if 'A' <= l <= 'Z']
            if not letras:
                return ""
            return max(letras)
        except:
            return ""

    def copiar_selecao(self):
        selecionados = self.listbox.curselection()
        if not selecionados:
            messagebox.showwarning("Aviso", "Selecione ao menos um item na lista.")
            return

        resultado = []
        for i in selecionados:
            nome_item = self.listbox.get(i).strip()

            if self.copy_mode == 1:
                resultado.append(self._extrair_tag(nome_item))

            elif self.copy_mode == 2:
                # padrão do app (igual o Ctrl+C normal)
                resultado.append(nome_item)

            elif self.copy_mode == 3:
                tag = self._extrair_tag(nome_item)
                item_path = os.path.join(self.projeto_path, nome_item)
                letra = self._ultima_revisao_letra(item_path)
                if letra:
                    resultado.append(f"{nome_item} - REV. {letra}")
                else:
                    resultado.append(f"{nome_item} - REV. ?")

        texto = "\r\n".join(resultado)
        try:
            self.clipboard_clear()
            self.clipboard_append(texto)
            self.update()
        except:
            pass

    def clique_fora(self, event):
        if not isinstance(event.widget, (tk.Listbox, tk.Entry, ctk.CTkEntry)):
            self.listbox.selection_clear(0, tk.END)

    def toggle_selection(self, event):
        idx = self.listbox.nearest(event.y)
        if self.listbox.selection_includes(idx):
            self.after(10, lambda: self.listbox.selection_clear(idx))

    def reset_total_busca(self):
        self.entry_id.delete(0, tk.END)
        self.listbox.delete(0, tk.END)
        self.todos_itens = []
        self.projeto_path = ""
        self.current_tkl = ""
        self.limpar_filtro()
        self.atualizar_status("AGUARDANDO BUSCA...", cor="gray")

    def limpar_filtro(self):
        self.entry_filtro.delete(0, tk.END)
        self.filtrar_itens()

    def carregar_historico_menu(self):
        try:
            if os.path.exists(self.historico_file):
                with open(self.historico_file, "r") as f:
                    hist = json.load(f)
                valores = ["HISTÓRICO"] + hist + ["LIMPAR TUDO"]
                self.btn_hist.configure(values=valores)
        except: pass

    def selecionar_historico(self, valor):
        if valor == "LIMPAR TUDO":
            if os.path.exists(self.historico_file): os.remove(self.historico_file)
            self.btn_hist.configure(values=["▼"])
        elif valor not in ["▼", "HISTÓRICO"]:
            self.entry_id.delete(0, tk.END)
            self.entry_id.insert(0, valor)
            self.iniciar_busca()
        self.btn_hist.set("▼")

    def salvar_no_historico(self, termo):
        try:
            hist = []
            if os.path.exists(self.historico_file):
                with open(self.historico_file, "r") as f:
                    hist = json.load(f)
            if termo in hist: hist.remove(termo)
            hist.insert(0, termo)
            hist = hist[:5]
            with open(self.historico_file, "w") as f:
                json.dump(hist, f)
            self.carregar_historico_menu()
        except: pass

    def filtrar_itens(self, event=None):
        termo = self.entry_filtro.get().upper()
        self.listbox.delete(0, tk.END)
        for it in self.todos_itens:
            if termo in it:
                self.listbox.insert(tk.END, it)

    def atualizar_status(self, ilustra, caminho="", cor="green"):
        self.label_status_ver.configure(state="normal")
        self.label_status_ver.delete(0, tk.END)
        self.label_status_ver.insert(0, ilustra)
        self.label_status_ver.configure(text_color=cor, state="readonly")
        self.entry_path_copy.configure(state="normal")
        self.entry_path_copy.delete(0, tk.END)
        self.entry_path_copy.insert(0, caminho)
        self.entry_path_copy.configure(state="readonly")

    def alternar_tema(self):
        mode = "Light" if self.switch_tema.get() == 1 else "Dark"
        ctk.set_appearance_mode(mode)
        self.aplicar_tema(mode)

    def aplicar_tema(self, mode=None):
        """Ajusta cores do tema (sem mudar layout/funções)."""
        mode = mode or ctk.get_appearance_mode()
        is_light = str(mode).lower().startswith("light")

        # Cores principais
        bg_main = "#f4f6f9" if is_light else "#1e1e1e"
        bg_panel = "#ffffff" if is_light else "#202020"
        fg_text = "#111827" if is_light else "white"
        fg_muted = "#6b7280" if is_light else "#999999"

        # Fundo da janela e frames
        try: self.configure(fg_color=bg_main)
        except: pass
        try: self.frame_list.configure(bg=bg_main)
        except: pass
        try: self.header.configure(fg_color=bg_main)
        except: pass
        try: self.frame_filtro.configure(fg_color=bg_main)
        except: pass

        # Listbox principal
        try:
            self.listbox.configure(bg=bg_panel, fg=fg_text, selectbackground="#93c5fd" if is_light else "#3b82f6", selectforeground="#111827" if is_light else "white")
        except:
            pass

        # Status/labels que existem
        try: self.status_label.configure(text_color=fg_muted)
        except: pass
        try: self.path_label.configure(text_color=fg_muted)
        except: pass

        # Botões pequenos do filtro (X e ⋮) – mantém discretos no claro
        try: self.btn_limpar_filtro.configure(fg_color="#e5e7eb" if is_light else "#333333", hover_color="#d1d5db" if is_light else "#555555", text_color="#111827" if is_light else "white")
        except: pass
        try: self.btn_menu_copia.configure(fg_color="#e5e7eb" if is_light else "#333333", hover_color="#d1d5db" if is_light else "#555555", text_color="#111827" if is_light else "white")
        except: pass

        # Força atualização das janelas de revisão abertas (se houver)
        try:
            if self.janela_rev is not None and self.janela_rev.winfo_exists():
                self.janela_rev.aplicar_tema(mode)
        except:
            pass

    def on_item_double_click(self, event):
        selecao = self.listbox.curselection()
        if not selecao: return
        item_nome = self.listbox.get(selecao[-1])
        item_path = os.path.join(self.projeto_path, item_nome)
        if self.janela_rev is not None and self.janela_rev.winfo_exists(): self.janela_rev.destroy()
        self.janela_rev = JanelaRevisoes(self, item_nome, item_path)

    def iniciar_busca(self): threading.Thread(target=self.executar_busca, daemon=True).start()

    def executar_busca(self):
        input_id = self.entry_id.get().strip().upper()
        if not input_id:
            return

        self.salvar_no_historico(input_id)

        def _reset_resultados():
            self.current_tkl = ""
            self.projeto_path = ""
            self.todos_itens = []
            try:
                self.listbox.delete(0, tk.END)
            except:
                pass
            try:
                self.entry_filtro.delete(0, tk.END)
            except:
                pass

        # Atalho: abrir pasta do ano quando usuário digita "22", "23", etc.
        if re.match(r'^\d{2}$', input_id):
            _reset_resultados()  # some a TKL/projeto anterior da tela
            ano_full = f"20{input_id}"
            self.atualizar_status(f"ABRINDO ANO {ano_full}", cor="green")
            try:
                # Cache do nome da pasta do ano (evita listdir repetido em rede)
                if not self._year_folder_name_cache:
                    for f in os.listdir(self.base_path_Z):
                        up = f.upper()
                        m = re.search(r'PROJETOS\s+(20\d{2})', up)
                        if m:
                            self._year_folder_name_cache[m.group(1)] = f
                year_folder = self._year_folder_name_cache.get(ano_full)
                if year_folder:
                    p_ano = os.path.join(self.base_path_Z, year_folder)
                    os.startfile(p_ano)
                    self.atualizar_status(f"ABRINDO ANO {ano_full}", p_ano, cor="green")
            except Exception as e:
                self.atualizar_status(f"ERRO: {e}", cor="red")
            return

        # Normaliza TKL (ex: 0155.25 -> TKL0155.25)
        if "." in input_id:
            self.current_tkl = input_id if input_id.startswith("TKL") else f"TKL{input_id}"
            y_suffix = self.current_tkl.split('.')[-1]
        else:
            self.current_tkl = "TKL" + input_id[-5:] if len(input_id) >= 5 else input_id
            y_suffix = self.current_tkl[3:5] if len(self.current_tkl) > 5 else "25"

        self.current_year = f"20{y_suffix}"
        self.atualizar_status("BUSCANDO...", cor="yellow")

        def _build_ano_cache(p_ano: str):
            try:
                lvl1 = [e for e in os.scandir(p_ano) if e.is_dir()]
            except:
                return {"p_ano": p_ano, "candidatos": [], "tkl_index": {}}

            candidatos = []
            for e in lvl1:
                n = e.name.upper()
                if "INSTALA" in n or "FR " in n or "FR-" in n:
                    candidatos.append(e.path)

            if not candidatos:
                candidatos = [e.path for e in lvl1]

            return {"p_ano": p_ano, "candidatos": candidatos, "tkl_index": {}}

        def _find_tkl_dir_cached(ano_cache: dict, tkl_upper: str) -> str:
            # 0) cache direto
            cached = ano_cache["tkl_index"].get(tkl_upper)
            if cached and os.path.isdir(cached):
                return cached

            # 1) procura rápido no 1º nível dos candidatos (quase sempre resolve)
            for base in ano_cache["candidatos"]:
                try:
                    with os.scandir(base) as it:
                        for e in it:
                            if e.is_dir() and e.name.upper().startswith(tkl_upper):
                                ano_cache["tkl_index"][tkl_upper] = e.path
                                return e.path
                except:
                    continue

            # 2) fallback em thread: BFS com profundidade limitada e limite de pastas escaneadas (não trava a UI)
            from collections import deque
            fila = deque([(ano_cache["p_ano"], 0)])
            vistos = 0
            while fila:
                cur, depth = fila.popleft()
                if depth >= 4:
                    continue
                try:
                    with os.scandir(cur) as it:
                        for e in it:
                            if not e.is_dir():
                                continue
                            vistos += 1
                            if vistos > 1500:
                                return ""  # evita varrer rede inteira
                            name_u = e.name.upper()
                            if name_u.startswith(tkl_upper):
                                ano_cache["tkl_index"][tkl_upper] = e.path
                                return e.path
                            fila.append((e.path, depth + 1))
                except:
                    continue
            return ""

        def _worker():
            try:
                # Cache do nome da pasta do ano (evita listdir repetido em rede)
                if not self._year_folder_name_cache:
                    for f in os.listdir(self.base_path_Z):
                        up = f.upper()
                        m = re.search(r'PROJETOS\s+(20\d{2})', up)
                        if m:
                            self._year_folder_name_cache[m.group(1)] = f

                year_folder = self._year_folder_name_cache.get(self.current_year)
                if not year_folder:
                    self.after(0, lambda: self.atualizar_status("ANO NÃO ENCONTRADO", cor="red"))
                    return

                p_ano = os.path.join(self.base_path_Z, year_folder)
                ano_cache = self._ano_cache.get(self.current_year)
                if not ano_cache or ano_cache.get("p_ano") != p_ano:
                    ano_cache = _build_ano_cache(p_ano)
                    self._ano_cache[self.current_year] = ano_cache

                tkl_upper = self.current_tkl.upper()
                projeto_path = _find_tkl_dir_cached(ano_cache, tkl_upper)

                if not projeto_path:
                    self.after(0, lambda: self.atualizar_status("TKL NÃO ENCONTRADA", cor="red"))
                    return

                def _apply():
                    self.projeto_path = projeto_path
                    self.atualizar_status(f"PROJETO: {os.path.basename(self.projeto_path)}", self.projeto_path)
                    self.listbox.delete(0, tk.END)
                    self.entry_filtro.delete(0, tk.END)
                    self.todos_itens = sorted([
                        d.upper() for d in os.listdir(self.projeto_path)
                        if os.path.isdir(os.path.join(self.projeto_path, d)) and d.upper().startswith("ITEM")
                    ])
                    for it in self.todos_itens:
                        self.listbox.insert(tk.END, it)

                self.after(0, _apply)

            except Exception as e:
                self.after(0, lambda: self.atualizar_status(f"ERRO: {e}", cor="red"))

        threading.Thread(target=_worker, daemon=True).start()

    def abrir_pdf_revisao(self):
        selecionados = self.listbox.curselection()
        if not selecionados:
            messagebox.showwarning("Aviso", "Selecione ao menos um item na lista.")
            return
        for i in selecionados:
            item_path = os.path.join(self.projeto_path, self.listbox.get(i))
            pdfs = [os.path.join(r, f) for r, d, fs in os.walk(item_path) for f in fs if f.lower().endswith(".pdf")]
            if pdfs: os.startfile(max(pdfs, key=os.path.getmtime))

    def abrir_kickoff(self):
        if not self.current_tkl: 
            messagebox.showwarning("Aviso", "Busque um TKL primeiro.")
            return
        threading.Thread(target=self.task_kickoff, daemon=True).start()

    def task_kickoff(self):
        try:
            folders = os.listdir(self.base_path_Kickoff)
            ano_dir = next((f for f in folders if self.current_year in f), None)
            if ano_dir:
                p_ano = os.path.join(self.base_path_Kickoff, ano_dir)
                for root, dirs, files in os.walk(p_ano):
                    if root.count(os.sep) - p_ano.count(os.sep) >= 3: del dirs[:] ; continue
                    tkl_dir = next((d for d in dirs if self.current_tkl in d.upper()), None)
                    if tkl_dir:
                        p_tkl = os.path.join(root, tkl_dir)
                        sub_folders = os.listdir(p_tkl)
                        comercial = next((d for d in sub_folders if "00" in d or "COMERCIAL" in d.upper()), None)
                        path_final = os.path.join(p_tkl, comercial) if comercial else p_tkl
                        os.startfile(path_final)
                        return
        except: pass
    def abrir_pasta_projeto(self):
        if self.projeto_path:
            os.startfile(self.projeto_path)
        else:
            messagebox.showwarning("Aviso", "Busque uma TKL primeiro.")

    def abrir_producao(self):
        if not self.projeto_path:
            messagebox.showwarning("Aviso", "Busque uma TKL primeiro.")
            return

        base_root = getattr(self, "base_path_ProducaoEletricaRoot", "").strip()
        if base_root and os.path.exists(base_root):
            # Descobre o ano do projeto (prioriza o ano detectado na busca)
            ano = getattr(self, "current_year", "")
            if not ano:
                m = re.search(r"(20\d{2})", str(self.projeto_path))
                ano = m.group(1) if m else ""

            base_ano = ""
            if ano:
                try:
                    # Ex: "1 - PROJETOS 2022", "3 - PROJETOS 2024"...
                    pastas = os.listdir(base_root)
                    base_ano_nome = next((p for p in pastas if f"PROJETOS {ano}" in p.upper()), "")
                    if base_ano_nome:
                        base_ano = os.path.join(base_root, base_ano_nome)
                except:
                    base_ano = ""

            # Se não achou a pasta do ano, abre a raiz do G:
            if not base_ano:
                try: os.startfile(base_root)
                except: pass
                return

            # Procura a TKL dentro da pasta do ano
            if getattr(self, "current_tkl", ""):
                try:
                    prefix = self.current_tkl.upper()
                    candidatos = [d for d in os.listdir(base_ano) if d.upper().startswith(prefix)]
                    if len(candidatos) == 1:
                        os.startfile(os.path.join(base_ano, candidatos[0]))
                        return
                except:
                    pass

            # Não achou / múltiplos -> abre a pasta do ano
            try: os.startfile(base_ano)
            except: pass
            return

        # Fallback: tenta achar pasta de produção dentro do projeto (comportamento antigo)
        possiveis = ["PRODUÇÃO ELÉTRICA", "PRODUCAO ELETRICA", "PRODUCAO_ELETRICA", "PRODUCAO", "PRODUÇÃO"]
        for nome in possiveis:
            candidato = os.path.join(self.projeto_path, nome)
            if os.path.exists(candidato):
                os.startfile(candidato)
                return

        messagebox.showwarning("Aviso", "Pasta de Produção Elétrica não encontrada.")
    def abrir_suprimentos(self):



        if os.path.exists(self.base_path_Suprimentos): os.startfile(self.base_path_Suprimentos)

    def preparar_impressao(self):
        selecionados = self.listbox.curselection()
        if not selecionados:
            messagebox.showwarning("Aviso", "Selecione ao menos um item na lista.")
            return
        desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
        pasta_impressao = os.path.join(desktop, f"IMPRIMIR_{self.current_tkl.replace('.', '_')}")
        if not os.path.exists(pasta_impressao): os.makedirs(pasta_impressao)
        pdfs_copiados = 0
        for i in selecionados:
            item_nome = self.listbox.get(i)
            item_path = os.path.join(self.projeto_path, item_nome)
            pdfs = []
            for r, d, fs in os.walk(item_path):
                if r.count(os.sep) - item_path.count(os.sep) > 3: continue
                for f in fs:
                    if f.lower().endswith(".pdf"): pdfs.append(os.path.join(r, f))
            if pdfs:
                pdf_recente = max(pdfs, key=os.path.getmtime)
                pdf_nome = os.path.basename(pdf_recente)
                # Evita duplicar nome do ITEM quando o PDF já começa com o mesmo texto
                def _norm(s):
                    return re.sub(r"\s+", " ", s).strip().upper()
                if _norm(pdf_nome).startswith(_norm(item_nome)):
                    nome_destino = pdf_nome
                else:
                    nome_destino = f"{item_nome}_{pdf_nome}"
                destino = os.path.join(pasta_impressao, nome_destino)
                try:
                    shutil.copy2(pdf_recente, destino)
                    pdfs_copiados += 1
                except: pass
        if pdfs_copiados > 0:
            self.criar_script_impressao(pasta_impressao)
            os.startfile(pasta_impressao)
            messagebox.showinfo("Sucesso", f"{pdfs_copiados} PDFs copiados.\n\nExecute o arquivo .BAT na Desktop para imprimir.")
        else: messagebox.showerror("Erro", "Nenhum PDF encontrado.")

    def criar_script_impressao(self, pasta):
        caminho_bat = os.path.join(pasta, "CLIQUE_PARA_IMPRIMIR.bat")
        script_content = "@echo off\ntitle IMPRESSÃO TRISKEL\necho Enviando PDFs para a impressora padrao...\npowershell -Command \"Get-ChildItem -Filter *.pdf | ForEach-Object { Start-Process $_.FullName -Verb Print }\"\necho.\necho PROCESSO CONCLUIDO!\npause"
        with open(caminho_bat, "w") as f: f.write(script_content)

if __name__ == "__main__":
    app = GerenciadorProjetos()
    app.mainloop()


    # =============================
    # BOTÕES RESTAURADOS / NOVOS
    # =============================

    def abrir_suprimentos(self):
        caminho = r"G:\Drives compartilhados\Suprimentos"
        if os.path.exists(caminho):
            os.startfile(caminho)
        else:
            messagebox.showerror("Erro", "Caminho de Suprimentos não encontrado.")

    def abrir_kickoff(self):
        tkl = self.entry_busca.get().strip().upper()
        if not tkl:
            messagebox.showwarning("Aviso", "Digite uma TKL primeiro.")
            return

        ano = "20" + tkl[-2:] if "." in tkl else "20" + tkl[:2]
        base = r"G:\Drives compartilhados\Kickoff"
        pasta_ano = os.path.join(base, f"KICK OFF {ano}")

        if not os.path.exists(pasta_ano):
            messagebox.showerror("Erro", "Ano de Kickoff não encontrado.")
            return

        encontrado = None
        for pasta in os.listdir(pasta_ano):
            if pasta.upper().startswith("TKL" + tkl.replace(".", "")):
                encontrado = os.path.join(pasta_ano, pasta)
                break

        if encontrado and os.path.exists(encontrado):
            os.startfile(encontrado)
        else:
            messagebox.showwarning("Aviso", "TKL não encontrada no Kickoff.")

    def abrir_producao_eletrica(self):
        tkl = self.entry_busca.get().strip().upper()
        if not tkl:
            messagebox.showwarning("Aviso", "Digite uma TKL primeiro.")
            return

        ano = "20" + tkl[-2:] if "." in tkl else "20" + tkl[:2]
        base = r"G:\Drives compartilhados\Projetos Elétricos (PDF)"
        pasta_ano = None

        for pasta in os.listdir(base):
            if ano in pasta:
                pasta_ano = os.path.join(base, pasta)
                break

        if not pasta_ano:
            messagebox.showerror("Erro", "Ano não encontrado na Produção Elétrica.")
            return

        for pasta in os.listdir(pasta_ano):
            if pasta.upper().startswith("TKL" + tkl.replace(".", "")):
                os.startfile(os.path.join(pasta_ano, pasta))
                return

        messagebox.showwarning("Aviso", "TKL não encontrada na Produção Elétrica.")

    def abrir_pasta_cliente(self):
        tkl = self.entry_busca.get().strip().upper()
        if not tkl:
            messagebox.showwarning("Aviso", "Digite uma TKL primeiro.")
            return

        ano = "20" + tkl[:2]
        base_drive = r"I:\Meu Drive"
        pasta_ano = None

        for pasta in os.listdir(base_drive):
            if ano in pasta:
                pasta_ano = os.path.join(base_drive, pasta)
                break

        if not pasta_ano:
            messagebox.showerror("Erro", "Ano não encontrado no Drive do Cliente.")
            return

        for root, dirs, files in os.walk(pasta_ano):
            for d in dirs:
                if d.upper().startswith("TKL" + tkl.replace(".", "")):
                    caminho_final = os.path.join(root, d, "0 - PROJETOS ELÉTRICOS")
                    if os.path.exists(caminho_final):
                        os.startfile(caminho_final)
                        return

        messagebox.showwarning("Aviso", "TKL não encontrada no Drive do Cliente.")
