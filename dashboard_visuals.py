"""Accessible, offline SVG/HTML views. All dynamic text is escaped."""
from html import escape
import base64
from functools import lru_cache
from pathlib import Path
from engine import as_bool, evaluate


def icon(name, color="#76b5bb"):
    paths = {
        "shield": '<path d="M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7l-9-4Z"/><path d="m8 12 3 3 5-6"/>',
        "camera": '<rect x="3" y="6" width="14" height="13" rx="3"/><path d="m17 10 4-3v11l-4-3M7 3h6"/>',
        "chip": '<rect x="6" y="6" width="12" height="12" rx="3"/><path d="M9 2v4m6-4v4M9 18v4m6-4v4M2 9h4m-4 6h4m12-6h4m-4 6h4"/><rect x="9" y="9" width="6" height="6" rx="1"/>',
        "cloud": '<path d="M6 18h12a4 4 0 0 0 0-8 6 6 0 0 0-11-3 5.5 5.5 0 0 0-1 11Z"/>',
        "layers": '<path d="m3 7 9-4 9 4-9 4-9-4Zm0 5 9 4 9-4M3 17l9 4 9-4"/>',
        "alert": '<path d="m12 3 10 18H2L12 3Z"/><path d="M12 9v5m0 3v.5"/>',
        "pulse": '<path d="M2 12h5l3-7 4 14 3-7h5"/>',
    }
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
           f'stroke="{color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
           + paths.get(name, paths["shield"]) + '</svg>')
    return f'<img class="rg-icon" alt="" aria-hidden="true" src="data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}">'


@lru_cache(maxsize=1)
def svg_font():
    path = Path(__file__).with_name("assets") / "IBMPlexSansArabic-Regular.woff2"
    if not path.exists():
        return ""
    data = base64.b64encode(path.read_bytes()).decode()
    return f"<style>@font-face{{font-family:RGArabic;src:url(data:font/woff2;base64,{data}) format('woff2');}}text{{font-family:RGArabic,sans-serif}}</style>"


