lines = open('gui_perfect.py', encoding='utf-8').read()
lines = lines.replace('ctk.CTkLabel(header_inner, text=f\x22{len(dup_rows)} รายการ\x22,\\n\\n        header.pack(fill=\'x\')', 'ctk.CTkLabel(header_inner, text=f\x22{len(dup_rows)} รายการ\x22, font=(\x22Segoe UI\x22, 12), text_color=\x22#fed7aa\x22).pack(side=\'right\')\\n\\n        header.pack(fill=\'x\')')
open('gui_perfect.py', 'w', encoding='utf-8').write(lines)
