"""Generate black & white thermal POS receipt invoice PNG.
Logo on left header, PAID icon from S3, WDSR reference format.
Compact for WhatsApp chat visibility.
"""
from PIL import Image, ImageDraw, ImageFont
import boto3, io

CHARS = 48
FONT_SZ = 15
LINE_H = 21
PX = 18
PY = 14

def mf(size, bold=False):
    names = ['consolab.ttf','courbd.ttf'] if bold else ['consola.ttf','cour.ttf']
    for n in names:
        try: return ImageFont.truetype(n, size)
        except: pass
    return ImageFont.load_default()

F   = mf(FONT_SZ)
FB  = mf(FONT_SZ, True)
FLG = mf(FONT_SZ + 4, True)
FSM = mf(FONT_SZ - 2)
FXS = mf(FONT_SZ - 4)

def _tw(d, t, f):
    try:
        bb = d.textbbox((0,0), t, font=f)
        return bb[2] - bb[0]
    except: return len(t) * 8

def load_s3_image(key):
    """Load an image from S3."""
    try:
        s3 = boto3.client('s3', region_name='us-east-1')
        r = s3.get_object(Bucket='app.wecare.digital', Key=key)
        return Image.open(io.BytesIO(r['Body'].read())).convert('RGBA')
    except Exception as e:
        print(f"S3 load {key}: {e}")
        return None

def generate_sample():
    lines = []

    def L(t, f=F):   lines.append((t, f, 'L'))
    def C(t, f=F):   lines.append((t, f, 'C'))
    def LR(l,r,f=F): lines.append(((l,r), f, 'LR'))
    def SEP():        lines.append(('-'*CHARS, F, 'C'))
    def DSEP():       lines.append(('='*CHARS, F, 'C'))
    def BL():         lines.append(('', F, 'L'))

    # ═══ HEADER ═══
    lines.append(('__LOGO__', FLG, 'LOGO'))

    # ═══ INVOICE META ═══
    DSEP()
    C("Invoice", FLG)
    DSEP()
    LR("Date    : 16-02-2026", "14:30 hrs")
    L("Order   : ORD-20260216-001")
    L("Ref     : WDSR41BA3534")
    L("Purpose : Monthly subscription")
    SEP()

    # ═══ BILL TO / SHIP TO ═══
    L("Bill To:", FB)
    L("  Manish Agarwal", FB)
    L("  +919330994400 | manish@wecare.digital", FSM)
    L("  The W.B.S.I.D.C. Building, Unit 1/20", FSM)
    L("  81/2/7 Phears Ln, Kolkata, WB 700012", FSM)
    L("Ship To:", FB)
    L("  456 Park Street, Suite 302", FSM)
    L("  Kolkata, WB 700016", FSM)
    SEP()

    # ═══ ITEMS ═══
    L(f"{'Sl':<3}{'Description':<22}{'Qty':>4}{'Rate':>10}{'Amount':>9}", FB)
    SEP()
    L(f"{'1':<3}{'Premium Plan-Annual':<22}{'1':>4}{'8,400.00':>10}{'8,400.00':>9}")
    L(f"{'2':<3}{'Setup & Onboarding':<22}{'1':>4}{'1,500.00':>10}{'1,500.00':>9}")
    SEP()

    # ═══ TOTALS ═══
    LR("Subtotal", "9,900.00")
    LR("Promo", "-500.00")
    LR("Express", "49.00")
    LR("CGST @9%", "846.00")
    LR("SGST @9%", "846.00")
    LR("Conv Fee", "221.88")
    DSEP()
    LR("Total  2 Items", "\u20b9 11,362.88", FB)
    DSEP()

    # ═══ GST SUMMARY ═══
    LR("CGST @9.0%  On 9,400.00", "846.00")
    LR("SGST @9.0%  On 9,400.00", "846.00")
    SEP()
    LR("Total Tax", "1,692.00", FB)
    DSEP()

    # ═══ PAID ICON (from S3) ═══
    BL()
    lines.append(('__PAID__', F, 'PAID_ICON'))
    BL()
    C("Paid: 16-02-2026 14:30 IST")
    DSEP()
    BL()
    C("Thank You!", FLG)
    C("Visit Again!", FLG)
    BL()
    SEP()
    C("Support: wecare.digital/selfservice", FSM)
    DSEP()

    # ══════════════════════════════════
    # RENDER
    # ══════════════════════════════════
    tmp = ImageDraw.Draw(Image.new('RGB',(1,1)))
    try:
        bb = tmp.textbbox((0,0),'M',font=F)
        CW = bb[2]-bb[0]
    except: CW=9

    W = CHARS*CW + PX*2
    est = len(lines)*LINE_H + PY*2 + 200
    img = Image.new('RGB', (W, est), '#fff')
    draw = ImageDraw.Draw(img)

    # Load assets from S3
    logo = load_s3_image('stream/media/m/wecare-digital.png')
    paid_icon = load_s3_image('stream/media/m/paid.png')

    y = PY

    for content, font, align in lines:
        if align == 'LOGO':
            # Logo left, company info to the right
            ls = 44
            if logo:
                lg = logo.resize((ls, ls), Image.LANCZOS)
                img.paste(lg, (PX, y), lg)
            hdr_lines = [
                ("WECARE.DIGITAL", FLG),
                ("GSTIN/UIN: 19AADFW7431N1ZK", FSM),
                ("The W.B.S.I.D.C. Building, Unit 1/20", FXS),
                ("81/2/7 Phears Ln, Kolkata, WB 700012", FXS),
                ("+91 9330994400 | one@wecare.digital", FXS),
            ]
            tx = PX + ls + 10
            avail = W - tx - PX
            hy = y
            for txt, hf in hdr_lines:
                tw = _tw(draw, txt, hf)
                hx = tx + (avail - tw) // 2
                draw.text((max(tx, hx), hy), txt, fill='#000', font=hf)
                hy += LINE_H - 3 if hf == FLG else LINE_H - 6
            y += max(ls + 4, hy - y + 4)
            continue

        if align == 'PAID_ICON':
            # Paste the PAID icon from S3, centered
            if paid_icon:
                icon_size = 100
                pi = paid_icon.resize((icon_size, icon_size), Image.LANCZOS)
                ix = (W - icon_size) // 2
                img.paste(pi, (ix, y), pi)
                y += icon_size + 6
            else:
                # Fallback text
                tw = _tw(draw, "[ PAID ]", FLG)
                draw.text(((W - tw) // 2, y), "[ PAID ]", fill='#059669', font=FLG)
                y += LINE_H + 6
            continue

        if align == 'LR':
            lt, rt = content
            draw.text((PX, y), lt, fill='#000', font=font)
            rw = _tw(draw, rt, font)
            draw.text((W - PX - rw, y), rt, fill='#000', font=font)
        elif align == 'C':
            tw = _tw(draw, content, font)
            draw.text(((W - tw) // 2, y), content, fill='#000', font=font)
        else:
            draw.text((PX, y), content, fill='#000', font=font)
        y += LINE_H

    y += PY
    img = img.crop((0, 0, W, y))

    # Scale 2x for WhatsApp readability
    fw, fh = W * 2, img.height * 2
    img = img.resize((fw, fh), Image.LANCZOS)

    img.save("_invoice_sample_output.png")
    print(f"Saved _invoice_sample_output.png ({fw}x{fh})")


if __name__ == '__main__':
    generate_sample()
