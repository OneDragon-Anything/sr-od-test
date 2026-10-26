"""环境直发策略取卡挂点 sim 全链轻量局测试(镜像 src = sim/cw_sim_backend.py
的 ``_begin_node_window`` 直发发放事件;按流程级测试落位本目录,引擎驱动
助手 import 自 sim/test_sim_backend.py〔在册超限拆分债文件,禁追加,只
import 复用不改;先例 = 本目录 test_env_bond_tier_sim_chain.py〕)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-46-celue-dashi.md(定稿)§4 锁 5(§2.2(e) 落地形态):
- 定向策略大师推进至 P3r5 → 无选卡屏、active_strategies +1(随机新策略,
  排除已拥有)、发放行金额 = 2×直发后持有数(直发本身触发金币腿的耦合锁,
  金额对账 = 发放行值 − 同窗轮首收入行值,与收入数值解耦);
- 直发后 excluded_invest 含到手名(全程去重契约锁);
- 窗口重放不双发(幂等守卫族语义锁,boss 先例同款断言位);
- 非挂点节点不发;表外环境不发。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war.sim.cw_sim_backend.test_p3_win_terminal import (
    _drive_step,
)
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _env_pick_backend,
    _force_settle,
    _seed_and_pick_env,
)

from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_INVEST_STRATEGY,
    SimBackend,
    uninstall_backend,
)

_SIG = ChannelSig(family='logic_action', actor='T46PickGrantTest',
                  mode='compute')

_ENV = '策略大师'
_FOREIGN_ENV = '增发货币'   # ENV_ECONOMY 成员 ∉ ENV_PICK_GRANTS/ENV_POOL_REWRITE


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(先例 = sim/test_sim_backend 同名 fixture,fixture
    不可跨文件 import 故本文件自带同名同语义副本)。"""
    consume_defect_sink()
    yield
    set_defect_sink(None)
    consume_defect_sink()


def _node_pos(b: SimBackend) -> tuple[int, int] | None:
    """当前节点序位(节点未进窗 = None)。"""
    node = b.gs.node.value
    return None if node is None else (node.plane, node.round_num)


def _drive_until_pos(b: SimBackend, pos: tuple[int, int],
                     limit: int = 512) -> None:
    """步进驱动至节点序位(超限响错防死循环;单步助手 =
    test_p3_win_terminal._drive_step——位面过渡屏在其分派表内,
    test_sim_backend._drive_env_grant_step 无该档,达 P3 必经)。"""
    for _ in range(limit):
        if _node_pos(b) == pos:
            return
        _drive_step(b, 37)
    raise AssertionError(f'驱动步数超限,未达 {pos}')


def _record_write_values(gs, monkeypatch: pytest.MonkeyPatch
                         ) -> list[tuple[str, str, str | None, object]]:
    """记录 (通道, 字段, evidence, 写入值) 四元写行(test_sim_backend
    ._record_all_writes 同式包装,本文件版增记 value 供发放金额对账;
    透传真实现零行为变化)。"""
    rows: list[tuple[str, str, str | None, object]] = []

    def _wrap_logic(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            rows.append((channel, gs._field_name(target), evidence, value))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    def _wrap_obs(real):
        def rec(target, value, *, evidence=None, sig, note=''):
            rows.append(('obs', gs._field_name(target), evidence, value))
            real(target, value, evidence=evidence, sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic', _wrap_logic(gs.write_logic,
                                                       'logic'))
    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap_logic(gs.write_logic_rand, 'rand'))
    monkeypatch.setattr(gs, 'observe', _wrap_obs(gs.observe))
    return rows


def _grant_gold_rows(rows: list[tuple[str, str, str | None, object]]
                     ) -> list[tuple[str, str, str | None, object]]:
    """直发金币腿写行(evidence = env_grant#<环境>#pick<k> 的 gold 行)。"""
    return [r for r in rows if r[0] == 'logic' and r[1] == 'gold'
            and r[2] and r[2].startswith('env_grant#策略大师#pick')]


