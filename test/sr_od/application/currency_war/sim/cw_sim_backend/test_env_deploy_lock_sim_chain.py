"""sim 全链赠卡锁分支轻量局测试(镜像 src 主断言对象 = kernel 赠卡锁分支经
sim 后端全链;按流程级测试落位本目录,引擎驱动助手 import 自
sim/test_sim_backend.py〔已登记超限拆分债文件,禁追加,只 import 复用不改;
先例 = 本目录 test_resolve_battle.py〕)。

测试面依据 = T-33 英雄登场设计(已退役账本
invest-effects-calc/设计稿(原件已退役;判据 = 本文件锁面申报))§2.3/§2.5 +
§4 锁 2/8/12:
- **开局面**:播种 invest_env_opts 选英雄登场 → bench = 5 张(M01 开局
  4 张 1★ + 1 张随机 2★5 费赠卡;开局费用形状无 5 费件,2★ = 赠卡),
  uid 随行;锁记录 = (名, uid, (3,4))(默认表 (1,1) 步进 19),done
  含 deploy_lock_uid#<uid>;
- **完胜提前链**:sim 结算分支补写环帧后,完胜帧 settle_confirm 推进 →
  unlock 逐帧递减(1-1 首帧宁缺勿造不判定,1-2/1-3 各回退一步);
- **确定性**:sim 采样走流键 rng(上报函数条件解析注入 = 状态副本里的值),
  同 seed 重放逐位确定。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _close_shop_feed,
    _force_settle,
    _node_advance_feed,
    _start_battle_feed,
)

from sr_od.application.currency_war.data.cw_chars import chars_by_cost
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_env_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_INVEST_ENV,
    SCREEN_PREP,
    SCREEN_SETTLE,
    SimBackend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_ports import (
    declare_world,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_SIG = ChannelSig(family='logic_action', actor='SimBackendTest',
                  mode='compute')

_COST5_POOL = {c.name for c in chars_by_cost(5)}


def _pick_hero_env(seed: int) -> SimBackend:
    """开局选英雄登场的装配后端(调用方负责 uninstall)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    from sr_od.application.currency_war.sim.cw_sim_backend import (
        install_backend,
    )
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    assert b.screen_identity() == SCREEN_INVEST_ENV
    b.gs.write_logic(b.gs.invest_env_opts,
                     ['英雄登场', '轮岗', '头彩'],
                     produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_env_param(
        b.gs, SimpleNamespace(idx=0), _SIG)
    assert out.applied
    declare_world(out.world_decl)
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP, '选卡确认交回备战'
    return b


def _settle_node_win(b: SimBackend, monkeypatch: pytest.MonkeyPatch) -> None:
    """当前节点强制胜局结算 + settle_confirm 推进(完胜帧路径)。"""
    _force_settle(monkeypatch, won=True)
    _start_battle_feed(b.gs)
    assert b.screen_identity() == SCREEN_SETTLE
    _node_advance_feed(b.gs, trigger='settle_confirm')


def test_full_chain_grant_lock_and_perfect_rewind(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """全链轻量局(T-33 设计 §4 锁 12):选英雄登场 → 开局面五断言 →
    1-1/1-2/1-3 三帧完胜 → unlock (3,4)→(3,4)(首帧宁缺勿造)→
    (3,3)→(3,2) 逐帧递减;环帧 node_type 随 sim kind 入结算行词表。"""
    b = _pick_hero_env(7)
    try:
        gs = b.gs
        # —— 开局面(设计 §4 锁 2 sim 端)——
        units = [(s.unit.char_id, s.unit.star, s.unit.uid)
                 for s in gs.bench.value.slots
                 if s is not None and s.kind == 'unit' and s.unit is not None]
        assert len(units) == 5, 'M01 开局 4 张 + 赠卡 1 张'
        two_star = [(n, u) for n, st, u in units if st == 2]
        assert len(two_star) == 1, '恰 1 张 2★(开局全 1★)'
        grant_name, grant_uid = two_star[0]
        assert grant_name in _COST5_POOL, '赠卡 ∈ 5 费全档池'
        assert grant_uid is not None, '实例号随行(sim 状态副本写即真值)'
        assert gs.env_grant_uid_seq.value == grant_uid, '发号计数器落账'
        assert gs.env_grant_deploy_locks.value == \
            ((grant_name, grant_uid, (3, 4)),), '锁记录 (3,4) = (1,1)+19 步'
        assert (gs.active_env.value, f'deploy_lock_uid#{grant_uid}') in \
            (gs.env_grants_done.value or ()), '完胜作用域键落 done'
        # —— 完胜提前链(设计 §4 锁 12)——
        # 1-1(奖励):结算帧 1 = 首帧,环不足两行宁缺勿造 → 不判定
        _settle_node_win(b, monkeypatch)
        assert gs.env_grant_deploy_locks.value[0][2] == (3, 4), \
            '首帧不判定(锁不回退)'
        frame1 = gs.settlement_ring.last_row()
        assert (frame1.round_num, frame1.node_type, frame1.killed) == \
            (1, '奖励', True), 'sim kind → 结算行词表(奖励)'
        # 1-2(奖励):帧 2 完胜(killed=True ∧ hp 持平)→ 回退一步
        #((1,2) 窗收尾自动弹店,2026-10-29 流程模型对齐:关店回备战再出战)
        _close_shop_feed(b)
        _settle_node_win(b, monkeypatch)
        assert gs.env_grant_deploy_locks.value[0][2] == (3, 3), '完胜回退 1'
        # 1-3(普通战斗):帧 3 完胜 → 再回退一步;P1r3 = U07 offer 槽,
        # 窗后停在投资策略屏(offer 决策面非本测辖域,直接出战结算)
        _settle_node_win(b, monkeypatch)
        assert gs.env_grant_deploy_locks.value[0][2] == (3, 2), '完胜回退 2'
        frame3 = gs.settlement_ring.last_row()
        assert (frame3.round_num, frame3.node_type) == (3, '普通战斗'), \
            '战斗帧词表'
        # (1,4) 窗收尾自动弹店 → 关店回备战(可操作主窗口)
        _close_shop_feed(b)
        assert b.screen_identity() == SCREEN_PREP
    finally:
        uninstall_backend()


def test_full_chain_same_seed_replay_deterministic(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """同 seed 重放确定(设计 §4 锁 12;赠卡分支采样走流键 rng = 状态副本
    真值,§2.5):双跑同 seed 同配置,赠卡名/实例号/锁序列逐位一致。"""
    def _run() -> tuple[str, int, tuple]:
        b = _pick_hero_env(42)
        try:
            gs = b.gs
            unit = next(s.unit for s in gs.bench.value.slots
                        if s is not None and s.kind == 'unit'
                        and s.unit is not None and s.unit.star == 2)
            _settle_node_win(b, monkeypatch)
            _settle_node_win(b, monkeypatch)
            return (unit.char_id, unit.uid,
                    gs.env_grant_deploy_locks.value)
        finally:
            uninstall_backend()

    first = _run()
    second = _run()
    assert first == second, f'同 seed 重放逐位确定: {first} vs {second}'
    assert first[2][0][2] == (3, 3), '重放锁序列同步(两帧完胜回退)'
