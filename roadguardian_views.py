"""Arabic presentation and verification views; no hardware control here."""
import csv
from datetime import datetime, timezone
import io
import time

import streamlit as st
from engine import evaluate
from safety_workflow import CrossingDemo, stopping_distance, validation_metrics

BRIDGE_VIEW = "حماية الجسور · BridgeShield"
RESPONSE_VIEW = "تسلسل الاستجابة"
VALIDATION_VIEW = "التحقق والقياسات"


def mission_banner():
    st.html('<section class="mission-grid"><div class="mission-primary">'
            '<span class="eyebrow">01 / SAFECROSS · التطبيق الرئيسي</span>'
            '<h2>نرصد الخطر قبل عبور المشاة</h2>'
            '<p>رصد منطقة الانتظار والمعبر واقتراب المركبات، ثم إنذار محلي. '
            'طلب العبور خطوة مستقلة عن السماح به.</p></div>'
            '<div class="mission-secondary"><span class="eyebrow">02 / BRIDGESHIELD</span>'
            '<h3>نفس المنصة، حماية للجسور</h3><p>تحذير الشاحنات المرتفعة قبل نقطة الخطر. '
            'القياس الميداني يحتاج حساس ارتفاع مستقلًا.</p></div></section>')


def provenance(event, simulated, state):
    site = event.get("site_configured") is True
    st.caption("مصدر القياسات: " + ("بيانات اصطناعية للعرض" if simulated else
               "كاميرا · أبعاد تقديرية من معايرة مستوى الأرض") +
               " · ثقة الكشف ليست دقة مثبتة باختبارات.")
    if not simulated:
        st.caption("مناطق الموقع: " + ("محددة بملف معايرة محلي" if site else
                   "غير معايرة بعد؛ زمن التقارب الحالي بين الأجسام وليس زمن الوصول إلى المعبر"))
        value = event.get("time_to_crosswalk_s")
        if site:
            st.info("زمن وصول المركبة إلى حد المعبر: " +
                    (f"{value:.2f} ثانية تقديرية" if isinstance(value, (float, int)) and not isinstance(value, bool) else
                     "غير متاح؛ يلزم تتبع اقتراب صالح"))
        st.caption("إقرار ESP32 يؤكد استقبال الأمر؛ لا يثبت توقف المركبات أو إضاءة المصباح فعليًا.")
    if event.get("truck_present") in (True, 1, "1", "True", "true"):
        st.caption("مصدر ارتفاع الشاحنة: " + ("قيمة محاكاة" if simulated else "تقدير بصري") +
                   " · حساس ارتفاع مستقل: غير مربوط حاليًا.")
    st.info("تنبيه السائق والمشاة لا يعني السماح بالعبور. لا توجد وحدة تحكم مرورية معتمدة متصلة بالمنصة.")


