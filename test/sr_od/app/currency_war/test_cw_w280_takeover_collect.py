"""行为锁:接管补采独立 op(TakeoverCollectPlaneIntel)。

背景:battle_loop 的 CollectPlaneIntel 实采块(内联)只在 loop 对局轮的
备战稳定帧触发;MCP 重启后内存 session 全丢、loop 首局 target 重选断档期,
手动补真值需要**不经 loop 即可调起**的独立入口(组装口径 已裁决=位面
详情屏唯一)。本文件锁住该 op 的壳层契约:

1. run_operation 可发现(op 注册扫描含它);
2. 入口门快速 fail(非对局画面不空转 retry、不点击);
3. 跳过门(session 已有真值 → 零点击直通,委派子 op 不发生);
4. 落 session 口径与 battle_loop 内联块同款(ADR-0414 双面锁):bosses
   **保位写**(None 原样占槽,滤掉=位面错序回潮)、affixes 仅空时写、
   消费后清 ctx 中转池(防跨局判空泄漏);
5. 实采无产出 → 不落 session(空表覆写会抹掉已有真值)。

fixture 帧:screens 存档离线跑(``fast_sleep`` + ``FixtureController``),
零实机交互。
"""
from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

from one_dragon.base.operation.operation_base import OperationResult
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

if TYPE_CHECKING:
    from test.conftest import SrTestContext

_OP_ID = (
    'sr_od.application.currency_war.operations.entry.'
    'takeover_collect_plane_intel.TakeoverCollectPlaneIntel'
)


def _make_op(test_context: SrTestContext, monkeypatch, phases: list[dict]):
    """构造被测 op(fixture 控制器注入 + 看门狗),返回 (op, fixture_controller)。"""
    from sr_od.application.currency_war.operations.entry.takeover_collect_plane_intel import (
        TakeoverCollectPlaneIntel,
    )

    class _Watched(WatchdogOperationMixin, TakeoverCollectPlaneIntel):
        pass

    fc = FixtureController(test_context)
    fc.set_phases(phases)
    # fixture 控制器注入 ctx(is_game_window_ready=True 绕过开游戏前置链)
    monkeypatch.setattr(test_context, 'controller', fc)
    return _Watched(test_context), fc


def _exec(op) -> OperationResult:
    with fast_sleep():
        return op.execute()


# --------------------------------------------------------------------------- #
# ①注册面:run_operation 可发现
# --------------------------------------------------------------------------- #


def test_takeover_op_discoverable_by_registry(test_context: SrTestContext) -> None:
    """锁①:op 扫描注册表应含本 op(run_operation 可调起的前提)。"""
    from sr_od.backend.operation_registry import scan_operations

    ops = {o.op_id for o in scan_operations(test_context, refresh=True).operations}
    assert _OP_ID in ops, f'接管补采 op 未被扫描注册: {_OP_ID}'


# --------------------------------------------------------------------------- #
# ②入口门:错屏快速 fail
# --------------------------------------------------------------------------- #


def test_gate_fail_fast_on_lobby_frame(test_context: SrTestContext, monkeypatch) -> None:
    """锁②:大厅帧 → 快速 fail 并存证,零点击、不碰 session。"""
    monkeypatch.setattr(
        test_context, 'cw_match',
        SimpleNamespace(session=SimpleNamespace(briefing_bosses=[], briefing_affixes=[])),
        raising=False)
    op, fc = _make_op(test_context, monkeypatch, [{'frame': ('货币战争-大厅', 'lobby')}])
    enter_running_state(test_context)
    try:
        res = _exec(op)
    finally:
        reset_running_state(test_context, op)
    assert not res.success, f'大厅帧应 fail,得成功:{res.status}'
    assert '无法补采' in str(res.status), f'status 应指明画面错误,得 {res.status!r}'
    assert fc.recorded_clicks == [], '入口门 fail 不应产生任何点击'
    sess = test_context.cw_match.session
    assert sess.briefing_bosses == [], 'fail 路径不得改写 session'


# --------------------------------------------------------------------------- #
# ③跳过门:session 已有真值 → 零点击,不委派子 op
# --------------------------------------------------------------------------- #


