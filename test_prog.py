import customtkinter as ctk

app = ctk.CTk()
f = ctk.CTkFrame(app, fg_color='#f1f5f9', border_width=1, border_color='#cbd5e1', corner_radius=8)
f.pack(padx=20, pady=20, fill='x', expand=True)

p = ctk.CTkProgressBar(f, progress_color='#bbf7d0', fg_color='#f1f5f9', corner_radius=7, height=36)
p.pack(fill='both', expand=True, padx=2, pady=2)
p.set(0)
app.update()

def update_p(val):
    p.set(val)
    # The text is drawn directly onto the progress bar's internal canvas AFTER set()
    p._canvas.create_text(
        p.winfo_width()/2, p.winfo_height()/2, 
        text=f'{int(val*100)}%', 
        fill='#15803D', font=('Segoe UI', 12, 'bold')
    )
    if val < 1:
        app.after(100, update_p, val+0.05)
    else:
        app.after(1000, app.destroy)

update_p(0.05)
app.mainloop()
