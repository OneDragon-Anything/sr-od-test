"""W628 · 重构迁移批 2(方向层接管+效果层归位+开关清偿)锁面。

依据 = 蓝图 v-final.1 §7 批 2 行 + §4.3-R1/R5 + W622 预验尸 P1-P9 +
W620 BATCH2_APPENDIX 三危险供给点(D1/D2/D3):

1. D1:hoard 可信位——投影失败帧 ``hoard_readable=False``,消费域走保守域,
   变异探针(投影抛错)下买侧行为 ≠ 空集放行;
2. D2:committed 缺供给帧 = 保守侧 False——本文件不再持测;保守侧直锁
   = test_cw_session_separation::test_none_state_criterion_faces_
   return_defaults(``committed_authority(None, bare) is False``)+ 本
   文件对拍锁帧 1-2(P1 帧ist 缺席 → False);原并入目标
   test_cw_w620_migration_b1 本体已随 dd-038 批删除,指针收口重锚;
3. D3:息线单一源 = ``registry.interest_floor()`` 派生(interest_cap×10),
   全仓属性读点 = 0(grep 锁)+ ALL IN override 通道;
4. P7:意向状态机驱动点契约——每 game-round 恰一次(键守卫幂等),
   registry 注入分歧探针(P6:注入臂与缺省臂必须出现受控分歧);
5. P4:ist 跨局零残留(每局新建 StrategySession 构造性保证的行为锁);
6. 哨兵锁:局23 型帧(100 金+备战空+息线姿态)在现行 mandate_v1 商店线
   决策面(``decide_shop_action``)。2026-09-08 覆盖对账后收敛为两面:
   2★ 压库件无退金背书 ⇒ 端到端零支出 + 必花域 L3 终结;金位不破息线
   (0-100 金全决策面端到端,主题文件无此扫面)。原「息线供给恒等」
   「不死守可辨收敛」两面经亲读对账由主题文件承载(test_cw_realizable_interest_floor/
   test_cw_statefn + test_cw_session_separation;test_cw_mandate_v1::
   test_shop_visit_sets_latch / test_cw_shop_line::
   test_d_p2idle_idle_gold_counter / test_cw_must_spend_zone::
   test_whitelist_empty_shop_cap_top_zero_consume),重复锁已删
   (README 纪律 7 跨文件择一);复活史见哨兵节注;
7. committed 翻真谓词 vs 旧 CommitSignals 判定:逐帧对拍锁(P1 段
   小帧集,分歧仅允许出现在方向层接管区并逐帧定性)。
"""
from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_board_state import (
    board_state_bridge,
)
from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    committed_authority,
    drive_intention,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY as _REG,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    CloseShop,
    GameState,
    LevelUpShop,
    RefreshShop,
    ShopCard,
)
from sr_od.application.currency_war.kernel.cw_transition import CommitSignals
from sr_od.application.currency_war.strategies.impl.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.impl.mandate_v1.assembly import (
    assemble,
    hoard_consumer_domain,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.contracts import (
    Snapshot,
    SubstateClassification,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    decide_shop_action,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    line_members,
)

_SRC = (Path(__file__).parents[5] / 'src' / 'sr_od' / 'application'
        / 'currency_war')


def _snapshot(plane: int = 1, round_num: int = 2) -> Snapshot:
    return Snapshot(
        classification=SubstateClassification(
            name='prep_shop', evidence=('test',), confident=True),
        plane=plane, round_num=round_num, level=3, gold=40, gold_trusted=True,
        free_bench_slots=3, deploy_vacancy=1, shop_open=False,
    )


def _state(plane: int = 1, round_num: int = 2, gold: int = 40) -> GameState:
    st = GameState()
    st.plane = plane
    st.round_num = round_num
    st.gold = gold
    st.level = 3
    return st


# ----------------------------------------------------- D1 hoard 可信位

def test_d1_hoard_readable_normal_frame():
    """正常帧:ist 未锁 → hoard = ⑤兜底域(fallback),可信位为真。

    「空集双义」分离的关键:正常帧 readable 恒 True(含 fallback 非空域
    与真空集),失败帧才 False——消费侧语义不因实现细节抖动。
    """
    sess = StrategySession()
    state_of(sess).v3_intention = IntentionState()
    turn = assemble(_snapshot(), sess)
    assert turn.direction.hoard_readable is True
    assert isinstance(turn.direction.hoard, frozenset)


def test_d1_mutation_probe_projection_failure_conservative_domain(monkeypatch):
    """变异探针(D1 验收判据):hoard_target_set 抛错 → 消费域 = 保守域。

    静默退空集 = 锁线局囤货方向消失一帧、买侧按无方向放行——本锁钉住
    「投影失败」与「真无目标」表示分离(hoard_readable 位)。
    """
    import sr_od.application.currency_war.kernel.cw_intention as cw_intention_mod

    sess = StrategySession()
    state_of(sess).v3_intention = IntentionState()

    def _boom(_state, _ist):
        raise RuntimeError('注入:投影失败')

    monkeypatch.setattr(cw_intention_mod, 'hoard_target_set', _boom)
    turn = assemble(_snapshot(), sess)
    d = turn.direction
    assert d.hoard_readable is False          # 失败帧显式暴露
    full = frozenset({'任意件A', '任意件B'})
    assert hoard_consumer_domain(d, full) == full     # 保守域,非空集放行
    ok = replace(d, hoard_readable=True)
    assert hoard_consumer_domain(ok, full) == ok.hoard  # 正常帧走目标集


# ----------------------------------------------------- D2 缺供给保守侧
# (原 test_d2_missing_supply_falls_conservative 删并:缺供给保守侧现由
#  test_cw_session_separation::test_none_state_criterion_faces_return_
#  defaults 直锁(committed_authority(None, bare) is False)+ 本文件
#  对拍锁帧 1-2 承载。原并入目标 test_cw_w620_migration_b1 本体已随
#  dd-038 批删除,死指针收口重锚。重复构成删并理由(README 纪律 8)。)


# ----------------------------------------------------- W629-R2 镜像雷锁


def test_d3_grep_lock_no_interest_floor_attribute_reads():
    """grep 锁(D3):``registry/reg.interest_floor`` 属性读点全仓 = 0。

    豁免:registry.py 定义处(方法本体/override 字段/注释);调用形态
    ``.interest_floor()`` 不匹配(带括号),裸属性读(无括号)即违规。
    """
    pat = re.compile(r'\b(?:registry|reg)\.interest_floor\b(?!\()')
    offenders = {}
    for path in _SRC.rglob('*.py'):
        hits = len(pat.findall(path.read_text(encoding='utf-8')))
        if hits:
            offenders[path.name] = hits
    assert set(offenders) <= {'registry.py'}, offenders


# ----------------------------------------------------- P7 驱动点契约 + P6 注入

def test_p7_drive_intention_idempotent_per_round():
    """P7:同 (plane, round) 重入驱动 = 幂等(键守卫),跨轮才推进。"""
    sess = StrategySession()
    st = _state(plane=1, round_num=2)
    # W6 波3:drive_intention 切容器签名,GameState 帧经过渡桥装箱。
    drive_intention(board_state_bridge(st), sess)
    assert state_of(sess).v3_intention_key == (1, 2)
    ev1 = state_of(sess).v3_intention.last_event
    drive_intention(board_state_bridge(st), sess)  # 同轮重入:不重复驱动
    assert state_of(sess).v3_intention_key == (1, 2)
    assert state_of(sess).v3_intention.last_event == ev1
    drive_intention(board_state_bridge(_state(plane=1, round_num=3)), sess)   # 跨轮:推进
    assert state_of(sess).v3_intention_key == (1, 3)


def test_p6_registry_injection_reaches_state_machine():
    """P6 注入分歧探针:注入臂与缺省臂必须出现受控分歧,无分歧 = 注入链断。

    旋钮 = line_env_lock_min_round(环境判据观察期):调大 = 判据本轮不辖
    → 对抗环境帧缺省臂缓锁、注入臂落锁——两臂 ist 分歧即注入链可达证。
    【夹具演进(经济冻结批)】原 plane=2 unlocked 帧:旧形态缺省臂保持
    unlocked;现 P2 unlocked 帧被强制移交重锁域接管(目标不空窗
    语义,载体 = test_cw_line_feasibility.py P2 移交组),与旋钮无关
    → 不再承载分歧。改用 weak 帧(撤销机器在册态,移交不辖,「直至
    新信号」语义保留)。
    """
    from sr_od.application.currency_war.kernel.cw_intention import update_intention
    st = _state(plane=2, round_num=1)   # P2:comp 锁定通道(P1 配方锁区不锁 comp)
    st.enemy_affixes = ['净化身心']            # 对抗词缀(万敌强环境不命中)
    st.shop = [SimpleNamespace(name='万敌')]   # ③核心卡信号可见
    reg_def = _REG
    reg_inj = replace(_REG, line_env_lock_min_round=99)
    ist_def = update_intention(board_state_bridge(st),
                               IntentionState(phase='weak', weak_comp='万敌单C'),
                               None, registry=reg_def)
    ist_inj = update_intention(board_state_bridge(st),
                               IntentionState(phase='weak', weak_comp='万敌单C'),
                               None, registry=reg_inj)
    assert ist_def.locked_comp == ''            # 缺省臂:环境判据缓锁(weak 保持)
    assert ist_inj.locked_comp != ''            # 注入臂:判据不辖 → 落锁


def test_p4_ist_zero_residue_across_matches():
    """P4:跨局 ist 零残留——每局新建 StrategySession,ist/驱动键从零开始。"""
    sess = StrategySession()
    drive_intention(board_state_bridge(_state()), sess)
    assert state_of(sess).v3_intention is not None and state_of(sess).v3_intention.evicted == set()
    fresh = StrategySession()   # 新局(构造性重置)
    assert state_of(fresh).v3_intention is None      # 策略器字段迁 MandateState
    assert state_of(fresh).v3_intention_key is None


# ----------------------------------------------------- 哨兵锁:局23 型帧
# 复活说明:原 test_sentinel_ju23_frame_releases_on_new_stack 以「并入
# w633」为名删除,并入目标经 2026-09-03 歼击战核查不存在 = 指针失真。
# 旧「release 帧」形态随 DP 姿态核/泄息指令死链退役(w633 同批注记),
# dp_posture='release' 遥测标签写端已死、不可锁;复活语义改锁现行
# mandate_v1 商店线决策面的三件事:息线供给恒等 / 不死守可辨收敛 /
# 金位不破息线。统一帧形状 = 列车同行线成型(全员 2★ 上场,stop_buy
# 成立)+ bench 空 + level 6(4 费档在档窗内)+ P1 局中帧。

_JU23_COMP = next(c for c in COMP_LIBRARY if c.name == '列车同行')
_JU23_STOCK_COST = 4     # 压库件卡费(档窗内;与注册表 cost 解耦)


def _sc(name: str, cost: int = _JU23_STOCK_COST, star: int = 1) -> ShopCard:
    return ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=star)


