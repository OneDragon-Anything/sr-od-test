"""EchoOfWarApp 历战余响节点测试(节点级,mock + 调节点 + 断言,对齐 email_app)。

覆盖:
- ``check_task``(纯配置逻辑,不读截图):
  - 有计划 + 周限次数>0 → ``STATUS_WITH_PLAN``。
  - 无计划(``next_plan_item`` 为 None)→ ``STATUS_NO_PLAN``。
  - 有计划但周限次数耗尽(``left_times``<=0)→ ``STATUS_NO_PLAN``。
- ``check_power``(委托 ``GuideCheckPower`` 读开拓力):
  - 星际和平指南-生存索引 → ``get_power_and_qty`` 读开拓力 / 沉浸器。

fixture(screens/):
- ``星际和平指南/生存索引.webp``:星际和平指南,生存索引 tab,顶部开拓力 ``~216/300`` +
  沉浸器 ``0/12``(``生存索引-完整体力`` / ``生存索引-完整沉浸器数量`` area;小区域开拓力 OCR 有
  ±1 噪声,故下方断言用区间而非精确值)。

注:
- ``check_task`` 是纯配置逻辑节点(``is_start_node``),不读截图 —— 用 ``monkeypatch`` 替换
  ``EchoOfWarConfig.next_plan_item`` / ``EchoOfWarRunRecord.left_times`` 控制分支,
  不写 config 文件(类级 property,测试后自动还原)。
- ``check_task`` 首行 ``ctx.power_config.check_plan_run_times()`` 走真实代码路径(不再
  monkeypatch):该函数曾对空 plan_list 死循环(``while True`` 不 break),已在
  ``TrailblazePowerConfig.check_plan_run_times`` / ``EchoOfWarConfig.check_plan_finished``
  加空 list 守卫修复;本测试用空计划的 test 实例(99)跑,兼作该修复的回归守卫。
- ``check_power`` 直调 ``GuideCheckPower.get_power_and_qty(screen)`` 单测 OCR 提取(绕开 op
  ``execute()`` 框架,后者在无 running 状态的 mock harness 下不收敛);该画面已在生存索引 tab
  (左上角标题含「生存索引」),单帧即可。
- ``_use_power``(挑战,含战斗/结果/弹框)待条件(消耗周限,难 mock)。
"""

import pytest
from test.conftest import SrTestContext

from sr_od.application.echo_of_war.echo_of_war_app import EchoOfWarApp
from sr_od.application.echo_of_war.echo_of_war_config import EchoOfWarConfig
from sr_od.application.echo_of_war.echo_of_war_run_record import EchoOfWarRunRecord
from sr_od.application.trailblaze_power.trailblaze_power_app import TrailblazePowerApp
from sr_od.interastral_peace_guide.guide_check_power import GuideCheckPower


class TestEchoOfWarApp:
    """EchoOfWarApp 历战余响节点测试。"""

    def _make_op(self, test_context: SrTestContext) -> EchoOfWarApp:
        """返回已就绪的 EchoOfWarApp(check_task 不读图,无需 mock_screen)。"""
        return EchoOfWarApp(test_context)

    def test_check_task_with_plan(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """有计划 + 周限次数>0 → STATUS_WITH_PLAN。"""
        # check_task 只判 next_plan_item 是否 None(不取其属性),任意非 None 即「有计划」。
        monkeypatch.setattr(
            EchoOfWarConfig, 'next_plan_item', property(lambda self: object())
        )
        monkeypatch.setattr(EchoOfWarRunRecord, 'left_times', property(lambda self: 3))
        op = self._make_op(test_context)
        result = op.check_task()
        assert result.status == TrailblazePowerApp.STATUS_WITH_PLAN, (
            f'有计划+有次数应为 WITH_PLAN,实际 status={result.status}'
        )

    def test_check_task_no_plan(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """无计划(next_plan_item=None)→ STATUS_NO_PLAN。"""
        monkeypatch.setattr(
            EchoOfWarConfig, 'next_plan_item', property(lambda self: None)
        )
        op = self._make_op(test_context)
        result = op.check_task()
        assert result.status == TrailblazePowerApp.STATUS_NO_PLAN, (
            f'无计划应为 NO_PLAN,实际 status={result.status}'
        )

    def test_check_task_no_left_times(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """有计划但周限次数耗尽(left_times<=0)→ STATUS_NO_PLAN。"""
        monkeypatch.setattr(
            EchoOfWarConfig, 'next_plan_item', property(lambda self: object())
        )
        monkeypatch.setattr(EchoOfWarRunRecord, 'left_times', property(lambda self: 0))
        op = self._make_op(test_context)
        result = op.check_task()
        assert result.status == TrailblazePowerApp.STATUS_NO_PLAN, (
            f'次数耗尽应为 NO_PLAN,实际 status={result.status}'
        )

    def test_check_power(self, test_context: SrTestContext) -> None:
        """星际和平指南-生存索引 → get_power_and_qty 读开拓力 / 沉浸器。"""
        if not test_context.has_screen('星际和平指南', '生存索引'):
            pytest.skip('存档截图缺失:screens/星际和平指南/生存索引.webp')
        screen = test_context.load_screen('星际和平指南', '生存索引')
        op = GuideCheckPower(test_context)
        power, qty = op.get_power_and_qty(screen)
        # 不 pin 精确值:小区域开拓力文字 OCR 有 ±1 噪声(全屏 216 / 裁剪 217 同一帧);
        # 只验证提取管线通(area crop → OCR → 解析 → int),真坏了 power/qty 为 None 会触发失败。
        assert isinstance(power, int) and 0 < power <= 300, (
            f'开拓力应读出 0<≤300(fixture ~216/300),实际 {power!r}'
        )
        assert isinstance(qty, int) and 0 <= qty <= 12, (
            f'沉浸器应读出 0..12(fixture 0/12),实际 {qty!r}'
        )
