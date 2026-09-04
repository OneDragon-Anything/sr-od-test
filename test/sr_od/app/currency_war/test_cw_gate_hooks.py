"""test_cw_gate_hooks 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- gate_flags: test_cw_gate_flags.py
- gate_post_collapse(收起探针段): test_cw_gate_post_collapse.py
- r330_hook_gates: test_cw_r330_hook_gates.py
- survey19_hooks: test_cw_survey19_hooks.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。

2026-09-03 gate 清尾批:cw_observation_gate 模块退役(RunNode 拆除后
wait_stable_frame 已无生产调用方,消费清零)——gate_fast_confirm /
gate_post_collapse(gate 桩段)/ gate_fixtures 三段随模块删除;保留的
收起探针行为锁去 gate 桩重写(行为语义不变:探针恰一次、单轮交回外循环)。
"""
from __future__ import annotations

# ==================== gate_flags ====================

from sr_od.application.currency_war.currency_war_config import CurrencyWarConfig


def test_gate_flags_removed() -> None:
    """r347:gate_* flag 不得回流——对拍已完成,gate 是唯一路径;
    flag 回流 = 死代码复活(双路径维护+组合爆炸)。"""
    src_attrs = [a for a in vars(CurrencyWarConfig) if a.startswith('gate_')]
    assert not src_attrs, f'gate flag 已删不得回流: {src_attrs}'
    import inspect
    init_src = inspect.getsource(CurrencyWarConfig.__init__)
    assert 'self.gate_' not in init_src, '__init__ 不得再读 gate flag'
    save_src = inspect.getsource(CurrencyWarConfig.save)
    assert "'gate_" not in save_src, 'save 白名单不得再写 gate flag 键'


# ==================== gate_post_collapse(收起探针段,gate 桩已去) ====================

from types import SimpleNamespace

import sr_od.application.currency_war.operations.cw_screen.cw_screen_prep as pd_mod
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    StartBattle,
)
from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import CwScreenPrep


def _make_director(monkeypatch, collapse_open):
    """构造绕过 __init__ 的 CwScreenPrep,mock 开店态探测(gate 桩已随
    gate 模块退役删除;单轮入口本就无稳定门调用)。

    collapse_open 控制 _try_collapse_open_shop 返回值(标量=恒值;
    列表=按序弹出,记录实际返回到返回的 list)。
    """
    d = CwScreenPrep.__new__(CwScreenPrep)
    d.ctx = SimpleNamespace(current_instance_idx=99)
    d._executor = SimpleNamespace(
        validate=lambda a: None,
        execute=lambda a: (True, 'ok'))
    # 拆内环后单轮 run() 会重建执行器 → 桩掉构造点,保注入面(离线单测)
    monkeypatch.setattr(pd_mod, 'PrepActionExecutor',
                        lambda op, ctx: d._executor)
    d._steps = 0
    d._stall = 0
    d._fail_counts = {}
    d._blocked = set()
    d._recovered = set()
    d._recovery_closed_known = {}
    d._recovery_tried = False
    d._bench_pts = []
    d._cached_state = None
    d._cached_bench = []
    d._cached_deployed = []
    d._cached_vacancy = 0
    d._cached_gold_trusted = False

    # 预收重试窗的 sleep 打桩(离线单测不付真实等待;记录间隔供断言)
    sleeps: list[float] = []
    monkeypatch.setattr(pd_mod.time, 'sleep', lambda s: sleeps.append(s))

    collapse_calls: list[bool] = []
    _collapse_seq = list(collapse_open) if isinstance(collapse_open, list) \
        else None

    def _fake_collapse():
        v = _collapse_seq.pop(0) if _collapse_seq is not None else collapse_open
        collapse_calls.append(v)
        return v

    monkeypatch.setattr(d, '_try_collapse_open_shop', _fake_collapse)

    def _observe(heavy, screen=None):
        from sr_od.application.currency_war.kernel.cw_prep_actions import (
            PrepObservation,
        )
        obs = PrepObservation()
        obs.state = GameState(plane=1, round_num=1)
        return obs

    monkeypatch.setattr(d, '_observe', _observe)
    monkeypatch.setattr(d, '_record_step', lambda o, a: None)
    import sr_od.application.currency_war.currency_war_config as cfg_mod
    monkeypatch.setattr(cfg_mod, 'CurrencyWarConfig', lambda idx: SimpleNamespace())
    match = SimpleNamespace(
        strategy=SimpleNamespace(
            # W971 P2 黑板接口(dd-014)+序列契约 v1(dd-020):
            # 生产环按 list[PrepAction] 消费(长度 1)
            decide_prep_screen=lambda session, config: [StartBattle()],
            update_target=lambda state, session, config: None),
        session=SimpleNamespace(defer_count=0))
    return d, match, collapse_calls, sleeps


