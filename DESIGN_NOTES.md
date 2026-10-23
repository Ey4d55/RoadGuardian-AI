# RoadGuardian interface

Direction: Arabic RTL operations dashboard, light workspace and navy right navigation.

- Local IBM Plex Sans Arabic regular/semibold; no font/CDN network dependency.
- Teal primary actions, red only for hazards. State labels accompany color.
- Native keyboard-accessible controls; visible focus, reduced-motion support.
- LTR isolation for metric values, identifiers and units; Arabic labels remain RTL.
- The road SVG is an explanatory schematic, explicitly labelled as such in both modes.
- Camera and ESP32 status derive from a fresh status snapshot and firmware ACK, never synthetic connectivity.
- Source selector, scenario controls, decision card, comparison page and setup guide remain functional.
- Responsive checks: 375px mobile, 768px tablet, 1440px desktop. Sidebar can collapse without hiding its reopening control.

UI UX Pro Max was used for dashboard style, hierarchy, contrast, feedback and responsive guidance. The returned marketing/enterprise-landing patterns were inappropriate and were not used. The operational grid is a task-specific design. Latin font suggestions were replaced by IBM's Arabic typeface.

Streamlit removes inline SVG from st.html, so audited local SVG strings are encoded into image data URLs. All variable external text is escaped; image fonts are embedded for offline consistency.
# تحديث حماية المشاة أولًا — 2026-10-19

أضيفت بطاقة رئيسية داكنة لـSafeCross وبطاقة ثانوية للجسور، مع بدء المشهد الافتراضي بالمشاة وعرض وجودهم بدل خانة ارتفاع فارغة. أضيفت صفحات الجسور والاستجابة والتحقق؛ بقي EcoTwin وحدة مساندة. حافظت الإضافات على RTL والخط المحلي والأرقام المعزولة وتخطيط البطاقات المتجاوب. صفحة الاستجابة تميز جميع مراحلها بأنها محاكاة، وصفحة التحقق لا تعرض قيم دقة بلا تجارب مرجعية.

