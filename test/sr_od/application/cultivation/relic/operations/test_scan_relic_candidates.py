"""ScanRelicCandidatesOp 流程测试(入口前置拦截 / 单屏扫描档案 / 合并语义)。

fixture 帧:替换屏 default(建议排序态,入口拦截剧本)+ 排序方向反转列表
(静态排序态,扫描剧本;黑塔头部列表 20 卡,末行满 4 列)。

分层:
- 入口拦截与合并语义为快测(合并语义用构造清单桩 recognize_for_pos);
- 扫描剧本跑真 TM 识别(20 卡 × 部位模板库,实测慢,登记 slow_marks),
  详情读取桩掉(词缀解析真实性由 test_relic_detail_reader 两帧单测锁,
  本文件锁点选序列与档案合并/bottom 判定)。
"""

import json
from types import SimpleNamespace

import pytest

import sr_od.application.cultivation.relic.operations.scan_relic_candidates as scan_mod
from sr_od.application.cultivation.relic.operations.scan_relic_candidates import (
    ScanRelicCandidatesOp,
)
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    reset_running_state,
    fast_sleep,
)

_TAB_FRAME = ('角色-遗器', 'default')
_REPLACE_FRAME = ('遗器-替换', 'default')
_STATIC_FRAME = ('遗器-替换', '排序方向反转列表')


class _WatchedScan(WatchdogOperationMixin, ScanRelicCandidatesOp):
    """带看门狗的流程测试 op(轮次超限自动停,防剧本错配死循环)。"""

    watchdog_max_rounds: int = 60

    def __init__(self, ctx: SrTestContext, pos: int = 1,
                 expected_character: str | None = None) -> None:
        ScanRelicCandidatesOp.__init__(self, ctx, pos=pos,
                                       expected_character=expected_character)
        self.need_check_game_win = False  # execute 期才读,实例属性即可关掉


