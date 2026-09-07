"""T-126 卖出通道排除仲裁·装配 A 身份段覆盖(单帧锁;批 2)。

出处(锁纪律:新锁必引设计出处):
- ADR-0585(卖出通道排除仲裁单一源;Z1 吸收 / F2 拆三块修订 /
  P78-4 类资格本义 / 消费点渐进迁移申报);
- docs/develop/currency_war/proofs/math_proofs.md **P78** 行(INV 主
  不变量 / P78-4 M4·funding 对③④持有件禁卖 / P78-6 读端同源);
- 方案 v3(`.debug/temp/currency_war/t126_sell_arbitration/方案.md`)
  §2.2(A 三段)/ §2.9 覆盖表(W4 · 备战F1 · 新格 A)/ §6.1 批 2 行;
- 双攻击报告案号:shop_sell W4(M4 腾席可卖③④持有件)、prep_loop F1
  (prep M4 漏 P60 注入 + ④件两域无豁免)。

批 2 辖域声明:本文件只锁身份段(义务基座 ∪ 静态持有两集);窗口段
(press/垫保发射登记)、funding 兜底豁免(P78-5)、projection 全资格
视图(T3 活跃集并入)归批 3,对应格(W1/W3)锁随批 3 落地。funding
空手率指标依赖批 4 plain 分键,批 4 前不可测、不得引用(方案 v3 §5.4
可用性次序)——本文件只以装配形态占位(见 TestSellGateIdentity)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_card_identity import (
    sell_hold_exclusion_names,
)
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    locked_buy_membership,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    PrepObservation,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    SellBench as PrepSellBench,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.kernel.cw_state import (
    SellBench as ShopSellBench,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    entry,
    mandate,
    sell_gate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    sell as crit_sell,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    decide_shop_action,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    predicates,
)

# ===== 测试基建(与 test_cw_locked_buy_membership_split 同构)=====

#: 锁定 comp:core ∩ 静态持有集 = ∅(持有个案探针核定;core 成员本身
#: ∈ 持有集的 comp 会使义务基座与持有集混淆,锁语义不纯)。
_COMP = '命运圣杯红A'
#: 持有件代表集(静态两集在册名,单件过 M4/凑息/funding 全部物理谓词
#: ——红证由各锁自带直接调用证明,非本注释口断)。
_HOLDS_9 = ('三月七', '丹恒·饮月', '千冶·刃', '姬子·启行', '希儿',
            '爻光', '符玄', '缇宝', '花火')


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _card(name: str, cost: int = 3, star: int = 1) -> ShopCard:
    return ShopCard(x=100, name=name, cost=cost, star=star)


def _core() -> tuple[str, ...]:
    return tuple(predicates.line_members(get_comp(_COMP)))


def _unlocked_sess() -> StrategySession:
    s = StrategySession()
    state_of(s).cw4_counters = {}
    state_of(s).target_comp = get_comp(_COMP)
    state_of(s).v3_intention = IntentionState()
    return s


def _locked_sess() -> StrategySession:
    s = _unlocked_sess()
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = _COMP
    ist.lock_plane = 2
    state_of(s).v3_intention = ist
    return s


def _state(gold: int, bench: list[BenchChar]) -> GameState:
    st = GameState(gold=gold, level=7, round_num=2, hp=60)
    st.plane = 2
    st.bench = list(bench)
    st.deployed = []
    return st


# ===== 装配 A 单一入口:身份段构成 + 通道闭集 + funding 占位 =====


class TestSellGateIdentity:
    """sell_gate 身份段装配锁(P78 INV §2.2 第 1 段;方案 v3 §3.1)。"""

    def test_unlocked_base_is_k_members(self):
        """身份段构成(未锁态):义务基座 = k_members(窄),∪ 静态持有
        两集。红证同构:拔掉静态两集(仅基座)时持有件不入排除集——
        即 W4/备战F1 的病理形态(装配缺构件 = 件可卖)。"""
        k = _core()
        sess = _unlocked_sess()
        excl = sell_gate.identity_exclusions(sess, k)
        assert set(k) <= excl
        assert set(sell_hold_exclusion_names()) <= excl
        holds = sell_hold_exclusion_names()
        assert excl - set(k) == set(holds), '窄静态全集之外不得多排(禁静态全集论证,ADR-0580)'

    def test_locked_base_is_wide_membership(self):
        """身份段构成(锁线态):义务基座 = locked_buy_membership 锁定
        采购集宽集(解析单点,与 shop buy_members 同源;ADR-0580 §7
        低-1 平移)。宽−窄成员(hoard-only)在排除集 = P60 换手通道
        对 M4/funding 闭合(备战 F1 注入齐)。"""
        sess = _locked_sess()
        ist = state_of(sess).v3_intention
        wide = set(locked_buy_membership(ist) or frozenset())
        k = _core()
        hoard_only = sorted(wide - set(k))
        assert hoard_only, '锁前提失效:该 comp 锁定采购集无窄集外成员'
        excl = sell_gate.identity_exclusions(sess, k)
        assert wide <= excl

    def test_batch2_all_channels_share_identity_segment(self):
        """批 2 通道无关性:通道闭集全集逐通道 == 同一身份段(窗口段/
        对价段批 3 才分叉)。通道参数为定形位,枚举外值拒收
        (单一入口防线,防第五通道绕 A 手搓排除复发)。"""
        import pytest

        k = _core()
        sess = _unlocked_sess()
        want = frozenset(sell_gate.identity_exclusions(sess, k))
        for ch in sorted(sell_gate.SELL_CHANNELS):
            got = sell_gate.sell_exclusions(sess, k, channel=ch)
            assert got == want, f'通道 {ch} 批 2 应返回同一身份段'
        with pytest.raises(ValueError):
            sell_gate.sell_exclusions(sess, k, channel='unknown_channel')

    def test_funding_empty_rate_placeholder_assembly_shape(self):
        """funding 空手率占位(装配形态,不测行为):funding 通道排除面
        = 身份段(含静态持有两集)——③④ 件退出 funding 主路径资格,
        「空手」形态的装配前提在位。指标本身(funding 空手率)依赖批 4
        plain 分键,批 4 前不可测、不得引用(方案 v3 §5.4;ADR-0585 §6)。
        兜底豁免(P78-5)批 3 接线后,本格由矩阵测试对角格(持有×funding)
        扩展承载。"""
        k = _core()
        sess = _unlocked_sess()
        funding_excl = sell_gate.sell_exclusions(sess, k, channel='funding')
        assert set(k) <= funding_excl
        assert set(sell_hold_exclusion_names()) <= funding_excl

    def test_hold_exclusions_moved_lifecycle_preserved(self):
        """平移兼容锁:sell_hold_exclusions 本体在 sell_gate(mandate 为
        再出口),②(b) 动态登记与 F1 锁线清空语义逐位保留(批 2 平移零
        行为变更,B3;P78-3 证其错误但修法随批 3,ADR-0585 消费限制)。
        反向格:sell_exclusions(身份段入口)**不含**动态登记名——窗口段
        未落地,批边界防提前渗漏。"""
        sess = _unlocked_sess()
        state_of(sess).cw4_dead_gold_bought_names.add('燃料件Z')
        excl = mandate.sell_hold_exclusions(sess, ())
        assert '燃料件Z' in excl, '动态登记未入凑息排除集 = 平移改行为'
        assert '燃料件Z' not in sell_gate.sell_exclusions(
            sess, (), channel='interest'), \
            '身份段入口不得含动态登记(窗口段归批 3)'
        # F1:锁线帧读点清空动态集(与平移前逐位一致)
        locked = _locked_sess()
        state_of(locked).cw4_dead_gold_bought_names.add('燃料件Z')
        mandate.sell_hold_exclusions(locked, ())
        assert not state_of(locked).cw4_dead_gold_bought_names, \
            'F1 定型清空语义在平移后必须原样保留(批 3 才改轮界过期)'


# ===== W4:M4 腾席对 ③④ 持有件禁卖(shop 域,方案 v3 §2.9)=====


class TestW4ShopM4HoldExcluded:
    """W4 锁(shop_sell 攻击报告 W4;P78-4):bench 满 ∧ M2 缺员 ∧
    可卖对象仅 ③④ 持有 1★ 件 ⇒ M4 不发射,m2_retry_exhausted 诚实
    停摆。红证(现行批 2 前形态):排除集仅义务基座(buy_members)时
    持有件恰全数入燃料候选——「移除身份段 → 持有件被腾席卖掉」的
    机制复现(凑息通道有 Z1 静态集,唯独 M4 无的病理在此闭死)。"""

    def test_hold_only_bench_honest_stall(self):
        k = _core()
        bench = [_bc(n, slot=i + 1) for i, n in enumerate(_HOLDS_9)]
        st = _state(gold=30, bench=bench)
        st.shop = [_card(k[0], 3)]          # 缺员核心件在店(可负担)
        sess = _unlocked_sess()
        act = decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert not isinstance(act, ShopSellBench), \
            'W4:③④ 持有件被 M4 腾席卖出 = 持有换手通道未闭死'
        ct = state_of(sess).cw4_counters
        assert ct.get('m2_retry_exhausted', 0) >= 1
        assert ct.get('bench_full_buy_abandon', 0) >= 1

    def test_red_proof_holds_qualify_under_pre_batch2_exclusion(self):
        """红证:同构帧按批 2 前排除形态(仅义务基座 = k_members)评估,
        9 张持有件全数入燃料候选——本锁绿由身份段排除承载,非谓词侧
        自带拒(判别:谓词拒则红证应空)。"""
        k = _core()
        bench = [_bc(n, slot=i + 1) for i, n in enumerate(_HOLDS_9)]
        st = _state(gold=30, bench=bench)
        cands = mandate.fuel_sell_candidates(bench, k, state=st,
                                             exclude_names=frozenset(k))
        assert {b.char_id for b in cands} == set(_HOLDS_9), \
            '红证失效:持有件未穿过身份段外的全部资格谓词'

    def test_liveness_ordinary_fuel_still_sold(self):
        """活性伴随格(防锁空转):同帧形态换普通线外燃料件 ⇒ M4 照常
        腾席卖 1(身份段只排持有/义务身份,不扩燃料面——禁静态全集
        论证,ADR-0580;ADR-0585 批 2 收紧仅持有身份维)。"""
        k = _core()
        bench = [_bc(f'填充燃料{i}', slot=i + 1)
                 for i in range(BENCH_CAPACITY)]
        st = _state(gold=30, bench=bench)
        st.shop = [_card(k[0], 3)]
        sess = _unlocked_sess()
        act = decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, ShopSellBench), \
            '普通线外燃料件被身份段误排 = 排除面过宽(禁静态全集违例)'


# ===== 备战 F1:prep M4 消费 A(prep_loop 攻击报告 F1;方案 v3 §2.9)=====


class TestBeiZhanF1PrepM4:
    """备战 F1 锁:锁线帧 prep M2→M4 重试环燃料集 = 身份段齐注入——
    hoard 宽集成员(P60 注入,原漏接)与 ④放行件(身份段,两域原无
    豁免)都不入候选;腾不出席走 m2_retry_exhausted 诚实停摆(伪装
    换手形态在此域闭死)。"""

    def test_prep_m4_sell_none_for_wide_and_hold_members(self):
        k = _core()
        sess = _locked_sess()
        bench_names = ('Saber', '吉尔伽美什',      # hoard-only 宽集成员
                       '丹恒·饮月', '千冶·刃', '希儿',
                       '爻光', '符玄', '缇宝', '藿藿')   # ④放行/静态持有
        bench = [_bc(n, slot=i + 1) for i, n in enumerate(bench_names)]
        frame = mandate.MandateFrame(
            gold=60, level=3, bench=bench, deployed=[], deploy_cap=4,
            node_type=None, stop_flag=False, k_members=k, round_num=2)
        out = mandate.run_mandate(frame, sess, state=_state(60, bench))
        sells = [e.action for e in out if isinstance(e.action, PrepSellBench)]
        assert not sells, \
            f'备战F1:prep M4 卖出 {sells} = P60/身份段注入缺位(伪装换手)'
        ct = state_of(sess).cw4_counters
        assert ct.get('m2_retry_exhausted', 0) >= 1

    def test_red_proof_wide_and_hold_qualify_pre_batch2(self):
        """红证(两病理腿各一):①拔掉排除集 → hoard 宽集成员(Saber)
        入候选 = prep_loop F1 漏注入病理;②排除集仅义务基座 → ④件
        (藿藿)仍入候选 = ④件两域无豁免病理。身份段双构件各对一格。"""
        k = _core()
        bench_names = ('Saber', '吉尔伽美什', '丹恒·饮月', '千冶·刃',
                       '希儿', '爻光', '符玄', '缇宝', '藿藿')
        bench = [_bc(n, slot=i + 1) for i, n in enumerate(bench_names)]
        st = _state(60, bench)
        no_excl = mandate.fuel_sell_candidates(bench, k, state=st)
        assert 'Saber' in {b.char_id for b in no_excl}, '红证①失效'
        base_only = mandate.fuel_sell_candidates(
            bench, k, state=st, exclude_names=frozenset(k))
        assert '藿藿' in {b.char_id for b in base_only}, '红证②失效'


# ===== 新格 A:entry 两处 funding 空排除接线(方案 v3 §2.9)=====


class TestEntryFundingCells:
    """entry funding 消费位锁(新格 A):两处旧**空排除**装配改为消费
    统一装配 A 身份段——锁线宽集成员不再可被 prep funding 卖(→ shop
    M2 重买换手),③④ 持有件同禁(P78-4)。"""

    def test_criteria_pass_funding_excludes_hold(self):
        """格④(_criteria_pass funding,方案锚 entry.py:769-802):
        bench 唯一 ④件 ⇒ funding 零发射。红证:判据直调不带排除集 ⇒
        该件恰入卖出槽集;活性伴随:普通燃料件照常卖出(分支非空转)。"""
        st = GameState(gold=1, level=5, round_num=2, hp=40)
        sess = SimpleNamespace(cw4_counters={})

        def _run(bench: list[BenchChar]) -> list:
            frame = mandate.MandateFrame(
                gold=1, level=5, bench=bench, deployed=[], deploy_cap=6,
                node_type=None, stop_flag=True, k_members=('线内件X',),
                round_num=2)
            return entry._criteria_pass(
                frame, sess, st, ('线内件X',),
                k_switched=False, old_line_members=())

        out = _run([_bc('藿藿', slot=1)])
        assert not [e for e in out if isinstance(e.action, PrepSellBench)], \
            '新格A④:④件被 EV funding 卖出 = 空排除未接身份段'
        slots, key = crit_sell.funding_support_sell(
            1, 9, [_bc('藿藿', slot=1)], ('线内件X',), state=st)
        assert key == '' and slots == [1], '红证失效:藿藿未穿过排除外谓词'
        out2 = _run([_bc('填充燃料F', slot=1)])
        assert [e.action.slot for e in out2
                if isinstance(e.action, PrepSellBench)] == [1], \
            '活性伴随失效:funding 分支未卖出普通燃料件(锁空转)'

    def test_skeleton_only_funding_excludes_hold(self):
        """格③(skeleton_only funding,方案锚 entry.py:492-506):全
        emit 链 skeleton_only 臂下,bench 唯一 ④件 ⇒ funding 零发射
        (骨架 M4 同帧亦不卖——同帧双通道一致)。红证:判据直调不带
        排除集 ⇒ 该件恰入卖出槽集。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
            MandateV1Strategy,
        )
        strat = MandateV1Strategy()
        sess = _unlocked_sess()
        # gold=0:comp 最低缺员价 = 1(注册表现算,gold=1 会落 not_needed
        # 死格,锁空转)——funding 触发前件 gold < need 必须真开。
        st = _state(gold=0, bench=[_bc('藿藿', slot=1)])
        st.shop = []
        obs = PrepObservation(state=st, bench_chars=[_bc('藿藿', slot=1)],
                              deployed_chars=[], deploy_vacancy=0)
        out = entry.emit(obs, SimpleNamespace(), sess, None,
                         ev_arm='skeleton_only', registry=strat.registry)
        sells = [e.action for e in out if isinstance(e.action, PrepSellBench)]
        assert not sells, \
            f'新格A③:skeleton_only funding 卖出 {sells} = 空排除未接身份段'
        slots, key = crit_sell.funding_support_sell(
            0, 9, [_bc('藿藿', slot=1)], _core(), state=st)
        assert key == '' and slots == [1], '红证失效:藿藿未穿过排除外谓词'