def _ju23_frame(gold: int, shop: list[ShopCard] | None = None) -> GameState:
    """局23 型帧:线成型(全员 2★ 上场)+ 备战空 + P1 局中。"""
    return GameState(
        plane=1, round_num=4, gold=gold, level=6, hp=80,
        shop_refresh_cost=2,
        deployed=[BenchChar(slot=20 + i, char_id=m, faction='仙舟罗浮',
                            star=2)
                  for i, m in enumerate(line_members(_JU23_COMP))],
        bench=[None] * BENCH_CAPACITY,
        shop=shop if shop is not None else [],
        node_type='battle', board={})


def _ju23_session() -> StrategySession:
    sess = StrategySession()
    state_of(sess).target_comp = _JU23_COMP
    return sess


# (test_ju23_supply_identity_gstar_and_s_reserve_boundary 已删 2026-09-08
#  覆盖对账:息线供给恒等两面均由主题文件承载——g*==50 = saturation_line(5)
#  ==50(test_cw_statefn)× cap_resolved_of_session(裸真 session)==DEFAULT
#  (test_cw_session_separation),组合面另经 test_cw_launch_arbitrage 全域
#  等价扫现算;s_reserve==50 金约束边界(49 拒/50 过)= test_cw_realizable_interest_floor::
#  test_m6_p56_reject_counter 同边界对 + test_stockpile_s_reserve_boundary
#  位移面超集。README 纪律 7 跨文件等价择一。)


