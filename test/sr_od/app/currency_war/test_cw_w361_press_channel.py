"""W361:目标外同名副本 press 通道锁(W300 design v3 V-B0~V-B9 落码)。

锁定对象(design = 唯一规格,.debug/temp/currency_war/w300_dup_ruling/
design.md v3 节;禁实现 v2 已废条款:V-A3 插件臂/COPY_PRIORITY_*/E08
「优先度」旧措辞):

1. V-B1 守卫收拢:_copy_swap_blocked 是唯一守卫合成点(生成层内联块
   已消失),探针态下生成层与守卫逐位一致;
2. V-B2 tag 路由:'copy_press' 标签进 buy_tag_priority;评分路由
   (press_copy_unit/press_core_mirror_bonus 独立给分域)已随
   ADR-0427 增补节定谳清理(生产默认 0.0 从未注入生产行为 ∧ 生成域
   被上游臂截流至近空,无观测支点),本文件锁改为「标签机制面 +
   清理卫生」——删除后评分只由通用板面维决定,与默认态逐位一致;V-B2.3 可观测行为断言(候选产出)保留;
3. V-B3/V-B5 band 推导与停机:[30] 开域覆盖 {1,2}/REFRESH_PROB 推导/
   observed 概率条优先(轮岗盲区)/带自洽闸 plane+level 停机;
4. V-B6 插件臂撤销:E05/E07 带外副本两臂都不产出候选;
5. V-B7 无第二序:COPY_PRIORITY_* 不存在,E08 走评分分量;
6. V-B8 逐轮 cap:press_copy_round_cap / press_exempt_round_cap +
   「[11] 保零息损不保 form_floor 本金」显式裁决;
7. V-B9 检查器 is_dup 双域:deployed 域判真拦,held 域只披露。
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2 import candidates as _cands
from sr_od.application.currency_war.decision_v2.arbiter import (
    _press_floor_exempt,
    arbitrate,
)
from sr_od.application.currency_war.decision_v2.candidates import (
    _buy_tag,
    _copy_swap_blocked,
    generate_candidates,
)
from sr_od.application.currency_war.decision_v2.discipline import (
    observed_probs,
    press_band,
    press_channel_max_band,
    press_channel_open,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
    DecisionV2Registry,
)
from sr_od.application.currency_war.decision_v2.scoring import (
    score_all,
    score_candidate,
)

# armA 注入(V-B3:总闸;量控 cap 走各自字段默认值)
_ARMA = replace(DEFAULT_REGISTRY, press_channel_enabled=True)

# 注入关臂:press 通道已正式开臂(默认 True,commit cb7688d4——W368
# A/B R2 验收);「通道关」行为锁改为显式注入,不再依赖默认值。
_ARM0 = replace(DEFAULT_REGISTRY, press_channel_enabled=False)

# 方向外低费件(CW 注册表真值:刃=星核猎手/燃血,黑塔=群攻/银河学者;
# 均 ∉ 姬子列车方向 {仙舟,列车同行,持续伤害},∉ 插件库/引擎名单)
_FILLER = '刃'
_FILLER_FAC = '星核猎手'
_FILLER2 = '黑塔'
_FILLER2_FAC = '银河学者'


def _dep(name: str, faction: str, slot: int = 0) -> SimpleNamespace:
    return SimpleNamespace(char_id=name, faction=faction, star=1,
                           slot=slot, position_pref='back', equips=())


def _sess() -> StrategySession:
    """锁线帧(方向=姬子列车,不含仙舟):生产路径形态——'copy'/'pair'
    既有豁免通道语义先于 press 臂(V-B2.1 放序),只有方向门拦下的
    目标外副本才落 'copy_press';裸 session 冷启动会让 pair_wants
    (同阵营/冷启动副本口)先命中。"""
    from sr_od.application.currency_war.kernel.cw_intention import (
        HoardTarget,
        IntentionState,
    )
    s = StrategySession()
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '姬子列车'
    s.v3_intention = ist
    s.v3_hoard = HoardTarget(
        frozenset({'姬子·启行', '三月七', '花火', '瓦尔特'}),
        frozenset(), 'locked')
    s.v3_core_names = {'姬子·启行'}
    s.target_comp = SimpleNamespace(factions=('列车同行',),
                                    core_chars=('姬子·启行',))
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 2, 'gold': 15, 'level': 3,
            'board': {}, 'deployed': [_dep(_FILLER, _FILLER_FAC)],
            'bench': [], 'shop': [], 'hp': 80}
    base.update(kw)
    return GameState(**base)


def _shop_card(name: str = _FILLER, cost: int = 1, x: int = 1) -> ShopCard:
    return ShopCard(x=x, faction=_FILLER_FAC, name=name, cost=cost)


# ------------------------------------------------------- V-B1 守卫收拢


def test_guard_synth_point_single_source() -> None:
    """V-B1:收拢后生成层与守卫合成点对探针态逐位一致——
    arm0 守卫拦=无候选;armA 豁免臂开=守卫放行且候选产出
    (V-B1.5「探针态必须产出候选」空臂红线)。"""
    sess = _sess()
    st = _state(shop=[_shop_card()])
    assert _copy_swap_blocked(st.shop[0], st, sess, _ARM0)
    assert _FILLER not in {c.action.card.name
                           for c in generate_candidates(st, sess,
                                                        _ARM0)
                           if isinstance(c.action, BuyCard)}
    assert not _copy_swap_blocked(st.shop[0], st, sess, _ARMA)
    got = [c for c in generate_candidates(st, sess, _ARMA)
           if isinstance(c.action, BuyCard)
           and c.action.card.name == _FILLER]
    assert got, '探针态下 armA 必须产出 press-band 副本候选(空臂红线)'
    assert got[0].tag == 'copy_press'


def test_guard_zero_drift_arms_unchanged() -> None:
    """V-B1 收拢是行为保持重构:①target 豁免臂语义不变(关=直通拦);
    ②C 臂(末窗 gap>0)放行不变;通道默认关下 press 臂不参与。
    (原 ② A 臂=filler_star_unit>0 放行,已随 ADR-0402 定谳清理删除,
    deployed 名副本放行现由 C 臂/press 臂承载。)
    """
    sess = _sess()
    st = _state(shop=[_shop_card()])
    # ① target 豁免(青雀非目标件,开关无效,守卫仍拦)——注入关臂
    # 隔离 press 豁免臂(开臂后默认注册表已带 press 臂)
    assert _copy_swap_blocked(st.shop[0], st, sess,
                              replace(_ARM0,
                                      copy_swap_target_exempt=True)) is True
    # ② C 臂:r≥handoff_gate_min_round 且 gap>0 → 放行(锁线帧 gap)
    s2 = _sess()
    st_c = _state(round_num=7, shop=[_shop_card()])
    reg_c = replace(_ARM0, handoff_gate_min_round=6)
    assert not _copy_swap_blocked(st_c.shop[0], st_c, s2, reg_c)


# ------------------------------------------------- V-B2 tag/评分路由


def test_tag_registration_and_priority_position() -> None:
    """V-B2.1/V-B3:'copy_press' 进 buy_tag_priority(置于 'copy' 之后)
    与 BUY_TAGS;band 外/通道关不产生标签。"""
    prio = DEFAULT_REGISTRY.buy_tag_priority
    assert 'copy_press' in prio
    assert prio.index('copy_press') == prio.index('copy') + 1
    assert 'copy_press' in _cands.BUY_TAGS
    st = _state(shop=[_shop_card()])
    sess = _sess()
    # 通道关(注入):无标签(开臂后默认注册表通道开,copy_press 激活)
    assert _buy_tag(st.shop[0], st, sess, _ARM0) is None
    # 通道开:copy_press
    assert _buy_tag(st.shop[0], st, sess, _ARMA) == 'copy_press'
    # bench 满:E03 门字面(〔W300 口述〕「囤满备战席→没位置」)
    st_full = _state(shop=[_shop_card()],
                     bench=[BenchChar(slot=i, char_id=f'杂{i}',
                                      faction=_FILLER_FAC)
                            for i in range(DEFAULT_REGISTRY.bench_capacity)])
    assert _buy_tag(st.shop[0], st_full, sess, _ARMA) is None
    # 同轮已卖守卫:r408 不回买
    s2 = _sess()
    s2.v2_round_key = (1, 2)
    s2.v2_round_sold = {_FILLER}
    assert _buy_tag(st.shop[0], st, s2, _ARMA) is None


def test_press_scoring_route_cleaned_hygiene() -> None:
    """定谳清理卫生锁(ADR-0427 增补节,策略开关生命周期第 4 态):
    ① 评分路由两字段已删(not hasattr);② 通道价值主体健在——
    总闸/双 cap 字段/[11] 豁免臂谓词;③ 删除后 copy_press 候选与
    删除前默认态(press_copy_unit=0.0)行为一致——探针态下正分可达
    (板面 depth 维自带 +2,与已删路由无关),通道行为面零漂移。"""
    assert not hasattr(DecisionV2Registry, 'press_copy_unit')
    assert not hasattr(DecisionV2Registry, 'press_core_mirror_bonus')
    assert DEFAULT_REGISTRY.press_channel_enabled is True
    assert DEFAULT_REGISTRY.press_copy_round_cap == 1
    assert DEFAULT_REGISTRY.press_exempt_round_cap == 2
    sess = _sess()
    st = _state(shop=[_shop_card()])
    cands = [c for c in generate_candidates(st, sess, _ARMA)
             if isinstance(c.action, BuyCard)
             and c.action.card.name == _FILLER]
    assert cands and cands[0].tag == 'copy_press'
    val, _bd = score_candidate(cands[0], st, sess, _ARMA)
    assert val > 0


def test_observable_reject_reason_never_guard_or_zero_score() -> None:
    """V-B2.3 可观测行为断言:armA 探针态下该卡产生买候选;若被拒,
    拒因 ∉ {copy_swap 守卫(候选不存在), 非正分}。评分路由删除
    (ADR-0427 增补节)不改本面:板面 depth 维自带正分,非正分拒
    仍是异常信号。"""
    sess = _sess()
    st = _state(shop=[_shop_card()])
    cands = generate_candidates(st, sess, _ARMA)
    got = [c for c in cands if isinstance(c.action, BuyCard)
           and c.action.card.name == _FILLER]
    assert got, 'V-B2.3:该卡必须产生买候选'
    scored = score_all(cands, st, sess, _ARMA)
    res = arbitrate(scored, st, sess, _ARMA)
    row = next(r for r in res.log if r['desc'].startswith(f'买 {_FILLER}'))
    if not row['accepted']:
        assert '非正分' not in (row['reject'] or ''), \
            f'拒因=非正分(异常,depth 维应给正分): {row}'
    assert got[0].tag == 'copy_press'


# ------------------------------------------- V-B3/V-B5 band 推导与停机


def test_band_derivation_and_authority_override() -> None:
    """V-B5.2:[30] 开域覆盖(lv1-6 band={1,2},lv4 不再是推导孤值);
    lv≥7 纯推导(lv7={1,2,3});自洽闸参照系 press_band(6)={1,2}。"""
    reg = DEFAULT_REGISTRY
    for lv in (1, 2, 3, 4, 5, 6):
        assert press_band(lv, None, reg) == {1, 2}, f'lv{lv}'
    assert press_channel_max_band(reg) == {1, 2}
    assert press_band(7, None, reg) == {1, 2, 3}
    assert press_band(8, None, reg) == {1, 2, 3}


def test_band_observed_probs_priority() -> None:
    """V-B5.3 轮岗盲区:observed 概率条优先于基线行(签名
    press_band(level, probs));取不到退 REFRESH_PROB 基线。"""
    reg = DEFAULT_REGISTRY
    # lv5 轮岗翻 2 费(2 费 p≈0.56 单档即过半):observed band 自动含 2 费
    rotation = {1: 0.15, 2: 0.56, 3: 0.22, 4: 0.05, 5: 0.02}
    assert 2 in press_band(5, rotation, reg)
    # observed 优先:翻 1 费时 1 费单档过半,band 截断含 {1,2}(开域覆盖)
    rot1 = {1: 0.60, 2: 0.22, 3: 0.15, 4: 0.02, 5: 0.01}
    assert press_band(5, rot1, reg) == {1, 2}
    # state.refresh_probs 披露域 → observed_probs 读取
    st = _state()
    assert observed_probs(st) is None
    st.refresh_probs = rotation
    assert observed_probs(st) == rotation


def test_channel_shutdown_conditions() -> None:
    """V-A2/V-B5 停机:plane≠1 关;lv>max 关;带自洽闸破(lv7)关;
    轮岗 observed 推出 3 费进带时保守关。"""
    reg = DEFAULT_REGISTRY
    st = _state()
    assert press_channel_open(st, reg)
    assert not press_channel_open(_state(plane=2), reg)
    assert not press_channel_open(_state(level=7), reg)
    # observed 使推导带破 {1,2}(3 费累计过半)→ 自洽闸保守关
    st_rot = _state()
    st_rot.refresh_probs = {1: 0.10, 2: 0.20, 3: 0.55, 4: 0.10, 5: 0.05}
    assert not press_channel_open(st_rot, reg)


def test_registry_press_defaults_zero_drift() -> None:
    """V-B3 默认值锁:press_channel_enabled 已正式开臂(默认 True,
    commit cb7688d4——W368 A/B R2 验收;「默认全关零漂移」旧锁随开臂
    失效,通道关行为改由 _ARM0 注入锁);其余参保持中性值。评分偏置
    两字段的删除锁在 test_press_scoring_route_cleaned_hygiene。"""
    assert DEFAULT_REGISTRY.press_channel_enabled is True
    assert DEFAULT_REGISTRY.press_band_cum_threshold == 0.50
    assert DEFAULT_REGISTRY.press_channel_max_level == 6
    assert DEFAULT_REGISTRY.press_copy_round_cap == 1
    assert DEFAULT_REGISTRY.press_exempt_round_cap == 2


# ------------------------------------------------- V-B6 插件臂撤销


def test_out_of_band_grayout_both_arms() -> None:
    """V-B6:E05/E07 band 外副本(cost=3)两臂都不产出候选
    (V-A3 插件臂已撤销,「才考虑」不实现为购买分支)。"""
    sess = _sess()
    st = _state(deployed=[_dep(_FILLER2, _FILLER2_FAC)],
                shop=[_shop_card(_FILLER2, 3, x=1)])
    for reg in (DEFAULT_REGISTRY, _ARMA):
        assert _copy_swap_blocked(st.shop[0], st, sess, reg)
        assert _FILLER2 not in {c.action.card.name
                                for c in generate_candidates(st, sess, reg)
                                if isinstance(c.action, BuyCard)}
    # V-B7:第二序不存在——registry 无 COPY_PRIORITY 字段
    assert not [f for f in DecisionV2Registry.__dataclass_fields__
                if 'priority' in f and f != 'buy_tag_priority'
                and f != 'sell_tag_priority']


# ------------------------------------------------------- V-B8 逐轮 cap


def test_press_floor_exempt_cap_and_ruling() -> None:
    """V-B8:[11] 三相位前置臂——同档/1费放行(保息档线不保
    form_floor 本金,gold=19/cost=9 击穿地板亦放行);逐轮 cap 超限
    失效;通道关/跨档/应急态不放行。"""
    reg_on = replace(DEFAULT_REGISTRY, press_channel_enabled=True)
    sess = _sess()
    st = _state(gold=19)
    working = st
    cand = BuyCard(_shop_card(_FILLER, 9), reason='')
    probe = _cands.Candidate(action=cand, tag='bridge_core', source='shop')
    # 9 费跨档?19//10=1,10//10=1 → 同档;cost=1 恒放。同档账:
    # (19-9)//10=1 >= 19//10=1 → 放行(击穿 20 地板至息档线,V-B8.2)
    auth: dict = {}
    assert _press_floor_exempt(probe, working, st, sess, reg_on, auth)
    assert 'press_floor_exempt' in auth
    # 通道关(注入 _ARM0):不放行(开臂后默认注册表通道开)
    assert not _press_floor_exempt(probe, working, st, sess,
                                   _ARM0)
    # 跨档有息损:不放行(gold=19, cost=19 → 0//10=0 < 1)
    cand_cross = BuyCard(_shop_card(_FILLER, 19), reason='')
    probe_cross = _cands.Candidate(action=cand_cross, tag='bridge_core',
                                   source='shop')
    assert not _press_floor_exempt(probe_cross, working, st, sess, reg_on)
    # 逐轮 cap:超 press_exempt_round_cap 后豁免失效
    sess.v2_round_press_exempt = reg_on.press_exempt_round_cap
    assert not _press_floor_exempt(probe, working, st, sess, reg_on)


def test_press_copy_round_cap_in_arbitration() -> None:
    """V-B8.1:press 候选逐轮采纳 ≤ press_copy_round_cap(默认 1)。
    评分以定值正分手工注入(与评分维解耦——cap 量控语义的独立锁
    不依赖任何评分偏置通道;原 filler_star_unit 注入已随 ADR-0402
    定谳清理删除)。"""
    reg = _ARMA
    sess = _sess()
    st = _state(deployed=[_dep(_FILLER, _FILLER_FAC),
                          _dep(_FILLER2, _FILLER2_FAC, slot=1)],
                shop=[_shop_card(_FILLER, 1, x=1),
                      _shop_card(_FILLER2, 1, x=2)])
    cands = [c for c in generate_candidates(st, sess, reg)
             if isinstance(c.action, BuyCard)]
    assert len(cands) == 2, '两笔 press 候选都应生成'
    scored = [(c, 5.0,
               {'cost': getattr(getattr(c.action, 'card', None),
                                'cost', 2) or 2})
              for c in cands]
    res = arbitrate(scored, st, sess, reg)
    accepted = [r for r in res.log if r['tag'] == 'copy_press'
                and r['accepted']]
    rejected = [r for r in res.log if r['tag'] == 'copy_press'
                and not r['accepted']]
    assert len(accepted) == reg.press_copy_round_cap
    assert any('press_copy_cap' in (r['reject'] or '') for r in rejected)


# ------------------------------------------- V-B9 检查器 is_dup 双域


def _seg_row(cards: list[dict], deployed: list[dict],
             bench: list[dict] | None = None) -> dict:
    """合成段级账本行(g0=13<20 同息档,未成型,未停手)。"""
    return {
        'plane': 1, 'round_num': 1, 'gold': 13, 'hp': 60,
        'formed_stop': False,
        'state': {'board_factions': {}, 'deployed': deployed,
                  'bench': bench or [], 'cap': 4, 'level': 4},
        'target_comp': '',
        'actions': [],
        'sim': {'node': 'battle',
                'income': {'base': 5, 'interest': 0, 'streak': 0,
                           'event': 1},
                'spend': {'buys': {}, 'levelup': 0, 'refresh': 0,
                          'sell_income': 0},
                'bench_full_skipped_buys': 0,
                'shop_waves': [{'event': 'offer', 'gold': 13,
                                'cards': cards}]},
    }


def test_checker_dup_dual_domain() -> None:
    """V-B9:deployed 同名压库副本未买 → 通道关非违规(披露
    copy_press_channel_closed);bench-only 同名 → 披露
    copy_bench_only_skipped 不进真拦;非重复散件(C-D)照报真拦。"""
    from sr_od.application.currency_war.sim import cw_sim_checks as chk
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_line_defs import (
        ENGINE_FACTIONS,
    )
    name = next(n for n, c in CHARACTERS.items()
                if c.cost == 1
                and set(c.factions or ()) & set(ENGINE_FACTIONS))
    cards = [{'name': name, 'cost': 1, 'faction': '?'}]
    # deployed 同名(通道开=新默认,commit cb7688d4):未买=C-B 真拦
    # (通道开转正=买家被授权买;旧「通道关转披露 copy_press_channel_
    # closed」语义由 seg_copy_press_disclosure 在通道关注册表下保留)
    row_dep = _seg_row(cards, deployed=[{'char_id': name}])
    evs_dep = chk.seg_check_lossless_buy_missed([row_dep])
    assert evs_dep and evs_dep[0]['class'] == 'C-B', evs_dep
    assert not chk.seg_copy_press_disclosure([row_dep])
    # bench-only 同名:披露不进真拦(V-B9.3)
    row_bench = _seg_row(cards, deployed=[],
                         bench=[{'char_id': name}])
    assert not chk.seg_check_lossless_buy_missed([row_bench])
    disc = chk.seg_copy_press_disclosure([row_bench])
    assert disc and disc[0]['kind'] == 'copy_bench_only_skipped'
    # 非重复散件(C-D):真拦语义保持
    row_plain = _seg_row(cards, deployed=[])
    evs = chk.seg_check_lossless_buy_missed([row_plain])
    assert evs and evs[0]['class'] == 'C-D'
    assert not chk.seg_copy_press_disclosure([row_plain])


def test_transition_cost_max_single_source() -> None:
    """V-A2:检查器成本带上限 import 买家侧单一源
    press_channel_max_band()(={1,2} 的 max=2,无数值漂移)。"""
    from sr_od.application.currency_war.sim.cw_sim_checks import (
        _seg_transition_cost_max,
    )
    assert _seg_transition_cost_max() == 2
    assert _seg_transition_cost_max() == max(
        press_channel_max_band(DEFAULT_REGISTRY))


# ------------------------------------------------- 供给一致性探针接线


def test_supply_consistency_probe_includes_w300() -> None:
    """V-B1.3:检查网总表含 press 通道探针;供给一致性探针与
    check_w300_press_channel_probe 均零违规(现行为回归面)。"""
    from sr_od.application.currency_war.sim import cw_sim_checks as chk
    r1 = chk.check_decision_v2_supply_label_consistency()
    assert r1['violations'] == 0, r1['detail']
    r2 = chk.check_w300_press_channel_probe()
    assert r2['violations'] == 0, r2['detail']
