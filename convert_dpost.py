import os
import re
import glob
import pandas as pd
from pypdf import PdfReader, PdfWriter
import requests
import io
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import code128, qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4, portrait, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

try:
    pdfmetrics.registerFont(TTFont('Tahoma', 'C:/Windows/Fonts/tahoma.ttf'))
    pdfmetrics.registerFont(TTFont('Tahoma-Bold', 'C:/Windows/Fonts/tahomabd.ttf'))
    FONT_REGISTERED = True
except Exception:
    FONT_REGISTERED = False

__version__ = "2026.0705.1424"

# Thailand Post API Credentials
API_KEY = "V9JN25IFH5hdZYc1k8NNRVgnLYXyQLzc"
SHOP_ID = "18488"
API_USERNAME = "noteratcha"
API_PASSWORD = "092149506"
POSTONE_API_URL = "https://postone.thailandpost.com/api/bc.php"

def calculate_check_digit(serial_str):
    """
    Calculate Check Digit using Modulus 11 for Thailand Post Barcode.
    Weights: 8, 6, 4, 2, 3, 5, 9, 7
    """
    if len(serial_str) != 8:
        return "0"
    
    weights = [8, 6, 4, 2, 3, 5, 9, 7]
    total = sum(int(digit) * weight for digit, weight in zip(serial_str, weights))
    remainder = total % 11
    
    if remainder == 0:
        return "5"
    elif remainder == 1:
        return "0"
    else:
        return str(11 - remainder)

def fetch_registered_barcodes(cnt):
    """
    Fetch `cnt` registered barcodes (typ=2) from Thailand Post API.
    Returns a list of 13-character barcode strings.
    """
    import base64
    if cnt <= 0:
        return []
        
    auth_str = f"{SHOP_ID}:{API_KEY}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_auth}"
    }
    
    try:
        response = requests.get(
            f"{POSTONE_API_URL}?typ=2&cnt={cnt}",
            headers=headers,
            timeout=10
        )
        # Remove UTF-8 BOM if present
        text = response.text
        if text.startswith('\ufeff'):
            text = text[len('\ufeff'):]
            
        import json
        data = json.loads(text)
        
        if data.get("STATUS") == "SUCCESS":
            prefix = data.get("PRE", "")
            begin = int(data.get("BEGIN", 0))
            end = int(data.get("END", 0))
            
            if begin > end:
                print("Error: BEGIN is greater than END")
                return []
            
            barcodes = []
            for serial in range(begin, end + 1):
                serial_str = str(serial).zfill(8)
                check_digit = calculate_check_digit(serial_str)
                # Depending on how PRE is formatted by the API. If PRE is "RETH", this puts "RE" at front and "TH" at back.
                # If PRE is just "RE", we append "TH".
                if len(prefix) >= 4:
                    full_barcode = f"{prefix[:2]}{serial_str}{check_digit}{prefix[2:4]}"
                else:
                    full_barcode = f"{prefix[:2]}{serial_str}{check_digit}TH"
                barcodes.append(full_barcode)
                
            return barcodes
        else:
            print(f"API Error: {data.get('STATUS')}")
            return []
    except Exception as e:
        print(f"Failed to fetch barcodes: {e}")
        return []

# Mapping of Thai digits to Arabic digits
THAI_TO_ARABIC = str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789')

def clean_thai_digits(text):
    if not text:
        return ""
    return text.translate(THAI_TO_ARABIC)

def apply_thai_pua(text):
    """
    Since Tahoma does not have MacThai PUA glyphs, tone marks placed over
    upper vowels or tall consonants will overlap in ReportLab. 
    This function injects ReportLab's Paragraph XML tags <super> 
    to manually lift the tone marks so they are visible.
    """
    if not isinstance(text, str):
        return text
        
    upper_vowels = "\u0e31\u0e34\u0e35\u0e36\u0e37\u0e4d" # ั, ิ, ี, ึ, ื, ํ
    tall_consonants = "\u0e1b\u0e1d\u0e1f\u0e2c" # ป, ฝ, ฟ, ฬ
    tone_marks = "\u0e48\u0e49\u0e4a\u0e4b\u0e4c" # ่, ้, ๊, ๋, ์
    
    res = []
    for i, char in enumerate(text):
        if char in tone_marks and i > 0 and (text[i-1] in upper_vowels or text[i-1] in tall_consonants):
            # Lift the tone mark using <super> so it sits above the upper vowel/tall consonant
            res.append(f'<super>{char}</super>')
        else:
            res.append(char)
            
    return "".join(res)

def extract_tel(text):
    """Extract telephone number from text and convert to Arabic digits."""
    if not text:
        return ""
    # Find patterns like โทร. 08-xxxx-xxxx or โทร. ๐๘ xxxx xxxx
    match = re.search(r'โทร\s*\.?\s*([๐-๙0-9\-\s\.,]+)', text)
    if match:
        tel = match.group(1).strip()
        # Clean digits and remove non-numeric chars except hyphen
        tel_clean = clean_thai_digits(tel)
        tel_digits = re.sub(r'[^0-9]', '', tel_clean)
        return tel_digits
    return ""

def parse_address_components(address_text):
    """
    Parse Tambon, Amphur, Province and Zipcode from address text.
    Standard patterns:
    ตำบล/แขวง ... -> ต. ...
    อำเภอ/เขต ... -> อ. ...
    จังหวัด ... -> จ. ...
    """
    # Normalize spaces
    address_text = re.sub(r'\s+', ' ', address_text)
    
    # Extract zipcode (5 digits)
    zip_match = re.search(r'(\b[0-9]{5}\b)', address_text)
    zipcode = zip_match.group(1) if zip_match else ""
    
    # Extract Amphur
    amphur_match = re.search(r'(?:อำเภอ/เขต|อำเภอ|อ\.)\s*([^\sจ\.]+)', address_text)
    amphur = amphur_match.group(1).strip() if amphur_match else ""
    
    # Extract Province
    province_match = re.search(r'(?:จังหวัด|จ\.)\s*([^\s\d]+)', address_text)
    province = province_match.group(1).strip() if province_match else ""
    
    # Fallback for Province: if not found, look for the word immediately preceding the zipcode
    if not province and zipcode:
        prov_match = re.search(r'([ก-ฮ]{2,})\s+' + zipcode, address_text)
        if prov_match:
            province = prov_match.group(1).strip()
            
    return amphur, province, zipcode

