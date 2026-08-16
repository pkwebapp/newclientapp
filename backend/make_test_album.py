"""Generate a synthetic album PDF: 1 cover + 5 spreads + 1 back cover.
Cover/back = 18x12 in (1296x864 pt). Spreads = 36x12 in (2592x864 pt).
Each spread draws a continuous panorama with a subtle center line so we can
verify left/right halves align across the binding in the viewer.
"""
import fitz

PT = 72
COVER = (18 * PT, 12 * PT)
SPREAD = (36 * PT, 12 * PT)
COLORS = [(0.15, 0.22, 0.30), (0.28, 0.18, 0.20), (0.18, 0.28, 0.22),
          (0.30, 0.26, 0.16), (0.22, 0.18, 0.30)]

doc = fitz.open()

def add_page(w, h):
    return doc.new_page(width=w, height=h)

# Front cover
p = add_page(*COVER)
p.draw_rect(p.rect, color=None, fill=(0.08, 0.08, 0.10))
p.insert_textbox(fitz.Rect(0, h_third := COVER[1]*0.38, COVER[0], COVER[1]*0.62),
                 "THE WEDDING ALBUM", fontsize=48, color=(0.85, 0.72, 0.42),
                 align=fitz.TEXT_ALIGN_CENTER, fontname="hebo")
p.insert_textbox(fitz.Rect(0, COVER[1]*0.63, COVER[0], COVER[1]*0.75),
                 "Aisha  &  Rohan", fontsize=26, color=(0.9, 0.9, 0.86),
                 align=fitz.TEXT_ALIGN_CENTER, fontname="heit")

# Interior spreads
for i in range(5):
    p = add_page(*SPREAD)
    c = COLORS[i]
    p.draw_rect(p.rect, fill=c)
    # panorama band crossing the center to test seam continuity
    band = fitz.Rect(0, SPREAD[1]*0.30, SPREAD[0], SPREAD[1]*0.70)
    p.draw_rect(band, fill=(min(c[0]+0.25,1), min(c[1]+0.25,1), min(c[2]+0.25,1)))
    # center guide line
    p.draw_line(fitz.Point(SPREAD[0]/2, 0), fitz.Point(SPREAD[0]/2, SPREAD[1]),
                color=(1, 1, 1), width=0.5, dashes="[4 6] 0")
    p.insert_textbox(fitz.Rect(0, SPREAD[1]*0.42, SPREAD[0], SPREAD[1]*0.58),
                     f"SPREAD {i+1}  —  continuous panorama across the binding",
                     fontsize=30, color=(1, 1, 1), align=fitz.TEXT_ALIGN_CENTER, fontname="hebo")
    # left/right markers
    p.insert_textbox(fitz.Rect(40, 30, 400, 90), "LEFT", fontsize=22, color=(1,1,1), fontname="hebo")
    p.insert_textbox(fitz.Rect(SPREAD[0]-400, 30, SPREAD[0]-40, 90), "RIGHT", fontsize=22,
                     color=(1,1,1), align=fitz.TEXT_ALIGN_RIGHT, fontname="hebo")

# Back cover
p = add_page(*COVER)
p.draw_rect(p.rect, fill=(0.08, 0.08, 0.10))
p.insert_textbox(fitz.Rect(0, COVER[1]*0.45, COVER[0], COVER[1]*0.6),
                 "Thank you", fontsize=34, color=(0.85, 0.72, 0.42),
                 align=fitz.TEXT_ALIGN_CENTER, fontname="heit")

out = "/tmp/test_album.pdf"
doc.save(out)
print("Saved", out, "pages:", doc.page_count)
doc.close()
