"""Build the explicit deliverable set, excluding dependencies and live status."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent
SOURCES = [(name, 'python') for name in (
    'engine.py', 'vision_serial_bridge.py', 'dashboard.py', 'dashboard_visuals.py',
    'ecotwin.py', 'hardware_check.py', 'safety_workflow.py', 'site_geometry.py',
    'roadguardian_views.py', 'tabletop_demo.py', 'traffic_simulation.py', 'review_project.py', 'package_release.py', 'build_pages.py')]
SOURCES += [('assets/dashboard.css', 'css'), ('assets/ecotwin.html', 'html'), ('assets/traffic_simulation.html', 'html'),
            ('.streamlit/config.toml', 'toml'), ('esp32_controller.ino', 'cpp'),
            ('requirements.txt', 'text'), ('requirements-dashboard.txt', 'text'),
            ('site.example.json', 'json'), ('road_region.example.json', 'json'),
            ('start_camera_check.ps1', 'powershell')]


def main():
    parts = ['# RoadGuardian AI — Complete source code\n\n'
             'Extract the complete ZIP to retain assets, local WOFF2 fonts and .streamlit/config.toml. '
             'The dashboard requires dashboard_visuals.py, ecotwin.py and both HTML/CSS assets. '
             'EcoTwin is a read-only illustrative impact model; it never changes safety decisions.\n']
    for name, language in SOURCES:
        parts.append(f'\n## {name}\n\n```{language}\n'
                     + (ROOT / name).read_text(encoding='utf-8').rstrip() + '\n```\n')
    (ROOT / 'COMPLETE_CODE.md').write_text(''.join(parts), encoding='utf-8')
    files = [name for name, _ in SOURCES] + [
        'events.csv', 'README.md', 'PHYSICAL_DEMO.md', 'DESIGN_NOTES.md',
        'COMPLETE_CODE.md', 'test_engine.py', 'test_dashboard.py', 'test_ecotwin.py',
        'test_hardware_check.py', 'test_audit.py', 'test_safety_workflow.py', 'PEDESTRIAN_FIRST.md',
        'ACCEPTANCE_REVIEW.md', 'test_tabletop_demo.py',
        'test_release.py', 'test_pages.py', 'test_traffic_simulation.py', 'GITHUB_READY.md', 'THIRD_PARTY_NOTICES.md',
        '.gitignore', '.github/workflows/ci.yml',
        'assets/IBMPlexSansArabic-Regular.woff2', 'assets/IBMPlexSansArabic-SemiBold.woff2',
        'assets/FONT-LICENSE.txt']
    # No personal photos, recordings or local road calibration in release.
    for name in ('docs/images/dashboard.png', 'docs/images/ecotwin.png', 'docs/images/congestion.png', 'reports/test-summary.json'):
        if (ROOT / name).exists():
            files.append(name)
    files += ['docs/index.html', 'docs/.nojekyll', 'docs/font.woff2', 'docs/FONT-LICENSE.txt']
    files += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / 'docs/scenes').glob('*.html'))]
    output = ROOT / 'RoadGuardian_AI_Edge_Package.zip'
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for name in files:
            archive.write(ROOT / name, name)
        archive.write(ROOT / 'esp32_controller.ino', 'esp32_controller/esp32_controller.ino')
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        for name in files:
            assert archive.read(name) == (ROOT / name).read_bytes(), name
    print(f'Verified {len(files) + 1} packaged files.')


if __name__ == '__main__':
    main()
