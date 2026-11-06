"""sim 策略选卡即时生命效果条目测试(镜像 src = sim/cw_sim_backend.py 的
apply_strategy_pick_hp helper + _on_invest_picked 落地效果条目 + 呈现一次性标志位 +
披露键 strategy_pick_instant_legs hp 族扩面)。

测试面依据 = 迭代设计 designs/T-127-jiankang-chongzhi.md §2.1/§4 三锁:
- 持卡发放真值(锁 1):offer 落地 advance 后 hp 恰 +30,独立 evidence
  笔 ``hp:strategy_pick:健康充值``(与开局 ``opening``/战斗
  ``battle:hp`` 笔分账),hp_trail 同步恰追加(落卡前/后/下一战斗三读),
  开局笔与战斗笔不受扰;
- 呈现一次性标志位防重放(锁 2):同 offer 落地 advance 重放 → 第二次零写(xp 效果条目
  一次性标志位锁同形,轨迹亦不再追加);
- 无卡局零扰动(锁 3):opts 含本卡但不落卡(选另一张)→ 落地交集空 →
  零 ``hp:strategy_pick`` 笔、hp 零增量(名单推导负例,防误发)。
T-144 先亏后盈随批扩面(designs/T-144-xiankui-houying.md §4 锁 3/5/8
+ 扩调用点漂移增量锁):负值支 delta 断言形 / 不 clip 下界直构与败局
floor 分支 / 持保险局选卡损血扩调用点入累计器 / 双持独立笔互不聚合。

复用声明:引擎驱动助手 import 自 sim/test_sim_backend.py(已登记超限
拆分债文件,禁追加,只 import 复用不改)与 cw_sim_backend/
test_p3_win_terminal.py(先例 = 同目录 test_strategy_pick_xp.py)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war.sim.cw_sim_backend.test_p3_win_terminal import (
    _drive_step,
)
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _SIG_OBS,
    _force_settle,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_strategy_param,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    equips_by_category,
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

#: hp 即时效果条目独立笔 evidence 前缀(单一源 = cw_sim_base.sim_evidence
#: 契约:前缀 sim:engine: + 写点 tag hp:strategy_pick:<卡名>)。
_HP_EV_PREFIX = 'sim:engine:hp:strategy_pick:'

#: 战斗结算 hp 写行 evidence 全串(开局/战斗笔分账的对照基准)。
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
    效果条目一次性标志位——本效果条目生效前提)。"""
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
    笔不被扰、下一战斗笔照常落账(写流↔轨迹同构的选卡效果条目延伸形态)。"""
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
    """呈现一次性标志位防重放(锁 2):同 offer 落地 advance 重放一次 → 第二次
    零写(一次性标志位已消费;hp 值/evidence/轨迹三方均不再动)。"""
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
    交集空 → 零 hp:strategy_pick 笔、hp 零增量、轨迹零追加(一次性标志位同拍
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


# ============================================================ T-144 扩面
# 负值支(先亏后盈 −20)与扩调用点(损血档位触发族第二调用点)


def test_pick_hp_loss_delta_written_negative() -> None:
    """负值支 delta 断言形(锁 3 扩面):持卡局选卡先亏后盈 → hp 写行
    after = 落地前值 − 20(禁 value 形——轨迹/写行承载值序列,断言
    「值恰 −20」与 −5 直构局自相矛盾),独立 evidence 笔,hp_trail 同步
    恰追加一行同值,开局笔与战斗笔不受扰。"""
    b = _backend(seed=44)
    try:
        gs = b.gs
        _drive_to_offer(b)
        hp_before = int(gs.hp.value)
        trail_before = list(b.hp_trail)
        _pick(b, '先亏后盈', ['先亏后盈', '躺平', '淘金客'])
        assert gs.hp.value == hp_before - 20, \
            f'delta 恰 −20: {gs.hp.value} vs {hp_before}'
        assert gs.hp.evidence == _HP_EV_PREFIX + '先亏后盈', \
            f'独立笔缺失或来源漂移: {gs.hp.evidence}'
        assert list(b.hp_trail) == trail_before + [hp_before - 20], \
            f'轨迹未同步恰追加: {list(b.hp_trail)} vs {trail_before}'
        # 下一战斗笔照常落账,选卡损血笔不被扰(写流↔轨迹同构保持)。
        _drive_until(b, lambda: len(b.hp_trail) > len(trail_before) + 1)
        assert gs.hp.evidence == _BATTLE_HP_EV, \
            f'下一笔应为战斗结算笔: {gs.hp.evidence}'
    finally:
        uninstall_backend()


def test_negative_no_clip_floor_branch_next_lost_battle() -> None:
    """不 clip 下界 + §1.4 机械推论(锁 5):直构 hp=15 → 选卡写 −5
    (负值直加不 clip,hp 出负 = 下界无消费端语义);下一败局结算按
    apply_hp_outcome ≤0 分支 → 首次保底剩 1(floor 位写真)。钉死
    「效果条目不 clip」默认案与「选卡写不经 floor 判定」边界。"""
    b = _backend(seed=45)
    mp = pytest.MonkeyPatch()
    try:
        gs = b.gs
        _drive_to_offer(b)
        gs.observe(gs.hp, 15, sig=_SIG_OBS)
        _pick(b, '先亏后盈', ['先亏后盈', '躺平', '淘金客'])
        assert gs.hp.value == -5, f'负值直加不 clip: {gs.hp.value}'
        assert -5 in b.hp_trail, f'轨迹含 −5: {list(b.hp_trail)}'
        _force_settle(mp, won=False)
        _drive_until(b, lambda: b.hp_trail[-1] == 1 or int(gs.hp.value) == 1)
        assert gs.hp.value == 1, \
            f'败局首次保底应剩 1(≤0 分支): {gs.hp.value}'
        assert gs.hp_floor_triggered.value is True, '保底位未写'
        assert b.hp_trail[-1] == int(gs.hp.value), \
            f'战斗笔轨迹不同步: {b.hp_trail[-1]} vs {gs.hp.value}'
    finally:
        mp.undo()
        uninstall_backend()


def test_pick_loss_feeds_insurance_accumulator_hook() -> None:
    """扩调用点行为锁(漂移增量):持保险局直构选卡先亏后盈 → 损血效果条目
    写后同拍调 check_strategy_hp_loss_grants:−20 换算 +20 损失入累计
    器(非「减负」)→ 档位当拍触发:金 +5(桶数 1)∧ 简易装备 +1 件
    ∧ 累计器取模回 0。扩调用点缺位时此局静默漏计(披露键 ③ 申报形态),
    本锁钉死第二调用点在码。"""
    b = _backend(seed=46)
    try:
        gs = b.gs
        _drive_to_offer(b)
        gs.write_logic(gs.active_strategies, ['保险'],
                       produced_by='test-seed', evidence='t:card', sig=_SIG)
        hp_before = int(gs.hp.value)
        gold_before = int(gs.gold.value or 0)
        equips_before = list(gs.equips.value or [])
        trail_before = len(b.hp_trail)
        _pick(b, '先亏后盈', ['先亏后盈', '躺平', '淘金客'])
        assert gs.hp.value == hp_before - 20, '前置:损血效果条目应写 −20'
        assert len(b.hp_trail) == trail_before + 1, '前置:轨迹恰追加一笔'
        assert gs.strategy_hp_loss_accum.value == 0, \
            f'累计器应 +20 入账后取模回 0: {gs.strategy_hp_loss_accum.value}'
        assert gs.gold.value == gold_before + 5, \
            f'保险档位金应 +5(1 桶): {gs.gold.value} vs {gold_before}'
        assert len(gs.equips.value or []) == len(equips_before) + 1, \
            f'保险档位装备应 +1 件: {gs.equips.value}'
        assert gs.equips.value[-1] in set(equips_by_category('简易')), \
            f'装备名出简易池: {gs.equips.value[-1]!r}'
    finally:
        uninstall_backend()


def test_dual_hold_independent_pens_not_aggregated() -> None:
    """双持独立笔(锁 8):健康充值 + 先亏后盈 同局双持(excluded_invest
    只防同卡,跨卡双持可达——前置持健康充值局再拿先亏后盈,opts 交集
    命中两卡)→ +30 与 −20 各自独立 hp 写行按 opts 序落账([b+30,
    b+10] 两行,互不聚合 = 禁聚合通道回归,聚合字段集不含 hp_instant);
    轨迹按写行粒度恰 +2(追加读现值语义 = 效果条目返回笔数,同拍多笔共用
    末值,逐值对拍归单笔锁)。"""
    b = _backend(seed=47)
    mp = pytest.MonkeyPatch()
    try:
        gs = b.gs
        _drive_to_offer(b)
        gs.write_logic(gs.active_strategies, ['健康充值'],
                       produced_by='test-seed', evidence='t:card', sig=_SIG)
        hp_before = int(gs.hp.value)
        hp_pens: list[tuple[str | None, int]] = []
        real_observe = gs.observe

        def _rec(target, value, **kw):
            if gs._field_name(target) == 'hp':
                hp_pens.append((kw.get('evidence'), value))
            return real_observe(target, value, **kw)

        mp.setattr(gs, 'observe', _rec)
        trail_before = len(b.hp_trail)
        _pick(b, '先亏后盈', ['健康充值', '先亏后盈', '躺平'])
        assert gs.hp.value == hp_before + 10, \
            f'双持净额 +30−20=+10: {gs.hp.value} vs {hp_before}'
        assert hp_pens == [
            (_HP_EV_PREFIX + '健康充值', hp_before + 30),
            (_HP_EV_PREFIX + '先亏后盈', hp_before + 10)], \
            f'双持应两笔独立写行(禁聚合): {hp_pens}'
        assert len(b.hp_trail) == trail_before + 2, \
            f'轨迹按写行粒度恰 +2: {list(b.hp_trail)}'
    finally:
        mp.undo()
        uninstall_backend()