def response_view(simulated):
    st.write("كشف الخطر ← تحذير محلي ← طلب مرحلة عبور ← تأكيد وحدة التحكم ← عبور ثم إخلاء.")
    if not simulated:
        st.session_state.pop("crossing_demo", None)
        st.warning("الرؤية الحية تُصدر إنذارًا فقط. تجربة طلب العبور وتأكيده متاحة في وضع المحاكاة.")
        return
    st.caption("محاكي تعليمي منفصل عن ESP32. الأوقات هنا توضيحية وليست توقيتات لإشارة حقيقية. "
               "غياب أجسام في الصورة لا يفتح مرحلة العبور.")
    if "crossing_demo" not in st.session_state:
        st.session_state.crossing_demo = CrossingDemo()

    def advance(action):
        st.session_state.crossing_demo = st.session_state.crossing_demo.step(action, time.monotonic())

    @st.fragment(run_every=1.0)
    def workflow():
        current = st.session_state.crossing_demo.step("tick", time.monotonic())
        st.session_state.crossing_demo = current
        labels = {"IDLE": "مراقبة · لا يوجد إذن عبور", "REQUESTED": "طلب مرسل · انتظار تأكيد وحدة التحكم",
                  "WALK_DEMO": "مرحلة عبور في المحاكاة فقط", "CLEARANCE": "إخلاء المعبر · انتظار إعادة الدورة",
                  "FAULT": "تعطل أو تعارض · لا يوجد إذن عبور"}
        phase = current.phase
        st.html(f'<div class="workflow-status"><span class="eyebrow">SIMULATED CONTROLLER</span>'
                f'<h2>{labels[phase]}</h2><p>حالة المحاكي: <bdi>{phase}</bdi></p></div>')
        cols = st.columns(4)
        for col, (name, text) in zip(cols, [
            ("01 · رصد", "وجود المشاة يطلق التقييم، ولا يفتح العبور."),
            ("02 · تنبيه وطلب", "تحذير السائق والمشاة ثم طلب مرحلة آمنة."),
            ("03 · تأكيد", "تأكيد محاكى بعد الانتقال؛ ليس إقرار Serial."),
            ("04 · إخلاء", "إنهاء العبور ثم الإخلاء قبل دورة المركبات.")]):
            col.markdown(f"**{name}**\n\n{text}")
        elapsed = time.monotonic() - current.since
        a, b, c = st.columns(3)
        a.button("اكتشاف مشاة وإرسال طلب", key="request_crossing", disabled=phase != "IDLE",
                 on_click=advance, args=("request",), width="stretch")
        b.button("محاكاة تأكيد وحدة التحكم", key="confirm_crossing",
                 disabled=phase != "REQUESTED" or elapsed < 3,
                 on_click=advance, args=("confirm",), width="stretch", type="primary")
        c.button("إنهاء مرحلة العبور", key="finish_crossing", disabled=phase != "WALK_DEMO",
                 on_click=advance, args=("finish",), width="stretch")
        a, b, c = st.columns(3)
        a.button("اكتمال الإخلاء", key="release_crossing", disabled=phase != "CLEARANCE" or elapsed < 4,
                 on_click=advance, args=("release",), width="stretch")
        b.button("محاكاة عطل أو مركبة مخالفة", key="fault_crossing",
                 on_click=advance, args=("fault",), width="stretch")
        c.button("إعادة ضبط التجربة", key="reset_crossing", on_click=advance, args=("reset",), width="stretch")
        if phase == "REQUESTED":
            st.warning("انتظار انتقال توضيحي 3 ثوانٍ، ثم تأكيد يدوي قبل انتهاء مهلة 15 ثانية. لا يوجد سماح تلقائي.")
        elif phase == "FAULT":
            st.error("أُلغي السماح التجريبي. افحص سبب العطل ثم أعد ضبط التجربة.")
        elif phase == "WALK_DEMO":
            st.info("هذا تأكيد محاكى فقط؛ تستمر مراقبة المركبات المخالفة. لا يُرسل أمر أخضر إلى العتاد.")
        elif phase == "CLEARANCE":
            st.warning("انتظار إخلاء توضيحي 4 ثوانٍ ثم تأكيد اكتماله يدويًا.")
    workflow()


