"""RoadGuardian operations dashboard. Run: python -m streamlit run dashboard.py"""
import base64
import binascii
import csv
from html import escape
import json
import math
import io
from pathlib import Path
import time
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, UnidentifiedImageError
from engine import evaluate, number, as_bool
from dashboard_visuals import icon, scene, decision_markup, analysis_markup
from ecotwin import payload as eco_payload, component_html as eco_html
from traffic_simulation import component_html as traffic_html
from roadguardian_views import (BRIDGE_VIEW, RESPONSE_VIEW, VALIDATION_VIEW,
                                mission_banner, provenance, response_view,
                                bridge_view, validation_view)

ROOT = Path(__file__).resolve().parent
ASSETS = Path(__file__).resolve().parent / "assets"
LABELS = {"CHILD_CROSSING": "عبور المشاة · التطبيق الرئيسي", "NORMAL": "حركة طبيعية",
          "AMBULANCE": "أولوية الإسعاف", "CLOUD_OFFLINE": "انقطاع السحابة",
          "CONGESTION": "ازدحام مروري", "TRUCK_OVERHEIGHT": "ارتفاع الشاحنة"}


def load_events():
    events = []
    path = ROOT / "events.csv"
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as source:
            events = list(csv.DictReader(source))
    defaults = dict(distance_m=40, relative_speed_kmh=30, pedestrian_present=False,
                    ambulance_present=False, cloud_online=True, model_confidence=0.95,
                    truck_present=False, truck_height_m=0.0)
    overrides = {"NORMAL": {}, "CHILD_CROSSING": {"distance_m": 3, "pedestrian_present": True},
                 "AMBULANCE": {"ambulance_present": True}, "CLOUD_OFFLINE": {"cloud_online": False},
                 "CONGESTION": {"relative_speed_kmh": 5},
                 "TRUCK_OVERHEIGHT": {"truck_present": True, "truck_height_m": 4.8}}
    for name, changes in overrides.items():
        if not any(event["scenario"] == name for event in events):
            events.append({**defaults, **changes, "scenario": name, "event_id": f"demo-{name}"})
    return events


