"""W628 · 重构迁移批 2(方向层接管+效果层归位+开关清偿)锁面。

依据 = 蓝图 v-final.1 §7 批 2 行 + §4.3-R1/R5 + W622 预验尸 P1-P9 +
W620 BATCH2_APPENDIX 三危险供给点(D1/D2/D3):

1. D1:hoard 可信位——投影失败帧 ``hoard_readable=False``,消费域走保守域,
   变异探针(投影抛错)下买侧行为 ≠ 空集放行;
2. D2:committed 缺供给帧 = 保守侧 False(拔供给探针),禁缺省激进侧;
3. D3:息线单一源 = ``registry.interest_floor()`` 派生(interest_cap×10),
   全仓属性读点 = 0(grep 锁)+ ALL IN override 通道;
4. P7:意向状态机驱动点契约——每 game-round 恰一次(键守卫幂等),
   registry 注入分歧探针(P6:注入臂与缺省臂必须出现受控分歧);
5. P4:ist 跨局零残留(每局新建 StrategySession 构造性保证的行为锁);
6. 哨兵锁:局23 型帧(100 金+备战空+息线姿态)在现行 mandate_v1 商店线
   决策面(``decide_shop_action``)复活 5 条——息线供给恒等(g*/s_reserve
   边界)、不死守可辨收敛(压库买/店空 CloseShop+计数)、金位不破息线
   (0-100 金全决策面端到端)。2026-09-03 歼击战核查:本条曾登记「并入
   w633」,并入目标不存在 = 指针失真,语义裸奔至今,本批复活;
7. committed 翻真谓词 vs 旧 CommitSignals 判定:逐帧对拍锁(P1 段
   小帧集,分歧仅允许出现在方向层接管区并逐帧定性)。
"""
from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_economy import (
    cap_resolved_of_session,
    saturation_line,
)
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
    sess.v3_intention = IntentionState()
    turn = assemble(_snapshot(), sess)
    assert turn.direction.hoard_readable is True
    assert isinstance(turn.direction.hoard, frozenset)


def test_d1_mutation_probe_projection_failure_conservative_domain():
    """变异探针(D1 验收判据):hoard_target_set 抛错 → 消费域 = 保守域。

    静默退空集 = 锁线局囤货方向消失一帧、买侧按无方向放行——本锁钉住
    「投影失败」与「真无目标」表示分离(hoard_readable 位)。
    """
    import sr_od.application.currency_war.kernel.cw_intention as cw_intention_mod

    sess = StrategySession()
    sess.v3_intention = IntentionState()
    orig = cw_intention_mod.hoard_target_set

    def _boom(_state, _ist):
        raise RuntimeError('注入:投影失败')

    try:
        cw_intention_mod.hoard_target_set = _boom
        turn = assemble(_snapshot(), sess)
    finally:
        cw_intention_mod.hoard_target_set = orig
    d = turn.direction
    assert d.hoard_readable is False          # 失败帧显式暴露
    full = frozenset({'任意件A', '任意件B'})
    assert hoard_consumer_domain(d, full) == full     # 保守域,非空集放行
    ok = replace(d, hoard_readable=True)
    assert hoard_consumer_domain(ok, full) == ok.hoard  # 正常帧走目标集


# ----------------------------------------------------- D2 缺供给保守侧
# (原 test_d2_missing_supply_falls_conservative 已并入
#  test_cw_w620_migration_b1::test_committed_from_semantics——缺供给
#  保守侧为其分支 1,committed_authority 直调两形态已随迁。重复构成
#  删并理由(README 纪律 8)。)


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
    drive_intention(st, sess)
    assert sess.v3_intention_key == (1, 2)
    ev1 = sess.v3_intention.last_event
    drive_intention(st, sess)                     # 同轮重入:不重复驱动
    assert sess.v3_intention_key == (1, 2)
    assert sess.v3_intention.last_event == ev1
    drive_intention(_state(plane=1, round_num=3), sess)   # 跨轮:推进
    assert sess.v3_intention_key == (1, 3)