# (test_ju23_stock_match_buys_and_empty_shop_close_discernible 已删
#  2026-09-08 覆盖对账:店空必花域帧 → LevelUpShop(m3_batch:must_spend)
#  终结面 = test_cw_mandate_v1::test_shop_visit_sets_latch 同构造帧
#  (_visit_state ≡ 本文件 _ju23_frame(100, []),gold/level/deployed 逐字段
#  一致)同断言;shop_visit_idle_gold==1 = test_cw_shop_line::
#  test_d_p2idle_idle_gold_counter,shop_r1_no_chaseable_member==1 =
#  test_cw_must_spend_zone::test_whitelist_empty_shop_cap_top_zero_consume;
#  stockpile_buy 放行面 = test_cw_shop_line::test_stockpile_face_m6_
#  opens_with_frame_window。README 纪律 7 跨文件择一。)


def test_ju23_star2_stock_card_has_no_refund_backing_no_spend():
    """局23 帧 2★ 压库件:无全额可退背书 ⇒ 端到端零支出。

    stockpile_buy 与 dominance 同以 refund_full_star_ok 为背书门:
    2★ 件两条买面都不可发射,溢余滞留(不放行)而非带病买——
    锁「背书门在局23 帧端到端成立」,非单位锁复述。
    """
    cfg = SimpleNamespace(ev_arm='full')
    sess = _ju23_session()
    act = decide_shop_action(_ju23_frame(
        100, [_sc('花火', star=2)]), sess, cfg)
    assert not isinstance(act, (BuyCard, RefreshShop))
    # 必花域末位 L3(店空/2★ 无背书 ⇒ 全层无对象)
    assert isinstance(act, LevelUpShop)
    assert act.auth_basis == 'm3_batch:must_spend'


