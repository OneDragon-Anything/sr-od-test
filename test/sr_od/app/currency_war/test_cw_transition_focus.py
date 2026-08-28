"""过渡收敛三层贯彻(ADR-0442;W451 P1 设计实现批)可代码锁定判据。

覆盖:开关值锁 / C1 锁定判据(配对 P*/希儿门/平局/滞回)/ C2 买层隶属度
先验 / C3 留层卖序(core 永不卖)/ 开关关=零漂移(评分逐位一致)。
A/B 归 sim 实测(框架非空轮次占比/买向迁移/e0→1 激活率/出口血量·2★,
守卫=金账息账不劣),本文件不锁分布数值。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'src'))

from sr_od.application.currency_war.cw_state import (  # noqa: E402
    GameState,
)
from sr_od.application.currency_war.cw_strategy import StrategySession  # noqa: E402
from sr_od.application.currency_war.cw_transition import (  # noqa: E402
    TransitionFocus,
    compute_transition_focus,
    focus_membership,
    focus_sell_rank,
)
from sr_od.application.currency_war.decision_v2.candidates import (  # noqa: E402
    generate_candidates,
)
from sr_od.application.currency_war.decision_v2.discipline import (  # noqa: E402
    sell_priority_key,
)
from sr_od.application.currency_war.decision_v2.registry import (  # noqa: E402
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.scoring import (  # noqa: E402
    score_candidate,
)

#: 开臂臂用 registry(只翻收敛开关,其余与生产默认逐位同)
FOCUS_ON = __import__('dataclasses').replace(
    DEFAULT_REGISTRY, transition_focus_enabled=True)


class _Card:
    def __init__(self, name: str, cost: int = 1):
        self.name = name
        self.cost = cost
        self.x = 0
        self.star = 1
        self.faction = '?'


class BC:
    def __init__(self, n: str, star: int = 1):
        self.char_id = n
        self.star = star
        self.slot = 0
        self.faction = '?'
        self.position_pref = 'back'


def _focus() -> TransitionFocus:
    """典型载体:F=仙舟,P*=列车同行(名集与 core 取计算规则产物)。"""
    f = compute_transition_focus(
        bench=[BC('藿藿'), BC('爻光')], deployed=[], shop=[],
        active_env='', leader_comp=None, framework='仙舟', current=None)
    assert f is not None and f.partner == '列车同行'
    return f


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 4, 'gold': 30, 'level': 5,
            'board': {'仙舟': 1}, 'bench': [], 'shop': [], 'hp': 100}
    base.update(kw)
    return GameState(**base)


# ===== 接线级测试(decide_prep 真调用;跨轮状态喂入,非直调纯函数)=====

def _bc(name: str):
    return BC(name)


def _wiring_sess(registry):
    """真 Strategy/Session(过 on_match_start 生命周期),接线测试共用。"""
    from sr_od.application.currency_war.decision_v2.strategy import (
        DecisionV2Strategy,
    )
    strat = DecisionV2Strategy(registry=registry)

    class _Cfg:
        pass

    st = GameState(gold=30, hp=80, level=5, round_num=3, plane=1,
                   board={'仙舟': 1})
    sess = strat.create_session(_Cfg())
    strat.on_match_start(st, sess, _Cfg())
    return strat, sess, _Cfg


def test_wiring_hysteresis_across_rounds() -> None:
    """w465 打回修复锁:滞回必须跨轮活——上一轮载体经
    session.transition_focus_prev 喂回 compute 的 current。
    r1:P*=列车同行(店半权 1.0);r2:列车 w 归零、挑战者 DOT 0.5
    (领先 <1)→ 仍保持列车同行;同局面无 prev 的新 session 则翻 DOT
    (证明保持来自接线而非纯函数巧合)。"""
    import dataclasses

    from sr_od.application.currency_war.cw_state import ShopCard
    reg = dataclasses.replace(DEFAULT_REGISTRY,
                              transition_focus_enabled=True,
                              framework_startup_v2_enabled=True)
    strat, sess, cfg = _wiring_sess(reg)
    sess.transition_framework = '仙舟'   # 框架块会因持有藿藿保持它
    st1 = GameState(gold=30, hp=80, level=5, round_num=3, plane=1,
                    board={'仙舟': 1}, bench=[_bc('藿藿')],
                    shop=[ShopCard(x=400, faction='列车同行', name='三月七', cost=1),
                          ShopCard(x=500, faction='列车同行', name='姬子·启行', cost=3)])
    strat.decide_prep(st1, sess, cfg)
    assert sess.transition_focus is not None \
        and sess.transition_focus.partner == '列车同行'
    assert sess.transition_focus_prev is sess.transition_focus
    # r2:列车 w=0,挑战者 DOT w=0.5(店半权 1 张)→ 滞回保持
    st2 = GameState(gold=30, hp=80, level=5, round_num=4, plane=1,
                    board={'仙舟': 1}, bench=[_bc('藿藿')],
                    shop=[ShopCard(x=400, faction='持续伤害', name='卡芙卡', cost=2)])
    strat.decide_prep(st2, sess, cfg)
    assert sess.transition_focus.partner == '列车同行', \
        '跨轮滞回失效:P* 随店波动翻转(接线把 current 掐死)'
    # 负对照:同局面无跨轮槽的新 session → 翻向 DOT(排他证明)
    _, sess2, _ = _wiring_sess(reg)
    sess2.transition_framework = '仙舟'
    strat.decide_prep(st2, sess2, cfg)
    assert sess2.transition_focus.partner == '持续伤害'


def test_wiring_break_supply_clears_both_slots() -> None:
    """断供(框架清空)→ 生效载体与跨轮槽**都**清 None(清除条件=断供,
    非轮边界);且下一轮不再有滞回基线。"""
    import dataclasses

    from sr_od.application.currency_war.cw_state import ShopCard
    reg = dataclasses.replace(DEFAULT_REGISTRY,
                              transition_focus_enabled=True,
                              framework_startup_v2_enabled=True)
    strat, sess, cfg = _wiring_sess(reg)
    sess.transition_framework = '仙舟'
    st1 = GameState(gold=30, hp=80, level=5, round_num=3, plane=1,
                    board={'仙舟': 1}, bench=[_bc('藿藿')],
                    shop=[ShopCard(x=400, faction='列车同行', name='三月七', cost=1)])
    strat.decide_prep(st1, sess, cfg)
    assert sess.transition_focus is not None
    # 断供:框架件全空 → 启动块清 transition_framework → 载体两槽皆清
    st2 = GameState(gold=30, hp=80, level=5, round_num=4, plane=1,
                    board={'仙舟': 1}, bench=[], shop=[])
    strat.decide_prep(st2, sess, cfg)
    assert sess.transition_framework == ''
    assert sess.transition_focus is None
    assert sess.transition_focus_prev is None


def test_wiring_dependency_switch_lazies_both_slots() -> None:
    """依赖惰性:只开收敛开关、启动开关关 → 两槽恒 None(不触碰)。"""
    import dataclasses

    reg = dataclasses.replace(DEFAULT_REGISTRY,
                              transition_focus_enabled=True,
                              framework_startup_v2_enabled=False)
    strat, sess, cfg = _wiring_sess(reg)
    sess.transition_framework = '仙舟'   # 即使外部塞了框架
    st = GameState(gold=30, hp=80, level=5, round_num=3, plane=1,
                   board={'仙舟': 1}, bench=[_bc('藿藿')], shop=[])
    strat.decide_prep(st, sess, cfg)
    assert sess.transition_focus is None
    assert sess.transition_focus_prev is None


# ===== 开关值锁(生命周期第 1 态:默认关)=====

def test_switch_default_off() -> None:
    """transition_focus_enabled 默认 False(开关生命周期第 1 态);
    开臂判据挂账在 registry 字段注释(A/B 归下一批)。"""
    assert DEFAULT_REGISTRY.transition_focus_enabled is False


def test_switch_off_scoring_unchanged() -> None:
    """C5-1(代码可锁子集):开关关(默认)时,载体在不在 session 上
    评分逐位一致(=不消费载体,零漂移)。"""
    st = _state(shop=[_Card('藿藿', 1)])
    sess_focus = StrategySession()
    sess_focus.transition_focus = _focus()
    sess_plain = StrategySession()
    cands = [c for c in generate_candidates(st, sess_focus, DEFAULT_REGISTRY)
             if c.tag != 'refresh']
    assert cands
    for c in cands:
        v_with, _ = score_candidate(c, st, sess_focus, DEFAULT_REGISTRY)
        v_without, _ = score_candidate(c, st, sess_plain, DEFAULT_REGISTRY)
        assert v_with == v_without, \
            f'开关关必须零漂移:{c.tag} {v_with} vs {v_without}'


# ===== C1 锁定判据 =====

def test_lock_partner_by_shop_half_weight() -> None:
    """C1-2:P* = argmax(owned+0.5·shop+3·portal+0.5·overlap)——
    F=仙舟,店在售三月七/姬子·启行各 1 → 列车半权 1.0 > DOT 0 → 列车。"""
    f = compute_transition_focus(
        bench=[BC('藿藿')], deployed=[], shop=[_Card('三月七'), _Card('姬子·启行')],
        active_env='', leader_comp=None, framework='仙舟', current=None)
    assert f is not None and f.partner == '列车同行'


def test_lock_seele_gate_requires_seele_held() -> None:
    """C1-3:希儿系候选门——希儿不在手,量子在售再多也不入候选。"""
    f = compute_transition_focus(
        bench=[BC('藿藿')], deployed=[],
        shop=[_Card('缇宝'), _Card('缇宝'), _Card('符玄')],
        active_env='', leader_comp=None, framework='仙舟', current=None)
    assert f is not None and f.partner != '希儿系'


def test_lock_seele_allowed_when_held() -> None:
    """C1-3:希儿在手(持有≥1)→ 希儿系可入候选并按 w 取胜。"""
    f = compute_transition_focus(
        bench=[BC('藿藿'), BC('希儿')], deployed=[],
        shop=[_Card('缇宝'), _Card('缇宝')],
        active_env='', leader_comp=None, framework='仙舟', current=None)
    assert f is not None and f.partner == '希儿系'
    assert '希儿' in f.core_names
    assert '希儿' in f.focus_names


def test_lock_tie_break_looser_requirement() -> None:
    """C1-4:w 全零平局 → 人员要求更松者胜(列车2/DOT2 无要求)。"""
    f = compute_transition_focus(
        bench=[BC('藿藿')], deployed=[], shop=[],
        active_env='', leader_comp=None, framework='仙舟', current=None)
    assert f is not None and f.partner == '列车同行'


def test_lock_hysteresis_keep_partner() -> None:
    """C1-5:P* 滞回——挑战者 w 领先现任 <1 → 保持现任。"""
    cur = _focus()   # 现任列车同行
    # 挑战者 DOT:w=0.5(店 1 张半权)< 现任 0+1 → 不换
    f = compute_transition_focus(
        bench=[BC('藿藿')], deployed=[], shop=[_Card('卡芙卡')],
        active_env='', leader_comp=None, framework='仙舟', current=cur)
    assert f is not None and f.partner == '列车同行'


def test_names_expansion() -> None:
    """C1-6:名集 = F 与 P* 的策展 carry/partial;drop 档不入;
    core_names 按 §3.3(仙舟=三人组)。"""
    f = _focus()
    assert {'藿藿', '丹恒·饮月', '爻光'} <= f.focus_names       # F carry/partial
    assert {'三月七', '姬子·启行', '花火'} <= f.focus_names      # P* carry
    assert '卡芙卡' not in f.focus_names                         # drop 档不入
    assert f.core_names == {'爻光', '藿藿', '丹恒·饮月'}


def test_break_supply_clears() -> None:
    """断供(框架空)→ 载体 None(调用方清 session 字段)。"""
    assert compute_transition_focus(
        bench=[], deployed=[], shop=[], active_env='', leader_comp=None,
        framework='', current=None) is None


# ===== C2 买层隶属度先验 =====

def test_buy_prior_membership() -> None:
    """C2-1:m∈{1.0,0.5,0} × 单位值;散件现状分不变(降权不归零);
    开关关零漂移。"""
    focus = _focus()
    st = _state(shop=[_Card('藿藿', 1), _Card('忘归人', 3), _Card('黑塔', 1)])
    sess = StrategySession()
    sess.transition_focus = focus
    vals: dict[str, tuple[float, float]] = {}
    for c in generate_candidates(st, sess, FOCUS_ON):
        if c.tag == 'refresh' or not hasattr(c.action, 'card'):
            continue
        name = c.action.card.name
        v_on, _ = score_candidate(c, st, sess, FOCUS_ON)
        v_off, _ = score_candidate(c, st, sess, DEFAULT_REGISTRY)
        vals.setdefault(name, (v_on, v_off))
    unit = DEFAULT_REGISTRY.transition_focus_buy_prior
    assert abs(vals['藿藿'][0] - vals['藿藿'][1] - unit * 1.0) < 1e-6
    assert abs(vals['忘归人'][0] - vals['忘归人'][1] - unit * 0.5) < 1e-6
    # 散件 m=0 → 评分与开关关逐位一致(散件现状分不变;黑塔这类无方向
    # 件连候选都不生成,是现状行为,不是本层改变)


def test_membership_helper() -> None:
    """隶属度函数:names=1.0/阵营域=0.5/其余=0;载体 None 恒 0。"""
    focus = _focus()
    focus = _focus()
    assert focus_membership('藿藿', focus) == 1.0
    assert focus_membership('忘归人', focus) == 0.5   # 仙舟阵营非策展名
    assert focus_membership('黑塔', focus) == 0.0
    assert focus_membership('藿藿', None) == 0.0


# ===== C3 留层卖序 =====

def test_sell_rank_order() -> None:
    """C3-1:散件(0) < 非收敛囤件(1) < 收敛 drop(2) < partial(3)
    < carry(4);同档 1★ 优先。"""
    focus = _focus()
    assert focus_sell_rank('镜流', 1, focus) == (1, 0)      # 非收敛囤件(狼狩/燃血)
    assert focus_sell_rank('某未识别件', 1, focus) == (0, 0)  # 零羁绊(未识别)散件 1★
    assert focus_sell_rank('镜流', 2, focus)[1] == 1        # 同档 2★ 后卖
    assert focus_sell_rank('阿格莱雅', 1, focus)[0] == 1    # 有羁绊非收敛囤件
    assert focus_sell_rank('卡芙卡', 1, focus) == (2, 0)    # 收敛体系 drop 档
    assert focus_sell_rank('停云', 1, focus) == (3, 0)      # 仙舟阵营非策展名=partial 级
    assert focus_sell_rank('爻光', 1, focus) is None        # core 永不卖(优先于档序)
    assert focus_sell_rank('花火', 1, focus) == (4, 0)      # P* carry
    assert focus_sell_rank('三月七', 1, focus) == (4, 0)    # P* carry
    assert focus_sell_rank('藿藿', 1, None) is None          # 载体 None=回退


def test_core_never_in_sell_channel() -> None:
    """C5-2:core_names 任何情况下不生成卖候选(不进卖序,不进 tag)。"""
    focus = _focus()
    # deployed 3 张仙舟件 → 仙舟 owned>tier,爻光的键 None 只能来自 core 保护
    st = _state(deployed=[BC('忘归人'), BC('停云'), BC('藿藿')],
                bench=[BC('爻光'), BC('镜流')])
    sess = StrategySession()
    sess.transition_focus = focus
    for c in generate_candidates(st, sess, FOCUS_ON):
        if c.action.__class__.__name__ == 'SellBench':
            idx = c.action.bench_idx
            bc = st.bench[idx]
            assert bc.char_id not in focus.core_names, \
                f'core {bc.char_id} 不得出现在卖候选'
    # 卖序键层面:core 返回 None(永不可卖;sole-engine 已被 deployed 稀释)
    assert sell_priority_key(BC('爻光'), st, sess,
                             registry=FOCUS_ON) is None


def test_sell_key_focus_segment_order() -> None:
    """卖序键 focus 段:囤件(1) < partial(3) < carry(4);
    开关切回 6 段键(现状行为)。"""
    focus = _focus()
    # deployed 稀释唯一引擎守卫(仙舟 3/列车 2),让键 None 只来自 focus
    st = _state(deployed=[BC('忘归人'), BC('忘归人'), BC('忘归人'),
                          BC('三月七'), BC('三月七')],
                bench=[BC('镜流'), BC('停云'), BC('花火')])
    sess = StrategySession()
    sess.transition_focus = focus
    k_hoard = sell_priority_key(BC('镜流'), st, sess, registry=FOCUS_ON)
    k_partial = sell_priority_key(BC('停云'), st, sess, registry=FOCUS_ON)
    k_carry = sell_priority_key(BC('花火'), st, sess, registry=FOCUS_ON)
    assert k_hoard is not None and k_partial is not None \
        and k_carry is not None
    assert k_hoard < k_partial < k_carry
    # 开关关(默认 registry):键不含 focus 段(6 元,现状行为)
    k_off = sell_priority_key(BC('镜流'), st, sess, registry=DEFAULT_REGISTRY)
    assert k_off is not None and len(k_off) == 6
