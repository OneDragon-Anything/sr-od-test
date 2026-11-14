from dataclasses import asdict, fields

from one_dragon.base.screen.screen_match import (
    AreaMatchDetail,
    ScreenMatch,
)
from sr_od.backend.schemas import (
    AnalyzeScreenResult,
    RunStatusResult,
    WindowStatus,
)

# (2026-09-03 攻击性排查:OcrText 字段透传/RunStatus 默认值/error 与
#  screenshot_path 默认值四条删除——dataclass 透传断言(纪律 18);
#  线格式由字段集登记门 + asdict 序列化锁管辖。)


def test_window_status_optional_rect() -> None:
    """校验 WindowStatus 的窗口矩形字段可选，缺省为 None。"""
    w = WindowStatus(win_title="星穹铁道", is_win_valid=True, is_win_active=True, is_win_scale=True)
    assert w.x is None
    assert w.width is None
    w2 = WindowStatus(win_title="t", is_win_valid=True, is_win_active=False, is_win_scale=True, x=1, y=2, width=3, height=4)
    assert (w2.x, w2.y, w2.width, w2.height) == (1, 2, 3, 4)


def test_analyze_result_asdict_nested_serializable() -> None:
    """asdict 递归嵌套 dataclass,可序列化;AreaMatchDetail 四字段进 JSON。"""
    detail = AreaMatchDetail(area_name='标题', pc_rect=[1, 1, 2, 2],
                             matched_text='菜单', match_target='菜单')
    match = ScreenMatch(screen_name='菜单', is_precise=True, areas=[detail])
    r = AnalyzeScreenResult(ocr_texts=[], screens=[match])
    d = asdict(r)
    assert d['screens'][0]['areas'][0]['area_name'] == '标题'
    assert d['screens'][0]['areas'][0]['match_target'] == '菜单'


def test_run_status_result_fields() -> None:
    """校验 RunStatusResult 的字段集合。"""
    names = {f.name for f in fields(RunStatusResult)}
    assert names == {
        'state', 'source', 'app', 'started_at', 'duration_seconds',
        'current_node', 'retry_count', 'last_status', 'failed_node',
    }


# (2026-09-03 攻击性排查:test_run_status_result_defaults /
#  test_analyze_result_default_screenshot_path_none 删除——默认值透传。)