def test_p6_registry_injection_reaches_state_machine():
    """P6 注入分歧探针:注入臂与缺省臂必须出现受控分歧,无分歧 = 注入链断。

    旋钮 = line_env_lock_min_round(环境判据观察期):调大 = 判据本轮不辖
    → 对抗环境帧缺省臂缓锁、注入臂落锁——两臂 ist 分歧即注入链可达证。
    【夹具演进(经济冻结批)】原 plane=2 unlocked 帧:旧形态缺省臂保持
    unlocked;现 P2 unlocked 帧被强制 assignment 移交锁接管(目标不空窗
    语义,test_cw_economic_freeze.py ①组),与旋钮无关 → 不再承载分歧。
    改用 weak 帧(撤销机器在册态,移交不辖,「直至新信号」语义保留)。
    """
    from sr_od.application.currency_war.kernel.cw_intention import update_intention
    st = _state(plane=2, round_num=1)   # P2:comp 锁定通道(P1 配方锁区不锁 comp)
    st.enemy_affixes = ['净化身心']            # 对抗词缀(万敌强环境不命中)
    st.shop = [SimpleNamespace(name='万敌')]   # ③核心卡信号可见
    reg_def = _REG
    reg_inj = replace(_REG, line_env_lock_min_round=99)
    ist_def = update_intention(st, IntentionState(phase='weak', weak_comp='万敌单C'),
                               None, registry=reg_def)
    ist_inj = update_intention(st, IntentionState(phase='weak', weak_comp='万敌单C'),
                               None, registry=reg_inj)
    assert ist_def.locked_comp == ''            # 缺省臂:环境判据缓锁(weak 保持)
    assert ist_inj.locked_comp != ''            # 注入臂:判据不辖 → 落锁


def test_p4_ist_zero_residue_across_matches():
    """P4:跨局 ist 零残留——每局新建 StrategySession,ist/驱动键从零开始。"""
    sess = StrategySession()
    drive_intention(_state(), sess)
    assert sess.v3_intention is not None and sess.v3_intention.evicted == set()
    fresh = StrategySession()   # 新局(构造性重置)
    assert fresh.v3_intention is None
    assert fresh.v3_intention_key is None


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
    sess.target_comp = _JU23_COMP
    return sess


def test_ju23_supply_identity_gstar_and_s_reserve_boundary():
    """息线供给恒等(局23 帧):g*==50 且 s_reserve 供给非退化。

    重推导(14号稿 §3.4/N2 收口:线内件压库域排除后,M6 端到端对拍
    载体「线成员件独辖」退役——线内副本买入归义务全链,§7.3 owned
    观测面收口):s_reserve 边界改判据层直锁——stockpile_buy 金约束
    (gold−cost ≥ s_reserve):53 金/4 费 → 49<50 拒('s_reserve');
    54 金 → 50≥50 过。两断言合取即 s_reserve==50(下界由拒、上界由过),
    供给恒等式不因实现细节漂移。
    """
    from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.stockpile import (
        stockpile_buy,
    )
    assert saturation_line(cap_resolved_of_session(StrategySession())) == 50
    ok_r, key_r = stockpile_buy(53, 50, 9, 4, 1, frozenset({4}))
    assert ok_r is False and key_r == 's_reserve'
    ok_a, _ = stockpile_buy(54, 50, 9, 4, 1, frozenset({4}))
    assert ok_a is True


