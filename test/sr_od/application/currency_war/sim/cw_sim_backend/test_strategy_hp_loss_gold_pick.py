"""sim 策略选卡已损血衍生金币效果条目测试(镜像 src = sim/cw_sim_backend.py 的
_on_invest_picked 已损血衍生金落地效果条目 + 呈现一次性标志位 + 披露键;kernel 触发函数
单元面 = kernel/cw_gain_chain/test_check_strategy_hp_loss_gold.py,本文件
锁 sim 选卡落地效果条目接入调用与状态副本里的值落地面)。

测试面依据 = 设计稿(原件已退役;§ 号 = 原稿节序)§4 锁 4
(已退役评审稿 无需用户决定 7/7;驱动与断言形态先例 = 同目录
test_strategy_pick_hp.py):
- 持卡发放真值:直构损血后选卡落地 → 金笔存在且 amount == max(0,
  opening−hp),独立 evidence 笔 ``strategy:hp_loss_gold``,sig = obs 族
  'sim:strategy' 组,披露键随局申报;
- 呈现一次性标志位防重放:同 offer 落地 advance 重放 → 第二次零写;
- 零损失选卡(开局即选,hp == 开局基线)→ 检查函数返回 0 = 零笔零申报;
- 无卡局零扰动:opts 含本卡但不落卡(选另一张)→ 落地交集空 → 零金笔。

复用声明:引擎驱动助手 import 自 sim/test_sim_backend.py(已登记超限
拆分债文件,禁追加,只 import 复用不改)与 cw_sim_backend/
test_p3_win_terminal.py(先例 = 同目录 test_strategy_pick_hp.py)。
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
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_strategy_param,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_HP_LOSS_GOLD_BASELINE_ASSUMPTION,
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

#: 衍生金币效果条目独立笔 evidence 全串(单一源 = cw_sim_base.sim_evidence
#: 契约:前缀 sim:engine: + 写点 tag strategy:hp_loss_gold)。
_GOLD_EV = 'sim:engine:strategy:hp_loss_gold'


def _backend(seed: int = 51) -> SimBackend:
    """装配后端至 P1r1 备战屏(调用方负责 uninstall;装配形态先例 =
    test_strategy_pick_hp._backend)。"""
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
    test_strategy_pick_hp._drive_until)。"""
    for _ in range(limit):
        if pred():
            return
        _drive_step(b, 37)
    raise AssertionError('驱动步数超限,谓词未达成')


def _drive_to_offer(b: SimBackend) -> None:
    """驱动至策略 offer 呈现(固定日程首槽;呈现即置衍生金币效果条目一次性标志位——本效果条目
    生效前提)。"""
    _drive_until(b, lambda: b.screen_identity() == SCREEN_INVEST_STRATEGY)