def parse_receiver_label(text):
    """
    Parse the receiver label block:
    เรียน <Name>
    <Address lines>
    <5-digit zipcode>
    """
    # Normalize lines
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    receiver_name = ""
    address_lines = []
    zipcode = ""
    
    # Look for the index of the line starting with "เรียน"
    start_idx = -1
    for i, line in enumerate(lines):
        if line.startswith("เรียน"):
            start_idx = i
            break
            
    if start_idx == -1:
        return None
        
    receiver_name = re.sub(r'^เรียน\s*', '', lines[start_idx]).strip()
    
    # Collect subsequent lines until a zipcode is found
    zip_pattern = re.compile(r'^[๐-๙0-9]{5}$')
    end_idx = -1
    
    for i in range(start_idx + 1, len(lines)):
        line_clean = clean_thai_digits(lines[i])
        if zip_pattern.match(line_clean):
            zipcode = line_clean
            end_idx = i
            break
            
    if end_idx == -1:
        # If no strict 5-digit line, check if the last line contains a zipcode
        for i in range(start_idx + 1, len(lines)):
            line_clean = clean_thai_digits(lines[i])
            zip_match = re.search(r'([0-9]{5})', line_clean)
            if zip_match:
                zipcode = zip_match.group(1)
                end_idx = i
                break
                
    if end_idx == -1:
        return None # Could not find valid zipcode boundary
        
    # Address lines are between start_idx+1 and end_idx (inclusive if zip was at the end of a line)
    raw_address_lines = lines[start_idx + 1 : end_idx]
    # If the end line had text before zip, append the text part
    end_line_clean = lines[end_idx]
    if len(clean_thai_digits(end_line_clean)) > 5:
        # Remove zipcode from the line
        text_before_zip = re.sub(r'[๐-๙0-9]{5}\s*$', '', end_line_clean).strip()
        if text_before_zip:
            raw_address_lines.append(text_before_zip)
            
    # Clean address lines (e.g. replace ตำบล/แขวง with ต. , อำเภอ/เขต with อ.)
    cleaned_address_lines = []
    amphur = ""
    province = ""
    
    for line in raw_address_lines:
        line_conv = clean_thai_digits(line)
        
        # Check for tambon
        t_match = re.search(r'^(?:ตำบล/แขวง|ตำบล|ต\.)\s*(.+)$', line_conv)
        if t_match:
            cleaned_address_lines.append(f"ต.{t_match.group(1).strip()}")
            continue
            
        # Check for amphur
        a_match = re.search(r'^(?:อำเภอ/เขต|อำเภอ|อ\.)\s*(.+)$', line_conv)
        if a_match:
            amphur = a_match.group(1).strip()
            # Do NOT append to cleaned_address_lines to cut from receiver_address
            continue
            
        # Check for province
        p_match = re.search(r'^(?:จังหวัด|จ\.)\s*(.+)$', line_conv)
        if p_match:
            province = p_match.group(1).strip()
            # Do NOT append to cleaned_address_lines to cut from receiver_address
            continue
            
        cleaned_address_lines.append(line)
        
    # Reconstruct address (excluding zipcode to cut it from receiver_address)
    receiver_address = " ".join(cleaned_address_lines)
    
    # Try to extract amphur and province if not found yet
    if not amphur or not province:
        raw_joined = " ".join(raw_address_lines) + " " + zipcode
        ext_amphur, ext_province, _ = parse_address_components(raw_joined)
        if not amphur:
            amphur = ext_amphur
        if not province:
            province = ext_province
            
    # Post-processing cleanup: Remove amphur, province, and zipcode from receiver_address if present
    if amphur:
        receiver_address = re.sub(r'(?:อำเภอ/เขต|อำเภอ|อ\.)\s*' + re.escape(amphur), '', receiver_address)
        receiver_address = re.sub(r'\b' + re.escape(amphur) + r'\b', '', receiver_address)
    if province:
        receiver_address = re.sub(r'(?:จังหวัด|จ\.)\s*' + re.escape(province), '', receiver_address)
        receiver_address = re.sub(r'\b' + re.escape(province) + r'\b', '', receiver_address)
    if zipcode:
        receiver_address = receiver_address.replace(zipcode, "")
        
    # Normalize spaces and strip
    receiver_address = re.sub(r'\s+', ' ', receiver_address).strip()
            
    return {
        'RECEIVER': receiver_name,
        'RECEIVER ADDRESS': receiver_address,
        'RECEIVER AMPHUR': amphur,
        'RECEIVER PROVINCE': province,
        'RECEIVER ZIPCODE': zipcode
    }