def read_status():
    try:
        def invalid_constant(value):
            raise ValueError(f"Nonfinite telemetry value: {value}")
        state = json.loads((ROOT / "edge_status.json").read_text(encoding="utf-8"),
                           parse_constant=invalid_constant)
        if not isinstance(state, dict):
            raise ValueError("Status must be an object")
        age = time.time() - float(state["updated_at"])
        if not math.isfinite(age) or not 0 <= age <= 2.0:
            return {}, "توقفت التحديثات. افحص برنامج الرؤية وأعد تشغيله."
        for field in ("edge_active", "esp32_connected"):
            if not isinstance(state.get(field, False), bool):
                raise ValueError(f"Invalid {field}")
        for field in ("preview_only", "camera_connected", "presence_test", "tabletop_test", "usable_frame", "frame_dark"):
            if field in state and type(state[field]) is not bool:
                raise ValueError(f"Invalid {field}")
        if state.get("preview_only"):
            if state.get("edge_active") or (state.get("presence_test") and state.get("tabletop_test")):
                raise ValueError("Conflicting telemetry modes")
            counts = state.get("counts", {})
            if not isinstance(counts, dict) or any(type(v) is not int or v < 0 for v in counts.values()):
                raise ValueError("Invalid detection counts")
            if state.get("command", "R") not in ("R", "G"):
                raise ValueError("Invalid bench command")
            for field, default in (("road_length_cm", 30), ("road_width_cm", 20)):
                if number(state.get(field, default), field) <= 0:
                    raise ValueError("Invalid road dimensions")
            if state.get("tabletop_test"):
                demo = state.get("tabletop")
                if not isinstance(demo, dict) or demo.get("reason") not in ("unknown", "warming_up", "near_line", "clear"):
                    raise ValueError("Invalid stop-line status")
                if demo.get("command") != state.get("command"):
                    raise ValueError("Inconsistent stop-line command")
                for field in ("distance_cm", "approach_cm_s", "time_to_line_s"):
                    if demo.get(field) is not None:
                        number(demo[field], field, minimum=-1e6 if field == "distance_cm" else 0)
        if state.get("edge_active"):
            event, outcome = state.get("event"), state.get("outcome")
            if not isinstance(event, dict) or not isinstance(outcome, dict):
                raise ValueError("Incomplete live event")
            expected = evaluate(event)
            if any(outcome.get(key) != value for key, value in expected.items()):
                raise ValueError("Live decision does not match its event")
            if number(event.get("scene_scale", 1), "scene_scale") <= 0:
                raise ValueError("Invalid scene scale")
            # Normalize display-only measurements before formatting, including
            # bridge-priority events that legitimately omit pedestrian fields.
            event["scene_scale"] = number(event.get("scene_scale", 1), "scene_scale")
            confidence = number(event.get("model_confidence", 0), "model_confidence")
            if confidence > 1:
                raise ValueError("Invalid confidence")
            event["model_confidence"] = confidence
            for field in ("pedestrian_present", "ambulance_present", "cloud_online"):
                if field in event:
                    event[field] = as_bool(event[field])
            if event.get("truck_height_physical_m") is not None:
                event["truck_height_physical_m"] = number(event["truck_height_physical_m"], "physical height")
            if "site_configured" in event and type(event["site_configured"]) is not bool:
                raise ValueError("Invalid site configuration flag")
            if event.get("time_to_crosswalk_s") is not None:
                event["time_to_crosswalk_s"] = number(event["time_to_crosswalk_s"], "crosswalk time")
            if state.get("command") not in ("R", "B", "E", "G"):
                raise ValueError("Unknown hardware command")
            if not isinstance(state.get("measurement_valid"), bool):
                raise ValueError("Missing measurement validity")
        return state, None
    except (OSError, ValueError, KeyError, TypeError):
        return {}, "بيانات الرؤية غير متاحة أو غير صالحة. شغّل برنامج الرؤية وافحص تحديثاته."


def stylesheet():
    css = (ASSETS / "dashboard.css").read_text(encoding="utf-8")
    for weight, filename in [(400, "Regular"), (600, "SemiBold")]:
        font = ASSETS / f"IBMPlexSansArabic-{filename}.woff2"
        if font.exists():
            encoded = base64.b64encode(font.read_bytes()).decode("ascii")
            css += (f"@font-face{{font-family:RGArabic;src:url(data:font/woff2;base64,{encoded}) "
                    f"format('woff2');font-weight:{weight};font-style:normal;font-display:swap;}}")
    return css


def connectivity():
    state, error = read_status()
    rows = []
    for title, key, symbol in [("الرؤية الطرفية", "edge_active", "camera"), ("وحدة ESP32", "esp32_connected", "chip")]:
        preview_camera = key == "edge_active" and state.get("preview_only") is True and state.get("camera_connected") is True
        active = state.get(key) is True or preview_camera
        label = "فحص الكاميرا" if preview_camera else "متصل" if active else "غير متصل"
        rows.append(f'<div class="device-row">{icon(symbol)}<span>{title}</span>'
                    f'<span class="device-state {"online" if active else "offline"}"><i></i>'
                    f'{label}</span></div>')
    st.html('<div class="sidebar-section-label">الأجهزة المتصلة</div><div class="device-list">' + ''.join(rows) + '</div>')
    if error:
        st.caption("الأجهزة غير متصلة حاليًا. يمكنك استكشاف سيناريوهات المحاكاة.")
    elif state.get("serial_error"):
        st.caption("اتصال ESP32 بانتظار تأكيد الأمر.")
    st.html('<div class="sidebar-foot">' + icon("shield")
            + '<div><strong>المعالجة على الطرف</strong><span>مسار القرار يعمل محليًا</span></div></div>')


