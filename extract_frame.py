from PIL import Image
import sys

webp_path = r'C:\Users\analistapi\.gemini\antigravity\brain\0a694aa0-28a2-46ac-9b9a-c00e166bac05\dnpra_portal_exploration_1772035299452.webp'
try:
    im = Image.open(webp_path)
    # Go to the last frame
    im.seek(im.n_frames - 1)
    out_path = r'C:\Users\analistapi\Desktop\Proyectos\scraper-DNPRA\data\last_frame.png'
    im.save(out_path)
    print(f"Frame guardado en {out_path}")
except Exception as e:
    print(f"Error: {e}")
