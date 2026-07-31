import sys
from pypdf import PdfReader

def get_y_coord(pdf_path):
    reader = PdfReader(pdf_path)
    for i, page in enumerate(reader.pages):
        coords = []
        def visitor_body(text, cm, tm, font_dict, font_size):
            if "เรียน" in text:
                coords.append((text, tm[4], tm[5]))
        page.extract_text(visitor_text=visitor_body)
        print(f"Page {i}: {coords}")

if __name__ == '__main__':
    # We will run this on a file in the directory
    import glob
    import os
    # Use path module to find PDF in sample folder
    pdfs = glob.glob(os.path.join('ไฟล์ตัวอย่าง', '*.pdf'))
    if pdfs:
        print(f"Testing on {pdfs[0]}")
        get_y_coord(pdfs[0])
    else:
        print("No PDF found")