def camera_monitor(state):
    """Only called with a fresh status; never show an old frame as live."""
    encoded = state.get("frame_jpeg")
    try:
        if not isinstance(encoded, str) or len(encoded) > 2_000_000:
            raise ValueError("Missing camera frame")
        jpeg = base64.b64decode(encoded, validate=True)
        if not jpeg.startswith(b"\xff\xd8"):
            raise ValueError("Invalid camera frame")
        with Image.open(io.BytesIO(jpeg)) as picture:
            if picture.format != "JPEG" or picture.width * picture.height > 2_000_000:
                raise ValueError("Invalid camera image dimensions")
            picture.verify()
    except (ValueError, binascii.Error, OSError, UnidentifiedImageError, Image.DecompressionBombError):
        st.info("بانتظار صورة حديثة من برنامج الكاميرا.")
        return
    dark = state.get("frame_dark") is True
    with st.container(key="camera_monitor"):
        mode = "خط توقف افتراضي · مسافات تقديرية" if state.get("tabletop_test") else "اختبار وجود شخص" if state.get("presence_test") else "فحص دون معايرة" if state.get("preview_only") else "رصد مباشر"
        st.html('<div class="monitor-heading"><div><span class="eyebrow">ROADGUARDIAN / LIVE MONITOR</span>'
                '<h2>عين على الطريق</h2><p>كاميرا 01 · الرؤية الطرفية</p></div>'
                f'<span class="monitor-live"><i></i>{"صورة داكنة" if dark else "مباشر"}</span></div>')
        st.image(jpeg, width="stretch")
        ack = "ESP32 متصل · تأكيد استقبال" if state.get("esp32_connected") else "ESP32 غير متصل"
        stamp = time.strftime("%H:%M:%S", time.localtime(state["updated_at"]))
        st.html(f'<div class="monitor-footer"><span>{escape(mode)}</span><span>{ack}</span>'
                f'<span>آخر تحديث <bdi>{stamp}</bdi></span></div>')
    st.caption("بث محلي مع مربعات الكشف · تُستبدل آخر صورة تلقائيًا، ولا يُنشأ أرشيف فيديو. تُخفى الصورة عند انقطاع التحديثات.")
    if dark:
        st.warning("تصل إطارات سوداء أو شديدة الظلمة من الكاميرا. افحص بث الجوال والعدسة والإضاءة؛ أعداد الكشف هنا لا تؤكد خلو المشهد.")


