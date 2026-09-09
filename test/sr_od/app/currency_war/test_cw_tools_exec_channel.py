"""工具执行批锁面(ADR-0532):执行链 + 消耗确认通道 + 开臂分键对照。

设计出处 = 21 号稿 §3.2(工具消耗确认通道:四态登记 + 成功/部分/取消
三分支)、§5 影响面(执行 op = cw_op_tools;发射位 = mandate_v1 M7.5)、
10 号稿 §2.1(判据收编源,判据面锁在 test_cw_opening_tool_semantics)。
锁面分组:
1. 执行链锁:admitted(usable)→ plan_tool_drags 逐件计划(炉目标 =
   recycle_qualified 死库存,禁宽取;特权目标 = key 对应进阶成品);
2. 消耗确认通道锁:classify_tool_consume 三分支 + 多副本 multiset diff;
3. 建档画面 fixture 交互锁:存档备战帧(「攻略已应用」,含冶金炉/
   轮滑鞋真值,W546 批实证)→ read_equips → 计划端到端;
4. 发射位锁(T-159 迁移 C 后 = entry.emit ②③之间;原 run_mandate M7.5
   块已删,dd-027 回排特例消除):admitted 非空才发 RunTools + 执行位闩
   (mark_tools_pass_executed,发射位只读不写,与 M7 闩同型);
5. 词表锁:RunTools 入 PREP_ACTION_TYPES 白名单 + entry 条件续分类。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / 'src'))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from sr_od.application.currency_war.data.cw_synthesis import (  # noqa: E402
    recycle_qualified,
)
from sr_od.application.currency_war.kernel.cw_comps import Comp  # noqa: E402
from sr_od.application.currency_war.kernel.cw_equip_env import (  # noqa: E402
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
    ToolDragPlan,
    classify_tool_consume,
    plan_tool_drags,
    run_tool_queue,
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
        (留合成)禁入选——执行面宽取 = 误烧负操作,本锁钉死。负例并入:
        画面无死库存 icon → 计划面目标为空(执行位跳过披露),禁落点
        到任意件。"""
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
        # 负例(并入正例):画面只有炉自身 → target_pos None
        lone = plan_tool_drags(admitted, [(_FURNACE, (1800, 200), 0.9)], comp)
        assert lone and lone[0].target_pos is None

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
        # 负例(并入正例):判据拒/准入拒件不产计划(令牌 R(c) 缺档 →
        # 判据拒;执行链只消费 usable,二道门缺一不发)
        acts = _admit([_TOKEN], comp)
        assert all(not a.usable for a in acts)
        assert plan_tool_drags(acts, [(_TOKEN, (1800, 200), 0.9)], comp) == []


# ===== 1b. 多计划执行环锁(ADR-0601 §3 C3 语义重推:op 内 replan 删除——
# 首件消费后 reflow 剩余计划坐标作废,如实上报交回分发层重算,禁 op 内
# 重评准入自建队列;cancel 件丢弃不消费、无 reflow,队列余件继续)=====

