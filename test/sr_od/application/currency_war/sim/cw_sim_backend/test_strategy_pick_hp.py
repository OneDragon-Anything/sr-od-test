"""sim 策略选卡即时生命腿测试(镜像 src = sim/cw_sim_backend.py 的
apply_strategy_pick_hp helper + _on_invest_picked 落地腿 + 呈现闩 +
披露键 strategy_pick_instant_legs hp 族扩面)。

测试面依据 = 迭代设计 designs/T-127-jiankang-chongzhi.md §2.1/§4 三锁:
- 持卡发放真值(锁 1):offer 落地 advance 后 hp 恰 +30,独立 evidence
  笔 ``hp:strategy_pick:健康充值``(与开局 ``opening``/战斗
  ``battle:hp`` 笔分账),hp_trail 同步恰追加(落卡前/后/下一战斗三读),
  开局笔与战斗笔不受扰;
- 呈现闩防重放(锁 2):同 offer 落地 advance 重放 → 第二次零写(xp 腿
  闩锁同形,轨迹亦不再追加);
- 无卡局零扰动(锁 3):opts 含本卡但不落卡(选另一张)→ 落地交集空 →
  零 ``hp:strategy_pick`` 笔、hp 零增量(名单推导负例,防误发)。

复用声明:引擎驱动助手 import 自 sim/test_sim_backend.py(在册超限
拆分债文件,禁追加,只 import 复用不改)与 cw_sim_backend/
test_p3_win_terminal.py(先例 = 同目录 test_strategy_pick_xp.py)。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war.sim.cw_sim_backend.test_p3_win_terminal import (
    _drive_step,
)
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_strategy_param,
)
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_INVEST_STRATEGY,
    SCREEN_PREP,
    SimBackend,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

#: hp 即时腿独立笔 evidence 前缀(单一源 = cw_sim_base.sim_evidence
#: 契约:前缀 sim:engine: + 写点 tag hp:strategy_pick:<卡名>)。
_HP_EV_PREFIX = 'sim:engine:hp:strategy_pick:'

#: 战斗结算 hp 写行 evidence 全串(开局/战斗笔分账的对照锚)。
_BATTLE_HP_EV = 'sim:engine:battle:hp'


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
    """驱动至策略 offer 呈现(固定日程首槽 P1r3 起;呈现即置即时生命
    腿闩——本腿生效前提)。"""
    _drive_until(b, lambda: b.screen_identity() == SCREEN_INVEST_STRATEGY)


def _pick(b: SimBackend, name: str, opts: list[str]) -> WorldDecl:
    """定向选卡落地(直写 opts 定卡 + 上报 + 声明喂入;现役 harness
    形态先例 = test_strategy_pick_xp._pick)。返回声明供重放用例复喂。"""
    gs = b.gs
    gs.write_logic(gs.invest_strategy_opts, opts,
                   produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_strategy_param(
        gs, SimpleNamespace(norm_name=name), _SIG, session=SimpleNamespace())
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    return out.world_decl


def test_pick_grants_exact_instant_hp_with_trail_append() -> None:
    """持卡发放真值(锁 1):offer 落地后 hp 恰 +30,独立 evidence 笔与
    开局/战斗笔分账,hp_trail 落卡前/后/下一战斗三读同步恰追加——开局
    笔不被扰、下一战斗笔照常落账(写流↔轨迹同构的选卡腿延伸形态)。"""
    b = _backend()
    try:
        gs = b.gs
        _drive_to_offer(b)
        hp_before = int(gs.hp.value)
        trail_before = list(b.hp_trail)
        assert trail_before and trail_before[-1] == hp_before, \
            f'开局轨迹首段异常: {trail_before} vs {hp_before}'
        _pick(b, '健康充值', ['健康充值', '躺平', '淘金客'])
        assert gs.hp.value == hp_before + 30, f'hp 恰 +30: {gs.hp.value}'
        assert gs.hp.evidence == _HP_EV_PREFIX + '健康充值', \
            f'独立笔缺失或来源漂移: {gs.hp.evidence}'
        trail_after = list(b.hp_trail)
        assert trail_after == trail_before + [hp_before + 30], \
            f'轨迹未同步恰追加: {trail_after} vs {trail_before}'
        # 下一战斗三读:战斗结算笔照常追加且选卡 +30 笔不被扰。
        _drive_until(b, lambda: len(b.hp_trail) > len(trail_after))
        assert gs.hp.evidence == _BATTLE_HP_EV, \
            f'下一笔应为战斗结算笔: {gs.hp.evidence}'
        assert b.hp_trail[-1] == int(gs.hp.value), \
            f'战斗笔轨迹不同步: {b.hp_trail[-1]} vs {gs.hp.value}'
        assert len(b.hp_trail) == len(trail_after) + 1, \
            f'战斗间轨迹多笔: {b.hp_trail}'
    finally:
        uninstall_backend()


def test_replay_advance_zero_double_grant() -> None:
    """呈现闩防重放(锁 2):同 offer 落地 advance 重放一次 → 第二次
    零写(闩已消费;hp 值/evidence/轨迹三方均不再动)。"""
    b = _backend(seed=42)
    try:
        gs = b.gs
        _drive_to_offer(b)
        hp0 = int(gs.hp.value)
        trail0 = len(b.hp_trail)
        decl = _pick(b, '健康充值', ['健康充值', '躺平', '淘金客'])
        assert gs.hp.value == hp0 + 30
        assert len(b.hp_trail) == trail0 + 1
        cw_sim_ports.declare_world(decl)
        assert gs.hp.value == hp0 + 30, f'重放双发: {gs.hp.value}'
        assert gs.hp.evidence == _HP_EV_PREFIX + '健康充值'
        assert len(b.hp_trail) == trail0 + 1, \
            f'重放轨迹追加: {b.hp_trail}'
    finally:
        uninstall_backend()


def test_unpicked_card_zero_grant() -> None:
    """无卡局零扰动(锁 3):opts 含本卡但不落卡(选另一张)→ 落地
    交集空 → 零 hp:strategy_pick 笔、hp 零增量、轨迹零追加(闩同拍
    消费,本次不残留)。"""
    b = _backend(seed=43)
    try:
        gs = b.gs
        _drive_to_offer(b)
        hp0, ev0 = gs.hp.value, gs.hp.evidence
        trail0 = len(b.hp_trail)
        _pick(b, '躺平', ['健康充值', '躺平', '淘金客'])
        assert '躺平' in (gs.active_strategies.value or [])
        assert '健康充值' not in (gs.active_strategies.value or [])
        assert gs.hp.value == hp0 and gs.hp.evidence == ev0, \
            f'未落卡出现 hp 笔: {gs.hp.value} / {gs.hp.evidence}'
        assert len(b.hp_trail) == trail0, f'未落卡轨迹追加: {b.hp_trail}'
    finally:
        uninstall_backend()
