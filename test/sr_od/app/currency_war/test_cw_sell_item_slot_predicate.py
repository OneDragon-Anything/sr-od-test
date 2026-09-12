"""凑息/支付变现通道占位件物理门锁(T-20;T-18 同族暴露上收)。

出处:迭代详设「腾席资格面与代理收窄」(IC-1 跨通道共享谓词)+
T-18 交付报告未尽①同族暴露登记。缺陷(修复前):criteria/sell.py
``sell_for_interest`` / ``funding_support_sell`` 资格循环对占位件
(``BenchChar.is_item_slot=True``,SIFT 不可读 ⇒ char_id=''、默认 1★)
无物理门——空名不在排除集/线内、星级 1、无同名副本、注册表查无此名
⇒ bench_effect 谓词 False,门组全放行;凑息缺口帧/筹资帧占位件按
未知名保守估 3 金计入止盈贪心 → 对不可卖对象发射 SellBench(实机 =
白耗动作,与 M4 燃料通道 T-209 案发形同族;游戏真值 = 占位件无卖出
交互且无金币现值,知识锚 = board_structure.md §备战栏)。生产当前由
观察层掩蔽(identify_slots 不产占位件条目),sim 假环境经观察面直喂
可及。

本批上收:判据单一源 = ``predicates.item_slot_unsellable`` 跨通道
共享谓词,M4 燃料/凑息/支付变现三通道资格循环同门消费。锁三层:

- **行为锁(凑息)**:占位件不入资格集(先于其余资格门,任何星级),
  真燃料件照卖,无占位件帧零漂移;
- **行为锁(筹资)**:同门 + 止盈贪心不消费占位件退金(缺口可覆盖
  帧修复前用「占位件 3 金 + 真件」凑满,修复后只用真件、不足诚实短欠);
- **单一源静态锁**:mandate_v1 生产树 ``is_item_slot`` 属性读唯一
  合法居所 = 谓词本体(statefn/predicates.py);部署侧 cw_deploy_logic
  同名读在其树外(防误上面,恒 held),非本锁辖域。
"""
from __future__ import annotations

import ast
from pathlib import Path

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_game_state import (
    board_state_bridge as _bsb,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BenchChar,
    CwWorkFrame,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    sell,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    item_slot_unsellable,
    line_members,
)

_COMP = '列车同行'
_K = ('线内件',)


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _item(slot: int = 1, star: int = 1) -> BenchChar:
    """占位件(T-216 假环境同款形态):SIFT 不可读 → char_id=''、默认 1★。"""
    return BenchChar(slot=slot, char_id='', star=star, is_item_slot=True)


def _state(bench: list[BenchChar],
           deployed: list[BenchChar] | None = None) -> CwWorkFrame:
    # deployed 缺省非空板:空板帧会被空板止损守卫
    # (sell_gate.empty_board_sell_blocked,ADR-0636)先于资格循环短路,
    # 测不到本文件辖的物理门本体;plane=2 压掉 P1 血线禁令域(凑息)。
    if deployed is None:
        deployed = [_bc('前线', slot=1)]
    st = CwWorkFrame()
    st.plane = 2
    st.hp = 50
    st.bench = list(bench)
    st.deployed = list(deployed)
    return st


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
        """占位件不入资格集,同帧真燃料件照卖(修复前形态 = 两槽全入)。"""
        fuel_a, _fuel_b = _fuel_pair()
        bench = [_item(slot=1), _bc(fuel_a, slot=2)]
        slots, key = sell.sell_for_interest(
            0, bench, 5, _K, state=_bsb(_state(bench)))
        assert key == ''
        assert slots == [2]

    def test_placeholder_only_bench_honest_empty(self):
        """仅占位件可「凑」的帧 = 诚实空集(占位件槽永不入发射列)。"""
        bench = [_item(slot=1)]
        slots, key = sell.sell_for_interest(
            0, bench, 5, _K, state=_bsb(_state(bench)))
        assert slots == []
        assert key == ''

    # 「门序锁」已删(T-102,同燃料通道判):滤门禁用变异下 star=2 占位件
    # 输入仍被星门(criteria/sell.py 内 b.star != 1)同样拒——两门同为纯拒、
    # 序不可观测,锁零拦截价值;滤门回归由星=1 两锁实际拦截(变异红证)。
    # 勿以「钉门序」为由重建:无合法可观测形态。

    def test_zero_drift_without_placeholder(self):
        """零误伤对照:无占位件帧输出与既有语义逐位一致(两件全入)。"""
        fuel_a, fuel_b = _fuel_pair()
        bench = [_bc(fuel_a, slot=1), _bc(fuel_b, slot=2)]
        slots, key = sell.sell_for_interest(
            0, bench, 5, _K, state=_bsb(_state(bench)))
        assert key == ''
        assert slots == [1, 2]


