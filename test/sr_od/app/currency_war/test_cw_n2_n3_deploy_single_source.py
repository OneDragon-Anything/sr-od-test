"""N2/N3/N4 规格锁(17 号稿 §7;出口③落码前置三规格)。

- N2:kernel 围栏语义单一源——held 拒因返回(select_deployments_reasoned)
  + 单件假想查询(can_deploy_single);held 判定语义单一源在本模块,
  消费面(出口③预检/部署执行侧闭环分键)禁第二套围栏语义。
- N3:闭环分键 fuel_filler_stall_held_postbuy(执行侧现读重建回流遥测)。
- N4:授权定性 docstring 写死(「有界成本结构改善」,禁回退旧措辞)。
"""

from types import SimpleNamespace as _NS

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    DEPLOY_FENCE,
    can_deploy_single,
    select_deployments,
    select_deployments_reasoned,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar


def _bc(name: str, slot: int, star: int = 1) -> BenchChar:
    ch = CHARACTERS.get(name)
    return BenchChar(slot=slot, char_id=name, star=star,
                     faction=(ch.factions[0] if ch and ch.factions else '?'),
                     position_pref='back')


def _off_fence_name() -> str:
    """主阵营 ∉ 围栏集的注册表角色(垫件形态:与围栏集零重叠)。"""
    for n, ch in CHARACTERS.items():
        if ch.factions and ch.factions[0] not in DEPLOY_FENCE:
            return n
    raise AssertionError('注册表缺少围栏外角色(锁前提失效)')


def _fence_name() -> str:
    """主阵营 ∈ 围栏集的注册表角色(如列车同行成员)。"""
    for n, ch in CHARACTERS.items():
        if ch.factions and ch.factions[0] in DEPLOY_FENCE:
            return n
    raise AssertionError('注册表缺少围栏内角色(锁前提失效)')


class TestN2ReasonReturn:

    def test_select_deployments_compat_two_tuple(self):
        """既有消费面零破坏:不传 reasons_out 仍返回二元组。"""
        n = _off_fence_name()
        out = select_deployments([_bc(n, 1)], deployed_cids=set(),
                                 deployed_fac={}, board={}, cap=9)
        assert len(out) == 2

    def test_reasons_scatter_fence(self):
        """散牌围栏拒因:围栏外件 ∧ 配方饥饿 ∧ 非富余(vacancy=0)∧
        非成对 ⇒ held 'scatter_fence'。"""
        n = _off_fence_name()
        up, held, reasons = select_deployments_reasoned(
            [_bc(n, 1)],
            deployed_cids={f'd{i}' for i in range(10)},
            deployed_fac={}, board={}, cap=10,
            target_factions=frozenset(), target_cores=frozenset(),
            locked_factions=frozenset())
        assert held == [0] and up == []
        assert reasons.get(0) == 'scatter_fence'

    def test_reasons_rest_capacity(self):
        """人口非扩展留置拒因:围栏内件(rest 桶)∧ vacancy≤2 ⇒
        'rest_capacity'(as-built 补名,规格四拒因外的真实第五态)。"""
        n = _fence_name()
        up, held, reasons = select_deployments_reasoned(
            [_bc(n, 1)],
            deployed_cids={f'd{i}' for i in range(9)},
            deployed_fac={}, board={}, cap=10,
            target_factions=frozenset(), target_cores=frozenset())
        assert held == [0]
        assert reasons.get(0) == 'rest_capacity'

    def test_reasons_cap(self):
        n = _fence_name()
        up, held, reasons = select_deployments_reasoned(
            [_bc(n, 1)],
            deployed_cids={'d1', 'd2'},
            deployed_fac={}, board={}, cap=2,
            target_factions=frozenset(CHARACTERS[n].factions),
            target_cores=frozenset())
        assert held == [0]
        assert reasons.get(0) == 'cap'

    def test_reasons_name_dup(self):
        n = _fence_name()
        up, held, reasons = select_deployments_reasoned(
            [_bc(n, 1)],
            deployed_cids={'d1', 'd2', n},
            deployed_fac={}, board={}, cap=9,
            target_factions=frozenset(CHARACTERS[n].factions),
            target_cores=frozenset())
        assert held == [0]
        assert reasons.get(0) == 'name_dup'

    def test_reasons_recipe_floor(self):
        n = next(name for name, ch in CHARACTERS.items()
                 if ch.factions and ch.factions[0] == '列车同行')
        up, held, reasons = select_deployments_reasoned(
            [_bc(n, 1)],
            deployed_cids={f'd{i}' for i in range(9)},
            deployed_fac={'列车同行': 2, '仙舟': 1},
            board={'列车同行': 2, '仙舟': 1}, cap=10,
            target_factions=frozenset(CHARACTERS[n].factions),
            target_cores=frozenset())
        assert held == [0]
        assert reasons.get(0) == 'recipe_floor'