def parse_shipper_label(text):
    """
    Parse raw shipper info from mailing label block:
    ฝ่ายรังวัด สำนักงานที่ดินจังหวัดนครพนม สาขาเรณูนคร
    อำเภอเรณูนคร นครพนม ๔๘๑๗๐
    ที่ นพ๐๐๒๐.๐๕/๘๘๙
    """
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    shipper_name = ""
    shipper_address = ""
    ref_no = ""
    
    # Find the shipper line
    shipper_idx = -1
    for i, line in enumerate(lines):
        if "ฝ่ายรังวัด สำนักงานที่ดิน" in line or "สำนักงานที่ดิน" in line:
            shipper_idx = i
            break
            
    if shipper_idx != -1:
        raw_name = lines[shipper_idx]
        
        # Clean up shipper_name by dropping preceding garbage (like "Kที่ นพ...")
        if "ฝ่ายรังวัด สำนักงานที่ดิน" in raw_name:
            shipper_name = raw_name[raw_name.find("ฝ่ายรังวัด สำนักงานที่ดิน"):]
        elif "สำนักงานที่ดิน" in raw_name:
            shipper_name = raw_name[raw_name.find("สำนักงานที่ดิน"):]
        else:
            shipper_name = raw_name
            
        # Attempt to extract ref_no if it was merged into the shipper_name line
        ref_match = re.search(r'ที่\s*([ก-ฮa-zA-Z]+[๐-๙0-9\.\/]+)', raw_name)
        if ref_match:
            ref_no = clean_thai_digits(ref_match.group(1).strip())
            
        # Collect subsequent lines as address parts until we hit reference number or other block
        addr_parts = []
        for j in range(shipper_idx + 1, len(lines)):
            line = lines[j]
            # Stop if we hit reference number, receiver, or another major section
            if line.startswith("ที่") or line.startswith("เรียน") or line.startswith("วันที่") or "ผู้ขอรังวัด" in line or "นายช่างรังวัด" in line or "ฝ่ายรังวัด" in line or "ท.ด." in line:
                break
            addr_parts.append(line)
            
        if addr_parts:
            raw_addr = " ".join(addr_parts)
            # Clean address
            addr_conv = clean_thai_digits(raw_addr)
            # Ensure correct formatting (e.g. อ.เรณูนคร จ.นครพนม)
            addr_conv = re.sub(r'อำเภอ/เขต|อำเภอ|อ\.', 'อ.', addr_conv)
            addr_conv = re.sub(r'จังหวัด|จ\.', 'จ.', addr_conv)
            shipper_address = addr_conv
                
        # Look for reference number "ที่ ..." if not already found in raw_name
        if not ref_no:
            for line in lines[shipper_idx:]:
                if line.startswith("ที่"):
                    ref_no = clean_thai_digits(line.replace("ที่", "").strip())
                    break
                
    return {
        'SHIPPER NAME': shipper_name,
        'SHIPPER ADDRESS': shipper_address,
        'REF NO': ref_no
    }

def process_pdf(pdf_path):
    print(f"กำลังประมวลผลไฟล์: {os.path.basename(pdf_path)}...")
    reader = PdfReader(pdf_path)
    records = []
    
    # 1. Scan all pages to extract the best/most complete shipper info
    best_shipper_name = ""
    best_shipper_address = ""
    best_shipper_tel = ""
    product_in_box = ""
    
    for page in reader.pages:
        text = page.extract_text() or ""
        shipper_info = parse_shipper_label(text)
        if shipper_info:
            name = shipper_info.get('SHIPPER NAME', '')
            addr = shipper_info.get('SHIPPER ADDRESS', '')
            if len(name) > len(best_shipper_name):
                best_shipper_name = name
            if len(addr) > len(best_shipper_address):
                best_shipper_address = addr
                
        tel = extract_tel(text)
        if len(tel) > len(best_shipper_tel):
            best_shipper_tel = tel
            
        # Extract form type (e.g. (ท.ด. ๓๘) -> ท.ด. 38) if not found yet
        if not product_in_box:
            form_match = re.search(r'\(\s*(ท\s*\.\s*ด\s*\.\s*[๐-๙0-9]+)\s*\)', text)
            if form_match:
                extracted = form_match.group(1).strip()
                # Convert Thai numbers to Arabic
                extracted = extracted.translate(THAI_TO_ARABIC)
                # Clean up spaces
                product_in_box = re.sub(r'\s+', ' ', extracted)
            else:
                # Fallback to extract from "เรื่อง ..." or specific document titles
                # Use negative lookbehind (?<!รับ) to prevent matching "รับเรื่อง"
                subject_match = re.search(r'(?<!รับ)เรื่อง\s+([^\n]+)', text)
                if "หนังสือมอบเรื่องการระวังชี้แนวเขตและลงชื่อรับรองเขตที่ดิน" in text or "เรื่อง การระวังชี้แนวเขตและลงชื่อรับรองเขตที่ดิน" in text:
                    product_in_box = "-"
                elif subject_match:
                    product_in_box = subject_match.group(1).strip()
                elif "ออกโฉนดที่ดิน" in text:
                    product_in_box = "ออกโฉนดที่ดิน"
            
    # 2. Post-process the shipper info based on the rules:
    # Rule 2: "ถ้าข้อมูลที่คอลัมน์ G (SHIPPER ADDRESS) ว่าง ให้ไปเอาข้อมูลวรรคสุดท้ายของ F (SHIPPER NAME) มาใส่ และลบข้อความนั้นออกจากคอลัมน์ F"
    if not best_shipper_address and best_shipper_name:
        parts = [p.strip() for p in best_shipper_name.split() if p.strip()]
        if len(parts) > 1:
            last_part = parts[-1]
            best_shipper_address = last_part
            best_shipper_name = " ".join(parts[:-1])
            
    # Extract components from shipper address
    shipper_amphur = ""
    shipper_province = ""
    shipper_zipcode = ""
    
    if best_shipper_address:
        shipper_amphur, shipper_province, shipper_zipcode = parse_address_components(best_shipper_address)
        
    # Fallback to parse Amphur and Province from SHIPPER NAME if still missing
    # E.g. "สำนักงานที่ดินจังหวัดนครพนม สาขาเรณูนคร"
    if not shipper_amphur and best_shipper_name:
        branch_match = re.search(r'สาขา\s*([ก-ฮ]+)', best_shipper_name)
        if branch_match:
            shipper_amphur = branch_match.group(1).strip()
            
    if not shipper_province and best_shipper_name:
        prov_match = re.search(r'สำนักงานที่ดินจังหวัด\s*([ก-ฮ]+)', best_shipper_name)
        if prov_match:
            shipper_province = prov_match.group(1).strip()
            
    # Rule 1: "ถ้าเอาข้อมูลบางส่วนมาระบุที่คอลัมน์ H,I,J,K (AMPHUR, PROVINCE, ZIPCODE, TEL) แล้วให้ลบข้อความนั้นออกจากคอลัมน์ G (SHIPPER ADDRESS)"
    if best_shipper_address:
        if shipper_amphur:
            best_shipper_address = re.sub(r'(?:อำเภอ/เขต|อำเภอ|อ\.)\s*' + re.escape(shipper_amphur), '', best_shipper_address)
            best_shipper_address = re.sub(r'\b' + re.escape(shipper_amphur) + r'\b', '', best_shipper_address)
        if shipper_province:
            best_shipper_address = re.sub(r'(?:จังหวัด|จ\.)\s*' + re.escape(shipper_province), '', best_shipper_address)
            best_shipper_address = re.sub(r'\b' + re.escape(shipper_province) + r'\b', '', best_shipper_address)
        if shipper_zipcode:
            best_shipper_address = best_shipper_address.replace(str(shipper_zipcode), "")
        if best_shipper_tel:
            best_shipper_address = best_shipper_address.replace(str(best_shipper_tel), "")
            
        # Clean up spaces
        best_shipper_address = re.sub(r'\s+', ' ', best_shipper_address).strip()
        
        # User requested to keep only the first word (วรรคแรก) for the address to remove document text garbage
        if best_shipper_address:
            best_shipper_address = best_shipper_address.split()[0]
        
    # Prepare the structured shipper dict
    final_shipper_info = {
        'SHIPPER NAME': best_shipper_name,
        'SHIPPER ADDRESS': best_shipper_address,
        'SHIPPER AMPHUR': shipper_amphur,
        'SHIPPER PROVINCE': shipper_province,
        'SHIPPER ZIPCODE': shipper_zipcode,
        'SHIPPER TEL': best_shipper_tel,
        'PRODUCT IN BOX': product_in_box
    }
    
    # 3. Process each page to associate receiver details with the best shipper info
    for i in range(len(reader.pages)):
        text = reader.pages[i].extract_text() or ""
        
        # Check if page contains receiver address block (mailing label)
        if "เรียน" in text and any(char.isdigit() or char in "๐๑๒๓๔๕๖๗๘๙" for char in text):
            # Parse receiver details
            receiver_info = parse_receiver_label(text)
            if receiver_info:
                # Find REF NO (Reference Number) for this specific letter
                # Scan current page
                page_shipper = parse_shipper_label(text)
                ref_no = page_shipper.get('REF NO', '')
                
                # Fallback to preceding page if REF NO is empty
                if not ref_no and i > 0:
                    prev_text = reader.pages[i - 1].extract_text() or ""
                    prev_shipper = parse_shipper_label(prev_text)
                    ref_no = prev_shipper.get('REF NO', '')
                    
                # Combine parsed information
                record = {
                    **final_shipper_info,
                    **receiver_info,
                    'REF NO': ref_no,
                    'SOURCE_FILE': pdf_path
                }
                
                # Check for duplicates (e.g., letter body vs envelope). 
                # Overwrite the existing record because the later page (envelope) usually has a cleaner, complete address.
                is_duplicate = False
                for r_idx, r in enumerate(records):
                    if r.get('REF NO') == record.get('REF NO') and r.get('RECEIVER') == record.get('RECEIVER'):
                        records[r_idx] = record
                        is_duplicate = True
                        break
                        
                if not is_duplicate:
                    records.append(record)
                
    return records

