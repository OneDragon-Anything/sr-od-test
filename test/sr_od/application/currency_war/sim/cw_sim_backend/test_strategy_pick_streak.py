"""sim 策略选卡连胜置位效果条目测试(镜像 src = sim/cw_sim_backend.py 的
apply_strategy_pick_streak helper + _on_invest_picked 落地效果条目 + 呈现一次性标志位)。

测试面依据 = 设计稿(原件已退役;§ 号 = 原稿节序)§4 八锁中的
sim 状态副本七锁(锁 7 注册表与双闭集断言落 kernel/test_cw_investments.py 与
strategies/impl/mandate_v1/test_invest_strategy.py 现址):
- 持卡置位真值(锁 1):预置 streak=1 落卡后恰 ==4,独立 evidence 笔
  ``streak:strategy_pick:胜利,还是胜利``(与结算笔 ``streak:pNrN`` 分账);
- 连败翻转(锁 2)/高连胜回落(锁 3):带符号绝对置位(-2→4、6→4,
  锁「变为」字面语义,禁 max 现值读法);
- 无效载荷零写(锁 4):opts 含本卡但不落卡 → 交集空零写且一次性标志位已消费
  (前置直构一次性标志位 True:锁面 = 「picked 空亦消费」,一次性标志位自始 None 则断言空转);
- 表外卡零写(锁 5):落无 streak_set 条目卡 → 注册表 miss→0 跳写;
- 重放防回写(锁 6):一次性标志位关重放零写(已推进 5 不得回写 4)/一次性标志位开恰一次
  置位写(锁面 = 一次性标志位本体是唯一闸);
- 自然跟随回归(锁 8):置位 4 → 下一胜局结算 → ==5 且结算笔存在
  (共用链零断;深井角斗场触发面已有 test_env_grants 覆盖不重复建)。

复用声明:引擎驱动助手 import 自 sim/test_p3_win_terminal.py 与
sim/test_sim_backend.py(已登记超限拆分债文件,禁追加,只 import 复用
不改;先例 = 本目录 test_strategy_pick_xp.py)。
"""
from __future__ import annotations