# (test_ju23_liquid_refund_shifts_s_reserve_down 已删 2026-09-08 覆盖对账:
#  断言面 = stockpile_buy 金约束边界在 s_reserve=48 的实例,与
#  test_cw_realizable_interest_floor::test_stockpile_s_reserve_boundary(s_reserve=47,差 1 拒/
#  边界过/差 2 过)同谓词等价,常量差异零新语义;docstring 所称「活期退金
#  投影进 s_reserve」的算术不在断言路径(s_reserve 是测试手抄入参,
#  stockpile_buy 不算投影)——与 DEBTS D21 删 test_liquid_refund_excludes_
#  material 同判据(rule 18 docstring≠断言面)。投影值收缩的 decide 级
#  真锁缺口维持 D21 记账。)


def test_ju23_full_surface_gold_never_breaks_interest_line():
    """金位不破息线(端到端复合):0-100 金全决策面逐帧走真函数。

    每个起始金位完整走一次店内访问(动作后真值回写再判,ADR-0517
    §8.1 口径):任一 BuyCard/RefreshShop 花后金 ≥ s_reserve(本帧形状
    = 50);息线下(≤50)整访问零支出(无误清);每访问都以 CloseShop
    收束且有界迭代(无死守环)。
    T-115 适配(ADR-0580):店卡改用真无关件(局23杂件,非④放行集/
    registry 核心)——原探针花火 ∈ TRANSITION_PACK carry,未锁双轨
    P1 帧会被 ④转线放行臂在息线下买入(1★ 全额退 = 可逆资产,裁定
    408② 的有意取舍);「息线下零支出」不变式对④放行件域已被裁定
    取代,④例外语义由 test_cw_locked_buy_membership_split 重推锁
    承载,本锁在真无关件域保持。"""
    cfg = SimpleNamespace(ev_arm='full')
    for gold0 in range(0, 101):
        st = _ju23_frame(gold0, [_sc('局23杂件')])
        sess = _ju23_session()
        for _ in range(15):
            act = decide_shop_action(st, sess, cfg)
            if isinstance(act, BuyCard):
                cost = act.card.cost if act.card.cost else 3
                if gold0 <= 50:
                    assert st.gold - cost >= 50, (gold0, st.gold, cost)
                st.gold -= cost
                st.shop = [c for c in st.shop if c is not act.card]
            elif isinstance(act, RefreshShop):
                if gold0 <= 50:
                    assert st.gold - act.cost >= 50, (gold0, st.gold)
                st.gold -= act.cost
            elif isinstance(act, LevelUpShop):
                # 必花域 L3(20 号稿):域内升级授权;域外(≤50)零升级
                if gold0 <= 50:
                    raise AssertionError(
                        f'域外帧意外升级 {act!r} @ {gold0} 金')
                st.gold -= act.cost
                st.level += 1
            elif isinstance(act, CloseShop):
                break
            else:
                raise AssertionError(f'局23 帧意外动作 {act!r} @ {gold0} 金')
        else:
            raise AssertionError(f'决策不收敛(死守嫌疑)@ {gold0} 金')
        if gold0 <= 50:
            assert st.gold == gold0, (gold0, st.gold)


