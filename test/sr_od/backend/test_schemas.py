from dataclasses import asdict, fields

from one_dragon.base.screen.screen_match import (
    AreaMatchDetail,
    AreaType,
    ScreenMatch,
    UnmatchedArea,
    UnmatchedReason,
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


def test_analyze_result_has_screens_field() -> None:
    """AnalyzeScreenResult 含 screens 字段,可装 ScreenMatch 列表。"""
    detail = AreaMatchDetail(area_name='标题', area_type=AreaType.TEXT,
                             x=1, y=1, width=1, height=1, text='菜单')
    match = ScreenMatch(screen_name='菜单', is_precise=True, areas=[detail])
    r = AnalyzeScreenResult(success=True, ocr_texts=[], screens=[match], error=None)
    assert r.success is True
    assert len(r.screens) == 1
    assert r.screens[0].screen_name == '菜单'


def test_analyze_result_asdict_nested_serializable() -> None:
    """asdict 递归嵌套 dataclass + str Enum,可序列化(area_type 序列化为 'text')。"""
    detail = AreaMatchDetail(area_name='标题', area_type=AreaType.TEXT,
                             x=1, y=1, width=1, height=1, text='菜单')
    match = ScreenMatch(screen_name='菜单', is_precise=True, areas=[detail])
    r = AnalyzeScreenResult(success=True, ocr_texts=[], screens=[match], error=None)
    d = asdict(r)
    assert d['screens'][0]['areas'][0]['area_type'] == 'text'  # str Enum 序列化为 .value 字符串(asdict 后保留 Enum 实例, == 'text' 验证 str 值非枚举自比)


def test_analyze_result_asdict_unmatched_areas() -> None:
    """精准命中 ScreenMatch 的 unmatched_areas 可序列化:reason 序列化为 'no_method'/'sub_state'。"""
    detail = AreaMatchDetail(area_name='标题', area_type=AreaType.TEXT,
                             x=1, y=1, width=1, height=1, text='菜单')
    unmatched = [
        UnmatchedArea(area_name='点击区', reason=UnmatchedReason.NO_METHOD,
                      pc_rect=[10, 20, 110, 120]),
        UnmatchedArea(area_name='开关态', reason=UnmatchedReason.SUB_STATE,
                      pc_rect=[0, 0, 50, 50], text='已开启'),
    ]
    match = ScreenMatch(screen_name='菜单', is_precise=True, areas=[detail],
                        unmatched_areas=unmatched)
    r = AnalyzeScreenResult(success=True, ocr_texts=[], screens=[match], error=None)
    d = asdict(r)
    um = d['screens'][0]['unmatched_areas']
    assert len(um) == 2
    assert um[0]['reason'] == 'no_method' and um[0]['pc_rect'] == [10, 20, 110, 120]
    assert um[1]['reason'] == 'sub_state' and um[1]['text'] == '已开启'


def test_run_status_result_fields() -> None:
    """校验 RunStatusResult 的字段集合。"""
    names = {f.name for f in fields(RunStatusResult)}
    assert names == {
        'state', 'source', 'app', 'started_at', 'duration_seconds',
        'current_node', 'retry_count', 'last_status', 'failed_node',
    }


# (2026-09-03 攻击性排查:test_run_status_result_defaults /
#  test_analyze_result_default_screenshot_path_none 删除——默认值透传。)
