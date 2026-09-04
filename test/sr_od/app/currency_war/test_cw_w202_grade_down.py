# -*- coding: utf-8 -*-
"""W202/ADR-0382 补完保护集分级单帧锁(136 型构造闭死修法)。

锁验收(锁构造行为,不锁分布):
1. 主锁:undeploy 常规候选枯竭(deployed 全保护)且缺口已持续
   ≥_GRADE_PERSIST_ROUNDS 轮 → 补完事务发射,undeploy 吃 G0
   非引擎锁定线件(级内最弱先下),缺口体系件上场;
2. 持续门:首次缺口帧(门未过)仍 None(不硬拆,回 ADR-0371 语义);
3. flag off(grade_down=False)同帧恒 None(逐位回退);
4. G2 已成型引擎件不可动(DOT 成型,桑博/卡芙卡不下场);
5. registry 默认 True + evolution_step 注入链(strategy.py 一行)。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_evolution import (
    EvolutionState,
    _GRADE_PERSIST_ROUNDS,
    _engine_completion_tx,
    evolution_step,
)
from sr_od.application.currency_war.kernel.cw_intention import IntentionState

from sr_od.application.currency_war.kernel.cw_battle_calib import _board_factions_of
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    CompTransaction,
    GameState,
    _recount_board,
    simulate,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import StrategySession
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)


def _char(name: str, star: int = 1, row: str = 'back') -> BenchChar:
    c = CHARACTERS[name]
    return BenchChar(slot=0, char_id=name,
                     faction=(c.factions or ['?'])[0],
                     position_pref=row, star=star)


def _sess() -> StrategySession:
    """locked_comp 帧(大黑塔银河学者)+ 列车缺口 pair——136 型同构:
    锁定线件(黑塔/翡翠=locked_buy_scope∩非TT)= G0 候选;
    DOT 四件成型(ob≥2)= G2 不可动。"""
    sess = StrategySession()
    sess.v3_intention = IntentionState(
        p1_pair=('列车同行',), phase='locked',
        locked_comp='大黑塔银河学者')
    return sess


def _state(round_num: int = 6) -> GameState:
    """136 型帧:cap 6/7,bench 2 件列车(owned=2=tier,ob=0),
    deployed 六件全保护(黑塔/翡翠=锁定线 G0;桑博/卡芙卡/艾丝妲/
    椒丘=DOT 引擎件,ob=4 已成型=G2)。"""
    st = GameState()
    st.plane = 1
    st.round_num = round_num
    st.level = 7
    st.gold = 30
    st.bench = [_char('丹恒·饮月'), _char('姬子·启行')]
    dep = ['黑塔', '翡翠', '桑博', '卡芙卡', '艾丝妲', '椒丘']
    st.deployed = [(_char(n, star=2 if n == '翡翠' else 1,
                          row='front') if i < 3 else _char(n))
                   for i, n in enumerate(dep)]
    st.board = _recount_board(st.deployed)
    return st


def _completion_txs(actions: list) -> list[CompTransaction]:
    return [a for a in actions if isinstance(a, CompTransaction)
            and 'engine_complete' in (a.reason or '')]


def test_grade_down_fires_after_persist_gate():
    """①主锁:缺口持续门过后(连续第 _GRADE_PERSIST_ROUNDS 轮),
   全保护帧降级换血——G0 最弱锁定线件(黑塔 1★)被换下,列车件
   上场,DOT 成型引擎件(G2)不动。"""
    mem = EvolutionState()
    sess = _sess()
    for rn in range(6, 6 + _GRADE_PERSIST_ROUNDS - 1):
        # 门未过(持续 < 门值):None(不硬拆)
        assert _engine_completion_tx(
            _state(rn), sess, deficit_memory=mem) is None
    # 连续第门值轮:门过 → 事务发射(G0 分级降级)
    built = _engine_completion_tx(
        _state(6 + _GRADE_PERSIST_ROUNDS - 1), sess, deficit_memory=mem)
    assert built is not None
    tx, sys_key = built
    assert sys_key == '列车同行'
    st = _state(6 + _GRADE_PERSIST_ROUNDS - 1)
    out = simulate(st, tx)
    assert out.action_log[-1]['result'] == 'applied', out.action_log[-1]
    # 列车 on-board 达 tier(治愈 136 型「轮轮被选却建不出」)
    assert _board_factions_of(out.deployed).get('列车同行', 0) >= 2
    # undeploy = G0 最弱(黑塔 1★;翡翠 2★ 不先下)
    downed = {st.deployed[i].char_id for i in tx.undeploy}
    assert downed == {'黑塔'}, downed
    # G2 已成型引擎件(DOT ob=4)与 pair 件不下场
    assert not downed & {'桑博', '卡芙卡', '艾丝妲', '椒丘'}


def test_grade_down_gate_first_round_blocks():
    """②持续门:首遇缺口(未持续)不降级——回 ADR-0371「不硬拆」。"""
    mem = EvolutionState()
    # 独立 state 序列:第一次调用必 None(门未过),即使全保护
    assert _engine_completion_tx(_state(6), _sess(),
                                 deficit_memory=mem) is None
    assert mem.completion_deficit.get('列车同行') is not None  # 已登记


def test_grade_down_flag_off_restores():
    """③A/B 通道:grade_down=False 同帧恒 None(逐位回 ADR-0371/0381
    后「不硬拆」语义)。"""
    mem = EvolutionState()
    sess = _sess()
    for rn in range(6, 6 + _GRADE_PERSIST_ROUNDS):
        # 门随缺口登记推进(flag off 不影响计数),但全程 None
        assert _engine_completion_tx(_state(rn), sess, grade_down=False,
                                     deficit_memory=mem) is None
    # 对照:同 memory 已连续门值轮,开则立即发射
    assert _engine_completion_tx(
        _state(6 + _GRADE_PERSIST_ROUNDS), sess,
        deficit_memory=mem) is not None


def test_persist_gap_resets_counter():
    """④断档重置:缺口中断 >1 轮后再现 → 门重新计(不沿用旧计数)。"""
    mem = EvolutionState()
    sess = _sess()
    assert _engine_completion_tx(_state(6), sess,
                                 deficit_memory=mem) is None
    # r6 后直接 r9(间隔 3 >1)→ 重置,门未过仍 None;继续连续到
    # 门值轮前恒 None,门值轮发射
    rn = 9
    fired = False
    while rn < 9 + _GRADE_PERSIST_ROUNDS + 1:
        built = _engine_completion_tx(_state(rn), sess,
                                      deficit_memory=mem)
        if built is not None:
            fired = True
            break
        rn += 1
    assert fired, f'断档重置后应重新计门并在门值轮发射(rn={rn})'
    assert rn == 9 + _GRADE_PERSIST_ROUNDS - 1


def test_registry_default_and_wiring():
    """⑤registry 默认开 + evolution_step 注入(grade_down 透传 tx)。"""
    assert DEFAULT_REGISTRY.engine_complete_grade_down is True
    assert _GRADE_PERSIST_ROUNDS >= 2
    # evolution_step 级:同一 memory 连续驱动,门值轮出补完事务
    mem = EvolutionState()
    sess = _sess()
    for rn in range(6, 6 + _GRADE_PERSIST_ROUNDS - 1):
        assert not _completion_txs(evolution_step(_state(rn), sess, mem))
    txs = _completion_txs(
        evolution_step(_state(6 + _GRADE_PERSIST_ROUNDS - 1), sess, mem))
    assert len(txs) == 1
    # flag off:同帧(新 memory 同序)无补完事务
    mem2 = EvolutionState()
    for rn in range(6, 6 + _GRADE_PERSIST_ROUNDS):
        evolution_step(_state(rn), sess, mem2, grade_down=False)
    assert not _completion_txs(
        evolution_step(_state(6 + _GRADE_PERSIST_ROUNDS), sess, mem2,
                       grade_down=False))

# —— 换核隔离桶(2026-09-03 测试分层批)——
# 本文件属 legacy_baseline 桶:锁的是旧决策核(decision_v2)内部行为语义,
# 随旧核退役而消亡;默认全量与快速集均不跑,仅基线冻结审计/A-B 开跑前
# 两时点单独跑。口径见 sr-od-test/README.md「测试纪律 · legacy 桶」。
import pytest

pytestmark = pytest.mark.legacy_baseline
