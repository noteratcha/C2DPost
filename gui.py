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
COLOR_BG = "#ebebeb"           # Default CustomTkinter light background
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
        
        # Initialize hover image state
        self.gray_x_img = self.create_cross_image("#94a3b8")
        self.red_x_img = self.create_cross_image("#ef4444")
        self.tooltip_window = None

    def create_cross_image(self, color):
        img = tk.PhotoImage(width=16, height=16)
        # Draw a diagonal cross centered in 16x16
        for i in range(4, 12):
            img.put(color, (i, i))
            img.put(color, (15-i, i))
            img.put(color, (i+1, i))
            img.put(color, (i, i+1))
            img.put(color, (15-i-1, i))
            img.put(color, (15-i, i+1))
        return img

    def create_layout(self):
        # 1. Header Banner (Green)
        header = ctk.CTkFrame(self, fg_color=COLOR_PRIMARY, corner_radius=0, height=60)
        header.pack(fill='x', side='top')
        header.pack_propagate(False)
        
        ctk.CTkLabel(header, text="สำนักงานที่ดิน", font=("Segoe UI", 18, "bold"), text_color="#ffffff").pack(side='left', padx=30)
        
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
        
        self.btn_clear = ctk.CTkButton(btn_frame, text=" 🧹 ล้างข้อมูล ", fg_color="#f1f5f9", 
                                       hover_color="#fecaca", text_color="#ef4444",
                                       font=("Segoe UI", 12, "bold"), command=self.clear_selection, width=100, height=36)
        self.btn_clear.pack(side='left')
        
        self.center_frame = ctk.CTkFrame(btn_frame, fg_color="transparent")
        self.center_frame.pack(side='left', fill='both', expand=True, padx=30)
        
        self.status_box = ctk.CTkFrame(self.center_frame, fg_color="#f5f5f5", border_width=1, border_color=COLOR_BORDER, corner_radius=6)
        self.status_box.pack(fill='both', expand=True)
        
        self.lbl_status = ctk.CTkLabel(self.status_box, text="ยังไม่ได้เลือกไฟล์", font=("Segoe UI", 12), text_color=COLOR_PRIMARY)
        self.lbl_status.pack(fill='both', expand=True, pady=(8, 8))
        
        self.btn_export = ctk.CTkButton(btn_frame, text=" ✖ บันทึกไฟล์ Excel... ", fg_color=COLOR_PRIMARY, hover_color="#14532d",
                                        font=("Segoe UI", 12, "bold"), command=self.export_excel, state='disabled', width=170, height=36)
        self.btn_export.pack(side='right')
        
        self.progress = ctk.CTkProgressBar(self.status_box, progress_color=COLOR_PRIMARY, height=8, corner_radius=4)
        
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
        self.lbl_stat_files.bind("<Button-1>", self.show_selected_files_popup)
        self.lbl_stat_files.configure(cursor="hand2")
        
        self.search_entry.bind("<KeyRelease>", self.filter_treeview)
        self.search_entry.bind("<Escape>", self.clear_search)
        
        # Treeview in a standard tk.Frame so it expands correctly
        table_frame = tk.Frame(card_preview, bg=COLOR_CARD)
        table_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        
        vsb = ctk.CTkScrollbar(table_frame, orientation="vertical")
        
        self.tree = ttk.Treeview(table_frame, selectmode="extended", yscrollcommand=vsb.set)
        vsb.configure(command=self.tree.yview)
        
        vsb.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        self.tree.bind("<Motion>", self.on_tree_motion)
        self.tree.bind("<Leave>", self.on_tree_leave)
        
        self.columns = [
            ("View", "ดู", 40),
            ("No", "ลำดับ", 50),
            ("Ref", "เลขที่อ้างอิง", 120),
            ("Receiver", "ผู้รับ", 180),
            ("Address", "ที่อยู่ผู้รับ (ที่อยู่ / อำเภอ / จังหวัด)", 450),
            ("Zip", "รหัสไปรษณีย์", 100)
        ]
        
        self.tree["columns"] = [col[0] for col in self.columns]
        self.tree["show"] = "tree headings"
        
        # Configure tree column (#0) for Delete action
        self.tree.heading("#0", text="ลบ", anchor='center')
        self.tree.column("#0", width=55, minwidth=50, stretch=False, anchor='center')
        
        for col_id, col_name, col_width in self.columns:
            self.tree.heading(col_id, text=col_name, command=lambda _col=col_id: self.sort_treeview(_col, False))
            self.tree.column(col_id, width=col_width, minwidth=50, anchor='w' if col_id in ["Receiver", "Address"] else 'center')
            
        self.set_step(1)

    def style_treeview(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        bg = "#ffffff"
        fg = "#334155"
        headings_bg = "#e2e8f0"
        selected_bg = "#dbeafe"
            
        style.configure('Treeview', background=bg, foreground=fg, rowheight=35, 
                        fieldbackground=bg, borderwidth=0, font=('Segoe UI', 10))
        style.map('Treeview', background=[('selected', selected_bg)], foreground=[('selected', '#1e293b')])
        
        style.configure('Treeview.Heading', background=headings_bg, foreground="#0f172a", 
                        font=('Segoe UI', 10, 'bold'), borderwidth=0, relief="flat", padding=(5, 8))
        style.map('Treeview.Heading', background=[('active', '#cbd5e1')])
        
        # Tags for alternating row colors
        self.tree.tag_configure('oddrow', background="#ffffff")
        self.tree.tag_configure('evenrow', background="#f8fafc")

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
                addr = f"{row.get('RECEIVER_ADDRESS', '')} {row.get('RECEIVER_DISTRICT', '')} {row.get('RECEIVER_AMPHUR', '')} {row.get('RECEIVER_PROVINCE', '')}".strip()
                # Clean up double spaces if any component is missing
                addr = ' '.join(addr.split())
                tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
                self.tree.insert("", "end", iid=str(idx), image=self.gray_x_img, values=(
                    "🔍",
                    idx + 1,
                    row.get('INV_NO', ''),
                    row.get('RECEIVER', ''),
                    addr,
                    row.get('RECEIVER_ZIPCODE', '')
                ), tags=(tag,))

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

    def on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region in ["cell", "tree"]:
            column = self.tree.identify_column(event.x)
            item = self.tree.identify_row(event.y)
            if item:
                if column == "#0":  # Column #0 is the tree column (Delete)
                    self.tree.selection_set(item)
                    self.delete_selected()
                elif column == "#1":  # Column #1 is the View column
                    self.tree.selection_set(item)
                    self.open_pdf()

    def on_tree_motion(self, event):
        region = self.tree.identify_region(event.x, event.y)
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        
        current_hovered = getattr(self, '_hovered_item', None)
        
        if region in ["cell", "tree"] and item:
            if column == "#0":
                self.tree.configure(cursor="hand2")
                if current_hovered != item:
                    if current_hovered:
                        try:
                            self.tree.item(current_hovered, image=self.gray_x_img)
                        except:
                            pass
                    self.tree.item(item, image=self.red_x_img)
                    self._hovered_item = item
                self.show_tooltip("ลบรายการ", event.x_root + 15, event.y_root + 15)
                return
            elif column == "#1":
                self.tree.configure(cursor="hand2")
                if current_hovered:
                    try:
                        self.tree.item(current_hovered, image=self.gray_x_img)
                    except:
                        pass
                    self._hovered_item = None
                self.show_tooltip("ดูไฟล์ PDF", event.x_root + 15, event.y_root + 15)
                return
                
        # If not hovering target columns, reset
        self.tree.configure(cursor="")
        if current_hovered:
            try:
                self.tree.item(current_hovered, image=self.gray_x_img)
            except:
                pass
            self._hovered_item = None
        self.hide_tooltip()

    def on_tree_leave(self, event):
        self.tree.configure(cursor="")
        current_hovered = getattr(self, '_hovered_item', None)
        if current_hovered:
            try:
                self.tree.item(current_hovered, image=self.gray_x_img)
            except:
                pass
            self._hovered_item = None
        self.hide_tooltip()

    def show_tooltip(self, text, x, y):
        if self.tooltip_window:
            self.tooltip_window.geometry(f"+{x}+{y}")
            if hasattr(self, 'tooltip_label') and self.tooltip_label:
                self.tooltip_label.configure(text=text)
            return
            
        self.tooltip_window = tk.Toplevel(self)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.geometry(f"+{x}+{y}")
        
        # Style the tooltip
        self.tooltip_label = tk.Label(self.tooltip_window, text=text, justify='left',
                         background="#334155", foreground="#ffffff",
                         font=("Segoe UI", 9),
                         relief='flat', borderwidth=0, padx=6, pady=4)
        self.tooltip_label.pack(ipadx=1)

    def hide_tooltip(self):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
            self.tooltip_label = None

    def delete_selected(self, event=None):
        import tkinter.messagebox as messagebox
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("ข้อแนะนำ", "กรุณาคลิกเลือกรายการในตารางที่ต้องการลบก่อนครับ")
            return
            
        if not messagebox.askyesno("ยืนยันการลบ", "คุณต้องการลบข้อมูลที่เลือกใช่หรือไม่?\n\n(ระบบจะนำไฟล์ PDF ต้นฉบับของข้อมูลเหล่านี้ออกจากรายการด้วย)"):
            return
            
        try:
            indices_to_delete = [int(iid) for iid in selected_items]
            
            files_to_remove = set()
            if self.dataframe is not None and not self.dataframe.empty and 'SOURCE_FILE' in self.dataframe.columns:
                for idx in indices_to_delete:
                    if idx in self.dataframe.index:
                        files_to_remove.add(self.dataframe.loc[idx, 'SOURCE_FILE'])
                        
            if files_to_remove:
                # Remove from selected_files
                self.selected_files = [f for f in self.selected_files if f not in files_to_remove]
                
                # Remove ALL rows from dataframe that belong to these files
                self.dataframe = self.dataframe[~self.dataframe['SOURCE_FILE'].isin(files_to_remove)]
                
                # Reset index of dataframe so idx matches row numbers again
                self.dataframe.reset_index(drop=True, inplace=True)
                self.parsed_records = self.dataframe.to_dict('records') if not self.dataframe.empty else []
                
                # Update UI
                self.lbl_stat_files.configure(text=f"📄 ไฟล์ PDF: {len(self.selected_files)} ไฟล์")
                self.lbl_stat_records.configure(text=f"👥 รายการผู้รับ: {len(self.dataframe)} รายการ")
                
                if self.dataframe.empty:
                    self.clear_selection()
                else:
                    self.filter_treeview()
        except Exception as e:
            messagebox.showerror("เกิดข้อผิดพลาด", f"ไม่สามารถลบรายการได้เนื่องจาก:\n{str(e)}")

    def open_pdf(self, event=None):
        import tkinter.messagebox as messagebox
        selected_items = self.tree.selection()
        if not selected_items:
            return
            
        try:
            iid = selected_items[0]
            idx = int(iid)
            
            if self.dataframe is None or self.dataframe.empty:
                messagebox.showwarning("ข้อผิดพลาด", "ไม่พบข้อมูลในตาราง")
                return
                
            if 'SOURCE_FILE' not in self.dataframe.columns:
                messagebox.showwarning("ข้อแนะนำ", "กรุณากดปุ่ม 'ล้างข้อมูล' และเลือกไฟล์ PDF เข้ามาใหม่อีกครั้ง เพื่อให้ระบบจำไฟล์ต้นฉบับครับ")
                return
                
            file_path = self.dataframe.loc[idx, 'SOURCE_FILE']
            if not file_path:
                messagebox.showwarning("ข้อผิดพลาด", "ข้อมูลบรรทัดนี้ไม่มีไฟล์ต้นฉบับบันทึกไว้")
                return
                
            if os.path.exists(file_path):
                os.startfile(file_path)
            else:
                messagebox.showerror("ไม่พบไฟล์", f"ไม่พบไฟล์ต้นฉบับในระบบ:\n{file_path}")
        except Exception as e:
            messagebox.showerror("เกิดข้อผิดพลาด", f"ไม่สามารถเปิดไฟล์ได้เนื่องจาก:\n{str(e)}")

    def show_selected_files_popup(self, event=None):
        if not self.selected_files:
            return
            
        popup = ctk.CTkToplevel(self)
        popup.title(f"ไฟล์ที่เลือกทั้งหมด ({len(self.selected_files)} ไฟล์)")
        popup.geometry("600x400")
        popup.transient(self) # Keep on top of main window
        popup.grab_set()      # Make it modal
        
        # Center the popup
        popup.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 600) // 2
        y = self.winfo_y() + (self.winfo_height() - 400) // 2
        popup.geometry(f"+{x}+{y}")
        
        frame = ctk.CTkScrollableFrame(popup, fg_color="transparent")
        frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        for i, filepath in enumerate(self.selected_files):
            filename = os.path.basename(filepath)
            lbl = ctk.CTkLabel(frame, text=f"{i+1}. {filename}", font=("Segoe UI", 12), anchor="w")
            lbl.pack(fill='x', pady=2)

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
        
        self.progress.pack(fill='x', side='bottom', padx=2, pady=(0, 2))
        self.progress.set(0)
        self.lbl_status.configure(text="กำลังแปลงไฟล์... (0%)")
        self.lbl_status.pack(pady=(4, 0)) # adjust padding when progress bar is visible
        
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
                
            self.after(10, self.update_progress, (i + 1) / total, i + 1, total)
            
        self.after(10, self.conversion_completed, new_records)

    def update_progress(self, val, current, total):
        self.progress.set(val)
        percent = int(val * 100)
        self.lbl_status.configure(text=f"กำลังแปลงไฟล์... {current}/{total} ({percent}%)")

    def conversion_completed(self, new_records):
        self.progress.pack_forget()
        self.lbl_status.pack(pady=(8, 8)) # restore padding
        
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
                
                # Drop metadata columns before export
                cols_to_drop = [c for c in ['SOURCE_FILE', 'source_file'] if c in export_df.columns]
                if cols_to_drop:
                    export_df = export_df.drop(columns=cols_to_drop)
                    
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
