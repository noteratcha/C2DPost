---
name: dpost_converter
description: Skills for converting mailing labels in PDF files into DPost Excel import sheets and managing the Tkinter GUI.
---
# DPost PDF Converter Skill

Use this skill when modifying the PDF mailing label conversion logic or updating the Tkinter GUI for the DPost application.

## Core Architecture
- **Backend ([convert_dpost.py](file:///d:/Note/โปรเจค/Convert%20Dpost/convert_dpost.py))**:
  - Handles parsing logic (using `pypdf.PdfReader` and regex).
  - Normalizes Thai addresses (tambon, amphur, province, zipcode).
  - Converts parsed records to pandas DataFrames using [records_to_dataframe](file:///d:/Note/โปรเจค/Convert%20Dpost/convert_dpost.py#L348).
- **Frontend ([gui.py](file:///d:/Note/โปรเจค/Convert%20Dpost/gui.py))**:
  - Desktop UI built using `tkinter` and `ttk`.
  - Multi-threaded processing to keep the GUI responsive.
  - Redirects console prints directly to the GUI Log window.

## Custom Constraints
- Version format must always follow: `Year.MonthDay.HourMinute` (e.g. `2026.0630.1453`).
- Custom Tkinter buttons must use `disabledforeground` instead of `disabledbackground`.

## GUI Specifications (v2026.0704+)
- **Header Banner**:
  - Displays "สำนักงานที่ดิน" on the left.
  - Displays a clean circular `ℹ` info button (24x24px, corner_radius=12) on the right side. When clicked, it lists supported documents (currently "• ท.ด. 38").
- **Unified Tools Column (#0)**:
  - Width: 100px, stretch=False, anchor='center'.
  - Contains both the **Delete ✕** and **View ⌕** icons drawn dynamically as a single 100x16 `tk.PhotoImage` (`self.tools_normal_img`, `self.tools_hover_x_img`, `self.tools_hover_view_img`).
  - Active hover/click boundaries: Delete at `15 <= x <= 35`, View at `65 <= x <= 85`.
  - The default Tkinter Treeview disclosure arrows (`∨` or `▶`) are hidden by overriding the `Treeview.Item` style layout.
  - A vertical 1px gray frame (`self.divider` at `x=100`) acts as a visual boundary separating the Tools column from the rest of the data.
- **Hover Interactions**:
  - Hovering exactly over the X icon highlights it as **red (`#ef4444`)**.
  - Hovering exactly over the Magnifier highlights it as **blue (`#3b82f6`)**.
  - Hovering anywhere over a row highlights the entire row's text color to **orange (`#ea580c`)** using the `'hover'` tag.
- **Dynamic Tooltips**:
  - Positioned relative to the cursor but includes a **screen boundary check** (`winfo_screenwidth()` / `winfo_width()`) to automatically flip to the left of the cursor if the tooltip would extend off the right edge of the screen.
- **Clear Selection**:
  - Located in the preview header to prevent accidental clicks near primary action buttons.
  - Prompts for confirmation via `messagebox.askyesno` before erasing data.
