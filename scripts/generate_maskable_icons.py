import os
from PIL import Image

def generate_maskable_icon(src_path, dest_path, size, target_size):
    if not os.path.exists(src_path):
        print(f"Source file {src_path} does not exist!")
        return False
        
    print(f"Generating maskable icon: {src_path} -> {dest_path} ({size}x{size})")
    
    # Open source icon
    img = Image.open(src_path)
    
    # Create white background
    bg = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    
    # Resize source icon to fit inside safe zone (75% size)
    resized_img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)
    
    # Center position
    offset = (size - target_size) // 2
    
    # Paste centered
    bg.paste(resized_img, (offset, offset), resized_img if resized_img.mode == 'RGBA' else None)
    
    # Save as PNG
    bg.convert("RGB").save(dest_path, "PNG")
    print(f"Successfully saved maskable icon to {dest_path}")
    return True

if __name__ == "__main__":
    webgis_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "webgis"))
    icons_dir = os.path.join(webgis_dir, "public", "icons")
    
    # 512x512
    generate_maskable_icon(
        src_path=os.path.join(icons_dir, "icon-512x512.png"),
        dest_path=os.path.join(icons_dir, "icon-maskable-512x512.png"),
        size=512,
        target_size=384
    )
    
    # 192x192
    generate_maskable_icon(
        src_path=os.path.join(icons_dir, "icon-192x192.png"),
        dest_path=os.path.join(icons_dir, "icon-maskable-192x192.png"),
        size=192,
        target_size=144
    )
