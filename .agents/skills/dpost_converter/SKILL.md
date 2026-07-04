---
name: dpost_converter
description: Skills for converting mailing labels in PDF files into DPost Excel import sheets and managing the Tkinter GUI.
---
# DPost PDF Converter Skill

Use this skill when modifying the PDF mailing label conversion logic or updating the Tkinter GUI for the DPost application.

## Core Architecture
- **Backend ([convert_dpost.py](file:///d:/โปรเจค/ConvertDpost/convert_dpost.py))**:
  - Handles parsing logic (using `pypdf.PdfReader` and regex).
  - Normalizes Thai addresses (tambon, amphur, province, zipcode).
  - Fetches registered barcodes from the Thailand Post API using Basic Auth + Base64 Encoding.
  - Converts parsed records to pandas DataFrames using `records_to_dataframe`.
- **Frontend ([gui.py](file:///d:/โปรเจค/ConvertDpost/gui.py))**:
  - Desktop UI built using `customtkinter` and `tkinter/ttk`.
  - Multi-threaded processing to keep the GUI responsive.
  - Handles background errors and displays them as UI popups to the user.

## Custom Constraints
- Version format must always follow: `Year.MonthDay.HourMinute` (e.g. `2026.0704.1453`).
- Custom Tkinter buttons should use styling configurations appropriate to `customtkinter`.

## GUI Specifications
- **Header Banner**:
  - Displays "สำนักงานที่ดิน" on the left.
  - Displays a clean circular `ℹ` info button (24x24px, corner_radius=12) on the right side. When clicked, it lists supported documents (currently "• ท.ด. 38").
- **Unified Tools Column (#0)**:
  - Width: 100px, stretch=False, anchor='center'.
  - Contains both the **Delete ✕** and **View ⌕** icons drawn dynamically as a single 100x16 `tk.PhotoImage`.
  - Active hover/click boundaries: Delete at `15 <= x <= 35`, View at `65 <= x <= 85`.
  - The default Tkinter Treeview disclosure arrows (`∨` or `▶`) are hidden by overriding the `Treeview.Item` style layout.
  - **Tool Lock**: If a row has been assigned a `BARCODE_NO` (meaning it has been exported and finalized), the tools (Delete/View) are locked. Hover effects are disabled, and clicking shows a warning popup preventing modifications.
- **Hover Interactions**:
  - Hovering exactly over the X icon highlights it as **red (`#ef4444`)**.
  - Hovering exactly over the Magnifier highlights it as **blue (`#3b82f6`)**.
  - Hovering anywhere over a row highlights the entire row's text color to **orange (`#ea580c`)** using the `'hover'` tag.
- **Dynamic Tooltips**:
  - Positioned relative to the cursor with a screen boundary check.
- **Clear Selection**:
  - Located in the preview header to prevent accidental clicks near primary action buttons.
  - Prompts for confirmation via `messagebox.askyesno` before erasing data.
  - Re-enables the "Add PDF" button.
- **Barcode Fetching & Export Flow**:
  - Barcodes are **not** fetched immediately upon PDF load.
  - When the user clicks "Export Excel", the system:
    1. Fetches barcodes from the API based on the number of records.
    2. Maps the barcodes to the `BARCODE_NO` column in the DataFrame.
    3. Updates the Treeview table UI to show the fetched barcodes instantly.
    4. Disables the "Add PDF" button to force a clean flow (requiring the user to clear data before importing new PDFs).
    5. Exports the updated DataFrame to Excel.
- **Error Handling**:
  - Background threading errors (e.g., from PDF processing or DataFrame creation) are caught, collected into a list, and dispatched to the main UI thread.
  - The main thread displays a comprehensive `messagebox.showerror` popup containing all accumulated errors, rather than printing silently to the console.
- **Path Memory**:
  - `filedialog.askopenfilenames` uses `initialdir` tied to a `self.last_pdf_dir` variable.
  - Upon successful file selection, this variable remembers the last directory used for seamless repeat usage.