def records_to_dataframe(all_records):
    num_records = len(all_records)
    barcodes = [] # Barcodes will be fetched later during export
            
    # Define exact columns matching the DPost template
    columns = [
        'NO', 'COMP_ORDER_ID', 'INV_NO', 'BARCODE_NO', 'PRODUCT_IN_BOX', 
        'SHIPPER_NAME', 'SHIPPER_ADDRESS', 'SHIPPER_AMPHUR', 'SHIPPER_PROVINCE', 'SHIPPER_ZIPCODE',
        'SHIPPER_TEL', 'SHIPPER_EMAIL', 'RECEIVER', 'RECEIVER_ADDRESS', 'RECEIVER_AMPHUR',
        'RECEIVER_PROVINCE', 'RECEIVER_ZIPCODE', 'RECEIVER_TEL', 'RECEIVER_EMAIL',
        'WEIGHT', 'PRICE', 'INSURE', 'INSURE_PRICE', 'COD_DETAIL_NAME', 'COD_DETAIL_SIZE',
        'COD_DETAIL_VOLUME', 'COD_DETAIL_QTY', 'COD_DETAIL_COLOR', 'COD_DETAIL_QTY_AMOUNT',
        'PROVE_OF_PAYMENT', 'IS_CONSENT', 'SOURCE_FILE'
    ]
    
    rows = []
    for idx, rec in enumerate(all_records, 1):
        row_data = {col: "" for col in columns}
        row_data['NO'] = idx
        inv_no = rec.get('REF NO', '')
        row_data['INV_NO'] = inv_no
        
        # Extract the part after "/" for COMP_ORDER_ID
        comp_order_id = ""
        if "/" in inv_no:
            comp_order_id = inv_no.split("/")[-1].strip()
        row_data['COMP_ORDER_ID'] = comp_order_id
        
        # Assign barcode if available
        if idx - 1 < len(barcodes):
            row_data['BARCODE_NO'] = barcodes[idx - 1]
        else:
            row_data['BARCODE_NO'] = ""
            
        product_in_box = rec.get('PRODUCT IN BOX', '').strip()
        row_data['PRODUCT_IN_BOX'] = product_in_box if product_in_box else "-"
        
        row_data['SHIPPER_NAME'] = rec.get('SHIPPER NAME', '')
        shipper_address = rec.get('SHIPPER ADDRESS', '').strip()
        row_data['SHIPPER_ADDRESS'] = shipper_address if shipper_address else "-"
        row_data['SHIPPER_AMPHUR'] = rec.get('SHIPPER AMPHUR', '')
        row_data['SHIPPER_PROVINCE'] = rec.get('SHIPPER PROVINCE', '')
        row_data['SHIPPER_ZIPCODE'] = rec.get('SHIPPER ZIPCODE', '')
        shipper_tel = rec.get('SHIPPER TEL', '').strip()
        row_data['SHIPPER_TEL'] = shipper_tel if shipper_tel else "-"
        row_data['SHIPPER_EMAIL'] = ""
        
        row_data['RECEIVER'] = rec.get('RECEIVER', '')
        row_data['RECEIVER_ADDRESS'] = rec.get('RECEIVER ADDRESS', '')
        row_data['RECEIVER_AMPHUR'] = rec.get('RECEIVER AMPHUR', '')
        row_data['RECEIVER_PROVINCE'] = rec.get('RECEIVER PROVINCE', '')
        row_data['RECEIVER_ZIPCODE'] = rec.get('RECEIVER ZIPCODE', '')
        row_data['RECEIVER_TEL'] = "0000000000"
        row_data['RECEIVER_EMAIL'] = ""
        
        row_data['WEIGHT'] = "10"
        row_data['PRICE'] = "0"
        row_data['INSURE'] = "N"
        row_data['INSURE_PRICE'] = "0"
        row_data['COD_DETAIL_NAME'] = ""
        row_data['COD_DETAIL_SIZE'] = ""
        row_data['COD_DETAIL_VOLUME'] = ""
        row_data['COD_DETAIL_QTY'] = ""
        row_data['COD_DETAIL_COLOR'] = ""
        row_data['COD_DETAIL_QTY_AMOUNT'] = ""
        row_data['PROVE_OF_PAYMENT'] = ""
        row_data['IS_CONSENT'] = ""
        row_data['SOURCE_FILE'] = rec.get('SOURCE_FILE', '')
        rows.append(row_data)
        
    return pd.DataFrame(rows, columns=columns)