def test_skip_when_session_has_truth(test_context: SrTestContext, monkeypatch) -> None:
    """锁③:briefing_bosses 非空 → 直通 success,CollectPlaneIntel 不被实例化。"""
    from sr_od.application.currency_war.operations.handlers import (
        collect_plane_intel as cpi_mod,
    )

    truth = ['巨鹿', None, '绘师']

    def _must_not_run(*a, **k):
        raise AssertionError('session 已有真值时不应委派实采子 op')

    monkeypatch.setattr(cpi_mod, 'CollectPlaneIntel', _must_not_run)
    sess = SimpleNamespace(briefing_bosses=list(truth), briefing_affixes=['已有'])
    monkeypatch.setattr(
        test_context, 'cw_match', SimpleNamespace(session=sess), raising=False)
    monkeypatch.setattr(test_context, 'cw_plane_bosses', ['残留'], raising=False)

    op, fc = _make_op(test_context, monkeypatch, [{'frame': ('货币战争-备战', '攻略已应用')}])
    enter_running_state(test_context)
    try:
        res = _exec(op)
    finally:
        reset_running_state(test_context, op)
    assert res.success, f'跳过路径应 success,得 {res.status!r}'
    assert '跳过' in str(res.status)
    assert fc.recorded_clicks == [], '跳过路径应为零点击'
    assert sess.briefing_bosses == truth, '跳过路径不得改写已有真值'
    assert getattr(test_context, 'cw_plane_bosses', None) is None, (
        '真值保护路径应清残留中转池(防跨局判空泄漏)'
    )
    # 跳过分支池空且 session 有真值 → 清残留也属消费收尾,但跳过节点不改池:
    # 本锁只钉「session 真值未被触碰」,池语义由写回节点测试覆盖。


# --------------------------------------------------------------------------- #
# ④成功链:实采产出 → 保位落 session → 清池
# --------------------------------------------------------------------------- #


class _FakeIntel:
    """CollectPlaneIntel 替身:直接产中转池结果(壳层测试不重跑 SIFT 链)。"""

    produced_bosses: list | None = ['巨鹿', None, '绘师']
    produced_affixes: list | None = ['财富造物主', '敌人难度108']

    def __init__(self, ctx) -> None:
        self.ctx = ctx

    def execute(self) -> OperationResult:
        self.ctx.cw_plane_bosses = list(self.produced_bosses)
        self.ctx.cw_plane_affixes = list(self.produced_affixes)
        return OperationResult(success=True, status='位面情报采集')


def test_success_writes_session_and_clears_pools(test_context: SrTestContext, monkeypatch) -> None:
    """锁④主链:保位 3 槽落 session、affixes 仅空时写、消费后清池。"""
    from sr_od.application.currency_war.operations.handlers import (
        collect_plane_intel as cpi_mod,
    )

    monkeypatch.setattr(cpi_mod, 'CollectPlaneIntel', _FakeIntel)
    sess = SimpleNamespace(briefing_bosses=[], briefing_affixes=[])
    monkeypatch.setattr(
        test_context, 'cw_match', SimpleNamespace(session=sess), raising=False)
    monkeypatch.setattr(test_context, 'cw_plane_bosses', None, raising=False)
    monkeypatch.setattr(test_context, 'cw_plane_affixes', None, raising=False)

    op, _fc = _make_op(test_context, monkeypatch, [{'frame': ('货币战争-备战', '攻略已应用')}])
    enter_running_state(test_context)
    try:
        res = _exec(op)
    finally:
        reset_running_state(test_context, op)

    assert res.success, f'成功链应 success,得 {res.status!r}'
    assert sess.briefing_bosses == ['巨鹿', None, '绘师'], (
        f'bosses 应保位写 3 槽(None 原样占槽),得 {sess.briefing_bosses}'
    )
    assert sess.briefing_affixes == ['财富造物主', '敌人难度108'], (
        f'affixes 仅空时应写入,得 {sess.briefing_affixes}'
    )
    assert test_context.cw_plane_bosses is None, '消费后 boss 中转池应清空'
    assert test_context.cw_plane_affixes is None, '消费后词缀中转池应清空'


