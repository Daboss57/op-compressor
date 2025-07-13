
import os
import argparse
from PIL import Image
from tkinter import Tk, filedialog
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

def get_file_size(file_path):
    """Returns the file size in a human-readable format (KB or MB)."""
    size_bytes = os.path.getsize(file_path)
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"

def compress_image(args_tuple):
    """Worker function to compress a single image. Designed for parallel processing."""
    input_path, output_path, quality, use_webp, webp_method, resize_percentage, max_dimension, strip_exif, dither = args_tuple

    if not input_path or not os.path.exists(input_path):
        print(f"Skipping missing file: {input_path}")
        return None

    try:
        original_size = get_file_size(input_path)
        img = Image.open(input_path)

        # --- 1. Strip EXIF Data ---
        if strip_exif and hasattr(img, 'info'):
            img_data = list(img.getdata())
            new_img = Image.new(img.mode, img.size)
            new_img.putdata(img_data)
            img = new_img

        # --- 2. Image Resizing ---
        if resize_percentage:
            width, height = img.size
            new_width = int(width * resize_percentage / 100)
            new_height = int(height * resize_percentage / 100)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        elif max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # --- 3. Smart Compression Logic ---
        save_params = {'optimize': True}
        if use_webp:
            save_params['quality'] = quality
            save_params['method'] = webp_method
            img.save(output_path, 'webp', **save_params)
        else:
            if img.mode == 'RGBA' or 'transparency' in img.info:
                img = img.quantize(colors=256, method=Image.Quantize.LIBIMAGEQUANT, dither=dither)
            else:
                img = img.convert('RGB').quantize(colors=256, method=Image.Quantize.LIBIMAGEQUANT, dither=dither)
            img.save(output_path, **save_params)

        compressed_size = get_file_size(output_path)
        return f"  - Input: {os.path.basename(input_path)} ({original_size}) -> Output: {os.path.basename(output_path)} ({compressed_size})"

    except Exception as e:
        return f"Error compressing {os.path.basename(input_path)}: {e}"

def main():
    parser = argparse.ArgumentParser(description="An advanced image compressor with resizing, EXIF stripping, and parallel processing.")
    
    # File I/O Arguments
    parser.add_argument("-i", "--input", help="Input image file or directory. Opens a dialog if omitted.")
    parser.add_argument("-o", "--output", help="Output file or directory. Opens a dialog if omitted.")

    # Compression Arguments
    parser.add_argument("-q", "--quality", type=int, default=85, help="Compression quality for WebP (1-100). Default: 85.")
    parser.add_argument("--no-webp", action="store_true", help="Disable WebP and use PNG quantization instead.")
    parser.add_argument("--webp-method", type=int, default=4, choices=range(0, 7), help="WebP method (0-6). Higher is slower but smaller. Default: 4.")

    # Resizing Arguments
    parser.add_argument("--resize", type=int, metavar='PCT', help="Resize image to a percentage of original size.")
    parser.add_argument("--max-dim", type=int, metavar='PIXELS', help="Set a maximum width or height for the image.")

    # Other Arguments
    parser.add_argument("--strip-exif", action="store_true", help="Remove EXIF data from images.")
    parser.add_argument("--no-parallel", action="store_true", help="Disable parallel processing for directories.")

    args = parser.parse_args()

    # --- Handle GUI File Pickers ---
    input_path = args.input
    output_path = args.output
    if not input_path:
        root = Tk()
        root.withdraw()
        
        choice = ''
        while choice not in ['f', 'd']:
            choice = input("What do you want to compress? (f = single file, d = directory): ").lower()

        if choice == 'f':
            print("Please select an image file to compress...")
            input_path = filedialog.askopenfilename(
                title="Select a Single Image File",
                filetypes=[("Image Files", "*.png *.jpg *.jpeg *.ppm"), ("All files", "*.*")]
            )
        else:
            print("Please select a directory of images to compress...")
            input_path = filedialog.askdirectory(title="Select a Directory of Images")

        if not input_path:
            print("No input selected. Exiting.")
            return

    if not output_path:
        if 'root' not in locals(): root = Tk(); root.withdraw()
        use_webp = not args.no_webp
        if os.path.isdir(input_path):
            print("Please choose an output directory...")
            output_path = filedialog.askdirectory(title="Save Compressed Images To...")
        else:
            ext = ".webp" if use_webp else ".png"
            ftypes = [("WebP", "*.webp"), ("PNG", "*.png")] if use_webp else [("PNG", "*.png")]
            print("Please choose where to save the compressed file...")
            output_path = filedialog.asksaveasfilename(title="Save Compressed Image As...", initialfile=os.path.splitext(os.path.basename(input_path))[0], defaultextension=ext, filetypes=ftypes)
        if not output_path:
            print("No output location chosen. Exiting."); return

    # --- Prepare and Execute Compression ---
    tasks = []
    if os.path.isdir(input_path):
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        for filename in os.listdir(input_path):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.ppm')):
                in_file = os.path.join(input_path, filename)
                out_file = os.path.join(output_path, os.path.splitext(filename)[0] + ('.webp' if not args.no_webp else '.png'))
                tasks.append((in_file, out_file, args.quality, not args.no_webp, args.webp_method, args.resize, args.max_dim, args.strip_exif, Image.Dither.NONE))
    else:
        tasks.append((input_path, output_path, args.quality, not args.no_webp, args.webp_method, args.resize, args.max_dim, args.strip_exif, Image.Dither.NONE))

    print(f"Starting compression for {len(tasks)} image(s)...")
    if len(tasks) > 1 and not args.no_parallel:
        # Parallel Processing
        num_workers = multiprocessing.cpu_count()
        print(f"Using {num_workers} CPU cores for parallel processing...")
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            results = executor.map(compress_image, tasks)
            for result in results:
                if result:
                    print(result)
    else:
        # Sequential Processing
        for task in tasks:
            result = compress_image(task)
            if result:
                print(result)

    print("\nCompression complete.")

if __name__ == "__main__":
    main()