# ===== 行为锁:筹资通道(funding_support_sell)=====


class TestFundingItemSlotGate:
    """筹资资格循环占位件物理门 + 止盈贪心不消费占位件退金。"""

    def test_placeholder_not_used_to_cover_gap(self):
        """缺口可覆盖帧:修复前 = 占位件(退金 3)+ 真件凑满贪心;
        修复后 = 只用真件,占位件槽不入发射列、缺口诚实短欠。"""
        fuel_a, _fuel_b = _fuel_pair()
        bench = [_item(slot=1), _bc(fuel_a, slot=2)]
        slots, key = sell.funding_support_sell(
            0, 5, bench, _K, state=_bsb(_state(bench)))
        assert key == ''
        assert slots == [2]

    def test_placeholder_only_bench_honest_empty(self):
        """仅占位件可「筹」的帧 = 诚实空集。"""
        bench = [_item(slot=1)]
        slots, key = sell.funding_support_sell(
            0, 5, bench, _K, state=_bsb(_state(bench)))
        assert slots == []
        assert key == ''

    # 「门序锁」已删(T-102,同凑息通道判):滤门禁用变异下 star=2 占位件
    # 输入仍被星门(criteria/sell.py 内 b.star != 1)同样拒——序不可观测,
    # 锁零拦截价值;滤门回归由星=1 锁实际拦截(变异红证)。

    def test_zero_drift_without_placeholder(self):
        """零误伤对照:无占位件帧输出与既有语义逐位一致。"""
        fuel_a, fuel_b = _fuel_pair()
        bench = [_bc(fuel_a, slot=1), _bc(fuel_b, slot=2)]
        slots, key = sell.funding_support_sell(
            0, 5, bench, _K, state=_bsb(_state(bench)))
        assert key == ''
        assert slots == [1, 2]


# ===== 单一源:谓词本体 + 生产树静态锁 =====


class TestItemSlotPredicateSingleSource:

    def test_predicate_truth_table(self):
        """谓词真值表:标记件真 / 无标记件假 / 鸭子缺字段防御读不误伤。"""
        assert item_slot_unsellable(
            BenchChar(slot=1, char_id='', star=1, is_item_slot=True)) is True
        assert item_slot_unsellable(
            BenchChar(slot=1, char_id='甲', star=1)) is False

        class _NoMark:
            """无 is_item_slot 字段的鸭子形态(防御读边界)。"""

        assert item_slot_unsellable(_NoMark()) is False   # type: ignore[arg-type]

    def test_mandate_v1_tree_no_inline_item_slot_reads(self):
        """mandate_v1 生产树 ``is_item_slot`` 属性读唯一居所 = 共享谓词
        本体(statefn/predicates.py)。AST 判定(注释/docstring 字样
        不误伤);新卖出通道经谓词消费,内联复制(第三处症状补丁)=
        本锁红。部署侧 cw_deploy_logic 同名读在其树外,非本锁辖域。
        """
        src_root = (Path(__file__).resolve().parents[5] / 'src' / 'sr_od'
                    / 'application' / 'currency_war'
                    / 'strategies' / 'impl' / 'mandate_v1')
        predicate_rel = 'statefn/predicates.py'
        violations: list[str] = []
        for py in sorted(src_root.rglob('*.py')):
            rel = py.relative_to(src_root).as_posix()
            if rel == predicate_rel:
                continue
            tree = ast.parse(py.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Attribute)
                        and node.attr == 'is_item_slot'):
                    violations.append(f'{rel}:L{node.lineno} '
                                      f'{type(node.value).__name__}')
        assert violations == [], (
            'mandate_v1 树出现 is_item_slot 内联读(判据单一源回潮):\n'
            + '\n'.join(violations))
