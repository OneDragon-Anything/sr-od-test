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


def test_analyze_result_pc_alt_defaults_false() -> None:
    """pc_alt 字段默认 False:dataclass 与输出模型不传时均为 False(现有构造点兼容)。"""
    from sr_od.backend.schemas import AnalyzeScreenOut

    r = AnalyzeScreenResult(ocr_texts=[], screens=[])
    assert r.pc_alt is False
    assert AnalyzeScreenOut().pc_alt is False


def test_run_status_result_fields() -> None:
    """校验 RunStatusResult 的字段集合。"""
    names = {f.name for f in fields(RunStatusResult)}
    assert names == {
        'state', 'source', 'app', 'started_at', 'duration_seconds',
        'current_op', 'current_node', 'retry_count', 'current_screen',
        'last_status', 'failed_node',
    }


# (2026-09-03 攻击性排查:test_run_status_result_defaults /
#  test_analyze_result_default_screenshot_path_none 删除——默认值透传。)
