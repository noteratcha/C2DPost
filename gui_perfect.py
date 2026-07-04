import os

import sys

import glob

import threading

from datetime import datetime

import tkinter as tk

from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

import pandas as pd

from PIL import Image



# Import conversion functions and version from convert_dpost

try:

    from convert_dpost import process_pdf, records_to_dataframe, __version__

except ImportError:

    def process_pdf(path): return []

    def records_to_dataframe(records): return pd.DataFrame()



# Set ctk options

# Set ctk options

ctk.set_appearance_mode("light")  # Modes: "System", "Dark", "Light"

class AutoScrollbar(ttk.Scrollbar):

    def set(self, lo, hi):

        if float(lo) <= 0.0 and float(hi) >= 1.0:

            self.pack_forget()

        else:

            if not self.winfo_ismapped():

                if self.cget("orient") == "horizontal":

                    self.pack(side="bottom", fill="x")

                else:

                    self.pack(side="right", fill="y")

        super().set(lo, hi)

class StdoutRedirector:

    """Redirects stdout to a customtkinter CTkTextbox widget with pretty icon prefixing."""

    def __init__(self, text_widget):

        self.text_widget = text_widget



    def write(self, string):

        if not string.strip():

            return

            

        # Decorate logs dynamically for a premium developer feel

        decorated = string

        if "เริ่ม" in string:

            decorated = f"🚀 {string}"

        self.text_widget.insert('end', decorated + "\n")

        self.text_widget.see('end')

        self.text_widget.configure(state='disabled')



    def flush(self):

        pass



class DuplicateConfirmDialog(ctk.CTkToplevel):

    """Custom styled confirmation dialog for duplicate receiver detection."""

    def __init__(self, parent, dup_rows):

        super().__init__(parent)

        self.result = False

        self.title("⚠️ พบข้อมูลผู้รับซ้ำ")

        self.geometry("540x420")

        self.resizable(False, False)

        self.grab_set()  # Modal

        self.lift()

        self.focus_force()

        

        # Center on parent

        self.update_idletasks()

        px = parent.winfo_x() + parent.winfo_width()//2 - 270

        py = parent.winfo_y() + parent.winfo_height()//2 - 210

        self.geometry(f"+{px}+{py}")

        

        # --- Header ---

        header = ctk.CTkFrame(self, corner_radius=0, fg_color="#b45309", height=58)

        header.pack(fill='x')

        header.pack_propagate(False)

        header_inner = ctk.CTkFrame(header, fg_color="transparent")

        header_inner.pack(fill='both', expand=True, padx=20, pady=10)

        ctk.CTkLabel(header_inner, text="⚠️ พบข้อมูลผู้รับซ้ำ",

                     font=("Segoe UI", 15, "bold"), text_color="#fff7ed").pack(side='left')

        ctk.CTkLabel(header_inner, text=f"{len(dup_rows)} รายการ",
                     font=("Segoe UI", 12), text_color="#fed7aa").pack(side='right')

        header.pack(fill='x')
        header.pack_propagate(False)
        header_inner = ctk.CTkFrame(header, fg_color="transparent")

        header_inner.pack(fill='both', expand=True, padx=20, pady=10)

        ctk.CTkLabel(header_inner, text="⚠️ พบข้อมูลผู้รับซ้ำ",

                     font=("Segoe UI", 15, "bold"), text_color="#fff7ed").pack(side='left')

        ctk.CTkLabel(header_inner, text=f"{len(dup_rows)} รายการ",

                     font=("Segoe UI", 12), text_color="#fed7aa").pack(side='right')

        

        # --- Body ---

        body = ctk.CTkFrame(self, fg_color="transparent")

        body.pack(fill='both', expand=True, padx=20, pady=15)

        

        ctk.CTkLabel(body,

                     text=f"ค้นพบรายการผู้รับที่ซ้ำกับข้อมูลเดิม {len(dup_rows)} รายการ ดังนี้:",

                     font=("Segoe UI", 11), text_color=("#0f172a", "#f8fafc"),

                     justify="left", anchor="w").pack(anchor='w', pady=(0, 8))

        

        # Scrollable list of duplicate names

        list_frame = ctk.CTkScrollableFrame(body, height=180,

                                            fg_color=("#f1f5f9", "#1e293b"),

                                            corner_radius=8)

        list_frame.pack(fill='x')

        

        for i, row in enumerate(dup_rows[:20]):

            row_bg = ("#e2e8f0", "#273548") if i % 2 == 0 else ("#f1f5f9", "#1e293b")

            item = ctk.CTkFrame(list_frame, fg_color=row_bg, corner_radius=4, height=32)

            item.pack(fill='x', pady=1)

            item.pack_propagate(False)

            ctk.CTkLabel(item, text=f"•  {row['RECEIVER']}",
                         font=("Segoe UI", 10, "bold"),
                         text_color=("#1e293b", "#cbd5e1")).pack(side='left', padx=10)

        

        if len(dup_rows) > 20:

            ctk.CTkLabel(list_frame, text=f"  ...และอีก {len(dup_rows)-20} รายการ",

                         font=("Segoe UI", 9, "italic"),

                         text_color=("#64748b", "#94a3b8")).pack(anchor='w', padx=10, pady=4)

        

        ctk.CTkLabel(body, text="ต้องการเพิ่มรายการที่ซ้ำเข้าไปด้วยหรือไม่?",

                     font=("Segoe UI", 11, "bold"),

                     text_color=("#0f172a", "#f8fafc")).pack(anchor='w', pady=(10, 0))

        

        # --- Buttons ---

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")

        btn_frame.pack(fill='x', padx=20, pady=(0, 16))

        

        ctk.CTkButton(btn_frame, text=" ✔️ ใช่ — เพิ่มทั้งหมด ",

                      fg_color="#d97706", hover_color="#b45309",

                      font=("Segoe UI", 11, "bold"), height=36,

                      command=self._on_yes).pack(side='right', padx=(8, 0))

        

        ctk.CTkButton(btn_frame, text=" ❌ ไม่ — เพิ่มเฉพาะรายการใหม่ ",

                      fg_color=("#e2e8f0", "#334155"),

                      hover_color=("#cbd5e1", "#475569"),

                      text_color=("#0f172a", "#f8fafc"),

                      font=("Segoe UI", 11, "bold"), height=36,

                      command=self._on_no).pack(side='right')

        

        self.protocol("WM_DELETE_WINDOW", self._on_no)

        self.wait_window()



    def _on_yes(self):

        self.result = True

        self.destroy()



    def _on_no(self):

        self.result = False

        self.destroy()





