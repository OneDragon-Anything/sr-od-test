"""CwEquipInventoryRefresh 装备读帧刷新原语测试(单一源回归 + 分支行为)。

锁的设计约定(被测单一源 = cw_equip_inventory_refresh + 共享读函数):

- **单一源回归**:原语消费的 ``read_owned_equips_dual_key`` 与
  observe_full heavy 产物同帧逐键一致(双键派生禁第二份,出现序口径
  单一源——识别层打桩,被测对象 = 派生与组装一致性,非识别本体);
- 浮层门:合成确认浮层在场帧 → 拒写 round_fail(浮层期 owned_equips 把
  预览框误读为已入库的毒化防线),状态带「未执行:浮层在场」前缀;
- 无局(session 缺)→ 不写、data 照返回(调用方取坐标可拖,记账将恒拒单
  的 docstring 契约);
- 有局 → gs.observe 双键整表覆盖(equips + owned_equip_xy,obs 通道);
- 识别域未就绪(共享读返 None)→ 不写保现值(宁缺勿造),round_fail;
- sim 装配 → 零读零写跳过;MCP 可运行单元契约:构造仅 ctx。
"""

import inspect
import types

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    fast_sleep,
)

from one_dragon.base.operation.operation_base import OperationResult
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    game_state_of,
)
from sr_od.application.currency_war.obs import cw_observe_full
from sr_od.application.currency_war.operations.tools import cw_equip_inventory_refresh
from sr_od.application.currency_war.operations.tools.cw_equip_inventory_refresh import (
    CwEquipInventoryRefresh,
)

_PREP_FRAME: tuple[str, str] = ('货币战争-备战', 'deployed_2star')
_OVERLAY_FRAME: tuple[str, str] = ('货币战争-备战-合成确认', '合成确认浮层')
_OBS = ChannelSig(family='obs', actor='test')

#: 共享读打桩产物(同名多条出现序 + 异名条目,派生口径断言样本)。
_STUB_HITS = [
    ('量产型装甲', (1740, 210), 50),
    ('量产型装甲', (1700, 300), 48),
    ('折叠小刀', (1760, 400), 47),
]
_STUB_NAMES = ['量产型装甲', '量产型装甲', '折叠小刀']
_STUB_XY = {'量产型装甲': [(1740, 210), (1700, 300)],
            '折叠小刀': [(1760, 400)]}


def _run_op(test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch,
            frame: tuple[str, str]) -> tuple[OperationResult, CwEquipInventoryRefresh]:
    """装假控制器(单帧剧本)+ 跑刷新原语,返回(结果, op)供断言。"""
    ctrl = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    ctrl.set_phases([{'frame': frame}])
    op = CwEquipInventoryRefresh(test_context)
    with fast_sleep(op):
        result = op.run()
    return result, op


def _stub_dual_ready(monkeypatch, hits=None) -> None:
    """共享读函数打桩(原语模块命名空间;识别本体不进测试)。"""
    if hits is None:
        hits = _STUB_HITS
    names = [n for n, _p, _s in hits]
    xy: dict = {}
    for n, (cx, cy), _s in hits:
        xy.setdefault(n, []).append((int(cx), int(cy)))
    monkeypatch.setattr(cw_equip_inventory_refresh,
                        'read_owned_equips_dual_key',
                        lambda ctx, frame: (names, xy))


def test_dual_key_single_source_consistency(monkeypatch) -> None:
    """单一源回归:共享读函数产物与 observe_full heavy 产物同帧逐键一致
    (识别层同桩下两消费方派生逐键相等,禁第二份双键派生)。"""
    monkeypatch.setattr(cw_observe_full, 'ensure_portrait_templates',
                        lambda ctx: None)
    monkeypatch.setattr(cw_observe_full, 'read_game_state',
                        lambda ctx, frame, screen_name: types.SimpleNamespace(
                            gold=5))
    monkeypatch.setattr(cw_observe_full, 'read_node_sequence',
                        lambda ctx, frame: None)
    monkeypatch.setattr(cw_observe_full, 'read_shop_cards',
                        lambda ctx, frame: None)
    monkeypatch.setattr(cw_observe_full, 'ensure_equip_sift_templates',
                        lambda ctx: object())
    monkeypatch.setattr(cw_observe_full, 'ensure_equip_tm_templates',
                        lambda ctx: None)
    monkeypatch.setattr(cw_observe_full, '_area_rect',
                        lambda ctx, name, screen=None: types.SimpleNamespace(
                            x1=1620, y1=90, x2=1918, y2=710))
    monkeypatch.setattr(cw_observe_full, 'read_equips',
                        lambda frame, templates, equip_rect=None: _STUB_HITS)
    dual = cw_observe_full.read_owned_equips_dual_key(None, frame=None)
    assert dual is not None
    names, xy = dual
    out = cw_observe_full.observe_full(None, frame=None, tier='heavy',
                                       source='test')
    assert names == _STUB_NAMES == out['owned_equips']
    assert xy == _STUB_XY == out['owned_equip_xy']