def generate_combined_pdf(dataframe, output_pdf_path, envelope_only=False):
    writer = PdfWriter()
    
    processed_files = set()
    
    for idx, row in dataframe.iterrows():
        source_file = row.get('SOURCE_FILE', '')
        if not source_file or not os.path.exists(source_file) or source_file in processed_files:
            continue
            
        processed_files.add(source_file)
        
        # Get all records for this file in original order
        file_records = dataframe[dataframe['SOURCE_FILE'] == source_file].to_dict('records')
        
        reader = PdfReader(source_file)
        if not reader.pages:
            continue
            
        current_record_idx = 0
                
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            clean_text = text.replace(" ", "")
            
            is_envelope = "ชำระค่าฝากส่งเป็นรายเดือน" in clean_text or "ใบอนุญาตเลขที่" in clean_text
            is_last_page = (i == len(reader.pages) - 1)
            
            has_overlay = False
            if (is_envelope or is_last_page) and current_record_idx < len(file_records):
                barcode_no = file_records[current_record_idx].get('BARCODE_NO', '')
                
                if barcode_no and str(barcode_no).strip() != "":
                    width = float(page.mediabox.width)
                    height = float(page.mediabox.height)
                
                # Find X and Y coordinate of "เรียน"
                y_coord_rian = None
                x_coord_rian = None
                def visitor_body(text_content, cm, tm, font_dict, font_size):
                    nonlocal y_coord_rian, x_coord_rian
                    # Find the first occurrence of "เรียน"
                    if "เรียน" in text_content and y_coord_rian is None:
                        x_coord_rian = tm[4]
                        y_coord_rian = tm[5]
                page.extract_text(visitor_text=visitor_body)
                
                packet = io.BytesIO()
                c = canvas.Canvas(packet, pagesize=(width, height))
                
                # Scale factor to make overlay smaller
                scale = 0.8

                if y_coord_rian is not None and x_coord_rian is not None:
                    # Position dynamically relative to "เรียน"
                    # Align the bottom edge of the e-AR box with the baseline of the "เรียน" text
                    # The e-AR box bottom is at base_y + (155 * scale)
                    # So base_y = y_coord_rian - (155 * scale)
                    base_y = y_coord_rian - (155 * scale)
                    
                    # Position horizontally to the left of "เรียน" making it closer (5pt gap)
                    # Right edge of barcode is base_x + (164.7 * scale)
                    base_x = x_coord_rian - 5 - (164.7 * scale)
                    
                    # Prevent going off-screen to the left or bottom
                    base_x = max(10, base_x)
                    base_y = max(10, base_y)
                else:
                    # Fallback to old default if "เรียน" is not found
                    base_x = width * 0.05
                    base_y = 40
                
                # Draw Barcode (Code128)
                barcode128 = code128.Code128(str(barcode_no), barHeight=20.625 * scale, barWidth=0.825 * scale)
                barcode128.drawOn(c, base_x, base_y + (40 * scale))
                
                # Get actual width for perfect centering
                barcode_width = getattr(barcode128, 'width', 164.7 * scale)
                center_x = base_x + (barcode_width / 2.0)
                
                # Draw text centered under barcode
                c.setFont("Helvetica-Bold", 14 * scale)
                c.drawCentredString(center_x, base_y + (20 * scale), str(barcode_no))
                
                # Draw QR Code centered above barcode
                qr_code = qr.QrCodeWidget(str(barcode_no))
                bounds = qr_code.getBounds()
                qr_width = bounds[2] - bounds[0]
                qr_height = bounds[3] - bounds[1]
                
                # Scale QR code
                qr_size = 75.0 * scale
                scale_w = qr_size / qr_width
                scale_h = qr_size / qr_height
                d = Drawing(qr_size, qr_size, transform=[scale_w, 0, 0, scale_h, 0, 0])
                d.add(qr_code)
                # Centered, Y: above barcode
                renderPDF.draw(d, c, center_x - (qr_size / 2.0), base_y + (65 * scale))
                
                # --- Draw E-AR Box above QR Code ---
                box_w = 120 * scale
                box_h = 55 * scale
                box_x = center_x - (box_w / 2.0)
                box_y = base_y + (155 * scale)
                
                c.setStrokeColorRGB(0, 0, 0) # Black border
                c.setLineWidth(1)
                c.setFillColorRGB(1, 1, 1) # White fill
                c.rect(box_x, box_y, box_w, box_h, fill=1, stroke=1)
                
                c.setFillColorRGB(0, 0, 0)
                if FONT_REGISTERED:
                    c.setFont('Tahoma-Bold', 24 * scale)
                else:
                    c.setFont('Helvetica-Bold', 24 * scale)
                c.drawCentredString(center_x, box_y + (31 * scale), "e-AR")
                
                if FONT_REGISTERED:
                    c.setFont('Tahoma', max(7.5, 9 * scale))
                else:
                    c.setFont('Helvetica', max(7.5, 9 * scale))
                c.drawCentredString(center_x, box_y + (19 * scale), "ลงทะเบียนตอบรับ")
                c.drawCentredString(center_x, box_y + (9 * scale), "ทางอิเล็กทรอนิกส์")
                # -----------------------------------
                
                c.save()
                packet.seek(0)
                
                overlay_pdf = PdfReader(packet)
                page.merge_page(overlay_pdf.pages[0])
                
                has_overlay = True
                current_record_idx += 1
                
            if envelope_only:
                if has_overlay:
                    if y_coord_rian is not None:
                        # Adjust top crop to just above the Garuda logo (around 140 pts above "เรียน")
                        page.mediabox.top = y_coord_rian + 145
                        page.mediabox.bottom = max(0, y_coord_rian - 145)
                        page.cropbox.top = page.mediabox.top
                        page.cropbox.bottom = page.mediabox.bottom
                    writer.add_page(page)
            else:
                writer.add_page(page)
        
    with open(output_pdf_path, "wb") as f_out:
        writer.write(f_out)

