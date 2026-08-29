"""W578:P1 配方锁帧的 target 载体物化(cw_intention.pair_target_comp)。

设计出处:ADR-0357(P1 锁定产物=体系对)+ W578 批 ADR(载体物化,
修 session.target_comp 在配方锁帧恒 None 导致的下游消费者断线——
部署选人/评分管线/投资装备钩子;边界声明:非 ADR-0442 删除的
transition_focus 复活,方向选择不动,只物化已锁方向)。

锁的是策略意图(「P1 配方方向对既有 target 消费者可见」「同 cap 内
先核心后填充」[21]),不锁具体发牌。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    pair_target_comp,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_deploy_logic import select_deployments
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.strategy import (
    DecisionV2Strategy,
)

_PAIR = ('列车同行', '持续伤害')


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 4, 'gold': 30, 'level': 5,
            'board': {}, 'bench': [], 'shop': [], 'hp': 80,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _pair_sess(pair: tuple[str, ...], plane: int = 1) -> tuple[
        DecisionV2Strategy, StrategySession, GameState]:
    """配方锁帧 fixture:ist.p1_pair 直设 + 段级守卫键置同轮(跳过
    update_intention,隔离派生逻辑——派生自有锁,本文件只锁写端物化)。"""
    strat = DecisionV2Strategy()
    sess = StrategySession()
    ist = IntentionState()
    ist.p1_pair = pair
    sess.v3_intention = ist
    sess.v3_intention_key = (plane, 4)   # = state 轮键 → 守卫跳过状态机驱动
    st = _state(plane=plane)
    return strat, sess, st


def _bench(name: str, faction: str, slot: int) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=1)


def test_pair_lock_frame_materializes_target() -> None:
    """配方锁帧:update_target 后 session.target_comp 非空,身份=已锁
    配方对(factions/core_chars/form_tiers 与 pair_target_comp 一致)。
    语义出处:W578(ADR-0357 锁定产物的载体化——修部署/评分/钩子
    消费者在 P1 配方锁局全盲的断线)。"""
    strat, sess, st = _pair_sess(_PAIR)
    strat.update_target(st, sess, None)
    tc = sess.target_comp
    assert tc is not None, 'P1 配方锁帧 target 载体不得为 None(断线病根)'
    assert tc.name == '过渡配方·列车同行+持续伤害'
    assert set(tc.factions) == {'列车同行', '持续伤害'}
    assert '三月七' in tc.core_chars and '艾丝妲' in tc.core_chars


def test_locked_comp_frame_takes_priority() -> None:
    """①锁局(locked_comp 非空)优先:真 Comp 不被配方伪 comp 覆盖
    (ADR-0357 ①类资格通道语义;w35 载体锁同口径)。"""
    strat, sess, st = _pair_sess(_PAIR)
    ist = sess.v3_intention
    ist.phase = 'locked'
    ist.locked_comp = '列车同行'
    strat.update_target(st, sess, None)
    assert sess.target_comp is not None
    assert sess.target_comp.name == '列车同行'


def test_p2_or_empty_pair_not_materialized() -> None:
    """辖域门:P2(p1_pair 残留)与 P1 空对均不物化——载体物化不越
    ADR-0357(P1 配方锁)辖域,P2 终局线走 locked_comp 通道。"""
    strat, sess, st = _pair_sess(_PAIR, plane=2)
    strat.update_target(st, sess, None)
    assert sess.target_comp is None
    strat2, sess2, st2 = _pair_sess(())
    strat2.update_target(st2, sess2, None)
    assert sess2.target_comp is None


def test_materialized_core_deploys_before_scatter() -> None:
    """部署传导(断点主修面行为锁):物化载体注入 target 后,cap 紧张
    (仅 1 空位)时 pair 成员在**引擎档内**被 tgt 身份前置——
    [21]「同 cap 内先核心后填充」。对照:无载体(旧断线形态)时两件
    同属引擎档且点火均 0,按槽序先者占位。断言序关系,不锁具体发牌。
    (构造:三月七=列车同行、饮月=仙舟,对 希儿系+仙舟 对前者是引擎
    档非成员、后者是成员;对任一载体均无点火增益,隔离点火键。)"""
    tc = pair_target_comp(('希儿系', '仙舟'))
    assert tc is not None
    bench = [_bench('三月七', '列车同行', 0),
             _bench('丹恒·饮月', '仙舟', 1)]
    up, _held = select_deployments(
        bench,
        deployed_cids={'卡芙卡'},          # 已占 1 位,cap=2 → 仅 1 空位
        deployed_fac={'星核猎手': 1},      # 对两件均无点火增益
        board={},
        cap=2,
        target_factions=frozenset(tc.factions),
        target_cores=frozenset(tc.core_chars))
    assert up == [1], '物化载体下 pair 成员(饮月)必须在引擎档内前置'
    # 对照:无载体(空 target,断线形态)→ 槽序先者(三月七)占位
    up0, _h0 = select_deployments(
        bench, {'卡芙卡'}, {'星核猎手': 1}, {}, 2)
    assert up0 == [0], '对照失败:无载体时应按槽序取首件(锁前提不成立)'


def test_seele_pair_expansion() -> None:
    """希儿系展开口径:factions=量子同频+贝洛伯格(+另一体系),与
    locked_faction_scope 展开同式;form_tiers 并量子配方档。"""
    tc = pair_target_comp(('希儿系', '仙舟'))
    assert tc is not None
    assert set(tc.factions) == {'量子同频', '贝洛伯格', '仙舟'}
    assert tc.form_tiers['量子同频'] >= 2 and tc.form_tiers['仙舟'] >= 2
    assert '希儿' in tc.core_chars


def test_form_tiers_single_source_bridge_pool() -> None:
    """form_tiers 单一源=BRIDGE_POOL:列车+DOT 对整组取 train_dot 档
    (对拍单一源,不锁写死数);空对返 None。"""
    from sr_od.application.currency_war.kernel.cw_bridge_pool import BRIDGE_POOL

    tc = pair_target_comp(_PAIR)
    assert tc is not None
    _src = next(c for c in BRIDGE_POOL
                if set(c.engine_bonds) == {'列车同行', '持续伤害'})
    assert tc.form_tiers == dict(_src.engine_bonds)
    assert pair_target_comp(()) is None
