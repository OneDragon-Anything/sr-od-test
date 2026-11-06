"""买面席位与追星改革单帧测试(迭代 ``2026-10-28-hp-purge-refresh-reform``
T-3;设计 = details/shop-buy-reform.md §1-§3,镜像 = mandate_v1/shop.py
``decide_shop_action`` 买面段)。

覆盖面(行为变化申报的锁定行):

- **W5 买臂可达性矩阵**(成员状态 × 需求 → 触发买臂,锁定后缺口口径;
  缺口单位 = 1★ 等价张数,2★=3/3★=9,3 合 1):
  | 成员状态 | 在售 | 触发买臂 |
  |---|---|---|
  | 未持 | 任意星级副本 | 序 1 缺件(m2_line_member) |
  | 持 2★ ∧ 追 3★ | 1★ 副本 | 序 1 缺件(缺口 > 0 照买——修「名单
    星级盲」四臂够不着缺陷,追查件缺陷 4) |
  | 持 2★ ∧ 追 3★ | 2★ 副本 | 序 1 缺件(任意星级照买) |
  | 持 2×1★(无 2★) | 1★ 副本 | M2b 即时合成(满栏例外免席快路径) |
  | 场上 2★ + 备战 1★×2 | 1★ 副本 | M2b(机制全集扩面形态) |
  | 持 2×2★ ∧ 追 3★ | 2★ 副本 | 序 1 缺件(买即连锁 3★) |
  | 达标(held ≥ need) | 1★/2★ 副本 | 无臂显式停买(拒因
    ``star_goal_met``) |
- **W4 停留刷窗口让位**:窗口内(``refresh_warranted`` 真)M6 压牌库
  囤货臂零发射;非窗口 M6 照常回归。
- **W11 刷新负结果记忆**(3.2 后记忆面 = 金线效果条目):拒绝态关店置标记;
  重入无状态变化跳过刷新提案;状态变化清标记后提案恢复(付费效果条目);
  「目标不可买」置位分支随预测门退役(design §2.2,免费效果条目无条件刷)。
- 合成效果条目谓词机制全集直调形态表(恰 2 张 1★ / 2×1★+2★ / 2×2★)。

帧构造 = 列车同行注册表线(need_star:姬子·启行 3/三月七 2/花火 2/
瓦尔特 1);deployed 定义件 = 白厄(注册表零阵营流派唯一名,板面标签空集
——序 2 场况插件羁绊差一门对任意在售牌零命中,买面测试免序 2 干扰);
node='reward' → 升级检查①奖励帧抑制 defer,会话恒进入买面与刷新提案。
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_card as _card,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_comp as _comp_of,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_decide as _decide,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_gs,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_members as _members,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_session as _session,
)

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_game_state import (
    Unit,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BENCH_CAPACITY,
    CwActionBuyCardParam,
    CwActionRefreshShopParam,
    CwActionSellBenchParam,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    session_scope,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    shop as _shop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

_COMP_NAME = '列车同行·反震'   # 批 3 拆分后取 A 主形态(测试载体与装备分岔无关)
_LINE = tuple(_members(_comp_of(_COMP_NAME)))
_TARGET = '姬子·启行'   # need_star 3(唯一 3★ 追到底目标)
_DEPLOY_ANCHOR = '白厄'   # 零阵营流派(板面标签空集定义件;注册表现查)


def _fillers(count: int, exclude: tuple[str, ...] = ()) -> list[str]:
    """非线燃料名(注册表现算防漂移;填充席位/在售候选——核心/保护
    身份规避面已随统一让位优先级迭代 3.4 退役,非线内即可)。"""
    out = [n for n in CHARACTERS
           if n not in _LINE and n not in exclude]
    assert len(out) >= count, '测试前提:填充名不足'
    return out[:count]


def _locked_frame(*, bench, deployed, gold: int, level: int,
                  cards: tuple = (), round_num: int = 2,
                  node: str = 'reward', comp_name: str = _COMP_NAME):
    """锁定线决策帧(cw4 种子家族 + 状态归一挂载 + 位面 2 边界执行;
    判据读口与 decide 驱动共用同一宿主形态)。"""
    s = _session(_comp_of(comp_name), plane_lengths=[9, 5, 7])
    axes = {'gold': gold, 'level': level, 'plane': 2,
            'round_num': round_num, 'node': node, 'hp': 100,
            'bench': list(bench), 'front_row': list(deployed),
            'shop': list(cards)}
    gs = cw4_gs(s, **axes)
    st = state_of(s)
    gs.strategy_state = st   # 宿主归一:判据读口(session_scope 族)同源
    gs.node_hist_pos = (2, 1)
    session_scope.handle_node_boundary(gs)
    st.gold_ledger = gold
    return s, gs, st


def _full_line_bench(*, jizi_star: int = 2, fillers: int = 5) -> list:
    """席满线基础数据:姬子 jizi_star 星(追 3★ 目标)+ 三月七/花火/瓦尔特
    达标 + 2★ 填充(无 1★ ⇒ 零燃料,目标可买席位效果条目恒假)。"""
    fill = _fillers(fillers)
    return [_bc(_TARGET, star=jizi_star), _bc('三月七', star=2),
            _bc('花火', star=2), _bc('瓦尔特', star=2)] \
        + [_bc(n, star=2) for n in fill[:fillers]]


class TestW5StarArmsMatrix:
    """买臂可达性矩阵必测行(锁定后缺口口径)。"""

    def test_unowned_member_any_star_copy_order1(self):
        """矩阵行 1:未持成员 × 1★ 在售 → 序 1 缺件买(现行语义保持)。"""
        fill = _fillers(4)
        bench = [_bc('花火', star=2), _bc('瓦尔特', star=1)] \
            + [_bc(n, star=2) for n in fill]
        s, gs, _st = _locked_frame(bench=bench,
                                   deployed=[Unit(char_id=_DEPLOY_ANCHOR, star=2)],
                                   gold=100, level=7,
                                   cards=(_card('三月七', cost=1, star=1,
                                                x=0),))
        acts = _decide(s)
        buys = [a for a in acts if isinstance(a, CwActionBuyCardParam)]
        assert buys, f'未持成员副本应被序 1 缺件买: {acts!r}'
        assert buys[0].reason == 'm2_line_member'

    def test_held_2star_chasing_3_buys_1star_copy(self):
        """矩阵行 2:持 2★ ∧ 追 3★ × 1★ 在售 → 序 1 缺件买(本批修复行
        ——旧口径名单星级盲,该副本四臂够不着,追查件缺陷 4)。"""
        fill = _fillers(3)
        bench = [_bc(_TARGET, star=2), _bc('三月七', star=2),
                 _bc('花火', star=2), _bc('瓦尔特', star=1)] \
            + [_bc(n, star=2) for n in fill]
        s, gs, _st = _locked_frame(bench=bench,
                                   deployed=[Unit(char_id=_DEPLOY_ANCHOR, star=2)],
                                   gold=100, level=7,
                                   cards=(_card(_TARGET, cost=3, star=1,
                                                x=0),))
        acts = _decide(s)
        buys = [a for a in acts if isinstance(a, CwActionBuyCardParam)]
        assert buys, f'持 2★ 追 3★ 成员 1★ 副本应照买(缺口口径): {acts!r}'
        assert buys[0].reason == 'm2_line_member'

    def test_held_2star_chasing_3_buys_2star_copy(self):
        """矩阵行 3:持 2★ ∧ 追 3★ × 2★ 直出在售 → 序 1 缺件买(任意
        星级照买口径;累积 2×2★ 向 3★ 推进)。"""
        fill = _fillers(3)
        bench = [_bc(_TARGET, star=2), _bc('三月七', star=2),
                 _bc('花火', star=2), _bc('瓦尔特', star=1)] \
            + [_bc(n, star=2) for n in fill]
        s, gs, _st = _locked_frame(bench=bench,
                                   deployed=[Unit(char_id=_DEPLOY_ANCHOR, star=2)],
                                   gold=100, level=7,
                                   cards=(_card(_TARGET,
                                                cost=3 * int(CHARACTERS[_TARGET].cost),
                                                star=2, x=0),))
        acts = _decide(s)
        buys = [a for a in acts if isinstance(a, CwActionBuyCardParam)]
        assert buys, f'持 2★ 追 3★ 成员 2★ 副本应照买: {acts!r}'
        assert buys[0].reason == 'm2_line_member'
        assert int(buys[0].card.star or 1) == 2

    def test_pair_1star_full_bench_m2b_seat_free(self):
        """矩阵行 4:持 2×1★ × 1★ 在售(席满帧)→ M2b 即时合成直发
        (满栏例外免席;该名经 m2b 快路径名排除,不入序 1 置换账)。"""
        fill = _fillers(4)
        bench = [_bc('花火', star=1), _bc('花火', star=1),
                 _bc(_TARGET, star=3), _bc('三月七', star=2),
                 _bc('瓦尔特', star=2)] \
            + [_bc(n, star=2) for n in fill]
        assert len(bench) == BENCH_CAPACITY
        s, gs, _st = _locked_frame(bench=bench,
                                   deployed=[Unit(char_id=_DEPLOY_ANCHOR, star=2)],
                                   gold=100, level=7,
                                   cards=(_card('花火', cost=2, star=1,
                                                x=0),))
        acts = _decide(s)
        buys = [a for a in acts if isinstance(a, CwActionBuyCardParam)]
        assert buys, f'2×1★ 席满帧应由 M2b 免席直发: {acts!r}'
        assert buys[0].reason == 'm2_merge_completion'
        assert not [a for a in acts if isinstance(a, CwActionSellBenchParam)], \
            '免席直发不得伴随置换卖出'

    def test_pair_1star_with_2star_on_field_m2b(self):
        """矩阵行 5(扩展形态):场上 2★ + 备战 1★×2 × 1★ 在售 → M2b
        (机制全集扩面——旧「恰 2 张全 1★」口径排除该形态,此帧结构性
        无臂;追 3★ 成员买第 3 张 1★ 合成第 2 个 2★,向 3★ 推进;
        成员 = 姬子·启行 need 3——2★ 即达标成员〔need 2〕无「向 3★
        推进」语义,如花火持 2★ 时同形态属达标停买辖)。"""
        fill = _fillers(4)
        bench = [_bc(_TARGET, star=1), _bc(_TARGET, star=1),
                 _bc('三月七', star=2), _bc('花火', star=2),
                 _bc('瓦尔特', star=2)] \
            + [_bc(n, star=2) for n in fill]
        assert len(bench) == BENCH_CAPACITY
        s, gs, _st = _locked_frame(bench=bench,
                                   deployed=[Unit(char_id=_TARGET, star=2)],
                                   gold=100, level=7,
                                   cards=(_card(_TARGET, cost=3, star=1,
                                                x=0),))
        acts = _decide(s)
        buys = [a for a in acts if isinstance(a, CwActionBuyCardParam)]
        assert buys, f'2×1★+场上 2★ 形态应由 M2b 承接: {acts!r}'
        assert buys[0].reason == 'm2_merge_completion'

    def test_two_2star_chasing_3_buys_2star_direct(self):
        """矩阵行 6:持 2×2★ ∧ 追 3★ × 2★ 直出在售 → 序 1 缺件买
        (缺口 3 张 1★ 等价;买第 3 张 2★ 即连锁合成 3★)。"""
        fill = _fillers(2)
        bench = [_bc(_TARGET, star=2), _bc(_TARGET, star=2),
                 _bc('三月七', star=2), _bc('花火', star=2),
                 _bc('瓦尔特', star=1)] \
            + [_bc(n, star=2) for n in fill]
        s, gs, _st = _locked_frame(bench=bench,
                                   deployed=[Unit(char_id=_DEPLOY_ANCHOR, star=2)],
                                   gold=100, level=7,
                                   cards=(_card(_TARGET,
                                                cost=3 * int(CHARACTERS[_TARGET].cost),
                                                star=2, x=0),))
        acts = _decide(s)
        buys = [a for a in acts if isinstance(a, CwActionBuyCardParam)]
        assert buys, f'2×2★ 追 3★ 帧的 2★ 副本应照买: {acts!r}'
        assert buys[0].reason == 'm2_line_member'

    def test_goal_met_member_stop_buy_1star(self):
        """矩阵行 7:达标成员(1★ 目标已持)× 同名 1★ 在售 → 追星臂
        显式停买,拒因 ``star_goal_met`` 双面可观测(计数键 + shop_rejects
        标签;旧口径 m2_stockpile 会买第二张 1★)。

        线 = 命运圣杯红A(远坂凛 need 1):瓦尔特 need 1 但其 星间旅人
        标签档表自 1 起(空板帧 0+1≥1 恒命中),序 2 场况插件臂会按
        羁绊差一判据正当买入——该臂语义 = 羁绊激活,与 W5 追星停买
        正交,不属本矩阵辖;远坂凛标签档表自 2 起,序 2 零命中。"""
        fill = _fillers(2)
        bench = [_bc('远坂凛', star=1), _bc('Archer', star=2)] \
            + [_bc(n, star=2) for n in fill]
        s, gs, st = _locked_frame(bench=bench,
                                  deployed=[Unit(char_id=_DEPLOY_ANCHOR, star=2)],
                                  gold=100, level=7,
                                  cards=(_card('远坂凛', cost=1, star=1,
                                               x=0),),
                                  comp_name='命运圣杯红A')
        acts = _decide(s)
        assert not [a for a in acts if isinstance(a, CwActionBuyCardParam)], \
            f'达标成员同名副本应显式停买: {acts!r}'
        assert st.cw4_counters.get('star_goal_met', 0) == 1, \
            'star_goal_met 拒因计数已登记(m2_stockpile 门位)'
        assert st.cw4_shop_rejects.get('远坂凛') == 'star_goal_met', \
            st.cw4_shop_rejects

    def test_goal_met_member_stop_buy_2star(self):
        """矩阵行 8:达标成员(三月七 2★ 目标已持,追查件三月七形态)×
        同名 2★ 在售 → 零臂买入,拒因标签 ``star_goal_met``。"""
        fill = _fillers(3)
        bench = [_bc(_TARGET, star=2), _bc('三月七', star=2),
                 _bc('花火', star=2), _bc('瓦尔特', star=2)] \
            + [_bc(n, star=2) for n in fill]
        s, gs, st = _locked_frame(bench=bench,
                                  deployed=[Unit(char_id=_DEPLOY_ANCHOR, star=2)],
                                  gold=100, level=7,
                                  cards=(_card('三月七',
                                               cost=3 * int(CHARACTERS['三月七'].cost),
                                               star=2, x=0),))
        acts = _decide(s)
        assert not [a for a in acts if isinstance(a, CwActionBuyCardParam)], \
            f'达标成员同名副本应显式停买: {acts!r}'
        assert st.cw4_shop_rejects.get('三月七') == 'star_goal_met', \
            st.cw4_shop_rejects

    def test_merge_pair_predicate_mechanism_full_set(self):
        """合成效果条目谓词机制全集直调形态表:恰 2 张 1★ / 2×1★ + 2★ /
        2×2★ 入集;1×1★ + 1×2★(双档各 1,任一档都凑不满 3)不入集。"""
        pairs = _shop._merge_pair_names(
            [_bc('花火', star=1), _bc('花火', star=1)],
            [Unit(char_id=_DEPLOY_ANCHOR, star=2)])
        assert '花火' in pairs, '恰 2 张 1★(经典形态)入集'
        pairs2 = _shop._merge_pair_names(
            [_bc('花火', star=1), _bc('花火', star=1),
             _bc('三月七', star=2)],
            [Unit(char_id='花火', star=2)])
        assert '花火' in pairs2, '2×1★ + 场上 2★(扩面形态)入集'
        pairs3 = _shop._merge_pair_names(
            [_bc('花火', star=2), _bc('花火', star=2)], [])
        assert '花火' in pairs3, '2×2★(2★ 档凑满进度)入集'
        pairs4 = _shop._merge_pair_names(
            [_bc('花火', star=1), _bc('花火', star=2),
             _bc('三月七', star=2)], [])
        assert '花火' not in pairs4, '1×1★ + 1×2★ 双档各 1 不入集'


class TestW4StayWindowYield:
    """停留刷窗口压牌库让位。"""

    def test_window_frame_m6_zero_fire_refresh_emits(self):
        """窗口内(refresh_warranted 真)M6 压牌库囤货臂零发射:压牌库
        候选在售帧让位刷新,买面零买入,刷新照发(付费)。"""
        base = _fillers(4)
        bench = [_bc(_TARGET, star=2), _bc('三月七', star=2),
                 _bc('花火', star=2), _bc('瓦尔特', star=2)] \
            + [_bc(n, star=2) for n in base]
        on_sale = _fillers(9, exclude=tuple(base))[0]
        s, gs, st = _locked_frame(bench=bench,
                                  deployed=[Unit(char_id=_DEPLOY_ANCHOR, star=2)],
                                  gold=100, level=7,
                                  cards=(_card(on_sale, cost=1, star=1,
                                               x=0),))
        acts = _decide(s)
        assert not [a for a in acts if isinstance(a, CwActionBuyCardParam)], \
            f'窗口帧 M6 囤货零发射: {acts!r}'
        assert st.cw4_counters.get('m6_stay_window_yield', 0) == 1, \
            '让位否决观测键已登记'
        refreshes = [a for a in acts
                     if isinstance(a, CwActionRefreshShopParam)]
        assert refreshes and refreshes[0].cost > 0, \
            f'窗口帧刷新照发: {acts!r}'

    def test_out_of_window_m6_fires_as_before(self):
        """非窗口回归:无星级目标帧(全部达标)refresh_warranted 假 →
        M6 照常发射(让位否决不误伤富余段压牌库)。"""
        base = _fillers(4)
        bench = [_bc(_TARGET, star=3), _bc('三月七', star=2),
                 _bc('花火', star=2), _bc('瓦尔特', star=2)] \
            + [_bc(n, star=2) for n in base]
        on_sale = _fillers(9, exclude=tuple(base))[0]
        s, gs, st = _locked_frame(bench=bench,
                                  deployed=[Unit(char_id=_DEPLOY_ANCHOR, star=2)],
                                  gold=100, level=7,
                                  cards=(_card(on_sale, cost=1, star=1,
                                               x=0),))
        acts = _decide(s)
        buys = [a for a in acts if isinstance(a, CwActionBuyCardParam)]
        assert buys and buys[0].reason == 'm6_stockpile', \
            f'非窗口 M6 照常发射: {acts!r}'
        assert st.cw4_counters.get('m6_stay_window_yield', 0) == 0, \
            '非窗口帧零让位否决'


class TestW11RefreshNegativeMemory:
    """刷新负结果记忆(轻量形态;统一让位优先级迭代 3.2 后记忆面 =
    金线效果条目——「目标不可买」置位分支随预测门退役,design §2.2;免费效果条目
    无条件刷,不再进入拒绝面)。"""

    def test_reject_close_sets_marker(self):
        """拒绝态关店(金线效果条目):带内可刷帧金不足(r2_budget 拒)→ 置
        会话标记(节点, 金, 席位, 星级目标键)+ 照常收店(驱动器契约:
        关店为收尾终结动作不入序列,空序列 = 纯关店帧)。"""
        bench = [_bc(_TARGET, star=2)] + _full_line_bench(jizi_star=2)[1:8]
        s, gs, st = _locked_frame(bench=bench,
                                  deployed=[Unit(char_id=_fillers(6)[5], star=2)],
                                  gold=10, level=7, cards=())
        acts = _decide(s)
        assert acts == [], f'拒绝帧照常收店(零处理动作): {acts!r}'
        assert st.refresh_blocked is not None, '负结果记忆标记置位'
        assert st.refresh_blocked[0] == (2, 1), \
            '键分量 = 生效节点序位(种子 node_pos 字段缺席,effective = hist 水位)'
        assert st.refresh_blocked[1] == 10, '键分量 = 金'
        assert st.refresh_blocked[3] == ((_TARGET, 3),), \
            '键分量 = 星级目标键(星级目标完成即键变)'
        assert st.cw4_counters.get('shop_refresh_target_unbuyable', 0) == 0, \
            '金线效果条目置位:目标可买拒因不在场(免费效果条目无条件刷已脱离拒绝面)'

    def test_reentry_same_state_skips_refresh_proposal(self):
        """拒绝态重入(无状态变化,解拦复核清 handled 重开形态):刷新
        提案跳过,按六序/关店走。"""
        bench = [_bc(_TARGET, star=2)] + _full_line_bench(jizi_star=2)[1:8]
        s, gs, st = _locked_frame(bench=bench,
                                  deployed=[Unit(char_id=_fillers(6)[5], star=2)],
                                  gold=10, level=7, cards=())
        _decide(s)
        assert st.refresh_blocked is not None
        # 重入 = visit 序号 +1 + 解拦复核清 handled 重开(生产重进形态)。
        st.cw4_segment_serial += 1
        st.shop_handled = None
        acts2 = _decide(s)
        assert acts2 == [], \
            f'无状态变化重入帧零刷新提案,按六序/关店走: {acts2!r}'
        assert st.cw4_counters.get(
            'shop_refresh_blocked_memory_skip', 0) == 1, '跳过观测键已登记'

    def test_state_change_clears_marker_and_proposal_recovers(self):
        """状态变化清标记:金变化(键分量比对)后重入,标记清除,刷新
        提案恢复发射(付费——金线闸放行效果条目)。"""
        bench = [_bc(_TARGET, star=2)] + _full_line_bench(jizi_star=2)[1:8]
        s, gs, st = _locked_frame(bench=bench,
                                  deployed=[Unit(char_id=_fillers(6)[5], star=2)],
                                  gold=10, level=7, cards=())
        _decide(s)
        assert st.refresh_blocked is not None
        st.cw4_segment_serial += 1
        st.shop_handled = None
        cw4_gs(s, gold=200)   # 金变化 → 比对键失配清标记
        acts2 = _decide(s)
        refreshes = [a for a in acts2
                     if isinstance(a, CwActionRefreshShopParam)]
        assert refreshes and refreshes[0].cost > 0, \
            f'金变化清标记后刷新提案恢复(付费): {acts2!r}'
        assert st.refresh_blocked is None, '标记已清'

    def test_extended_merge_form_refresh_at_full_bench(self):
        """合成效果条目扩面单帧:席满 + 零燃料 + 场上 2★ + 备战 1★×2 → 目标
        可买为真(旧「恰 2 张全 1★」口径该帧三条效果条目全无误拦追星刷新)。"""
        fill = _fillers(4)
        bench = [_bc(_TARGET, star=1), _bc(_TARGET, star=1),
                 _bc('三月七', star=2), _bc('花火', star=2),
                 _bc('瓦尔特', star=2)] \
            + [_bc(n, star=2) for n in fill]
        assert len(bench) == BENCH_CAPACITY
        s, gs, st = _locked_frame(bench=bench,
                                  deployed=[Unit(char_id=_TARGET, star=2)],
                                  gold=100, level=7, cards=())
        acts = _decide(s)
        refreshes = [a for a in acts
                     if isinstance(a, CwActionRefreshShopParam)]
        assert refreshes and refreshes[0].cost > 0, \
            f'扩面形态席满帧刷新应发射: {acts!r}'
