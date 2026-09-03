# -*- coding: utf-8 -*-
"""test_cw_scoring 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- adr0291_decision_v2: test_cw_adr0291_decision_v2.py
- adr0295_form_domain: test_cw_adr0295_form_domain.py
- adr0298_equip_value_debt: test_cw_adr0298_equip_value_debt.py
- adr0332_forming_scoring: test_cw_adr0332_forming_scoring.py
- adr0333_concentration: test_cw_adr0333_concentration.py
冲突改名:后来者顶层名加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== adr0291_decision_v2 ====================

from types import SimpleNamespace


from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
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


# ==================== adr0295_form_domain ====================

from dataclasses import replace

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision.decision_v2.scoring import (
    _held_form_weights,
    board_rung_x,
    score_state,
)


def _char_of_faction(faction: str) -> str:
    """取首个主阵营=faction 的真注册表角色名(引擎判定需真数据)。"""
    for n, c in CHARACTERS.items():
        if faction in (c.factions or ()):
            return n
    raise AssertionError(f'注册表无阵营 {faction} 角色')


def _adr0295_form_domain_bench(name: str, slot: int, star: int = 1) -> BenchChar:
    ch = CHARACTERS[name]
    return BenchChar(slot=slot, char_id=name,
                     faction=(ch.factions or ['?'])[0], star=star)


def _adr0295_form_domain_state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 4, 'gold': 30, 'level': 5,
            'board': {}, 'bench': [], 'shop': [], 'hp': 100,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def test_bench_only_no_engine() -> None:
    """bench 折减:bench-only 仙舟×3 计数 1.05<3 → 不成引擎(x<1)。"""
    name = _char_of_faction('仙舟')
    st = _adr0295_form_domain_state(bench=[_adr0295_form_domain_bench(name, i) for i in (1, 2, 3)])
    assert board_rung_x(st, DEFAULT_REGISTRY) < 1.0, (
        'bench-only 囤件不得撑满引擎档(ADR-0295 deployed 主导)')


def test_deployed_full_weight_engine() -> None:
    """deployed 主导:上场仙舟×3 全额计数 → 引擎档(x≥1)。"""
    name = _char_of_faction('仙舟')
    st = _adr0295_form_domain_state(
        deployed=[_adr0295_form_domain_bench(name, i) for i in (1, 2, 3)],
        board={'仙舟': 3},
    )
    assert board_rung_x(st, DEFAULT_REGISTRY) >= 1.0


def test_bench_weight_adjustable() -> None:
    """权重可调:w=1.0 时 bench-only 也成引擎(等权=旧持有域行为)。"""
    name = _char_of_faction('仙舟')
    st = _adr0295_form_domain_state(bench=[_adr0295_form_domain_bench(name, i) for i in (1, 2, 3)])
    reg = replace(DEFAULT_REGISTRY, bench_form_weight=1.0)
    assert board_rung_x(st, reg) >= 1.0, (
        'w=1.0 应退化为旧持有域等权行为(bench-only 成引擎)')
    # 加权聚合同步锁:factions 计数 = 星级 × 权重
    fac, main, _dep = _held_form_weights(st, DEFAULT_REGISTRY)
    assert abs(fac['仙舟'] - 3 * DEFAULT_REGISTRY.bench_form_weight) < 1e-9
    assert abs(main['仙舟'] - 3 * DEFAULT_REGISTRY.bench_form_weight) < 1e-9


def test_target_hold_ceiling_discounted() -> None:
    """持有进度项天花板折减:n≥base 时 targets = cap_frac × value。"""
    from sr_od.application.currency_war.kernel.cw_bridge_pool import BRIDGE_POOL
    from sr_od.application.currency_war.kernel.cw_intention import HoardTarget
    from sr_od.application.currency_war.decision.cw_strategy import StrategySession
    # 目标件取桥池 fixed∪core 并作意向 hoard(ADR-0336 后裸 session
    # 只走引擎件种子;意向载体才是目标集生产形态)
    names = sorted({n for combo in BRIDGE_POOL
                    for n in set(combo.fixed) | set(combo.core)
                    if n in CHARACTERS})
    name = names[0]
    n = DEFAULT_REGISTRY.target_hold_base + 1
    st = _adr0295_form_domain_state(bench=[_adr0295_form_domain_bench(name, i) for i in range(1, n + 1)])
    sess = StrategySession()
    sess.v3_hoard = HoardTarget(frozenset({name}), frozenset(), 'locked')
    bd = score_state(st, DEFAULT_REGISTRY, sess)
    expect = (DEFAULT_REGISTRY.target_hold_cap_frac
              * DEFAULT_REGISTRY.target_hold_value)
    assert abs(bd['targets'] - round(expect, 3)) < 0.01, (
        f"顶格 targets 应为 {expect}(实际 {bd['targets']})——"
        '顶格不再=满形态(ADR-0295)')


# (原 test_form_domain_initial_values 逐值断言 bench_form_weight==0.35 /
#  target_hold_cap_frac==0.8 已并入 test_cw_adr0293_calibration 字段面锁
# ——该表逐值辖此二字段,独立逐值锁=双源漂移风险,重复构成删并理由
# (README 纪律 8);行为锁全数保留。)


# ==================== adr0298_equip_value_debt ====================

from sr_od.application.currency_war.data.cw_equipment_data import (
    EQUIPMENT_ROSTER,
)
from sr_od.application.currency_war.kernel.cw_events import (
    _EQUIP_VALUE,
    SupplyOption,
    _equip_value,
    decide_supply,
)

from sr_od.application.currency_war.sim.checks.ledger import check_equip_value_table_roster_coherence
from sr_od.application.currency_war.kernel.cw_state import GameState

# ---- 方向1:价值表键 ⊆ 注册表名(死名清零) --------------------------------


def test_equip_value_keys_subset_of_roster() -> None:
    """表键必须全部在 EQUIPMENT_ROSTER 内(批㉛ F2 死名不得回归)。"""
    stale = sorted(n for n in _EQUIP_VALUE if n not in EQUIPMENT_ROSTER)
    assert stale == [], f'价值表死名 {stale}(ADR-0298 清偿后不得回归)'


def test_dead_names_removed_and_mass_transferred() -> None:
    """3 死名已删;翁瓦克 4 分转投蓄能帆(0 分→4 分)。"""
    for dead in ('超级电池', '能量饮料', '翁瓦克'):
        assert dead not in _EQUIP_VALUE
    assert _EQUIP_VALUE.get('蓄能帆') == 4


# ---- 方向2:roster 供给名(进 sim 采样池者)⊆ 表键(无静默过滤) ------------


def test_sim_supply_pool_equals_table_keys() -> None:
    """sim 供给采样池构造(cw_sim 同式)与表键完全一致。

    ADR-0294 件2 的注册表过滤此前静默剔出 20% 表值质量;死名清偿后
    过滤应为恒等(池=表),再出现差集 = 表-注册表漂移回归。
    """
    pool = [n for n in _EQUIP_VALUE if n in EQUIPMENT_ROSTER]
    assert sorted(pool) == sorted(_EQUIP_VALUE)


# ---- 生产侧 decide_supply 对齐 ---------------------------------------------


def test_decide_supply_reads_transferred_value() -> None:
    """补给决策读得到转投后的蓄能帆价值(真名不再恒 0 分)。"""
    assert _equip_value('蓄能帆') == 4
    assert _equip_value('翁瓦克') == 0  # 死名按未知名 0 分(永不出现)


def test_decide_supply_prefers_valued_equip() -> None:
    """无钻不刷新场景:蓄能帆(4)压过 2 分档活名。"""
    st = GameState()
    opts = [
        SupplyOption(idx=0, equip='绝对热量'),
        SupplyOption(idx=1, equip='蓄能帆'),
        SupplyOption(idx=2, equip='轮滑鞋'),
    ]
    # 轮滑鞋 4 同分:构造上取高分者之一即可——改用唯一高分者断言精确 idx
    opts[2].equip = '物质分解液'  # 3 分
    pick = decide_supply(opts, st, None, None, refresh_used=True)
    assert pick.idx == 1


# ---- 检查项转绿 -------------------------------------------------------------


def test_check_item_green_after_clearance() -> None:
    """批㉛ 验收硬指标:equip_value_table_roster_coherence 归 0(恒绿)。"""
    assert check_equip_value_table_roster_coherence([{}]) == []


# ==================== adr0332_forming_scoring ====================

import dataclasses
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision.decision_v2.scoring import (
    _cand_is_engine_piece,
    score_candidate,
)

_adr0332_forming_scoring_REG = DEFAULT_REGISTRY


def _adr0332_forming_scoring_card(name: str, faction: str = '仙舟', cost: int = 1) -> object:
    return SimpleNamespace(name=name, faction=faction, cost=cost,
                           x=0, star=1)


def _adr0332_forming_scoring_bench(name: str, faction: str = '公司',
           slot: int = 0, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _adr0332_forming_scoring_sess() -> StrategySession:
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    return s


def _adr0332_forming_scoring_state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 7, 'gold': 55, 'level': 6, 'hp': 80,
            'board': {'公司': 6},
            'deployed': [_adr0332_forming_scoring_bench(f'板件{i}', faction='公司', slot=i)
                         for i in range(6)],
            'bench': [], 'shop': [], 'hp': 80}
    base.update(kw)
    return GameState(**base)


def _buy_cand(st: GameState, name: str):
    """层1 真链生成指定买候选(取首个;无则断言失败)。"""
    cands = [c for c in generate_candidates(st, _adr0332_forming_scoring_sess(), _adr0332_forming_scoring_REG)
             if c.action.__class__.__name__ == 'BuyCard'
             and c.action.card.name == name]
    assert cands, f'店件 {name} 应生成买候选'
    return cands[0]


# --- ① 息崖平滑(war 破息窗) ------------------------------------------------


def test_cliff_smooth_war_window_crossing() -> None:
    """war 窗(P1 r7 非应急)gold 52 买 3 费引擎件(52→49 破平台):
    息损平滑到真实档位(-5)+ 成型偏置 → 正分(修复前 -24.55 恒死)。"""
    st = _adr0332_forming_scoring_state(gold=52, shop=[_adr0332_forming_scoring_card('爻光', cost=3)])
    cand = _buy_cand(st, '爻光')
    val, bd = score_candidate(cand, st, _adr0332_forming_scoring_sess(), _adr0332_forming_scoring_REG)
    assert bd['base']['interest'] == 25.0, bd['base']
    assert bd['after']['interest'] == 0.0, bd['after']
    assert val > 0, f'war 窗破平台买应正分(平滑+偏置;实际 {val})'


def test_cliff_kept_in_emergency() -> None:
    """emergency(hp20)同场景:息崖 -25 保持([18] 不为苟住破息,
    ADR-0302 锁同族);偏置禁域(不顶深负)→ 恒负分。"""
    st = _adr0332_forming_scoring_state(gold=52, hp=20, shop=[_adr0332_forming_scoring_card('爻光', cost=3)])
    cand = _buy_cand(st, '爻光')
    val, _ = score_candidate(cand, st, _adr0332_forming_scoring_sess(), _adr0332_forming_scoring_REG)
    assert val < 0, f'emergency 破平台买应负分(息崖保持;实际 {val})'


def test_cliff_kept_in_economy_window() -> None:
    """经济态(r4 非破息窗)gold 52 买 3 费:不触发平滑/偏置 → 恒负分
    ([17] 满息平台,经济态破 50 不被授权)。"""
    st = _adr0332_forming_scoring_state(round_num=4, gold=52, shop=[_adr0332_forming_scoring_card('爻光', cost=3)])
    cand = _buy_cand(st, '爻光')
    val, _ = score_candidate(cand, st, _adr0332_forming_scoring_sess(), _adr0332_forming_scoring_REG)
    assert val < 0, f'经济态破平台买应负分(实际 {val})'


# --- ② 成型补充偏置 ----------------------------------------------------------


def test_forming_bias_additive() -> None:
    """未成型 + 引擎件跨 50 平台买入(平滑后小负):forming_bias 加性
    (on−off 差分恰=bias);偏置开时分正(可执行)——修复前 -24.55 恒死。"""
    st = _adr0332_forming_scoring_state(gold=52, shop=[_adr0332_forming_scoring_card('爻光', cost=3)])
    cand = _buy_cand(st, '爻光')
    assert _cand_is_engine_piece(cand), '爻光应为引擎件'
    reg_off = dataclasses.replace(_adr0332_forming_scoring_REG, forming_bias=0.0)
    v_off, _ = score_candidate(cand, st, _adr0332_forming_scoring_sess(), reg_off)
    v_on, _ = score_candidate(cand, st, _adr0332_forming_scoring_sess(), _adr0332_forming_scoring_REG)
    assert v_off < 0, f'前置:平滑后应小负(实际 {v_off})'
    assert v_on - v_off == _adr0332_forming_scoring_REG.forming_bias, (v_off, v_on)
    assert v_on > 0, '未成型+引擎件跨平台应可执行(>0)'


def test_forming_bias_off_when_formed() -> None:
    """成型后(引擎≥2,[13] 成型即停手):引擎件买入不顶偏置
    (on−off 差分=0)。"""
    st = _adr0332_forming_scoring_state(
        deployed=[_adr0332_forming_scoring_bench('爻光', faction='仙舟', slot=0),
                  _adr0332_forming_scoring_bench('藿藿', faction='仙舟', slot=1),
                  _adr0332_forming_scoring_bench('符玄', faction='仙舟', slot=2),
                  _adr0332_forming_scoring_bench('卡芙卡', faction='星核猎手', slot=3),
                  _adr0332_forming_scoring_bench('黑天鹅', faction='盛会之星', slot=4),
                  _adr0332_forming_scoring_bench('板件5', faction='公司', slot=5)],
        board={'仙舟': 3, '持续伤害': 2, '公司': 1},
        shop=[_adr0332_forming_scoring_card('停云')],   # 仙舟件(引擎件,但板面已成)
    )
    cand = _buy_cand(st, '停云')
    reg_off = dataclasses.replace(_adr0332_forming_scoring_REG, forming_bias=0.0)
    v_off, _ = score_candidate(cand, st, _adr0332_forming_scoring_sess(), reg_off)
    v_on, _ = score_candidate(cand, st, _adr0332_forming_scoring_sess(), _adr0332_forming_scoring_REG)
    assert v_on - v_off == 0.0, (v_off, v_on)


def test_forming_bias_not_on_already_positive() -> None:
    """已正分(>forming_bias_val_max)的引擎件买入不叠加偏置
    (防 ADR-0301「高单位挤掉目标件」过冲;只顶 0/小负)。"""
    # cap 有空位:买 爻光 部署成引擎 → 板面差分大正 → 出带上沿
    st = _adr0332_forming_scoring_state(
        deployed=[_adr0332_forming_scoring_bench('爻光', faction='仙舟', slot=0),
                  _adr0332_forming_scoring_bench('藿藿', faction='仙舟', slot=1),
                  _adr0332_forming_scoring_bench('板件2', faction='公司', slot=2),
                  _adr0332_forming_scoring_bench('板件3', faction='公司', slot=3),
                  _adr0332_forming_scoring_bench('板件4', faction='公司', slot=4)],
        board={'仙舟': 2, '公司': 3},
        shop=[_adr0332_forming_scoring_card('饮月')] if False else [_adr0332_forming_scoring_card('符玄')],
    )
    cand = _buy_cand(st, '符玄')
    reg_off = dataclasses.replace(_adr0332_forming_scoring_REG, forming_bias=0.0)
    v_off, _ = score_candidate(cand, st, _adr0332_forming_scoring_sess(), reg_off)
    v_on, _ = score_candidate(cand, st, _adr0332_forming_scoring_sess(), _adr0332_forming_scoring_REG)
    assert v_off > _adr0332_forming_scoring_REG.forming_bias_val_max, \
        f'场景前置:板面差分应出带上沿(实际 {v_off})'
    assert v_on - v_off == 0.0, (v_off, v_on)


def test_forming_bias_off_channel_constants() -> None:
    """常量锁:bias 默认开(5.0);顶分上沿 0.5。"""
    assert _adr0332_forming_scoring_REG.forming_bias == 5.0
    assert _adr0332_forming_scoring_REG.forming_bias_val_max == 0.5


# ==================== adr0333_concentration ====================

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_line_defs import (
    board_max_recipe_tier,
    board_recipe_faction_count,
    board_system_tiers,
    board_total_faction_count,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    _engine_seed_affinity,
    generate_candidates,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

_adr0333_concentration_REG = DEFAULT_REGISTRY


def _adr0333_concentration_card(name: str, faction: str = '仙舟', cost: int = 1) -> object:
    return SimpleNamespace(name=name, faction=faction, cost=cost,
                           x=0, star=1)


def _adr0333_concentration_bench(name: str, faction: str = '公司',
           slot: int = 0, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _adr0333_concentration_sess() -> StrategySession:
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    return s


def _adr0333_concentration_state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 7, 'gold': 55, 'level': 6, 'hp': 80,
            'board': {'公司': 6},
            'deployed': [_adr0333_concentration_bench(f'板件{i}', faction='公司', slot=i)
                         for i in range(6)],
            'bench': [], 'shop': [], 'hp': 80}
    base.update(kw)
    return GameState(**base)


# --- ① 候选层配方亲和 _engine_seed_affinity -------------------------------


def test_affinity_empty_window_pass() -> None:
    """空窗(板面无任何过渡体系)→ 新体系引擎件放行(第一体系要开,[31])。"""
    st = _adr0333_concentration_state(board={'公司': 6}, shop=[_adr0333_concentration_card('爻光')])
    assert _engine_seed_affinity(_adr0333_concentration_card('爻光'), st, _adr0333_concentration_REG), '空窗应放行'


def test_affinity_deepen_pass() -> None:
    """板面已有仙舟 1 件(未成型)→ 仙舟件(深化)放行。"""
    st = _adr0333_concentration_state(board={'仙舟': 1, '公司': 5}, shop=[_adr0333_concentration_card('爻光')])
    assert _engine_seed_affinity(_adr0333_concentration_card('爻光'), st, _adr0333_concentration_REG), '深化件应放行'


def test_affinity_new_system_reject() -> None:
    """板面已有仙舟 1 件(未成型)→ 列车件(新体系第 1 件)拒(散买断)。"""
    st = _adr0333_concentration_state(board={'仙舟': 1, '公司': 5},
                shop=[_adr0333_concentration_card('三月七', faction='列车同行')])
    assert not _engine_seed_affinity(
        _adr0333_concentration_card('三月七', faction='列车同行'), st, _adr0333_concentration_REG), '新体系件应拒'


def test_affinity_all_formed_pass() -> None:
    """板面全部成型(仙舟3+列车2=引擎2)→ 新体系件放行(两两组合)。"""
    st = _adr0333_concentration_state(board={'仙舟': 3, '列车同行': 2, '公司': 1},
                shop=[_adr0333_concentration_card('艾丝妲', faction='持续伤害')])
    assert _engine_seed_affinity(
        _adr0333_concentration_card('艾丝妲', faction='持续伤害'), st, _adr0333_concentration_REG), '成型后可开新体系'


def test_affinity_non_recipe_immune() -> None:
    """非三羁绊件(公司/砂金)不辖(返回 True,engine_seed 本就不辖)。"""
    st = _adr0333_concentration_state(board={'仙舟': 1, '公司': 5},
                shop=[_adr0333_concentration_card('砂金', faction='公司', cost=2)])
    assert _engine_seed_affinity(
        _adr0333_concentration_card('砂金', faction='公司', cost=2), st, _adr0333_concentration_REG), '非三羁绊件不辖'


def test_affinity_seele_immune() -> None:
    """希儿系(deployed 二元判定)不辖(返回 True)。"""
    st = _adr0333_concentration_state(board={'仙舟': 1, '公司': 5},
                shop=[_adr0333_concentration_card('希儿', faction='贝洛伯格', cost=3)])
    assert _engine_seed_affinity(
        _adr0333_concentration_card('希儿', faction='贝洛伯格', cost=3), st, _adr0333_concentration_REG), '希儿系不辖'


# --- ② 买标签接线(engine_seed 分支叠加亲和) --------------------------------


def test_buy_tag_affinity_filter() -> None:
    """板面已有仙舟 1 件(未成型)+ shop 新体系引擎件(列车星期日,
    非桥名单):
    亲和过滤后不生成 engine_seed 候选(散买断)。"""
    st = _adr0333_concentration_state(
        deployed=[_adr0333_concentration_bench('爻光', faction='仙舟', slot=0),
                  _adr0333_concentration_bench('板件1', faction='公司', slot=1),
                  _adr0333_concentration_bench('板件2', faction='公司', slot=2),
                  _adr0333_concentration_bench('板件3', faction='公司', slot=3),
                  _adr0333_concentration_bench('板件4', faction='公司', slot=4),
                  _adr0333_concentration_bench('板件5', faction='公司', slot=5)],
        board={'仙舟': 1, '公司': 5},
        shop=[_adr0333_concentration_card('星期日', faction='列车同行', cost=3)],
    )
    cands = [c for c in generate_candidates(st, _adr0333_concentration_sess(), _adr0333_concentration_REG)
             if c.action.__class__.__name__ == 'BuyCard']
    assert not any(c.action.card.name == '星期日' for c in cands), \
        '新体系引擎件(未成型窗)不应生成 engine_seed 候选'


def test_buy_tag_affinity_deepen_generated() -> None:
    """板面已有仙舟 1 件(未成型)+ shop 深化件(爻光):
    生成 engine_seed 候选(配方加法)。"""
    st = _adr0333_concentration_state(
        deployed=[_adr0333_concentration_bench('爻光', faction='仙舟', slot=0),
                  _adr0333_concentration_bench('板件1', faction='公司', slot=1),
                  _adr0333_concentration_bench('板件2', faction='公司', slot=2),
                  _adr0333_concentration_bench('板件3', faction='公司', slot=3),
                  _adr0333_concentration_bench('板件4', faction='公司', slot=4),
                  _adr0333_concentration_bench('板件5', faction='公司', slot=5)],
        board={'仙舟': 1, '公司': 5},
        shop=[_adr0333_concentration_card('藿藿')],
    )
    cands = [c for c in generate_candidates(st, _adr0333_concentration_sess(), _adr0333_concentration_REG)
             if c.action.__class__.__name__ == 'BuyCard']
    assert any(c.action.card.name == '藿藿' for c in cands), \
        '深化件应生成 engine_seed 候选'


def test_buy_tag_affinity_empty_window_generated() -> None:
    """空窗(板面无过渡体系)+ shop 引擎件(爻光):
    生成 engine_seed 候选(第一体系要开)。"""
    st = _adr0333_concentration_state(
        deployed=[_adr0333_concentration_bench('板件0', faction='公司', slot=0),
                  _adr0333_concentration_bench('板件1', faction='公司', slot=1),
                  _adr0333_concentration_bench('板件2', faction='公司', slot=2),
                  _adr0333_concentration_bench('板件3', faction='公司', slot=3),
                  _adr0333_concentration_bench('板件4', faction='公司', slot=4),
                  _adr0333_concentration_bench('板件5', faction='公司', slot=5)],
        board={'公司': 6},
        shop=[_adr0333_concentration_card('爻光')],
    )
    cands = [c for c in generate_candidates(st, _adr0333_concentration_sess(), _adr0333_concentration_REG)
             if c.action.__class__.__name__ == 'BuyCard']
    assert any(c.action.card.name == '爻光' for c in cands), \
        '空窗引擎件应生成候选'


# --- ③ 新 sim 指标纯函数 ----------------------------------------------------


def test_board_concentration_metrics() -> None:
    """集中度指标纯函数:深堆 vs 散面的区分度量。"""
    deep = {'仙舟': 3, '列车同行': 2, '公司': 1, '治疗': 1}
    spread = {'仙舟': 1, '列车同行': 1, '持续伤害': 1,
              '公司': 1, '治疗': 1, '能量': 1, '欢愉': 1}
    assert board_max_recipe_tier(deep) == 3
    assert board_max_recipe_tier(spread) == 1
    assert board_recipe_faction_count(deep) == 2
    assert board_recipe_faction_count(spread) == 3
    assert board_total_faction_count(spread) == 7
    # 空板
    assert board_max_recipe_tier({}) == 0
    assert board_recipe_faction_count({}) == 0
    assert board_system_tiers({'仙舟': 3, '公司': 2}) == {
        '仙舟': 3, '列车同行': 0, '持续伤害': 0}

# —— 换核隔离桶(2026-09-03 测试分层批)——
# 本文件属 legacy_baseline 桶:锁的是旧决策核(decision_v2)内部行为语义,
# 随旧核退役而消亡;默认全量与快速集均不跑,仅基线冻结审计/A-B 开跑前
# 两时点单独跑。口径见 sr-od-test/README.md「测试纪律 · legacy 桶」。
import pytest

pytestmark = pytest.mark.legacy_baseline