def show_outcome(event, outcome, simulated=True, state=None):
    state = state or {}
    scale = event.get("scene_scale", 1.0)
    if scale != 1:
        st.info(f"مجسم بمقياس 1:{scale:g} · القيم المعروضة مكافئة بالحجم الكامل")
        physical = event.get("truck_height_physical_m")
        if physical is not None:
            st.caption(f"الارتفاع المقدّر داخل المجسم: {physical * 100:.1f} سم")
    with st.container(key="metrics"):
        a, b, c, d = st.columns(4)
        a.metric("مؤشر الخطر", f"{outcome['risk']:.1f}", help="مؤشر قواعد القرار من 100، وليس احتمال تصادم.")
        ttc = outcome["ttc_s"]
        b.metric("زمن الوصول للمعبر" if event.get("site_configured") else "زمن التقارب", "—" if ttc is None or ttc >= 999 else f"{ttc:.2f} s", help="تقدير بالثواني؛ ليس ضمانًا لتقاطع المسارات أو توقف المركبة.")
        if outcome["truck_present"]:
            c.metric("ارتفاع الشاحنة", f"{outcome['truck_height_m']:.2f} m", help="ارتفاع مكافئ بالمتر. حد الجسر 4.5 متر.")
        else:
            c.metric("وجود مشاة", "مرصود" if as_bool(event.get("pedestrian_present", False)) else "غير مرصود",
                     help="وجود المشاة لا يمنح السماح بالعبور، وعدم رصدهم لا يثبت خلو الطريق.")
        d.metric("ثقة الكشف", f"{float(event.get('model_confidence', 0)) * 100:.0f}%", help="قيمة اصطناعية في المحاكاة، وثقة النموذج في الرؤية.")
    with st.container(key="scene_layout"):
        main_col, decision_col = st.columns([1.9, 1], gap="medium")
    with main_col:
        st.html(scene(event, outcome, simulated))
    with decision_col:
        with st.container(key="decision_panel"):
            st.html(decision_markup(outcome, simulated, state.get("command"), state.get("measurement_valid")))
            level = outcome["level"]
            if level == "BRIDGE_CRITICAL":
                st.error("الشاحنة تتجاوز ارتفاع الجسر!", icon=":material/warning:")
            elif level == "CRITICAL":
                st.error("خطر تقارب مع المشاة. تنبيه أحمر محلي.", icon=":material/warning:")
            elif level == "WARNING":
                st.warning("تقارب يستدعي الانتباه. التحذير ممثّل بمصباح أحمر.")
            elif level == "EMERGENCY_PRIORITY":
                st.info("أولوية مرور تجريبية للإسعاف.")
            elif not simulated and not state.get("measurement_valid"):
                st.warning("لا يمكن تأكيد حالة الطريق؛ الأمر المطلوب تحذير احترازي.")
            elif not simulated and state.get("command") in ("R", "B"):
                st.warning("القراءة الحالية دون عتبة الخطر، لكن أمر التحذير ما زال محتفظًا به مؤقتًا.")
            else:
                st.success("لم تُفعّل عتبة التنبيه لهذا الحدث.")
            st.html(f'<div class="decision-code"><span>قرار المحرك</span><bdi>{escape(level)}</bdi></div>')
    if not simulated:
        if not state.get("measurement_valid"):
            st.warning("بعض القياسات غير متاحة؛ العتاد في وضع تحذير احترازي.")
        if state.get("detections", 0) == 0:
            st.warning("لم تُرصد أجسام. الحالة الطبيعية وحدها لا تؤكد تعرف النموذج على الألعاب.")
        st.caption(f"الأجسام المكتشفة: {state.get('detections', 0)} · زمن المعالجة: {state.get('inference_ms', '—')} ms")
    cloud = "متصلة" if outcome["cloud_online"] else "غير متصلة"
    event_id = str(event.get("event_id", "LIVE"))
    st.html(f'<div class="event-strip"><span>{icon("layers")} {"الحدث التجريبي" if simulated else "المشهد الحي"} <bdi>{escape(event_id)}</bdi></span>'
            f'<span>{icon("cloud")} {"السحابة في المحاكاة: " + cloud if simulated else "الخدمات السحابية غير مستخدمة"}</span>'
            '<span>القياسات تقديرية · المشهد توضيحي</span></div>')
    provenance(event, simulated, state)