class TestN2SinglePieceQuery:

    def test_fenced_candidate_rejected_with_reason(self):
        """出口③预检形态:垫件(围栏外)∧ 配方饥饿 ∧ 非富余(vacancy=0)
        ⇒ 假想查询拒,拒因 scatter_fence(消费单一源,零第二套语义)。"""
        n = _off_fence_name()
        ok, why = can_deploy_single(
            _bc(n, 1), bench=[],
            deployed_cids={f'd{i}' for i in range(10)},
            deployed_fac={}, board={}, cap=10,
            target_factions=frozenset(), target_cores=frozenset(),
            locked_factions=frozenset())
        assert ok is False and why == 'scatter_fence'

    def test_filler_candidate_accepted_when_vacancy_expands(self):
        """人口扩展期(vacancy>2)垫件可落板 ⇒ (True, '')。"""
        n = _off_fence_name()
        ok, why = can_deploy_single(
            _bc(n, 1), bench=[],
            deployed_cids={'d1'},
            deployed_fac={}, board={}, cap=9,
            target_factions=frozenset(), target_cores=frozenset(),
            locked_factions=frozenset())
        assert ok is True and why == ''

    def test_unannotated_hold_reason_surfaces(self, monkeypatch):
        """缺因缺省显影(策略审查二十三跳必改项):held 而拒因字典无标注
        (未来新增 hold 路径漏标形态)⇒ 返回 'unannotated',不冒名
        'cap'。"""
        from sr_od.application.currency_war.kernel import cw_deploy_logic
        monkeypatch.setattr(
            cw_deploy_logic, 'select_deployments_reasoned',
            lambda *a, **kw: ([], [0], {}))   # held 且零标注
        n = _off_fence_name()
        ok, why = can_deploy_single(
            _bc(n, 1), bench=[],
            deployed_cids={'d1'}, deployed_fac={}, board={}, cap=9,
            target_factions=frozenset(), target_cores=frozenset(),
            locked_factions=frozenset())
        assert ok is False and why == 'unannotated'


class TestN3HeldPostbuy:

    def test_counts_for_registered_buys(self):
        """N3:登记名集内的 held 垫件 → held_postbuy 计数;登记外不计数。"""
        from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
            record_fuel_filler_held_postbuy,
        )
        sess = _NS(cw4_counters={},
                   cw4_fuel_filler_stall_buys={'垫件A'})
        n = record_fuel_filler_held_postbuy(
            sess, [('垫件A', 'scatter_fence'), ('垫件B', 'cap')])
        assert n == 1
        assert sess.cw4_counters.get('fuel_filler_stall_held_postbuy') == 1

    def test_zero_when_registry_absent_or_empty(self):
        """未登记(发射位未接线/无出口③买入)⇒ 零计数零异常。"""
        from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
            record_fuel_filler_held_postbuy,
        )
        sess = _NS(cw4_counters={})
        assert record_fuel_filler_held_postbuy(
            sess, [('垫件A', 'scatter_fence')]) == 0
        assert 'fuel_filler_stall_held_postbuy' not in sess.cw4_counters


class TestN4AuthorityWording:

    def test_authority_wording_written_and_old_wording_absent(self):
        """N4 定性随批写死:「有界成本结构改善」在案;「无条件」旧措辞
        禁回退。"""
        import re

        from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
            record_fuel_filler_held_postbuy,
        )
        doc = re.sub(r'\s+', '', record_fuel_filler_held_postbuy.__doc__ or '')
        assert '有界成本结构改善' in doc
        assert '无条件授权' not in doc, 'N4:旧「无条件授权」措辞禁回退'
        assert '净成本≤1金' in doc