def generate_delivery_note_pdf(dataframe, output_pdf_path):
    if dataframe.empty:
        return
        
    doc = SimpleDocTemplate(output_pdf_path, pagesize=portrait(A4),
                            rightMargin=1.5*cm, leftMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    elements = []
    
    styles = getSampleStyleSheet()
    font_name = 'Tahoma' if FONT_REGISTERED else 'Helvetica'
    font_bold = 'Tahoma-Bold' if FONT_REGISTERED else 'Helvetica-Bold'
    
    style_normal = ParagraphStyle('ThaiNormal', parent=styles['Normal'], fontName=font_name, fontSize=10, leading=14)
    style_bold_center = ParagraphStyle('ThaiBoldCenter', parent=styles['Normal'], fontName=font_bold, fontSize=16, alignment=TA_CENTER)
    style_right = ParagraphStyle('ThaiRight', parent=styles['Normal'], fontName=font_name, fontSize=10, alignment=TA_RIGHT, leading=24)
    style_table_header = ParagraphStyle('ThaiTableHeader', parent=styles['Normal'], fontName=font_bold, fontSize=10, alignment=TA_CENTER)
    style_table_cell_left = ParagraphStyle('ThaiTableCellL', parent=styles['Normal'], fontName=font_name, fontSize=9, leading=12)
    style_table_cell_center = ParagraphStyle('ThaiTableCellC', parent=styles['Normal'], fontName=font_name, fontSize=9, leading=12, alignment=TA_CENTER)
    style_footer_center = ParagraphStyle('ThaiFooterCenter', parent=styles['Normal'], fontName=font_name, fontSize=10, leading=24, alignment=TA_CENTER)
    
    # Get shipper info from the first row
    first_row = dataframe.iloc[0]
    shipper_name = apply_thai_pua(str(first_row.get('SHIPPER_NAME', '')))
    shipper_addr = apply_thai_pua(str(first_row.get('SHIPPER_ADDRESS', '')))
    shipper_amphur = apply_thai_pua(str(first_row.get('SHIPPER_AMPHUR', '')))
    shipper_prov = apply_thai_pua(str(first_row.get('SHIPPER_PROVINCE', '')))
    shipper_zip = str(first_row.get('SHIPPER_ZIPCODE', ''))
    shipper_tel = str(first_row.get('SHIPPER_TEL', ''))
    
    shipper_full_address = f"{shipper_addr} {shipper_amphur} {shipper_prov} {shipper_zip}".strip()
    shipper_text = f"<b>{apply_thai_pua('ผู้ส่ง:')}</b> {shipper_name}<br/><b>{apply_thai_pua('ที่อยู่:')}</b> {shipper_full_address}<br/><b>{apply_thai_pua('โทร:')}</b> {shipper_tel}"
    
    p_shipper = Paragraph(shipper_text, style_normal)
    p_title = Paragraph(apply_thai_pua('ใบนำส่ง'), style_bold_center)
    p_license = Paragraph(apply_thai_pua('ใบอนุญาตเลขที่............................................<br/>ปณ./ปจ. ............................................'), style_right)
    
    # Shipper and License row (2 columns)
    header_data = [[p_shipper, p_license]]
    header_table = Table(header_data, colWidths=[9*cm, 9*cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (0,0), (0,0), 'LEFT'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
    ]))
    
    # Table Data (wrapping header inside to repeat on every page)
    main_table_data = []
    
    # Row 0: Title on top (spans all columns)
    main_table_data.append([p_title, '', '', '', '', ''])
    
    # Row 1: Header table (spans all columns)
    main_table_data.append([header_table, '', '', '', '', ''])
    
    # Row 2: Spacer row
    main_table_data.append(['', '', '', '', '', ''])
    
    # Row 3: Column Headers
    main_table_data.append([
        Paragraph(apply_thai_pua('ลำดับ'), style_table_header),
        Paragraph(apply_thai_pua('หมายเลข'), style_table_header),
        Paragraph(apply_thai_pua('ผู้รับ'), style_table_header),
        Paragraph(apply_thai_pua('ที่อยู่'), style_table_header),
        Paragraph(apply_thai_pua('น้ำหนัก'), style_table_header),
        Paragraph(apply_thai_pua('ค่าบริการ'), style_table_header)
    ])
    
    for idx, row in dataframe.iterrows():
        no = str(row.get('NO', idx + 1))
        barcode = str(row.get('BARCODE_NO', ''))
        receiver = apply_thai_pua(str(row.get('RECEIVER', '')))
        
        r_addr = apply_thai_pua(str(row.get('RECEIVER_ADDRESS', '')))
        r_amphur = apply_thai_pua(str(row.get('RECEIVER_AMPHUR', '')))
        r_prov = apply_thai_pua(str(row.get('RECEIVER_PROVINCE', '')))
        r_zip = str(row.get('RECEIVER_ZIPCODE', ''))
        
        # Use <br/> to break line before Amphur
        addr_line1 = r_addr.strip()
        addr_line2 = f"{r_amphur} {r_prov} {r_zip}".strip()
        full_r_addr = f"{addr_line1}<br/>{addr_line2}" if addr_line1 and addr_line2 else f"{addr_line1}{addr_line2}"
        
        weight = str(row.get('WEIGHT', ''))
        
        main_table_data.append([
            Paragraph(no, style_table_cell_center),
            Paragraph(barcode, style_table_cell_center),
            Paragraph(receiver, style_table_cell_left),
            Paragraph(full_r_addr, style_table_cell_left),
            Paragraph(weight, style_table_cell_center),
            Paragraph('', style_table_cell_center) # Empty for service fee
        ])
        
    # Adjusted column widths to prevent header text wrapping
    # [ลำดับ 1.5, หมายเลข 3.0, ผู้รับ 4.0, ที่อยู่ 5.8, น้ำหนัก 1.7, ค่าบริการ 2.0] = Total 18.0cm
    t = Table(main_table_data, colWidths=[1.5*cm, 3.0*cm, 4.0*cm, 5.8*cm, 1.7*cm, 2.0*cm], repeatRows=4)
    t.setStyle(TableStyle([
        # Header spans
        ('SPAN', (0,0), (-1,0)),
        ('SPAN', (0,1), (-1,1)),
        ('SPAN', (0,2), (-1,2)),
        
        ('LEFTPADDING', (0,0), (-1,2), 0),
        ('RIGHTPADDING', (0,0), (-1,2), 0),
        ('BOTTOMPADDING', (0,0), (-1,0), 15), # Space under title
        ('BOTTOMPADDING', (0,1), (-1,1), 10), # Space after header table
        
        # Grid and Background only for data rows and col headers
        ('BACKGROUND', (0,3), (-1,3), colors.lightgrey),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
        ('ALIGN', (0,3), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,3), (-1,-1), 0.5, colors.black),
        ('BOTTOMPADDING', (0,3), (-1,-1), 4),
        ('TOPPADDING', (0,3), (-1,-1), 4),
        ('LEFTPADDING', (0,3), (-1,-1), 2),  # Reduce left padding in cells
        ('RIGHTPADDING', (0,3), (-1,-1), 2), # Reduce right padding in cells
    ]))
    
    elements.append(t)
    elements.append(Spacer(1, 1*cm))
    
    # Footer
    footer_text_left = apply_thai_pua('<br/><br/>ลงชื่อผู้ส่ง ..............................................................<br/>( .............................................................. )<br/>วันที่.............................................')
    footer_text_right = apply_thai_pua('<br/><br/>ลงชื่อผู้รับ ..............................................................<br/>( .............................................................. )<br/>วันที่.............................................')
    
    p_footer_l = Paragraph(footer_text_left, style_footer_center)
    p_footer_r = Paragraph(footer_text_right, style_footer_center)
    
    footer_data = [[p_footer_l, p_footer_r]]
    footer_table = Table(footer_data, colWidths=[9*cm, 9*cm])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (0,0), (0,0), 'CENTER'),
        ('ALIGN', (1,0), (1,0), 'CENTER'),
    ]))
    
    elements.append(footer_table)
    
    def draw_page_number(canvas, doc):
        canvas.saveState()
        if FONT_REGISTERED:
            canvas.setFont('Tahoma', 9)
        else:
            canvas.setFont('Helvetica', 9)
        canvas.drawRightString(19.5*cm, 28.5*cm, apply_thai_pua(f"หน้า {doc.page}"))
        canvas.restoreState()
        
    doc.build(elements, onFirstPage=draw_page_number, onLaterPages=draw_page_number)