@pytest.fixture()
def fixture_controller(
    test_context: SrTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> FixtureController:
    ctrl = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    monkeypatch.setattr(ctrl, 'mouse_move', lambda pos: None, raising=False)
    return ctrl


def _require_screens(test_context: SrTestContext, frames: list[tuple[str, str]]) -> None:
    for frame in frames:
        if not test_context.has_screen(*frame):
            pytest.skip(f'存档截图缺失:screens/{frame[0]}/{frame[1]}.webp')


def _run_op(test_context: SrTestContext, op: ScanRelicCandidatesOp):
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            return op.execute()
    finally:
        reset_running_state(test_context, op)


def test_entry_rejects_suggested_sort(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """建议排序开着的替换屏(替换屏 default 帧,摘要=「遗器建议排序」)→
    入口显式失败(动态重排下点选→读取漂移,EquipRelicOp 已档教训)。"""
    _require_screens(test_context, [_REPLACE_FRAME])
    fixture_controller.set_phases([{'frame': _REPLACE_FRAME}])
    op = _WatchedScan(test_context, pos=1)
    result = _run_op(test_context, op)

    assert not result.success, '建议排序态应入口拦截'
    assert '建议排序' in (result.status or ''), \
        f'失败原因应指向排序前置:{result.status!r}'
    assert fixture_controller.recorded_clicks == [], \
        f'入口拦截不应有卡点选:{fixture_controller.recorded_clicks}'


def test_scan_produces_candidates_and_bottom(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """静态排序帧(排序方向反转列表,黑塔头部 20 卡)单屏扫描:逐卡点选、
    详情桩值入档、bottom_reached=False(末行满 4 列)。"""
    _require_screens(test_context, [_STATIC_FRAME])

    detail_calls: list[tuple[int, int]] = []

    def fake_read_detail(ctx, screen=None):
        detail_calls.append((0, 0))
        return {
            'piece': f'详情桩件名{len(detail_calls)}',
            'pos_cn': '头部', 'level': 15,
            'main': {'name': '生命值', 'stat': '生命值', 'value': '705'},
            'subs': [{'name': '暴击率', 'stat': '暴击率', 'value': '9.3%',
                      'times': 2, 'times_confirmed': True}],
        }

    monkeypatch.setattr(scan_mod, 'read_detail', fake_read_detail)

    fixture_controller.set_phases([{'frame': _STATIC_FRAME}])
    op = _WatchedScan(test_context, pos=1, expected_character='黑塔')
    result = _run_op(test_context, op)

    assert result.success, f'扫描未成功:status={result.status!r}'
    assert result.status == 'SCANNED'
    archive = json.loads(result.data)
    assert archive['pos'] == 1
    # 帧实况(识别器标定):该帧列表处于滚动态,视口底行被裁切 → 19 卡、
    # 末行带 3 卡(<4 列)→ bottom_reached=True 是正确判定(调用方滚动续扫
    # 自会确认是否真到底;识别与判定对帧诚实,不猜测)
    assert archive['bottom_reached'] is True
    candidates = archive['candidates']
    assert len(candidates) == 19, f'帧实况 19 卡:{len(candidates)}'
    first = candidates[0]
    assert set(first.keys()) == {'cell', 'piece', 'set', 'pos_cn', 'level',
                                 'owner', 'main', 'subs', 'times_confirmed'}, \
        f'候选档案字段面不符:{sorted(first.keys())}'
    assert first['piece'] == '详情桩件名1', '件名应以详情 OCR 为准(桩值覆盖 TM)'
    assert first['times_confirmed'] is True
    # 逐卡点选 = 每卡一次点击,点击均落列表区内(不触右侧详情/底部按钮)
    assert len(fixture_controller.recorded_clicks) == len(candidates), \
        f'点选次数应等于候选数:{len(fixture_controller.recorded_clicks)}'


def test_detail_none_falls_back_to_tm_and_masked_priority(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """合并语义(构造清单桩 recognize,快测):详情读到 = 详情件名优先
    (masked 卡 TM 身份 None 也入档);详情读不到 = 退 TM 先验 + 无词缀
    数据标 times_confirmed=False(约束判定按不满足)。"""
    _require_screens(test_context, [_STATIC_FRAME])
    items = [
        {'cell': [39, 180, 159, 340], 'piece': None, 'level': 15,
         'owner': '黑塔', 'identity': 'masked'},  # masked:TM 不判
        {'cell': [162, 180, 282, 340], 'piece': '雪猎的荒神兜帽', 'level': 15,
         'owner': None, 'identity': 'tm(0.978)', 'set': '密林卧雪的猎人',
         'pos_cn': '头部'},
    ]

    class _FakeRecognizer:
        def _detect_pos_from_tabs(self, ctx, image):
            return 1

        def recognize_for_pos(self, ctx, image, pos):
            return {'items': items, 'total_cards': len(items)}

    monkeypatch.setattr(scan_mod, 'RelicReplaceRecognizer', _FakeRecognizer)
    # 详情两次调用:第一次读到(masked 卡,详情件名桩值),第二次 None(fallback)
    detail_returns = [
        {'piece': '重掷遮罩卡的详情件名', 'pos_cn': '头部', 'level': 15,
         'main': {'name': '生命值', 'stat': '生命值', 'value': '705'},
         'subs': [{'name': '暴击率', 'stat': '暴击率', 'value': '9.3%',
                   'times': 1, 'times_confirmed': False}]},  # 角标未确证
        None,
    ]
    monkeypatch.setattr(scan_mod, 'read_detail',
                        lambda ctx, screen=None: detail_returns.pop(0))

    fixture_controller.set_phases([{'frame': _STATIC_FRAME}])
    op = _WatchedScan(test_context, pos=1)
    result = _run_op(test_context, op)

    assert result.success, f'扫描未成功:{result.status!r}'
    archive = json.loads(result.data)
    masked, normal = archive['candidates'][0], archive['candidates'][1]
    # masked 卡:详情件名入档(F21 详情 OCR 为准,不依赖 TM 身份)
    assert masked['piece'] == '重掷遮罩卡的详情件名'
    assert masked['times_confirmed'] is False, '角标未确证行 → 候选级标记 False'
    # 详情读不到:退 TM 先验,subs 空 + times_confirmed False(无词缀数据)
    assert normal['piece'] == '雪猎的荒神兜帽'
    assert normal['subs'] == [] and normal['times_confirmed'] is False
    # 末行 1 卡(<4 列)→ bottom_reached=True
    assert archive['bottom_reached'] is True