class TestRunToolQueue:

    def test_queue_stops_after_first_consume_with_remaining(self):
        """消费后剩余计划作废(行为锁):双件队列首件 consumed → 停,
        返回 (1, 1, plan_stale=True)——第二件**不执行**(过期坐标拖曳 =
        误烧负操作),plan_stale 供节点 round_fail 上报(旧 replan 接管
        语义已随 C3 删除)。"""
        calls: list[str] = []

        def exec_fn(plan):
            calls.append(plan.action)
            return 'consumed'

        queue = [ToolDragPlan('furnace_single', _FURNACE, _DEAD,
                              (1800, 200), (1843, 250)),
                 ToolDragPlan('privilege_upgrade', '特权赋予卡', _UNIQUE_BASE,
                              (1768, 200), (1768, 250))]
        consumed, attempts, plan_stale = run_tool_queue(queue, exec_fn)
        assert (consumed, attempts, plan_stale) == (1, 1, True)
        assert calls == ['furnace_single'], \
            f'首件消费后剩余计划禁执行,实得 {calls}'

    def test_queue_completes_when_last_item_consumed(self):
        """末件消费 = 计划完整走完:plan_stale False(无剩余件作废)→
        节点按正常成功收口,不误报计划失效。"""
        calls: list[str] = []

        def exec_fn(plan):
            calls.append(plan.action)
            return 'consumed'

        queue = [ToolDragPlan('furnace_single', _FURNACE, _DEAD,
                              (1800, 200), (1843, 250))]
        result = run_tool_queue(queue, exec_fn)
        assert result == (1, 1, False)
        assert calls == ['furnace_single']

    def test_queue_cancel_drops_without_blocking_rest(self):
        """cancel(重试预算耗尽)件直接丢弃:画面未消费 = 无 reflow,
        队列其余坐标仍有效,继续下一件(ADR-0601 §3 语义:cancel 不触发
        计划失效;防同件原地重拖死循环的旧语义保留)。"""
        calls: list[str] = []

        def exec_fn(plan):
            calls.append(plan.action)
            return 'cancel'

        queue = [ToolDragPlan('furnace_single', _FURNACE, _DEAD,
                              (1800, 200), (1843, 250)),
                 ToolDragPlan('privilege_upgrade', '特权赋予卡', _UNIQUE_BASE,
                              (1768, 200), (1768, 250))]
        consumed, attempts, plan_stale = run_tool_queue(queue, exec_fn)
        assert (consumed, attempts, plan_stale) == (0, 2, False)
        assert len(calls) == 2

    def test_queue_partial_also_invalidates_remaining(self):
        """partial(部分消费)同样触发 reflow:剩余计划作废
        (plan_stale=True),禁把部分消费当无变化继续拖过期坐标。"""
        def exec_fn(plan):
            return 'partial'

        queue = [ToolDragPlan('furnace_single', _FURNACE, _DEAD,
                              (1800, 200), (1843, 250)),
                 ToolDragPlan('privilege_upgrade', '特权赋予卡', _UNIQUE_BASE,
                              (1768, 200), (1768, 250))]
        consumed, attempts, plan_stale = run_tool_queue(queue, exec_fn)
        assert (consumed, attempts, plan_stale) == (0, 1, True)

    def test_replan_removed_from_queue_driver(self):
        """C3 结构锁:run_tool_queue 签名无 replan_fn 参数、节点源内无
        admitted 重评调用——「重评 admitted」是策略判据在 op 内第二次
        触发,防旧 replan 形态回归。"""
        import inspect

        from sr_od.application.currency_war.operations.cw_op import (
            cw_op_tools,
        )
        sig = inspect.signature(run_tool_queue)
        assert 'replan_fn' not in sig.parameters, \
            'replan_fn 参数回归(C3 已删,计划失效改上报)'
        node_src = inspect.getsource(cw_op_tools.CwOpTools.tools_consume)
        assert 'evaluate_tool_actions(fresh_names' not in node_src, \
            '节点内 fresh owned 重评准入回归(C3 已删)'


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
    state_of(s).cw4_counters = {}
    s.last_owned_equips = list(owned)
    state_of(s).target_comp = _mk_comp([_KEY])
    return s


