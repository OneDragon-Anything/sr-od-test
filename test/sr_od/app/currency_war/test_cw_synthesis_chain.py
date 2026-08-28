"""合成执行链行为锁:plan_syntheses 纯函数 + cw_sim 合成 hook。

背景:系统此前「只囤组件从不执行合成」,ADR-0265 组件保留池的前提
「组件留作合成」永不兑现(cw_synthesis 模块 docstring / W465 装备流
分析)。本链的语义:持有组件凑齐**当前目标 comp 需求线**配方 → 装备栏
内合成(免费口径,耗金无文献记载),产物为进阶成品、不在
RESERVED_COMPONENTS——自然进入可穿池,与 ADR-0265 不对撞。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war import cw_synthesis
from sr_od.application.currency_war.cw_synthesis import (
    plan_syntheses,
    synthesis_membership,
)

POOL = 'snapshot'


@pytest.fixture()
def _run_game():
    from sr_od.application.currency_war.cw_sim import simulate_p1
    return simulate_p1


class TestPlanSyntheses:
    """纯函数语义(配方数据源 = 注册表派生图谱,K8 闭合)。"""

    def test_cross_recipe_completes(self):
        # 火力风暴潮 = 轮滑鞋 + 折叠小刀(交叉配方,cw_synthesis docstring 例)
        actions = plan_syntheses(['火力风暴潮'], ['轮滑鞋', '折叠小刀'])
        # 配方组件序以注册表 recipes 原序为准(折叠小刀在前),断言随源
        assert actions == [('火力风暴潮', ('折叠小刀', '轮滑鞋'))]

    def test_self_recipe_needs_two_copies(self):
        # 反重力皮靴 = 轮滑鞋 ×2:库存 1 件不可合成(不能用「出现即有」判)
        assert plan_syntheses(['反重力皮靴'], ['轮滑鞋']) == []
        actions = plan_syntheses(['反重力皮靴'], ['轮滑鞋', '轮滑鞋'])
        assert actions == [('反重力皮靴', ('轮滑鞋', '轮滑鞋'))]

    def test_owned_advance_deducts_demand(self):
        # 已持有同名成品 1:1 抵扣需求,不再消耗组件
        assert plan_syntheses(
            ['火力风暴潮'], ['火力风暴潮', '轮滑鞋', '折叠小刀']) == []

    def test_multiplicity_fires_repeatedly(self):
        actions = plan_syntheses(
            ['反重力皮靴', '反重力皮靴'], ['轮滑鞋'] * 4)
        assert len(actions) == 2
        assert all(a == '反重力皮靴' for a, _c in actions)

    def test_non_recipe_key_skipped(self):
        # 白昼类无常规配方(component_demand 同口径)不产生可执行合成
        assert plan_syntheses(['白昼'], ['轮滑鞋', '折叠小刀']) == []

    def test_inputs_not_mutated(self):
        owned = ['轮滑鞋', '折叠小刀']
        plan_syntheses(['火力风暴潮'], owned)
        assert owned == ['轮滑鞋', '折叠小刀']


class TestSynthesisMembershipGate:
    """方向确定性门(用户裁决:乱合成=后期缺关键装备;P1 FORM 期换线
    压注禁合成)。隶属度:目标件 1.0 / 共享件 0.5 / 无关 0;默认阈值
    1.0 = 只合目标件。"""

    def test_target_item_membership_one(self):
        assert synthesis_membership('火力风暴潮', ['火力风暴潮']) == 1.0

    def test_shared_component_membership_half(self):
        # 轮滑鞋 ∈ 火力风暴潮需求向量 → 含轮滑鞋的其他进阶(反重力皮靴
        # = 轮滑鞋×2,不在 key)= 共享件 0.5
        assert synthesis_membership('反重力皮靴', ['火力风暴潮']) == 0.5

    def test_unrelated_membership_zero(self):
        # 永动机 = 光能电池×2,与 火力风暴潮(轮滑鞋+折叠小刀)无交
        assert synthesis_membership('永动机', ['火力风暴潮']) == 0.0

    def test_no_direction_no_synthesis(self):
        # 无方向(key 空)→ 恒 0:不存在无方向合成路径
        assert synthesis_membership('火力风暴潮', []) == 0.0
        assert plan_syntheses([], ['轮滑鞋', '折叠小刀']) == []

    def test_default_floor_blocks_shared_item(self):
        # 默认阈值 1.0:候选扩扫中的共享件(0.5)被门拦下
        actions = plan_syntheses(
            ['火力风暴潮'], ['轮滑鞋'] * 2,
            candidates=['反重力皮靴'])
        assert all(a == '火力风暴潮' for a, _c in actions)
        # 显式降阈值 → 共享件可合(显式放宽,非默认)
        actions = plan_syntheses(
            ['火力风暴潮'], ['轮滑鞋'] * 4,
            membership_floor=0.5, candidates=['反重力皮靴'])
        assert any(a == '反重力皮靴' for a, _c in actions)

    def test_gate_fires_only_under_locked_intention(self, monkeypatch,
                                                    _run_game):
        # 变异法:patch plan_syntheses 恒产 1 件成品(hook 只要被调用就
        # 会留痕),断言台账中「有合成事件的轮」全部满足意向已锁线
        # (phase=='locked'∧locked_comp)——锁线门在位且无旁路。
        monkeypatch.setattr(
            cw_synthesis, 'plan_syntheses',
            lambda keys, owned: [('反重力皮靴', ())] if owned else [])
        r = _run_game(4, pool=POOL, planes=2, synthesis_chain=True)
        assert any(row['sim'].get('syntheses') for row in r.ledger), \
            '锁线门下 0 合成事件:seed 漂移或门过严,换 seed 复查'
        for row in r.ledger:
            if row['sim'].get('syntheses'):
                ist = row.get('v3_intention') or {}
                assert ist.get('phase') == 'locked' and ist.get('locked_comp')


class TestWearBasicBypass:
    """C 臂旁路:equiv_allocation.allow_basic_wear(默认关=ADR-0265 逐位
    不变;用户裁定基础件穿着可逆=卖角色取回,不构成锁死)。"""

    def test_default_off_unchanged(self):
        from sr_od.application.currency_war.cw_comps import equip_allocation
        from sr_od.application.currency_war.cw_state import BenchChar
        dep = [BenchChar(slot=1, char_id='飞霄', position_pref='front')]
        owned = ['轮滑鞋', '光能电池', '蓄能帆']
        alloc = equip_allocation(None, dep, owned, plane=1)
        assert {e for _w, e in alloc} == {'蓄能帆'}, '默认关=保留池语义不变'

    def test_bypass_wears_basic_p1(self):
        from sr_od.application.currency_war.cw_comps import equip_allocation
        from sr_od.application.currency_war.cw_state import BenchChar
        dep = [BenchChar(slot=1, char_id='飞霄', position_pref='front')]
        owned = ['轮滑鞋', '光能电池', '蓄能帆']
        alloc = equip_allocation(None, dep, owned, plane=1,
                                 allow_basic_wear=True)
        worn = {e for _w, e in alloc}
        # 基础件两两互为配方(K8 闭合图):先穿的轮滑鞋会经 ADR-0391
        # 配对守卫拦下第二件基础件光能电池(非 key 配对=误合成防护),
        # 旁路只放开保留池过滤、不放开配对守卫——两 gate 叠加是预期语义
        assert '轮滑鞋' in worn and '蓄能帆' in worn, f'得 {alloc}'
        assert '光能电池' not in worn, '配对守卫应拦第二件基础件'


class TestSimSynthesisHook:
    """cw_sim 合成执行 hook(synthesis_chain=True 点火;默认关零漂移)。"""

    def test_hook_fires_and_advance_enters_pool(self, monkeypatch, _run_game):
        # 变异法证明 hook 在位:patch plan_syntheses 恒产 1 件成品,
        # 断言 ①台账 syntheses 行出现;②成品进池(被穿或留 owned)。
        # 成品选反重力皮靴(进阶,非 RESERVED_COMPONENTS——P1 保留池
        # 过滤不拦,这正是链的设计语义)。seed 4 = 探针确认有装备发放
        # 行的最小 seed(发放面 supply 节点;发放轮可能落在 P2 段,
        # 故全账本行扫描)。
        fired: list[int] = []

        def fake(keys, owned):
            if owned and '反重力皮靴' not in owned:
                fired.append(1)
                return [('反重力皮靴', ())]
            return []

        monkeypatch.setattr(cw_synthesis, 'plan_syntheses', fake)
        r = _run_game(4, pool=POOL, planes=2, synthesis_chain=True)
        assert fired, 'hook 未被调用(st.equips 恒空?seed 漂移,换 seed)'
        assert any(row['sim'].get('syntheses') for row in r.ledger)
        have = {e for row in r.ledger
                for d in row['state']['deployed']
                for e in d.get('equips', [])}
        have |= set(r.ledger[-1]['state']['owned_equips'])
        assert '反重力皮靴' in have

    def test_chain_on_without_actions_zero_drift(self, monkeypatch, _run_game):
        # 开关开启但无可执行合成(恒返回空)→ 与默认关逐位一致
        # (零漂移锚:差异只能来自合成事件本身)。
        monkeypatch.setattr(cw_synthesis, 'plan_syntheses', lambda k, o: [])
        on = _run_game(4, pool=POOL, planes=2, synthesis_chain=True)
        off = _run_game(4, pool=POOL, planes=2)
        assert on.final_hp == off.final_hp
        assert on.hp_trail == off.hp_trail

    def test_default_off_no_synthesis_rows(self, _run_game):
        r = _run_game(0, pool=POOL, planes=1)
        assert all(not row['sim'].get('syntheses') for row in r.ledger)