def test_overlay_frame_refuses_write(test_context, monkeypatch) -> None:
    """浮层门:合成确认浮层在场帧 → 拒写 round_fail(未执行:浮层在场前缀)。"""
    result, _ = _run_op(test_context, monkeypatch, _OVERLAY_FRAME)
    assert not result.is_success
    assert '未执行:浮层在场' in (result.status or '')
    assert '合成确认浮层' in (result.status or '')


def test_no_session_readonly_returns_data(test_context, monkeypatch) -> None:
    """无局(session 缺)→ 不写、data 照返回(无局只读语义)。"""
    _stub_dual_ready(monkeypatch)
    result, _ = _run_op(test_context, monkeypatch, _PREP_FRAME)
    assert result.is_success
    assert '无局只读' in (result.status or '')
    assert result.data == {'owned_equips': _STUB_NAMES,
                           'owned_equip_xy': _STUB_XY}


def test_with_session_observes_dual_key(test_context, monkeypatch) -> None:
    """有局 → gs.observe 双键整表覆盖(obs 通道;evidence 无标记)。"""
    _stub_dual_ready(monkeypatch)
    match = types.SimpleNamespace(session=types.SimpleNamespace())
    monkeypatch.setattr(test_context, 'cw_match', match)
    gs = game_state_of(match.session)
    gs.observe(gs.equips, ['旧件'], sig=_OBS)
    gs.observe(gs.owned_equip_xy, {'旧件': [(1, 1)]}, sig=_OBS)
    result, _ = _run_op(test_context, monkeypatch, _PREP_FRAME)
    assert result.is_success
    assert gs.equips.value == _STUB_NAMES
    assert gs.owned_equip_xy.value == _STUB_XY


def test_read_not_ready_keeps_current(test_context, monkeypatch) -> None:
    """识别域未就绪(共享读返 None)→ 不写保现值 + round_fail(宁缺勿造)。"""
    monkeypatch.setattr(cw_equip_inventory_refresh,
                        'read_owned_equips_dual_key',
                        lambda ctx, frame: None)
    match = types.SimpleNamespace(session=types.SimpleNamespace())
    monkeypatch.setattr(test_context, 'cw_match', match)
    gs = game_state_of(match.session)
    gs.observe(gs.equips, ['旧件'], sig=_OBS)
    gs.observe(gs.owned_equip_xy, {'旧件': [(1, 1)]}, sig=_OBS)
    result, _ = _run_op(test_context, monkeypatch, _PREP_FRAME)
    assert not result.is_success
    assert '保现值不写' in (result.status or '')
    assert gs.equips.value == ['旧件']
    assert gs.owned_equip_xy.value == {'旧件': [(1, 1)]}


def test_sim_installed_skips(test_context, monkeypatch) -> None:
    """sim 装配 → 零读零写跳过(机械面零触及;共享读不被调)。"""
    from sr_od.application.currency_war.sim import cw_sim_ports
    monkeypatch.setattr(cw_sim_ports, 'sim_backend_installed', lambda: True)
    monkeypatch.setattr(cw_equip_inventory_refresh,
                        'read_owned_equips_dual_key',
                        lambda ctx, frame: pytest.fail('sim 态不应触发共享读'))
    result, _ = _run_op(test_context, monkeypatch, _PREP_FRAME)
    assert result.is_success
    assert 'sim' in (result.status or '')


def test_mcp_runnable_contract() -> None:
    """MCP 可运行单元契约:构造签名仅 ctx(逐字命名,零业务参数)。"""
    sig = inspect.signature(CwEquipInventoryRefresh.__init__)
    assert list(sig.parameters) == ['self', 'ctx']
