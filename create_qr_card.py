# Optional design tools: pip install qrcode pillow arabic-reshaper python-bidi
from pathlib import Path
import qrcode
from PIL import Image,ImageDraw,ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
import cv2
URL='https://ey4d55.github.io/RoadGuardian-AI/'
OUT=Path('docs/images');OUT.mkdir(exist_ok=True)
qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H,box_size=14,border=4)
qr.add_data(URL);qr.make(fit=True)
matrix=qr.get_matrix();n=len(matrix);size=n*14
qrimg=qr.make_image(fill_color='#102537',back_color='white').convert('RGB')
qrimg.save(OUT/'roadguardian-qr-code.png')
w,h=1200,1600
im=Image.new('RGB',(w,h),'#0e2231');d=ImageDraw.Draw(im)
for x in range(0,w,80): d.line((x,0,x,h),fill='#122b3b')
for y in range(0,h,80): d.line((0,y,w,y),fill='#122b3b')
d.rounded_rectangle((48,48,1152,1552),radius=42,fill='#102a3a',outline='#315366',width=2)
d.rounded_rectangle((90,90,1110,100),radius=5,fill='#6bd4c5')
font=lambda sz,b=False:ImageFont.truetype('C:/Windows/Fonts/'+('arialbd.ttf' if b else 'arial.ttf'),sz)
def center(text,y,sz,color,b=False,ar=False):
 if ar:text=get_display(arabic_reshaper.reshape(text))
 d.text((600,y),text,font=font(sz,b),fill=color,anchor='mt')
# Shield symbol with a clear pedestrian-safety identity.
d.polygon([(600,135),(660,158),(653,222),(600,257),(547,222),(540,158)],outline='#6bd4c5',width=5)
d.line([(575,194),(593,211),(627,175)],fill='#6bd4c5',width=7)
center('RoadGuardian AI',290,70,'#f4fbff',True)
center('حماية المشاة أولًا',385,49,'#79dfcf',True,True)
center('امسح الرمز وجرّب المنصة',485,48,'#ffffff',True,True)
# Exact integer modules and uninterrupted white quiet zone.
x=(w-size)//2;y=590
im.paste(qrimg,(x,y))
center('SCAN TO EXPLORE',y+size+38,27,'#79dfcf',True)
center('محاكاة تفاعلية • حماية المشاة والجسور',y+size+100,34,'#d5e6ef',False,True)
center('EcoTwin',y+size+152,31,'#79dfcf',True)
center('ey4d55.github.io/RoadGuardian-AI',1450,31,'#cfdee8')
center('نموذج أولي تجريبي',1500,24,'#89a8ba',False,True)
im.save(OUT/'roadguardian-qr.png',dpi=(300,300))
# Vector card for scalable printing; keep the QR geometry identical.
rects=''.join(f'<rect x="{x+c*14}" y="{y+r*14}" width="14" height="14"/>' for r,row in enumerate(matrix) for c,on in enumerate(row) if on)
svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1600" viewBox="0 0 1200 1600"><rect width="1200" height="1600" fill="#0e2231"/><rect x="48" y="48" width="1104" height="1504" rx="42" fill="#102a3a" stroke="#315366" stroke-width="2"/><rect x="90" y="90" width="1020" height="10" rx="5" fill="#6bd4c5"/><path d="M600 135L660 158 653 222 600 257 547 222 540 158Z M575 194L593 211 627 175" fill="none" stroke="#6bd4c5" stroke-width="6"/><g text-anchor="middle" font-family="Arial,sans-serif"><text x="600" y="350" font-size="70" font-weight="bold" fill="white">RoadGuardian AI</text><text x="600" y="430" font-size="49" fill="#79dfcf" direction="rtl">حماية المشاة أولًا</text><text x="600" y="530" font-size="48" fill="white" direction="rtl">امسح الرمز وجرّب المنصة</text><text x="600" y="{y+size+65}" font-size="27" fill="#79dfcf">SCAN TO EXPLORE</text><text x="600" y="{y+size+130}" font-size="34" fill="#d5e6ef" direction="rtl">محاكاة تفاعلية • حماية المشاة والجسور</text><text x="600" y="{y+size+180}" font-size="31" fill="#79dfcf">EcoTwin</text><text x="600" y="1478" font-size="31" fill="#cfdee8">ey4d55.github.io/RoadGuardian-AI</text><text x="600" y="1523" font-size="24" fill="#89a8ba" direction="rtl">نموذج أولي تجريبي</text></g><rect x="{x}" y="{y}" width="{size}" height="{size}" fill="white"/><g fill="#102537">{rects}</g></svg>'''
Path('docs/roadguardian-qr.svg').write_text(svg,encoding='utf-8')
for file in ('roadguardian-qr-code.png','roadguardian-qr.png'):
 image=cv2.imread(str(OUT/file)); decoded,points,_=cv2.QRCodeDetector().detectAndDecode(image)
 assert decoded==URL,(file,decoded)
 print(file,'decoded correctly:',decoded)
