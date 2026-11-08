"""FarmMaterialOp(按材料刷副本)构造期定位与委托流程测试。

测试层级声明:构造定位走真实常量 + 指南数据(零画面、零 IO——两者都是
项目内静态资产);节点流程为桩子 op 的流程测试(回大世界/UseTrailblazePower
打桩断言委托参数)——本 op 只是把「材料→副本」定位接到既有刷本 op 上,
战斗链路本体由 UseTrailblazePower 的生产实测覆盖,不在此重复。

锁的内容(出处 src/sr_od/operations/farm_material.py):
- 构造定位:天人遗垢 → 凝滞虚影·天人之形@丹鼎司;多实例材料按
  mission_index 选(信用点 index 1 = 同谐之蕾@「白日梦」酒店-梦境);
- 守卫:无映射材料 / mission_index 越界 / times<=0 / 常量-指南不同步
  → 构造期 ValueError 显式失败;
- 委托:先回大世界再 UseTrailblazePower,子 op 收到解析出的 mission 与 times。
"""

from __future__ import annotations

import pytest

from one_dragon.base.operation.operation_base import OperationResult
from sr_od.operations import farm_material as farm_material_module
from sr_od.operations.farm_material import FarmMaterialOp
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)


class _NoWindowFarmMaterial(FarmMaterialOp):
    """真实构造路径;测试无游戏窗口,跳过窗口前置链(同 test_upgrade_character)。"""

    def __init__(self, ctx: SrTestContext, material: str, times: int,
                 mission_index: int = 0, team_num: int = 0) -> None:
        FarmMaterialOp.__init__(self, ctx, material, times,
                                mission_index=mission_index, team_num=team_num)
        self.need_check_game_win = False  # execute 期才读,实例属性即可关掉


def _run_op(op: FarmMaterialOp) -> OperationResult:
    """运行态前置复位 + fast_sleep 跑完整 execute(跳过真机等待)。"""
    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            return op.execute()
    finally:
        reset_running_state(op.ctx, op)


def test_resolve_material_to_mission(test_context: SrTestContext) -> None:
    """构造定位走真实常量+指南数据:材料 → 具体副本实例。

    天人遗垢 → 凝滞虚影·天人之形@丹鼎司(character_lookup 实测链路的
    代码侧同源验证);信用点多实例时 mission_index 逐个可选。"""
    op = _NoWindowFarmMaterial(test_context, '天人遗垢', times=1)
    assert op.mission.mission_name == '天人之形'
    assert op.mission.cate.cn == '凝滞虚影'
    assert op.mission.region_name == '丹鼎司'
    assert op.mission.power == 30

    second = _NoWindowFarmMaterial(test_context, '信用点', times=1, mission_index=1)
    assert second.mission.mission_name == '同谐之蕾'
    assert second.mission.region_name == '「白日梦」酒店-梦境'


def test_construction_guards(test_context: SrTestContext,
                             monkeypatch: pytest.MonkeyPatch) -> None:
    """四类守卫全部构造期 ValueError 显式失败,不静默。"""
    with pytest.raises(ValueError, match='无实例级副本映射'):
        _NoWindowFarmMaterial(test_context, '不存在的材料', times=1)
    with pytest.raises(ValueError, match='越界'):
        _NoWindowFarmMaterial(test_context, '天人遗垢', times=1, mission_index=5)
    with pytest.raises(ValueError, match='times 必须 > 0'):
        _NoWindowFarmMaterial(test_context, '天人遗垢', times=0)
    # 常量表与指南数据不同步(常量给出指南没有的关卡)→ 指向重新生成
    monkeypatch.setattr(
        farm_material_module, 'find_missions_by_material',
        lambda name: [{'category': '凝滞虚影', 'mission': '不存在的关卡',
                       'region': '不存在区域'}])
    with pytest.raises(ValueError, match='不同步'):
        _NoWindowFarmMaterial(test_context, '天人遗垢', times=1)


def test_delegates_to_use_trailblaze_power(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """节点流程:先回大世界再委托刷本,子 op 收到解析出的 mission 与 times。"""
    recorded: dict = {}

    class _StubBackToWorld:
        def __init__(self, ctx) -> None:
            pass

        def execute(self) -> OperationResult:
            recorded['back_ran'] = True
            return OperationResult(success=True, status='BACK')

    class _StubUseTrailblazePower:
        def __init__(self, ctx, mission, team_num, plan_times,
                     support=None, on_battle_success=None) -> None:
            recorded['mission'] = mission
            recorded['team_num'] = team_num
            recorded['plan_times'] = plan_times
            recorded['support'] = support

        def execute(self) -> OperationResult:
            return OperationResult(success=True, status='FARM')

    monkeypatch.setattr(farm_material_module, 'BackToNormalWorldPlus', _StubBackToWorld)
    monkeypatch.setattr(farm_material_module, 'UseTrailblazePower', _StubUseTrailblazePower)

    op = _NoWindowFarmMaterial(test_context, '天人遗垢', times=2)
    result = _run_op(op)

    assert result.success, f'委托流程应成功结束,status={result.status}'
    assert recorded.get('back_ran') is True, '应先执行回大世界节点'
    assert recorded['mission'].mission_name == '天人之形'
    assert recorded['plan_times'] == 2
    assert recorded['team_num'] == 0
    assert recorded['support'] is None
