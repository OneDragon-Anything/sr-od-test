"""工具执行批锁面(ADR-0532):执行链 + 消耗确认通道 + 开臂分键对照。

设计出处 = 21 号稿 §3.2(工具消耗确认通道:四态登记 + 成功/部分/取消
三分支)、§5 影响面(执行 op = cw_op_tools;发射位 = mandate_v1 M7.5)、
10 号稿 §2.1(判据收编源,判据面锁在 test_cw_equip_wear_semantics_21)。
锁面分组:
1. 执行链锁:admitted(usable)→ plan_tool_drags 逐件计划(炉目标 =
   recycle_qualified 死库存,禁宽取;特权目标 = key 对应进阶成品);
2. 消耗确认通道锁:classify_tool_consume 三分支 + 多副本 multiset diff;
3. 建档画面 fixture 交互锁:存档备战帧(「攻略已应用」,含冶金炉/
   轮滑鞋真值,W546 批实证)→ read_equips → 计划端到端;
4. 发射位锁:run_mandate admitted 非空才发 RunTools + 执行位闩
   (mark_tools_pass_executed,发射位只读不写,与 M7 闩同型);
5. 词表锁:RunTools 入 PREP_ACTION_TYPES 白名单 + entry 条件续分类。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / 'src'))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from sr_od.application.currency_war.data.cw_synthesis import (  # noqa: E402
    recycle_qualified,
)
from sr_od.application.currency_war.kernel.cw_comps import Comp  # noqa: E402
from sr_od.application.currency_war.kernel.cw_equip_env import (  # noqa: E402
    ToolAction,
    admitted_tool_actions,
    evaluate_tool_actions,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (  # noqa: E402
    PREP_ACTION_TYPES,
    RunEquip,
    RunTools,
)
from sr_od.application.currency_war.kernel.cw_state import GameState  # noqa: E402
from sr_od.application.currency_war.kernel.cw_strategy_session import (  # noqa: E402
    StrategySession,
)
from sr_od.application.currency_war.operations.cw_op.cw_op_tools import (  # noqa: E402
    classify_tool_consume,
    plan_tool_drags,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (  # noqa: E402
    entry,
    mandate,
)

_KEY = '火力风暴潮'        # 进阶非唯一(与 21 号稿锁面同源样本)
_PRIV = '电光履·特权'
_UNIQUE_BASE = '电光履'
_FURNACE = '冶金炉'
_TOKEN = '好运令牌'
_RQ = recycle_qualified([_KEY])
_DEAD = sorted(_RQ)[0]      # 任一死库存基础件(判据面真值域)


def _mk_comp(keys=None):
    c = Comp(name='测试线', factions=['贝洛伯格'], core_chars=['卡芙卡'],
             form_tiers={}, strength=5.0, form_difficulty='hard')
    c.key_equips = list(keys or [])
    return c


def _admit(owned, comp):
    return admitted_tool_actions(evaluate_tool_actions(owned, comp))


# ===== 1. 执行链锁:admitted → 拖曳计划 =====

class TestPlanToolDrags:

    def test_furnace_targets_dead_stock_only(self):
        """炉目标 = 死库存件(recycle_qualified 同源过滤):需求向量内件
        (留合成)禁入选——执行面宽取 = 误烧负操作,本锁钉死。"""
        comp = _mk_comp([_KEY])
        demand_ok = _KEY          # 在需求向量内的成品(非死库存)
        admitted = [a for a in _admit([_FURNACE, _DEAD], comp) if a.usable]
        assert admitted and admitted[0].action == 'furnace_single'
        hits = [(_FURNACE, (1800, 200), 0.9), (_DEAD, (1843, 250), 0.9),
                (demand_ok, (1768, 300), 0.9)]
        plans = plan_tool_drags(admitted, hits, comp)
        furnace = [p for p in plans if p.action == 'furnace_single']
        assert len(furnace) == 1
        assert furnace[0].target == _DEAD
        assert furnace[0].target_pos == (1843, 250)
        assert furnace[0].tool_pos == (1800, 200)

    def test_furnace_without_readable_target_yields_empty_plan(self):
        """判据放行但画面无死库存 icon(现读已消/reflow miss)→ 计划面
        目标为空(执行位跳过披露),禁落点到任意件。"""
        comp = _mk_comp([_KEY])
        admitted = [a for a in _admit([_FURNACE, _DEAD], comp) if a.usable]
        hits = [(_FURNACE, (1800, 200), 0.9)]   # 画面只有炉自身
        plans = plan_tool_drags(admitted, hits, comp)
        assert plans and plans[0].target_pos is None

    def test_privilege_card_targets_key_base(self):
        """特权卡目标 = key 特权件对应进阶成品(栏内拖法;21 号稿 §3.4)。"""
        comp = _mk_comp([_PRIV])
        admitted = [a for a in _admit(['特权赋予卡', _UNIQUE_BASE], comp)
                    if a.usable]
        assert admitted and admitted[0].action == 'privilege_upgrade'
        hits = [('特权赋予卡', (1800, 200), 0.9),
                (_UNIQUE_BASE, (1843, 250), 0.9)]
        plans = [p for p in plan_tool_drags(admitted, hits, comp)
                 if p.action == 'privilege_upgrade']
        assert len(plans) == 1
        assert plans[0].target == _UNIQUE_BASE

    def test_non_usable_never_planned(self):
        """判据拒/准入拒件不产计划(执行链只消费 usable,二道门缺一不发)。"""
        comp = _mk_comp([_KEY])
        acts = _admit([_TOKEN], comp)          # 令牌 R(c) 缺档 → 判据拒
        assert all(not a.usable for a in acts)
        hits = [(_TOKEN, (1800, 200), 0.9)]
        assert plan_tool_drags(acts, hits, comp) == []


# ===== 2. 消耗确认通道锁(21 号稿 §3.2 三分支)=====

class TestClassifyToolConsume:

    def test_consumed(self):
        """成功:工具消失 ∧ 目标消失 → 全量登记(含变异新件 added)。"""
        outcome, removed, added = classify_tool_consume(
            [_FURNACE, '轮滑鞋'], ['折叠小刀'], _FURNACE, '轮滑鞋')
        assert outcome == 'consumed'
        assert removed == [_FURNACE, '轮滑鞋']
        assert added == ['折叠小刀']

    def test_partial(self):
        """部分消费:目标消失但工具仍在(如只拆不耗的精密扳手形态)→
        按现读登记,消费方显影 tool_partial_consume。"""
        outcome, removed, _added = classify_tool_consume(
            [_FURNACE, '轮滑鞋'], [_FURNACE], _FURNACE, '轮滑鞋')
        assert outcome == 'partial'
        assert removed == ['轮滑鞋']

    def test_cancel(self):
        """拖曳落空:工具与目标原样 → 空登记(无账面变化)。"""
        outcome, removed, added = classify_tool_consume(
            [_FURNACE, '轮滑鞋'], [_FURNACE, '轮滑鞋'], _FURNACE, '轮滑鞋')
        assert outcome == 'cancel'
        assert removed == [] and added == []

    def test_multiset_diff(self):
        """多副本:两张特权卡消一张 → diff 逐名计数,不集合化丢副本。"""
        outcome, removed, _a = classify_tool_consume(
            ['特权赋予卡', '特权赋予卡', _UNIQUE_BASE],
            ['特权赋予卡', '电光履·特权'],
            '特权赋予卡', _UNIQUE_BASE)
        assert outcome == 'consumed'
        assert removed == ['特权赋予卡', _UNIQUE_BASE]
        assert _a == ['电光履·特权']


# ===== 3. 建档画面 fixture 交互锁(存档备战帧端到端)=====

class TestFixtureInteraction:

    def test_prep_frame_to_plan(self):
        """存档帧(「攻略已应用」:冶金炉+轮滑鞋真值,W546 批实证)→
        read_equips → 拖曳计划端到端:炉计划指向画面真死库存件。"""
        equip_dir = REPO / 'assets' / 'template' / 'currency_war' / 'equip_plaza'
        frame = None
        for p in (REPO / 'sr-od-test' / 'screens').rglob('攻略已应用.*'):
            if p.suffix in ('.png', '.webp'):
                img = cv2.imdecode(np.fromfile(str(p), np.uint8),
                                   cv2.IMREAD_COLOR)
                frame = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                break
        if frame is None or not equip_dir.is_dir():
            pytest.skip('存档帧/模板库缺失(本地资源面,缺 = 环境不全非回归)')
        from sr_od.application.currency_war.obs.cw_equipment import (
            load_equip_templates,
            read_equips,
        )
        hits = read_equips(frame, load_equip_templates(equip_dir))
        names = [n for n, _p, _s in hits]
        assert _FURNACE in names, 'fixture 真值失真:冶金炉应在该帧 owned'
        comp = _mk_comp([_KEY])
        admitted = _admit(names, comp)
        plans = [p for p in plan_tool_drags(admitted, hits, comp)
                 if p.action == 'furnace_single']
        assert plans and plans[0].tool_pos is not None
        assert plans[0].target in recycle_qualified([_KEY])
        assert plans[0].target_pos is not None


# ===== 4. 发射位锁:M7.5 RunTools + 执行位闩 =====

def _session_with(owned):
    s = StrategySession()
    s.cw4_counters = {}
    s.last_owned_equips = list(owned)
    s.target_comp = _mk_comp([_KEY])
    return s


class TestMandateEmission:

    def _frame(self, round_num: int = 3):
        return mandate.MandateFrame(
            gold=20, level=3, bench=[], deployed=[], deploy_cap=4,
            node_type=None, stop_flag=False, k_members=(),
            round_num=round_num)

    def test_admitted_emits_runtools(self):
        """admitted 非空(炉+死库存)→ 发射 RunTools;判据全拒时不发。"""
        s = _session_with([_FURNACE, _DEAD])
        st = GameState(plane=1, round_num=3)
        out = mandate.run_mandate(self._frame(), s, state=st)
        assert any(isinstance(e.action, RunTools) for e in out)
        s2 = _session_with([_TOKEN])   # 令牌 R(c) 缺档 → 全拒 → 不发
        out2 = mandate.run_mandate(self._frame(), s2, state=st)
        assert not any(isinstance(e.action, RunTools) for e in out2)

    def test_exec_latch_blocks_reemission_same_phase(self):
        """执行位闩:mark_tools_pass_executed 置位后同 phase 不再发
        (发射位只读不写,与 M7 装备闩同型);位面推进 = 新键自动失效。"""
        s = _session_with([_FURNACE, _DEAD])
        st = GameState(plane=1, round_num=3)
        out1 = mandate.run_mandate(self._frame(), s, state=st)
        assert any(isinstance(e.action, RunTools) for e in out1)
        mandate.mark_tools_pass_executed(s, st)
        out2 = mandate.run_mandate(self._frame(), s, state=st)
        assert not any(isinstance(e.action, RunTools) for e in out2)
        assert s.cw4_counters.get('tools_latch_skip', 0) == 1
        st2 = GameState(plane=1, round_num=4)   # 轮次推进 → 键失效重评
        out3 = mandate.run_mandate(self._frame(round_num=4), s, state=st2)
        assert any(isinstance(e.action, RunTools) for e in out3)

    def test_runtools_reordered_before_truncation(self):
        """dd-027 同型回排:RunTools 与开店意图同帧时,工具先于截断点。"""
        from sr_od.application.currency_war.kernel.cw_prep_actions import (
            OpenShop,
        )
        s = _session_with([_FURNACE, _DEAD])
        st = GameState(plane=1, round_num=3)
        out = mandate.run_mandate(self._frame(), s, state=st)
        kinds = [type(e.action) for e in out]
        if OpenShop in kinds and RunTools in kinds:
            assert kinds.index(RunTools) < kinds.index(OpenShop)

    def test_latch_write_point_is_executor_only(self):
        """闩唯一写点在 mandate.mark_tools_pass_executed(键式 = (plane,
        round),与 run_mandate phase 同构);发射位无写点(静态锁:
        cw4_tools_phase 只允许出现在 mandate.py 两处——写点与读点)。"""
        src = Path(mandate.__file__).read_text(encoding='utf-8')
        # 读点(getattr)+ 写点(赋值)= 恰两处;再多 = 第二写点病灶
        assert src.count("'cw4_tools_phase'") == 1   # getattr 读点
        assert src.count('session.cw4_tools_phase') == 1   # 唯一写点


# ===== 5. 词表锁 =====

class TestActionVocab:

    def test_runtools_in_whitelist(self):
        assert RunTools in PREP_ACTION_TYPES

    def test_runtools_frame_stability_conditional(self):
        """RunTools = 条件续类(组合语义,画面零迁移;词表外会被发射器
        fail-closed 截断——漏登记 = 动作从未真正执行的 OpenTome 病)。"""
        assert entry.classify_frame_stability(RunTools()) == 'conditional'
        assert entry.classify_frame_stability(RunEquip()) == 'conditional'
