"""环境 XP 窗口(成功经验)sim 全链轻量局测试(镜像 src 主断言对象 =
kernel 发放桥 grant_effect_node_xp 经 sim 后端节点推进全链;按流程级
测试落位本目录,引擎驱动助手 import 自 sim/test_sim_backend.py〔在册
超限拆分债文件,禁追加,只 import 复用不改;先例 = 同目录
test_env_deploy_lock_sim_chain.py〕)。

测试面依据 = 迭代 T-38 设计(.debug/progress/2026-09-23-invest-effects-
calc/designs/T-38-chenggong-jingyan.md)§2.6 实机(live)和模拟器(sim)两边语义 + §4 锁 10(sim 半):
- **sim = 世界真值**:节点边界发放经 kernel tick 段 write_logic 写
  gs.xp/gs.level → sim 世界等级随白送经验真实推进(8→9 跨级例证),
  零额外接线;
- **达成检测时点**:种子 lv8 路径达成位已达标(检测体首拍 tick 即记,
  当拍零发放);非买经验源跨级(节点经验等)走升级连锁 = 结算时点记锚
  (迭代 2026-09-23-invest-effects-calc T-432 定案),晚拍仅剩 live 观察
  路径的留白申报;
- **同 seed 重放**:发放序列逐位一致(发放链零 rng 消费的结构判据);
- **披露键族在册**:ENV_XP_WINDOW_DISCLOSURES 整表并入 sim 披露集。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _force_settle,
    _node_advance_feed,
    _start_battle_feed,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_env_param,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    CounterKey,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    bind_session_container,
    effective_node_pos,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    ENV_XP_WINDOW_DISCLOSURES,
    SCREEN_BRIEFING,
    SCREEN_INVEST_ENV,
    SCREEN_PREP,
    SCREEN_SETTLE,
    SimBackend,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_ports import declare_world
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_SIG = ChannelSig(family='logic_action', actor='SimBackendTest',
                  mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='TestXpWindow', mode='read')


def _bound_session(gs):
    """裸 session 桩 + 后端容器绑定(register_portal_from_env 经
    game_state_of 取绑定容器;弱引用表随桩对象回收自动解绑)。"""
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    session = StrategySession()
    bind_session_container(session, gs)
    return session
_ENV_ID = '138'   # 成功经验 plaza id(env_portal_effects 结构化条目主键)


def _pick_xp_env(seed: int) -> SimBackend:
    """开局选成功经验的装配后端(调用方负责 uninstall);选卡确认交回
    备战后把等级种子到已达标位(观察链同写入口,观察→观察覆盖静默)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108, env_present=True))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    assert b.screen_identity() == SCREEN_INVEST_ENV
    b.gs.write_logic(b.gs.invest_env_opts,
                     ['成功经验', '轮岗', '头彩'],
                     produced_by='Test', evidence='t:opts', sig=_SIG)
    # session 绑定后端容器(portal 登记分支消费;session=None = 登记分支跳过)
    out = report_action_pick_invest_env_param(
        b.gs, SimpleNamespace(idx=0), _SIG, session=_bound_session(b.gs))
    assert out.applied
    declare_world(out.world_decl)
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP, '选卡确认交回备战'
    b.gs.observe(b.gs.level, 8, evidence='t:seed:lv', sig=_SIG_OBS)
    b.gs.observe(b.gs.xp, (60, 72), evidence='t:seed:xp', sig=_SIG_OBS)
    return b


def _settle_node_win(b: SimBackend, monkeypatch: pytest.MonkeyPatch) -> None:
    """当前节点强制胜局结算 + settle_confirm 推进。"""
    _force_settle(monkeypatch, won=True)
    _start_battle_feed(b.gs)
    assert b.screen_identity() == SCREEN_SETTLE
    _node_advance_feed(b.gs, trigger='settle_confirm')


def _walk(b: SimBackend, monkeypatch: pytest.MonkeyPatch,
          steps: int) -> list:
    """逐节点推进并记录 (生效位, level, xp, 已发放数, 达成锚) 轨迹
    (发放序列重放对拍载体)。"""
    gs = b.gs
    entry = gs.effects.first(_ENV_ID)
    assert entry is not None, '成功经验条目在册(portal 登记链)'
    trail = []
    for _ in range(steps):
        _settle_node_win(b, monkeypatch)
        trail.append((effective_node_pos(gs), gs.level.value,
                      gs.xp.value,
                      entry.counters.get(CounterKey.XP_GRANTED, 0),
                      entry.anchor_pos))
    return trail


def test_sim_chain_world_truth_and_seed_replay(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """sim 全链(设计 §2.6/§4 锁 10):种子 lv8(60/72)→ 达成当拍
    (1-2 tick)只记锚零发放 → (1,3)/(1,4)/(1,5) 三节点各 +12 且发放
    +12 恰跨 72 门槛把 sim 世界等级真推到 9 → 同 seed 双跑轨迹逐位一致;
    披露键族整表在册。"""
    b = _pick_xp_env(7)
    try:
        for k in ENV_XP_WINDOW_DISCLOSURES:
            assert k in b.disclosures, f'披露键缺登记: {k}'
        trail = _walk(b, monkeypatch, steps=4)
    finally:
        uninstall_backend()
    # 1-2 拍:锚已记、零发放(离开 1-1 奖励 +2 → (62,72))
    assert trail[0] == ((1, 2), 8, (62, 72), 0, (1, 2)), '达成拍零发放'
    # 1-3 拍:首发放 +12 → 74 ≥ 72 跨级,世界等级真推 9(溢出结转 2,
    # 分母 84);离开 1-2 奖励 +2 → (4,84)
    assert trail[1] == ((1, 3), 9, (4, 84), 1, (1, 2)), \
        '发放跨级,sim 世界等级随白送经验推进'
    assert trail[2] == ((1, 4), 9, (18, 84), 2, (1, 2)), '第二发放'
    assert trail[3] == ((1, 5), 9, (32, 84), 3, (1, 2)), '窗口耗尽'
    # —— 同 seed 重放:发放序列逐位一致(单装配纪律:前局先卸再装)——
    b2 = _pick_xp_env(7)
    try:
        trail2 = _walk(b2, monkeypatch, steps=4)
    finally:
        uninstall_backend()
    assert trail2 == trail, '同 seed 重放逐位一致'