def main():
    st.set_page_config(page_title="RoadGuardian AI | مركز المراقبة", page_icon=":material/shield:", layout="wide", initial_sidebar_state="auto")
    st.html(f"<style>{stylesheet()}</style>")
    with st.sidebar:
        st.html(f'<div class="brand">{icon("shield")}<div><bdi>RoadGuardian<span> AI</span></bdi><small>حماية المشاة أولًا</small></div></div>')
        st.html('<div class="sidebar-section-label">مساحة العمل</div>')
        view = st.radio("التنقل", ["لوحة المراقبة", BRIDGE_VIEW, RESPONSE_VIEW, VALIDATION_VIEW,
                                  "تحليل الأثر · EcoTwin", "مقارنة السيناريوهات", "دليل العرض"], key="view", label_visibility="collapsed")
        st.html('<div class="sidebar-section-label source-heading">مصدر البيانات</div>')
        mode = st.radio("مصدر البيانات", ["محاكاة السيناريوهات", "الرؤية الحية"], key="source", label_visibility="collapsed")
        st.fragment(run_every=1.0)(connectivity)()
    simulated = mode == "محاكاة السيناريوهات"
    badge_text = ("نتائج مسجلة يدويًا" if view == VALIDATION_VIEW else "بيانات المحاكاة" if view == "مقارنة السيناريوهات" else "دليل التشغيل"
                  if view == "دليل العرض" else "وضع المحاكاة" if simulated else "مصدر الرؤية الحية")
    st.html(f'<header class="topbar"><div class="breadcrumb">مركز العمليات <span>/</span> {view}</div>'
            f'<div class="source-badge {"demo" if simulated else "live"}"><i></i>{badge_text}</div></header>')
    subtitles = {"لوحة المراقبة": "التطبيق الرئيسي: كشف الخطر وتنبيه السائق والمشاة محليًا.",
                 BRIDGE_VIEW: "التطبيق الثاني: كشف تجاوز الارتفاع والتحذير قبل الجسر.",
                 RESPONSE_VIEW: "من اكتشاف الخطر إلى تأكيد الاستجابة — بخطوات واضحة.",
                 VALIDATION_VIEW: "نتائج يمكن مراجعتها. المحاكاة والاختبار المادي منفصلان.",
                 "تحليل الأثر · EcoTwin": "وحدة مساندة: أثر الانتظار المفترض. قرار الحماية يبقى أولًا.", "مقارنة السيناريوهات": "اقرأ أثر كل سيناريو على قرارات السلامة.", "دليل العرض": "المشاة أولًا، ثم الجسور، ثم إثبات العمل دون إنترنت."}
    st.html(f'<div class="page-heading"><div><div class="eyebrow">ROADGUARDIAN / CONTROL CENTER</div>'
            f'<h1>{"SafeCross · حماية المشاة" if view == "لوحة المراقبة" else view}</h1><p>{subtitles[view]}</p></div>'
            f'<div class="version-mark">{icon("shield")}<span>حماية المشاة<br>وسلامة الجسور</span></div></div>')
    events = load_events()
    if view == RESPONSE_VIEW:
        response_view(simulated)
        return
    if view == VALIDATION_VIEW:
        validation_view()
        return
    if view == BRIDGE_VIEW:
        bridge_view(simulated, show_outcome, read_status)
        return
    if view == "تحليل الأثر · EcoTwin":
        eco_view(events, simulated)
        return
    if view == "مقارنة السيناريوهات":
        st.html(analysis_markup(events, LABELS))
        st.caption("جميع النتائج في هذه المقارنة ناتجة عن بيانات المحاكاة.")
        return
    if view == "دليل العرض":
        st.html('<div class="guide-intro">RoadGuardian منصة للحماية الاستباقية؛ SafeCross التطبيق الرئيسي وBridgeShield يوضح قابلية التوسع. العرض يثبت الكشف والتنبيه، وليس منع الحوادث فعليًا.</div>')
        st.info("حالة النموذج: جُرّب كشف الشخص منفصلًا، والسيارة مع خط توقف افتراضي وESP32. اختبار مشاة ومركبة معًا وقياس ارتفاع الجسر بالعتاد ما زالا مؤجلين.")
        for title, text in [
            ("01 · المشاة والاستجابة", "ابدأ بمشهد المشاة في لوحة المراقبة: اكتشاف وتقارب وتنبيه. افتح تسلسل الاستجابة لشرح طلب العبور وتأكيد وحدة التحكم في المحاكاة. الإنذار وحده لا يمنح إذنًا للمشاة."),
            ("02 · الجسر والمسار البديل", "افتح BridgeShield، وقارن شاحنة 4 م بأخرى 5 م. اعرض توقف الشاحنة ثم مسار B في المجسم، أو التوقف عند غياب بديل. مصدر الارتفاع في هذا المشهد محاكاة؛ الحساس المستقل لم يُربط بعد."),
            ("03 · دون إنترنت ثم التحقق", "بعد تجهيز الأوزان وتشغيل الكاميرا والعتاد فعليًا، افصل الإنترنت وأعد مشهد المشاة. لا تعتبر اختيار CLOUD_OFFLINE إثباتًا ماديًا. سجّل النتائج والأزمنة المرجعية في صفحة التحقق والقياسات، وصدّر CSV.")]:
            with st.expander(title, expanded=True):
                st.write(text)
        st.markdown("**أوامر التشغيل على الكمبيوتر** — اكتبها في Terminal داخل مجلد المشروع بعد تثبيت المتطلبات. هذه الأوامر تشغّل الأجهزة الفعلية؛ أزرار المحاكاة في الصفحة تعرض الحركة فقط.")
        st.markdown("**فحص المصابيح واللوحة فقط:** يرسل أوامر الاختبار إلى COM3، دون استخدام الكاميرا. أوقف برنامج الرؤية وأغلق Serial Monitor أولًا.")
        st.code("python hardware_check.py --port COM3")
        st.markdown("**عرض الكاميرا داخل المنصة:** يشغّل YOLO على الكاميرا رقم 0 ويتصل بـESP32. في وضع الفحص يبقى الأحمر احترازيًا، ولا تُقاس المسافات.")
        st.code("python vision_serial_bridge.py --preview-only --port COM3 --camera 0 --no-display")
        st.markdown("**تجربة السيارة وخط التوقف:** بعد ضبط حدود الطريق في road_region.json، يربط اقتراب السيارة بالمصباح الحقيقي. أغلق تطبيق Camera وبرنامج فحص المصابيح قبل تشغيله.")
        st.code("python vision_serial_bridge.py --tabletop-test --road-region road_region.json --port COM3 --camera 0 --no-display")
        st.caption("COM3 هو منفذ اللوحة المجربة؛ camera 0 هو رقم الكاميرا لدى Windows. اضغط Ctrl+C في Terminal لإيقاف البرنامج. لا تشغّل برنامجي العتاد على المنفذ نفسه معًا.")
        st.caption("الكاميرا ثابتة عند المعبر. للجسر وحدة كشف منفصلة ميدانيًا. معايرة مناطق الانتظار والمعبر والاقتراب تُضبط عند تجهيز الكاميرا؛ تحريكها يحتاج إعادة معايرة.")
        return
    if simulated:
        mission_banner()
    if not simulated:
        @st.fragment(run_every=0.25)
        def live_view():
            state, error = read_status()
            if not error and state.get("preview_only") is True and state.get("camera_connected") is True:
                camera_monitor(state)
                if state.get("road_region"):
                    st.info("الإطار الأصفر طريق تجريبي تقريبي. ثبّت الجوال والدفتر؛ تحريكهما يحتاج إعادة التحديد. هذه ليست معايرة فعلية.")
                if state.get("tabletop_test"):
                    st.warning(f"اختبار توضيحي: طول الطريق {state.get('road_length_cm', 30):g} سم وعرضه {state.get('road_width_cm', 20):g} سم. حدود الصورة وموضع السيارة من المربع تقديريان؛ الأبعاد وحدها لا تثبت دقة المسافات، وهذا ليس كشف تصادم مع مشاة.")
                    demo = state.get("tabletop") or {}
                    for col, label, key, unit in zip(st.columns(3),
                        ("المسافة الافتراضية للخط", "سرعة الاقتراب التقديرية", "الزمن التقديري للخط"),
                        ("distance_cm", "approach_cm_s", "time_to_line_s"), ("سم", "سم/ث", "ث")):
                        value = demo.get(key)
                        col.metric(label, "—" if value is None else f"{value:g} {unit}")
                    reasons = {"unknown": "لا توجد مركبة متتبعة صالحة داخل الطريق؛ الأحمر احترازي.",
                               "warming_up": "السيارة مرصودة بعيدًا عن الخط؛ نجمع عينات السرعة، والأحمر مطفأ مؤقتًا في هذا الاختبار.",
                               "near_line": "اقتراب من الخط أو تجاوزه؛ تنبيه أحمر تجريبي.",
                               "clear": "لم تتحقق عتبة التنبيه التجريبية؛ الأحمر مطفأ."}
                    st.info(reasons.get(demo.get("reason"), "بانتظار بيانات الاختبار"))
                    st.caption("العتبة التجريبية: 3 سم قبل الخط أو زمن وصول ≤ ثانيتين. قيمة المسافة السالبة تعني تجاوز الخط. لا نطبق مقياس 1:20 على هذه الأرقام.")
                elif state.get("presence_test"):
                    st.warning("اختبار ربط فقط: وجود شخص يشغّل الأحمر، وغيابه يطفئه بعد ثانية. هذا ليس كشف خطر تصادم ولا سماحًا بالعبور.")
                    st.info("الأمر المرسل: " + ("الأحمر مضاء" if state.get("command") == "R" else "الأحمر مطفأ"))
                    if not state.get("usable_frame"):
                        st.warning("الصورة غير صالحة للاختبار؛ الأحمر احترازي.")
                else:
                    st.warning("الأحمر احترازي ثابت أثناء الإعداد، وليس نتيجة خطر مقاس. لا توجد قياسات مسافة أو ارتفاع في هذا الوضع.")
                counts = state.get("counts", {})
                names = ("car", "truck") if state.get("tabletop_test") else ("person", "car", "truck")
                labels = ("سيارات", "شاحنات") if state.get("tabletop_test") else ("أشخاص", "سيارات", "شاحنات")
                for col, name, label in zip(st.columns(len(names)), names, labels):
                    col.metric(label, counts.get(name, 0))
                st.caption("هذا الاختبار يتتبع السيارات والشاحنات فقط؛ كشف المشاة غير مفعل فيه." if state.get("tabletop_test") else "فئات الكشف: شخص، سيارة، شاحنة. وجود شخص وحده لا يعني وجود خطر تصادم.")
                st.caption("ESP32: " + ("تم تأكيد استقبال " + str(state.get("command", "R")) if state.get("esp32_connected") else "بانتظار الاتصال"))
                return
            if error or not state.get("edge_active"):
                st.html(f'<section class="empty-state">{icon("camera")}<span class="eyebrow">EDGE VISION</span>'
                        '<h2>بانتظار اتصال الكاميرا</h2><p>ستظهر القياسات وقرارات الحماية هنا عند تشغيل الرؤية الطرفية.</p>'
                        '<div class="empty-tags"><span>كاميرا محلية</span><span>معالجة على الجهاز</span><span>اتصال ESP32</span></div></section>')
                st.caption(error or "الرؤية غير نشطة حاليًا. افحص برنامج الكاميرا.")
                with st.expander("طريقة الاتصال"):
                    st.code("python vision_serial_bridge.py --port COM3 --camera-height-m 0.3 --focal-px 700 --horizon-y 240 --scene-scale 20")
                    st.caption("استبدل قيم المعايرة بما يناسب كاميرتك.")
                return
            event, outcome = state.get("event"), state.get("outcome")
            if isinstance(event, dict) and isinstance(outcome, dict):
                camera_monitor(state)
                show_outcome(event, outcome, False, state)
            else:
                st.info("بانتظار أول إطار مكتمل.")
        live_view()
    else:
        with st.container(key="controls"):
            scenario = st.selectbox("اختر مشهد المحاكاة المتحركة", list(LABELS), key="scenario_picker", format_func=lambda name: LABELS[name])
        with st.container(key="traffic_animation"):
            components.html(traffic_html(scenario), height=1600, scrolling=True)
    st.html('<footer class="page-footer"><span>ROADGUARDIAN AI</span><p>نموذج تجريبي للسلامة المرورية · بيانات المحاكاة لا تتحكم بالعتاد</p></footer>')


