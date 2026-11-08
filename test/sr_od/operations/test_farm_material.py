"""FarmMaterialOp(缺料跳转刷取)扫描/匹配/委托测试。

测试层级声明:途径行匹配为纯函数直测;缺料扫描打桩 OCR 锁「拥有<所需」
判定语义;节点流程为桩子 op 流程测试(UseTrailblazePower 打桩断言委托
参数与 skip_transport)——本 op 只做「缺料格→弹窗→途径行」的定位与
跳转,战斗链路本体由 UseTrailblazePower 的生产实测覆盖,不在此重复。

锁的内容(出处 src/sr_od/operations/farm_material.py):
- 缺料扫描:拥有<所需 判缺;无计数文本的空格跳过;全充足返回 None;
- 途径行匹配:类别主干+区域 双关键词命中预期行;敌方掉落/合成类行
  (永寿荣枝实机样本)落选返回 None;多行时按静态表预期选中,不误点
  同类别的其他区域;
- 节点委托:跳转落点核对后,UseTrailblazePower 收到 skip_transport=True、
  解析出的 mission 与 times。
"""

from __future__ import annotations

import pytest

from one_dragon.base.matcher.ocr.ocr_match_result import OcrMatchResult
from one_dragon.base.operation.operation_base import OperationResult
from sr_od.operations import farm_material as farm_material_module
from sr_od.operations.farm_material import FarmMaterialOp
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

_ASCEND: str = '光锥-等级提升'
_CHALLENGE: str = '挑战副本'


class _NoWindowFarmMaterial(FarmMaterialOp):
    """真实构造路径;测试无游戏窗口,跳过窗口前置链(同 test_upgrade_character)。"""

    def __init__(self, ctx: SrTestContext, times: int, team_num: int = 0) -> None:
        FarmMaterialOp.__init__(self, ctx, times, team_num=team_num)
        self.need_check_game_win = False  # execute 期才读,实例属性即可关掉


def _line(text: str, y: int = 655) -> OcrMatchResult:
    """构造一条弹窗途径行 OCR 结果(几何同实机样本:行高约 45,x 同列表列)。"""
    return OcrMatchResult(c=0.9, x=793, y=y, w=655, h=45, data=text)


def test_match_expected_row() -> None:
    """途径行匹配:静态表预期(类别主干+区域)双关键词定位;不可跳行落选。"""
    missions = [{'category': '拟造花萼（赤）', 'mission': '丰饶之蕾', 'region': '边缘通路'}]

    # 命中:行文案含类别主干+区域
    hit = FarmMaterialOp._match_expected_row([_line('拟造花萼【边缘通路】')], missions)
    assert hit is not None and hit.data == '拟造花萼【边缘通路】'

    # 多行时按预期选中,不误点同类别其他区域
    hit = FarmMaterialOp._match_expected_row(
        [_line('拟造花萼【太卜司】', y=632), _line('拟造花萼【边缘通路】', y=700)], missions)
    assert hit is not None and hit.data == '拟造花萼【边缘通路】'

    # 永寿荣枝实机样本:第一行敌方掉落、第二行合成,均无副本途径 → None
    none_missions = [{'category': '拟造花萼（赤）', 'mission': '丰饶之蕾', 'region': '边缘通路'}]
    assert FarmMaterialOp._match_expected_row(
        [_line('突破至均衡等级4后，丰饶孽物掉落', y=632),
         _line('「万能合成机」-材料合成', y=700)], none_missions) is None


def test_scan_lacking_cell(test_context: SrTestContext,
                           monkeypatch: pytest.MonkeyPatch) -> None:
    """缺料扫描:拥有<所需 判缺;无计数空格跳过;全充足 None。"""
    op = _NoWindowFarmMaterial(test_context, times=1)

    def _install(counts: dict[int, tuple[int, int] | None]) -> None:
        monkeypatch.setattr(FarmMaterialOp, '_read_cell_count',
                            lambda self, idx: counts.get(idx))

    # 实机样本(惊魂夜 50 突破):格2 永恒之花 0/15 缺
    _install({1: (3560, 74), 2: (0, 15), 3: (8544, 14), 4: (30, 30)})
    assert op._scan_lacking_cell() == 2

    # 全充足(含恰好相等)→ None
    _install({1: (3560, 74), 2: (15, 15), 3: (8544, 14), 4: (30, 30)})
    assert op._scan_lacking_cell() is None

    # 空格(无计数文本)跳过,继续扫后续格
    _install({1: None, 2: (0, 5), 3: (8544, 14), 4: (30, 30)})
    assert op._scan_lacking_cell() == 2


def test_delegates_to_use_trailblaze_power_with_skip_transport(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """节点流程:缺料格→弹窗→途径行→落点核对→委托免传送刷本。"""
    recorded: dict = {}

    def _fake_find_area(self, screen, s_name, a_name, *args, **kwargs):
        if (s_name, a_name) in {(_ASCEND, '文本-可提升至'), (_CHALLENGE, '挑战按钮')}:
            return self.round_success(status=a_name)
        return self.round_wait(status=f'未找到 {a_name}')

    def _fake_find_click(self, screen, s_name, a_name, *args, **kwargs):
        return self.round_success(status=a_name)

    def _stub_use_trailblaze_power(ctx, mission, team_num, plan_times,
                                   support=None, on_battle_success=None,
                                   skip_transport=False):
        recorded['mission'] = mission
        recorded['team_num'] = team_num
        recorded['plan_times'] = plan_times
        recorded['support'] = support
        recorded['skip_transport'] = skip_transport

        class _Result:
            def execute(self) -> OperationResult:
                return OperationResult(success=True, status='FARMED')

        return _Result()

    monkeypatch.setattr(FarmMaterialOp, 'round_by_find_area', _fake_find_area)
    monkeypatch.setattr(FarmMaterialOp, 'round_by_find_and_click_area', _fake_find_click)
    monkeypatch.setattr(FarmMaterialOp, '_scan_lacking_cell', lambda self: 2)
    monkeypatch.setattr(FarmMaterialOp, '_read_popup_material_name',
                        lambda self: '永恒之花')
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda image, **kwargs: [_line('拟造花萼【边缘通路】')])
    monkeypatch.setattr(farm_material_module, 'UseTrailblazePower',
                        _stub_use_trailblaze_power)

    op = _NoWindowFarmMaterial(test_context, times=2)
    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            result = op.execute()
    finally:
        reset_running_state(op.ctx, op)

    assert result.success, f'跳转刷取流程应成功结束,status={result.status}'
    assert recorded['skip_transport'] is True, '跳转路径应免传送'
    assert recorded['mission'].mission_name == '丰饶之蕾'
    assert recorded['mission'].region_name == '边缘通路'
    assert recorded['plan_times'] == 2
    assert recorded['support'] is None


def test_construction_guard(test_context: SrTestContext) -> None:
    """times 守卫:构造期显式失败。"""
    with pytest.raises(ValueError, match='times 必须 > 0'):
        _NoWindowFarmMaterial(test_context, times=0)
