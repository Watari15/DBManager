import customtkinter as ctk
import sqlite3
import os
import threading
import time
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

# ─── PALETTE ──────────────────────────────────────────────────────────────
COLORS = {
    "bg":           "#0a0a0f",
    "bg2":          "#0f0f1a",
    "bg3":          "#141428",
    "panel":        "#0d0d1f",
    "border":       "#1a1a3a",
    "border_glow":  "#2a2a6a",
    "cyan":         "#00f5ff",
    "magenta":      "#ff00aa",
    "green":        "#00ff88",
    "yellow":       "#ffee00",
    "red":          "#ff2255",
    "text":         "#c8d8ff",
    "text_dim":     "#4a5080",
    "text_bright":  "#e8f0ff",
    "accent1":      "#7b2fff",
    "accent2":      "#ff6b35",
    "glow":         "#00f5ff22",
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ─── ÉTAT GLOBAL ──────────────────────────────────────────────────────────
current_db_path = None
current_conn = None
selected_table = None

# ═══════════════════════════════════════════════════════════════════════════
# DATABASE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_conn():
    return current_conn

def load_database(path):
    global current_db_path, current_conn
    if current_conn:
        current_conn.close()
    current_db_path = path
    current_conn = sqlite3.connect(path, check_same_thread=False)
    current_conn.row_factory = sqlite3.Row
    return current_conn

def get_tables():
    if not current_conn:
        return []
    cur = current_conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    return [r[0] for r in cur.fetchall()]

def get_table_info(table_name):
    if not current_conn:
        return []
    cur = current_conn.cursor()
    cur.execute(f"PRAGMA table_info('{table_name}');")
    return cur.fetchall()

def get_table_rows(table_name, limit=200):
    if not current_conn:
        return [], []
    cur = current_conn.cursor()
    info = get_table_info(table_name)
    columns = [col[1] for col in info]
    cur.execute(f"SELECT * FROM '{table_name}' LIMIT {limit};")
    rows = cur.fetchall()
    return columns, [list(r) for r in rows]

def create_table(name, columns):
    """columns: list of (col_name, col_type, primary_key, not_null, default)"""
    if not current_conn:
        return False, "Aucune base de données ouverte."
    col_defs = []
    for col_name, col_type, pk, nn, default in columns:
        d = f'"{col_name}" {col_type}'
        if pk:
            d += " PRIMARY KEY"
        if nn:
            d += " NOT NULL"
        if default.strip():
            d += f" DEFAULT {default.strip()}"
        col_defs.append(d)
    sql = f'CREATE TABLE IF NOT EXISTS "{name}" ({", ".join(col_defs)});'
    try:
        current_conn.execute(sql)
        current_conn.commit()
        return True, sql
    except Exception as e:
        return False, str(e)

def drop_table(name):
    if not current_conn:
        return False, "Aucune base de données ouverte."
    try:
        current_conn.execute(f'DROP TABLE IF EXISTS "{name}";')
        current_conn.commit()
        return True, f'Table "{name}" supprimée.'
    except Exception as e:
        return False, str(e)

def insert_row(table_name, values_dict):
    if not current_conn:
        return False, "Aucune base de données ouverte."
    cols = ", ".join(f'"{k}"' for k in values_dict)
    placeholders = ", ".join("?" for _ in values_dict)
    sql = f'INSERT INTO "{table_name}" ({cols}) VALUES ({placeholders});'
    try:
        current_conn.execute(sql, list(values_dict.values()))
        current_conn.commit()
        return True, "Ligne insérée."
    except Exception as e:
        return False, str(e)

def execute_sql(sql_text):
    if not current_conn:
        return False, "Aucune base de données ouverte.", []
    try:
        cur = current_conn.cursor()
        statements = [s.strip() for s in sql_text.split(";") if s.strip()]
        results = []
        for stmt in statements:
            cur.execute(stmt)
            if cur.description:
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()
                results.append((cols, rows))
            else:
                results.append(([], []))
        current_conn.commit()
        return True, f"{len(statements)} requête(s) exécutée(s).", results
    except Exception as e:
        return False, str(e), []

def generate_sql_schema():
    if not current_conn:
        return ""
    cur = current_conn.cursor()
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL ORDER BY name;")
    rows = cur.fetchall()
    lines = [
        "-- ════════════════════════════════════════",
        f"-- SCHEMA SQL GÉNÉRÉ — {os.path.basename(current_db_path or 'database.db')}",
        "-- ════════════════════════════════════════",
        ""
    ]
    for r in rows:
        lines.append(r[0] + ";")
        lines.append("")
    return "\n".join(lines)

def generate_drawio_xml():
    if not current_conn:
        return ""
    tables = get_tables()
    cells = []
    cell_id = 2
    table_ids = {}
    x, y = 80, 80
    spacing_x, spacing_y = 260, 0

    for t in tables:
        info = get_table_info(t)
        table_ids[t] = cell_id
        # Table container
        height = 30 + len(info) * 24
        cells.append(
            f'<mxCell id="{cell_id}" value="{t}" style="shape=table;startSize=30;container=1;collapsible=1;childLayout=tableLayout;fixedRows=1;rowLines=0;fontStyle=1;align=center;resizeLast=1;fontSize=13;fillColor=#0d0d1f;strokeColor=#00f5ff;fontColor=#00f5ff;" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="220" height="{height}" as="geometry"/></mxCell>'
        )
        cell_id += 1
        for col in info:
            cid, cname, ctype, notnull, dflt, pk = col
            pk_str = " 🔑" if pk else ""
            nn_str = " NN" if notnull else ""
            cells.append(
                f'<mxCell id="{cell_id}" value="{cname}{pk_str} [{ctype}{nn_str}]" style="shape=tableRow;startSize=0;swimlaneHead=0;swimlaneBody=0;fillColor=none;collapsible=0;dropTarget=0;points=[[0,0.5],[1,0.5]];portConstraint=eastwest;fontSize=11;fontColor=#c8d8ff;strokeColor=#1a1a3a;" vertex="1" parent="{table_ids[t]}"><mxGeometry y="{30 + cid * 24}" width="220" height="24" as="geometry"/></mxCell>'
            )
            cell_id += 1
        x += spacing_x
        if x > 900:
            x = 80
            y += 280

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="Electron" modified="2024-01-01T00:00:00.000Z">
  <diagram name="Schema UML" id="schema">
    <mxGraphModel dx="1422" dy="762" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1169" pageHeight="827" math="0" shadow="0">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        {''.join(cells)}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>"""
    return xml


# ═══════════════════════════════════════════════════════════════════════════
# WIDGETS CUSTOM
# ═══════════════════════════════════════════════════════════════════════════

class GlitchLabel(ctk.CTkLabel):
    """Label avec effet glitch anim."""
    def __init__(self, master, text, glitch=False, **kwargs):
        kwargs.setdefault("font", ("Courier New", 12, "bold"))
        kwargs.setdefault("text_color", COLORS["cyan"])
        super().__init__(master, text=text, **kwargs)
        self._orig_text = text
        if glitch:
            self._start_glitch()

    def _start_glitch(self):
        chars = "!@#$%^&*01█▓▒░<>{}[]"
        def _glitch_loop():
            while True:
                time.sleep(4 + __import__("random").random() * 6)
                orig = self._orig_text
                for _ in range(4):
                    glitched = "".join(
                        c if __import__("random").random() > 0.15 else __import__("random").choice(chars)
                        for c in orig
                    )
                    self.configure(text=glitched, text_color=COLORS["magenta"])
                    time.sleep(0.07)
                self.configure(text=orig, text_color=COLORS["cyan"])
        t = threading.Thread(target=_glitch_loop, daemon=True)
        t.start()


class NeonButton(ctk.CTkButton):
    def __init__(self, master, text, color="cyan", **kwargs):
        c = COLORS.get(color, COLORS["cyan"])
        kwargs.setdefault("font", ("Courier New", 11, "bold"))
        kwargs.setdefault("fg_color", COLORS["bg3"])
        kwargs.setdefault("hover_color", COLORS["bg2"])
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", c)
        kwargs.setdefault("text_color", c)
        kwargs.setdefault("corner_radius", 4)
        kwargs.setdefault("height", 32)
        super().__init__(master, text=text, **kwargs)


class ScanlineFrame(ctk.CTkFrame):
    """Frame avec bordure colorée style terminal."""
    def __init__(self, master, border_color=None, **kwargs):
        kwargs.setdefault("fg_color", COLORS["bg2"])
        kwargs.setdefault("corner_radius", 6)
        if border_color:
            kwargs["border_width"] = 1
            kwargs["border_color"] = border_color
        super().__init__(master, **kwargs)


class StatusBar(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg3"], height=28, corner_radius=0)
        self.pack_propagate(False)
        self._db_label = ctk.CTkLabel(self, text="● NO DB", font=("Courier New", 10),
                                       text_color=COLORS["red"])
        self._db_label.pack(side="left", padx=12)
        self._msg_label = ctk.CTkLabel(self, text="", font=("Courier New", 10),
                                        text_color=COLORS["text_dim"])
        self._msg_label.pack(side="left", padx=6)
        self._count_label = ctk.CTkLabel(self, text="", font=("Courier New", 10),
                                          text_color=COLORS["text_dim"])
        self._count_label.pack(side="right", padx=12)

    def set_db(self, path):
        name = os.path.basename(path) if path else "NO DB"
        color = COLORS["green"] if path else COLORS["red"]
        dot = "●" if path else "●"
        self._db_label.configure(text=f"{dot} {name}", text_color=color)

    def set_msg(self, msg, ok=True):
        self._msg_label.configure(text=msg,
                                   text_color=COLORS["green"] if ok else COLORS["red"])

    def set_count(self, txt):
        self._count_label.configure(text=txt)


# ═══════════════════════════════════════════════════════════════════════════
# ONGLET 1 — ÉDITEUR DE BASE DE DONNÉES
# ═══════════════════════════════════════════════════════════════════════════

class DatabaseEditorTab(ctk.CTkFrame):
    def __init__(self, master, status_bar, **kwargs):
        super().__init__(master, fg_color=COLORS["bg"], **kwargs)
        self.status = status_bar
        self._build()

    def _build(self):
        # ── Toolbar ──
        toolbar = ScanlineFrame(self, border_color=COLORS["border"])
        toolbar.pack(fill="x", padx=10, pady=(10, 6))

        GlitchLabel(toolbar, "// DATABASE MANAGER", glitch=True,
                    font=("Courier New", 13, "bold")).pack(side="left", padx=12, pady=6)

        NeonButton(toolbar, "◈ NOUVELLE DB", color="green",
                   command=self._new_db, width=130).pack(side="right", padx=6, pady=6)
        NeonButton(toolbar, "⬆ OUVRIR DB", color="cyan",
                   command=self._open_db, width=120).pack(side="right", padx=0, pady=6)

        # ── Corps principal ──
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=10, pady=4)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # ── Panel gauche: tables ──
        left = ScanlineFrame(body, border_color=COLORS["border_glow"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=0)
        left.configure(width=200)

        ctk.CTkLabel(left, text="TABLES", font=("Courier New", 10, "bold"),
                     text_color=COLORS["magenta"]).pack(pady=(8, 2), padx=8, anchor="w")

        self._table_list = tk.Listbox(
            left, bg=COLORS["bg2"], fg=COLORS["cyan"],
            selectbackground=COLORS["accent1"], selectforeground="#fff",
            font=("Courier New", 11), bd=0, highlightthickness=0,
            relief="flat", activestyle="none"
        )
        self._table_list.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._table_list.bind("<<ListboxSelect>>", self._on_table_select)

        btn_frame = ctk.CTkFrame(left, fg_color="transparent")
        btn_frame.pack(fill="x", padx=6, pady=(0, 8))
        NeonButton(btn_frame, "+ TABLE", color="cyan", command=self._show_create_table,
                   width=88, height=28).pack(side="left")
        NeonButton(btn_frame, "✕ DROP", color="red", command=self._drop_table,
                   width=66, height=28).pack(side="right")

        # ── Panel droit: contenu table ──
        right = ScanlineFrame(body, border_color=COLORS["border_glow"])
        right.grid(row=0, column=1, sticky="nsew")

        # Header du panel droit
        r_header = ctk.CTkFrame(right, fg_color="transparent")
        r_header.pack(fill="x", padx=10, pady=(8, 4))
        self._table_title = ctk.CTkLabel(r_header, text="SELECT A TABLE",
                                          font=("Courier New", 12, "bold"),
                                          text_color=COLORS["text_dim"])
        self._table_title.pack(side="left")
        NeonButton(r_header, "+ INSERT ROW", color="green",
                   command=self._show_insert_row, width=120, height=26).pack(side="right")
        NeonButton(r_header, "⟳ REFRESH", color="cyan",
                   command=self._refresh_table, width=100, height=26).pack(side="right", padx=6)

        # Treeview
        tree_frame = ctk.CTkFrame(right, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Glitch.Treeview",
                         background=COLORS["bg2"],
                         foreground=COLORS["text"],
                         fieldbackground=COLORS["bg2"],
                         borderwidth=0,
                         rowheight=22,
                         font=("Courier New", 10))
        style.configure("Glitch.Treeview.Heading",
                         background=COLORS["bg3"],
                         foreground=COLORS["cyan"],
                         borderwidth=0,
                         font=("Courier New", 10, "bold"))
        style.map("Glitch.Treeview",
                  background=[("selected", COLORS["accent1"])],
                  foreground=[("selected", "#fff")])

        self._tree = ttk.Treeview(tree_frame, style="Glitch.Treeview", show="headings")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

    # ── Actions ──
    def _new_db(self):
        path = filedialog.asksaveasfilename(
            title="Créer une base de données",
            defaultextension=".db",
            filetypes=[("SQLite DB", "*.db"), ("Tous", "*.*")]
        )
        if not path:
            return
        load_database(path)
        self.status.set_db(path)
        self.status.set_msg(f"Nouvelle DB créée : {os.path.basename(path)}")
        self._refresh_tables()

    def _open_db(self):
        path = filedialog.askopenfilename(
            title="Ouvrir une base de données",
            filetypes=[("SQLite DB", "*.db *.sqlite *.sqlite3"), ("Tous", "*.*")]
        )
        if not path:
            return
        load_database(path)
        self.status.set_db(path)
        self.status.set_msg(f"DB chargée : {os.path.basename(path)}")
        self._refresh_tables()

    def _refresh_tables(self):
        self._table_list.delete(0, "end")
        for t in get_tables():
            self._table_list.insert("end", f"  {t}")
        self.status.set_count(f"{len(get_tables())} table(s)")

    def _on_table_select(self, event=None):
        sel = self._table_list.curselection()
        if not sel:
            return
        global selected_table
        selected_table = self._table_list.get(sel[0]).strip()
        self._table_title.configure(text=f"▸ {selected_table}", text_color=COLORS["cyan"])
        self._load_table(selected_table)

    def _load_table(self, name):
        cols, rows = get_table_rows(name)
        self._tree["columns"] = cols
        self._tree.delete(*self._tree.get_children())
        for c in cols:
            self._tree.heading(c, text=c)
            self._tree.column(c, width=max(80, len(c) * 9), stretch=True)
        for r in rows:
            self._tree.insert("", "end", values=r)
        self.status.set_count(f"{len(rows)} ligne(s)")

    def _refresh_table(self):
        if selected_table:
            self._load_table(selected_table)
        self._refresh_tables()

    def _drop_table(self):
        if not selected_table:
            messagebox.showwarning("Attention", "Sélectionne une table d'abord.")
            return
        if messagebox.askyesno("Confirmer", f"Supprimer la table '{selected_table}' ?"):
            ok, msg = drop_table(selected_table)
            self.status.set_msg(msg, ok)
            self._refresh_tables()
            self._tree["columns"] = []
            self._tree.delete(*self._tree.get_children())

    def _show_create_table(self):
        CreateTableDialog(self, on_done=self._refresh_tables)

    def _show_insert_row(self):
        if not selected_table:
            messagebox.showwarning("Attention", "Sélectionne une table d'abord.")
            return
        InsertRowDialog(self, table_name=selected_table, on_done=lambda: self._load_table(selected_table))


# ─── Dialogue Créer Table ──────────────────────────────────────────────────
class CreateTableDialog(ctk.CTkToplevel):
    def __init__(self, master, on_done=None):
        super().__init__(master)
        self.on_done = on_done
        self.title("Créer une Table")
        self.geometry("560x520")
        self.configure(fg_color=COLORS["bg"])
        self.resizable(False, False)
        self._col_rows = []
        self._build()
        self.lift()
        self.focus_force()

    def _build(self):
        GlitchLabel(self, "// CREATE TABLE", font=("Courier New", 14, "bold"),
                    text_color=COLORS["magenta"]).pack(pady=(16, 4))

        name_f = ctk.CTkFrame(self, fg_color="transparent")
        name_f.pack(fill="x", padx=20, pady=(4, 8))
        ctk.CTkLabel(name_f, text="Nom de la table :", font=("Courier New", 11),
                     text_color=COLORS["text"]).pack(side="left")
        self._name_entry = ctk.CTkEntry(name_f, font=("Courier New", 11),
                                         fg_color=COLORS["bg3"], border_color=COLORS["cyan"],
                                         text_color=COLORS["cyan"], width=220)
        self._name_entry.pack(side="left", padx=10)

        # En-tête colonnes
        header = ctk.CTkFrame(self, fg_color=COLORS["bg3"])
        header.pack(fill="x", padx=20)
        for txt, w in [("Nom", 120), ("Type", 90), ("PK", 30), ("NN", 30), ("Default", 90)]:
            ctk.CTkLabel(header, text=txt, font=("Courier New", 9, "bold"),
                         text_color=COLORS["cyan"], width=w).pack(side="left", padx=3, pady=4)

        self._cols_frame = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg2"],
                                                   border_width=1, border_color=COLORS["border_glow"],
                                                   height=240)
        self._cols_frame.pack(fill="x", padx=20, pady=4)

        self._add_column()  # Une colonne par défaut

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=4)
        NeonButton(btn_row, "+ COLONNE", color="cyan", command=self._add_column, width=110).pack(side="left")
        NeonButton(btn_row, "- COLONNE", color="red", command=self._remove_column, width=110).pack(side="left", padx=8)

        NeonButton(self, "▶ CRÉER LA TABLE", color="green",
                   command=self._create, width=200).pack(pady=(8, 16))

    TYPES = ["INTEGER", "TEXT", "REAL", "BLOB", "NUMERIC", "BOOLEAN", "DATE", "DATETIME"]

    def _add_column(self):
        row = ctk.CTkFrame(self._cols_frame, fg_color="transparent")
        row.pack(fill="x", pady=2)
        name_e = ctk.CTkEntry(row, width=120, font=("Courier New", 10),
                               fg_color=COLORS["bg3"], border_color=COLORS["border_glow"],
                               text_color=COLORS["text"])
        name_e.pack(side="left", padx=3)
        type_cb = ctk.CTkComboBox(row, values=self.TYPES, width=90, font=("Courier New", 10),
                                   fg_color=COLORS["bg3"], border_color=COLORS["border_glow"],
                                   text_color=COLORS["text"], button_color=COLORS["bg3"],
                                   dropdown_fg_color=COLORS["bg3"])
        type_cb.set("TEXT")
        type_cb.pack(side="left", padx=3)
        pk_var = tk.BooleanVar()
        pk_cb = ctk.CTkCheckBox(row, text="", variable=pk_var, width=30,
                                 checkbox_width=16, checkbox_height=16,
                                 fg_color=COLORS["accent1"], border_color=COLORS["cyan"])
        pk_cb.pack(side="left", padx=3)
        nn_var = tk.BooleanVar()
        nn_cb = ctk.CTkCheckBox(row, text="", variable=nn_var, width=30,
                                 checkbox_width=16, checkbox_height=16,
                                 fg_color=COLORS["accent1"], border_color=COLORS["cyan"])
        nn_cb.pack(side="left", padx=3)
        default_e = ctk.CTkEntry(row, width=90, font=("Courier New", 10),
                                  fg_color=COLORS["bg3"], border_color=COLORS["border_glow"],
                                  text_color=COLORS["text"])
        default_e.pack(side="left", padx=3)
        self._col_rows.append((name_e, type_cb, pk_var, nn_var, default_e))

    def _remove_column(self):
        if len(self._col_rows) > 1:
            *rest, last = self._col_rows
            last[0].master.destroy()
            self._col_rows = rest

    def _create(self):
        name = self._name_entry.get().strip()
        if not name:
            messagebox.showerror("Erreur", "Le nom de la table est requis.", parent=self)
            return
        cols = []
        for name_e, type_cb, pk_v, nn_v, def_e in self._col_rows:
            cn = name_e.get().strip()
            if not cn:
                continue
            cols.append((cn, type_cb.get(), pk_v.get(), nn_v.get(), def_e.get()))
        if not cols:
            messagebox.showerror("Erreur", "Au moins une colonne est requise.", parent=self)
            return
        ok, msg = create_table(name, cols)
        if ok:
            if self.on_done:
                self.on_done()
            self.destroy()
        else:
            messagebox.showerror("Erreur SQL", msg, parent=self)