def eco_view(events, simulated):
    """Explicit hypothetical comparison, isolated from safety and serial output."""
    if not simulated:
        @st.fragment(run_every=2.0)
        def live_eco():
            state, error = read_status()
            if error or not state.get("edge_active"):
                st.info("بانتظار بيانات رؤية حديثة. لا توجد قياسات بيئية حية لعرضها.")
                return
            event, outcome = state.get("event"), state.get("outcome")
            if not isinstance(event, dict) or not isinstance(outcome, dict):
                st.info("بانتظار أول قرار مكتمل.")
                return
            if not state.get("measurement_valid"):
                st.warning("قياسات الرؤية غير مكتملة؛ راجع التحذير الاحترازي في لوحة المراقبة.")
                st.info("لا تُعرض قطاعات توحي بحالة طريق مؤكدة حتى تكتمل القياسات.")
                return
            with st.container(key="eco_frame"):
                components.html(eco_html(eco_payload(event, outcome, simulated=False)), height=900, scrolling=True)
        live_eco()
        return
    selector, event_selector = st.columns([2, 1])
    scenario = selector.selectbox("سيناريو تحليل الأثر", list(LABELS),
                            format_func=lambda name: LABELS[name], key="eco_scenario")
    subset = [event for event in events if event["scenario"] == scenario]
    index = event_selector.select_slider("الحدث في السيناريو", options=list(range(1, len(subset) + 1)),
                             key=f"eco_event_{scenario}") if len(subset) > 1 else 1
    event = subset[index - 1]
    outcome = evaluate(event)
    # These are presentation assumptions, deliberately not inferred from speed or risk.
    presets = {"TRUCK_OVERHEIGHT": (20, 50), "CHILD_CROSSING": (20, 35),
               "AMBULANCE": (40, 30), "CONGESTION": (55, 40),
               "NORMAL": (20, 20), "CLOUD_OFFLINE": (20, 20)}
    if st.session_state.get("eco_assumption_scenario") != scenario:
        before, after = presets[scenario]
        st.session_state.update(eco_assumption_scenario=scenario, eco_before=before,
                                eco_after=after, eco_vehicles=12)
    with st.expander("افتراضات المقارنة ومراجع الرسم", expanded=False):
        st.caption("هذه مدخلات افتراضية للعرض، وليست نتائج خوارزمية تحسين الإشارات أو قياسات كاميرا. تغييرها لا يغيّر قرار المحرك.")
        a, b, c = st.columns(3)
        vehicles = a.number_input("عدد المركبات المفترض", min_value=0, max_value=500, step=1, key="eco_vehicles")
        before_s = b.number_input("انتظار الأساس لكل مركبة (ث)", min_value=0, max_value=600, step=5, key="eco_before")
        after_s = c.number_input("الانتظار مع القرار (ث)", min_value=0, max_value=600, step=5, key="eco_after")
        d, e = st.columns(2)
        idle = d.number_input("استهلاك التوقف (لتر/ساعة/مركبة)", min_value=0.0, max_value=10.0, value=1.0, step=0.1, key="eco_idle")
        factor = e.number_input("عامل CO₂ (كغ/لتر)", min_value=0.0, max_value=5.0, value=2.348, step=0.01, format="%.3f", key="eco_factor")
        st.caption("الوقود = المركبات × متوسط الانتظار ÷ 3600 × استهلاك التوقف. CO₂ = الوقود × عامل الانبعاث. القيم الافتراضية مستمدة من معاملات ملف EcoTwin المرجعي، وليست معايرة لأسطول محلي.")
        st.caption("مراجع القطاعات: خطر القرار 75/100، الجسر 4.5 م؛ وللمقارنة البصرية فقط: انتظار 60 ث، وقود 0.2 لتر، CO₂ بمقدار 469.6 غ. مراجع البيئة ليست حدود سلامة أو حدودًا كوكبية.")
    assumptions = dict(vehicles=vehicles, before_s=before_s, after_s=after_s,
                       idle_lph=idle, co2_kg_per_l=factor)
    st.caption(f"الحدث: {event.get('event_id', index)} · {outcome['level']} · الحركة عرض متدرج للنتائج من 0 إلى 100%، وليست تسجيلًا أو توقعًا مروريًا.")
    if outcome["level"] == "BRIDGE_CRITICAL":
        st.error("الشاحنة تتجاوز ارتفاع الجسر! قرار حماية الجسر له الأولوية.")
    elif outcome["level"] in ("CRITICAL", "WARNING"):
        st.error("تنبيه المشاة مستمر. لا تسمح المقارنة البيئية بتجاوز قرار الحماية.")
    with st.container(key="eco_frame"):
        components.html(eco_html(eco_payload(event, outcome, assumptions)), height=900, scrolling=True)


if __name__ == "__main__":
    main()