def scene(event, outcome, simulated):
    """Stylized explanatory map, never presented as camera pixels or real tracks."""
    bridge = outcome["level"] == "BRIDGE_CRITICAL"
    ped = as_bool(event.get("pedestrian_present", False))
    truck = outcome["truck_present"]
    ambulance = as_bool(event.get("ambulance_present", False))
    hazard = outcome["level"] in ("CRITICAL", "WARNING")
    accent = "#fb8193" if bridge or hazard else "#67d9cd"
    label = "شاحنة مرتفعة" if bridge else "شاحنة" if truck else "إسعاف" if ambulance else "مركبة"
    truck_x = 355 if bridge else 330
    vehicle_width = 113 if truck else 73
    box_width = vehicle_width + 22
    bridge_color = "#ed8295" if bridge else "#8cafd6"
    zebra = ''.join(f'<rect x="191" y="{y}" width="43" height="9" rx="1" fill="#a5b6c4" opacity=".58"/>' for y in range(169, 301, 18))
    trees = ''.join(f'<circle cx="{x}" cy="{y}" r="13" fill="#1e4a46" stroke="#35645c"/><circle cx="{x-3}" cy="{y-3}" r="6" fill="#2f5b51"/>' for x, y in [(48, 89), (78, 99), (44, 343), (82, 351), (314, 92), (640, 340), (673, 345), (668, 94)])
    pedestrian = (f'<circle cx="213" cy="320" r="26" fill="#e6b465" opacity=".09"/>'
                  '<rect x="199" y="304" width="29" height="36" rx="4" fill="none" stroke="#e8bb77" stroke-dasharray="4 3"/>'
                  '<circle cx="213" cy="315" r="5" fill="#ecc68b"/><path d="M213 321v10m0-5-7 4m7-4 7 4m-7 1-6 7m6-7 6 7" stroke="#ecc68b" stroke-width="3" stroke-linecap="round"/>'
                  '<text x="213" y="362" fill="#e8c58f" font-size="12" text-anchor="middle">مشاة</text>') if ped else ''
    risk_zone = '<rect x="180" y="157" width="66" height="149" rx="8" fill="#f27b8f" opacity=".1" stroke="#fa8a9a" stroke-dasharray="5 5"/>' if hazard else ''
    dimensions = (f'<path d="M{truck_x+vehicle_width+24} 251v54m-4-54h8m-8 54h8" stroke="{accent}"/>'
                  f'<text x="{truck_x+vehicle_width+31}" y="282" fill="{accent}" font-size="12" direction="ltr">{outcome["truck_height_m"]:.1f} m</text>') if truck else ''
    cross = '<path d="M386 267v15m-7-8h14" stroke="#f1848d" stroke-width="4"/>' if ambulance else ''
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 408" role="img" aria-label="مشهد توضيحي للطريق ومعبر المشاة والجسر؛ ليس بث كاميرا">
    {svg_font()}<defs><pattern id="rg-grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0v24" fill="none" stroke="#21354a" stroke-width=".7"/></pattern>
    <linearGradient id="rg-road" x2="0" y2="1"><stop stop-color="#2b4054"/><stop offset="1" stop-color="#23374b"/></linearGradient>
    <filter id="rg-shadow"><feDropShadow dx="0" dy="5" stdDeviation="4" flood-color="#000" flood-opacity=".35"/></filter></defs>
    <rect width="720" height="408" fill="#122438"/><rect width="720" height="408" fill="url(#rg-grid)"/>
    <path d="M124 25h115v93H124Z M375 33h112v82H375Z M102 335h132v57H102Z M294 335h178v56H294Z" fill="#182e43" stroke="#2d465a"/>
    <path d="M135 37h93v68h-93ZM388 46h85v55h-85ZM115 347h106v32H115ZM308 347h150v32H308Z" fill="none" stroke="#294357"/>
    <path d="M550 0v408" stroke="#1c3249" stroke-width="100"/>
    <rect x="0" y="144" width="720" height="173" fill="#3a5064"/>
    <rect x="0" y="155" width="720" height="151" fill="url(#rg-road)"/>
    <path d="M0 160h720M0 301h720" stroke="#a6b7c4" stroke-width="1.5" opacity=".7"/>
    <path d="M0 229h720M0 233h720" stroke="#d0b875" stroke-width="1.5" opacity=".65"/>
    <path d="M0 195h170m90 0h260m70 0h130M0 270h170m340 0h210" stroke="#a8bdcc" stroke-width="2" stroke-dasharray="20 22" opacity=".35"/>
    {zebra}{risk_zone}{trees}
    <g opacity=".6" stroke="#a8bdcc" fill="none" stroke-width="2"><path d="M93 277h32m-9-8 9 8-9 8M452 190h-32m9-8-9 8 9 8"/></g>
    <g filter="url(#rg-shadow)"><rect x="73" y="176" width="65" height="33" rx="8" fill="#90a8bc"/><rect x="85" y="180" width="33" height="25" rx="4" fill="#4a657f"/><rect x="119" y="182" width="11" height="21" rx="3" fill="#29455e"/><path d="M78 178v29m55-26v23" stroke="#c0d1db" stroke-width="2"/></g>
    <g filter="url(#rg-shadow)"><rect x="{truck_x}" y="254" width="{vehicle_width}" height="43" rx="7" fill="{('#c4b79c' if truck else '#59bbb2')}"/>
    <rect x="{truck_x+vehicle_width-25}" y="258" width="20" height="35" rx="5" fill="#b9d7da"/><rect x="{truck_x+vehicle_width-20}" y="262" width="11" height="27" rx="2" fill="#365d73"/>
    <path d="M{truck_x+9} 260h{vehicle_width-40}m-{vehicle_width-40} 8h{vehicle_width-40}m-{vehicle_width-40} 8h{vehicle_width-40}m-{vehicle_width-40} 8h{vehicle_width-40}" stroke="#f0ece0" opacity=".24" stroke-width="2"/>{cross}</g>
    <rect x="{truck_x-10}" y="246" width="{box_width}" height="60" rx="5" stroke="{accent}" stroke-width="1.5" fill="none" stroke-dasharray="6 4"/>
    <rect x="{truck_x-10}" y="219" width="{box_width}" height="22" rx="4" fill="{accent}" opacity=".95"/>
    <text x="{truck_x+box_width/2-10}" y="234" fill="#14283c" text-anchor="middle" font-size="11" font-weight="600">{label}</text>
    {dimensions}{pedestrian}
    <g filter="url(#rg-shadow)"><rect x="553" y="122" width="24" height="216" rx="4" fill="#57758f" stroke="{bridge_color}"/><rect x="538" y="126" width="54" height="20" rx="4" fill="#7b96ad"/>
    <rect x="538" y="315" width="54" height="20" rx="4" fill="#7b96ad"/><path d="M559 152h12m-12 20h12m-12 20h12m-12 20h12m-12 20h12m-12 20h12m-12 20h12m-12 20h12" stroke="#a3b8c9" opacity=".6"/>
    <rect x="527" y="75" width="76" height="36" rx="6" fill="#152b41" stroke="{bridge_color}"/><text x="565" y="99" fill="{bridge_color}" font-size="18" text-anchor="middle" direction="ltr">4.5 m</text></g>
    <text x="565" y="365" fill="#adc6dd" text-anchor="middle" font-size="12">حد ارتفاع الجسر</text>
    <text x="212" y="133" fill="#a5bed0" text-anchor="middle" font-size="11">معبر المشاة</text>
    <g transform="translate(28 27)" stroke="#718ea5" fill="none"><circle cx="11" cy="11" r="10"/><path d="M11 3v16m-5-10 5-6 5 6"/></g>
    <text x="28" y="390" fill="#829caf" font-size="9" letter-spacing="2" direction="ltr">SCHEMATIC / NOT TO SCALE</text>
    </svg>'''
    scene_image = f'<img class="scene-image" alt="مشهد توضيحي للطريق ومعبر المشاة والجسر؛ ليس بث كاميرا" src="data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}">'
    return ('<section class="road-panel"><div class="panel-top"><div><h2>المشهد المروري</h2>'
            '<p>تمثيل توضيحي للحالة · ليس بثًا من الكاميرا</p></div>'
            f'<span class="camera-tag">{icon("camera")} SCENE 01</span></div>'
            f'<div class="road-canvas">{scene_image}<div class="scene-chip">'
            f'{"بيانات اصطناعية" if simulated else "مبني على قرار الرؤية"}<bdi>{"SIMULATION" if simulated else "EDGE INPUT"}</bdi></div></div>'
            '<div class="panel-bottom"><div class="legend"><span><i></i>المركبات</span><span><i class="ped"></i>المشاة</span><span><i class="bridge"></i>الجسر</span></div>'
            '<span>القرار محلي · الأولوية للسلامة</span></div></section>')


def decision_markup(outcome, simulated, command=None, measurement_valid=None):
    level = outcome["level"]
    configurations = {
        "NORMAL": ("", "مراقبة", "المسار تحت المراقبة", "المؤشرات الحالية ضمن عتبات القرار المحددة.", "shield", "G"),
        "WARNING": ("warn", "انتباه", "تقارب يستدعي الانتباه", "تفعيل التحذير المبكر لحماية منطقة العبور.", "alert", "R"),
        "CRITICAL": ("danger", "خطر مرتفع", "أولوية حماية المشاة", "تجاوزت مؤشرات التقارب عتبة التنبيه الحرج.", "alert", "R"),
        "BRIDGE_CRITICAL": ("danger", "حالة حرجة", "حماية الجسر أولًا", f"الارتفاع يتجاوز الحد بمقدار {outcome['truck_height_m'] - 4.5:.2f} متر. تنبيه الجسر له الأولوية.", "alert", "B"),
        "EMERGENCY_PRIORITY": ("priority", "أولوية", "إفساح المسار للإسعاف", "سيناريو تجريبي لأولوية مرور مركبات الطوارئ.", "pulse", "E"),
    }
    tone, tag, title, description, symbol, expected = configurations[level]
    if not simulated and measurement_valid is False and level == "NORMAL":
        tone, tag, title, description, symbol = ("warn", "غير مؤكد", "بيانات الرؤية غير مكتملة",
            "تعذر تأكيد حالة الطريق. راجع أمر التحذير المطلوب وحالة اتصال العتاد.", "alert")
    elif not simulated and level == "NORMAL" and command in ("R", "B"):
        tone, tag, title, description, symbol = ("warn", "تحذير مستمر", "التحذير ما زال فعالًا",
            "انخفضت القراءة الحالية؛ يحتفظ النظام بالتحذير مؤقتًا لتجنب تبدّل المصابيح السريع.", "alert")
    active_command = expected if simulated else command
    leds = []
    for name, code, color in [("طبيعي", "G", "#687e93"), ("المشاة", "R", "#d74d63"), ("الجسر", "B", "#be821d"), ("إسعاف", "E", "#0c9674")]:
        active = active_command == code or active_command == "B" and code == "R"
        leds.append(f'<div class="output {"active" if active else ""}" style="--led:{color}"><i></i>{name}</div>')
    return (f'<div class="decision-head"><span>قرار الحماية</span><span class="status-tag {tone}">{tag}</span></div>'
            f'<div class="decision-symbol {tone}">{icon(symbol, "#bc3044" if tone == "danger" else "#087e8b")}</div><h2 class="decision-title">{title}</h2>'
            f'<p class="decision-description">{description}</p><div class="output-title">'
            f'{"تمثيل المخارج · لا تُرسل أوامر للعتاد" if simulated else "المخارج المطلوبة · التأكيد في حالة الأجهزة"}</div>'
            f'<div class="outputs">{"".join(leds)}</div>')


def analysis_markup(events, labels):
    rows = []
    for name, label in labels.items():
        results = [evaluate(event) for event in events if event["scenario"] == name]
        mean = sum(result["risk"] for result in results) / len(results) if results else 0
        critical = sum(result["level"] in ("CRITICAL", "BRIDGE_CRITICAL") for result in results)
        rows.append(f'<div class="analysis-row"><span>{escape(label)}</span><div class="bar-track" aria-hidden="true">'
                    f'<div class="bar-fill" style="width:{mean:.1f}%;background:{"#bc4058" if name == "TRUCK_OVERHEIGHT" else "#168b98"}"></div></div>'
                    f'<bdi>{mean:.1f}</bdi><small>{critical} حدث حرج</small></div>')
    return '<section class="analysis-card"><h2>مؤشر الخطر عبر السيناريوهات</h2><p>متوسط المؤشر من 100 · الأرقام مأخوذة من أحداث المحاكاة</p>' + ''.join(rows) + '</section>'
