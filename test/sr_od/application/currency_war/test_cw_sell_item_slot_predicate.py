"""凑息/支付变现通道占位件物理门锁(同族暴露上收)。

出处:迭代详设「腾席资格面与代理收窄」(IC-1 跨通道共享谓词)+
交付报告未尽①同族暴露登记。缺陷(修复前):criteria/sell.py
``sell_for_interest`` / ``funding_support_sell`` 资格循环对占位件
(备战槽占位 kind,SIFT 不可读 ⇒ char_id=''、默认 1★)
无物理门——空名不在排除集/线内、星级 1、无同名副本、注册表查无此名
⇒ bench_effect 谓词 False,门组全放行;凑息缺口帧/筹资帧占位件按
未知名保守估 3 金计入止盈贪心 → 对不可卖对象发射 CwActionSellBenchParam(实机 =
白耗动作,与 M4 燃料通道案发形同族;游戏真值 = 占位件无卖出
交互且无金币现值,知识锚 = board_structure.md §备战栏)。生产当前由
观察层掩蔽(identify_slots 不产占位件条目),sim 假环境经观察面直喂
可及。

本批上收:判据单一源 = ``predicates.item_slot_unsellable`` 跨通道
共享谓词,M4 燃料/凑息/支付变现三通道资格循环同门消费。锁两层:

- **行为锁(凑息)**:占位件不入资格集(先于其余资格门,任何星级),
  真燃料件照卖;仅占位件可「凑」的帧 = 诚实空集(占位件槽永不入
  发射列);
- **行为锁(筹资)**:同门 + 止盈贪心不消费占位件退金(缺口可覆盖
  帧只用真件、不足诚实短欠);仅占位件可「筹」的帧同 = 诚实空集。

(谓词自身 True/False 行为半由两通道锁承压,独立真值表锁退役;
占位判定唯一合法居所 = 谓词本体(statefn/predicates.py,槽位 kind 面)——
防线归 review 与代码规范。)
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box as _bsb,
)

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_game_state import BenchSlot, Unit
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    sell,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    line_members,
)

_COMP = '列车同行'
_K = ('线内件',)


def _bc(name: str, star: int = 1) -> BenchSlot:
    """容器占席条目(P4 载体迁移:身份/星级/槽号随内嵌 Unit)。"""
    return BenchSlot(kind='unit',
                     unit=Unit(char_id=name, star=star))


def _item(slot: int = 1, star: int = 1) -> BenchSlot:
    """占位件(假环境同款形态):kind 非 unit、无内嵌单位。"""
    return BenchSlot(kind='tome', unit=None)


def _state(bench: list, deployed: list | None = None) -> dict:
    # 上阵缺省非空板:空板帧会被空板止损守卫
    # (sell_gate.empty_board_sell_blocked,ADR-0636)先于资格循环短路,
    # 测不到本文件辖的物理门本体;plane=2 压掉 P1 血线禁令域(凑息)。
    # 资格循环输入 = 容器占席条目(本文件辖的载体);返回 = ``_bsb``
    # kwargs(桥配方,旧帧缺省 gold=0/hp 直写)。
    if deployed is None:
        deployed = [Unit(char_id='前线', star=1)]
    return {'plane': 2, 'hp': 50, 'bench': list(bench),
            'front_row': list(deployed)}


def _fuel_pair() -> tuple[str, str]:
    """两个线外无后台效果注册表名(注册表现查,禁手抄)。"""
    km = set(line_members(get_comp(_COMP)))
    pool = [n for n, c in CHARACTERS.items()
            if n not in km and not getattr(c, 'bench_effect', '') and c.cost]
    assert len(pool) >= 2, '注册表缺少线外无效果角色(锁前提失效)'
    return pool[0], pool[1]


# ===== 行为锁:凑息通道(sell_for_interest)=====


class TestInterestItemSlotGate:
    """凑息资格循环占位件物理门(gap 帧:gold < g*)。"""

    def test_placeholder_excluded_real_fuel_kept(self):
        """占位件不入资格集,同帧真燃料件照卖(修复前形态 = 两槽全入);
        仅占位件可「凑」的帧 = 诚实空集(占位件槽永不入发射列)。"""
        fuel_a, _fuel_b = _fuel_pair()
        bench = [_item(slot=1), _bc(fuel_a)]
        slots, key = sell.sell_for_interest(
            0, bench, 5, _K, state=_bsb(**_state(bench)))
        assert key == ''
        assert slots == [1]   # 紧缩位键(0 基)
        # 仅占位件帧 = 诚实空集
        bench_only = [_item(slot=1)]
        slots2, key2 = sell.sell_for_interest(
            0, bench_only, 5, _K, state=_bsb(**_state(bench_only)))
        assert slots2 == []
        assert key2 == ''

    # 「门序锁」已删(同燃料通道判):滤门禁用变异下 star=2 占位件
    # 输入仍被星门(criteria/sell.py 内 b.star != 1)同样拒——两门同为纯拒、
    # 序不可观测,锁零拦截价值;滤门回归由星=1 两锁实际拦截(变异红证)。
    # 勿以「钉门序」为由重建:无合法可观测形态。


# ===== 行为锁:筹资通道(funding_support_sell)=====


class TestFundingItemSlotGate:
    """筹资资格循环占位件物理门 + 止盈贪心不消费占位件退金。"""

    def test_placeholder_not_used_to_cover_gap(self):
        """缺口可覆盖帧:修复前 = 占位件(退金 3)+ 真件凑满贪心;
        修复后 = 只用真件,占位件槽不入发射列、缺口诚实短欠;仅占位件
        可「筹」的帧 = 诚实空集。"""
        fuel_a, _fuel_b = _fuel_pair()
        bench = [_item(slot=1), _bc(fuel_a)]
        slots, key = sell.funding_support_sell(
            0, 5, bench, _K, state=_bsb(**_state(bench)))
        assert key == ''
        assert slots == [1]   # 紧缩位键(0 基)
        # 仅占位件帧 = 诚实空集
        bench_only = [_item(slot=1)]
        slots2, key2 = sell.funding_support_sell(
            0, 5, bench_only, _K, state=_bsb(**_state(bench_only)))
        assert slots2 == []
        assert key2 == ''

    # 「门序锁」已删(同凑息通道判):滤门禁用变异下 star=2 占位件
    # 输入仍被星门(criteria/sell.py 内 b.star != 1)同样拒——序不可观测,
    # 锁零拦截价值;滤门回归由星=1 锁实际拦截(变异红证)。

