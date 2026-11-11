"""kernel 获得链交换分支测试(镜像 src = kernel/cw_gain_chain.py 的
on_strategy_gained economy 交换分支 + cw_investments.SQUAD_HP_CAP;按
被测方法拆目录规范落位,先例 = 同目录 test_gain_invest_strategy_pick_
grant.py)。

测试面依据 = 原稿锁面 §4 锁 1-4(原稿评审锁(§ 号 = 原稿节序)§五.④ 同面):
- 注册行锁(锁 1):STRATEGY_ECONOMY['不等价交换'].hp_gold_swap is True,
  防注册漂移;
- 交换行为锁(锁 2):持卡获得 → hp == min(gold_old, SQUAD_HP_CAP) ∧
  gold == hp_old,双字段各一条逻辑写且 evidence 同串
  ``strategy:hp_gold_swap``;无卡安静零写;
- clip 锁(锁 3):gold=150 → hp 落 SQUAD_HP_CAP 且等值仍落写行;
  gold=0 → hp 字面落 0(死亡判定归战斗结算链,本分支零改);gold 侧
  无截断(gold 写后 == hp_old,防 clip 误泛化到 gold 侧);
- None 闸锁(锁 4):hp/gold 任一 None → 双字段零写跳过(宁缺勿造,
  apply_equip_acquire_hp 同闸)。
构造沿现役获得链测试先例:GameState 直构 + 观察面播种 + report_action_
pick_invest_strategy_param 上报;写行凭据 = 状态 journal sink 内存捕获
(run_id 两件套装配,先例 = kernel/test_game_state.py journal fixture)。
"""
from __future__ import annotations

from collections.abc import Callable

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_strategy_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    set_run_id_provider,
    set_state_journal_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    SQUAD_HP_CAP,
    STRATEGY_ECONOMY,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionPickInvestStrategyParam,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

#: 双字段交换写行的 evidence 同串(单一源 = cw_gain_chain 交换分支
#: 写点字面)。
_SWAP_EVIDENCE = 'strategy:hp_gold_swap'


