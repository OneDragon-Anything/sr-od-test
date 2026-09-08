"""T-126 卖出通道排除仲裁·装配 A 身份段覆盖(单帧锁;批 2 建,批 3 扩)。

出处(锁纪律:新锁必引设计出处):
- ADR-0585(卖出通道排除仲裁单一源;Z1 吸收 / F2 拆三块修订 /
  P78-4 类资格本义 / 消费点渐进迁移申报);
- docs/develop/currency_war/proofs/math_proofs.md **P78** 行(INV 主
  不变量 / P78-4 M4·funding 对③④持有件禁卖 / P78-6 读端同源);
- 方案 v3(`.debug/temp/currency_war/t126_sell_arbitration/方案.md`)
  §2.2(A 三段)/ §2.9 覆盖表(W4 · 备战F1 · 新格 A)/ §6.1 批 2 行;
- 双攻击报告案号:shop_sell W4(M4 腾席可卖③④持有件)、prep_loop F1
  (prep M4 漏 P60 注入 + ④件两域无豁免)。

批 3 适配申报(ADR-0585 §6 分批;锁语义重推非机械跟绿):①F1 锁线
清空语义已废除(P78-3 证其为错误),原平移兼容锁改锁 W3 轮界过期语义
(窗口段锁 = test_cw_sell_window_launch.py,本文件只留凑息出口形态);
②funding 兜底豁免(P78-5)落地,原「④件 funding 零发射」中介窗口
(ADR-0585 Status 申报「③④件 funding 变现出口批 2→3 缺席」)按四
条件重开——新格 A 锁改锁兜底豁免形态。窗口段/发射登记/五键/W1/W3/W5
场景锁在 test_cw_sell_window_launch.py(批 3 新建主题文件)。
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
        """通道视图构成锁:空登记簿帧各通道 == 同一身份段(通道差异面
        只来自窗口段/projection 并集——空簿帧窗口段与 T3 视图皆空,故
        全通道同构)。通道参数为定形位,枚举外值拒收(单一入口防线,
        防第五通道绕 A 手搓排除复发)。"""
        import pytest

        k = _core()
        sess = _unlocked_sess()
        want = frozenset(sell_gate.identity_exclusions(sess, k))
        for ch in sorted(sell_gate.SELL_CHANNELS):
            got = sell_gate.sell_exclusions(sess, k, channel=ch)
            assert got == want, f'通道 {ch} 空登记簿帧应返回同一身份段'
        with pytest.raises(ValueError):
            sell_gate.sell_exclusions(sess, k, channel='unknown_channel')

    def test_funding_empty_rate_placeholder_assembly_shape(self):
        """funding 空手率占位(装配形态,不测行为):funding 通道排除面
        = 身份段(含静态持有两集)——③④ 件退出 funding 主路径资格,
        「空手」形态的装配前提在位。指标本身(funding 空手率)依赖批 4
        plain 分键,批 4 前不可测、不得引用(方案 v3 §5.4;ADR-0585 §6)。
        兜底豁免(P78-5)已批 3 接线:对角格(持有×funding)行为锁 =
        test_cw_sell_window_launch.py TestFundingHoldFallback。"""
        k = _core()
        sess = _unlocked_sess()
        funding_excl = sell_gate.sell_exclusions(sess, k, channel='funding')
        assert set(k) <= funding_excl
        assert set(sell_hold_exclusion_names()) <= funding_excl

    def test_window_round_lifecycle_replaces_f1(self):
        """W3 修法锁(P78-3;shop_sell 报告 W3):F1 锁线清空废除改轮界
        过期——press 登记活跃轮(登记轮==当前轮)入凑息排除面,轮进即
        回池(禁卖面有界性反向锁);锁线帧不清空登记(锁线定型不是任何
        买因类的账闭合事件,锁线帧买入由登记轮==当前轮天然覆盖)。原批 2
        平移锁钉 F1 旧语义,P78-3 证其错误,本锁为批 3 语义重推非跟绿。"""
        sess = _unlocked_sess()
        sell_gate.register_launch(sess, '燃料件Z', cause='press', round_num=2)
        assert '燃料件Z' in sell_gate.sell_exclusions(
            sess, (), channel='interest', current_round=2), \
            '登记轮活跃帧不入凑息排除 = W1 同 visit 卖回未闭死'
        assert '燃料件Z' not in sell_gate.sell_exclusions(
            sess, (), channel='interest', current_round=3), \
            '轮界过期未回池 = 过度禁卖无界(P78-2b τ=同轮违例)'
        # 锁线帧不清空(F1 废除;锁线帧活跃覆盖见窗口段锁 W3 格)
        locked = _locked_sess()
        sell_gate.register_launch(locked, '燃料件Z', cause='press',
                                  round_num=2)
        sell_gate.sell_exclusions(locked, (), channel='interest',
                                  current_round=2)
        assert state_of(locked).cw4_fuel_filler_stall_buys, \
            '锁线帧清空登记 = F1 错误语义回流(P78-3)'

    def test_hold_exclusions_compat_shim_identity_only(self):
        """兼容再出口锁:sell_hold_exclusions 语义 = 身份段(生产消费位
        已批 3 全量迁移 sell_exclusions;本名保留测试/外部引用零断链,
        ADR-0585 渐进迁移申报)——不含动态登记、不再清空旧载体。"""
        sess = _unlocked_sess()
        sell_gate.register_launch(sess, '燃料件Z', cause='press', round_num=2)
        excl = mandate.sell_hold_exclusions(sess, ())
        assert '燃料件Z' not in excl, \
            '兼容出口含窗口段 = 无轮号帧放大禁卖面(V2-09 放行向违例)'
        assert excl == sell_gate.identity_exclusions(sess, ())


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


# ===== 新格 A:entry 两处 funding 空排除接线(方案 v3 §2.9;批 3 兜底
#      豁免 P78-5 重开 ④件变现出口,ADR-0585 Status 中介窗口收口)=====


class TestEntryFundingCells:
    """entry funding 消费位锁(新格 A + P78-5 兜底形态):两处旧**空
    排除**装配消费统一装配 A——义务基座/③④ 持有件退出 funding 主路径
    (空排除 = 锁线宽集成员可被 prep funding 卖 → shop M2 重买换手,
    病理格);主路径空 ∧ 仍需筹资时经兜底豁免(P78-5 四条件:非持有
    资格面耗尽顺序豁免)单笔变现 ④件。批 2 锁「④件零发射」钉的是
    中介窗口形态(ADR-0585 Status 申报批 2→3 缺席),批 3 兜底重开为
    设计语义,本锁按 P78-5 重推非跟绿。"""

    def test_criteria_pass_funding_fallback_liquidates_hold(self):
        """格④(_criteria_pass funding,方案锚 entry.py:769-802):
        bench 唯一 ④件 ⇒ 主路径空 → 兜底豁免单笔卖出(行为面;分键
        计数已随 2026-09-08 用户归因遥测删除指令拆除)。红证:判据直调
        不带排除集 ⇒ 该件恰入卖出槽集;活性伴随:普通燃料件走主路径。"""
        st = GameState(gold=1, level=5, round_num=2, hp=40)
        sess = SimpleNamespace()

        def _run(bench: list[BenchChar]) -> tuple[list, dict]:
            state_of(sess).cw4_counters = {}
            frame = mandate.MandateFrame(
                gold=1, level=5, bench=bench, deployed=[], deploy_cap=6,
                node_type=None, stop_flag=True, k_members=('线内件X',),
                round_num=2)
            out = entry._criteria_pass(
                frame, sess, st, ('线内件X',),
                k_switched=False, old_line_members=())
            return out, state_of(sess).cw4_counters

        out, _ct = _run([_bc('希儿', slot=1)])
        sells = [e.action for e in out if isinstance(e.action, PrepSellBench)]
        assert [s.slot for s in sells] == [1], \
            '新格A④:④件兜底豁免未接线 = 变现出口缺席(中介窗口未收口)'
        slots, key = crit_sell.funding_support_sell(
            1, 9, [_bc('希儿', slot=1)], ('线内件X',), state=st)
        assert key == '' and slots == [1], '红证失效:希儿未穿过排除外谓词'
        # 达成量化(P78-5 条③):藿藿退金 1 < 缺口 2(need 3 − gold 1)
        # ⇒ 不放行——期权损失(P01)已付而义务未达成 = 严格有害
        out3, _ct3 = _run([_bc('藿藿', slot=1)])
        assert not [e for e in out3 if isinstance(e.action, PrepSellBench)], \
            '兜底卖出退金不达缺口 = 达成量化(P78-5 条③)违例'
        out2, _ct2 = _run([_bc('填充燃料F', slot=1)])
        assert [e.action.slot for e in out2
                if isinstance(e.action, PrepSellBench)] == [1], \
            '活性伴随失效:funding 分支未卖出普通燃料件(锁空转)'

    def test_skeleton_only_funding_fallback_liquidates_hold(self):
        """格③(skeleton_only funding,方案锚 entry.py:492-506):全
        emit 链 skeleton_only 臂下,bench 唯一 ④件 ⇒ 主路径空 → 兜底
        豁免单笔卖出(骨架 M4 同帧不卖——同帧双通道一致,席未满)。红证:
        判据直调不带排除集 ⇒ 该件恰入卖出槽集。"""
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
        assert [s.slot for s in sells] == [1], \
            f'新格A③:skeleton_only funding 兜底未卖出 {sells} = 出口缺席'
        slots, key = crit_sell.funding_support_sell(
            0, 9, [_bc('藿藿', slot=1)], _core(), state=st)
        assert key == '' and slots == [1], '红证失效:藿藿未穿过排除外谓词'