def bridge_view(simulated, show_outcome, read_status):
    st.caption("التطبيق الثاني · بوابة كشف قبل الجسر · حساس ارتفاع + كاميرا تصنيف في التصميم الميداني.")
    if not simulated:
        @st.fragment(run_every=1.0)
        def live_bridge():
            state, error = read_status()
            if error or not state.get("edge_active"):
                st.info("بانتظار بيانات الكاميرا. لم يُربط حساس ارتفاع مستقل بعد.")
            else:
                show_outcome(state["event"], state["outcome"], False, state)
                st.warning("لا يوجد مسار بديل ميداني معتمد أو موصول بالنظام. عند التحذير يلزم التوقف قبل الخطر وفق تنظيم الموقع.")
        live_bridge()
        return
    height = st.number_input("ارتفاع الشاحنة المكافئ في المحاكاة (م)", min_value=0.1, max_value=8.0,
                             value=5.0, step=0.1, key="bridge_demo_height")
    route = st.checkbox("إظهار مسار بديل محدد مسبقًا داخل المجسم", key="demo_route", value=True)
    event = dict(distance_m=40, relative_speed_kmh=30, pedestrian_present=False,
                 ambulance_present=False, cloud_online=False, model_confidence=0.95,
                 truck_present=True, truck_height_m=height, scenario="TRUCK_OVERHEIGHT",
                 event_id="BRIDGE-DEMO", scene_scale=20, truck_height_physical_m=height / 20)
    result = evaluate(event)
    show_outcome(event, result)
    if result["level"] == "BRIDGE_CRITICAL":
        st.error("توقف — جسر منخفض. التحويل لا يلغي إنذار الارتفاع.")
        if route:
            st.html('<div class="route-card"><span class="eyebrow">MODEL ROUTE B / مسار توضيحي</span>'
                    '<h3>بوابة الكشف ← نقطة توقف ← المسار B حول الجسر</h3>'
                    '<p>مسار محدد مسبقًا للعرض داخل المجسم؛ ليس اقتراح ملاحة أو اعتمادًا لصلاحية طريق حقيقي.</p></div>')
        else:
            st.warning("لا يوجد مسار بديل في هذا المشهد: توقف قبل نقطة الخطر واطلب توجيه الجهة المختصة.")
    with st.expander("حاسبة تقديرية لمسافة الكشف والإنذار"):
        st.caption("مثال الدكتورة لحركة مستقيمة على طريق مستوٍ. القيم مفترضة؛ يلزم تصميم هندسي للموقع الحقيقي.")
        a, b = st.columns(2)
        speed = a.number_input("سرعة الشاحنة (كم/ساعة)", 0.0, 150.0, 60.0, key="stop_speed")
        response = b.number_input("زمن استجابة النظام والسائق (ث)", 0.0, 20.0, 2.5, key="stop_response")
        deceleration = a.number_input("التباطؤ المفترض (م/ث²)", 0.1, 10.0, 3.0, key="stop_decel")
        margin = b.number_input("هامش الأمان (م)", 0.0, 500.0, 30.0, key="stop_margin")
        distance = stopping_distance(speed, response, deceleration, margin)
        st.metric("مسافة الكشف والإنذار التقديرية", f"{distance:.1f} m")
        st.code("D = v × t + v² / (2 × a) + margin     v = km/h ÷ 3.6")
        st.caption("هذه المسافة من الحساب المفترض، وليست مسافة متبقية مقاسة بالكاميرا.")


