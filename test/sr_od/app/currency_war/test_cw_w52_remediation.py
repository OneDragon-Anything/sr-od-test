"""W52 批锁:「拒绝→补裁决」通用回连机制 + S3/S4/S5 + N1 前置修复。

载体:决策框架 v2 层4 回连(§1-§5 设计稿 W52 r4 + 任务书 AD9 裁决)。
全部单帧锁(构造 GameState → 断言 decide_prep/arbitrate 输出);
**bench 构造按槽位模型**(定长 9,None=空槽——ADR-0316)。

逐链两向锁 + 防环边界锁 + N1 前置锁 + expect 代际锁 + 标签链锁 +
遥测锚点锁;检查网 decision_v2_remedy_loop(连续放弃轮≥3)另行锁。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_intention import HoardTarget
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    DeployMove,
    GameState,
    LevelUp,
    RefreshShop,
    SellBench,
    ShopCard,
    SwapDeploy,
    bench_occupied,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.arbiter import (
    arbitrate,
)
from sr_od.application.currency_war.decision_v2.candidates import (
    Candidate,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

_REG = DEFAULT_REGISTRY


def _card(name: str, faction: str = '公司', cost: int = 2) -> ShopCard:
    return ShopCard(x=0, name=name, faction=faction, cost=cost)


def _bench(name: str, faction: str = '公司', slot: int = 0,
           star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 4, 'gold': 40, 'level': 5,
            'board': {}, 'bench': [], 'shop': [], 'hp': 80,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _sess(**kw) -> StrategySession:
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def _locked_sess(**kw) -> StrategySession:
    """意向锁定 session(锁定套=列车同行;hoard=意向线采购集子样)。"""
    from sr_od.application.currency_war.kernel.cw_intention import IntentionState
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '列车同行'   # COMP_LIBRARY v2 套名(姬子列车家族)
    s = _sess(v3_intention=ist, **kw)
    s.v3_hoard = HoardTarget(
        frozenset({'姬子·启行', '三月七', '花火', '瓦尔特'}),
        frozenset(), 'locked')
    s.v3_core_names = {'姬子·启行'}
    return s


# --- S3 同星豁免(H3 口径;§2/§7) ----------------------------------------------


def _full_bench_with(names_stars: list) -> GameState:
    """9/9 满员 bench(槽位表;names_stars=[(名, 星), ...] 恰好 9 件)。"""
    assert len(names_stars) == 9
    st = _state(bench=[_bench(n, slot=i, star=s)
                       for i, (n, s) in enumerate(names_stars)])
    assert bench_occupied(st.bench) == 9
    return st


def test_s3_merge_buy_exempt_at_full_bench() -> None:
    """S3 正向(H3 口径):bench 9/9 + 同名**同 1★ 已 2 份** + 店内第 3 张
    1★ → 买被采纳(容量豁免;合并净 −1,不占新槽)。"""
    sess = _sess()
    sess.v2_round_key = (1, 4)
    st = _full_bench_with([('X', 1), ('X', 1)] + [(f'C{i}', 1) for i in range(7)])
    st.shop = [_card('X', cost=1)]
    scored = [(Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                         merge=True, source='test'), 5.0, {})]
    res = arbitrate(scored, st, sess, _REG)
    assert [r['accepted'] for r in res.log] == [True], (
        f'9/9+同 1★ 已 2 份+第 3 张 1★ → 合并买入应容量豁免(净−1):'
        f'{res.log[0]["reject"] if res.log else "无 log"}')


def test_s3_weighted2_star2_not_merge_still_rejected() -> None:
    """S3 反例 A:bench 9/9 + **1 个 2★(加权2)** + 店内第 3 张 1★ →
    仍拒(同星计数=1,不合成交净+1——旧加权判据的误标例)。"""
    sess = _sess()
    sess.v2_round_key = (1, 4)
    st = _full_bench_with([('X', 2)] + [(f'C{i}', 1) for i in range(8)])
    st.shop = [_card('X', cost=1)]
    scored = [(Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                         merge=False, source='test'), 5.0, {})]
    res = arbitrate(scored, st, sess, _REG)
    assert res.log[0]['accepted'] is False, \
        '1 个 2★(加权2)+第 3 张 1★ 不合成(同星=1)→ 满员仍拒'
    assert 'bench 满' in (res.log[0]['reject'] or '')


def test_s3_non_merge_buy_still_rejected_at_full() -> None:
    """S3 反例 B:bench 9/9 + 非 merge 买 → 仍拒(容量不豁免普通买)。"""
    sess = _sess()
    sess.v2_round_key = (1, 4)
    st = _full_bench_with([(f'C{i}', 1) for i in range(9)])
    st.shop = [_card('散件', cost=1)]
    scored = [(Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                         merge=False, source='test'), 5.0, {})]
    res = arbitrate(scored, st, sess, _REG)
    assert res.log[0]['accepted'] is False


def test_s3_will_merge_generation_mirror_same_star() -> None:
    """S3 生成侧镜像(candidates.will_merge):2× 同 1★ + 店第 3 张 1★ →
    merge=True;1× 2★ + 店第 3 张 1★ → merge=False(旧加权判据误标例)。"""
    from sr_od.application.currency_war.decision_v2.candidates import (
        generate_candidates,
    )
    # 正向:同 1★ 已 2 份
    st1 = _state(gold=60, bench=[_bench('X', slot=0, star=1),
                                 _bench('X', slot=1, star=1),
                                 _bench('C0', slot=2)],
                 shop=[_card('X', cost=1)])
    sess = _sess()
    sess.v2_round_key = (1, 4)
    m1 = [c for c in generate_candidates(st1, sess, _REG)
          if isinstance(c.action, BuyCard) and c.action.card.name == 'X']
    assert m1 and m1[0].merge, '同 1★ 已 2 份+第 3 张 1★ → merge 候选'
    # 反例:1× 2★(加权2)不是同星 2 份
    st2 = _state(gold=60, bench=[_bench('X', slot=0, star=2),
                                 _bench('C0', slot=1)],
                 shop=[_card('X', cost=1)])
    m2 = [c for c in generate_candidates(st2, sess, _REG)
          if isinstance(c.action, BuyCard) and c.action.card.name == 'X']
    assert m2 and not m2[0].merge, \
        '1× 2★(加权2)不构成同 1★ 2 份 → 非 merge(旧判据误标)'


def test_s3_merge_buy_simulates_net_minus1_at_full() -> None:
    """S3 执行侧:9/9 满员合并买入 simulate 后 bench 占用 8(净 −1),
    新卡不占槽(合成载体留原槽);非合并买在满员时仍 no-op。"""
    from sr_od.application.currency_war.kernel.cw_state import simulate
    sess = _sess()
    sess.v2_round_key = (1, 4)
    st = _full_bench_with([('X', 1), ('X', 1)] + [(f'C{i}', 1) for i in range(7)])
    st.gold = 60
    st.shop = [_card('X', cost=1)]
    out = simulate(st, BuyCard(st.shop[0]))
    assert bench_occupied(out.bench) == 8, \
        f'合并买入净 −1(期望 8,实得 {bench_occupied(out.bench)})'
    x2 = [b for b in out.bench if b is not None and b.char_id == 'X']
    assert len(x2) == 1 and x2[0].star == 2
    assert out.gold == 60 - 1
    # 非合并买满员 no-op
    st2 = _full_bench_with([(f'C{i}', 1) for i in range(9)])
    st2.gold = 60
    st2.shop = [_card('散件', cost=1)]
    out2 = simulate(st2, BuyCard(st2.shop[0]))
    assert out2.gold == 60 and bench_occupied(out2.bench) == 9


# --- S4 上阵补偿(H2 口径;§1.4/§7) -------------------------------------------


def _s4_state(round_num: int = 4, gold: int = 70, level: int = 5,
              xp: tuple | None = (0, 20), bench_units: list | None = None,
              deployed_units: list | None = None) -> GameState:
    """S4 场景状态:cap 满(5/5)+bench 有目标件(姬子·启行)+金足。"""
    if deployed_units is None:
        deployed_units = ['卡芙卡', '千冶·刃', '绯英', '娜塔莎', '阿格莱雅']
    if bench_units is None:
        bench_units = ['姬子·启行']
    return _state(round_num=round_num, gold=gold, hp=80, level=level,
                  xp_progress=xp,
                  bench=[_bench(n, faction='公司', slot=i)
                         for i, n in enumerate(bench_units)],
                  shop=[_card('占位', cost=1)],
                  deployed=[_bench(n, faction='公司', slot=i)
                            for i, n in enumerate(deployed_units)],
                  board={})


def test_s4_levelup_group_emitted_when_gold_covers_total() -> None:
    """S4 正向(H2):cap 满+bench 有 target_core 件+金足(≥n×单击总价)
    非 boss 轮 → **n 个 LevelUp** 追加(n=ceil(剩余XP/XP_PER_BUY))。"""
    from sr_od.application.currency_war.kernel.cw_state import LevelUp
    sess = _locked_sess()
    sess.v2_round_key = (1, 4)
    # level 5, xp (0,20) → 剩余 20 → n=5;总价 5×4=20;金 70-20=50 过息门
    st = _s4_state()
    cand = Candidate(action=DeployMove(bench_idx=0, to_row='back',
                                       faction='列车同行'),
                     tag='deploy', source='test')
    res = arbitrate([(cand, 5.0, {})], st, sess, _REG)
    assert res.rejections and res.rejections[0].reason.resource == 'slot'
    lv = [a for a in res.actions if isinstance(a, LevelUp)]
    assert len(lv) == 5, \
        f'n=ceil(20/4)=5 个 LevelUp 应追加(实得 {len(lv)}):{res.actions}'
    assert all(a.cost == 4 for a in lv)
    assert not any(isinstance(a, DeployMove) for a in res.actions), \
        '受益 DeployMove 本轮仍拒(升级解的是下轮)'


def test_s4_swap_when_gold_short() -> None:
    """S4 ②臂:金不足总价 → LevelUp 臂不发(可负担性入口门拒),改
    SwapDeploy(换下最弱非核心);SwapDeploy 带 expect 代际校验字段。

    (旧「boss 轮也走 ②」断言随 ADR-0410 过期:boss 升级禁令删除,
    boss 轮 LevelUp 改由 EV 总账裁决——合法面见 test_cw_w255 锁。)"""
    # 金 12 只够部分点击:① 臂 EV 可负担性不过(按 n×总价口径)→ ②
    sess = _locked_sess()
    sess.v2_round_key = (1, 8)
    st = _s4_state(round_num=8, gold=12)
    cand = Candidate(action=DeployMove(bench_idx=0, to_row='back',
                                       faction='列车同行'),
                     tag='deploy', source='test')
    res = arbitrate([(cand, 5.0, {})], st, sess, _REG)
    swaps = [a for a in res.actions if isinstance(a, SwapDeploy)]
    assert len(swaps) == 1, f'金不足总价 → SwapDeploy(实得 {res.actions})'
    sw = swaps[0]
    assert sw.bench_idx == 0 and sw.expect_bench == '姬子·启行'
    assert sw.expect_deployed in ('卡芙卡', '千冶·刃', '绯英', '娜塔莎',
                                  '阿格莱雅'), \
        '换下最弱非核心(不动 target_cores/引擎件)'


def test_s4_noop_when_bench_weaker_than_deployed() -> None:
    """S4 反例:cap 满但 bench 件弱于全场 deployed → 无动作(换上不优
    不换)。ADR-0410 适配:①臂 boss 禁令删后,EV 总账人口位需
    「bench 有目标件」——本反例 bench=卡芙卡(非列车同行采购集)→
    ① 臂自然不走(非 boss 语义),② 臂「换上不优」判据为行为锁本体。
    故基座移到非 boss 轮,断言不变。"""
    sess = _locked_sess()
    sess.v2_round_key = (1, 5)
    # bench 件=卡芙卡(2费 1星);deployed 全 2★ 高费 → 换上不优
    # ADR-0410 适配:金 70 时 EV 总账臂②(DP 说升+平台未破)会发
    # 升级组——「换上不优 → 无动作」锁的纯度要 ② 臂也不开,压到金不足
    # 平台的金位(12,「换上不优」判据不依赖金位)。
    st = _s4_state(round_num=5, gold=12, bench_units=['卡芙卡'],
                   deployed_units=['丹恒·饮月', '千冶·刃', '绯英',
                                   '娜塔莎', '阿格莱雅'])
    st.deployed = [BenchChar(slot=i, char_id=n, faction='公司', star=2)
                   for i, n in enumerate(['丹恒·饮月', '千冶·刃', '绯英',
                                          '娜塔莎', '阿格莱雅'])]
    cand = Candidate(action=DeployMove(bench_idx=0, to_row='back',
                                       faction='公司'),
                     tag='deploy', source='test')
    res = arbitrate([(cand, 5.0, {})], st, sess, _REG)
    assert res.rejections
    assert not any(isinstance(a, (SwapDeploy, LevelUp))
                   for a in res.actions), '换上不优 → 无补偿动作'


def test_s4_partial_gold_group_abandoned() -> None:
    """S4 事务性反例:金只够部分点击(<n×总价)→ 整组不发(arbiter 逐
    动作重验失败 → abandon,零 LevelUp 追加)。"""
    from sr_od.application.currency_war.kernel.cw_state import LevelUp
    sess = _locked_sess()
    sess.v2_round_key = (1, 4)
    sess.v2_ever_full_interest = True   # 过补偿器息门(ever_full)
    # gold 12, n=5 总价 20 → 第 3 击后金 4 < 地板(12%10=2) → 整组放弃
    st = _s4_state(gold=12, xp=(0, 20))
    cand = Candidate(action=DeployMove(bench_idx=0, to_row='back',
                                       faction='列车同行'),
                     tag='deploy', source='test')
    res = arbitrate([(cand, 5.0, {})], st, sess, _REG)
    assert not any(isinstance(a, LevelUp) for a in res.actions), \
        '金只够部分点击 → 整组不发(事务性)'
    assert res.remediation_log, '应有补偿日志(abandon 记录)'


# --- S2 报警 refresh 辖域(§2/§7) ---------------------------------------------


def test_s2_alarm_refresh_compensated_when_authorized() -> None:
    """S2 正向:报警升级态(allow_refresh_in_war 授权)+refresh 被金拒+
    可卖弱件 → 产出 [Sell≥1, RefreshShop](不为常态刷新借钱——仅报警
    辖域);非报警态 refresh 金拒 → 无补偿。"""
    from sr_od.application.currency_war.decision_v2.discipline import (
        DisciplineView,
    )
    # 报警升级态:war 地板 30,金 25,refresh 2 费 → 缺 7;可卖件用
    # **各 1 份**的散件(加权副本≥2 的 3合1 素材不可卖,AD9-2-3;
    # ADR-0375 适配:娜塔莎=贝洛伯格希儿系贡献件唯一时卖禁,
    # 换非希儿系 3 费件黄泉凑足缺金)
    sellable_names = ['卡芙卡', '千冶·刃', '绯英', '黄泉', '阿格莱雅']
    sess = _locked_sess()
    sess.v3_mode = 'war'
    sess.v2_round_key = (1, 4)
    st = _state(round_num=4, gold=25, hp=80,
                bench=[_bench(n, faction='公司', slot=i)
                       for i, n in enumerate(sellable_names)],
                shop=[_card('占位', cost=1)], board={})
    disc = DisciplineView(coverage='blood_alarm', mode='war',
                          allow_refresh_in_war=True)
    cand = Candidate(action=RefreshShop(cost=2), tag='refresh',
                     source='test')
    res = arbitrate([(cand, 2.0, {})], st, sess, _REG, disc_view=disc)
    sells = [a for a in res.actions if isinstance(a, SellBench)]
    refs = [a for a in res.actions if isinstance(a, RefreshShop)]
    assert sells and refs, \
        f'报警 refresh 金拒 → [Sell, RefreshShop]:{res.actions}'
    assert res.rejections[0].reason.resource == 'gold'
    for s in sells:
        assert st.bench[s.bench_idx].char_id in sess.v2_round_sold
    # 非报警态(无授权)→ 无补偿
    sess2 = _locked_sess()
    sess2.v3_mode = 'war'
    sess2.v2_round_key = (1, 4)
    st2 = _state(round_num=4, gold=25, hp=80,
                 bench=[_bench(n, faction='公司', slot=i)
                        for i, n in enumerate(sellable_names)],
                 shop=[_card('占位', cost=1)], board={})
    disc2 = DisciplineView(coverage='mode', mode='war',
                           allow_refresh_in_war=False)
    res2 = arbitrate([(cand, 2.0, {})], st2, sess2, _REG,
                     disc_view=disc2)
    assert not any(isinstance(a, (SellBench, RefreshShop))
                   for a in res2.actions), \
        '非报警态 refresh 金拒 → 无补偿(不为常态刷新借钱)'


def test_s2_25_40_two_lines_documented() -> None:
    """S2 顺手:25/40 两档并存口径已成文——应急清仓线(25)与报警
    降档线(40)分别存在于 registry/discipline 常量(两线并存不是
    二选一;补偿机制只消费资源门槛事件)。"""
    from sr_od.application.currency_war.decision_v2.discipline import (
        BLOOD_MARGIN_LOW_HP,
    )
    assert _REG.emergency_hp == 25
    assert BLOOD_MARGIN_LOW_HP == 40
    import inspect

    import sr_od.application.currency_war.decision_v2.discipline as m
    src = inspect.getsource(m)
    assert '25/40 两档并存口径' in src, '25/40 docstring 应成文(防口径漂移)'


# --- S5 统一卖件弱序(§4/§7;ADR-0327)-----------------------------------------


def test_s5_key_orders_low_cost_net0_first() -> None:
    """S5 键序:同状态两可卖件(单 1★ 低费 vs 单 1★ 高费)→ 低费
    (净0/再遇代价小)先卖(键序断言);2★/2 份素材件 → 键 None 不入卖序
    (AD9-2-3 守卫面)。"""
    from sr_od.application.currency_war.decision_v2.discipline import (
        sell_priority_key,
    )
    sess = _sess()
    sess.v2_round_key = (1, 4)
    # 黑塔(1费)vs 黄泉(3费)——均单份 1★ 可卖(后三月七/瓦尔特
    # 为 TT 列车件另有唯一引擎卖禁;后娜塔莎为希儿系贡献件另有
    # 卖禁,通用键序锁改用非 TT 非希儿系件)
    st = _state(gold=60, bench=[_bench('黑塔', faction='公司', slot=0),
                                _bench('黄泉', faction='公司', slot=1)],
                board={})
    k_low = sell_priority_key(st.bench[0], st, sess, None, _REG)
    k_high = sell_priority_key(st.bench[1], st, sess, None, _REG)
    assert k_low is not None and k_high is not None
    assert k_low < k_high, \
        f'低费件应先卖(键 {k_low} < {k_high}):{st.bench[0].char_id} 先'
    # 守卫面:2★(加权 2)/同 1★ 两 份/注册表外 → None
    st2 = _state(gold=60, bench=[_bench('瓦尔特', slot=0, star=2),
                                 _bench('卡芙卡', slot=1),
                                 _bench('卡芙卡', slot=2),
                                 _bench('囤件甲', slot=3)], board={})
    assert sell_priority_key(st2.bench[0], st2, sess, None, _REG) is None, \
        '2★(加权副本 2)=3合1 进行中素材 → None'
    assert sell_priority_key(st2.bench[1], st2, sess, None, _REG) is None, \
        '同 1★ 两 份(加权 2)→ None'
    assert sell_priority_key(st2.bench[3], st2, sess, None, _REG) is None, \
        '注册表外(未识别)→ None'


def test_s5_ad9_2_3_compensation_not_sell_merge_material() -> None:
    """AD9-2-3(升格必改):加权副本≥2 的件不可卖——补偿器也不得拆
    3合1 进行中素材(唯一可卖=2 份素材时整组放弃)。"""
    from dataclasses import replace
    sess = _locked_sess()
    sess.v3_mode = 'war'
    sess.v2_round_key = (1, 4)
    # 卡芙卡×2(加权 2)=进行中素材;金不足买 4 费 carry
    st = _state(round_num=4, gold=13, hp=80,
                bench=[_bench('卡芙卡', faction='公司', slot=0),
                       _bench('卡芙卡', faction='公司', slot=1)],
                shop=[_card('姬子·启行', cost=4)],
                deployed=[_bench(f'D{i}', faction='公司', slot=i)
                          for i in range(5)],
                board={})
    cand = Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                     source='test')
    res = arbitrate([(cand, 5.0, {})], st, sess,
                    replace(_REG, war_floor=10))
    assert res.rejections
    assert not any(isinstance(a, SellBench) for a in res.actions), \
        '2 份素材(加权 2)不得被补偿卖出(AD9-2-3)'
    assert sess.v2_round_sold == set()


# --- expect 代际锁(§1.7/ADR-0326 r4;AD9-1-1)--------------------------------


def test_expect_remediation_sells_carry_expect_field() -> None:
    """expect 正向:remediation 发射的 SellBench 带 expect 字段且与
    执行态一致 → 正常执行(simulate 后槽清空、金入账)。"""
    from dataclasses import replace

    from sr_od.application.currency_war.kernel.cw_state import simulate
    sess = _locked_sess()
    sess.v3_mode = 'war'
    sess.v2_round_key = (1, 4)
    st = _state(round_num=4, gold=13, hp=80,
                bench=[_bench('卡芙卡', faction='公司', slot=0),
                       _bench('千冶·刃', faction='公司', slot=1)],
                shop=[_card('姬子·启行', cost=4)],
                deployed=[_bench(f'D{i}', faction='公司', slot=i)
                          for i in range(5)],
                board={})
    cand = Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                     source='test')
    res = arbitrate([(cand, 5.0, {})], st, sess,
                    replace(_REG, war_floor=10))
    sells = [a for a in res.actions if isinstance(a, SellBench)]
    assert sells, '应有补偿卖件'
    for s in sells:
        assert s.expect == st.bench[s.bench_idx].char_id, \
            f'补偿 SellBench 必填 expect(来自 state 快照):{s}'
    # 正常执行:simulate 逐动作(expect 与槽内名一致 → 卖成;金先增后
    # 扣,买入落首个空槽=刚卖出的槽)
    wk = st
    for a in res.actions:
        wk = simulate(wk, a)
    _income = sum((s.income or 0) for s in sells)
    assert wk.gold == st.gold + _income - 4, \
        f'卖成+买入扣金({wk.gold} vs {st.gold}+{_income}-4)'
    assert any(b is not None and b.char_id == '姬子·启行'
               for b in wk.bench), '买入件应落 bench(expect 一致 → 正常执行)'


def test_expect_mismatch_stale_proposal_rejected() -> None:
    """expect 反向:手工构造 expect 与 state 槽内名不符的 SellBench →
    断言 stale_proposal 整动作拒(防线真触发,非恒放行;simulate 与
    mutate 两执行面一致)。"""
    from sr_od.application.currency_war.kernel.cw_state import (
        mutate_bench_deployed,
        simulate,
    )
    st = _state(gold=10, bench=[_bench('卡芙卡', faction='公司', slot=0)])
    stale = SellBench(bench_idx=0, income=2, expect='瓦尔特')   # 不符
    out = simulate(st, stale)
    assert out.gold == 10, 'expect 不符 → no-op(不卖)'
    assert out.bench[0] is not None and out.bench[0].char_id == '卡芙卡'
    assert any('stale_proposal' in (e.get('reason') or '')
               for e in out.action_log), \
        f'应记录 stale_proposal 拒绝:{out.action_log}'
    # mutate 面同源
    bench = [_bench('卡芙卡', faction='公司', slot=0)]
    deployed: list = []
    mutate_bench_deployed(bench, deployed, stale)
    assert bench[0] is not None and bench[0].char_id == '卡芙卡', \
        'mutate 面 expect 不符 → no-op'
    # 对照:expect 一致 → 正常卖
    ok = SellBench(bench_idx=0, income=2, expect='卡芙卡')
    out2 = simulate(st, ok)
    assert out2.bench[0] is None and out2.gold == 10 + 2


# --- 检查网 decision_v2_remedy_loop(§1.5-3;变异自检探针)----------------------


def _row(round_num: int, abandoned: int = 0, d2: bool = True) -> dict:
    """ledger 行构造(简化:只带检查需要的字段)。"""
    return {
        'round_num': round_num,
        'actions': ([{'__type__': 'SellBench', 'reason': 'd2_x',
                      'bench_idx': 0}]
                    if d2 else []),
        'sim': {'remedy_abandoned': abandoned},
    }


def test_remedy_loop_fires_on_consecutive_abandons() -> None:
    """检查项正向:连续 3 轮补偿放弃 → 报警(设计容量不足信号)。"""
    from sr_od.application.currency_war.sim.cw_sim_checks import (
        check_decision_v2_remedy_loop,
    )
    r = check_decision_v2_remedy_loop([[
        _row(1), _row(2, 1), _row(3, 1), _row(4, 1), _row(5),
    ]])
    assert r['violations'] > 0, f'连续 3 轮放弃应报警:{r}'
    # 边界:恰好 2 轮 → 不报
    r2 = check_decision_v2_remedy_loop([[
        _row(1), _row(2, 1), _row(3, 1), _row(4),
    ]])
    assert r2['violations'] == 0, f'2 轮放弃不构成连续 3 轮:{r2}'


def test_remedy_loop_clean_when_no_abandon() -> None:
    """检查项反例:无放弃/零星放弃 → 0 违规(非安慰剂:构造有放弃必报
    的对照见上;本锁钉「零放弃恒绿」)。"""
    from sr_od.application.currency_war.sim.cw_sim_checks import (
        check_decision_v2_remedy_loop,
    )
    r = check_decision_v2_remedy_loop([[
        _row(1), _row(2, 1), _row(3), _row(4), _row(5, 1), _row(6),
    ]])
    assert r['violations'] == 0
    assert r['d2_batch'] is True


def test_remedy_loop_d2_batch_scoped() -> None:
    """检查项辖域:非 d2 批次(无 d2_ 前缀 reason 动作)不辖——即便
    账本有 abandon 形状也不报(补偿趟只存在于 decision_v2 载体)。"""
    from sr_od.application.currency_war.sim.cw_sim_checks import (
        check_decision_v2_remedy_loop,
    )
    r = check_decision_v2_remedy_loop([[
        _row(1, d2=False), _row(2, 1, d2=False), _row(3, 1, d2=False),
        _row(4, 1, d2=False),
    ]])
    assert r['violations'] == 0, f'非 d2 批次不辖:{r}'
    assert r['d2_batch'] is False


# --- 防环/互斥/守卫面(§1.5/§7)-----------------------------------------------


def test_remedy_single_pass_per_round() -> None:
    """单趟(§1.5-1):一轮内第二次资源拒 → 无补偿(v2_remedy_used 轮键
    防环;arbitrate 补偿趟不重入不循环)。"""
    from dataclasses import replace
    sess = _locked_sess()
    sess.v3_mode = 'war'
    sess.v2_round_key = (1, 4)
    reg10 = replace(_REG, war_floor=10)
    # 第一次仲裁:金不足 buy → 补偿卖出(绯英=非 TT 件,后 TT
    # 唯一引擎件不进补偿卖序,通用锁用非 TT 件)
    st1 = _state(round_num=4, gold=13, hp=80,
                 bench=[_bench('绯英', faction='公司', slot=0)],
                 shop=[_card('姬子·启行', cost=4)],
                 deployed=[_bench(f'D{i}', faction='公司', slot=i)
                           for i in range(5)], board={})
    res1 = arbitrate([(Candidate(action=BuyCard(st1.shop[0]),
                                 tag='line_carry', source='test'),
                       5.0, {})], st1, sess, reg10)
    assert res1.remediation_log, '第一次应有补偿'
    assert sess.v2_remedy_used is True
    # 同轮第二次仲裁(另一金不足买)→ v2_remedy_used 拦 → 无补偿
    st2 = _state(round_num=4, gold=13, hp=80,
                 bench=[_bench('千冶·刃', faction='公司', slot=0)],
                 shop=[_card('花火', cost=4)],
                 deployed=[_bench(f'D{i}', faction='公司', slot=i)
                           for i in range(5)], board={})
    res2 = arbitrate([(Candidate(action=BuyCard(st2.shop[0]),
                                 tag='line_carry', source='test'),
                       5.0, {})], st2, sess, reg10)
    assert res2.rejections, '第二次仍有拒绝(捕获照常)'
    assert res2.remediation_log == [], \
        'v2_remedy_used 轮键:一轮至多一趟补偿(防环)'
    assert not any(isinstance(a, SellBench) for a in res2.actions)


def test_remedy_sold_not_rebought_same_round() -> None:
    """r408 对称臂:补偿卖出的件同轮再在店出现同名 → 买候选被
    same_round_mutex 拒(不回买——同一件卖了再买=振荡,结构禁止)。"""
    from dataclasses import replace
    sess = _locked_sess()
    sess.v3_mode = 'war'
    sess.v2_round_key = (1, 4)
    reg10 = replace(_REG, war_floor=10)
    st1 = _state(round_num=4, gold=13, hp=80,
                 bench=[_bench('绯英', faction='公司', slot=0)],
                 shop=[_card('姬子·启行', cost=4)],
                 deployed=[_bench(f'D{i}', faction='公司', slot=i)
                           for i in range(5)], board={})
    res1 = arbitrate([(Candidate(action=BuyCard(st1.shop[0]),
                                 tag='line_carry', source='test'),
                       5.0, {})], st1, sess, reg10)
    assert res1.remediation_log, '第一次应有补偿'
    assert '绯英' in sess.v2_round_sold, '补偿卖出应入已卖集'
    # 同轮店内又现绯英 → 买候选被 same_round_mutex 拒
    st2 = _state(round_num=4, gold=60, hp=80, bench=[],
                 shop=[_card('绯英', cost=2)],
                 deployed=[_bench(f'D{i}', faction='公司', slot=i)
                           for i in range(5)], board={})
    res2 = arbitrate([(Candidate(action=BuyCard(st2.shop[0]),
                                 tag='line_carry', source='test'),
                       5.0, {})], st2, sess, reg10)
    assert not any(isinstance(a, BuyCard) for a in res2.actions), \
        '同轮已卖的同名买候选应被 same_round_mutex 拒(振荡结构禁止)'
    rejects = [r['reject'] for r in res2.log if not r['accepted']]
    assert any('同轮已卖' in (r or '') for r in rejects), rejects


def test_prior_accepted_sell_no_compensation() -> None:
    """W56 攻击面 3(先采纳卖→金足→无补偿):同轮存在高正分卖候选
    且先于买被采纳 → 卖出回金后买候选直接通过(无拒绝事件)→
    无补偿动作(不与常规通道重复变现)。

    ADR-0347 构造适配:经济态地板=FORM_FLOOR(20,相位地板)——
    gold 取 22(卖回金 2 后买 4 费恰达 20 地板;无卖则 18<20 会拒,
    保住「卖先采纳→金足」的因果链)。"""
    from dataclasses import replace
    sess = _locked_sess()
    sess.v2_round_key = (1, 4)
    reg10 = replace(_REG, war_floor=10)
    st = _state(round_num=4, gold=22, hp=80,
                # ADR-0380 语义化适配:卡芙卡(DOT)换非 TT 件银枝
                # (cost 同 2,回金链不变;TT 唯一件卖出由 test_cw_w197 辖)
                bench=[_bench('银枝', faction='星间旅人', slot=0)],
                shop=[_card('姬子·启行', cost=4)],
                deployed=[_bench(f'D{i}', faction='公司', slot=i)
                          for i in range(5)], board={})
    buy_c = Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                      source='test')
    sell_c = Candidate(action=SellBench(bench_idx=0), tag='off_target',
                       source='test',
                       breakdown_hint={'name': '银枝'})
    res = arbitrate([(buy_c, 2.0, {}), (sell_c, 5.0, {})], st, sess,
                    reg10)
    assert any(isinstance(a, SellBench) for a in res.actions)
    assert any(isinstance(a, BuyCard) for a in res.actions), \
        '卖先采纳回金 → 买直接通过(不再金拒)'
    assert res.rejections == [], '无拒绝事件 → 无补偿'
    assert res.remediation_log == [], '先采纳卖→金足→无补偿'


def test_marginal_bond_guard_protects_recipe_parts() -> None:
    """r3(§0.6-①):过渡配方件(与 board 阵营凑羁绊)不进补偿卖序——
    bench 同时有配方件与纯垫层件 → 只卖垫层件;全部可卖件均配方件
    → 整组放弃(abandon 语义)。"""
    from dataclasses import replace
    # 混合:board 有仙舟;青雀(仙舟=配方件)挡,卡芙卡(垫层)可卖
    sess = _locked_sess()
    sess.v3_mode = 'war'
    sess.v2_round_key = (1, 4)
    st = _state(round_num=4, gold=13, hp=80,
                bench=[_bench('青雀', faction='仙舟', slot=0),
                       _bench('银枝', faction='公司', slot=1)],
                shop=[_card('姬子·启行', cost=4)],
                deployed=[_bench(f'D{i}', faction='仙舟', slot=i)
                          for i in range(5)],
                board={'仙舟': 5})
    res = arbitrate([(Candidate(action=BuyCard(st.shop[0]),
                                tag='line_carry', source='test'),
                      5.0, {})], st, sess, replace(_REG, war_floor=10))
    sells = [a for a in res.actions if isinstance(a, SellBench)]
    assert len(sells) == 1 and st.bench[sells[0].bench_idx].char_id \
        == '银枝', \
        f'只卖垫层件(配方件青雀不卖):{[s.bench_idx for s in sells]}'
    assert sess.v2_round_sold == {'银枝'}
    # 全配方件 → 整组放弃
    sess2 = _locked_sess()
    sess2.v3_mode = 'war'
    sess2.v2_round_key = (1, 4)
    st2 = _state(round_num=4, gold=13, hp=80,
                 bench=[_bench('青雀', faction='仙舟', slot=0),
                        _bench('丹恒·饮月', faction='仙舟', slot=1)],
                 shop=[_card('姬子·启行', cost=4)],
                 deployed=[_bench(f'D{i}', faction='仙舟', slot=i)
                           for i in range(5)],
                 board={'仙舟': 5})
    res2 = arbitrate([(Candidate(action=BuyCard(st2.shop[0]),
                                 tag='line_carry', source='test'),
                       5.0, {})], st2, sess2, replace(_REG, war_floor=10))
    assert not any(isinstance(a, SellBench) for a in res2.actions), \
        '全配方件 → 无可卖垫层 → 整组放弃(不拆配方)'


def test_buy_tag_chain_lock() -> None:
    """标签链锁(H1):锁定意向+cores 命中 → 'line_carry'(在
    remedy_buy_tags);v3_core_names 空窗 → 落点('carry_gate'/
    'line_opportunistic')均在 remedy_buy_tags 内(金补偿路径对两种
    标签结果都稳健——路径对标签裁决序改动免疫)。"""
    from sr_od.application.currency_war.decision_v2.candidates import (
        _buy_tag,
    )
    # 锁定+cores 命中
    sess = _locked_sess()
    st = _state(gold=60, bench=[], shop=[_card('姬子·启行', cost=3)])
    tag = _buy_tag(st.shop[0], st, sess, _REG)
    assert tag == 'line_carry'
    assert tag in _REG.remedy_buy_tags
    # 锁定+cores 命中+bench 满+r≤7 → 仍 'line_carry'(核心优先于
    # carry_gate 分支——§7 标签链锁的显式用例)
    st_full = _state(gold=60, round_num=4,
                     bench=[_bench(f'C{i}', slot=i) for i in range(9)],
                     shop=[_card('姬子·启行', cost=3)])
    tag_full = _buy_tag(st_full.shop[0], st_full, sess, _REG)
    assert tag_full == 'line_carry', \
        f'锁定+cores 命中时 bench 满不降级 carry_gate(核心优先):{tag_full}'
    # 空窗+bench 满+r≤7 → carry_gate
    sess2 = _sess()
    sess2.v3_hoard = HoardTarget(frozenset({'姬子·启行'}), frozenset(),
                                 'locked')
    sess2.v3_core_names = set()
    st2 = _state(gold=60, round_num=4,
                 bench=[_bench(f'C{i}', slot=i) for i in range(9)],
                 shop=[_card('姬子·启行', cost=3)])
    tag2 = _buy_tag(st2.shop[0], st2, sess2, _REG)
    assert tag2 == 'carry_gate'
    assert tag2 in _REG.remedy_buy_tags
    # 空窗+bench 未满 → line_opportunistic
    st3 = _state(gold=60, round_num=4, bench=[_bench('C0', slot=0)],
                 shop=[_card('姬子·启行', cost=3)])
    tag3 = _buy_tag(st3.shop[0], st3, sess2, _REG)
    assert tag3 == 'line_opportunistic'
    assert tag3 in _REG.remedy_buy_tags


def test_remediation_log_schema() -> None:
    """遥测锚点:remediation_log 条目字段=§1.1 schema 表键集合。
    (log 行格式 [cw][d2][remedy] 由补偿器 log.info 恒定前缀保证,
    生产日志消费侧按前缀过滤。"""
    from dataclasses import replace
    sess = _locked_sess()
    sess.v3_mode = 'war'
    sess.v2_round_key = (1, 4)
    st = _state(round_num=4, gold=13, hp=80,
                bench=[_bench('卡芙卡', faction='公司', slot=0),
                       _bench('千冶·刃', faction='公司', slot=1)],
                shop=[_card('姬子·启行', cost=4)],
                deployed=[_bench(f'D{i}', faction='公司', slot=i)
                          for i in range(5)], board={})
    res = arbitrate([(Candidate(action=BuyCard(st.shop[0]),
                                tag='line_carry', source='test'),
                      5.0, {})], st, sess, replace(_REG, war_floor=10))
    assert res.remediation_log
    entry = res.remediation_log[0]
    assert set(entry.keys()) == {'kind', 'benefit_tag', 'benefit_desc',
                                 'actions', 'outcome', 'reason'}, entry
    assert entry['kind'] == 'gold'
    assert entry['benefit_tag'] == 'line_carry'
    assert entry['outcome'] == 'done'
    assert isinstance(entry['actions'], list) and entry['actions'], entry


def test_remedy_trigger_source_working_gold() -> None:
    """收编等价(§5/ADR-0326 触发源修正):同轮已有采纳买消耗金 → 补偿
    缺口按 working.gold 真缺口算,不多卖(旧 liquidity 按 state.gold
    预测会多卖——差异面显式声明)。"""
    from dataclasses import replace
    reg10 = replace(_REG, war_floor=10)
    sess = _locked_sess()
    sess.v3_mode = 'war'
    sess.v2_round_key = (1, 4)
    # 同轮先采纳一笔 2 费买(金 15→13)→ 4 费 carry 再拒(缺 1)
    st = _state(round_num=4, gold=15, hp=80,
                bench=[_bench('卡芙卡', faction='公司', slot=0),
                       _bench('千冶·刃', faction='公司', slot=1)],
                shop=[_card('花火', cost=2), _card('姬子·启行', cost=4)],
                deployed=[_bench(f'D{i}', faction='公司', slot=i)
                          for i in range(5)], board={})
    c1 = Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                   source='test')
    c2 = Candidate(action=BuyCard(st.shop[1]), tag='line_carry',
                   source='test')
    res = arbitrate([(c1, 6.0, {}), (c2, 5.0, {})], st, sess, reg10)
    # 花火买(6.0)先采纳 → working.gold=13 → 姬子·启行(5.0)金拒缺 1
    sells = [a for a in res.actions if isinstance(a, SellBench)]
    buys = [a for a in res.actions if isinstance(a, BuyCard)]
    assert len(buys) == 2, f'两笔买都应成交(先采纳+补偿重试):{res.actions}'
    assert len(sells) == 1, \
        f'按真缺口(1)只卖 1 件(旧 state.gold 预测缺口 2 会多卖):{sells}'
    assert st.bench[sells[0].bench_idx].char_id in sess.v2_round_sold


# --- AD9-2-1 补偿组插入位置(方案 D')+ 拓扑无环锁 -----------------------------


def test_ad9_2_1_remedy_before_accepted_refresh() -> None:
    """AD9-2-1(方案 D'):同轮含已采纳 refresh + 资源拒 → 补偿组
    **出现在 refresh 之前**(受益买是旧店目标件,refresh 后店即换——
    补偿必须在 refresh 前落地,语义才自洽)。"""
    from dataclasses import replace
    sess = _locked_sess()
    sess.v3_mode = 'war'
    sess.v2_round_key = (1, 4)
    reg10 = replace(_REG, war_floor=10)
    # war 地板 10:金 13 → 买 13-4=9<10 拒(缺 1);refresh 13-2=11>=10 采纳
    st = _state(round_num=4, gold=13, hp=80,
                bench=[_bench('绯英', faction='公司', slot=0)],
                shop=[_card('姬子·启行', cost=4)],
                deployed=[_bench(f'D{i}', faction='公司', slot=i)
                          for i in range(5)], board={})
    buy_c = Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                      source='test')
    refresh_c = Candidate(action=RefreshShop(cost=2), tag='refresh',
                          source='test')
    res = arbitrate([(buy_c, 5.0, {}), (refresh_c, 2.0, {})], st, sess,
                    reg10)
    # refresh 被采纳(金足),买被金拒(缺 1)→ 补偿 [Sell, Buy]
    assert any(isinstance(a, RefreshShop) for a in res.actions), \
        f'refresh 应被采纳:{res.actions}'
    assert res.remediation_log, '买金拒应有补偿'
    idx_refresh = next(i for i, a in enumerate(res.actions)
                       if isinstance(a, RefreshShop))
    idx_sell = next(i for i, a in enumerate(res.actions)
                    if isinstance(a, SellBench))
    idx_buy = next(i for i, a in enumerate(res.actions)
                   if isinstance(a, BuyCard))
    assert idx_sell < idx_refresh and idx_buy < idx_refresh, \
        f'补偿组必须在已采纳 refresh 之前:{res.actions}'


def test_remediation_no_arbiter_import() -> None:
    """拓扑无环锁(ADR-0326 方案 B):remediation 不 import arbiter——
    正则只匹配 import 语句(文档性提及不算),防未来重构引入环。"""
    import re

    import sr_od.application.currency_war.decision_v2.remediation as m
    src = m.__loader__.get_source('sr_od.application.currency_war.'
                                  'decision_v2.remediation') or ''
    for line in src.splitlines():
        s = line.strip()
        if re.match(r'^(from|import)\b', s) and 'arbiter' in s:
            raise AssertionError(
                f'remediation 不得 import arbiter(拓扑无环):{s}')


# --- S6 腾位补偿(§1.4/§7) ----------------------------------------------------


def test_s6_bench_compensation_sell_and_retry_buy() -> None:
    """S6 正向:bench 9/9 占用+高分买被 bench 拒(非 merge)+有非保护
    可卖件 → 产出 [Sell, Buy](腾位卖+重试买);卖出件入同轮已卖集。"""
    sess = _locked_sess()
    sess.v2_round_key = (1, 4)
    st = GameState(round_num=4, gold=60, hp=80, level=5, plane=1,
                   bench=[_bench('花火', faction='列车同行', slot=0),
                          _bench('三月七', faction='列车同行', slot=1),
                          _bench('瓦尔特', faction='列车同行', slot=2),
                          _bench('卡芙卡', faction='公司', slot=3),
                          _bench('千冶·刃', faction='公司', slot=4),
                          _bench('绯英', faction='公司', slot=5),
                          _bench('娜塔莎', faction='公司', slot=6),
                          _bench('阿格莱雅', faction='公司', slot=7),
                          _bench('丹恒·饮月', faction='仙舟', slot=8)],
                   shop=[_card('散件', cost=1)],
                   board={})
    cand = Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                     merge=False, source='test')
    res = arbitrate([(cand, 5.0, {})], st, sess, _REG)
    assert res.rejections and res.rejections[0].reason.resource == 'bench'
    sells = [a for a in res.actions if isinstance(a, SellBench)]
    buys = [a for a in res.actions if isinstance(a, BuyCard)]
    assert len(sells) == 1 and buys, \
        f'bench 满+可卖件 → 腾位 [Sell, Buy]:{res.actions}'
    assert sells[0].bench_idx in (3, 4, 5, 6, 7), \
        f'只卖非保护可卖件(不得动正料/引擎件):槽{sells[0].bench_idx}'
    assert buys[0].card.name == '散件'
    sold_name = st.bench[sells[0].bench_idx].char_id
    assert sold_name in sess.v2_round_sold


def test_s6_bench_compensation_no_sellable_noop() -> None:
    """S6 反例:bench 9/9 全保护件(无可卖)→ 无补偿(整组放弃语义,
    零动作);bench 未满时买不拒(无拒绝事件)。"""
    sess = _locked_sess()
    sess.v2_round_key = (1, 4)
    st = GameState(round_num=4, gold=60, hp=80, level=5, plane=1,
                   bench=[_bench('花火', faction='列车同行', slot=i)
                          for i in range(9)],
                   shop=[_card('散件', cost=1)],
                   board={})
    cand = Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                     merge=False, source='test')
    res = arbitrate([(cand, 5.0, {})], st, sess, _REG)
    assert res.rejections
    assert not any(isinstance(a, SellBench) for a in res.actions), \
        '全保护件 → 无可卖 → 零动作(不卖正料)'
    assert not any(isinstance(a, BuyCard) for a in res.actions)
    assert sess.v2_round_sold == set()


# --- 补偿骨架锁(§1.1/§1.2;AD9 随批带修) -------------------------------------


def test_rejections_collect_only_resource_type() -> None:
    """rejections 收集面反锁:非资源型拒绝(纪律型)不进
    rejections;资源型拒绝(gold_floor/bench/deploy)进(§1.1 捕获条件
    + 正分闸)。ADR-0349:refresh_budget 已退场,纪律型代表改用
    refresh 的「非正分」拒绝(评分侧 V_D 判负 → 段尾拒,不进回连)。"""
    sess = _sess()
    sess.v2_round_key = (1, 4)
    st = _state(round_num=2, gold=60, shop=[_card('甲', cost=1)])
    cands = [
        (Candidate(action=RefreshShop(cost=2), tag='refresh', source='test'),
         -2.0, {}),   # 评分制:非正分(裸 session 无 V_D 目标语境)
        (Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                   source='test'), 5.0, {}),
    ]
    res = arbitrate(cands, st, sess, _REG)
    # log 序=主循环(买)在前、refresh 收尾在后
    assert [r['accepted'] for r in res.log] == [True, False]
    assert res.rejections == [], \
        '纪律型拒绝(非正分刷新)不得进 rejections(§1.1 捕获条件)'
    # 资源型:金不足买被 gold_floor 拒(war 地板 30,金 25 费 4)
    sess2 = _sess(v3_mode='war')
    sess2.v2_round_key = (1, 4)
    st2 = _state(round_num=4, gold=25, shop=[_card('甲', cost=4)])
    scored2 = [(Candidate(action=BuyCard(st2.shop[0]), tag='line_carry',
                          source='test'), 5.0, {})]
    res2 = arbitrate(scored2, st2, sess2, _REG)
    assert len(res2.rejections) == 1
    rj = res2.rejections[0]
    assert rj.reason.resource == 'gold'
    assert rj.reason.shortfall == 30 + 4 - 25
    assert rj.cand.action.card.name == '甲'


def test_reject_log_format_compat() -> None:
    """log 行格式不变(W52 兼容锁):拒绝字段仍是「约束名:人读原因」
    原字符串语义(RejectReason.describe 迁移,判读面零波及)。"""
    sess = _sess(v3_mode='war')
    sess.v2_round_key = (1, 4)
    st = _state(round_num=4, gold=25, shop=[_card('甲', cost=4)])
    scored = [(Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                         source='test'), 5.0, {})]
    res = arbitrate(scored, st, sess, _REG)
    assert res.log[0]['reject'] == 'gold_floor:金<30(地板;现25-费4)', \
        res.log[0]['reject']


# --- N1 前置锁(第 0 步;§0.5) ------------------------------------------------


def test_n1_bench_double_count_two_buys_both_accepted() -> None:
    """N1:同轮两笔买候选(均可采纳)→ **双采纳**。

    构造:bench 7/9 占用 + 金足(60,经济地板 50)+ 两笔 1 费买。
    第二笔检查时 working=8/9(**恰剩 1 空槽**)——修复前
    ``bench_occupied(working)+pending_bench=8+1=9≥9`` 被双计误拒;
    修复后(pending_bench 删除,容量判据=占用计数)8<9 → 采纳。
    """
    sess = _sess()
    sess.v2_round_key = (1, 4)
    bench = [_bench(f'C{i}', slot=i) for i in range(7)]
    st = _state(round_num=4, gold=60, bench=bench,
                shop=[_card('甲', cost=1), _card('乙', cost=1)])
    scored = [
        (Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                   source='test'), 5.0, {}),
        (Candidate(action=BuyCard(st.shop[1]), tag='line_carry',
                   source='test'), 4.0, {}),
    ]
    res = arbitrate(scored, st, sess, _REG)
    buys = [r for r in res.log if r['tag'] == 'line_carry']
    assert len(buys) == 2
    rejects = [(r['desc'], r['reject']) for r in buys]
    assert all(r['accepted'] for r in buys), (
        f'双买应双采纳(第二笔检查 working=8/9 恰剩 1 空槽,'
        f'不得被 pending_bench 双计误拒):{rejects}')