class TestMandateEmission:
    """T-159 迁移 C 改写(锁语义重推,非机械跟绿):发射位自 run_mandate
    M7.5 块物理移出至 entry.emit ②证明 pass 与③升档器求值位之间(审 A1
    主案:dd-027 回排使 run_mandate 内任何 RunTools 必被重排到 LevelUp
    之后 ⇒ 同帧常态下本帧从未执行)——原「run_mandate 发射」断言面随
    设计出处失效,本组改锚 emit 链;admitted 门/评估留痕/执行位闩语义
    零变更。位置/执行序行为细锁 = test_cw_prep_flag_machine。"""

    def _emit(self, s, st):
        from types import SimpleNamespace

        from sr_od.application.currency_war.kernel.cw_prep_actions import (
            PrepObservation,
        )
        # 黑板契约 = 紧缩型(仅已识别件;snapshot_from_obs 同款过滤),
        # GameState.bench 是 pad 态,禁原样传入决策面。
        obs = PrepObservation(
            state=st,
            bench_chars=[b for b in getattr(st, 'bench', [])
                         if b is not None],
            deployed_chars=[d for d in getattr(st, 'deployed', [])
                            if d is not None],
            free_bench_slots=9)
        return entry.emit(obs, SimpleNamespace(), s, None)

    # admitted 非空 → 发射 RunTools 的正面断言面由 test_cw_prep_flag_machine
    # .TestRuntoolsEmitPosition 承载(同缝位 entry.emit,发射恰一次+位次);
    # 判据全拒 → 不发的负面面由本类 test_m75_evaluated… s2 腿承载——
    # 原双锁 test_admitted_emits_runtools 已按覆盖关系表删除。

    def test_m75_evaluated_trace_and_reject_keys(self):
        """M7.5 评估即留痕锁(二十四局复盘候选⑤:评估过但拒与未评估
        不可辨):owned 快照在场 ⇒ m7_5_evaluated 计数;判据全拒帧按拟
        执行动作分键(m7_5_reject_lucky_token_pick);零条目产出帧计
        m7_5_reject_none。发射门行为不变(全拒仍不发 RunTools)。"""
        st = GameState(plane=1, round_num=3)
        s2 = _session_with([_TOKEN])   # 令牌 R(c) 缺档 → 判据全拒
        out2 = self._emit(s2, st)
        assert state_of(s2).cw4_counters.get('m7_5_evaluated') == 1
        assert state_of(s2).cw4_counters.get('m7_5_reject_lucky_token_pick') == 1
        assert not any(isinstance(e.action, RunTools) for e in out2)
        s3 = _session_with(['轮滑鞋'])   # owned 在场但无工具条目产出
        self._emit(s3, st)
        assert state_of(s3).cw4_counters.get('m7_5_evaluated') == 1
        assert state_of(s3).cw4_counters.get('m7_5_reject_none') == 1
        # 未评估帧(owned 快照空)不计 evaluated(评估帧与未评估帧可辨)
        s4 = StrategySession()
        state_of(s4).cw4_counters = {}
        s4.last_owned_equips = None
        state_of(s4).target_comp = _mk_comp([_KEY])
        self._emit(s4, st)
        assert 'm7_5_evaluated' not in state_of(s4).cw4_counters

    def test_exec_latch_blocks_reemission_same_phase(self):
        """执行位闩:mark_tools_pass_executed 置位后同 phase 不再发
        (发射位只读不写,与 M7 装备闩同型);位面推进 = 新键自动失效。"""
        s = _session_with([_FURNACE, _DEAD])
        st = GameState(plane=1, round_num=3)
        out1 = self._emit(s, st)
        assert any(isinstance(e.action, RunTools) for e in out1)
        mandate.mark_tools_pass_executed(s, st)
        out2 = self._emit(s, st)
        assert not any(isinstance(e.action, RunTools) for e in out2)
        assert state_of(s).cw4_counters.get('tools_latch_skip', 0) == 1
        st2 = GameState(plane=1, round_num=4)   # 轮次推进 → 键失效重评
        out3 = self._emit(s, st2)
        assert any(isinstance(e.action, RunTools) for e in out3)

    def test_latch_write_point_is_executor_only(self):
        """闩唯一写点在 mandate.mark_tools_pass_executed(键式 = (plane,
        round),与 run_mandate phase 同构);发射位无写点(T-159 迁移 C
        后读点随发射位迁 entry.emit,单一源守卫按新布局登记:mandate.py
        恰一写点零读点,entry.py 恰一读点零写点)。"""
        src_mandate = Path(mandate.__file__).read_text(encoding='utf-8')
        src_entry = Path(entry.__file__).read_text(encoding='utf-8')
        assert src_mandate.count('state_of(session).cw4_tools_phase') == 1
        assert src_mandate.count("'cw4_tools_phase'") == 0
        assert src_entry.count("'cw4_tools_phase'") == 1   # getattr 读点
        assert 'state_of(session).cw4_tools_phase =' not in src_entry


# ===== 5. 词表锁 =====

class TestActionVocab:

    def test_runtools_in_whitelist(self):
        assert RunTools in PREP_ACTION_TYPES

    def test_runtools_frame_stability_conditional(self):
        """RunTools = 条件续类(组合语义,画面零迁移;词表外会被发射器
        fail-closed 截断——漏登记 = 动作从未真正执行的 OpenTome 病)。"""
        assert entry.classify_frame_stability(RunTools()) == 'conditional'
        assert entry.classify_frame_stability(RunEquip()) == 'conditional'