def generate_custom_envelopes_pdf(dataframe, output_pdf_path):
    if dataframe.empty:
        return
        
    writer = PdfWriter()
    
    # DL Size is 220x110 mm
    
    for idx, row in dataframe.iterrows():
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(220*mm, 110*mm))
        
        font_normal = 'Tahoma' if FONT_REGISTERED else 'Helvetica'
        font_bold = 'Tahoma-Bold' if FONT_REGISTERED else 'Helvetica-Bold'
        
        c.setFont(font_normal, 10)
        base_y_sender = 90 * mm
        
        # --- Top Left (Sender) ---
        shipper_name = str(row.get('SHIPPER_NAME', '')).replace('None', '')
        shipper_address = str(row.get('SHIPPER_ADDRESS', '')).replace('None', '')
        shipper_amphur = str(row.get('SHIPPER_AMPHUR', '')).replace('None', '')
        shipper_province = str(row.get('SHIPPER_PROVINCE', '')).replace('None', '')
        shipper_zipcode = str(row.get('SHIPPER_ZIPCODE', '')).replace('None', '')
        ref_no = str(row.get('INV_NO', '')).replace('None', '')
        
        c.drawString(30 * mm, base_y_sender, shipper_name)
        c.drawString(30 * mm, base_y_sender - 5*mm, f"อำเภอ{shipper_amphur} {shipper_province} {shipper_zipcode}".strip())
        if ref_no:
            c.drawString(30 * mm, base_y_sender - 10*mm, f"ที่ {ref_no}")
        
        # --- Top Right ---
        c.drawString(160 * mm, base_y_sender, "ชำระค่าฝากส่งเป็นรายเดือน")
        c.drawString(160 * mm, base_y_sender - 5*mm, "ใบอนุญาตเลขที่")
        if shipper_amphur:
            c.drawString(160 * mm, base_y_sender - 10*mm, f"ไปรษณีย์{shipper_amphur}")
        
        # --- Center (Receiver) ---
        c.setFont(font_normal, 12)
        base_x_receiver = 80 * mm
        base_y_receiver = 60 * mm
        
        receiver = str(row.get('RECEIVER', '')).replace('None', '')
        receiver_address = str(row.get('RECEIVER_ADDRESS', '')).replace('None', '')
        receiver_amphur = str(row.get('RECEIVER_AMPHUR', '')).replace('None', '')
        receiver_province = str(row.get('RECEIVER_PROVINCE', '')).replace('None', '')
        receiver_zipcode = str(row.get('RECEIVER_ZIPCODE', '')).replace('None', '')
        
        c.drawString(base_x_receiver - 10*mm, base_y_receiver, "เรียน")
        c.drawString(base_x_receiver, base_y_receiver, receiver)
        
        # Draw address lines
        current_y = base_y_receiver - 6*mm
        if receiver_address:
            # Try to split long address into 2 lines if possible
            if len(receiver_address) > 40:
                parts = receiver_address.split(' ต.')
                if len(parts) > 1:
                    c.drawString(base_x_receiver, current_y, parts[0])
                    current_y -= 6*mm
                    c.drawString(base_x_receiver, current_y, f"ต.{parts[1]}")
                else:
                    c.drawString(base_x_receiver, current_y, receiver_address)
            else:
                c.drawString(base_x_receiver, current_y, receiver_address)
            current_y -= 6*mm
            
        if receiver_amphur:
            c.drawString(base_x_receiver, current_y, f"อำเภอ/เขต {receiver_amphur}")
            current_y -= 6*mm
            
        if receiver_province:
            c.drawString(base_x_receiver, current_y, f"จังหวัด {receiver_province}")
            current_y -= 6*mm
            
        if receiver_zipcode:
            c.drawString(base_x_receiver, current_y, receiver_zipcode)
            
        # --- Overlay (Barcode & QR) ---
        barcode_no = str(row.get('BARCODE_NO', '')).replace('None', '').strip()
        if barcode_no:
            scale = 0.8
            # Position it to the left of "เรียน"
            x_coord_rian = base_x_receiver - 10*mm
            y_coord_rian = base_y_receiver
            
            base_y = y_coord_rian - (155 * scale)
            base_x = x_coord_rian - 5 - (164.7 * scale)
            
            barcode128 = code128.Code128(barcode_no, barHeight=20.625 * scale, barWidth=0.825 * scale)
            barcode128.drawOn(c, base_x, base_y + (40 * scale))
            
            barcode_width = getattr(barcode128, 'width', 164.7 * scale)
            center_x = base_x + (barcode_width / 2.0)
            
            c.setFont(font_bold, 14 * scale)
            c.drawCentredString(center_x, base_y + (20 * scale), barcode_no)
            
            qr_code = qr.QrCodeWidget(barcode_no)
            bounds = qr_code.getBounds()
            qr_size = 75.0 * scale
            scale_w = qr_size / (bounds[2] - bounds[0])
            scale_h = qr_size / (bounds[3] - bounds[1])
            d = Drawing(qr_size, qr_size, transform=[scale_w, 0, 0, scale_h, 0, 0])
            d.add(qr_code)
            renderPDF.draw(d, c, center_x - (qr_size / 2.0), base_y + (65 * scale))
            
            box_w = 120 * scale
            box_h = 55 * scale
            box_x = center_x - (box_w / 2.0)
            box_y = base_y + (155 * scale)
            
            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(1)
            c.setFillColorRGB(1, 1, 1)
            c.rect(box_x, box_y, box_w, box_h, fill=1, stroke=1)
            
            c.setFillColorRGB(0, 0, 0)
            c.setFont(font_bold, 24 * scale)
            c.drawCentredString(center_x, box_y + (31 * scale), "e-AR")
            c.setFont(font_normal, max(7.5, 9 * scale))
            c.drawCentredString(center_x, box_y + (19 * scale), "ลงทะเบียนตอบรับ")
            c.drawCentredString(center_x, box_y + (9 * scale), "ทางอิเล็กทรอนิกส์")
            
        c.save()
        packet.seek(0)
        
        new_page_pdf = PdfReader(packet)
        writer.add_page(new_page_pdf.pages[0])
        
    with open(output_pdf_path, "wb") as f_out:
        writer.write(f_out)

