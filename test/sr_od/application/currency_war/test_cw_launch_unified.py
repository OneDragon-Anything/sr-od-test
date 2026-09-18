"""出战统一执行器(launch_battle_unified)直测:迭代
changes/2026-09-16-prep-visit-op landing 3.1 判据面。

出战执行路径现存测试锁 = 零(audit-executor.md §2.4 实证),本文件为首批:
- armed 全绿 → 事实返回,无调用面私有记账(失败语义分轨);
- stale(非备战屏) → (False, 'readiness_stale_screen') + 分键;
- 浮层命中(遭遇 OCR 兜底路径) → (False, 'readiness_overlay_hold:…') + 分键;
- resume 闩:首调部署原子序 + 置闩,次调跳过部署;
- 非法 face 拒绝;
- readiness_battle_launch 抽取 helper 后等价守卫(stale 形态同返回)。
"""

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war import prep_actions
from sr_od.application.currency_war.kernel.cw_vocab import CwActionStartBattleParam
from sr_od.application.currency_war.operations import cw_loop
from sr_od.application.currency_war.operations.cw_loop import (
    launch_battle_unified,
)

PREP_HITS = {('货币战争-备战', '备战标识-购买经验'),
             ('货币战争-备战', '按钮-出战')}


class _Frame:
    """一帧截图的桩:hits = 命中的 (画面名, 区名) 集合;ocr_hit = 遭遇 OCR。"""

    def __init__(self, hits=(), ocr_hit: bool = False) -> None:
        self.hits = set(hits)
        self.ocr_hit = ocr_hit


class _StubOp:
    """op 桩:脚本化帧序列 + 锚/OCR 应答(实现执行路径零真实点击)。"""

    def __init__(self, frames: list[_Frame]) -> None:
        self._frames = list(frames)

    def screenshot(self):
        return self._frames.pop(0)

    def round_by_find_area(self, screen, screen_name, area, crop_first=False):
        return SimpleNamespace(is_success=(screen_name, area) in screen.hits)

    def round_by_ocr(self, screen, text, lcs_percent=0.5):
        return SimpleNamespace(is_success=screen.ocr_hit)


class _StubExecutor:
    """PrepActionExecutor 替身:记录执行序列,CwActionStartBattleParam 置发射事实。"""

    instances: list['_StubExecutor'] = []

    def __init__(self, op, ctx) -> None:
        self.executed: list[object] = []
        self.last_launch_ok = False
        self.last_detail = ''
        _StubExecutor.instances.append(self)

    def execute(self, action) -> None:
        self.executed.append(action)
        if isinstance(action, CwActionStartBattleParam):
            self.last_launch_ok = True
            self.last_detail = 'stub 出战已点击'


@pytest.fixture()
def launch_env(monkeypatch):
    """公共桩:分键容器 + 部署计划桩 + 执行器替身 + 身份分发桩(逐测重置)。"""
    counters: dict[str, int] = {}
    state = SimpleNamespace(cw4_counters=counters, target_comp=None)
    monkeypatch.setattr(cw_loop, 'strategy_state_of', lambda s: state)
    monkeypatch.setattr(cw_loop, 'get_match_screen_name',
                        lambda ctx, screen, screen_name_list: None)
    deploy_calls: list[int] = []

    def _moves(session):
        deploy_calls.append(1)
        return [object(), object()]

    monkeypatch.setattr(cw_loop, '_battle_chain_deploy_moves', _moves)
    monkeypatch.setattr(prep_actions, 'PrepActionExecutor', _StubExecutor)
    _StubExecutor.instances = []
    ctx = SimpleNamespace(cw_match=SimpleNamespace(session=object()))
    return SimpleNamespace(counters=counters, ctx=ctx, deploy_calls=deploy_calls)


def test_unified_armed_green_and_fail_track_split(launch_env, monkeypatch) -> None:
    """armed 全绿:复验→浮层→部署原子序→CwActionStartBattleParam;失败记账不入执行器
    (readiness_launch_fail 归调用方,分轨判据)。"""
    monkeypatch.setattr(cw_loop, '_prep_anchors_hit',
                        lambda op, screen: PREP_HITS.issubset(screen.hits))
    op = _StubOp([_Frame(hits=PREP_HITS)])
    ok, detail = launch_battle_unified(op, launch_env.ctx, face='armed')
    assert ok is True and '出战' in detail
    assert len(_StubExecutor.instances) == 1
    assert any(isinstance(a, CwActionStartBattleParam)
               for a in _StubExecutor.instances[0].executed)
    assert 'readiness_launch_fail' not in launch_env.counters, '分轨:记账归调用方'


def test_unified_stale_rejects(launch_env) -> None:
    """stale:非备战屏 → (False, 'readiness_stale_screen') + 分键,零执行。"""
    op = _StubOp([_Frame(hits=set())])
    ok, detail = launch_battle_unified(op, launch_env.ctx, face='armed')
    assert (ok, detail) == (False, 'readiness_stale_screen')
    assert launch_env.counters['readiness_stale_screen'] == 1
    assert _StubExecutor.instances == [], 'stale 帧零执行'


def test_unified_overlay_hold_rejects(launch_env) -> None:
    """浮层命中(遭遇 OCR 兜底路径)→ (False, 'readiness_overlay_hold:…')
    + 分键,零执行——误触防护载体内嵌验证。"""
    op = _StubOp([_Frame(hits=PREP_HITS, ocr_hit=True)])
    ok, detail = launch_battle_unified(op, launch_env.ctx, face='armed')
    assert ok is False
    assert detail.startswith('readiness_overlay_hold:'), detail
    assert '遭遇选择面板' in detail
    assert launch_env.counters['readiness_overlay_hold'] == 1
    assert _StubExecutor.instances == [], '浮层帧零执行'


def test_unified_resume_latch(launch_env) -> None:
    """resume 闩:首调部署原子序 + 置闩;次调跳过部署、CwActionStartBattleParam 照发。"""
    op = _StubOp([_Frame(hits=PREP_HITS), _Frame(hits=PREP_HITS)])
    ok1, _ = launch_battle_unified(op, launch_env.ctx, face='resume')
    assert ok1 is True
    assert op._cw_locked_sync_done is True, '首调置闩'
    assert launch_env.deploy_calls == [1], '首调部署原子序一次'
    ok2, _ = launch_battle_unified(op, launch_env.ctx, face='resume')
    assert ok2 is True
    assert launch_env.deploy_calls == [1], '闩后部署原子序不再现算'
    assert len(_StubExecutor.instances) == 2, '两调各一次 CwActionStartBattleParam 执行'


def test_unified_invalid_face_rejected(launch_env) -> None:
    """非法 face = 参数错误拒绝(禁静默兜底成某一面)。"""
    with pytest.raises(ValueError):
        launch_battle_unified(_StubOp([_Frame()]), launch_env.ctx, face='x')


