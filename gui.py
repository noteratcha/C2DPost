import os
import sys
import glob
import threading
from datetime import datetime
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import customtkinter as ctk
import requests
import io
from PIL import Image, ImageTk

try:
    from convert_dpost import process_pdf, records_to_dataframe, fetch_registered_barcodes, generate_combined_pdf, generate_delivery_note_pdf, __version__
except Exception as e:
    import traceback
    traceback.print_exc()
    messagebox.showerror("Critical Error", f"Failed to load convert_dpost:\n{str(e)}")
    sys.exit(1)
ctk.set_appearance_mode("light")

# Modern Premium Colors (Emerald & Slate theme)
COLOR_PRIMARY = "#059669"      # Emerald 600 (Header, primary buttons)
COLOR_PRIMARY_HOVER = "#047857" # Emerald 700
COLOR_SUCCESS = "#10b981"      # Emerald 500
COLOR_SUCCESS_HOVER = "#059669"
COLOR_BG = "#e2e8f0"           # Slate 200 (App background darker)
COLOR_CARD = "#ffffff"         # White for cards
COLOR_BORDER = "#cbd5e1"       # Slate 300 (Borders darker)
COLOR_TEXT_MAIN = "#0f172a"    # Slate 900 (Main text)
COLOR_TEXT_MUTED = "#475569"   # Slate 600 (Subtitles/Hints)
COLOR_DANGER = "#ef4444"       # Red 500
COLOR_DANGER_HOVER = "#dc2626" # Red 600

def make_entry_context_menu(widget):
    menu = tk.Menu(widget, tearoff=0)
    menu.add_command(label="Copy", command=lambda: widget.event_generate("<<Copy>>"))
    menu.add_command(label="Paste", command=lambda: widget.event_generate("<<Paste>>"))
    menu.add_command(label="Cut", command=lambda: widget.event_generate("<<Cut>>"))
    
    def show_menu(event):
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
            
    widget.bind("<Button-3>", show_menu)
    
    # Robust Ctrl+V paste handler for all keyboard layouts
    def handle_ctrl_key(event):
        # 86 is the hardware keycode for 'V' on Windows
        if getattr(event, 'keycode', None) == 86 or getattr(event, 'char', '').lower() in ('v', 'อ', 'ฮ'):
            try:
                text = widget.clipboard_get()
                try:
                    widget.delete("sel.first", "sel.last")
                except tk.TclError:
                    pass
                widget.insert(tk.INSERT, text)
            except tk.TclError:
                pass
            return "break"
            
    widget.bind("<Control-Key>", handle_ctrl_key, add="+")

class LoginWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("เข้าสู่ระบบ C2DPost")
        self.geometry("500x450")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG)
        
        # Center the window
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.winfo_screenheight() // 2) - (450 // 2)
        self.geometry(f"+{x}+{y}")
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.transient(master)
        self.grab_set()

        # White Card Layout
        self.card = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=15, border_width=1, border_color=COLOR_BORDER)
        self.card.pack(expand=True, padx=40, pady=40, fill="both")

        self.lbl_title = ctk.CTkLabel(self.card, text="C2DPost Login", font=("Segoe UI", 28, "bold"), text_color=COLOR_PRIMARY)
        self.lbl_title.pack(pady=(35, 25))

        self.entry_username = ctk.CTkEntry(self.card, placeholder_text="Username", width=280, height=45, font=("Segoe UI", 14), corner_radius=8, border_color=COLOR_BORDER)
        self.entry_username.pack(pady=(0, 15))
        make_entry_context_menu(self.entry_username._entry)

        self.entry_password = ctk.CTkEntry(self.card, placeholder_text="Password", show="*", width=280, height=45, font=("Segoe UI", 14), corner_radius=8, border_color=COLOR_BORDER)
        self.entry_password.pack(pady=(0, 10))
        self.entry_password.bind("<Return>", lambda e: self.login())
        make_entry_context_menu(self.entry_password._entry)

        self.lbl_error = ctk.CTkLabel(self.card, text="", text_color=COLOR_DANGER, font=("Segoe UI", 12))
        self.lbl_error.pack(pady=(0, 10))

        self.btn_login = ctk.CTkButton(self.card, text="เข้าสู่ระบบ", fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER, 
                                       text_color="#ffffff", font=("Segoe UI", 16, "bold"), 
                                       width=280, height=45, command=self.login, corner_radius=8)
        self.btn_login.pack(pady=(5, 30))

    def on_close(self):
        self.master.destroy()

    def login(self):
        username = self.entry_username.get().strip()
        password = self.entry_password.get().strip()

        if not username or not password:
            self.lbl_error.configure(text="กรุณากรอก Username และ Password")
            return

        self.btn_login.configure(state="disabled", text="กำลังตรวจสอบ...")
        self.lbl_error.configure(text="")
        
        # Run in thread to not block UI
        threading.Thread(target=self.verify_login, args=(username, password), daemon=True).start()

    def verify_login(self, username, password):
        sheet_url = "https://docs.google.com/spreadsheets/d/1hiWww6BI7NCTAw3Ai3CjbzS8TWdIX2AAOj7P_2BxMcQ/export?format=csv&gid=0"
        try:
            response = requests.get(sheet_url, timeout=10)
            response.encoding = 'utf-8'
            response.raise_for_status()
            
            # Read CSV
            df = pd.read_csv(io.StringIO(response.text))
            
            # Filter rows
            df['UserName'] = df['UserName'].astype(str).str.strip()
            df['Password'] = df['Password'].astype(str).str.strip()
            
            user_row = df[(df['UserName'] == username) & (df['Password'] == password)]
            
            if not user_row.empty:
                # Login successful
                row_data = user_row.iloc[0].to_dict()
                status = str(row_data.get('Status', '')).strip().upper()
                
                if status == "DOL":
                    self.after(0, self.login_success, row_data)
                elif status == "ADMIN":
                    self.after(0, self.admin_login_success, row_data)
                else:
                    self.after(0, self.login_fail, "คุณไม่มีสิทธิ์เข้าถึงระบบ (Status ไม่ใช่ DOL หรือ ADMIN)")
            else:
                self.after(0, self.login_fail, "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
                
        except requests.exceptions.RequestException:
            self.after(0, self.login_fail, "ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้")
        except Exception as e:
            self.after(0, self.login_fail, f"เกิดข้อผิดพลาด: {str(e)}")

    def login_success(self, user_data):
        self.master.on_login_success(user_data)
        self.destroy()

    def admin_login_success(self, user_data):
        self.master.on_admin_login_success(user_data)
        self.destroy()

    def login_fail(self, message):
        self.btn_login.configure(state="normal", text="Login")
        self.lbl_error.configure(text=message)
        username = self.entry_username.get() if hasattr(self, 'entry_username') else "Unknown"
        if username and hasattr(self, 'master') and hasattr(self.master, 'record_user_log'):
            self.master.record_user_log(username, "Login - ไม่สำเร็จ")


class AdminManagementWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("ระบบจัดการผู้ใช้งาน (Management)")
        self.geometry("1400x800")
        self.after(0, lambda: self.state('zoomed'))
        self.configure(fg_color=COLOR_BG)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.create_layout()
        self.load_data()
        
    def on_close(self):
        self.master.destroy()

    def logout(self):
        if self.master.user_data:
            self.master.record_user_log(self.master.user_data.get("UserName", "Admin"), "Logout - สำเร็จ")
        self.destroy()
        self.master.user_data = None
        self.master.show_login_window()

    def create_layout(self):
        # Title
        header = ctk.CTkFrame(self, fg_color=COLOR_PRIMARY, corner_radius=0, height=60)
        header.pack(fill='x', side='top')
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="ระบบจัดการผู้ใช้งาน (Management)", font=("Segoe UI", 18, "bold"), text_color="#ffffff").pack(side='left', padx=30)
        
        btn_logout = ctk.CTkButton(header, text="ออกจากระบบ", fg_color="#dc2626", hover_color="#991b1b",
                                 text_color="#ffffff", font=("Segoe UI", 12, "bold"),
                                 height=28, width=120, corner_radius=14,
                                 command=self.logout)
        btn_logout.pack(side='right', padx=30)
        
        # Main container
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill='both', expand=True, padx=20, pady=15)
        
        # Left Panel: Data Entry Form
        form_frame = ctk.CTkScrollableFrame(container, width=400, fg_color=COLOR_CARD, corner_radius=12, border_width=1, border_color=COLOR_BORDER)
        form_frame.pack(side='left', fill='y', padx=(0, 15))
        
        ctk.CTkLabel(form_frame, text="ข้อมูลผู้ใช้งาน", font=("Segoe UI", 18, "bold"), text_color=COLOR_PRIMARY).pack(pady=(15, 20))
        
        self.entries = {}
        fields = [
            ("UserName", True), ("Password", True), ("Email", True), ("Prefix", True), 
            ("Organization", True), ("ResponsiblePostoffice", True), ("ResponsibleZipcode", True), 
            ("ActivationDate", True), ("ContactPerson1", True), ("TelContactPerson1", True),
            ("ContactPerson2", False), ("TelContactPerson2", False), 
            ("ContactPerson3", False), ("TelContactPerson3", False)
        ]
        
        for field, req in fields:
            lbl_text = f"{field} *" if req else field
            ctk.CTkLabel(form_frame, text=lbl_text, font=("Segoe UI", 12), text_color=COLOR_TEXT_MAIN).pack(anchor='w', padx=10)
            entry = ctk.CTkEntry(form_frame, width=350, height=35, corner_radius=8, border_color=COLOR_BORDER)
            entry.pack(padx=10, pady=(0, 10))
            make_entry_context_menu(entry._entry)
            self.entries[field] = entry
            
        # Status Dropdown
        ctk.CTkLabel(form_frame, text="Status *", font=("Segoe UI", 12), text_color=COLOR_TEXT_MAIN).pack(anchor='w', padx=10)
        self.combo_status = ctk.CTkComboBox(form_frame, values=["DOL", "ADMIN", "INACTIVE"], width=350, height=35, corner_radius=8, border_color=COLOR_BORDER)
        self.combo_status.set("DOL")
        self.combo_status.pack(padx=10, pady=(0, 20))
        
        # Buttons
        btn_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        btn_frame.pack(fill='x', padx=10, pady=15)
        
        self.btn_save = ctk.CTkButton(btn_frame, text="บันทึก", fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS_HOVER, corner_radius=8, height=38, font=("Segoe UI", 14, "bold"), command=self.save_data)
        self.btn_save.pack(side='left', expand=True, padx=5)
        
        self.btn_clear = ctk.CTkButton(btn_frame, text="ล้าง", fg_color=COLOR_TEXT_MUTED, hover_color="#334155", corner_radius=8, height=38, font=("Segoe UI", 14, "bold"), command=self.clear_form)
        self.btn_clear.pack(side='left', expand=True, padx=5)
        
        # Right Panel: Treeview
        tree_container = ctk.CTkFrame(container, fg_color=COLOR_CARD, corner_radius=12, border_width=1, border_color=COLOR_BORDER)
        tree_container.pack(side='right', fill='both', expand=True)
        
        tree_header = ctk.CTkFrame(tree_container, fg_color="transparent")
        tree_header.pack(fill='x', padx=20, pady=15)
        ctk.CTkLabel(tree_header, text="รายชื่อผู้ใช้ในระบบ", font=("Segoe UI", 18, "bold"), text_color=COLOR_TEXT_MAIN).pack(side='left')
        
        self.btn_refresh = ctk.CTkButton(tree_header, text="รีเฟรชข้อมูล", width=120, height=35, corner_radius=8, fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER, font=("Segoe UI", 12, "bold"), command=self.load_data)
        self.btn_refresh.pack(side='right')
        
        # Setup Treeview
        table_frame = tk.Frame(tree_container, bg=COLOR_CARD)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        vsb = ctk.CTkScrollbar(table_frame, orientation="vertical")
        hsb = ctk.CTkScrollbar(table_frame, orientation="horizontal")
        
        self.tree = ttk.Treeview(table_frame, selectmode="browse", yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.configure(command=self.tree.yview)
        hsb.configure(command=self.tree.xview)
        
        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')
        self.tree.pack(side='left', fill='both', expand=True)
        
        # Columns based on sheet
        self.tree_cols = [f[0] for f in fields] + ["Status"]
        self.tree["columns"] = self.tree_cols
        self.tree["show"] = "headings"
        
        for col in self.tree_cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, minwidth=100)
            
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        
    def clear_form(self):
        for entry in self.entries.values():
            entry.delete(0, 'end')
        self.combo_status.set("DOL")
        
    def on_tree_select(self, event):
        selected = self.tree.selection()
        if not selected: return
        item = self.tree.item(selected[0])
        values = item['values']
        
        self.clear_form()
        for i, col in enumerate(self.tree_cols):
            val = str(values[i]) if values[i] is not None and str(values[i]) != "nan" else ""
            if col == "Status":
                self.combo_status.set(val)
            else:
                self.entries[col].insert(0, val)

    def load_data(self):
        sheet_url = "https://docs.google.com/spreadsheets/d/1hiWww6BI7NCTAw3Ai3CjbzS8TWdIX2AAOj7P_2BxMcQ/export?format=csv&gid=0"
        try:
            self.btn_refresh.configure(state="disabled", text="กำลังโหลด...")
            # Use thread to not freeze UI
            threading.Thread(target=self._fetch_data_thread, args=(sheet_url,), daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", f"โหลดข้อมูลล้มเหลว: {str(e)}")
            self.btn_refresh.configure(state="normal", text="รีเฟรชข้อมูล")

    def _fetch_data_thread(self, url):
        try:
            response = requests.get(url, timeout=10)
            response.encoding = 'utf-8'
            response.raise_for_status()
            df = pd.read_csv(io.StringIO(response.text))
            self.after(0, self._update_tree, df)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", f"โหลดข้อมูลล้มเหลว: {str(e)}"))
        finally:
            self.after(0, lambda: self.btn_refresh.configure(state="normal", text="รีเฟรชข้อมูล"))

    def _update_tree(self, df):
        # Clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Populate tree
        for index, row in df.iterrows():
            row_vals = [row.get(col, "") for col in self.tree_cols]
            self.tree.insert("", "end", values=row_vals)
            
    def save_data(self):
        required = ["UserName", "Password", "Email", "Prefix", "Organization", "ResponsiblePostoffice", "ResponsibleZipcode", "ActivationDate", "ContactPerson1", "TelContactPerson1"]
        for req in required:
            if not self.entries[req].get().strip():
                messagebox.showwarning("คำเตือน", f"กรุณาระบุ {req}")
                return
                
        messagebox.showinfo("แจ้งเตือน", "ข้อมูลพร้อมบันทึก\n(รอการเชื่อมต่อ API หรือสคริปต์สำหรับเขียนข้อมูลลง Google Sheets)")


class DPostConverterGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.withdraw()  # Hide main window initially
        self.title(f"C2DPost v{__version__}")
        self.geometry("1300x800")
        self.configure(fg_color=COLOR_BG)
        
        self.selected_files = []
        self.parsed_records = []
        self.dataframe = None
        self.current_theme = "light"
        self.last_pdf_dir = None
        self.user_data = None
        
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

        # Show login window
        self.after(100, self.show_login_window)

    def show_login_window(self):
        self.login_window = LoginWindow(self)
        
    def logout(self):
        if self.user_data:
            self.record_user_log(self.user_data.get("UserName", "Unknown"), "Logout - สำเร็จ")
        self.withdraw()
        self.user_data = None
        
        # Clear previous session data automatically
        self.selected_files = []
        self.parsed_records = []
        self.dataframe = None
        self.lbl_status.configure(text="ยังไม่ได้เลือกไฟล์")
        self.lbl_stat_files.configure(text="ไฟล์ PDF: 0 ไฟล์")
        self.lbl_stat_records.configure(text="รายการผู้รับ: 0 รายการ")
        self.btn_export.configure(state='disabled')
        self.btn_envelope.configure(state='disabled')
        self.btn_select_files.configure(text=" เพิ่มไฟล์ PDF ", state='normal')
        if hasattr(self, 'search_entry'):
            self.search_entry.delete(0, 'end')
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        self.show_login_window()

    def on_login_success(self, user_data):
        self.user_data = user_data
        self.record_user_log(user_data.get("UserName", "Unknown"), "Login - สำเร็จ")
        
        org_name = user_data.get("Organization", "สำนักงานที่ดิน")
        if pd.isna(org_name) or str(org_name).strip() == "":
            org_name = "สำนักงานที่ดิน"
        
        self.lbl_header_title.configure(text=str(org_name).strip())
        
        self.deiconify()
        self.state('zoomed')

    def on_admin_login_success(self, user_data):
        self.user_data = user_data
        self.record_user_log(user_data.get("UserName", "Admin"), "Login - สำเร็จ")
        # Don't show main GUI, show Admin Management
        self.admin_window = AdminManagementWindow(self)

    def record_user_log(self, username, action_status):
        # TODO: Replace with your deployed Google Apps Script Web App URL
        script_url = "https://script.google.com/macros/s/AKfycbzNEBcaLUc7UWSXtLuf3VnaTR4pP_4Xfxwaq8zKOQHGolyQL9UT2RAGKaT8jtBCzko/exec"
        
        if script_url == "YOUR_WEB_APP_URL_HERE":
            return
            
        def _send_log():
            try:
                data = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "username": username,
                    "status": action_status
                }
                requests.post(script_url, json=data, timeout=5)
            except Exception as e:
                print(f"Failed to record user log: {e}")
                
        threading.Thread(target=_send_log, daemon=True).start()

    def record_detailed_barcodes(self, records):
        # TODO: Replace with your deployed Google Apps Script Web App URL for Barcode Sheet
        script_url = "https://script.google.com/macros/s/AKfycbyznLrLf7Qgi0glxzytW8uhpZfnu5Jkh_eUibgJxBe8z9dmBDs7ndM6deT6x8v59Q/exec"
        
        if script_url == "YOUR_BARCODE_WEB_APP_URL_HERE":
            return
            
        def _send_log():
            try:
                requests.post(script_url, json={"action": "log_detailed_barcodes", "data": records}, timeout=10)
            except Exception as e:
                print(f"Failed to record detailed barcodes: {e}")
                
        threading.Thread(target=_send_log, daemon=True).start()

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
        # 1. Header Banner (Emerald)
        header = ctk.CTkFrame(self, fg_color=COLOR_PRIMARY, corner_radius=0, height=65)
        header.pack(fill='x', side='top')
        header.pack_propagate(False)
        self.lbl_header_title = ctk.CTkLabel(header, text="สำนักงานที่ดิน", font=("Segoe UI", 20, "bold"), text_color="#ffffff")
        self.lbl_header_title.pack(side='left', padx=30)
        
        btn_logout = ctk.CTkButton(header, text="ออกจากระบบ", fg_color=COLOR_DANGER, hover_color=COLOR_DANGER_HOVER,
                                 text_color="#ffffff", font=("Segoe UI", 14, "bold"),
                                 height=32, width=130, corner_radius=8,
                                 command=self.logout)
        btn_logout.pack(side='right', padx=(15, 30))

        btn_info = ctk.CTkButton(header, text="ⓘ", fg_color="#047857", hover_color="#064e3b",
                                 text_color="#ffffff", font=("Segoe UI", 14, "bold"),
                                 width=32, height=32, corner_radius=16,
                                 command=self.show_supported_docs)
        btn_info.pack(side='right', padx=(10, 0))
        
        def open_dpost_website():
            import webbrowser
            webbrowser.open("https://dpost.thailandpost.com")
            
        def open_ear_website():
            import webbrowser
            webbrowser.open("https://e-ar.thailandpost.com/")
            
        btn_ear = ctk.CTkButton(header, text="e-AR", fg_color="#047857", hover_color="#064e3b",
                                 text_color="#ffffff", font=("Segoe UI", 14, "bold"),
                                 height=32, corner_radius=8,
                                 command=open_ear_website)
        btn_ear.pack(side='right', padx=(10, 0))
        
        btn_ear.bind("<Enter>", lambda event: self.show_tooltip("เว็บสำหรับตรวจใบตอบรับทางอิเล็กทรอนิกส์", event.x_root + 10, event.y_root + 10))
        btn_ear.bind("<Leave>", lambda event: self.hide_tooltip())
            
        btn_dpost = ctk.CTkButton(header, text="DPost", fg_color="#047857", hover_color="#064e3b",
                                 text_color="#ffffff", font=("Segoe UI", 14, "bold"),
                                 height=32, corner_radius=8,
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
        card_files = ctk.CTkFrame(container, fg_color=COLOR_CARD, corner_radius=12, border_width=1, border_color=COLOR_BORDER)
        card_files.grid(row=0, column=0, sticky='nsew', pady=(0, 15))
        
        ctk.CTkLabel(card_files, text="เลือกเอกสาร PDF", font=("Segoe UI", 16, "bold"), text_color=COLOR_PRIMARY).pack(anchor='w', padx=20, pady=(15, 5))
        
        btn_frame = ctk.CTkFrame(card_files, fg_color="transparent")
        btn_frame.pack(fill='x', padx=20, pady=(5, 12))
        
        self.btn_select_files = ctk.CTkButton(btn_frame, text="เพิ่มไฟล์ PDF", fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER,
                                                text_color="#ffffff",
                                                font=("Segoe UI", 14, "bold"), command=self.select_files, width=160, height=40, corner_radius=8)
        self.btn_select_files.pack(side='left', padx=(0, 10))
        
        # Add tooltip for select files button
        self.btn_select_files.bind("<Enter>", lambda event: self.show_tooltip("เลือกไฟล์ PDF ที่ออกจากระบบ", event.x_root + 10, event.y_root + 10))
        self.btn_select_files.bind("<Leave>", lambda event: self.hide_tooltip())
        
        # Removed btn_clear from here to place it in preview_header
        
        self.center_frame = ctk.CTkFrame(btn_frame, fg_color="transparent")
        self.center_frame.pack(side='left', fill='both', expand=True, padx=30)
        
        self.status_box = ctk.CTkFrame(self.center_frame, fg_color="#f5f5f5", border_width=1, border_color=COLOR_BORDER, corner_radius=6)
        self.status_box.pack(fill='both', expand=True)
        
        self.lbl_status = ctk.CTkLabel(self.status_box, text="ยังไม่ได้เลือกไฟล์", font=("Segoe UI", 12), text_color=COLOR_PRIMARY)
        self.lbl_status.pack(fill='both', expand=True, pady=(8, 8))
        
        self.btn_envelope = ctk.CTkButton(btn_frame, text="สร้างจ่าหน้าซอง", fg_color="#3b82f6", hover_color="#2563eb",
                                        text_color="#ffffff",
                                        font=("Segoe UI", 14, "bold"), command=self.export_envelope, state='disabled', width=160, height=40, corner_radius=8)
        self.btn_envelope.pack(side='right', padx=(15, 0))
        self.btn_envelope.bind("<Enter>", lambda event: self.show_tooltip("ต้องบันทึกไฟล์ก่อน จึงจะสร้างจ่าหน้าซองได้", event.x_root + 10, event.y_root + 10))
        self.btn_envelope.bind("<Leave>", lambda event: self.hide_tooltip())
        
        self.btn_export = ctk.CTkButton(btn_frame, text="บันทึกไฟล์", fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS_HOVER,
                                        text_color="#ffffff",
                                        font=("Segoe UI", 14, "bold"), command=self.export_excel, state='disabled', width=160, height=40, corner_radius=8)
        self.btn_export.pack(side='right')
        
        # Add tooltip for save button
        self.btn_export.bind("<Enter>", lambda event: self.show_tooltip("เมื่อบันทึกไฟล์ จะไม่สามารถแก้ไขข้อมูลได้\nไฟล์ที่ได้รับ\n1.ไฟล์ excel (สำหรับ DPost)\n2.ไฟล์ PDF (เอกสารพร้อมบาร์โค้ด)\n3.ไฟล์ PDF (ใบนำส่ง)", event.x_root + 10, event.y_root + 10))
        self.btn_export.bind("<Leave>", lambda event: self.hide_tooltip())
        
        self.progress = ctk.CTkProgressBar(self.status_box, progress_color=COLOR_PRIMARY, height=8, corner_radius=4)
        
        # Card 2: Preview Table
        card_preview = ctk.CTkFrame(container, fg_color=COLOR_CARD, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        card_preview.grid(row=1, column=0, sticky='nsew')
        
        preview_header = ctk.CTkFrame(card_preview, fg_color="transparent")
        preview_header.pack(fill='x', padx=20, pady=(15, 10))
        
        ctk.CTkLabel(preview_header, text="ตารางแสดงข้อมูล", font=("Segoe UI", 16, "bold"), text_color=COLOR_PRIMARY).pack(side='left')
        
        # Right aligned stats and search
        self.search_entry = ctk.CTkEntry(preview_header, placeholder_text=" ค้นหาผู้รับ / เลขอ้างอิง... ", width=250, height=30, font=("Segoe UI", 11), corner_radius=15)
        self.search_entry.pack(side='right', padx=(15, 0))
        
        self.btn_clear = ctk.CTkButton(preview_header, text="ล้างข้อมูล", fg_color=COLOR_DANGER, 
                                       hover_color=COLOR_DANGER_HOVER, text_color="#ffffff",
                                       font=("Segoe UI", 12, "bold"), command=self.clear_selection, width=110, height=30, corner_radius=15)
        self.btn_clear.pack(side='right', padx=(10, 0))
        self.btn_clear.bind("<Enter>", lambda event: self.show_tooltip("ลบข้อมูลทั้งหมด", event.x_root + 10, event.y_root + 10))
        self.btn_clear.bind("<Leave>", lambda event: self.hide_tooltip())
        
        self.lbl_stat_records = ctk.CTkLabel(preview_header, text="รายการผู้รับ: 0 รายการ", font=("Segoe UI", 11, "bold"), text_color=COLOR_TEXT_MUTED)
        self.lbl_stat_records.pack(side='right', padx=10)
        
        self.lbl_stat_files = ctk.CTkLabel(preview_header, text="ไฟล์ PDF: 0 ไฟล์", font=("Segoe UI", 11, "bold"), text_color=COLOR_TEXT_MUTED)
        self.lbl_stat_files.pack(side='right', padx=10)
        self.lbl_stat_files.bind("<Button-1>", self.show_selected_files_popup)
        self.lbl_stat_files.configure(cursor="hand2")
        self.lbl_stat_files.bind("<Enter>", lambda event: self.show_tooltip("คลิกเพื่อดูไฟล์ PDF ที่เลือก", event.x_root + 10, event.y_root + 10))
        self.lbl_stat_files.bind("<Leave>", lambda event: self.hide_tooltip())
        
        self.search_entry.bind("<KeyRelease>", self.filter_treeview)
        self.search_entry.bind("<Escape>", self.clear_search)
        
        # Treeview in a standard tk.Frame so it expands correctly
        table_frame = tk.Frame(card_preview, bg=COLOR_CARD)
        table_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        
        vsb = ctk.CTkScrollbar(table_frame, orientation="vertical")
        
        self.tree = ttk.Treeview(table_frame, selectmode="none", yscrollcommand=vsb.set)
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
            ("Select", "[ ✓ ]", 45, 45),
            ("No", "ลำดับ", 50, 40),
            ("Barcode", "หมายเลข", 130, 100),
            ("Ref", "เลขที่อ้างอิง", 120, 100),
            ("Receiver", "ผู้รับ", 180, 120),
            ("Address", "ที่อยู่ผู้รับ (ที่อยู่ / อำเภอ / จังหวัด)", 400, 150),
            ("Zip", "รหัสไปรษณีย์", 100, 80)
        ]
        
        self.tree["columns"] = [col[0] for col in self.columns]
        self.tree["show"] = "tree headings"
        
        # Configure tree column (#0) for unified Tools action (Delete + View)
        self.tree.heading("#0", text="เครื่องมือ", anchor='center')
        self.tree.column("#0", width=100, minwidth=100, stretch=False, anchor='center')
        
        for col_id, col_name, col_width, col_minwidth in self.columns:
            h_anchor = 'center'
            if col_id == "Select":
                self.tree.heading(col_id, text=col_name, anchor=h_anchor, command=self.toggle_all_checkboxes)
            else:
                self.tree.heading(col_id, text=col_name, anchor=h_anchor, command=lambda _col=col_id: self.sort_treeview(_col, False))
            
            # Make only Address stretch dynamically (responsive)
            stretch = True if col_id == "Address" else False
            
            col_anchor = 'w' if col_id in ["Receiver", "Address"] else 'center'
            self.tree.column(col_id, width=col_width, minwidth=col_minwidth, stretch=stretch, anchor=col_anchor)
            

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
        
        self.tree.tag_configure('selected_row', foreground='#166534', font=('Segoe UI', 10, 'bold'))
        self.tree.tag_configure('evenrow', background='#f8fafc')
        self.tree.tag_configure('oddrow', background='#ffffff')
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
            
        col_max_widths = {col[0]: col[2] for col in self.columns}

            
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
                if 'SELECTED' not in self.dataframe.columns:
                    self.dataframe['SELECTED'] = False
                is_selected = self.dataframe.at[idx, 'SELECTED']
                chk_text = "[ ✓ ]" if is_selected else "[   ]"
                
                # Calculate text widths dynamically (approximate pixel width)
                barcode_val = str(row.get('BARCODE_NO', ''))
                ref_val = str(row.get('INV_NO', ''))
                receiver_val = str(row.get('RECEIVER', ''))
                zip_val = str(row.get('RECEIVER_ZIPCODE', ''))
                
                col_max_widths['Barcode'] = max(col_max_widths['Barcode'], len(barcode_val) * 7 + 30)
                col_max_widths['Ref'] = max(col_max_widths['Ref'], len(ref_val) * 7 + 30)
                col_max_widths['Receiver'] = max(col_max_widths['Receiver'], len(receiver_val) * 7 + 30)
                col_max_widths['Address'] = max(col_max_widths['Address'], len(addr) * 7 + 30)
                
                tags = (tag, 'selected_row') if is_selected else (tag,)
                self.tree.insert("", "end", iid=str(idx), image=self.tools_normal_img, values=(
                    chk_text,
                    idx + 1,
                    barcode_val,
                    ref_val,
                    receiver_val,
                    addr,
                    zip_val
                ), tags=tags)
                
        # Apply dynamic column widths after loading all rows
        for col_id, max_w in col_max_widths.items():
            # Cap maximum width for Address to avoid pushing everything else off-screen
            final_width = min(max_w, 600) if col_id == "Address" else max_w
            self.tree.column(col_id, width=final_width)

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

    def toggle_all_checkboxes(self):
        if self.dataframe is None or self.dataframe.empty:
            return
            
        if 'SELECTED' not in self.dataframe.columns:
            self.dataframe['SELECTED'] = False
            
        # Only consider rows that have a barcode
        has_barcode = self.dataframe['BARCODE_NO'].notna() & (self.dataframe['BARCODE_NO'] != "")
        if not has_barcode.any():
            self.show_custom_msgbox("info", "แจ้งเตือน", "กรุณากด 'บันทึกไฟล์' เพื่อดึงหมายเลขบาร์โค้ดก่อนครับ")
            return
            
        # If all valid rows are selected, deselect them. Otherwise, select all valid rows.
        all_valid_selected = self.dataframe.loc[has_barcode, 'SELECTED'].all()
        new_val = not all_valid_selected
        
        self.dataframe.loc[has_barcode, 'SELECTED'] = new_val
        
        chk_text = "[ ✓ ]" if new_val else "[   ]"
        # Update the heading icon to reflect state
        self.tree.heading("Select", text=chk_text)
        
        for idx in self.dataframe[has_barcode].index:
            try:
                self.tree.set(str(idx), "Select", chk_text)
                # Update tags for coloring
                current_tags = list(self.tree.item(str(idx), "tags"))
                if "selected_row" in current_tags:
                    current_tags.remove("selected_row")
                if new_val:
                    current_tags.append("selected_row")
                self.tree.item(str(idx), tags=tuple(current_tags))
            except Exception:
                pass

    def on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region in ["cell", "tree"]:
            column = self.tree.identify_column(event.x)
            item = self.tree.identify_row(event.y)
            if item:
                if column == "#1":  # Our new Select column
                    idx = int(item)
                    
                    # Check if barcode exists before allowing selection
                    barcode = self.dataframe.at[idx, 'BARCODE_NO']
                    if pd.isna(barcode) or str(barcode).strip() == "":
                        self.show_custom_msgbox("info", "แจ้งเตือน", "รายการนี้ยังไม่มีหมายเลขบาร์โค้ด กรุณากด 'บันทึกไฟล์' เพื่อดึงหมายเลขก่อนครับ")
                        return

                    if 'SELECTED' not in self.dataframe.columns:
                        self.dataframe['SELECTED'] = False
                    current_val = self.dataframe.at[idx, 'SELECTED']
                    new_val = not current_val
                    self.dataframe.at[idx, 'SELECTED'] = new_val
                    chk_text = "[ ✓ ]" if new_val else "[   ]"
                    self.tree.set(item, "Select", chk_text)
                    
                    current_tags = list(self.tree.item(item, "tags"))
                    if "selected_row" in current_tags:
                        current_tags.remove("selected_row")
                    if new_val:
                        current_tags.append("selected_row")
                    self.tree.item(item, tags=tuple(current_tags))
                    
                    # Update header if all valid are selected or not
                    has_barcode = self.dataframe['BARCODE_NO'].notna() & (self.dataframe['BARCODE_NO'] != "")
                    all_selected = self.dataframe.loc[has_barcode, 'SELECTED'].all()
                    self.tree.heading("Select", text="[ ✓ ]" if all_selected else "[   ]")
                    return
                elif column == "#0":  # Column #0 is the unified Tools column
                    # Check if this row already has a barcode
                    try:
                        idx = int(item)
                        if self.dataframe is not None and not pd.isna(self.dataframe.loc[idx].get('BARCODE_NO')) and str(self.dataframe.loc[idx].get('BARCODE_NO')).strip():
                            self.show_custom_msgbox("info", "ข้อมูลถูกยืนยันแล้ว", "รายการนี้ถูกออกเลขลงทะเบียนแล้ว ไม่สามารถใช้งานเครื่องมือได้ครับ")
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
            else:
                # Hovering over other columns, maybe show full text tooltip if it's Address
                if column == "#6":  # Address column
                    vals = self.tree.item(item, 'values')
                    if vals and len(vals) >= 6:
                        address_text = vals[5]
                        self.show_tooltip(address_text, event.x_root + 15, event.y_root + 15)
                        return
                elif column == "#5": # Receiver column
                    vals = self.tree.item(item, 'values')
                    if vals and len(vals) >= 5:
                        receiver_text = vals[4]
                        self.show_tooltip(receiver_text, event.x_root + 15, event.y_root + 15)
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
        self.tooltip_window.wm_attributes("-transparentcolor", "black")
        self.tooltip_window.configure(bg="black")
        
        # Style the tooltip with a modern rounded frame
        self.tooltip_frame = ctk.CTkFrame(self.tooltip_window, fg_color="#ea580c", corner_radius=8, border_width=2, border_color="#ffffff")
        self.tooltip_frame.pack(fill="both", expand=True, padx=1, pady=1)
        
        self.tooltip_label = ctk.CTkLabel(self.tooltip_frame, text=text, justify='left',
                                          text_color="#ffffff", font=("Segoe UI", 12, "bold"), wraplength=400)
        self.tooltip_label.pack(padx=16, pady=10)
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

    def delete_selected(self):
        selected_iids = self.tree.selection()
        if not selected_iids:
            self.show_custom_msgbox("warning", "ข้อแนะนำ", "กรุณาคลิกเลือกรายการในตารางที่ต้องการลบก่อนครับ")
            return
            
        if not self.show_custom_msgbox("askyesno", "ยืนยันการลบ", "คุณต้องการลบข้อมูลที่เลือกใช่หรือไม่?\n\n(ระบบจะนำไฟล์ PDF ต้นฉบับของข้อมูลเหล่านี้ออกจากรายการด้วย)"):
            return
            
        if self.user_data:
            receiver_names = []
            for iid in selected_iids:
                row_values = self.tree.item(iid, 'values')
                if len(row_values) > 4:
                    receiver_names.append(str(row_values[4]))
            names_str = ", ".join(receiver_names)
            if len(names_str) > 100:
                names_str = names_str[:97] + "..."

        try:
            indices_to_delete = [int(iid) for iid in selected_iids]
            
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
                
                # Recalculate NO column after deletion
                if 'NO' in self.dataframe.columns:
                    self.dataframe['NO'] = list(range(1, len(self.dataframe) + 1))
                    
                self.parsed_records = self.dataframe.to_dict('records') if not self.dataframe.empty else []
                
                # Update UI
                self.lbl_stat_files.configure(text=f"ไฟล์ PDF: {len(self.selected_files)} ไฟล์")
                self.lbl_stat_records.configure(text=f"รายการผู้รับ: {len(self.dataframe)} รายการ")
                
                if self.dataframe.empty:
                    self.clear_selection()
                else:
                    self.filter_treeview()
                    
            if self.user_data:
                self.record_user_log(self.user_data.get("UserName", "Unknown"), f"Delete: {names_str} - สำเร็จ")
        except Exception as e:
            if self.user_data:
                self.record_user_log(self.user_data.get("UserName", "Unknown"), f"Delete: {names_str} - ไม่สำเร็จ")
            self.show_custom_msgbox("error", "เกิดข้อผิดพลาด", f"ไม่สามารถลบรายการได้เนื่องจาก:\n{str(e)}")

    def open_pdf(self, event=None):
        selected_iids = self.tree.selection()
        if not selected_iids:
            return
            
        try:
            idx = int(selected_iids[0])
            if self.dataframe is None or self.dataframe.empty or idx not in self.dataframe.index:
                self.show_custom_msgbox("warning", "ข้อผิดพลาด", "ไม่พบข้อมูลในตาราง")
                return
                
            file_path = self.dataframe.loc[idx, 'FILE_PATH']
            if not file_path:
                self.show_custom_msgbox("warning", "ข้อแนะนำ", "กรุณากดปุ่ม 'ล้างข้อมูล' และเลือกไฟล์ PDF เข้ามาใหม่อีกครั้ง เพื่อให้ระบบจำไฟล์ต้นฉบับครับ")
                return
                
            if str(file_path).strip() == "" or str(file_path).strip() == "nan":
                self.show_custom_msgbox("warning", "ข้อผิดพลาด", "ข้อมูลบรรทัดนี้ไม่มีไฟล์ต้นฉบับบันทึกไว้")
                return
                
            import os
            import sys
            if not os.path.exists(file_path):
                self.show_custom_msgbox("error", "ไม่พบไฟล์", f"ไม่พบไฟล์ต้นฉบับในระบบ:\n{file_path}")
                return
                
            if sys.platform == "win32":
                os.startfile(file_path)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.call(["open", file_path])
        except Exception as e:
            self.show_custom_msgbox("error", "เกิดข้อผิดพลาด", f"ไม่สามารถเปิดไฟล์ได้เนื่องจาก:\n{str(e)}")

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
        if self.dataframe is not None and not self.dataframe.empty:
            if not self.show_custom_msgbox("askyesno", "ยืนยันการล้างข้อมูล", "คุณต้องการล้างข้อมูลผู้รับและไฟล์ PDF ทั้งหมดที่เลือกไว้ใช่หรือไม่?"):
                return
                
        self.selected_files = []
        self.parsed_records = []
        self.dataframe = None
        self.lbl_status.configure(text="ยังไม่ได้เลือกไฟล์")
        self.lbl_stat_files.configure(text="ไฟล์ PDF: 0 ไฟล์")
        self.lbl_stat_records.configure(text="รายการผู้รับ: 0 รายการ")
        
        self.btn_export.configure(state='disabled')
        self.btn_envelope.configure(state='disabled')
        self.btn_select_files.configure(text=" เพิ่มไฟล์ PDF ", state='normal')
        
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        if self.user_data:
            self.record_user_log(self.user_data.get("UserName", "Unknown"), "Clear All Data - สำเร็จ")

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
            if len(new_files) < len(files):
                self.show_custom_msgbox("info", "ข้อมูลซ้ำ", f"พบไฟล์ที่เลือกไปแล้ว {len(files) - len(new_files)} ไฟล์\nระบบจะเพิ่มเฉพาะไฟล์ใหม่")
            
            if new_files:
                self.selected_files.extend(new_files)
                self.lbl_status.configure(text=f"เลือกไฟล์ทั้งหมด {len(self.selected_files)} ไฟล์")
                self.start_conversion(new_files)

    def start_conversion(self, files_to_process):
        if not files_to_process:
            return

        self.btn_select_files.configure(state='disabled')
        self.btn_clear.configure(state='disabled')
        self.btn_export.configure(state='disabled')
        self.btn_envelope.configure(state='disabled')
        
        self.progress.pack(fill='x', side='bottom', padx=2, pady=(0, 2))
        self.progress.set(0)
        self.lbl_status.configure(text="กำลังแปลงไฟล์... (0%)")
        self.lbl_status.pack(pady=(4, 0)) # adjust padding when progress bar is visible
        
        thread = threading.Thread(target=self.run_conversion_task, args=(files_to_process,))
        thread.daemon = True
        thread.start()

    def run_conversion_task(self, files_to_process):
        new_records = []
        error_files = []
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
                    error_files.append((filepath, "ไม่พบข้อมูล"))
            except Exception as e:
                error_files.append((filepath, str(e)))
                
            self.after(10, self.update_progress, (i + 1) / total, i + 1, total)
            
        new_df = None
        if new_records:
            self.after(10, lambda: self.lbl_status.configure(text=f"กำลังสร้างตารางข้อมูล..."))
            try:
                new_df = records_to_dataframe(new_records)
            except Exception as e:
                error_files.append(("General", f"การสร้างตารางข้อมูล: {str(e)}"))
            
        self.after(10, self.conversion_completed, new_records, error_files, new_df)

    def update_progress(self, val, current, total):
        self.progress.set(val)
        percent = int(val * 100)
        self.lbl_status.configure(text=f"กำลังแปลงไฟล์... {current}/{total} ({percent}%)")

    def conversion_completed(self, new_records, error_files, new_df=None):
        self.progress.pack_forget()
        self.lbl_status.pack(pady=(8, 8)) # restore padding
        
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONINFORMATION)
        except Exception:
            pass
        
        if error_files:
            error_list = "\n".join([f"- {os.path.basename(f)}: {err}" for f, err in error_files])
            self.show_custom_msgbox("error", "พบปัญหาในการทำงาน", f"เกิดข้อผิดพลาดดังนี้:\n\n{error_list}")
            
        # Remove failed files from self.selected_files
        failed_files = [f for f, _ in error_files]
        if failed_files:
            self.selected_files = [f for f in self.selected_files if f not in failed_files]
            
        if new_records and new_df is not None:
            # new_df = records_to_dataframe(new_records)
            
            if self.dataframe is None or self.dataframe.empty:
                self.dataframe = new_df
            else:
                # Merge dataframes
                self.dataframe = pd.concat([self.dataframe, new_df], ignore_index=True)
                
            # Recalculate NO column to ensure continuous sequence across multiple files
            if 'NO' in self.dataframe.columns:
                self.dataframe['NO'] = list(range(1, len(self.dataframe) + 1))
                
            self.parsed_records = self.dataframe.to_dict('records')
            
            self.lbl_stat_files.configure(text=f"ไฟล์ PDF: {len(self.selected_files)} ไฟล์")
            self.lbl_stat_records.configure(text=f"รายการผู้รับ: {len(self.dataframe)} รายการ")
            self.lbl_status.configure(text=f"ประมวลผลเสร็จสิ้น รวมทั้งหมด {len(self.dataframe)} รายการ")
            
            if self.user_data:
                file_names = ", ".join([os.path.basename(f) for f in self.selected_files]) if self.selected_files else f"{len(new_records)} items"
                self.record_user_log(self.user_data.get("UserName", "Unknown"), f"Load PDF: {file_names} - สำเร็จ")
            
            self.filter_treeview()
        else:
            self.lbl_stat_files.configure(text=f"ไฟล์ PDF: {len(self.selected_files)} ไฟล์")
            self.lbl_stat_records.configure(text=f"รายการผู้รับ: {len(self.dataframe) if self.dataframe is not None else 0} รายการ")
            
            if not self.parsed_records:
                self.lbl_status.configure(text="ไม่พบข้อมูลในไฟล์ที่เลือก")
                if self.user_data:
                    file_names = ", ".join([os.path.basename(f) for f in self.selected_files]) if self.selected_files else "Unknown"
                    self.record_user_log(self.user_data.get("UserName", "Unknown"), f"Load PDF: {file_names} - ไม่สำเร็จ")
            else:
                self.lbl_status.configure(text=f"ประมวลผลเสร็จสิ้น รวมทั้งหมด {len(self.dataframe)} รายการ")
                if self.user_data:
                    file_names = ", ".join([os.path.basename(f) for f in self.selected_files]) if self.selected_files else "Unknown"
                    self.record_user_log(self.user_data.get("UserName", "Unknown"), f"Load PDF: {file_names} - สำเร็จ")
        
        self.btn_select_files.configure(state='normal')
        self.btn_clear.configure(state='normal')
        if self.dataframe is not None and not self.dataframe.empty:
            self.btn_export.configure(state='normal')
            if 'BARCODE_NO' in self.dataframe.columns and not (self.dataframe['BARCODE_NO'].isna() | (self.dataframe['BARCODE_NO'] == "")).any():
                self.btn_envelope.configure(state='normal')
            else:
                self.btn_envelope.configure(state='disabled')
        else:
            self.btn_export.configure(state='disabled')
            self.btn_envelope.configure(state='disabled')

    def show_supported_docs(self):
        self.show_custom_msgbox(
            "info",
            "เอกสารที่รองรับ",
            "ระบบปัจจุบันรองรับการแปลงไฟล์ประเภท:\n\n"
            "• ท.ด. 38\n"
            "• ท.ด. 81\n"
            "• ออกโฉนดที่ดิน"
        )

    def export_excel(self):
        if self.dataframe is None or self.dataframe.empty:
            self.show_custom_msgbox("warning", "ไม่มีข้อมูล", "กรุณาแปลงไฟล์ PDF ก่อนบันทึก")
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
                    self.show_custom_msgbox("warning", "คำเตือน", "ดึงบาร์โค้ดได้ไม่ครบตามจำนวนข้อมูล")
                
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
                        self.dataframe.at[i, 'SELECTED'] = True
                    else:
                        self.dataframe.at[i, 'BARCODE_NO'] = ""
                        self.dataframe.at[i, 'SELECTED'] = True
                        
                # Update header to checked since default is now True
                if len(barcodes) > 0 and len(barcodes) == num_records:
                    self.tree.heading("Select", text="[ ✓ ]")
                    
                # Generate detailed barcode logs
                barcode_logs = []
                for i in range(num_records):
                    if i < len(barcodes):
                        barcode = barcodes[i]
                        receiver = str(self.dataframe.at[i, 'RECEIVER']) if pd.notna(self.dataframe.at[i, 'RECEIVER']) else ""
                        address = str(self.dataframe.at[i, 'RECEIVER_ADDRESS']) if pd.notna(self.dataframe.at[i, 'RECEIVER_ADDRESS']) else ""
                        amphur = str(self.dataframe.at[i, 'RECEIVER_AMPHUR']) if 'RECEIVER_AMPHUR' in self.dataframe.columns and pd.notna(self.dataframe.at[i, 'RECEIVER_AMPHUR']) else ""
                        province = str(self.dataframe.at[i, 'RECEIVER_PROVINCE']) if 'RECEIVER_PROVINCE' in self.dataframe.columns and pd.notna(self.dataframe.at[i, 'RECEIVER_PROVINCE']) else ""
                        zipcode = str(self.dataframe.at[i, 'RECEIVER_ZIPCODE']) if pd.notna(self.dataframe.at[i, 'RECEIVER_ZIPCODE']) else ""
                        
                        details = " ".join([part for part in [receiver, address, amphur, province, zipcode] if part.strip()])
                        
                        barcode_logs.append({
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "username": self.user_data.get("UserName", "Unknown") if self.user_data else "Unknown",
                            "barcode": barcode,
                            "details": details
                        })
                
                if barcode_logs:
                    self.record_detailed_barcodes(barcode_logs)
                        
                # Update the UI table to show the fetched barcodes
                self.filter_treeview()
                self.update()
                
                # Enable envelope generation after barcodes are fetched
                self.btn_envelope.configure(state='normal')
                
                # Disable Add PDF button so user must clear data to start over
                self.btn_select_files.configure(state='disabled')

                export_df = self.dataframe.copy()
                
                # Drop metadata and internal state columns before export
                cols_to_drop = [c for c in ['SOURCE_FILE', 'source_file', 'SELECTED'] if c in export_df.columns]
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
                    if hasattr(self, 'user_data') and self.user_data:
                        self.record_user_log(self.user_data.get("UserName", "Unknown"), f"Export Excel ({len(self.dataframe)} items) - สำเร็จ")
                except Exception as pdf_e:
                    self.show_custom_msgbox("error", "ข้อผิดพลาด PDF", f"สร้าง Excel สำเร็จ แต่ไม่สามารถสร้าง PDF ได้:\n{str(pdf_e)}")
                    self.show_success_dialog(filepath, "", "")
                    self.lbl_status.configure(text="บันทึกไฟล์ Excel สำเร็จ แต่สร้าง PDF ล้มเหลว")
                    if hasattr(self, 'user_data') and self.user_data:
                        self.record_user_log(self.user_data.get("UserName", "Unknown"), f"Export Excel ({len(self.dataframe)} items) - สำเร็จ (PDF Fail)")
                
                if sys.platform == "win32":
                    os.startfile(filepath)
                    if os.path.exists(pdf_filepath):
                        os.startfile(pdf_filepath)
                    if os.path.exists(delivery_note_filepath):
                        os.startfile(delivery_note_filepath)
            except Exception as e:
                try:
                    import winsound
                    winsound.MessageBeep(winsound.MB_ICONHAND)
                except Exception:
                    pass
                self.show_custom_msgbox("error", "ข้อผิดพลาด", f"ไม่สามารถบันทึกไฟล์ได้:\n{str(e)}")
                if hasattr(self, 'user_data') and self.user_data:
                    self.record_user_log(self.user_data.get("UserName", "Unknown"), f"Export Excel ({len(self.dataframe)} items) - ไม่สำเร็จ")

    def show_custom_msgbox(self, msg_type, title, message):
        try:
            import winsound
            if msg_type == "error":
                winsound.MessageBeep(winsound.MB_ICONHAND)
            elif msg_type == "askyesno" or msg_type == "warning":
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            else:
                winsound.MessageBeep(winsound.MB_OK)
        except Exception:
            pass

        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("450x300")
        dialog.configure(fg_color=COLOR_CARD)
        dialog.transient(self)
        dialog.grab_set()

        # Center the dialog
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 450) // 2
        y = self.winfo_y() + (self.winfo_height() - 300) // 2
        dialog.geometry(f"+{x}+{y}")

        main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Icon and Colors based on msg_type
        if msg_type == "info":
            icon_text = "i️"
            icon_color = "#3b82f6"  # Blue
        elif msg_type == "warning":
            icon_text = ""
            icon_color = "#eab308"  # Yellow
        elif msg_type == "error":
            icon_text = ""
            icon_color = "#ef4444"  # Red
        elif msg_type == "askyesno":
            icon_text = ""
            icon_color = "#f97316"  # Orange
        else:
            icon_text = "i️"
            icon_color = COLOR_PRIMARY
            
        icon_lbl = ctk.CTkLabel(main_frame, text=icon_text, font=("Segoe UI", 48), text_color=icon_color)
        icon_lbl.pack(pady=(0, 10))

        msg_lbl = ctk.CTkLabel(main_frame, text=message, font=("Segoe UI", 14), text_color=COLOR_TEXT_MAIN, wraplength=400, justify="center")
        msg_lbl.pack(pady=(0, 20), expand=True)

        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(10, 0))

        result = tk.BooleanVar(value=False)

        def on_yes():
            result.set(True)
            dialog.destroy()

        def on_no():
            result.set(False)
            dialog.destroy()

        if msg_type == "askyesno":
            btn_yes = ctk.CTkButton(btn_frame, text="ตกลง", command=on_yes, font=("Segoe UI", 14, "bold"), fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER, width=130, height=36, corner_radius=8)
            btn_yes.pack(side="left", padx=10, expand=True, anchor="e")
            
            btn_no = ctk.CTkButton(btn_frame, text="ยกเลิก", command=on_no, font=("Segoe UI", 14, "bold"), fg_color=COLOR_DANGER, hover_color=COLOR_DANGER_HOVER, width=130, height=36, corner_radius=8)
            btn_no.pack(side="right", padx=10, expand=True, anchor="w")
        else:
            btn_ok = ctk.CTkButton(btn_frame, text="ตกลง", command=on_yes, font=("Segoe UI", 14, "bold"), fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER, width=130, height=36, corner_radius=8)
            btn_ok.pack(pady=0)

        # Wait for user action
        dialog.wait_window()
        
        return result.get()

    def show_success_dialog(self, excel_path, pdf_path, delivery_path):
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_OK)
        except Exception:
            pass
            
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
        
        icon_lbl = ctk.CTkLabel(main_frame, text="", font=("Segoe UI", 48), text_color=COLOR_SUCCESS)
        icon_lbl.pack(pady=(0, 10))
        
        title_lbl = ctk.CTkLabel(main_frame, text="บันทึกไฟล์สำเร็จเรียบร้อยแล้ว!", font=("Segoe UI", 16, "bold"), text_color=COLOR_TEXT_MAIN)
        title_lbl.pack(pady=(0, 15))
        
        paths_frame = ctk.CTkFrame(main_frame, fg_color="#f8fafc", corner_radius=8, border_width=1, border_color="#e2e8f0")
        paths_frame.pack(fill="x", expand=True)
        
        import os
        files_list = []
        if excel_path:
            files_list.append(f"{os.path.basename(excel_path)}")
        if pdf_path:
            files_list.append(f"{os.path.basename(pdf_path)}")
        if delivery_path:
            files_list.append(f"{os.path.basename(delivery_path)}")
            
        files_text = "\n".join(files_list)
            
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
        
        icon_lbl = ctk.CTkLabel(main_frame, text="ⓘ", font=("Segoe UI", 48))
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
            
        btn_download = ctk.CTkButton(btn_frame, text="ดาวน์โหลด", command=on_download, fg_color=COLOR_PRIMARY, hover_color="#14532d", font=("Segoe UI", 12, "bold"))
        btn_download.pack(side="left", padx=10)
        
        btn_cancel = ctk.CTkButton(btn_frame, text="ไว้ทีหลัง", command=dialog.destroy, fg_color="#ef4444", hover_color="#b91c1c", font=("Segoe UI", 12, "bold"))
        btn_cancel.pack(side="left", padx=10)

    def export_envelope(self):
        if self.dataframe is None or self.dataframe.empty:
            return
            
        if 'SELECTED' not in self.dataframe.columns:
            self.dataframe['SELECTED'] = True
            
        selected_mask = self.dataframe['SELECTED'] == True
        if not selected_mask.any():
            self.show_custom_msgbox("info", "ยังไม่ได้เลือกรายการ", "กรุณาเลือกรายการที่ต้องการสร้างจ่าหน้าซองก่อนครับ")
            return
            
        target_df = self.dataframe[selected_mask]
            
        # Check if barcodes exist
        missing_barcodes = target_df['BARCODE_NO'].isna() | (target_df['BARCODE_NO'] == "")
        if missing_barcodes.any():
            self.show_custom_msgbox("info", "ยังไม่ได้ออกเลขบาร์โค้ด", "รายการที่เลือกยังไม่ได้ออกเลขบาร์โค้ด กรุณากด 'บันทึกไฟล์' ก่อนครับ\n(หรือกรอกเลขบาร์โค้ดให้ครบในตาราง)")
            return
            
        import datetime
        now = datetime.datetime.now()
        default_filename = f"Envelopes_{now.strftime('%Y%m%d_%H%M%S')}.pdf"
        
        output_pdf = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=default_filename,
            filetypes=[("PDF files", "*.pdf")],
            title="บันทึกไฟล์จ่าหน้าซอง"
        )
        
        if not output_pdf:
            return
            
        try:
            self.lbl_status.configure(text="กำลังสร้างไฟล์จ่าหน้าซอง...")
            self.update_idletasks()
            
            from convert_dpost import generate_combined_pdf
            generate_combined_pdf(target_df, output_pdf, envelope_only=True)
            
            self.show_success_dialog("", output_pdf, "")
            self.lbl_status.configure(text="สร้างไฟล์จ่าหน้าซองสำเร็จ")
            
            import os
            import sys
            if sys.platform == "win32":
                os.startfile(output_pdf)
        except Exception as e:
            self.show_custom_msgbox("error", "ข้อผิดพลาด", f"ไม่สามารถสร้างไฟล์จ่าหน้าซองได้:\n{str(e)}")
            self.lbl_status.configure(text="เกิดข้อผิดพลาดในการสร้างไฟล์จ่าหน้าซอง")

def main():
    app = DPostConverterGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