def main():
    print(f"โปรแกรมแปลงข้อมูล DPost (Version {__version__})")
    # Find all PDFs in the current directory
    pdf_files = glob.glob("*.pdf")
    if not pdf_files:
        print("ไม่พบไฟล์ PDF ในโฟลเดอร์นี้ กรุณาใส่ไฟล์ PDF ที่ต้องการแปลงข้อมูล")
        return
        
    all_records = []
    for pdf_file in pdf_files:
        records = process_pdf(pdf_file)
        all_records.extend(records)
        
    if not all_records:
        print("ไม่สามารถสกัดข้อมูลจากไฟล์ PDF ได้")
        return
        
    # Create DataFrame using extracted function
    df = records_to_dataframe(all_records)
        
    # Output file path with current datetime suffix (YYYYMMDDHHMM)
    from datetime import datetime
    suffix = datetime.now().strftime("%Y%m%d%H%M")
    output_filename = f"dpost_import_{suffix}.xlsx"
    
    # Save with sheet_name="New Order Data"
    df.to_excel(output_filename, sheet_name="New Order Data", index=False)
    print(f"\nบันทึกข้อมูลเรียบร้อยแล้วลงไฟล์ Excel: {output_filename}")
    print(f"รวมข้อมูลทั้งหมด {len(df)} รายการ")

if __name__ == "__main__":
    main()