# ------------------------------------------- committed 谓词逐帧对拍(P1 附)

# 旧语义复刻的基准常量:生产面 t_of/ready/阈值常量已随旧定型机退役
# (working tree 在飞批删除),此处按退役前版本原值记录,只辖本对拍
# 基准,非生产路径。
_COMMIT_SIGNAL_THRESHOLD: float = 5.0
_COMMIT_MIN_T: int = 7


def _old_t_of(plane: int, round_num: int) -> int:
    """全局节点序号((plane−1)*9 + round,round 1-9 截断;与 horizon 的 t 同构)。"""
    return (min(plane, 3) - 1) * 9 + max(1, min(round_num, 9))


def _old_ready(sig: CommitSignals, t: int = 0) -> bool:
    """退役版 ready 判定:领先线信号分 ≥ 阈值 且 t ≥ 轮门。"""
    if t and t < _COMMIT_MIN_T:
        return False
    lead = sig.leader()
    return lead is not None and lead[1] >= _COMMIT_SIGNAL_THRESHOLD


def _old_committed(state: GameState, session: StrategySession) -> bool:
    """旧语义复刻(退役战略层判定式;对拍基准,非生产路径)。

    committed = plane≥2 ∨ (signals.ready ∧ (可切换 ∨ target==领先线));
    ready/t_of 消费退役前复刻(见上常量注)。
    """
    if state.plane >= 2:
        return True
    sig = getattr(state_of(session), 'commit_signals', None)
    if sig is None:
        return False
    ready = _old_ready(sig, _old_t_of(state.plane, state.round_num))
    lead = sig.leader() if ready else None
    return bool(ready and lead is not None)


def test_committed_predicate_frame_by_frame_vs_old():
    """committed 翻真谓词 vs 旧 CommitSignals 判定:逐帧对拍锁。

    帧集(判前锁):分歧仅允许出现在「方向层接管区」= 新谓词尚保守
    (ist 未锁)而旧信号已 ready 的窗口;反向分歧(新 True 旧 False)
    仅允许 plane≥2 帧。任何出区分歧 = 谓词漂移,门红。
    """
    frames = []
    # 帧1-2:P1 前段,信号空、ist 未锁 → 双 False
    for rnd in (1, 3):
        frames.append((_state(plane=1, round_num=rnd), StrategySession(),
                       'both_false'))
    # 帧3:P1 信号 ready(分超阈+过轮门)但 ist 未锁 → 预期分歧(接管区,
    # 新谓词保守)
    s3 = StrategySession()
    state_of(s3).commit_signals = CommitSignals()
    state_of(s3).commit_signals.scores = {'万敌燃血': 99.0}
    frames.append((_state(plane=1, round_num=8), s3, 'takeover_zone_only_old'))
    # 帧4:ist 已锁 → 双 True
    s4 = StrategySession()
    state_of(s4).v3_intention = IntentionState(phase='locked', locked_comp='万敌燃血')
    state_of(s4).commit_signals = CommitSignals()
    state_of(s4).commit_signals.scores = {'万敌燃血': 99.0}
    frames.append((_state(plane=1, round_num=8), s4, 'both_true'))
    # 帧5:P2 → 双 True(语义边界保留)
    frames.append((_state(plane=2, round_num=1), StrategySession(),
                   'both_true_p2'))
    for st, sess, expect in frames:
        new_v = committed_authority(st, sess)
        old_v = _old_committed(st, sess)
        if expect == 'both_false':
            assert not new_v and not old_v
        elif expect == 'both_true' or expect == 'both_true_p2':
            assert new_v and old_v
        else:   # takeover_zone_only_old:旧翻新未翻 = 接管区唯一合法分歧形
            assert old_v and not new_v, (st.plane, st.round_num, new_v, old_v)
