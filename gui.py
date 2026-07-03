import os
import sys
import glob
import threading
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import customtkinter as ctk
import pandas as pd

try:
    from convert_dpost import process_pdf, records_to_dataframe, __version__
except ImportError:
    __version__ = "2026.0630.1801"
    def process_pdf(path): return []
    def records_to_dataframe(records): return pd.DataFrame()

ctk.set_appearance_mode("light")

# Colors matching the user's screenshot
COLOR_PRIMARY = "#15803d"      # Dark green (Header, primary buttons)
COLOR_SUCCESS = "#16a34a"      # Green
COLOR_BG = "#f8fafc"           # Very light gray for app background
COLOR_CARD = "#ffffff"         # White for cards
COLOR_BORDER = "#cbd5e1"       # Light gray border
COLOR_TEXT_MAIN = "#0f172a"    # Dark slate for main text
COLOR_TEXT_MUTED = "#64748b"   # Muted slate

class DPostConverterGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"Convert PDF To Excel v{__version__}")
        self.geometry("1300x800")
        self.configure(fg_color=COLOR_BG)
        
        self.selected_files = []
        self.parsed_records = []
        self.dataframe = None
        self.current_theme = "light"
        
        self.create_layout()
        self.style_treeview()
        
        self.bind("<Control-o>", lambda e: self.select_files())
        self.bind("<Control-O>", lambda e: self.select_files())
        self.bind("<Control-s>", lambda e: self.export_excel_shortcut())
        self.bind("<Control-S>", lambda e: self.export_excel_shortcut())
        self.bind("<Escape>", self.on_escape_press)

    def create_layout(self):
        # 1. Header Banner (Green)
        header = ctk.CTkFrame(self, fg_color=COLOR_PRIMARY, corner_radius=0, height=60)
        header.pack(fill='x', side='top')
        header.pack_propagate(False)
        
        ctk.CTkLabel(header, text="กรมที่ดิน", font=("Segoe UI", 18, "bold"), text_color="#ffffff").pack(side='left', padx=30)
        
        # Steps Indicator
        steps_frame = ctk.CTkFrame(header, fg_color="transparent")
        steps_frame.pack(side='right', padx=30)
        
        ctk.CTkLabel(steps_frame, text="💡 ขั้นตอนการทำงาน:", font=("Segoe UI", 12), text_color="#ffffff").pack(side='left', padx=(0, 15))
        
        self.lbl_step1 = ctk.CTkLabel(steps_frame, text=" [1] เลือกไฟล์ PDF ", font=("Segoe UI", 11, "bold"), text_color="#ffffff", fg_color="#166534", corner_radius=6)
        self.lbl_step1.pack(side='left', padx=5, ipady=3)
        ctk.CTkLabel(steps_frame, text="➔", font=("Segoe UI", 12), text_color="#86efac").pack(side='left', padx=2)
        
        self.lbl_step2 = ctk.CTkLabel(steps_frame, text=" [2] พรีวิวข้อมูล ", font=("Segoe UI", 11, "bold"), text_color="#ffffff", fg_color="#166534", corner_radius=6)
        self.lbl_step2.pack(side='left', padx=5, ipady=3)
        ctk.CTkLabel(steps_frame, text="➔", font=("Segoe UI", 12), text_color="#86efac").pack(side='left', padx=2)
        
        self.lbl_step3 = ctk.CTkLabel(steps_frame, text=" [3] บันทึกไฟล์ Excel ", font=("Segoe UI", 11, "bold"), text_color="#14532d", fg_color="#86efac", corner_radius=6)
        self.lbl_step3.pack(side='left', padx=5, ipady=3)
        
        # Main Container
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill='both', expand=True, padx=20, pady=15)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)
        
        # Card 1: File Selection
        card_files = ctk.CTkFrame(container, fg_color=COLOR_CARD, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        card_files.grid(row=0, column=0, sticky='nsew', pady=(0, 15))
        
        ctk.CTkLabel(card_files, text="1. เลือกเอกสาร PDF", font=("Segoe UI", 12, "bold"), text_color=COLOR_TEXT_MAIN).pack(anchor='w', padx=20, pady=(12, 5))
        
        btn_frame = ctk.CTkFrame(card_files, fg_color="transparent")
        btn_frame.pack(fill='x', padx=20, pady=(5, 12))
        
        self.btn_select_files = ctk.CTkButton(btn_frame, text=" ➕ เพิ่มไฟล์ (Append) ", fg_color=COLOR_PRIMARY, hover_color="#14532d",
                                                font=("Segoe UI", 12, "bold"), command=self.select_files, width=150, height=36)
        self.btn_select_files.pack(side='left', padx=(0, 10))
        
        self.btn_clear = ctk.CTkButton(btn_frame, text=" 🧹 ล้างข้อมูล ", fg_color="#f1f5f9", hover_color="#e2e8f0", text_color="#475569",
                                         font=("Segoe UI", 12, "bold"), command=self.clear_selection, width=100, height=36)
        self.btn_clear.pack(side='left')
        
        self.center_frame = ctk.CTkFrame(btn_frame, fg_color="transparent")
        self.center_frame.pack(side='left', fill='both', expand=True, padx=10)
        
        self.lbl_status = ctk.CTkLabel(self.center_frame, text="ยังไม่ได้เลือกไฟล์", font=("Segoe UI", 12), text_color=COLOR_PRIMARY)
        self.lbl_status.pack(fill='x', expand=True)
        
        self.btn_export = ctk.CTkButton(btn_frame, text=" ✖ บันทึกไฟล์ Excel... ", fg_color=COLOR_PRIMARY, hover_color="#14532d",
                                        font=("Segoe UI", 12, "bold"), command=self.export_excel, state='disabled', width=170, height=36)
        self.btn_export.pack(side='right')
        
        self.progress = ctk.CTkProgressBar(self.center_frame, progress_color=COLOR_PRIMARY, height=6)
        
        # Card 2: Preview Table
        card_preview = ctk.CTkFrame(container, fg_color=COLOR_CARD, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        card_preview.grid(row=1, column=0, sticky='nsew')
        
        preview_header = ctk.CTkFrame(card_preview, fg_color="transparent")
        preview_header.pack(fill='x', padx=20, pady=(15, 10))
        
        ctk.CTkLabel(preview_header, text="2. ตารางตัวอย่างข้อมูลหลังสกัด (Preview)", font=("Segoe UI", 12, "bold"), text_color=COLOR_TEXT_MAIN).pack(side='left')
        
        # Right aligned stats and search
        self.search_entry = ctk.CTkEntry(preview_header, placeholder_text=" 🔍 ค้นหาผู้รับ / เลขอ้างอิง... ", width=250, height=30, font=("Segoe UI", 11), corner_radius=15)
        self.search_entry.pack(side='right', padx=(15, 0))
        
        self.lbl_stat_records = ctk.CTkLabel(preview_header, text="👥 รายการผู้รับ: 0 รายการ", font=("Segoe UI", 11, "bold"), text_color=COLOR_TEXT_MUTED)
        self.lbl_stat_records.pack(side='right', padx=10)
        
        self.lbl_stat_files = ctk.CTkLabel(preview_header, text="📄 ไฟล์ PDF: 0 ไฟล์", font=("Segoe UI", 11, "bold"), text_color=COLOR_TEXT_MUTED)
        self.lbl_stat_files.pack(side='right', padx=10)
        
        self.search_entry.bind("<KeyRelease>", self.filter_treeview)
        self.search_entry.bind("<Escape>", self.clear_search)
        
        # Treeview in a standard tk.Frame so it expands correctly
        table_frame = tk.Frame(card_preview, bg=COLOR_CARD)
        table_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        
        vsb = ttk.Scrollbar(table_frame, orient="vertical")
        hsb = ttk.Scrollbar(table_frame, orient="horizontal")
        
        self.tree = ttk.Treeview(table_frame, selectmode="extended", yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)
        
        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')
        self.tree.pack(side='left', fill='both', expand=True)
        
        self.columns = [
            ("No", "ลำดับ", 50),
            ("Ref", "เลขที่อ้างอิง", 120),
            ("Receiver", "ผู้รับ", 180),
            ("Address", "ที่อยู่ผู้รับ (ที่อยู่ / อำเภอ / จังหวัด)", 450),
            ("Zip", "รหัสไปรษณีย์", 100)
        ]
        
        self.tree["columns"] = [col[0] for col in self.columns]
        self.tree["show"] = "headings"
        
        for col_id, col_name, col_width in self.columns:
            self.tree.heading(col_id, text=col_name, command=lambda _col=col_id: self.sort_treeview(_col, False))
            self.tree.column(col_id, width=col_width, minwidth=50, anchor='w' if col_id in ["Receiver", "Address"] else 'center')
            
        self.set_step(1)

    def style_treeview(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        bg = "#ffffff"
        fg = "#0f172a"
        headings_bg = "#f1f5f9"
        selected_bg = "#e2e8f0"
            
        style.configure('Treeview', background=bg, foreground=fg, rowheight=28, 
                        fieldbackground=bg, borderwidth=0, font=('Segoe UI', 10))
        style.map('Treeview', background=[('selected', selected_bg)], foreground=[('selected', '#0f172a')])
        
        style.configure('Treeview.Heading', background=headings_bg, foreground=fg, 
                        font=('Segoe UI', 11, 'bold'), borderwidth=1, relief="flat", padding=(5, 5))
        style.map('Treeview.Heading', background=[('active', '#e2e8f0')])

    def set_step(self, step):
        inactive_color = "#166534"
        active_color = "#86efac"
        
        self.lbl_step1.configure(fg_color=active_color if step == 1 else inactive_color, text_color="#14532d" if step == 1 else "#ffffff")
        self.lbl_step2.configure(fg_color=active_color if step == 2 else inactive_color, text_color="#14532d" if step == 2 else "#ffffff")
        self.lbl_step3.configure(fg_color=active_color if step == 3 else inactive_color, text_color="#14532d" if step == 3 else "#ffffff")

    def filter_treeview(self, event=None):
        query = self.search_entry.get().strip().lower()
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        if self.dataframe is None or self.dataframe.empty:
            return
            
        for idx, row in self.dataframe.iterrows():
            matches = False
            if not query:
                matches = True
            else:
                for col in self.dataframe.columns:
                    if query in str(row[col]).lower():
                        matches = True
                        break
            
            if matches:
                addr = f"{row.get('RECEIVER_ADDRESS', '')} {row.get('RECEIVER_DISTRICT', '')} {row.get('RECEIVER_PROVINCE', '')}".strip()
                self.tree.insert("", "end", values=(
                    idx + 1,
                    row.get('REF_NO', ''),
                    row.get('RECEIVER', ''),
                    addr,
                    row.get('RECEIVER_ZIPCODE', '')
                ))

    def clear_search(self, event=None):
        self.search_entry.delete(0, 'end')
        self.filter_treeview()
        self.focus()

    def export_excel_shortcut(self):
        if self.btn_export.cget('state') == 'normal':
            self.export_excel()

    def on_escape_press(self, event=None):
        if self.search_entry.get():
            self.clear_search()

    def sort_treeview(self, col_id, reverse):
        items = [(self.tree.set(k, col_id), k) for k in self.tree.get_children('')]
        try:
            items.sort(key=lambda t: float(t[0]), reverse=reverse)
        except ValueError:
            items.sort(reverse=reverse)
            
        for index, (val, k) in enumerate(items):
            self.tree.move(k, '', index)
        self.tree.heading(col_id, command=lambda: self.sort_treeview(col_id, not reverse))

    def clear_selection(self):
        self.selected_files = []
        self.parsed_records = []
        self.dataframe = None
        self.lbl_status.configure(text="ยังไม่ได้เลือกไฟล์")
        self.lbl_stat_files.configure(text="📄 ไฟล์ PDF: 0 ไฟล์")
        self.lbl_stat_records.configure(text="👥 รายการผู้รับ: 0 รายการ")
        
        self.btn_export.configure(state='disabled')
        self.btn_select_files.configure(text=" ➕ เพิ่มไฟล์ (Append) ")
        
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        self.set_step(1)

    def select_files(self):
        files = filedialog.askopenfilenames(
            title="เลือกไฟล์ PDF ใบนำส่ง DPost",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
        )
        if files:
            # Check for duplicates if already have files
            new_files = [f for f in files if f not in self.selected_files]
            if len(new_files) < len(files) and self.selected_files:
                messagebox.showinfo("ข้อมูลซ้ำ", f"พบไฟล์ที่เลือกไปแล้ว {len(files) - len(new_files)} ไฟล์\nระบบจะเพิ่มเฉพาะไฟล์ใหม่")
            
            if new_files:
                self.selected_files.extend(new_files)
                self.lbl_status.configure(text=f"เลือกไฟล์ทั้งหมด {len(self.selected_files)} ไฟล์")
                self.start_conversion(new_files)

    def start_conversion(self, files_to_process):
        self.btn_select_files.configure(state='disabled')
        self.btn_clear.configure(state='disabled')
        self.btn_export.configure(state='disabled')
        
        self.progress.pack(fill='x', side='bottom', pady=(0, 5))
        self.progress.set(0)
        
        self.set_step(2)
        
        thread = threading.Thread(target=self.run_conversion_task, args=(files_to_process,))
        thread.daemon = True
        thread.start()

    def run_conversion_task(self, files_to_process):
        new_records = []
        total = len(files_to_process)
        
        for i, filepath in enumerate(files_to_process):
            try:
                records = process_pdf(filepath)
                if records:
                    for r in records:
                        r['source_file'] = os.path.basename(filepath)
                    new_records.extend(records)
            except Exception as e:
                print(f"Error processing {os.path.basename(filepath)}: {e}")
                
            self.after(10, self.update_progress, (i + 1) / total)
            
        self.after(10, self.conversion_completed, new_records)

    def update_progress(self, val):
        self.progress.set(val)

    def conversion_completed(self, new_records):
        self.progress.pack_forget()
        
        if new_records:
            new_df = records_to_dataframe(new_records)
            
            if self.dataframe is None or self.dataframe.empty:
                self.dataframe = new_df
            else:
                # Merge dataframes
                self.dataframe = pd.concat([self.dataframe, new_df], ignore_index=True)
                
            self.parsed_records = self.dataframe.to_dict('records')
            
            self.lbl_stat_files.configure(text=f"📄 ไฟล์ PDF: {len(self.selected_files)} ไฟล์")
            self.lbl_stat_records.configure(text=f"👥 รายการผู้รับ: {len(self.dataframe)} รายการ")
            self.lbl_status.configure(text=f"ประมวลผลเสร็จสิ้น รวมทั้งหมด {len(self.dataframe)} รายการ")
            
            self.filter_treeview()
            self.set_step(3)
        else:
            if not self.parsed_records:
                self.lbl_status.configure(text="ไม่พบข้อมูลในไฟล์ที่เลือก")
                self.set_step(1)
        
        self.btn_select_files.configure(state='normal')
        self.btn_clear.configure(state='normal')
        if self.dataframe is not None and not self.dataframe.empty:
            self.btn_export.configure(state='normal')

    def export_excel(self):
        if self.dataframe is None or self.dataframe.empty:
            messagebox.showwarning("ไม่มีข้อมูล", "กรุณาแปลงไฟล์ PDF ก่อนบันทึก")
            return
            
        default_filename = f"DPost_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        initial_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
        
        filepath = filedialog.asksaveasfilename(
            title="บันทึกไฟล์ Excel",
            initialdir=initial_dir,
            initialfile=default_filename,
            defaultextension=".xlsx",
            filetypes=[("Excel Files", "*.xlsx")]
        )
        
        if filepath:
            try:
                export_df = self.dataframe.copy()
                if 'source_file' in export_df.columns:
                    export_df = export_df.drop('source_file', axis=1)
                    
                export_df.to_excel(filepath, index=False, engine='openpyxl')
                messagebox.showinfo("สำเร็จ", f"บันทึกไฟล์เรียบร้อยแล้วที่:\n{filepath}")
                self.lbl_status.configure(text="บันทึกไฟล์ Excel สำเร็จ")
                
                if sys.platform == "win32":
                    os.startfile(filepath)
            except Exception as e:
                messagebox.showerror("ข้อผิดพลาด", f"ไม่สามารถบันทึกไฟล์ได้:\n{str(e)}")

def main():
    app = DPostConverterGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