def test_success_does_not_overwrite_existing_affixes(test_context: SrTestContext, monkeypatch) -> None:
    """锁④伴生:session.briefing_affixes 已有值时随采词缀**不覆写**(与
    battle_loop 内联块「仅简报未供时」口径一致)。"""
    from sr_od.application.currency_war.operations.handlers import (
        collect_plane_intel as cpi_mod,
    )

    monkeypatch.setattr(cpi_mod, 'CollectPlaneIntel', _FakeIntel)
    sess = SimpleNamespace(briefing_bosses=[], briefing_affixes=['简报先到'])
    monkeypatch.setattr(
        test_context, 'cw_match', SimpleNamespace(session=sess), raising=False)
    monkeypatch.setattr(test_context, 'cw_plane_bosses', None, raising=False)
    monkeypatch.setattr(test_context, 'cw_plane_affixes', None, raising=False)

    op, _fc = _make_op(test_context, monkeypatch, [{'frame': ('货币战争-备战', '攻略已应用')}])
    enter_running_state(test_context)
    try:
        res = _exec(op)
    finally:
        reset_running_state(test_context, op)

    assert res.success
    assert sess.briefing_affixes == ['简报先到'], '已有词缀不得被随采覆写'
    assert sess.briefing_bosses == ['巨鹿', None, '绘师']


# --------------------------------------------------------------------------- #
# ⑤异常形态:实采成功但无产出 → 不落 session
# --------------------------------------------------------------------------- #


class _EmptyIntel(_FakeIntel):
    """成功但不产出的异常替身(中转池保持 None)。"""

    def execute(self) -> OperationResult:
        return OperationResult(success=True, status='位面情报采集(空)')


def test_no_output_leaves_session_untouched(test_context: SrTestContext, monkeypatch) -> None:
    """锁⑤:子 op 称成功但中转池空 → fail,session 保持空表不被覆写成假成功。"""
    from sr_od.application.currency_war.operations.handlers import (
        collect_plane_intel as cpi_mod,
    )

    monkeypatch.setattr(cpi_mod, 'CollectPlaneIntel', _EmptyIntel)
    sess = SimpleNamespace(briefing_bosses=[], briefing_affixes=[])
    monkeypatch.setattr(
        test_context, 'cw_match', SimpleNamespace(session=sess), raising=False)
    monkeypatch.setattr(test_context, 'cw_plane_bosses', None, raising=False)

    op, fc = _make_op(test_context, monkeypatch, [{'frame': ('货币战争-备战', '攻略已应用')}])
    enter_running_state(test_context)
    try:
        res = _exec(op)
    finally:
        reset_running_state(test_context, op)

    assert not res.success, f'无产出应 fail,得 {res.status!r}'
    assert sess.briefing_bosses == [], '无产出不得写 session'


# --------------------------------------------------------------------------- #
# ⑥静态口径锁:ADR-0414 双面之一(loop 内联块的镜像面在 w219/w221 锁)
# --------------------------------------------------------------------------- #


def test_static_write_semantics_locked() -> None:
    """锁⑥:静态锁——保位写形态在位、None 过滤禁回潮、双池取走即清。"""
    from sr_od.application.currency_war.operations.entry.takeover_collect_plane_intel import (
        TakeoverCollectPlaneIntel,
    )

    src = inspect.getsource(TakeoverCollectPlaneIntel.write_back)
    assert 'list(bosses)' in src, '保位写形态消失(须 list() 原样拷贝)'
    assert '[n for n in' not in src, '滤 None 回潮(徽章态位面名字左移错序)'
    assert 'self.ctx.cw_plane_bosses = None' in src, 'boss 中转池未清(跨局泄漏)'
    assert 'self.ctx.cw_plane_affixes = None' in src, '词缀中转池未清(跨局泄漏)'


# --------------------------------------------------------------------------- #
# fixture 真帧锚:存档引用帧仍是组装画面单一源(id_mark 在屏可判)
# --------------------------------------------------------------------------- #


def test_w277_reference_frame_ids_plane_detail(test_context: SrTestContext) -> None:
    """锁⑦:存档引用帧(screens png 存档)上「标识-位面详情标题」id_mark
    必命中——组装画面锚漂移即本 op 入口判定失效的前置信号。"""
    import cv2
    import numpy as np

    p = (Path(__file__).parents[4] / 'screens' / '货币战争-位面详情'
         / '位面详情-点节点直开.png')
    img_bgr = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert img_bgr is not None, f'fixture 缺失: {p}'
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)   # 生产语义:RGB

    from sr_od.application.currency_war.operations.entry.takeover_collect_plane_intel import (
        TakeoverCollectPlaneIntel,
    )

    op = TakeoverCollectPlaneIntel(test_context)
    res = op.round_by_find_area(img_rgb, '货币战争-位面详情', '标识-位面详情标题',
                                crop_first=False)
    assert res.is_success, 'W277 引用帧上位面详情 id_mark 应命中(真实 OCR)'
