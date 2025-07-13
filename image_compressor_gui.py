import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from PIL import Image

# --- Core Compression Logic (adapted from the CLI script) ---

def get_file_size(file_path):
    size_bytes = os.path.getsize(file_path)
    if size_bytes == 0: return "0 B"
    size_name = ("B", "KB", "MB", "GB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

def compress_image_worker(args_tuple):
    input_path, output_dir, quality, use_webp, webp_method, resize_percentage, max_dimension, strip_exif = args_tuple
    
    base_name = os.path.basename(input_path)
    output_ext = '.webp' if use_webp else '.png'
    output_path = os.path.join(output_dir, os.path.splitext(base_name)[0] + output_ext)

    try:
        img = Image.open(input_path)

        if strip_exif and hasattr(img, 'info'):
            img_data = list(img.getdata())
            new_img = Image.new(img.mode, img.size)
            new_img.putdata(img_data)
            img = new_img

        if resize_percentage and resize_percentage < 100:
            w, h = img.size
            nw, nh = int(w * resize_percentage / 100), int(h * resize_percentage / 100)
            img = img.resize((nw, nh), Image.Resampling.LANCZOS)
        elif max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        save_params = {'optimize': True}
        if use_webp:
            save_params.update({'quality': quality, 'method': webp_method})
            img.save(output_path, 'webp', **save_params)
        else:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img = img.quantize(colors=256, method=Image.Quantize.LIBIMAGEQUANT, dither=Image.Dither.NONE)
            img.save(output_path, 'png', **save_params)
            
        return f"SUCCESS: {base_name} -> {os.path.basename(output_path)}"
    except Exception as e:
        return f"ERROR: Compressing {base_name}: {e}"

# --- GUI Application Class ---

class ImageCompressorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Smart Image Compressor")
        self.geometry("800x600")

        self.file_list = []

        # --- Main Layout ---
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        right_frame = ttk.Frame(main_frame, width=250)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        right_frame.pack_propagate(False)

        # --- Left Frame: File List and Log ---
        self.setup_file_list_ui(left_frame)
        self.setup_log_ui(left_frame)

        # --- Right Frame: Controls ---
        self.setup_controls_ui(right_frame)

    def setup_file_list_ui(self, parent):
        frame = ttk.LabelFrame(parent, text="Files to Compress")
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.listbox = tk.Listbox(frame)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)

        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(button_frame, text="Add Files", command=self.add_files).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,5))
        ttk.Button(button_frame, text="Add Folder", command=self.add_folder).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,5))
        ttk.Button(button_frame, text="Clear List", command=self.clear_list).pack(side=tk.LEFT, expand=True, fill=tk.X)

    def setup_log_ui(self, parent):
        frame = ttk.LabelFrame(parent, text="Log")
        frame.pack(fill=tk.BOTH, expand=True, ipady=5)
        self.log_text = tk.Text(frame, height=10, state='disabled', wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def setup_controls_ui(self, parent):
        # WebP Options
        webp_frame = ttk.LabelFrame(parent, text="Format")
        webp_frame.pack(fill=tk.X, pady=5)
        self.use_webp = tk.BooleanVar(value=True)
        ttk.Checkbutton(webp_frame, text="Use WebP", variable=self.use_webp, command=self.toggle_webp_options).pack(anchor='w', padx=5)
        
        # Quality
        self.quality = tk.IntVar(value=85)
        ttk.Label(webp_frame, text="Quality (WebP Only):").pack(anchor='w', padx=5, pady=(5,0))
        self.quality_scale = ttk.Scale(webp_frame, from_=1, to=100, orient=tk.HORIZONTAL, variable=self.quality)
        self.quality_scale.pack(fill=tk.X, padx=5)

        # WebP Method
        self.webp_method = tk.IntVar(value=4)
        ttk.Label(webp_frame, text="Method (WebP Only):").pack(anchor='w', padx=5, pady=(5,0))
        self.webp_method_scale = ttk.Scale(webp_frame, from_=0, to=6, orient=tk.HORIZONTAL, variable=self.webp_method)
        self.webp_method_scale.pack(fill=tk.X, padx=5, pady=(0,5))

        # Resizing Options
        resize_frame = ttk.LabelFrame(parent, text="Resizing")
        resize_frame.pack(fill=tk.X, pady=5)
        self.resize_mode = tk.StringVar(value="none")
        ttk.Radiobutton(resize_frame, text="None", variable=self.resize_mode, value="none").pack(anchor='w')
        
        self.resize_pct_var = tk.IntVar(value=50)
        pct_frame = ttk.Frame(resize_frame)
        pct_frame.pack(fill=tk.X)
        ttk.Radiobutton(pct_frame, text="Resize to", variable=self.resize_mode, value="pct").pack(side=tk.LEFT)
        ttk.Entry(pct_frame, textvariable=self.resize_pct_var, width=4).pack(side=tk.LEFT)
        ttk.Label(pct_frame, text="%").pack(side=tk.LEFT)

        self.max_dim_var = tk.IntVar(value=1920)
        dim_frame = ttk.Frame(resize_frame)
        dim_frame.pack(fill=tk.X)
        ttk.Radiobutton(dim_frame, text="Max Dim.", variable=self.resize_mode, value="dim").pack(side=tk.LEFT)
        ttk.Entry(dim_frame, textvariable=self.max_dim_var, width=6).pack(side=tk.LEFT)
        ttk.Label(dim_frame, text="px").pack(side=tk.LEFT)

        # Other Options
        misc_frame = ttk.LabelFrame(parent, text="Misc")
        misc_frame.pack(fill=tk.X, pady=5)
        self.strip_exif = tk.BooleanVar(value=True)
        ttk.Checkbutton(misc_frame, text="Strip EXIF Data", variable=self.strip_exif).pack(anchor='w', padx=5)

        # Action Button
        self.progress = ttk.Progressbar(parent, orient='horizontal', mode='determinate')
        self.progress.pack(fill=tk.X, pady=(10, 5))
        
        ttk.Button(parent, text="Start Compression", command=self.start_compression_thread, style="Accent.TButton").pack(fill=tk.X, ipady=10)
        style = ttk.Style(self)
        style.configure("Accent.TButton", foreground="white", background="blue")

    def toggle_webp_options(self):
        state = 'normal' if self.use_webp.get() else 'disabled'
        self.quality_scale.config(state=state)
        self.webp_method_scale.config(state=state)

    def add_files(self):
        files = filedialog.askopenfilenames(title="Select Image Files", filetypes=[("Image Files", "*.png *.jpg *.jpeg *.ppm"), ("All files", "*.*")])
        for f in files:
            if f not in self.file_list:
                self.file_list.append(f)
                self.listbox.insert(tk.END, os.path.basename(f))

    def add_folder(self):
        folder = filedialog.askdirectory(title="Select Folder Containing Images")
        if not folder: return
        for filename in os.listdir(folder):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.ppm')):
                full_path = os.path.join(folder, filename)
                if full_path not in self.file_list:
                    self.file_list.append(full_path)
                    self.listbox.insert(tk.END, filename)

    def clear_list(self):
        self.file_list.clear()
        self.listbox.delete(0, tk.END)

    def log(self, message):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.config(state='disabled')
        self.log_text.see(tk.END)

    def start_compression_thread(self):
        if not self.file_list:
            messagebox.showerror("Error", "No files selected for compression.")
            return
        
        output_dir = filedialog.askdirectory(title="Select Output Folder")
        if not output_dir:
            return

        # Start the compression in a new thread to avoid freezing the GUI
        thread = threading.Thread(target=self.run_compression, args=(output_dir,))
        thread.daemon = True
        thread.start()

    def run_compression(self, output_dir):
        self.progress['value'] = 0
        self.progress['maximum'] = len(self.file_list)
        self.log("Starting compression...")

        resize_pct = self.resize_pct_var.get() if self.resize_mode.get() == 'pct' else None
        max_dim = self.max_dim_var.get() if self.resize_mode.get() == 'dim' else None

        tasks = [(f, output_dir, self.quality.get(), self.use_webp.get(), self.webp_method.get(), resize_pct, max_dim, self.strip_exif.get()) for f in self.file_list]

        with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
            for i, result in enumerate(executor.map(compress_image_worker, tasks)):
                self.log(result)
                self.progress['value'] = i + 1
                self.update_idletasks()
        
        self.log("--- Compression Complete ---")
        messagebox.showinfo("Success", "All images have been processed.")

if __name__ == "__main__":
    import math
    app = ImageCompressorApp()
    app.mainloop()
