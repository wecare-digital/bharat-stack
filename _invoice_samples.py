"""Generate 3 invoice style samples: Monospace POS, Modern Card, Hybrid"""
from PIL import Image, ImageDraw, ImageFont
import os

# Try to load nice fonts, fallback to default
def get_fonts(style='mono'):
    """Get font set for a given style."""
    try:
        if style == 'mono':
            return {
                'title': ImageFont.truetype("consola.ttf", 18) if os.path.exists("C:/Windows/Fonts/consola.ttf") else ImageFont.truetype("cour.ttf", 18),
                'bold': ImageFont.truetype("consolab.ttf", 13) if os.path.exists("C:/Windows/Fonts/consolab.ttf") else ImageFont.truetype("courbd.ttf", 13),
                'regular': ImageFont.truetype("consola.ttf", 11) if os.path.exists("C:/Windows/Fonts/consola.ttf") else ImageFont.truetype("cour.ttf", 11),
                'small': ImageFont.truetype("consola.ttf", 10) if os.path.exists("C:/Windows/Fonts/consola.ttf") else ImageFont.truetype("cour.ttf", 10),
                'paid': ImageFont.truetype("consolab.ttf", 24) if os.path.exists("C:/Windows/Fonts/consolab.ttf") else ImageFont.truetype("courbd.ttf", 24),
                'header': ImageFont.truetype("consolab.ttf", 12) if os.path.exists("C:/Windows/Fonts/consolab.ttf") else ImageFont.truetype("courbd.ttf", 12),
            }
        elif style == 'modern':
            return {
                'title': ImageFont.truetype("segoeui.ttf", 20),
                'bold': ImageFont.truetype("segoeuib.ttf", 13),
                'regular': ImageFont.truetype("segoeui.ttf", 11),
                'small': ImageFont.truetype("segoeui.ttf", 10),
                'paid': ImageFont.truetype("segoeuib.ttf", 26),
                'header': ImageFont.truetype("segoeuib.ttf", 12),
            }
        else:  # hybrid
            return {
                'title': ImageFont.truetype("segoeuib.ttf", 18),
                'bold': ImageFont.truetype("consolab.ttf", 12) if os.path.exists("C:/Windows/Fonts/consolab.ttf") else ImageFont.truetype("segoeuib.ttf", 12),
                'regular': ImageFont.truetype("consola.ttf", 11) if os.path.exists("C:/Windows/Fonts/consola.ttf") else ImageFont.truetype("segoeui.ttf", 11),
                'small': ImageFont.truetype("segoeui.ttf", 10),
                'paid': ImageFont.truetype("segoeuib.ttf", 24),
                'header': ImageFont.truetype("segoeuib.ttf", 12),
            }
    except:
        f = ImageFont.load_default()
        return {'title': f, 'bold': f, 'regular': f, 'small': f, 'paid': f, 'header': f}

def center(draw, text, W, y, font, fill='#000'):
    try:
        bbox = draw.textbbox((0,0), text, font=font)
        tw = bbox[2] - bbox[0]
    except:
        tw = len(text) * 7
    draw.text(((W - tw) // 2, y), text, fill=fill, font=font)

def right(draw, text, x_right, y, font, fill='#000'):
    try:
        bbox = draw.textbbox((0,0), text, font=font)
        tw = bbox[2] - bbox[0]
    except:
        tw = len(text) * 7
    draw.text((x_right - tw, y), text, fill=fill, font=font)

def lr(draw, left_text, right_text, pad, W, y, font, fill='#000'):
    draw.text((pad, y), left_text, fill=fill, font=font)
    right(draw, right_text, W - pad, y, font, fill)

def dashed(draw, x1, x2, y, fill='#999'):
    x = x1
    while x < x2:
        draw.line([(x, y), (min(x+6, x2), y)], fill=fill, width=1)
        x += 10