def _make_gs(hp: int | None, gold: int | None) -> GameState:
    """观测面组装(hp/gold 观察直构;None = 不播种保持字段未知态)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if hp is not None:
        gs.observe(gs.hp, hp, sig=_SIG_OBS)
    if gold is not None:
        gs.observe(gs.gold, gold, sig=_SIG_OBS)
    return gs


def _pick_card(gs: GameState, name: str) -> None:
    """定向选卡上报(获得链全链直入;session 缺省 = 登记分支跳过,
    本卡 ∉ STRATEGY_EFFECTS 登记面本就为零)。"""
    out = report_action_pick_invest_strategy_param(
        gs, CwActionPickInvestStrategyParam(idx=0, norm_name=name), _LSIG)
    assert out.applied and out.reason == 'gain_chain_applied'


def _journal_capture(action: Callable[[], None]) -> list[dict]:
    """journal sink 内存捕获(run_id 两件套装配,finally 必卸;先例 =
    kernel/test_game_state.py journal fixture)。"""
    rows: list[dict] = []
    set_state_journal_sink(rows.append)
    set_run_id_provider(lambda: 'run_probe')
    try:
        action()
    finally:
        set_state_journal_sink(None)
        set_run_id_provider(None)
    return rows


def _write_rows(rows: list[dict], field: str) -> list[dict]:
    return [r for r in rows
            if r.get('row') == 'write' and r.get('field') == field]


def test_registry_row_holds_swap_flag() -> None:
    """注册行锁(锁 1):STRATEGY_ECONOMY['不等价交换'].hp_gold_swap
    is True(防注册漂移;血本位族判据 is_blood_economy 依赖此位)。"""
    eff = STRATEGY_ECONOMY['不等价交换']
    assert eff.hp_gold_swap is True


def test_swap_writes_both_fields_with_shared_evidence() -> None:
    """交换行为锁(锁 2):持卡获得 → hp == min(gold_old, SQUAD_HP_CAP)
    ∧ gold == hp_old;双字段各一条逻辑写行,evidence 同串;换未收录卡
    → 双字段零写(查无安静零写)。"""
    gs = _make_gs(hp=30, gold=150)
    rows = _journal_capture(lambda: _pick_card(gs, '不等价交换'))
    assert gs.hp.value == min(150, SQUAD_HP_CAP), \
        f'hp 应 = min(gold_old, 上界): {gs.hp.value}'
    assert gs.gold.value == 30, f'gold 应 = hp_old: {gs.gold.value}'
    assert gs.hp.evidence == _SWAP_EVIDENCE, f'hp evidence: {gs.hp.evidence}'
    assert gs.gold.evidence == _SWAP_EVIDENCE, \
        f'gold evidence: {gs.gold.evidence}'
    hp_rows = _write_rows(rows, 'hp')
    gold_rows = _write_rows(rows, 'gold')
    assert len(hp_rows) == 1 and hp_rows[0]['after'] == SQUAD_HP_CAP
    assert len(gold_rows) == 1 and gold_rows[0]['after'] == 30
    # 无卡负例:未收录卡走同口上报,双字段零写(值与 evidence 均不动)。
    hp_ev, gold_ev = gs.hp.evidence, gs.gold.evidence
    rows2 = _journal_capture(
        lambda: _pick_card(gs, '随便一张未收录卡'))
    assert gs.hp.value == SQUAD_HP_CAP and gs.gold.value == 30, \
        '无卡不应写 hp/gold'
    assert gs.hp.evidence == hp_ev and gs.gold.evidence == gold_ev
    assert not _write_rows(rows2, 'hp') and not _write_rows(rows2, 'gold')


def test_clip_caps_hp_and_gold_side_unclamped() -> None:
    """clip 锁(锁 3):gold=150 → hp 落 SQUAD_HP_CAP;gold=0 → hp 字面
    落 0(死亡判定归战斗结算链,交换分支零改);gold 侧无截断(gold 写
    后 == hp_old,防 clip 误泛化到 gold 侧)。"""
    # 上界截断:hp := min(150, 100) = 100,gold := hp_old = 30(非 100)。
    gs = _make_gs(hp=30, gold=150)
    rows = _journal_capture(lambda: _pick_card(gs, '不等价交换'))
    assert gs.hp.value == SQUAD_HP_CAP, f'上界截断: {gs.hp.value}'
    assert gs.gold.value == 30, \
        f'gold 侧无截断(应 == hp_old): {gs.gold.value}'
    assert _write_rows(rows, 'gold')[0]['after'] == 30
    # 下界字面 0:gold=0 选卡 → hp=0(不设 floor,保底写端唯一在
    # apply_hp_outcome 战斗结算链)。
    gs2 = _make_gs(hp=30, gold=0)
    rows2 = _journal_capture(lambda: _pick_card(gs2, '不等价交换'))
    assert gs2.hp.value == 0, f'下界字面 0: {gs2.hp.value}'
    assert gs2.gold.value == 30
    assert _write_rows(rows2, 'hp')[0]['after'] == 0


def test_equal_value_swap_still_lands_write_rows() -> None:
    """等值仍落写(锁 3 等值支):hp == min(gold, SQUAD_HP_CAP) 已相等
    时交换写行照落(same_value 行在案;先例 = apply_hp_outcome 胜局支
    等值写)——模拟器轨迹配对按「每发恰一写行」计数,漏写行会破写流
    ↔轨迹同构。"""
    gs = _make_gs(hp=50, gold=50)
    rows = _journal_capture(lambda: _pick_card(gs, '不等价交换'))
    assert gs.hp.value == 50 and gs.gold.value == 50
    hp_rows = _write_rows(rows, 'hp')
    gold_rows = _write_rows(rows, 'gold')
    assert len(hp_rows) == 1 and hp_rows[0]['same_value'] is True, \
        f'等值 hp 写行应在案: {hp_rows}'
    assert len(gold_rows) == 1 and gold_rows[0]['same_value'] is True, \
        f'等值 gold 写行应在案: {gold_rows}'
    assert gs.hp.evidence == _SWAP_EVIDENCE and \
        gs.gold.evidence == _SWAP_EVIDENCE


def test_none_precondition_skips_both_writes() -> None:
    """None 闸锁(锁 4):hp/gold 任一 None → 双字段零写跳过(宁缺勿造;
    gold 播种后恒有值故模拟器结构性不触发,None 闸 = live 防御面)。"""
    # hp None:双字段零写(gold 不变)。
    gs = _make_gs(hp=None, gold=50)
    rows = _journal_capture(lambda: _pick_card(gs, '不等价交换'))
    assert gs.hp.value is None and gs.gold.value == 50, \
        f'hp None 应双零写: {gs.hp.value} / {gs.gold.value}'
    assert not _write_rows(rows, 'hp') and not _write_rows(rows, 'gold')
    # gold None:同(双字段零写,hp 不变)。
    gs2 = _make_gs(hp=40, gold=None)
    rows2 = _journal_capture(lambda: _pick_card(gs2, '不等价交换'))
    assert gs2.hp.value == 40 and gs2.gold.value is None, \
        f'gold None 应双零写: {gs2.hp.value} / {gs2.gold.value}'
    assert not _write_rows(rows2, 'hp') and not _write_rows(rows2, 'gold')