class DPostConverterGUI(ctk.CTk):

    def __init__(self):

        super().__init__()

        

        self.title(f"Convert PDF To Excel v{__version__}")

        self.geometry("1100x780")

        self.minsize(950, 720)

        

        # Set modern window background

        self.configure(fg_color=("#f8fafc", "#0f172a"))

        

        self.title(f"Convert PDF To Excel v{__version__}")

        self.geometry("1100x780")

        self.minsize(950, 720)

        

        # Set modern window background

        self.configure(fg_color=("#f8fafc", "#0f172a"))

        

        self.selected_files = []

        self.parsed_records = []

        self.dataframe = None

        self._append_mode = False  # Flag for append vs replace conversion

        # Redirect stdout
        sys.stdout = StdoutRedirector(self.log_text)
        
        # Setup keyboard shortcuts for advanced UX
        self.bind("<Control-o>", lambda e: self.select_files())
        self.bind("<Control-O>", lambda e: self.select_files())
        self.bind("<Control-s>", lambda e: self.export_excel_shortcut())
        self.bind("<Control-S>", lambda e: self.export_excel_shortcut())
        self.bind("<Escape>", self.on_escape_press)


    def create_layout(self):

        # 1. Header Banner

        header = ctk.CTkFrame(self, corner_radius=0, fg_color=("#166534", "#052e16"), height=70)

        header.pack(fill='x', side='top')

        header.pack_propagate(False)

        

        # Center container in header for nice padding

        header_content = ctk.CTkFrame(header, fg_color="transparent")

        header_content.pack(fill='both', expand=True, padx=30, pady=10)

        title_lbl.pack(anchor='w', side='left')

        

        # Theme toggle switch on the right side of header

        self.switch_theme = ctk.CTkSwitch(header_content, text="โหมดมืด (Dark Mode)", 

                                           font=("Segoe UI", 10, "bold"), text_color="#cbd5e1",

                                           command=self.toggle_theme)

        self.switch_theme.select() # Default to dark mode selected

        self.switch_theme.pack(anchor='e', side='right', padx=10)



        # 2. Sub-header Instruction Bar (Step-by-step guidance)

        instruction_bar = ctk.CTkFrame(self, corner_radius=8, border_width=1, border_color=("#cbd5e1", "#334155"))

        instruction_bar.pack(fill='x', padx=20, pady=(15, 0))

        

        center_frame = ctk.CTkFrame(instruction_bar, fg_color="transparent")

        center_frame.pack(anchor='center', pady=8)

        

        icon_lbl = ctk.CTkLabel(center_frame, text="💡 ขั้นตอนการทำงาน:", font=("Segoe UI", 11, "bold"), text_color="#38bdf8")

        icon_lbl.pack(side='left', padx=(0, 10))

        

        self.lbl_step1 = ctk.CTkLabel(center_frame, text=" [1] เลือกไฟล์ PDF (หรือโฟลเดอร์) ", font=("Segoe UI", 11, "bold"), text_color=("#64748b", "#94a3b8"), padx=8, pady=3)

        self.lbl_step1.pack(side='left')

        

        arrow1 = ctk.CTkLabel(center_frame, text=" ➔ ", font=("Segoe UI", 11), text_color="#64748b")

        arrow1.pack(side='left')

        

        self.lbl_step2 = ctk.CTkLabel(center_frame, text=" [2] เริ่มแปลงข้อมูล (ขวาบน) ", font=("Segoe UI", 11, "bold"), text_color=("#64748b", "#94a3b8"), padx=8, pady=3)

        self.lbl_step2.pack(side='left')

        

        arrow2 = ctk.CTkLabel(center_frame, text=" ➔ ", font=("Segoe UI", 11), text_color="#64748b")

        arrow2.pack(side='left')

        

        self.lbl_step3 = ctk.CTkLabel(center_frame, text=" [3] บันทึกไฟล์ Excel... (ขวาล่าง) ", font=("Segoe UI", 11, "bold"), text_color=("#64748b", "#94a3b8"), padx=8, pady=3)

        self.lbl_step3.pack(side='left')



        # 3. Main Container

        container = ctk.CTkFrame(self, fg_color="transparent")

        container.pack(fill='both', expand=True, padx=20, pady=15)

        

        # Grid config

        container.columnconfigure(0, weight=1)

        container.rowconfigure(0, weight=0) # File Selection Card

        container.rowconfigure(1, weight=3) # Preview Table Card

        container.rowconfigure(2, weight=2) # Log & Export Card



        # --- Card 1: File Selection & Controls ---

        card_files = ctk.CTkFrame(container, corner_radius=10, border_width=1, border_color=("#cbd5e1", "#334155"))

        card_files.grid(row=0, column=0, sticky='nsew', pady=(0, 10))

        

        ctk.CTkLabel(card_files, text="1. เลือกแหล่งข้อมูลเอกสาร PDF", font=("Segoe UI", 12, "bold"), 

                     text_color=("#0f172a", "#f8fafc")).pack(anchor='w', padx=20, pady=(12, 5))

        

        btn_frame = ctk.CTkFrame(card_files, fg_color="transparent")

        btn_frame.pack(fill='x', padx=20, pady=(5, 10))

        

        self.btn_select_files = ctk.CTkButton(btn_frame, text=" 📄 เลือกไฟล์ PDF... ", fg_color="#0284c7", hover_color="#0369a1",

                                              font=("Segoe UI", 11, "bold"), command=self.select_files, width=170)

        self.btn_select_files.pack(side='left', padx=(0, 10))

        

        self.btn_append_files = ctk.CTkButton(btn_frame, text=" ➕ เพิ่มไฟล์ PDF... ", fg_color="#7c3aed", hover_color="#6d28d9",

                                              font=("Segoe UI", 11, "bold"), command=self.append_files, width=170, state='disabled')

        self.btn_append_files.pack(side='left', padx=(0, 10))

        

        self.btn_clear = ctk.CTkButton(btn_frame, text=" 🧹 ล้างข้อมูล ", fg_color="#475569", hover_color="#334155",

                                       font=("Segoe UI", 11, "bold"), command=self.clear_selection, width=110)

        self.btn_clear.pack(side='left', padx=(0, 20))

        

        self.lbl_status = ctk.CTkLabel(btn_frame, text="ยังไม่ได้เลือกไฟล์", font=("Segoe UI", 11, "italic"), text_color=("#475569", "#94a3b8"))

        self.lbl_status.pack(side='left', fill='x', expand=True, anchor='w')

        

        self.btn_convert = ctk.CTkButton(btn_frame, text=" ⚡ เริ่มแปลงข้อมูล ", fg_color="#0f766e", hover_color="#0d9488",

                                         font=("Segoe UI", 11, "bold"), command=self.start_conversion, state='disabled', width=170)

        self.btn_convert.pack(side='right')



        # Progress bar

        self.progress = ctk.CTkProgressBar(card_files, progress_color="#0f766e", height=8)

        self.progress.pack(fill='x', padx=20, pady=(0, 12))

        self.progress.set(0)



        # --- Card 2: Preview Table ---

        card_preview = ctk.CTkFrame(container, corner_radius=10, border_width=1, border_color=("#cbd5e1", "#334155"))

        card_preview.grid(row=1, column=0, sticky='nsew', pady=(0, 10))

        

        # Header frame with real-time search box

        preview_header = ctk.CTkFrame(card_preview, fg_color="transparent")

        preview_header.pack(fill='x', padx=20, pady=(10, 5))

        

        title_lbl = ctk.CTkLabel(preview_header, text="2. ตารางตัวอย่างข้อมูลหลังสกัด (Preview)", font=("Segoe UI", 12, "bold"), 

                                 text_color=("#0f172a", "#f8fafc"))

        title_lbl.pack(side='left')

        

        self.search_entry = ctk.CTkEntry(preview_header, placeholder_text=" 🔍 ค้นหาผู้รับ / ผู้ส่ง / เลขอ้างอิง... ", 

                                         width=300, height=28, font=("Segoe UI", 11))

        self.search_entry.pack(side='right')

        self.search_entry.bind("<KeyRelease>", self.filter_treeview)

        self.search_entry.bind("<Escape>", self.clear_search)



        table_frame = ctk.CTkFrame(card_preview, fg_color="transparent")

        table_frame.pack(fill='both', expand=True, padx=20, pady=(0, 15))

        

        # Scrollbars for Treeview

        vsb = ttk.Scrollbar(table_frame, orient="vertical")

        hsb = ttk.Scrollbar(table_frame, orient="horizontal")

        

        # Setup Styles for treeview

        self.preview_cols = ["NO", "INV_NO", "RECEIVER", "RECEIVER_ADDRESS", "RECEIVER_ZIPCODE"]

        col_widths = {"NO": 50, "INV_NO": 130, "RECEIVER": 180, "RECEIVER_ADDRESS": 450, "RECEIVER_ZIPCODE": 110}

        col_titles = {"NO": "ลำดับ", "INV_NO": "เลขที่อ้างอิง", "RECEIVER": "ผู้รับ", "RECEIVER_ADDRESS": "ที่อยู่ผู้รับ (ที่อยู่ / อำเภอ / จังหวัด)", "RECEIVER_ZIPCODE": "รหัสไปรษณีย์"}

        

        self.tree = ttk.Treeview(table_frame, columns=self.preview_cols, show="headings", 

                                 yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        

        vsb.config(command=self.tree.yview)

        hsb.config(command=self.tree.xview)

        

        for col in self.preview_cols:

            self.tree.heading(col, text=col_titles[col], anchor='w')

            self.tree.column(col, width=col_widths[col], minwidth=50, anchor='w')

            

        vsb.pack(side='right', fill='y')

        hsb.pack(side='bottom', fill='x')

        self.tree.pack(side='left', fill='both', expand=True)



        # Style Treeview initially for dark mode

        self.style_treeview("dark")



        # --- Card 3: Log console & Save Action ---

        card_footer = ctk.CTkFrame(container, fg_color="transparent")

        card_footer.grid(row=2, column=0, sticky='nsew')

        card_footer.columnconfigure(0, weight=2) # Log console

        card_footer.columnconfigure(1, weight=1) # Export Panel

        card_footer.rowconfigure(0, weight=1)

        

        # Card 3a: Logs

        log_frame = ctk.CTkFrame(card_footer, corner_radius=10, border_width=1, border_color=("#cbd5e1", "#334155"))

        log_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 10))

        

        ctk.CTkLabel(log_frame, text="3. รายละเอียดการทำงาน (Log)", font=("Segoe UI", 12, "bold"), 

                     text_color=("#0f172a", "#f8fafc")).pack(anchor='w', padx=20, pady=(12, 5))

        

        self.log_text = ctk.CTkTextbox(log_frame, state='disabled', fg_color=("#f1f5f9", "#0f172a"), text_color=("#0f172a", "#38bdf8"), 

                                       font=("Consolas", 11), corner_radius=6)

        self.log_text.pack(fill='both', expand=True, padx=20, pady=(0, 15))

        

        # Card 3b: Export panel

        export_frame = ctk.CTkFrame(card_footer, corner_radius=10, border_width=1, border_color=("#cbd5e1", "#334155"))

        export_frame.grid(row=0, column=1, sticky='nsew')

        

        ctk.CTkLabel(export_frame, text="4. นำออกไฟล์ Excel", font=("Segoe UI", 12, "bold"), 

                     text_color=("#0f172a", "#f8fafc")).pack(anchor='w', padx=20, pady=(12, 5))

        

        export_inner = ctk.CTkFrame(export_frame, fg_color="transparent")

        export_inner.pack(fill='both', expand=True, padx=20, pady=10)

        

        # Stats summary dashboard frame

        self.stats_frame = ctk.CTkFrame(export_inner, fg_color=("#f1f5f9", "#1e293b"), corner_radius=6)

        self.stats_frame.pack(fill='x', pady=(0, 10))

        

        self.lbl_stat_files = ctk.CTkLabel(self.stats_frame, text="📂 ไฟล์ PDF: 0 ไฟล์", font=("Segoe UI", 11, "bold"), text_color=("#475569", "#cbd5e1"))

        self.lbl_stat_files.pack(anchor='w', padx=15, pady=(8, 3))

        

        self.lbl_stat_records = ctk.CTkLabel(self.stats_frame, text="👥 รายการผู้รับ: 0 รายการ", font=("Segoe UI", 11, "bold"), text_color=("#475569", "#cbd5e1"))



        

        export_action_frame = ctk.CTkFrame(preview_footer, fg_color="transparent")

        export_action_frame.pack(side='right')

        

        self.lbl_export_status = ctk.CTkLabel(export_action_frame, text="กรุณาแปลงข้อมูลก่อนบันทึก", 

                                              font=("Segoe UI", 11, "italic"), text_color=("#64748b", "#94a3b8"))

        # self.lbl_export_status.pack(side='left', padx=(0, 10))





        # --- Log Popup Dialog ---

        self.log_popup = ctk.CTkToplevel(self)

        self.log_popup.title("รายละเอียดการทำงาน (Log)")

        self.log_popup.geometry("600x400")

        self.log_popup.withdraw() # Hide by default

        self.log_popup.protocol("WM_DELETE_WINDOW", self.log_popup.withdraw)

        

        self.log_text = ctk.CTkTextbox(self.log_popup, state='disabled', fg_color="#f8fafc", text_color="#334155", 

                                       font=("Consolas", 12), corner_radius=12)

        self.log_text.pack(fill='both', expand=True, padx=20, pady=20)

        

        if mode == "dark":

            bg = "#1e293b"          # Dark slate

            fg = "#f8fafc"          # Light text

            headings_bg = "#334155" # Slate 700

            selected_bg = "#475569" # Slate 600

            border_color = "#1e293b"

        else:

            bg = "#ffffff"          # White

            fg = "#0f172a"          # Dark slate text

            headings_bg = "#f1f5f9" # Slate 100

            selected_bg = "#cbd5e1" # Slate 300

            border_color = "#ffffff"

            

        style.configure('Treeview', 

                        background=bg, 

                        foreground=fg, 

                        rowheight=32, 

                        fieldbackground=bg, 

                        font=('Segoe UI', 11),

                        borderwidth=0)

        style.map('Treeview', 

                  background=[('selected', selected_bg)], 

                  foreground=[('selected', '#ffffff' if mode == "dark" else '#0f172a')])

        

        style.configure('Treeview.Heading', 

                        background=headings_bg, 

                        foreground=fg, 

                        font=('Segoe UI', 11, 'bold'),

                        relief='flat',

                        padding=5)





    def set_current_step(self, step):

        """Highlights the active step label and dims inactive steps."""

        for s_num, lbl in {1: self.lbl_step1, 2: self.lbl_step2, 3: self.lbl_step3}.items():

            if s_num == step:

                # Active style: Primary color background with white text

                lbl.configure(text_color="#ffffff", fg_color="#0284c7")

            else:

                # Inactive style: Muted gray text, transparent background

                lbl.configure(text_color=("#64748b", "#94a3b8"), fg_color="transparent")



    def toggle_theme(self):

                  foreground=[('selected', '#ffffff' if mode == "dark" else '#0f172a')])

        

        style.configure('Treeview.Heading', 

                        background=headings_bg, 

                        foreground=fg, 

                        font=('Segoe UI', 11, 'bold'),

    def set_current_step(self, step):

        """Highlights the active step label and dims inactive steps."""

        for s_num, lbl in {1: self.lbl_step1, 2: self.lbl_step2, 3: self.lbl_step3}.items():

            if s_num == step:

                # Active style: Primary color

                lbl.configure(text_color="#166534", fg_color="#86EFAC")

            else:

                # Inactive style: Muted gray text, transparent background

                lbl.configure(text_color="#94a3b8", fg_color="transparent")



    # --- UX Dynamic Helpers ---

    

    def update_stats(self):

        """Updates the mini-dashboard stats panel."""

        file_count = len(self.selected_files)

            amphur = str(row.get("RECEIVER_AMPHUR", "")).lower()

            province = str(row.get("RECEIVER_PROVINCE", "")).lower()

            zipcode = str(row.get("RECEIVER_ZIPCODE", "")).lower()

            

            # Combine full address: address + amphur + province

            parts = [str(row.get("RECEIVER_ADDRESS", "")),

                     str(row.get("RECEIVER_AMPHUR", "")),

                     str(row.get("RECEIVER_PROVINCE", ""))]

            full_address = " ".join(p for p in parts if p.strip())

            

            if (not query) or (query in inv_no or query in receiver or query in address or query in amphur or query in province or query in zipcode):

                values = [

                    row.get("NO", idx+1),

                    row.get("INV_NO", ""),

                    row.get("RECEIVER", ""),

                    full_address,

                    row.get("RECEIVER_ZIPCODE", "")

                ]

                self.tree.insert("", "end", values=values)



    def clear_search(self, event=None):

        """Clears the search entry content and resets view."""

        self.search_entry.delete(0, tk.END)

        self.filter_treeview()



            

            # Combine full address: address + amphur + province

            parts = [str(row.get("RECEIVER_ADDRESS", "")),

                     str(row.get("RECEIVER_AMPHUR", "")),

                     str(row.get("RECEIVER_PROVINCE", ""))]

            full_address = " ".join(p for p in parts if p.strip())

            

            if (not query) or (query in inv_no or query in receiver or query in address or query in amphur or query in province or query in zipcode):

                values = [

            self.focus_set() # Unfocus search entry

        else:

            self.clear_selection()



    # --- Command Event Handlers ---

    

    def select_files(self):

        files = filedialog.askopenfilenames(

            title="เลือกไฟล์ PDF ใบนำส่ง DPost",

            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]

        )

        if files:

            self.selected_files = list(files)

            self.update_file_selection_status()



    def select_directory(self):

        directory = filedialog.askdirectory(title="เลือกโฟลเดอร์ที่เก็บไฟล์ PDF")

        if directory:

            files = glob.glob(os.path.join(directory, "*.pdf"))

            if files:

                self.selected_files = files

                self.update_file_selection_status()

            else:

                messagebox.showwarning("ไม่พบไฟล์", "ไม่พบไฟล์ PDF ในโฟลเดอร์ที่เลือก")



    def append_files(self):

        """Opens additional PDF files and appends them to existing data with duplicate checking."""

        files = filedialog.askopenfilenames(

            title="เพิ่มไฟล์ PDF ใบนำส่ง DPost (Append Mode)",

            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]

        )

        if files:

            # Merge new files into selected_files (avoid exact path duplicates)

            existing = set(self.selected_files)

            new_files = [f for f in files if f not in existing]

            if not new_files:

                messagebox.showinfo("ไม่มีไฟล์ใหม่", "ไฟล์ที่เลือกทั้งหมดถูกโหลดแล้ว")

                return

            self.selected_files.extend(new_files)

            count = len(self.selected_files)

            self.lbl_status.configure(

                text=f"โหมดเพิ่มข้อมูล: ไฟล์ทั้งหมด {count} ไฟล์ (เพิ่ม {len(new_files)} ไฟล์ใหม่)",

                text_color=("#7c3aed", "#a78bfa")

            )

            self._append_mode = True

            self.btn_convert.configure(state='normal')

            self.progress.set(0)

            self.update_stats()

            self.set_current_step(2)



    def update_file_selection_status(self):

        count = len(self.selected_files)

        if count == 1:

            name = os.path.basename(self.selected_files[0])

            self.lbl_status.configure(text=f"เลือกไฟล์: {name}", text_color=("#0284c7", "#38bdf8"))

        else:

            self.lbl_status.configure(text=f"เลือกไฟล์ทั้งหมด {count} ไฟล์", text_color=("#0284c7", "#38bdf8"))

        

        self._append_mode = False

        self.btn_convert.configure(state='normal')

        self.progress.set(0)

        self.btn_export.configure(state='disabled')

        self.lbl_export_status.configure(text="พร้อมเริ่มแปลงข้อมูล", text_color=("#475569", "#94a3b8"))

        

        # Update dynamic stats panel

        self.update_stats()

    def select_files(self):

        files = filedialog.askopenfilenames(

            title="เลือกไฟล์ PDF ใบนำส่ง DPost",

            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]

        )

        if files:

            self.selected_files = list(files)

            self.update_file_selection_status()



    def select_directory(self):

        directory = filedialog.askdirectory(title="เลือกโฟลเดอร์ที่เก็บไฟล์ PDF")

        if directory:

            files = glob.glob(os.path.join(directory, "*.pdf"))

            if files:

                self.selected_files = files

                self.update_file_selection_status()

            else:

                messagebox.showwarning("ไม่พบไฟล์", "ไม่พบไฟล์ PDF ในโฟลเดอร์ที่เลือก")



    def append_files(self):

        """Opens additional PDF files and appends them to existing data with duplicate checking."""

        files = filedialog.askopenfilenames(

            title="เพิ่มไฟล์ PDF ใบนำส่ง DPost (Append Mode)",

            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]

        )

        if files:

            # Merge new files into selected_files (avoid exact path duplicates)

            existing = set(self.selected_files)

            new_files = [f for f in files if f not in existing]

            if not new_files:

                messagebox.showinfo("ไม่มีไฟล์ใหม่", "ไฟล์ที่เลือกทั้งหมดถูกโหลดแล้ว")

                return

            self.selected_files.extend(new_files)

            count = len(self.selected_files)

            self.lbl_status.configure(

                text=f"โหมดเพิ่มข้อมูล: ไฟล์ทั้งหมด {count} ไฟล์ (เพิ่ม {len(new_files)} ไฟล์ใหม่)",

                text_color=("#7c3aed", "#a78bfa")

            )

            self._append_mode = True

            self.btn_convert.configure(state='normal')

            self.progress.set(0)

            self.update_stats()

            self.set_current_step(2)

            self.start_conversion()

            self.progress.set(0)


            self.update_stats()


            self.set_current_step(2)


            self.start_conversion()





    def update_file_selection_status(self):


        count = len(self.selected_files)


        if count == 1:


            name = os.path.basename(self.selected_files[0])


            self.lbl_status.configure(text=f"เน€เธโฌเน€เธเธ…เน€เธเธ—เน€เธเธเน€เธยเน€เธยเน€เธยเน€เธเธ…เน€เธย: {name}", text_color=("#15803D", "#4ADE80"))


        else:


            self.lbl_status.configure(text=f"เน€เธโฌเน€เธเธ…เน€เธเธ—เน€เธเธเน€เธยเน€เธยเน€เธยเน€เธเธ…เน€เธยเน€เธโ€”เน€เธเธ‘เน€เธยเน€เธยเน€เธเธเน€เธเธเน€เธโ€ {count} เน€เธยเน€เธยเน€เธเธ…เน€เธย", text_color=("#15803D", "#4ADE80"))


        


        self.btn_select_files.configure(text=" เนยโ€ข เน€เธโฌเน€เธยเน€เธเธ”เน€เธยเน€เธเธเน€เธยเน€เธยเน€เธเธ…เน€เธย (Append) ", command=self.append_files)


        


        self._append_mode = False





        self.progress.set(0)


        self.btn_export.configure(state='disabled', fg_color='#cbd5e1')


        self.lbl_export_status.configure(text="เน€เธยเน€เธเธเน€เธยเน€เธเธเน€เธเธเน€เธโฌเน€เธเธเน€เธเธ”เน€เธยเน€เธเธเน€เธยเน€เธยเน€เธเธ…เน€เธยเน€เธยเน€เธยเน€เธเธเน€เธเธเน€เธเธเน€เธเธ…", text_color=("#475569", "#94a3b8"))


        


        # Update dynamic stats panel


        self.update_stats()


        


        # Transition to step 2 (ready to convert)


        self.set_current_step(2)


        


        # Auto start conversion


        self.start_conversion()





    def clear_selection(self):


        self.selected_files = []


        self.parsed_records = []


        self.dataframe = None


        self._append_mode = False


        self._prev_file_count = 0


        self.lbl_status.configure(text="เน€เธเธเน€เธเธ‘เน€เธยเน€เธยเน€เธเธเน€เธยเน€เธยเน€เธโ€เน€เธยเน€เธโฌเน€เธเธ…เน€เธเธ—เน€เธเธเน€เธยเน€เธยเน€เธยเน€เธเธ…เน€เธย", text_color="#94a3b8")


        self.btn_select_files.configure(text=" เนยโ€ย เน€เธโฌเน€เธเธ…เน€เธเธ—เน€เธเธเน€เธยเน€เธยเน€เธยเน€เธเธ…เน€เธย PDF... ", command=self.select_files, state='normal', fg_color='#3b82f6')





        self.btn_export.configure(state='disabled', fg_color='#cbd5e1')


        self.lbl_export_status.configure(text="เน€เธยเน€เธเธเน€เธเธเน€เธโ€เน€เธเธ’เน€เธยเน€เธยเน€เธเธ…เน€เธยเน€เธยเน€เธยเน€เธเธเน€เธเธเน€เธเธเน€เธเธ…เน€เธยเน€เธยเน€เธเธเน€เธยเน€เธยเน€เธเธ‘เน€เธยเน€เธโ€”เน€เธเธ–เน€เธย", text_color=("#475569", "#94a3b8"))


        # Clear preview table

        for item in self.tree.get_children():

            self.tree.delete(item)

            

        # Clear log text

        self.log_text.configure(state='normal')

        self.log_text.delete('1.0', tk.END)

        self.log_text.configure(state='disabled')

        

        # Reset to step 1

        self.set_current_step(1)



    def start_conversion(self):

        # Disable buttons during work



    def start_conversion(self):

        # Disable buttons during work

        self.btn_select_files.configure(state='disabled')



        self.btn_clear.configure(state='disabled')

        

        self.lbl_status.pack_forget()

        self.progress.pack(side='left', fill='both', expand=True, padx=(2, 0), pady=2)

        self.lbl_percent.pack(side='right', padx=15)

        self.progress.set(0)

            for item in self.tree.get_children():

                self.tree.delete(item)

            

        # Run conversion in background thread

        thread = threading.Thread(target=self.run_conversion_task)

                for _, row in new_df.iterrows():

                    key = (str(row['RECEIVER']).strip().lower(),

                           str(row['RECEIVER_ADDRESS']).strip().lower())

                    if key in existing_keys:

                        dup_rows.append(row)

                    else:

                        non_dup_rows.append(row)

                

                if dup_rows:

                    dlg = DuplicateConfirmDialog(self, dup_rows)

                    confirm = dlg.result

                    if confirm:

                        rows_to_add = non_dup_rows + dup_rows

                    else:

                        rows_to_add = non_dup_rows

                else:

                    rows_to_add = non_dup_rows

                

                if not rows_to_add:

                    self.after(0, self.conversion_failed, "ไม่มีรายการใหม่ที่จะเพิ่ม (ทั้งหมดซ้ำและผู้ใช้ไม่ยืนยัน)")

                    return

                

                added_df = pd.DataFrame(rows_to_add)

                combined = pd.concat([self.dataframe, added_df], ignore_index=True)

                # Renumber NO column

                combined['NO'] = range(1, len(combined) + 1)

                self.dataframe = combined

                self.parsed_records.extend(new_records)

                self._prev_file_count = len(self.selected_files)

                self._append_mode = False

                self.after(0, self.conversion_success, len(rows_to_add))

                

            else:

                # Replace mode

                print(f"=== เริ่มการแปลงข้อมูล ({datetime.now().strftime('%H:%M:%S')}) ===")

                self.parsed_records = []

                

                total_files = len(self.selected_files)

                for index, file_path in enumerate(self.selected_files, 1):

            print(f"เกิดข้อผิดพลาด: {str(e)}\n")

            self.after(0, self.conversion_failed, str(e))



    def update_progress(self, val):

        self.progress.set(val)



    def conversion_success(self, append_info=None):

        # Re-enable action buttons but lock file selection to prevent data replacement

        self.btn_select_files.configure(state='disabled')  # Lock: data already loaded

        self.btn_append_files.configure(state='normal')

        self.btn_convert.configure(state='normal')

        self.btn_clear.configure(state='normal')

        

        # Refresh Treeview preview

        self.filter_treeview()

            

        self.btn_export.configure(state='normal')

        total = len(self.dataframe)

        if append_info:

            self.lbl_export_status.configure(

                text=f"เพิ่มข้อมูลสำเร็จ รวมทั้งหมด {total} รายการ (เพิ่ม {append_info} รายการ)",

                text_color="#a855f7"

            )

        else:

            self.lbl_export_status.configure(

                text=f"แปลงข้อมูลสำเร็จ ค้นพบทั้งหมด {total} รายการ พร้อมนำออกไฟล์",

                text_color="#16a34a"

            )

        

        # Update dynamic stats panel

        self.update_stats()

        

        if append_info:

            messagebox.showinfo("เพิ่มข้อมูลสำเร็จ", f"เพิ่มข้อมูลสำเร็จ {append_info} รายการ\nรวมทั้งหมด {total} รายการ")

        else:

            messagebox.showinfo("เสร็จสิ้น", f"แปลงข้อมูลสำเร็จทั้งหมด {total} รายการ")

        

        # Transition to step 3 (ready to export)

        self.set_current_step(3)



    def conversion_failed(self, error_msg):

        # Re-enable file selection only if there is no existing data

        has_data = self.dataframe is not None and not self.dataframe.empty

        self.btn_select_files.configure(state='disabled' if has_data else 'normal')

        self.btn_append_files.configure(state='normal')

        self.btn_convert.configure(state='normal')

        self.btn_clear.configure(state='normal')

        

        self.btn_export.configure(state='disabled')

        self.lbl_export_status.configure(text="การแปลงข้อมูลล้มเหลว", text_color="#dc2626")

        

        # Reset stats

        self.update_stats()

        

        messagebox.showerror("เกิดข้อผิดพลาด", f"ไม่สามารถแปลงข้อมูลได้:\n{error_msg}")

                    self.dataframe = records_to_dataframe(self.parsed_records)

                    self._prev_file_count = len(self.selected_files)

                    self.after(0, self.conversion_success)

                else:

                    self.after(0, self.conversion_failed, "ไม่พบข้อมูลใบนำส่งที่ถูกต้องในไฟล์ PDF ที่เลือก")

                

        except Exception as e:

            print(f"เกิดข้อผิดพลาด: {str(e)}\n")

            self.after(0, self.conversion_failed, str(e))



    def update_progress(self, val):

        self.progress.set(val)

        self.lbl_percent.configure(text=f"{int(val * 100)}%")



    def conversion_success(self, append_info=None):

        self.progress.pack_forget()

        self.lbl_percent.pack_forget()

        self.lbl_status.pack(side='left', fill='x', expand=True, padx=15, pady=8, anchor='w')

        # Re-enable action buttons

        self.btn_select_files.configure(text=" ➕ เพิ่มไฟล์ (Append) ", command=self.append_files, state='normal')



        self.btn_clear.configure(state='normal')

        

        # Refresh Treeview preview

        self.filter_treeview()

            

        self.btn_export.configure(state='normal')

        total = len(self.dataframe)

        if append_info:

            self.lbl_export_status.configure(

                text=f"เพิ่มข้อมูลสำเร็จ รวมทั้งหมด {total} รายการ (เพิ่ม {append_info} รายการ)",

                text_color="#a855f7"

            )

        else:

            self.lbl_export_status.configure(

                text=f"แปลงข้อมูลสำเร็จ ค้นพบทั้งหมด {total} รายการ พร้อมนำออกไฟล์",

                text_color="#16a34a"

            )

        

        # Update dynamic stats panel

        self.update_stats()

        

        if append_info:

            messagebox.showinfo("เพิ่มข้อมูลสำเร็จ", f"เพิ่มข้อมูลสำเร็จ {append_info} รายการ\nรวมทั้งหมด {total} รายการ")

        else:

            messagebox.showinfo("เสร็จสิ้น", f"แปลงข้อมูลสำเร็จทั้งหมด {total} รายการ")

        

        # Transition to step 3 (ready to export)

        self.set_current_step(3)



    def conversion_failed(self, error_msg):

        self.progress.pack_forget()

        self.lbl_percent.pack_forget()

        self.lbl_status.pack(side='left', fill='x', expand=True, padx=15, pady=8, anchor='w')

        # Re-enable file selection only if there is no existing data

        has_data = self.dataframe is not None and not self.dataframe.empty

