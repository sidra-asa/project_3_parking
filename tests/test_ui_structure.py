"""Checks for the navigation and page contracts of the course project UI."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'app' / 'templates'
SCRIPTS = ROOT / 'app' / 'static' / 'js'


def test_navigation_uses_business_labels():
    html = (TEMPLATES / 'base.html').read_text(encoding='utf-8')
    for name in ('總覽', '統計分析', '停車管理', '系統管理'):
        assert name in html
    assert 'project_3_parking' not in html
    assert '延伸分析' not in html


def test_analysis_page_contains_all_chart_targets():
    html = (TEMPLATES / 'advanced_analytics.html').read_text(encoding='utf-8')
    script = (SCRIPTS / 'advanced_analytics.js').read_text(encoding='utf-8')
    assert '固定比較 2026/6/1–6/14 與 6/15–6/28' in html
    for chart in ('chartIdentity', 'chartHourPhase', 'durationChart',
                  'chartPeak', 'revenueChart'):
        assert f'id="{chart}"' in html
        assert chart in script
    assert 'snapshotAt' in html and 'occupancyList' in html


def test_overview_is_summary_first():
    html = (TEMPLATES / 'dashboard.html').read_text(encoding='utf-8')
    assert '每日進場車次' in html
    assert 'chartDaily' in html
    assert 'chartPeak' not in html
    assert '停車證與收費' not in html


def test_pending_lists_link_to_management():
    script = (SCRIPTS / 'management_review.js').read_text(encoding='utf-8')
    assert 'encodeURIComponent(item.plate_no)' in script
    assert '停車證' in (TEMPLATES / 'management_review.html').read_text(encoding='utf-8')


def test_permit_flows_and_record_entry_are_explicit():
    script = (SCRIPTS / 'resource.js').read_text(encoding='utf-8')
    assert '既有車輛續辦' in script
    assert '新車首次申辦' in script
    assert "!['exit_time','permit_id'].includes" in script
    assert "resource==='vehicles'" in script