def validation_view():
    st.info("هذه صفحة سجل الاختبارات للمراجعة ولجنة التحكيم: تسجّل ما حدث فعلًا، ثم تحسب صحة التنبيهات والإنذارات الكاذبة. لا تشغّل الكاميرا ولا اللمبات.")
    st.caption("مثال: اقتربت السيارة من الخط وأضاء الأحمر → سجّل تجربة مادية ونتيجتها. إذا لم تختبر حالة بعد، اتركها غير محسومة. نزّل CSV لحفظ السجل قبل إغلاق الجلسة.")
    st.write("سجل التجارب المرجعية: هل كان هناك خطر فعلًا؟ وهل صدر الإنذار الصحيح؟")
    st.caption("السجل يدوي داخل جلسة المتصفح؛ صدّره قبل الإغلاق. لا تُملأ النتائج تلقائيًا من ثقة YOLO، "
               "ولا تُخلط المحاكاة مع الاختبارات المادية.")
    rows = st.session_state.setdefault("validation_rows", [])
    with st.form("trial_form", clear_on_submit=False):
        a, b = st.columns(2)
        kind = a.selectbox("نوع التجربة", ["محاكاة برمجية", "اختبار مادي"], key="trial_kind")
        scenario = b.selectbox("المشهد المختبر", ["المشاة", "الجسر", "المسار البديل", "انقطاع الإنترنت"], key="trial_scene")
        expected = a.selectbox("الحقيقة المرجعية حسب المراقب", ["خطر يستوجب التنبيه", "لا يوجد خطر", "غير محسوم"], key="trial_expected")
        observed = b.selectbox("الاستجابة المرصودة", ["غير محسوم", "صدر إنذار الخطر الصحيح", "لم يصدر إنذار الخطر"], key="trial_observed")
        notes = st.text_input("مرجع التجربة والملاحظات (رقم فيديو أو وصف الإعداد)", key="trial_notes")
        measured = st.checkbox("لدي قياس موثق للزمن من ظهور الخطر إلى التنبيه الفعلي", key="trial_measured")
        delay = st.number_input("زمن التنبيه المقاس (ms)", min_value=0.0, value=0.0, key="trial_delay")
        st.caption("الأحمر الاحترازي بسبب غياب القياسات ليس كشفًا ناجحًا للخطر. "
                   "زمن معالجة الإطار وإقرار Serial ليسا زمن ظهور الإنذار الفعلي.")
        submit = st.form_submit_button("تسجيل التجربة", type="primary")
        if submit:
            if not notes.strip():
                st.error("أدخل مرجعًا أو وصفًا للتجربة حتى تكون النتيجة قابلة للمراجعة.")
            elif measured and (delay <= 0 or expected != "خطر يستوجب التنبيه" or observed != "صدر إنذار الخطر الصحيح"):
                st.error("الزمن الموثق يجب أن يكون موجبًا لتجربة خطر صدر فيها الإنذار الصحيح.")
            else:
                rows.append(dict(id=len(rows) + 1, recorded_at=datetime.now(timezone.utc).isoformat(),
                                 kind=kind, scenario=scenario,
                                 expected={"خطر يستوجب التنبيه": True, "لا يوجد خطر": False, "غير محسوم": None}[expected],
                                 observed={"صدر إنذار الخطر الصحيح": True, "لم يصدر إنذار الخطر": False, "غير محسوم": None}[observed],
                                 alert_ms=delay if measured else None, notes=notes.strip()))
                st.success("سُجلت النتيجة اليدوية؛ صدّر السجل لحفظها.")
    selected = st.radio("عرض نتائج", ["اختبار مادي", "محاكاة برمجية"], horizontal=True, key="trial_filter")
    filtered = [r for r in rows if r["kind"] == selected]
    metrics = validation_metrics(filtered)
    def percent(value):
        return "—" if value is None else f"{value * 100:.1f}%"
    a, b, c, d = st.columns(4)
    a.metric("تجارب محسومة", str(metrics["n"]))
    b.metric("صحة قرار التنبيه", percent(metrics["accuracy"]))
    c.metric("معدل الإنذار الكاذب", percent(metrics["false_alarm_rate"]))
    d.metric("معدل كشف حالات الخطر", percent(metrics["recall"]))
    st.caption(f"نتائج غير محسومة مستبعدة: {metrics['excluded']} · حالات الخطر الفائتة: {metrics['fn']} · "
               f"التجارب الموقّتة: {metrics['timed_trials']}")
    if metrics["mean_alert_ms"] is not None:
        st.metric("متوسط زمن التنبيه الموثق يدويًا", f"{metrics['mean_alert_ms']:.1f} ms")
    st.caption("صحة القرار = (التنبيهات الصحيحة + الحالات السليمة الصحيحة) ÷ التجارب المحسومة. "
               "الإنذار الكاذب = إنذارات الحالات السليمة ÷ الحالات السليمة. هذه مقاييس على مستوى التجربة وليست دقة كشف الأجسام.")
    if not filtered:
        st.info("لا توجد نتائج مسجلة لهذا النوع بعد. الأرقام غير المتاحة تظهر بشرطة ولا تُحسب صفرًا.")
    else:
        st.dataframe(filtered, hide_index=True, width="stretch")
    if rows:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            # Export text safely for spreadsheets (avoid formula injection).
            writer.writerow({k: ("'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v)
                             for k, v in row.items()})
        st.download_button("تنزيل سجل التجارب CSV", buffer.getvalue().encode("utf-8-sig"),
                           "roadguardian_trials.csv", "text/csv")