def _pick(b: SimBackend, name: str, opts: list[str]) -> WorldDecl:
    """定向选卡落地(直写 opts 定卡 + 上报 + 声明喂入;现役 harness
    形态先例 = test_strategy_pick_hp._pick)。返回声明供重放用例复喂。"""
    gs = b.gs
    gs.write_logic(gs.invest_strategy_opts, opts,
                   produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_strategy_param(
        gs, SimpleNamespace(norm_name=name), _SIG, session=SimpleNamespace())
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    return out.world_decl


def test_pick_grants_exact_hp_loss_gold_with_disclosure(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """持卡发放真值:直构损血 25 后选卡落地 → 金笔 +25,evidence/sig
    形态 + 建模假设披露键随局申报(开局基线 = hp_trail[0] 开局真值,
    非 hp 现值)。"""
    b = _backend()
    try:
        gs = b.gs
        _drive_to_offer(b)
        opening_hp = b.hp_trail[0]
        gs.observe(gs.hp, opening_hp - 25, sig=_SIG_OBS)   # 直构已损 25
        gold_before = int(gs.gold.value or 0)
        gold_pens: list[tuple[str | None, int, object]] = []
        real_observe = gs.observe

        def _rec(target, value, **kw):
            if gs._field_name(target) == 'gold':
                gold_pens.append((kw.get('evidence'), value,
                                  kw.get('sig')))
            return real_observe(target, value, **kw)

        monkeypatch.setattr(gs, 'observe', _rec)
        _pick(b, '星际和平保险', ['星际和平保险', '躺平', '淘金客'])
        assert gs.gold.value == gold_before + 25, \
            f'衍生金恰 +25: {gs.gold.value} vs {gold_before}'
        assert gs.gold.evidence == _GOLD_EV, \
            f'独立笔缺失或来源漂移: {gs.gold.evidence}'
        pens = [p for p in gold_pens if p[0] == _GOLD_EV]
        assert len(pens) == 1, f'衍生金笔数漂移: {gold_pens}'
        assert pens[0][2] is not None \
            and pens[0][2].family == 'obs' \
            and pens[0][2].group_id == 'sim:strategy', \
            f'sig 组漂移: {pens[0][2]}'
        assert b.disclosures.get(STRATEGY_HP_LOSS_GOLD_BASELINE_ASSUMPTION) \
            == 'opening_minus_current_sim_model_v0', \
            '基线判读申报披露键未随局申报'
    finally:
        monkeypatch.undo()
        uninstall_backend()


def test_replay_advance_zero_double_grant() -> None:
    """呈现一次性标志位防重放:同 offer 落地 advance 重放一次 → 第二次零写(一次性标志位已
    消费;金值/evidence/披露键三方均不再动)。"""
    b = _backend(seed=52)
    try:
        gs = b.gs
        _drive_to_offer(b)
        opening_hp = b.hp_trail[0]
        gs.observe(gs.hp, opening_hp - 10, sig=_SIG_OBS)
        gold0 = int(gs.gold.value or 0)
        decl = _pick(b, '星际和平保险', ['星际和平保险', '躺平', '淘金客'])
        assert gs.gold.value == gold0 + 10
        assert gs.gold.evidence == _GOLD_EV
        cw_sim_ports.declare_world(decl)
        assert gs.gold.value == gold0 + 10, f'重放双发: {gs.gold.value}'
        assert gs.gold.evidence == _GOLD_EV, \
            f'重放笔 evidence 漂移: {gs.gold.evidence}'
    finally:
        uninstall_backend()


def test_zero_loss_pick_no_gold_pen() -> None:
    """零损失选卡(开局即选,hp == 开局基线)→ 衍生金 0 = 零笔零申报
    (与游戏「已损失 0 → 金 0」自算同形)。"""
    b = _backend(seed=53)
    try:
        gs = b.gs
        _drive_to_offer(b)
        assert int(gs.hp.value) == b.hp_trail[0], \
            f'前置:首槽前应零损血(现值 {gs.hp.value} vs 基线 ' \
            f'{b.hp_trail[0]})'
        gold0, ev0 = gs.gold.value, gs.gold.evidence
        _pick(b, '星际和平保险', ['星际和平保险', '躺平', '淘金客'])
        assert gs.gold.value == gold0, \
            f'零损失选卡误发金: {gs.gold.value} vs {gold0}'
        assert gs.gold.evidence == ev0, \
            f'零损失选卡出金笔: {gs.gold.evidence}'
        assert STRATEGY_HP_LOSS_GOLD_BASELINE_ASSUMPTION \
            not in b.disclosures, '零额选卡误申报披露键'
    finally:
        uninstall_backend()


def test_unpicked_card_zero_grant() -> None:
    """无卡局零扰动(名单推导负例):opts 含本卡但不落卡(选另一张)→
    落地交集空 → 零金笔、金零增量(一次性标志位同拍消费,本次不残留)。"""
    b = _backend(seed=54)
    try:
        gs = b.gs
        _drive_to_offer(b)
        opening_hp = b.hp_trail[0]
        gs.observe(gs.hp, opening_hp - 30, sig=_SIG_OBS)
        gold0, ev0 = gs.gold.value, gs.gold.evidence
        _pick(b, '躺平', ['星际和平保险', '躺平', '淘金客'])
        assert '躺平' in (gs.active_strategies.value or [])
        assert '星际和平保险' not in (gs.active_strategies.value or [])
        assert gs.gold.value == gold0 and gs.gold.evidence == ev0, \
            f'未落卡出现衍生金笔: {gs.gold.value} / {gs.gold.evidence}'
    finally:
        uninstall_backend()
