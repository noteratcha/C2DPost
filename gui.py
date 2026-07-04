import os
import sys
import glob
import threading
from datetime import datetime
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import customtkinter as ctk

try:
    from convert_dpost import process_pdf, records_to_dataframe, fetch_registered_barcodes, generate_combined_pdf, generate_delivery_note_pdf, __version__
except ImportError:
    __version__ = "2026.0704.2226"
    def process_pdf(path): return []
    def records_to_dataframe(recs): return pd.DataFrame()
    def fetch_registered_barcodes(num): return []

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
        self.after(0, lambda: self.state('zoomed'))
        self.configure(fg_color=COLOR_BG)
        
        self.selected_files = []
        self.parsed_records = []
        self.dataframe = None
        self.current_theme = "light"
        self.last_pdf_dir = None
        
        self.create_layout()
        self.style_treeview()
        
        self.bind("<Control-o>", lambda e: self.select_files())
        self.bind("<Control-O>", lambda e: self.select_files())
        self.bind("<Control-s>", lambda e: self.export_excel_shortcut())
        self.bind("<Control-S>", lambda e: self.export_excel_shortcut())
        self.bind("<Escape>", self.on_escape_press)
        
        # Check for updates after GUI loads
        self.after(1000, self.check_for_updates)
        
        # Initialize hover image state
        self.tools_normal_img = self.create_tools_image("#94a3b8", "#94a3b8")
        self.tools_hover_x_img = self.create_tools_image("#ef4444", "#94a3b8")
        self.tools_hover_view_img = self.create_tools_image("#94a3b8", "#3b82f6")
        self.tooltip_window = None

    def create_tools_image(self, x_color, view_color):
        img = tk.PhotoImage(width=100, height=16)
        
        # 1. Draw X at x=25 (centered around 25, offset 17)
        offset_x = 17
        for i in range(4, 12):
            img.put(x_color, (offset_x + i, i))
            img.put(x_color, (offset_x + 15 - i, i))
            img.put(x_color, (offset_x + i + 1, i))
            img.put(x_color, (offset_x + i, i + 1))
            img.put(x_color, (offset_x + 15 - i - 1, i))
            img.put(x_color, (offset_x + 15 - i, i + 1))
            
        # 2. Draw Magnifier at x=75 (centered around 75, offset 67)
        offset_view = 67
        # Draw thick lens (radius 4 and radius 3)
        points = [
            # Outer ring (radius 4)
            (offset_view + 6, 2), (offset_view + 5, 2), (offset_view + 7, 2),
            (offset_view + 6, 10), (offset_view + 5, 10), (offset_view + 7, 10),
            (offset_view + 2, 6), (offset_view + 2, 5), (offset_view + 2, 7),
            (offset_view + 10, 6), (offset_view + 10, 5), (offset_view + 10, 7),
            (offset_view + 3, 3), (offset_view + 3, 4), (offset_view + 4, 3),
            (offset_view + 9, 3), (offset_view + 9, 4), (offset_view + 8, 3),
            (offset_view + 3, 9), (offset_view + 3, 8), (offset_view + 4, 9),
            (offset_view + 9, 9), (offset_view + 9, 8), (offset_view + 8, 9),
            
            # Inner ring (radius 3) to make it thick
            (offset_view + 6, 3), (offset_view + 5, 3), (offset_view + 7, 3),
            (offset_view + 6, 9), (offset_view + 5, 9), (offset_view + 7, 9),
            (offset_view + 3, 6), (offset_view + 3, 5), (offset_view + 3, 7),
            (offset_view + 9, 6), (offset_view + 9, 5), (offset_view + 9, 7),
            (offset_view + 4, 4), (offset_view + 8, 4), (offset_view + 4, 8), (offset_view + 8, 8)
        ]
        for px, py in points:
            img.put(view_color, (px, py))
        # Handle (thick diagonal line)
        for i in range(5):
            img.put(view_color, (offset_view + 9 + i, 9 + i))
            img.put(view_color, (offset_view + 9 + i + 1, 9 + i))
            img.put(view_color, (offset_view + 9 + i, 9 + i + 1))
            img.put(view_color, (offset_view + 9 + i - 1, 9 + i + 1))
            
        return img

    def create_layout(self):
        # 1. Header Banner (Green)
        header = ctk.CTkFrame(self, fg_color=COLOR_PRIMARY, corner_radius=0, height=60)
        header.pack(fill='x', side='top')
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="สำนักงานที่ดิน", font=("Segoe UI", 18, "bold"), text_color="#ffffff").pack(side='left', padx=30)
        
        btn_info = ctk.CTkButton(header, text="ℹ", fg_color="#0f5128", hover_color="#0b3d1e",
                                 text_color="#ffffff", font=("Segoe UI", 12, "bold"),
                                 width=24, height=24, corner_radius=12,
                                 command=self.show_supported_docs)
        btn_info.pack(side='right', padx=(10, 30))
        
        def open_dpost_website():
            import webbrowser
            webbrowser.open("https://dpost.thailandpost.com")
            
        def open_ear_website():
            import webbrowser
            webbrowser.open("https://e-ar.thailandpost.com/")
            
        btn_ear = ctk.CTkButton(header, text="🔗    e-AR", fg_color="#0f5128", hover_color="#0b3d1e",
                                 text_color="#ffffff", font=("Segoe UI", 12, "bold"),
                                 height=28, corner_radius=14,
                                 command=open_ear_website)
        btn_ear.pack(side='right', padx=(10, 0))
        
        btn_ear.bind("<Enter>", lambda event: self.show_tooltip("เว็บสำหรับตรวจใบตอบรับทางอิเล็กทรอนิกส์", event.x_root + 10, event.y_root + 10))
        btn_ear.bind("<Leave>", lambda event: self.hide_tooltip())
            
        btn_dpost = ctk.CTkButton(header, text="🔗    DPost", fg_color="#0f5128", hover_color="#0b3d1e",
                                 text_color="#ffffff", font=("Segoe UI", 12, "bold"),
                                 height=28, corner_radius=14,
                                 command=open_dpost_website)
        btn_dpost.pack(side='right')
        
        btn_dpost.bind("<Enter>", lambda event: self.show_tooltip("เว็บสำหรับอัปโหลดข้อมูล", event.x_root + 10, event.y_root + 10))
        btn_dpost.bind("<Leave>", lambda event: self.hide_tooltip())
        
        # Bind hover tooltip to show 'เอกสารที่รองรับ'
        btn_info.bind("<Enter>", lambda event: self.show_tooltip("เอกสารที่รองรับ", event.x_root + 10, event.y_root + 10))
        btn_info.bind("<Leave>", lambda event: self.hide_tooltip())
        
        # Main Container
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill='both', expand=True, padx=20, pady=15)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)
        
        # Card 1: File Selection
        card_files = ctk.CTkFrame(container, fg_color=COLOR_CARD, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        card_files.grid(row=0, column=0, sticky='nsew', pady=(0, 15))
        
        ctk.CTkLabel(card_files, text="📄 ขั้นตอนที่ 1: เลือกเอกสาร PDF", font=("Segoe UI", 14, "bold"), text_color=COLOR_PRIMARY).pack(anchor='w', padx=20, pady=(15, 5))
        
        btn_frame = ctk.CTkFrame(card_files, fg_color="transparent")
        btn_frame.pack(fill='x', padx=20, pady=(5, 12))
        
        self.btn_select_files = ctk.CTkButton(btn_frame, text=" ➕ เพิ่มไฟล์ PDF ", fg_color=COLOR_PRIMARY, hover_color="#14532d",
                                                text_color="#ffffff",
                                                font=("Segoe UI", 12, "bold"), command=self.select_files, width=150, height=36)
        self.btn_select_files.pack(side='left', padx=(0, 10))
        
        # Removed btn_clear from here to place it in preview_header
        
        self.center_frame = ctk.CTkFrame(btn_frame, fg_color="transparent")
        self.center_frame.pack(side='left', fill='both', expand=True, padx=30)
        
        self.status_box = ctk.CTkFrame(self.center_frame, fg_color="#f5f5f5", border_width=1, border_color=COLOR_BORDER, corner_radius=6)
        self.status_box.pack(fill='both', expand=True)
        
        self.lbl_status = ctk.CTkLabel(self.status_box, text="ยังไม่ได้เลือกไฟล์", font=("Segoe UI", 12), text_color=COLOR_PRIMARY)
        self.lbl_status.pack(fill='both', expand=True, pady=(8, 8))
        
        self.btn_export = ctk.CTkButton(btn_frame, text=" 📥 บันทึกไฟล์ ", fg_color=COLOR_PRIMARY, hover_color="#14532d",
                                        text_color="#ffffff",
                                        font=("Segoe UI", 12, "bold"), command=self.export_excel, state='disabled', width=170, height=36)
        self.btn_export.pack(side='right')
        
        self.progress = ctk.CTkProgressBar(self.status_box, progress_color=COLOR_PRIMARY, height=8, corner_radius=4)
        
        # Card 2: Preview Table
        card_preview = ctk.CTkFrame(container, fg_color=COLOR_CARD, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        card_preview.grid(row=1, column=0, sticky='nsew')
        
        preview_header = ctk.CTkFrame(card_preview, fg_color="transparent")
        preview_header.pack(fill='x', padx=20, pady=(15, 10))
        
        ctk.CTkLabel(preview_header, text="📊 ขั้นตอนที่ 2: ตารางแสดงข้อมูล", font=("Segoe UI", 14, "bold"), text_color=COLOR_PRIMARY).pack(side='left')
        
        # Right aligned stats and search
        self.search_entry = ctk.CTkEntry(preview_header, placeholder_text=" 🔍 ค้นหาผู้รับ / เลขอ้างอิง... ", width=250, height=30, font=("Segoe UI", 11), corner_radius=15)
        self.search_entry.pack(side='right', padx=(15, 0))
        
        self.btn_clear = ctk.CTkButton(preview_header, text=" 🧹 ล้างข้อมูล ", fg_color="#f1f5f9", 
                                       hover_color="#fecaca", text_color="#ef4444",
                                       font=("Segoe UI", 11, "bold"), command=self.clear_selection, width=95, height=30, corner_radius=15)
        self.btn_clear.pack(side='right', padx=(10, 0))
        
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
        
        # Physical separator line between function columns and data columns
        self.divider = tk.Frame(self.tree, width=1, bg="#cbd5e1")
        self.divider.place(relheight=1.0, x=100)
        
        self.columns = [
            ("No", "ลำดับ", 50),
            ("Barcode", "หมายเลข", 130),
            ("Ref", "เลขที่อ้างอิง", 120),
            ("Receiver", "ผู้รับ", 180),
            ("Address", "ที่อยู่ผู้รับ (ที่อยู่ / อำเภอ / จังหวัด)", 420),
            ("Zip", "รหัสไปรษณีย์", 100)
        ]
        
        self.tree["columns"] = [col[0] for col in self.columns]
        self.tree["show"] = "tree headings"
        
        # Configure tree column (#0) for unified Tools action (Delete + View)
        self.tree.heading("#0", text="เครื่องมือ", anchor='center')
        self.tree.column("#0", width=100, minwidth=100, stretch=False, anchor='center')
        
        for col_id, col_name, col_width in self.columns:
            h_anchor = 'center'
            self.tree.heading(col_id, text=col_name, anchor=h_anchor, command=lambda _col=col_id: self.sort_treeview(_col, False))
            stretch = True
            col_anchor = 'w' if col_id in ["Receiver", "Address"] else 'center'
            self.tree.column(col_id, width=col_width, minwidth=col_width, stretch=stretch, anchor=col_anchor)
            

    def style_treeview(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        bg = "#ffffff"
        fg = "#334155"
        headings_bg = "#e2e8f0"
        selected_bg = "#dcfce7"  # Light green for selection
            
        style.configure('Treeview', background=bg, foreground=fg, rowheight=35, 
                        fieldbackground=bg, borderwidth=0, font=('Segoe UI', 10))
        style.map('Treeview', background=[('selected', selected_bg)], foreground=[('selected', '#1e293b')])
        
        style.configure('Treeview.Heading', background=headings_bg, foreground="#0f172a", 
                        font=('Segoe UI', 10, 'bold'), borderwidth=0, relief="flat", padding=(5, 8))
        style.map('Treeview.Heading', background=[('active', '#cbd5e1')])
        
        # Hide the tree indicator (disclosure arrow) in column #0
        style.layout('Treeview.Item', [
            ('Treeitem.padding', {'side': 'left', 'sticky': 'ns', 'children': [
                ('Treeitem.image', {'side': 'left', 'sticky': ''}),
                ('Treeitem.focus', {'side': 'left', 'sticky': 'ns', 'children': [
                    ('Treeitem.text', {'side': 'left', 'sticky': ''})
                ]})
            ]})
        ])

        self.tree.tag_configure('oddrow', background="#ffffff")
        self.tree.tag_configure('evenrow', background="#f8fafc")
        self.tree.tag_configure('hover', foreground="#ea580c")
        


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
                self.tree.insert("", "end", iid=str(idx), image=self.tools_normal_img, values=(
                    idx + 1,
                    row.get('BARCODE_NO', ''),
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
                if column == "#0":  # Column #0 is the unified Tools column
                    # Check if this row already has a barcode
                    try:
                        idx = int(item)
                        if self.dataframe is not None and not pd.isna(self.dataframe.loc[idx].get('BARCODE_NO')) and str(self.dataframe.loc[idx].get('BARCODE_NO')).strip():
                            import tkinter.messagebox as messagebox
                            messagebox.showinfo("ข้อมูลถูกยืนยันแล้ว", "รายการนี้ถูกออกเลขลงทะเบียนแล้ว ไม่สามารถใช้งานเครื่องมือได้ครับ")
                            return
                    except:
                        pass
                        
                    if 15 <= event.x <= 35:
                        self.tree.selection_set(item)
                        self.delete_selected()
                    elif 65 <= event.x <= 85:
                        self.tree.selection_set(item)
                        self.open_pdf()

    def on_tree_motion(self, event):
        region = self.tree.identify_region(event.x, event.y)
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        
        current_hovered = getattr(self, '_hovered_item', None)
        
        # 1. Row Hover Text Highlight (for all columns when hovering a row)
        for row in self.tree.get_children():
            tags = list(self.tree.item(row, 'tags'))
            clean_tags = [t for t in tags if t not in ['oddrow', 'evenrow', 'hover']]
            idx = self.tree.index(row)
            alt_tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            clean_tags.append(alt_tag)
            
            if row == item:
                clean_tags.append('hover')
            self.tree.item(row, tags=clean_tags)

        # 2. Icon Hover (Delete or View)
        if region in ["cell", "tree"] and item and column == "#0":
            has_barcode = False
            try:
                idx = int(item)
                if self.dataframe is not None and not pd.isna(self.dataframe.loc[idx].get('BARCODE_NO')) and str(self.dataframe.loc[idx].get('BARCODE_NO')).strip():
                    has_barcode = True
            except:
                pass
                
            if not has_barcode:
                # Delete Icon (15-35)
                if 15 <= event.x <= 35:
                    self.tree.configure(cursor="hand2")
                    if current_hovered != (item, 'delete'):
                        if current_hovered:
                            try:
                                self.tree.item(current_hovered[0], image=self.tools_normal_img)
                            except:
                                pass
                        self.tree.item(item, image=self.tools_hover_x_img)
                        self._hovered_item = (item, 'delete')
                    self.show_tooltip("ลบรายการ", event.x_root + 15, event.y_root + 15)
                    return
                # View Icon (65-85)
                elif 65 <= event.x <= 85:
                    self.tree.configure(cursor="hand2")
                    if current_hovered != (item, 'view'):
                        if current_hovered:
                            try:
                                self.tree.item(current_hovered[0], image=self.tools_normal_img)
                            except:
                                pass
                        self.tree.item(item, image=self.tools_hover_view_img)
                        self._hovered_item = (item, 'view')
                    self.show_tooltip("ดูไฟล์ PDF", event.x_root + 15, event.y_root + 15)
                    return
                
        # If not hovering target icons, reset cursor/images but keep row hover
        self.tree.configure(cursor="")
        if current_hovered:
            try:
                self.tree.item(current_hovered[0], image=self.tools_normal_img)
            except:
                pass
            self._hovered_item = None
        self.hide_tooltip()

    def on_tree_leave(self, event):
        self.tree.configure(cursor="")
        current_hovered = getattr(self, '_hovered_item', None)
        if current_hovered:
            try:
                self.tree.item(current_hovered[0], image=self.tools_normal_img)
            except:
                pass
            self._hovered_item = None
        self.hide_tooltip()
        
        # Clear row hover tag when leaving the tree
        for row in self.tree.get_children():
            tags = list(self.tree.item(row, 'tags'))
            if 'hover' in tags:
                tags.remove('hover')
                self.tree.item(row, tags=tags)

    def show_tooltip(self, text, x, y):
        if self.tooltip_window:
            if hasattr(self, 'tooltip_label') and self.tooltip_label:
                self.tooltip_label.configure(text=text)
            self.position_tooltip(x, y)
            return
            
        self.tooltip_window = tk.Toplevel(self)
        self.tooltip_window.wm_overrideredirect(True)
        
        # Style the tooltip
        self.tooltip_label = tk.Label(self.tooltip_window, text=text, justify='left',
                         background="#334155", foreground="#ffffff",
                         font=("Segoe UI", 9),
                         relief='flat', borderwidth=0, padx=6, pady=4)
        self.tooltip_label.pack(ipadx=1)
        self.position_tooltip(x, y)

    def position_tooltip(self, x, y):
        self.tooltip_window.update_idletasks()
        width = self.tooltip_window.winfo_width()
        screen_width = self.winfo_screenwidth()
        
        # If the tooltip extends beyond the right edge of the screen
        if x + width > screen_width:
            x = x - width - 25  # Shift to the left of the cursor
            
        self.tooltip_window.geometry(f"+{x}+{y}")

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
        if self.selected_files or (self.dataframe is not None and not self.dataframe.empty):
            if not messagebox.askyesno("ยืนยันการล้างข้อมูล", "คุณต้องการล้างข้อมูลผู้รับและไฟล์ PDF ทั้งหมดที่เลือกไว้ใช่หรือไม่?"):
                return
                
        self.selected_files = []
        self.parsed_records = []
        self.dataframe = None
        self.lbl_status.configure(text="ยังไม่ได้เลือกไฟล์")
        self.lbl_stat_files.configure(text="📄 ไฟล์ PDF: 0 ไฟล์")
        self.lbl_stat_records.configure(text="👥 รายการผู้รับ: 0 รายการ")
        
        self.btn_export.configure(state='disabled')
        self.btn_select_files.configure(text=" ➕ เพิ่มไฟล์ PDF ", state='normal')
        
        for item in self.tree.get_children():
            self.tree.delete(item)

    def select_files(self):
        files = filedialog.askopenfilenames(
            title="เลือกไฟล์ PDF ใบนำส่ง DPost",
            initialdir=self.last_pdf_dir,
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
        )
        if files:
            # Update last_pdf_dir for next time
            self.last_pdf_dir = os.path.dirname(files[0])
            
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
        
        thread = threading.Thread(target=self.run_conversion_task, args=(files_to_process,))
        thread.daemon = True
        thread.start()

    def run_conversion_task(self, files_to_process):
        new_records = []
        failed_files = []
        errors = []
        total = len(files_to_process)
        
        for i, filepath in enumerate(files_to_process):
            filename = os.path.basename(filepath)
            try:
                records = process_pdf(filepath)
                if records:
                    for r in records:
                        r['source_file'] = filepath
                    new_records.extend(records)
                else:
                    failed_files.append(filename)
            except Exception as e:
                errors.append(f"ไฟล์ {filename}: {str(e)}")
                failed_files.append(filename)
                
            self.after(10, self.update_progress, (i + 1) / total, i + 1, total)
            
        new_df = None
        if new_records:
            self.after(10, lambda: self.lbl_status.configure(text=f"กำลังสร้างตารางข้อมูล..."))
            try:
                new_df = records_to_dataframe(new_records)
            except Exception as e:
                errors.append(f"การสร้างตารางข้อมูล: {str(e)}")
            
        self.after(10, self.conversion_completed, new_records, failed_files, new_df, errors)

    def update_progress(self, val, current, total):
        self.progress.set(val)
        percent = int(val * 100)
        self.lbl_status.configure(text=f"กำลังแปลงไฟล์... {current}/{total} ({percent}%)")

    def conversion_completed(self, new_records, failed_files, new_df=None, errors=None):
        self.progress.pack_forget()
        self.lbl_status.pack(pady=(8, 8)) # restore padding
        
        if errors:
            error_list = "\n".join(f"- {err}" for err in errors[:10])
            if len(errors) > 10:
                error_list += f"\n... และอีก {len(errors) - 10} ปัญหา"
            messagebox.showerror("พบปัญหาในการทำงาน", f"เกิดข้อผิดพลาดดังนี้:\n\n{error_list}")
            
        # Remove failed files from self.selected_files
        if failed_files:
            self.selected_files = [f for f in self.selected_files if os.path.basename(f) not in failed_files]
            
            # Show warning to user about incorrect files
            failed_list = "\n".join(f"- {name}" for name in failed_files)
            messagebox.showwarning(
                "พบไฟล์ไม่ถูกต้อง",
                f"ไฟล์ต่อไปนี้ไม่ใช่รูปแบบใบนำส่ง DPost หรือไม่มีข้อมูลผู้รับ:\n\n{failed_list}\n\n(ระบบได้นำออกจากการเลือกแล้ว)"
            )
            
        if new_records and new_df is not None:
            # new_df = records_to_dataframe(new_records)
            
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
        else:
            self.lbl_stat_files.configure(text=f"📄 ไฟล์ PDF: {len(self.selected_files)} ไฟล์")
            self.lbl_stat_records.configure(text=f"👥 รายการผู้รับ: {len(self.dataframe) if self.dataframe is not None else 0} รายการ")
            
            if not self.parsed_records:
                self.lbl_status.configure(text="ไม่พบข้อมูลในไฟล์ที่เลือก")
            else:
                self.lbl_status.configure(text=f"ประมวลผลเสร็จสิ้น รวมทั้งหมด {len(self.dataframe)} รายการ")
        
        self.btn_select_files.configure(state='normal')
        self.btn_clear.configure(state='normal')
        if self.dataframe is not None and not self.dataframe.empty:
            self.btn_export.configure(state='normal')

    def show_supported_docs(self):
        messagebox.showinfo(
            "เอกสารที่รองรับ",
            "ระบบปัจจุบันรองรับการแปลงไฟล์ประเภท:\n\n"
            "• ท.ด. 38"
        )

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
                # Fetch barcodes right before exporting
                num_records = len(self.dataframe)
                self.lbl_status.configure(text=f"กำลังดึงบาร์โค้ดลงทะเบียนจำนวน {num_records} หมายเลข...")
                self.update() # Force UI update
                
                barcodes = fetch_registered_barcodes(num_records)
                if len(barcodes) < num_records:
                    messagebox.showwarning("คำเตือน", "ดึงบาร์โค้ดได้ไม่ครบตามจำนวนข้อมูล")
                
                # นับแยกประเภทบาร์โค้ด (EMS=E,J, R=R,B, eCo=O)
                ems_count = sum(1 for b in barcodes if str(b).upper().startswith(('E', 'J')))
                r_count = sum(1 for b in barcodes if str(b).upper().startswith(('R', 'B')))
                eco_count = sum(1 for b in barcodes if str(b).upper().startswith('O'))
                
                # ส่งข้อมูลไปบันทึกบน Google Sheet
                def log_barcodes(ems, r, eco):
                    try:
                        import urllib.parse
                        import urllib.request
                        url = "https://script.google.com/macros/s/AKfycbyElrFXMUEN4pqhpNWD7lxQ_z1l1pCIOny1Ipk9yOEwuWTnASplduekZxzZWFRGSdHh/exec"
                        params = urllib.parse.urlencode({'action': 'log_barcode', 'ems': ems, 'r': r, 'eco': eco})
                        full_url = f"{url}?{params}"
                        req = urllib.request.Request(full_url, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req, timeout=5):
                            pass
                    except Exception as e:
                        print(f"Barcode tracking failed: {e}")
                
                if len(barcodes) > 0:
                    threading.Thread(target=log_barcodes, args=(ems_count, r_count, eco_count), daemon=True).start()
                
                # Assign barcodes to dataframe
                for i in range(num_records):
                    if i < len(barcodes):
                        self.dataframe.at[i, 'BARCODE_NO'] = barcodes[i]
                    else:
                        self.dataframe.at[i, 'BARCODE_NO'] = ""
                        
                # Update the UI table to show the fetched barcodes
                self.filter_treeview()
                self.update()
                
                # Disable Add PDF button so user must clear data to start over
                self.btn_select_files.configure(state='disabled')

                export_df = self.dataframe.copy()
                
                # Drop metadata columns before export
                cols_to_drop = [c for c in ['SOURCE_FILE', 'source_file'] if c in export_df.columns]
                if cols_to_drop:
                    export_df = export_df.drop(columns=cols_to_drop)
                    
                export_df.to_excel(filepath, index=False, engine='openpyxl', sheet_name='New Order Data')
                
                # Generate combined PDF
                pdf_filepath = filepath.rsplit('.', 1)[0] + '.pdf'
                delivery_note_filepath = filepath.rsplit('.', 1)[0] + '_ใบนำส่ง.pdf'
                self.lbl_status.configure(text="กำลังสร้างไฟล์ PDF สรุปรวมและใบนำส่ง...")
                self.update()
                
                try:
                    generate_combined_pdf(self.dataframe, pdf_filepath)
                    generate_delivery_note_pdf(self.dataframe, delivery_note_filepath)
                    self.show_success_dialog(filepath, pdf_filepath, delivery_note_filepath)
                    self.lbl_status.configure(text="บันทึกไฟล์ Excel, PDF รวม และ ใบนำส่ง สำเร็จ")
                except Exception as pdf_e:
                    messagebox.showerror("ข้อผิดพลาด PDF", f"สร้าง Excel สำเร็จ แต่ไม่สามารถสร้าง PDF ได้:\n{str(pdf_e)}")
                    self.show_success_dialog(filepath, "", "")
                    self.lbl_status.configure(text="บันทึกไฟล์ Excel สำเร็จ แต่สร้าง PDF ล้มเหลว")
                
                if sys.platform == "win32":
                    os.startfile(filepath)
                    if os.path.exists(pdf_filepath):
                        os.startfile(pdf_filepath)
                    if os.path.exists(delivery_note_filepath):
                        os.startfile(delivery_note_filepath)
            except Exception as e:
                messagebox.showerror("ข้อผิดพลาด", f"ไม่สามารถบันทึกไฟล์ได้:\n{str(e)}")

    def show_success_dialog(self, excel_path, pdf_path, delivery_path):
        dialog = ctk.CTkToplevel(self)
        dialog.title("บันทึกไฟล์สำเร็จ")
        dialog.geometry("450x300")
        dialog.transient(self)
        dialog.grab_set()
        
        # Center the dialog
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 450) // 2
        y = self.winfo_y() + (self.winfo_height() - 300) // 2
        dialog.geometry(f"+{x}+{y}")
        
        main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        icon_lbl = ctk.CTkLabel(main_frame, text="✅", font=("Segoe UI", 48), text_color=COLOR_SUCCESS)
        icon_lbl.pack(pady=(0, 10))
        
        title_lbl = ctk.CTkLabel(main_frame, text="บันทึกไฟล์สำเร็จเรียบร้อยแล้ว!", font=("Segoe UI", 16, "bold"), text_color=COLOR_TEXT_MAIN)
        title_lbl.pack(pady=(0, 15))
        
        paths_frame = ctk.CTkFrame(main_frame, fg_color="#f8fafc", corner_radius=8, border_width=1, border_color="#e2e8f0")
        paths_frame.pack(fill="x", expand=True)
        
        import os
        files_text = f"📊 {os.path.basename(excel_path)}"
        if pdf_path:
            files_text += f"\n📑 {os.path.basename(pdf_path)}"
        if delivery_path:
            files_text += f"\n📑 {os.path.basename(delivery_path)}"
            
        files_lbl = ctk.CTkLabel(paths_frame, text=files_text, font=("Segoe UI", 12), text_color=COLOR_TEXT_MUTED, justify="left")
        files_lbl.pack(padx=15, pady=15, anchor="w")
        
        btn_close = ctk.CTkButton(main_frame, text="ตกลง", command=dialog.destroy, font=("Segoe UI", 12, "bold"), fg_color=COLOR_PRIMARY, hover_color="#14532d", width=120)
        btn_close.pack(pady=(15, 0))

    def check_for_updates(self):
        def fetch_version():
            import urllib.request
            import csv
            import io
            url = 'https://docs.google.com/spreadsheets/d/1jFaKQepC60TZBIsFoDeGYPeOHw_eeMpbgEjF5ZdPYk4/export?format=csv&gid=0'
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    content = response.read().decode('utf-8')
                    reader = csv.reader(io.StringIO(content))
                    for row in reader:
                        if len(row) >= 2:
                            latest_version = row[0].strip()
                            download_url = row[1].strip()
                            
                            # Normalize versions for comparison
                            current_v = f"v{__version__}" if not __version__.startswith('v') else __version__
                            latest_v = f"v{latest_version}" if not latest_version.startswith('v') else latest_version
                            
                            if current_v != latest_v:
                                self.after(0, lambda: self.show_update_dialog(latest_v, download_url))
                        break
            except Exception as e:
                print(f"Update check failed: {e}")
                
            # 2. Track Usage Count
            # นำ Web App URL ที่ได้จาก Google Apps Script มาแทนที่ข้อความด้านล่างนี้
            usage_tracking_url = "https://script.google.com/macros/s/AKfycbyElrFXMUEN4pqhpNWD7lxQ_z1l1pCIOny1Ipk9yOEwuWTnASplduekZxzZWFRGSdHh/exec"
            if usage_tracking_url and "YOUR_WEB_APP" not in usage_tracking_url:
                try:
                    track_req = urllib.request.Request(usage_tracking_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(track_req, timeout=5) as track_res:
                        pass # Trigger success
                except Exception as e:
                    print(f"Usage tracking failed: {e}")
                
        threading.Thread(target=fetch_version, daemon=True).start()

    def show_update_dialog(self, latest_version, download_url):
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_OK)
        except Exception:
            pass
            
        dialog = ctk.CTkToplevel(self)
        dialog.title("แจ้งเตือนการอัปเดต")
        dialog.geometry("450x250")
        dialog.transient(self)
        dialog.grab_set()
        
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 450) // 2
        y = self.winfo_y() + (self.winfo_height() - 250) // 2
        dialog.geometry(f"+{x}+{y}")
        
        main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        icon_lbl = ctk.CTkLabel(main_frame, text="🔔", font=("Segoe UI", 48))
        icon_lbl.pack(pady=(0, 10))
        
        title_lbl = ctk.CTkLabel(main_frame, text=f"มีโปรแกรมเวอร์ชันใหม่: {latest_version}", font=("Segoe UI", 16, "bold"), text_color=COLOR_PRIMARY)
        title_lbl.pack(pady=(0, 10))
        
        msg_lbl = ctk.CTkLabel(main_frame, text="กรุณาดาวน์โหลดเวอร์ชันล่าสุดเพื่อให้ทำงานได้อย่างสมบูรณ์", font=("Segoe UI", 12))
        msg_lbl.pack(pady=(0, 20))
        
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack()
        
        def on_download():
            import webbrowser
            webbrowser.open(download_url)
            dialog.destroy()
            
        btn_download = ctk.CTkButton(btn_frame, text="📥 ดาวน์โหลด", command=on_download, fg_color=COLOR_PRIMARY, hover_color="#14532d", font=("Segoe UI", 12, "bold"))
        btn_download.pack(side="left", padx=10)
        
        btn_cancel = ctk.CTkButton(btn_frame, text="ไว้ทีหลัง", command=dialog.destroy, fg_color="#ef4444", hover_color="#b91c1c", font=("Segoe UI", 12, "bold"))
        btn_cancel.pack(side="left", padx=10)

def main():
    app = DPostConverterGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