import re
from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war.sim.cw_sim_backend.test_p3_win_terminal import (
    _drive_step,
)
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _SIG_OBS,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_strategy_param,
)
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.sim import cw_sim_backend as sb
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_INVEST_STRATEGY,
    SCREEN_PREP,
    SimBackend,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_battle import (
    SIM_BATTLE_FACE,
    BattleOutcome,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

#: 置位效果条目独立笔 evidence 前缀(单一源 = cw_sim_base.sim_evidence
#: 契约:前缀 sim:engine: + 写点 tag streak:strategy_pick:<卡名>)。
_STREAK_EV_PREFIX = 'sim:engine:streak:strategy_pick:'

#: 结算连胜笔形态(§1.2e 共用链;与置位笔分账的判别基准)。
_SETTLE_EV_PATTERN = re.compile(r'^sim:engine:streak:p\d+r\d+$')


def _backend(seed: int = 41) -> SimBackend:
    """装配后端至 P1r1 备战屏(调用方负责 uninstall;装配形态先例 =
    test_strategy_pick_xp._backend)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP
    return b


def _drive_until(b: SimBackend, pred, limit: int = 512) -> None:
    """步进驱动至谓词成立(超限响错防死循环;单步助手 =
    test_p3_win_terminal._drive_step,import 复用先例 =
    test_strategy_pick_xp._drive_until)。"""
    for _ in range(limit):
        if pred():
            return
        _drive_step(b, 37)
    raise AssertionError('驱动步数超限,谓词未达成')


def _drive_to_offer(b: SimBackend) -> None:
    """驱动至策略 offer 呈现(固定日程首槽 P1r3 起;呈现即置置位效果条目一次性标志位
    ——本效果条目生效前提)。"""
    _drive_until(b, lambda: b.screen_identity() == SCREEN_INVEST_STRATEGY)


def _pick(b: SimBackend, name: str, opts: list[str]) -> WorldDecl:
    """定向选卡落地(直写 opts 定卡 + 上报 + 声明喂入;现役 harness
    形态先例 = test_sim_backend 选卡链族)。返回声明供重放用例复喂。"""
    gs = b.gs
    gs.write_logic(gs.invest_strategy_opts, opts,
                   produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_strategy_param(
        gs, SimpleNamespace(norm_name=name), _SIG, session=SimpleNamespace())
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    return out.world_decl


def _seed_streak(gs, value: int) -> None:
    """连胜观察直种(带符号;测试种子纪律先例 =
    test_strategy_pick_xp._seed_level_xp)。"""
    gs.observe(gs.streak, value, sig=_SIG_OBS)


@pytest.fixture()
def _always_win(monkeypatch):
    """结算恒胜桩(确定性:置位 4 → 胜局转移 +1 的跟随面不依赖种子;
    桩形态先例 = test_p3_win_terminal 恒败桩,方向反转)。"""
    def _win(rng, *, plane: int, round_num: int) -> BattleOutcome:
        return BattleOutcome(won=True, progress=1.0, base_damage=None,
                             progress_damage=None, hp_delta=-2,
                             face=SIM_BATTLE_FACE)

    monkeypatch.setattr(sb, 'settle_battle', _win)


def test_pick_sets_streak_to_absolute_value() -> None:
    """持卡置位真值(锁 1):预置 streak=1 落卡后恰 ==4,独立 evidence
    笔与结算笔分账可归因。"""
    b = _backend()
    try:
        gs = b.gs
        _drive_to_offer(b)
        _seed_streak(gs, 1)
        _pick(b, '胜利,还是胜利', ['胜利,还是胜利', '躺平', '淘金客'])
        assert gs.streak.value == 4, f'绝对置位 4: {gs.streak.value}'
        assert gs.streak.evidence == _STREAK_EV_PREFIX + '胜利,还是胜利', \
            f'独立笔缺失或来源漂移: {gs.streak.evidence}'
    finally:
        uninstall_backend()


def test_negative_streak_flips_to_set_value() -> None:
    """连败翻转(锁 2):落卡前 -2 → 落地后 ==4(带符号绝对置位,
    「变为」字面覆盖连败态,非负向递增亦非保持)。"""
    b = _backend(seed=42)
    try:
        gs = b.gs
        _drive_to_offer(b)
        _seed_streak(gs, -2)
        _pick(b, '胜利,还是胜利', ['胜利,还是胜利', '躺平', '淘金客'])
        assert gs.streak.value == 4, f'连败翻转: {gs.streak.value}'
    finally:
        uninstall_backend()


def test_high_streak_falls_back_to_set_value() -> None:
    """高连胜回落(锁 3):落卡前 6 → 落地后 ==4(绝对置位非
    max(现值,置位值),外加抬升读法被设计裁决点 4 否决)。"""
    b = _backend(seed=43)
    try:
        gs = b.gs
        _drive_to_offer(b)
        _seed_streak(gs, 6)
        _pick(b, '胜利,还是胜利', ['胜利,还是胜利', '躺平', '淘金客'])
        assert gs.streak.value == 4, f'高连胜回落: {gs.streak.value}'
    finally:
        uninstall_backend()


def test_unpicked_card_zero_write_and_latch_consumed() -> None:
    """无效载荷零写(锁 4):opts 含本卡但不落卡(选另一张)→ 交集空
    零写,且呈现一次性标志位已消费(picked 空亦消费 = 每呈现窗至多一次落地消费,
    无效载荷的重放同样不得再触发)。advance 前直构一次性标志位 True:锁面 =
    消费支被武装下的交集空支,一次性标志位自始 None 则断言空转锁面失效。"""
    b = _backend(seed=44)
    try:
        gs = b.gs
        _drive_to_offer(b)
        b._strategy_pick_streak_latch = True
        streak0, ev0 = gs.streak.value, gs.streak.evidence
        _pick(b, '躺平', ['胜利,还是胜利', '躺平', '淘金客'])
        assert '躺平' in (gs.active_strategies.value or [])
        assert '胜利,还是胜利' not in (gs.active_strategies.value or [])
        assert gs.streak.value == streak0 and gs.streak.evidence == ev0, \
            f'未落卡出现置位笔: {gs.streak.value} / {gs.streak.evidence}'
        assert b._strategy_pick_streak_latch is None, '一次性标志位未消费'
    finally:
        uninstall_backend()


def test_card_without_leg_zero_write() -> None:
    """表外卡零写(锁 5):落无 streak_set 条目卡(经验到账)→ 注册表
    直读 miss→0 跳写(通用通道辖域 = streak_set≠0,非单卡特判的
    反向证据)。"""
    b = _backend(seed=45)
    try:
        gs = b.gs
        _drive_to_offer(b)
        _seed_streak(gs, 1)
        streak0, ev0 = gs.streak.value, gs.streak.evidence
        _pick(b, '经验到账', ['经验到账', '躺平', '淘金客'])
        assert gs.streak.value == streak0 and gs.streak.evidence == ev0, \
            f'表外卡出现置位笔: {gs.streak.value} / {gs.streak.evidence}'
    finally:
        uninstall_backend()


def test_replay_zero_write_when_latch_closed_then_single_write_when_open(
        _always_win) -> None:
    """重放防回写(锁 6,两态直构一次性标志位态免流形依赖):①一次性标志位关(落地消费后
    未复置位)——置位后战斗推进至 5,重放同一落地 advance 零写(不得
    把 5 回写成 4,实害面);②一次性标志位开(直构呈现置位态)——重放恰一次
    置位写且一次性标志位再消费(锁面 = 一次性标志位本体是唯一闸,不是巧合不写)。"""
    b = _backend(seed=46)
    try:
        gs = b.gs
        _drive_to_offer(b)
        _seed_streak(gs, 1)
        decl = _pick(b, '胜利,还是胜利', ['胜利,还是胜利', '躺平', '淘金客'])
        assert gs.streak.value == 4
        assert b._strategy_pick_streak_latch is None
        # 一次性标志位关分支:战斗推进 4→5 后重放,零写(已推进真值不回写)。
        _drive_until(b, lambda: gs.streak.value == 5)
        assert _SETTLE_EV_PATTERN.match(gs.streak.evidence or ''), \
            f'推进笔非结算形态: {gs.streak.evidence}'
        cw_sim_ports.declare_world(decl)
        assert gs.streak.value == 5, f'一次性标志位关重放回写: {gs.streak.value}'
        assert _SETTLE_EV_PATTERN.match(gs.streak.evidence or ''), \
            f'一次性标志位关重放换笔: {gs.streak.evidence}'
        # 一次性标志位开分支:直构呈现置位态后重放,恰一次置位写。
        b._strategy_pick_streak_latch = True
        cw_sim_ports.declare_world(decl)
        assert gs.streak.value == 4, f'一次性标志位开置位未写: {gs.streak.value}'
        assert gs.streak.evidence == _STREAK_EV_PREFIX + '胜利,还是胜利'
        assert b._strategy_pick_streak_latch is None, '一次性标志位开消费缺失'
    finally:
        uninstall_backend()


def test_set_value_naturally_follows_settlement_chain(_always_win) -> None:
    """自然跟随回归(锁 8):置位 4 → 下一胜局结算 → ==5 且结算笔存在
    (置位值经现役共享链自动跟随,零新接入调用;结算笔与置位笔分账)。"""
    b = _backend(seed=47)
    try:
        gs = b.gs
        _drive_to_offer(b)
        _seed_streak(gs, 1)
        _pick(b, '胜利,还是胜利', ['胜利,还是胜利', '躺平', '淘金客'])
        assert gs.streak.value == 4
        _drive_until(b, lambda: gs.streak.value == 5)
        assert _SETTLE_EV_PATTERN.match(gs.streak.evidence or ''), \
            f'胜局转移笔缺失: {gs.streak.evidence}'
    finally:
        uninstall_backend()
