"""ADR-0291 决策框架 v2 骨架锁(候选生成/过滤链/仲裁审计/端到端)。

锁定对象(src/sr_od/application/currency_war/decision_v2/):
① 候选生成:无方向种子覆盖(鸡生蛋解:全桥 fixed∪core)、动作类
   覆盖(buy/sell/levelup/refresh/deploy;synthesize=merge 标记)、
   锁线 carry 标签、[31] bond_fallback 门;
② 过滤链三态:应急(HP 危危急收窄)/追赶(禁 for_gold+refresh)/
   模式(economy 含 bond_fallback——0/N 买入根因③的回归锁);
③ 评分:息 EV 只在满息平台计值(gold<50 → 0)、追级 EV(小数
   等级)、目标件持有进度(cap 饱和时目标买入>0);
④ 仲裁:阶梯地板(≥50→50 / ≥10→gold%10 / <10→0——0/N 买入
   根因②的回归锁)、完备性审计表无空格+约束名存在;
⑤ 端到端 3 局(sim fallback 池):跑通 + 决策活性(前 4 轮有
   BuyCard)+方向建立。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.sim.cw_sim import simulate_p1
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    RefreshShop,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import (
    _active_floor,
    build_audit_report,
)
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    ACTION_CLASSES,
    generate_candidates,
)
from sr_od.application.currency_war.decision.decision_v2.filters import (
    filter_candidates,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision.decision_v2.scoring import (
    score_candidate,
    score_state,
)
from sr_od.application.currency_war.decision.decision_v2.strategy import (
    DecisionV2Strategy,
)

_REG = DEFAULT_REGISTRY
#: 桥池首桥样例件(xianzhou_dot;fixed/core 各一)+ 线外散件反例
_SEED_FIXED = '爻光'
_SEED_CORE = '藿藿'
_CARRY = '姬子·启行'
_OPP = '瓦尔特'
_SCATTER = '线外散件不存在'


def _card(name: str, faction: str = '仙舟罗浮', cost: int = 1) -> object:
    return SimpleNamespace(name=name, faction=faction, cost=cost,
                           x=0, star=1)


def _bench(name: str, faction: str = '仙舟罗浮',
           slot: int = 0, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _sess(line: str | None = None, bridge: str | None = None,
          mode: str = 'economy') -> StrategySession:
    """语义化(W35 载体批):``line`` 参数=意向锁定视窗(v3_hoard/v3_core),
    非旧 locked_line——candidates 层1 已换源 cw_intention。"""
    s = StrategySession()
    s.v2_state = (mode, False, False, 0, 0, 0, 0, 0)
    s.v3_mode = mode
    if line:
        from sr_od.application.currency_war.kernel.cw_intention import (
            HoardTarget,
            IntentionState,
        )
        ist = IntentionState()
        ist.phase = 'locked'
        ist.locked_comp = '姬子列车'
        s.v3_intention = ist
        s.v3_hoard = HoardTarget(
            frozenset({'姬子·启行', '瓦尔特', '三月七', '花火'}),
            frozenset(), 'locked')
        s.v3_core_names = {'姬子·启行'}
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 4, 'gold': 30, 'level': 5,
                'board': {'仙舟罗浮': 1}, 'bench': [], 'shop': [], 'hp': 100}
    base.update(kw)
    return GameState(**base)


# --- ① 候选生成 ------------------------------------------------------------


def test_no_direction_seed_candidates() -> None:
    """无方向(未锁线未成桥)时,桥池 fixed∪core 件仍生成候选
    (种子语义,dir_round=99 团灭根因①的回归锁);线外散件不生成。"""
    sess = _sess()          # 无方向
    st = _state(shop=[_card(_SEED_FIXED), _card(_SEED_CORE),
                      _card(_SCATTER, faction='公司')])   # 阵营也不在已有集
    cands = generate_candidates(st, sess, _REG)
    buy_names = {c.action.card.name for c in cands
                 if c.action.__class__.__name__ == 'BuyCard'}
    assert _SEED_FIXED in buy_names and _SEED_CORE in buy_names
    assert _SCATTER not in buy_names, '[31] 反散件:线外不生成买候选'


def test_candidate_action_class_coverage() -> None:
    """动作类覆盖:buy/sell/levelup/refresh/deploy 全出现;synthesize
    以 merge 标记承载(第 3 张同名副本)。"""
    sess = _sess(line='jizi_train')
    st = _state(
        shop=[_card(_CARRY)],
        bench=[_bench('散件甲', faction='公司'), _bench(_CARRY, slot=1),
               _bench(_CARRY, slot=2)],   # 同名已有 2 份 → 买第 3 张即合成
    )
    cands = generate_candidates(st, sess, _REG)
    kinds = set()
    merge_seen = False
    for c in cands:
        kinds.add(c.action.__class__.__name__)
        if c.action.__class__.__name__ == 'BuyCard' and c.merge:
            merge_seen = True
    assert {'BuyCard', 'SellBench', 'LevelUp', 'RefreshShop',
            'DeployMove'} <= kinds, f'动作类缺:{kinds}'
    assert merge_seen, '第 3 张同名副本应为合成候选(merge=True)'
    assert {'buy', 'sell', 'levelup', 'refresh',
                              'deploy', 'synthesize'} <= ACTION_CLASSES


def test_locked_line_carry_tag_and_bond_fallback_gate() -> None:
    """锁线:carry 标签裁决;[31] bond_fallback:锁线+全缺+1-2费+
    阵营凑档才生成(四门反例:散件名不在任何目标集)。"""
    sess = _sess(line='jizi_train')
    st = _state(shop=[_card(_CARRY)])
    cands = generate_candidates(st, sess, _REG)
    assert [c.tag for c in cands
            if c.action.__class__.__name__ == 'BuyCard'] == ['line_carry']
    # bond_fallback:目标全缺 + 店内 1 费件与已有阵营同阵营
    st2 = _state(shop=[_card('凑档件', faction='仙舟罗浮', cost=1)],
                 round_num=4)
    tags = [c.tag for c in generate_candidates(st2, sess, _REG)
            if c.action.__class__.__name__ == 'BuyCard']
    assert 'bond_fallback' in tags
    # 反例:高费带外(cost 3)不生成
    st3 = _state(shop=[_card('高费凑档', faction='仙舟罗浮', cost=3)])
    tags3 = [c.tag for c in generate_candidates(st3, sess, _REG)
             if c.action.__class__.__name__ == 'BuyCard']
    assert 'bond_fallback' not in tags3


# --- ② 过滤链三态 ----------------------------------------------------------


def test_filter_emergency_narrows() -> None:
    """应急态(HP≤25):refresh/bond_fallback 被滤出;ADR-0302 后
    应急集=战力买+卖弱件(for_gold)+升级(levelup)——旧版把
    for_gold/levelup 一并滤死(应急卖弱件/金>50 升级通道死亡)是
    批㉝ F4 实证的应急集内容缺陷,本锁改为断言正确语义。"""
    sess = _sess(mode='economy')
    st = _state(hp=20, gold=30, shop=[_card(_SEED_CORE)],
                bench=[_bench('散件甲', faction='公司')])
    cands = generate_candidates(st, sess, _REG)
    kept, flog = filter_candidates(cands, st, sess, _REG)
    kept_tags = {c.tag for c in kept}
    assert 'refresh' not in kept_tags
    assert 'bond_fallback' not in kept_tags
    # ADR-0302:卖弱件(for_gold,应急态非目标 bench 件的生成标签)
    # 与升级进应急集
    assert 'for_gold' in kept_tags, '应急态卖弱件通道应放行(ADR-0302)'
    assert 'levelup' in kept_tags, '应急态升级应放行(ADR-0302)'
    assert flog and flog[0]['level'] == 'emergency'


def test_filter_mode_economy_allows_bond_fallback() -> None:
    """模式(economy)态含 bond_fallback(0/N 买入根因③回归锁)。

    ADR-0300 后 pair 通道在 _buy_tag 中先于 bond_fallback——常态
    「同阵营已拥有」件被 pair 接管;bond_fallback 的独占场景=
    r350 方向门外(锁线后线外阵营 pair 拒、[31] 降级仍收)。"""
    assert 'bond_fallback' in _REG.economy_tags
    sess = _sess(line='jizi', mode='economy')   # 意向锁定(线外阵营 pair 拒)
    st = _state(round_num=5, board={'昼之半神': 1},
                shop=[_card('凑档件', faction='昼之半神', cost=1)])
    cands = generate_candidates(st, sess, _REG)
    kept, _ = filter_candidates(cands, st, sess, _REG)
    assert any(c.tag == 'bond_fallback' for c in kept)


# --- ③ 评分 ----------------------------------------------------------------


def test_score_interest_only_above_platform() -> None:
    """息 EV 平台制:gold<50 → 0;gold≥50 → 满息×轮数。"""
    s_low = score_state(_state(gold=49), _REG)
    s_high = score_state(_state(gold=55), _REG)
    assert s_low['interest'] == 0.0
    assert s_high['interest'] == _REG.interest_cap * _REG.interest_rounds


def test_score_has_level_and_targets_terms() -> None:
    """追级 EV(小数等级)与目标件持有进度两项在表。"""
    s = score_state(_state(gold=49, level=5, xp_progress=(1, 4)), _REG)
    assert 'level' in s and 'targets' in s
    assert s['level'] == 5.25    # 5 + 1/4


def test_engine_frac_progress_term_adr0301() -> None:
    """ADR-0301 成型进度项:过渡体系进度小数余量显影(unit>0),
    unit=0 关闭;cap 饱和态买进度件评分随 unit 单调(非 0 分拒的
    「评分没买」主因回归锁)。"""
    from dataclasses import replace as _repl
    # 两件仙舟 deployed(进度 2/3,未跨阈值→余量 2/3)
    st = _state(gold=30, level=5,
                deployed=[_bench('藿藿', slot=0), _bench('爻光', slot=1)])
    s = score_state(st, _REG)
    assert 'eng_frac' in s
    assert s['eng_frac'] == 0.667, f'2/3 余量×unit=1.0(实际 {s})'
    reg0 = _repl(_REG, engine_frac_unit=0.0)
    assert score_state(st, reg0)['eng_frac'] == 0.0
    # cap 饱和态(deployed=cap):仙舟进度件买入评分 unit>0 严格更高
    sess = _sess(line='jizi_train')
    st2 = _state(gold=60, level=5,
                 deployed=[_bench(f'板件{i}', faction='公司', slot=i)
                           for i in range(5)],
                 shop=[_card('藿藿', faction='仙舟', cost=1)])
    cands = [c for c in generate_candidates(st2, sess, _REG)
             if c.action.__class__.__name__ == 'BuyCard'
             and c.action.card.name == '藿藿']
    assert cands, '仙舟件(桥 core)应生成买候选'
    v_on, _ = score_candidate(cands[0], st2, sess, _REG)
    v_off, _ = score_candidate(cands[0], st2, sess, reg0)
    assert v_on > v_off, (v_on, v_off)


def test_target_buy_positive_at_saturated_cap() -> None:
    """cap 饱和态(level=deployed)目标件买入评分>0(持有进度显影;
    全 0 分空转攒金团灭的回归锁)。"""
    sess = _sess(line='jizi_train')
    st = _state(gold=60, level=5,
                deployed=[_bench(f'板件{i}', slot=i) for i in range(5)],
                shop=[_card(_OPP, cost=2)])
    cands = [c for c in generate_candidates(st, sess, _REG)
             if c.action.__class__.__name__ == 'BuyCard'
             and c.action.card.name == _OPP]
    assert cands, 'opportunistic 件应生成候选'
    val, _bd = score_candidate(cands[0], st, sess, _REG)
    assert val > 0, f'cap 饱和时目标买入应>0(实际 {val})'


# --- ④ 仲裁:阶梯地板 + 审计表 ---------------------------------------------


def test_active_floor_tiered_economy() -> None:
    """地板分派:相位地板(W119/ADR-0347,阶梯地板退场)+旁路优先序。

    - 经济态 FORM(意向未锁/板面空)→ FORM_FLOOR(保险丝 20);
    - HOARD(form_ok+金<50)/SPEND(金≥50)→ INTEREST_FLOOR(50);
    - 应急(hp≤25)→ rebirth_floor(旁路,优先于相位——逐位不变);
    - boss 窗(node_type 缺读 P1 r≥9 兜底)→ boss_floor(节点图统一
      口径,轮数兜底只此一处)。
    """
    sess = _sess(mode='economy')
    # FORM:unlocked 空 board → form_ok False
    assert _active_floor(_state(gold=55), sess, _REG) == _REG.form_floor
    assert _active_floor(_state(gold=12), sess, _REG) == _REG.form_floor
    assert _active_floor(_state(hp=20, gold=55), sess, _REG) == \
        _REG.rebirth_floor
    # boss 兜底:node_type 缺读 + P1 r9 → boss_floor
    assert _active_floor(_state(round_num=9, gold=55), sess, _REG) == \
        _REG.boss_floor
    # HOARD/SPEND:form_ok 真帧(锁定+三件套)金 40/55 → 50
    from sr_od.application.currency_war.kernel.cw_comps import get_comp
    from sr_od.application.currency_war.kernel.cw_intention import (
        IntentionState,
        intention_core,
    )
    comp = get_comp('DOT队')
    core = intention_core(comp)
    _f = dict(plane=1, round_num=7, level=5, hp=60,
              board={f: t for f, t in comp.form_tiers.items()},
              deployed=[BenchChar(slot=0, char_id=core,
                                  faction='仙舟罗浮', star=2)],
              bench=[], shop=[])
    s2 = StrategySession()
    s2.v3_intention = IntentionState(phase='locked', locked_comp='DOT队')
    assert _active_floor(_state(gold=40, **_f), s2, _REG) == \
        _REG.interest_floor()
    assert _active_floor(_state(gold=55, **_f), s2, _REG) == \
        _REG.interest_floor()


def test_audit_report_full_matrix() -> None:
    """完备性审计表:无空格 + 约束名全部存在于 constraints。"""
    rep = build_audit_report(_REG)
    assert rep['violations'] == [], f'审计表违规:{rep["violations"]}'
    for res_dim in _REG.audit_resource_dims:
        assert res_dim in rep['matrix']
        for st_dim in _REG.audit_round_state_dims:
            assert rep['matrix'][res_dim][st_dim] is not None


def test_registry_constraints_known() -> None:
    """约束清单非空且实现映射覆盖(未知名=放行的兜底不许静默)。"""
    assert _REG.constraints
    assert {'gold_floor', 'interest_rule', 'bench_capacity',
            'same_round_mutex', 'boss_levelup_ban'} <= set(
        _REG.constraints)


# --- ⑤ 端到端 3 局 ---------------------------------------------------------


def test_end_to_end_three_games_active() -> None:
    """3 局 sim(fallback 池):跑通无崩 + 前 4 轮有买入(决策活性)
    + 方向建立率≥2/3。"""
    strat = DecisionV2Strategy()
    buys_early = 0
    dirs = []
    for seed in (900000, 900001, 900002):
        res = simulate_p1(seed, pool='fallback', strategy=strat)
        assert res.final_hp >= 0
        dirs.append(res.dir_round)
        n_buys = sum(
            1 for row in res.ledger[:4]
            for a in (row.get('actions') or [])
            if a.get('__type__') == 'BuyCard')
        buys_early += n_buys
    assert buys_early > 0, '前 4 轮应有买入(骨架活性;0/N 回归)'
    assert sum(1 for d in dirs if d < 99) >= 2


def test_strategy_metadata() -> None:
    """策略身份:STRATEGY_ID=decision_v2,默认注册表注入。"""
    s = DecisionV2Strategy()
    assert s.STRATEGY_ID == 'decision_v2'
    assert s.registry is DEFAULT_REGISTRY
    assert isinstance(RefreshShop(cost=2).cost, int)