def test_ju23_stock_match_buys_and_empty_shop_close_discernible():
    """不死守可辨收敛(局23 帧):店空显式收店 + 压库买判据直锁。

    店空帧必须以 CloseShop 终结(全函数契约,禁静默死守),且带可辨
    计数键:shop_visit_idle_gold(带金零动作帧)+ shop_r1_no_chaseable_
    member(息账无追件、R1 关闭)——判读者从计数即知「为何不动」,
    而非空转或 None。压库买资格本体(档匹配 + 1★ 全退 + 金约束)判据层
    直锁(线内件排除后的载体迁移,见上锁重推导注)。
    """
    from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.stockpile import (
        stockpile_buy,
    )
    sess = _ju23_session()
    act = decide_shop_action(_ju23_frame(100, []), sess,
                             SimpleNamespace(ev_arm='full'))
    # gold=100 为必花域帧(20 号稿 §3.1-L3):店空无 L1/L2 对象 ⇒ 分层
    # 末位 L3 升级消费(LevelUpShop),分键语义保留可辨。
    assert isinstance(act, LevelUpShop)
    assert act.auth_basis == 'm3_batch:must_spend'
    assert sess.cw4_counters.get('shop_visit_idle_gold') == 1
    assert sess.cw4_counters.get('shop_r1_no_chaseable_member') == 1
    ok, _ = stockpile_buy(100, 0, 9, 2, 1, frozenset({2}))
    assert ok is True


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


def test_ju23_liquid_refund_shifts_s_reserve_down():
    """活期退金投影进 s_reserve(P56):bench 有 2 费活期件 ⇒ 线降至 48。

    重推导(线内件压库排除,载体迁移同上锁):边界改判据层直锁——
    51 金买 4 费件后 47 < 48 拒、52 金买后 48 ≥ 48 过——边界随活期
    退金逐金位移,钉死 s_reserve 是「可变现息线下界」而非静态 g*。
    """
    from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.stockpile import (
        stockpile_buy,
    )
    ok_r, key_r = stockpile_buy(51, 48, 9, 4, 1, frozenset({4}))
    assert ok_r is False and key_r == 's_reserve'
    ok_a, _ = stockpile_buy(52, 48, 9, 4, 1, frozenset({4}))
    assert ok_a is True


def test_ju23_full_surface_gold_never_breaks_interest_line():
    """金位不破息线(端到端复合):0-100 金全决策面逐帧走真函数。

    每个起始金位完整走一次店内访问(动作后真值回写再判,ADR-0517
    §8.1 口径):任一 BuyCard/RefreshShop 花后金 ≥ s_reserve(本帧形状
    = 50);息线下(≤50)整访问零支出(无误清);每访问都以 CloseShop
    收束且有界迭代(无死守环)。
    """
    cfg = SimpleNamespace(ev_arm='full')
    for gold0 in range(0, 101):
        st = _ju23_frame(gold0, [_sc('花火')])
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
    """全局节点序号(plane*9 + round 的简化;与 horizon 的 t 同构)。"""
    return (min(plane, 3) - 1) * 9 + max(1, min(round_num, 9))


def _old_ready(sig: CommitSignals, t: int = 0) -> bool:
    """退役版 ready 判定:领先线信号分 ≥ 阈值 且 t ≥ 轮门。"""
    if t and t < _COMMIT_MIN_T:
        return False
    lead = sig.leader()
    return lead is not None and lead[1] >= _COMMIT_SIGNAL_THRESHOLD


def _old_committed(state: GameState, session: StrategySession) -> bool:
    """旧语义复刻(update_target 判定式;对拍基准,非生产路径)。

    committed = plane≥2 ∨ (signals.ready ∧ (可切换 ∨ target==领先线));
    ready/t_of 消费退役前复刻(见上常量注)。
    """
    if state.plane >= 2:
        return True
    sig = getattr(session, 'commit_signals', None)
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
    s3.commit_signals = CommitSignals()
    s3.commit_signals.scores = {'万敌燃血': 99.0}
    frames.append((_state(plane=1, round_num=8), s3, 'takeover_zone_only_old'))
    # 帧4:ist 已锁 → 双 True
    s4 = StrategySession()
    s4.v3_intention = IntentionState(phase='locked', locked_comp='万敌燃血')
    s4.commit_signals = CommitSignals()
    s4.commit_signals.scores = {'万敌燃血': 99.0}
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