# ─── Dialogue Insérer Ligne ───────────────────────────────────────────────
class InsertRowDialog(ctk.CTkToplevel):
    def __init__(self, master, table_name, on_done=None):
        super().__init__(master)
        self.table_name = table_name
        self.on_done = on_done
        self.title(f"INSERT INTO {table_name}")
        self.geometry("440x420")
        self.configure(fg_color=COLORS["bg"])
        self.resizable(False, False)
        self._fields = {}
        self._build()
        self.lift()
        self.focus_force()

    def _build(self):
        GlitchLabel(self, f"// INSERT INTO {self.table_name}",
                    font=("Courier New", 12, "bold"), text_color=COLORS["magenta"]).pack(pady=(16, 8))
        form = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg2"],
                                       border_width=1, border_color=COLORS["border_glow"],
                                       height=300)
        form.pack(fill="x", padx=20, pady=4)
        info = get_table_info(self.table_name)
        for col in info:
            _, cname, ctype, _, dflt, pk = col
            row = ctk.CTkFrame(form, fg_color="transparent")
            row.pack(fill="x", pady=4)
            label_txt = f"{cname} [{ctype}]"
            if pk:
                label_txt += " 🔑"
            ctk.CTkLabel(row, text=label_txt, font=("Courier New", 10),
                         text_color=COLORS["text"], width=160, anchor="w").pack(side="left", padx=6)
            entry = ctk.CTkEntry(row, font=("Courier New", 10),
                                  fg_color=COLORS["bg3"], border_color=COLORS["border_glow"],
                                  text_color=COLORS["cyan"], width=200,
                                  placeholder_text=str(dflt) if dflt else "")
            entry.pack(side="left")
            self._fields[cname] = entry

        NeonButton(self, "▶ INSERT", color="green", command=self._insert, width=160).pack(pady=12)

    def _insert(self):
        data = {k: v.get() for k, v in self._fields.items() if v.get().strip()}
        ok, msg = insert_row(self.table_name, data)
        if ok:
            if self.on_done:
                self.on_done()
            self.destroy()
        else:
            messagebox.showerror("Erreur", msg, parent=self)