def test_prep_round_entry_collapse_once(monkeypatch) -> None:
    """拆内环定稿(替代原 gate 时序四锁):备战单轮入口 = 开店态收起探针
    **恰一次**;gate 时间稳定窗(wait_stable_frame)随内环整体拆除、模块
    已退役(2026-09-03 清尾批),单轮直接进观察(稳定性由外循环每轮重
    识别保证)。"""
    d, match, collapse_calls, _sleeps = _make_director(
        monkeypatch, collapse_open=True)
    match.strategy.decide_prep_screen = (
        lambda session, config: [pd_mod.DeferSpheres()])
    d.ctx.cw_match = match   # 单轮 run 入口读 ctx.cw_match

    result = d.run()   # 离线直调节点(SimpleNamespace ctx 无 run_context;
    #                     等待已由 harness sleep 桩吃掉,不需要 fast_sleep)

    assert collapse_calls == [True], f'收起探针应恰调一次,实得 {collapse_calls}'
    assert '交回外循环' in (result.status or ''), f'单轮须交回外循环:{result.status!r}'


# ==================== r330_hook_gates ====================
# (2026-09-03 瘦身批:test_is_prep_like_frame_exists / test_layout_hook_gated /
#  test_star_hook_gated 三条纯在场锁删除(纪律 8:hasattr/标识符在源=实现的
#  影子);钩子门控行为面由各钩子的行为测辖定。)

import inspect as _r330_hook_gates_inspect


def test_bookcard_stop_hook_removed() -> None:
    """bookcard 确认停机钩子退役(2026-08-30 开启语义确认,自动处理链接管):
    read_bench_chars 不再有停机逻辑;处理链接线在 cw_loop + handlers。
    (原锁 r133→r330「钩子过帧态门」钉的是停机语义,钩子删除后语义换新。
    2026-09-03 瘦身批:三个肯定式在场断言删除,否定墓碑保留。)"""
    from sr_od.application.currency_war.obs import cw_identity_obs
    src = _r330_hook_gates_inspect.getsource(cw_identity_obs.read_bench_chars)
    assert 'bookcard_confirm' not in src   # 停机钩子段已删


# ==================== survey19_hooks ====================

from sr_od.application.currency_war.kernel.cw_survey19_hooks import (  # noqa: E402
    encounter_tier_score,
    supply_reroll_decision,
    wear_discipline_alert,
)


def test_p9_encounter_tier_context_dependent() -> None:
    """遭遇档评分场合依赖:同 −4,边际局高分/大胜局≈0;位面无放大
    (ADR-0519:P1 尖峰 ×1.5 系数未证退役,保守缺省 = 位面中性)。"""
    edge = encounter_tier_score(100, -4, gap=0, plane=2)
    blow = encounter_tier_score(100, -4, gap=-80, plane=2)
    p1 = encounter_tier_score(100, -4, gap=0, plane=1)
    assert edge > blow
    assert p1 == edge   # ADR-0519:P1 尖峰放大已退役


def test_p1_wear_discipline() -> None:
    """狼狩穿戴纪律:可穿而未穿 = 报警;无空槽的真积压才算;非狼狩无 XP 项。"""
    # 3 件闲 + 2 空槽 → overflow 1 → 报警(狼狩:每战 −1 XP)
    r = wear_discipline_alert(['a', 'b', 'c'], total_slots=10, worn_count=8,
                              faction_hunt_active=True)
    assert r['alert'] and r['unwearable_overflow'] == 1
    assert r['hunt_xp_loss_per_battle'] == 1
    # 全穿满 → 无报警(装备可循环,合成交换不算积压)
    ok = wear_discipline_alert([], total_slots=10, worn_count=10,
                               faction_hunt_active=True)
    assert not ok['alert'] and ok['hunt_xp_loss_per_battle'] == 0
    # 非狼狩:仅战力视角
    no_hunt = wear_discipline_alert(['a', 'b', 'c'], 10, 8, faction_hunt_active=False)
    assert no_hunt['alert'] and no_hunt['hunt_xp_loss_per_battle'] == 0


def test_p8_supply_reroll() -> None:
    """补给重刷:出钻直选/未出可刷→刷/刷过仍无→按价值选。"""
    assert supply_reroll_decision(True, False) == 'pick_diamond'
    assert supply_reroll_decision(True, True) == 'pick_diamond'
    assert supply_reroll_decision(False, False) == 'reroll'
    assert supply_reroll_decision(False, True) == 'pick_best'
