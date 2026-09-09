"""N2/N3/N4 规格锁(设计出处 = docs/develop/currency_war/strategy-docs/
17_stall_form_spend_authority.md §7 + ADR-0525;出口③落码前置三规格)。

- N2:kernel 围栏语义单一源——held 拒因返回(select_deployments_reasoned)
  + 单件假想查询(can_deploy_single);held 判定语义单一源在本模块,
  消费面(出口③预检/部署执行侧闭环分键)禁第二套围栏语义。
- N3:闭环分键 fuel_filler_stall_held_postbuy(执行侧现读重建回流遥测)。
- N4:授权定性 docstring 写死(「有界成本结构改善」,禁回退旧措辞)。
"""

import re
from types import SimpleNamespace as _NS

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel import cw_deploy_logic
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    DEPLOY_FENCE,
    RECIPE_FLOOR_TRAIN_CAP,
    RECIPE_FLOOR_XZ_BASE,
    can_deploy_single,
    select_deployments,
    select_deployments_reasoned,
)
from sr_od.application.currency_war.kernel.cw_launch_admission import (
    DEPLOY_FENCE as _LAUNCH_FENCE,
)
from sr_od.application.currency_war.kernel.cw_line_defs import (
    ENGINE_FACTIONS,
    RECIPE_FACTIONS,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar
from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
    record_fuel_filler_held_postbuy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)


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

    def test_fence_set_single_derived_source(self):
        """围栏集单一源守卫:kernel 存在两个 DEPLOY_FENCE 派生绑定
        (cw_deploy_logic / cw_launch_admission,注释均自称同源)——两者
        必须都等于 cw_line_defs 桥派生集(r357 收口口径)。任一侧被改
        字面量即围栏语义在 kernel 内部分叉(发射准入集 ≠ 执行侧 held
        集),本锁红。"""
        assert frozenset(RECIPE_FACTIONS | ENGINE_FACTIONS) == DEPLOY_FENCE
        assert _LAUNCH_FENCE == DEPLOY_FENCE

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
        # 门界输入从档值单一源现算(README 纪律 9):列车恰在门槛上、
        # 仙舟在基础线下——校准漂移时输入随动,红只剩分支语义失守。
        fac = {'列车同行': RECIPE_FLOOR_TRAIN_CAP,
               '仙舟': RECIPE_FLOOR_XZ_BASE - 1}
        up, held, reasons = select_deployments_reasoned(
            [_bc(n, 1)],
            deployed_cids={f'd{i}' for i in range(9)},
            deployed_fac=dict(fac),
            board=dict(fac), cap=10,
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
        """N3:登记名集内的 held 垫件 → held_postbuy 计数;登记外不计数。
        计数载体 = MandateState(N3 登记写端 = 策略层,dict 形态)。"""
        # 计数载体迁 MandateState:cw4_counters 经 state_of(桩同效);
        # 买入登记名集同迁 MandateState(N3 登记写端 = 策略层)
        sess = _NS()
        state_of(sess).cw4_fuel_filler_stall_buys = {'垫件A'}
        n = record_fuel_filler_held_postbuy(
            sess, [('垫件A', 'scatter_fence'), ('垫件B', 'cap')])
        assert n == 1
        assert state_of(sess).cw4_counters.get('fuel_filler_stall_held_postbuy') == 1

    def test_zero_when_registry_absent_or_empty(self):
        """未登记(发射位未接线/无出口③买入,登记集缺省空)⇒ 零计数
        零写入零异常;载体异常形态(None)同判(两形态兼容守卫)。"""
        sess = _NS()
        st = state_of(sess)   # 登记集与计数容器均在 MandateState 上
        assert record_fuel_filler_held_postbuy(
            sess, [('垫件A', 'scatter_fence')]) == 0
        assert 'fuel_filler_stall_held_postbuy' not in st.cw4_counters
        st.cw4_fuel_filler_stall_buys = None   # 载体异常形态:静默零不炸
        assert record_fuel_filler_held_postbuy(
            sess, [('垫件A', 'scatter_fence')]) == 0
        assert 'fuel_filler_stall_held_postbuy' not in st.cw4_counters


class TestN4AuthorityWording:

    def test_authority_wording_written_and_old_wording_absent(self):
        """N4 定性随批写死:「有界成本结构改善」在案;「无条件」旧措辞
        禁回退(定性单一源 = record_fuel_filler_held_postbuy docstring,
        ADR-0525)。"""
        doc = re.sub(r'\s+', '', record_fuel_filler_held_postbuy.__doc__ or '')
        assert '有界成本结构改善' in doc
        assert '无条件授权' not in doc, 'N4:旧「无条件授权」措辞禁回退'
        assert '净成本≤1金' in doc