# ═══════════════════════════════════════════════════════════════════════════
# ONGLET 2 — GÉNÉRATEUR SQL
# ═══════════════════════════════════════════════════════════════════════════

class SQLGeneratorTab(ctk.CTkFrame):
    def __init__(self, master, status_bar, **kwargs):
        super().__init__(master, fg_color=COLORS["bg"], **kwargs)
        self.status = status_bar
        self._build()

    def _build(self):
        # ── Toolbar ──
        toolbar = ScanlineFrame(self, border_color=COLORS["border"])
        toolbar.pack(fill="x", padx=10, pady=(10, 6))
        GlitchLabel(toolbar, "// SQL GENERATOR", glitch=False,
                    font=("Courier New", 13, "bold")).pack(side="left", padx=12, pady=6)
        NeonButton(toolbar, "⬆ EXPORTER .SQL", color="yellow",
                   command=self._export, width=140).pack(side="right", padx=6, pady=6)
        NeonButton(toolbar, "▶ EXÉCUTER", color="green",
                   command=self._execute, width=110).pack(side="right", pady=6)
        NeonButton(toolbar, "⟳ SCHEMA", color="cyan",
                   command=self._gen_schema, width=100).pack(side="right", padx=6, pady=6)

        # ── Zone éditeur ──
        paned = ctk.CTkFrame(self, fg_color="transparent")
        paned.pack(fill="both", expand=True, padx=10, pady=4)
        paned.rowconfigure(0, weight=2)
        paned.rowconfigure(1, weight=1)
        paned.columnconfigure(0, weight=1)

        # Éditeur SQL
        editor_frame = ScanlineFrame(paned, border_color=COLORS["border_glow"])
        editor_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        ctk.CTkLabel(editor_frame, text="SQL EDITOR", font=("Courier New", 9, "bold"),
                     text_color=COLORS["magenta"]).pack(anchor="w", padx=10, pady=(6, 0))
        self._sql_text = tk.Text(
            editor_frame, bg=COLORS["bg2"], fg=COLORS["cyan"],
            insertbackground=COLORS["cyan"], selectbackground=COLORS["accent1"],
            font=("Courier New", 12), bd=0, padx=12, pady=8,
            relief="flat", highlightthickness=0, wrap="none",
            undo=True
        )
        self._sql_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._sql_text.insert("1.0", "-- Écris ou génère du SQL ici\n\n")

        # Résultats
        result_frame = ScanlineFrame(paned, border_color=COLORS["border"])
        result_frame.grid(row=1, column=0, sticky="nsew")
        ctk.CTkLabel(result_frame, text="OUTPUT", font=("Courier New", 9, "bold"),
                     text_color=COLORS["magenta"]).pack(anchor="w", padx=10, pady=(6, 0))
        self._result_text = tk.Text(
            result_frame, bg=COLORS["bg3"], fg=COLORS["green"],
            insertbackground=COLORS["green"],
            font=("Courier New", 10), bd=0, padx=10, pady=6,
            relief="flat", highlightthickness=0, state="disabled", height=6
        )
        self._result_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _write_result(self, txt, color=None):
        self._result_text.configure(state="normal")
        self._result_text.delete("1.0", "end")
        self._result_text.insert("1.0", txt)
        if color:
            self._result_text.configure(fg=color)
        self._result_text.configure(state="disabled")

    def _gen_schema(self):
        sql = generate_sql_schema()
        if not sql:
            self._write_result("⚠ Aucune base de données ouverte.", COLORS["yellow"])
            return
        self._sql_text.delete("1.0", "end")
        self._sql_text.insert("1.0", sql)
        self._write_result(f"✓ Schéma de {len(get_tables())} table(s) généré.", COLORS["green"])
        self.status.set_msg("Schéma SQL généré.")

    def _execute(self):
        sql = self._sql_text.get("1.0", "end").strip()
        if not sql:
            return
        ok, msg, results = execute_sql(sql)
        if not ok:
            self._write_result(f"✗ ERREUR : {msg}", COLORS["red"])
            self.status.set_msg(msg, False)
            return
        output = [f"✓ {msg}", ""]
        for i, (cols, rows) in enumerate(results):
            if cols:
                output.append(f"--- Résultat {i+1} ({len(rows)} ligne(s)) ---")
                output.append("  ".join(f"{c:<14}" for c in cols))
                output.append("  ".join("─" * 14 for _ in cols))
                for r in rows[:50]:
                    output.append("  ".join(f"{str(v):<14}" for v in r))
                if len(rows) > 50:
                    output.append(f"  ... ({len(rows)-50} lignes supplémentaires)")
        self._write_result("\n".join(output), COLORS["green"])
        self.status.set_msg(f"SQL exécuté : {msg}")

    def _export(self):
        sql = self._sql_text.get("1.0", "end")
        path = filedialog.asksaveasfilename(
            title="Exporter le SQL",
            defaultextension=".sql",
            filetypes=[("SQL File", "*.sql"), ("Tous", "*.*")]
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(sql)
        self.status.set_msg(f"SQL exporté → {os.path.basename(path)}")


# ═══════════════════════════════════════════════════════════════════════════
# ONGLET 3 — VISUALISATION UML / DRAWIO
# ═══════════════════════════════════════════════════════════════════════════

class DrawioTab(ctk.CTkFrame):
    def __init__(self, master, status_bar, **kwargs):
        super().__init__(master, fg_color=COLORS["bg"], **kwargs)
        self.status = status_bar
        self._build()

    def _build(self):
        toolbar = ScanlineFrame(self, border_color=COLORS["border"])
        toolbar.pack(fill="x", padx=10, pady=(10, 6))
        GlitchLabel(toolbar, "// UML DRAWIO GENERATOR", glitch=False,
                    font=("Courier New", 13, "bold")).pack(side="left", padx=12, pady=6)
        NeonButton(toolbar, "⬆ EXPORTER .DRAWIO", color="yellow",
                   command=self._export, width=160).pack(side="right", padx=6, pady=6)
        NeonButton(toolbar, "⟳ GÉNÉRER XML", color="magenta",
                   command=self._generate, width=130).pack(side="right", pady=6)

        # Info
        info = ScanlineFrame(self, border_color=COLORS["border"])
        info.pack(fill="x", padx=10, pady=(0, 6))
        ctk.CTkLabel(info, text="  ℹ  Génère un fichier .drawio prêt à ouvrir dans draw.io / diagrams.net — visualisation UML de ton schéma.",
                     font=("Courier New", 10), text_color=COLORS["text_dim"]).pack(anchor="w", padx=4, pady=6)

        # Aperçu XML
        preview_frame = ScanlineFrame(self, border_color=COLORS["border_glow"])
        preview_frame.pack(fill="both", expand=True, padx=10, pady=4)
        ctk.CTkLabel(preview_frame, text="APERÇU XML", font=("Courier New", 9, "bold"),
                     text_color=COLORS["magenta"]).pack(anchor="w", padx=10, pady=(6, 0))
        self._xml_text = tk.Text(
            preview_frame, bg=COLORS["bg2"], fg=COLORS["accent2"],
            insertbackground=COLORS["cyan"],
            font=("Courier New", 10), bd=0, padx=10, pady=8,
            relief="flat", highlightthickness=0
        )
        self._xml_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._xml_text.insert("1.0", "-- Clique sur GÉNÉRER XML pour prévisualiser --")

    def _generate(self):
        xml = generate_drawio_xml()
        if not xml:
            self._xml_text.delete("1.0", "end")
            self._xml_text.insert("1.0", "⚠ Aucune base de données ouverte ou aucune table.")
            return
        self._xml_text.delete("1.0", "end")
        self._xml_text.insert("1.0", xml)
        self.status.set_msg(f"Drawio XML généré pour {len(get_tables())} table(s).")

    def _export(self):
        xml = self._xml_text.get("1.0", "end").strip()
        if not xml or xml.startswith("--") or xml.startswith("⚠"):
            self._generate()
            xml = self._xml_text.get("1.0", "end").strip()
        if not xml or xml.startswith("--"):
            return
        default_name = os.path.splitext(os.path.basename(current_db_path or "schema"))[0]
        path = filedialog.asksaveasfilename(
            title="Exporter .drawio",
            initialfile=f"{default_name}.drawio",
            defaultextension=".drawio",
            filetypes=[("Drawio File", "*.drawio"), ("XML", "*.xml"), ("Tous", "*.*")]
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(xml)
        self.status.set_msg(f"Fichier .drawio exporté → {os.path.basename(path)}")


# ═══════════════════════════════════════════════════════════════════════════
# NAVIGATION TABS CUSTOM (style onglets navigateur)
# ═══════════════════════════════════════════════════════════════════════════

class TabBar(ctk.CTkFrame):
    def __init__(self, master, tabs, on_change, **kwargs):
        super().__init__(master, fg_color=COLORS["bg3"], height=40, corner_radius=0, **kwargs)
        self.pack_propagate(False)
        self._buttons = []
        self._active = 0
        self._on_change = on_change

        # Logo
        ctk.CTkLabel(self, text="  ⬡ SQLRIFT  ", font=("Courier New", 12, "bold"),
                     text_color=COLORS["accent1"]).pack(side="left", padx=(8, 16))

        for i, (icon, label) in enumerate(tabs):
            btn = ctk.CTkButton(
                self, text=f"{icon}  {label}",
                font=("Courier New", 11, "bold"),
                fg_color=COLORS["bg"] if i == 0 else "transparent",
                hover_color=COLORS["bg2"],
                text_color=COLORS["cyan"] if i == 0 else COLORS["text_dim"],
                border_width=0, corner_radius=0, height=40,
                command=lambda idx=i: self._switch(idx)
            )
            btn.pack(side="left")
            self._buttons.append(btn)

        # Separator
        ctk.CTkFrame(self, fg_color=COLORS["cyan"], width=2).pack(side="left", fill="y", padx=4)
        # Right spacer
        ctk.CTkLabel(self, text="", fg_color="transparent").pack(side="right", fill="x", expand=True)
        # Version
        ctk.CTkLabel(self, text="v1.0 ALPHA  ",
                     font=("Courier New", 9), text_color=COLORS["text_dim"]).pack(side="right")

    def _switch(self, idx):
        for i, btn in enumerate(self._buttons):
            if i == idx:
                btn.configure(fg_color=COLORS["bg"], text_color=COLORS["cyan"])
            else:
                btn.configure(fg_color="transparent", text_color=COLORS["text_dim"])
        self._active = idx
        self._on_change(idx)


# ═══════════════════════════════════════════════════════════════════════════
# APPLICATION PRINCIPALE
# ═══════════════════════════════════════════════════════════════════════════

class SQLRiftApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SQLRIFT — Database Manager")
        self.geometry("1100x720")
        self.minsize(800, 560)
        self.configure(fg_color=COLORS["bg"])
        self._build()

    def _build(self):
        # Status bar
        self._status = StatusBar(self)
        self._status.pack(side="bottom", fill="x")

        # Separator
        ctk.CTkFrame(self, fg_color=COLORS["border_glow"], height=1).pack(side="bottom", fill="x")

        # Tab bar
        TABS = [
            ("◈", "DATABASE EDITOR"),
            ("◇", "SQL GENERATOR"),
            ("◆", "UML / DRAWIO"),
        ]
        self._tabbar = TabBar(self, TABS, on_change=self._switch_tab)
        self._tabbar.pack(side="top", fill="x")

        # Separator under tabs
        ctk.CTkFrame(self, fg_color=COLORS["cyan"], height=1).pack(fill="x")

        # Content frame
        self._content = ctk.CTkFrame(self, fg_color=COLORS["bg"])
        self._content.pack(fill="both", expand=True)

        # Create all tabs
        self._tabs = [
            DatabaseEditorTab(self._content, self._status),
            SQLGeneratorTab(self._content, self._status),
            DrawioTab(self._content, self._status),
        ]
        self._current = 0
        self._tabs[0].pack(fill="both", expand=True)

    def _switch_tab(self, idx):
        self._tabs[self._current].pack_forget()
        self._current = idx
        self._tabs[idx].pack(fill="both", expand=True)


# ─── LANCEMENT ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = SQLRiftApp()
    app.mainloop()