def test_direct_grant_fires_at_p3r5_no_offer_screen(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """主锁(T-46 设计 §4 锁 5):策略大师局推进至 P3r5 窗口 → 直发恰
    一张(随机新策略,排除已拥有)、无选卡屏(窗后直落节点屏)、发放行
    金额 = 2×直发后持有数(直发经获得链自动触发金币腿)、到手名并入
    excluded_invest。结算恒胜桩保全程存活(死亡腿与本测无关)。
    非挂点节点不发:r4 窗开时点已入快照基线——若误挂 (3,4),直发卡已在
    held_before 内、r5 段零新发放行,本组断言即红(最近邻非挂点窗负例;
    表外环境负例另测)。"""
    _force_settle(monkeypatch, True)
    b = _env_pick_backend(7)
    try:
        gs = b.gs
        _seed_and_pick_env(b, _ENV)
        assert gs.active_env.value == _ENV, '选卡事实前置'
        rows = _record_write_values(gs, monkeypatch)
        _drive_until_pos(b, (3, 4))
        held_before = list(gs.active_strategies.value or [])
        grants_before = len(_grant_gold_rows(rows))
        _drive_until_pos(b, (3, 5))
        # 无选卡屏:直发不开 offer,窗后直落节点屏
        assert b.screen_identity() != SCREEN_INVEST_STRATEGY, '无选卡屏'
        held_after = list(gs.active_strategies.value or [])
        assert len(held_after) == len(held_before) + 1, \
            f'r5 窗直发恰一张: {held_before} -> {held_after}'
        name = held_after[-1]
        assert name not in held_before, '随机新策略(排除已拥有)'
        # 直发本身触发金币腿(耦合锁):r4→r5 段恰一行新发放写,
        # 金额 = 2×直发后持有数(与同窗轮首收入解耦的差分;
        # 前段既有行 = offer 取卡腿各行,同 evidence 形态属预期)
        grants_after = _grant_gold_rows(rows)
        assert len(grants_after) == grants_before + 1, \
            f'r5 段恰一行新发放写: {grants_before} -> {len(grants_after)}'
        grant = grants_after[-1]
        assert grant[2] == f'env_grant#{_ENV}#pick{len(held_after)}', \
            f'evidence 携含本张 k: {grant[2]}'
        idx = rows.index(grant)
        income_value = next(r[3] for r in reversed(rows[:idx])
                            if r[1] == 'gold')
        assert int(grant[3]) - int(income_value) == 2 * len(held_after), \
            f'金额 = 2×含本张持有数: {grant[3]} - {income_value}'
        # 全程去重契约:到手名并入 excluded_invest
        assert name in b.excluded_invest, \
            f'到手名并入排除集: {name} ∉ {sorted(b.excluded_invest)}'
    finally:
        uninstall_backend()


def test_window_replay_no_double_grant(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """窗口重放不双发(幂等守卫族语义锁,boss 先例同款断言位):P3r5 窗
    已开(直发已落)后,同节点二次 ``_begin_node_window`` 零二次发放
    (持有数与金不动)。"""
    _force_settle(monkeypatch, True)
    b = _env_pick_backend(7)
    try:
        gs = b.gs
        _seed_and_pick_env(b, _ENV)
        _drive_until_pos(b, (3, 5))
        held_at_window = len(gs.active_strategies.value or [])
        assert held_at_window >= 1, '直发已落(窗口已开)'
        rows = _record_write_values(gs, monkeypatch)
        b._begin_node_window()
        assert len(gs.active_strategies.value or []) == held_at_window, \
            '重放零二次发放(持有不动)'
        assert _grant_gold_rows(rows) == [], '重放零发放写行'
    finally:
        uninstall_backend()


def test_foreign_env_no_grant_at_p3r5(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """表外环境不发(T-46 设计 §4 锁 5):登记表外环境(增发货币)局
    推进至 (3,5) 窗口 → 零直发(持有不动、零 env_grant gold 写行);
    direct 挂点查询 get None = 无直发的合法语义。"""
    _force_settle(monkeypatch, True)
    b = _env_pick_backend(7)
    try:
        gs = b.gs
        _seed_and_pick_env(b, _FOREIGN_ENV)
        assert gs.active_env.value == _FOREIGN_ENV
        rows = _record_write_values(gs, monkeypatch)
        _drive_until_pos(b, (3, 4))
        held_at_r4 = len(gs.active_strategies.value or [])
        _drive_until_pos(b, (3, 5))
        assert len(gs.active_strategies.value or []) == held_at_r4, \
            '表外环境零直发(持有不动)'
        assert _grant_gold_rows(rows) == [], '表外环境零 env_grant 写行'
    finally:
        uninstall_backend()
