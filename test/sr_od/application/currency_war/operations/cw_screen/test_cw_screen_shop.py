"""CwScreenShop 兜底建核防御支测试(镜像锚 = cw_screen_shop.py::observe)。

锁设计约定(判据单一源 = 2026-11-19-resume-rebuild design §2.2 写入端
第三处):无对局态(独立 run_operation 调本 op)→ 先弃置残留容器再经
establish 漏斗建核,opened_via='takeover'(局外兜底 = 缺口接管语义,
与新局链写入方向禁反——传 new_game 会让防御容器永不进探针面)。

演法 = 直调 observe 节点,防御支之后的重识别面全桩:卡位点/按钮区桩给
非空(过建档复查门),模块级 sleep 桩空转,park_cursor 桩抛哨兵——哨兵
即驱动终点(防御支已执行完毕,后续识别不进),零真实识别零落盘。遥测
run 态簇 = 模块级单例,夹具前后 ``reset_run_state`` 复位(生产零调用
的测试复位正规入口)。
"""

from types import SimpleNamespace

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import FixtureController

from sr_od.application.currency_war.operations.cw_screen import cw_screen_shop
from sr_od.application.currency_war.operations.cw_screen.cw_screen_shop import (
    CwScreenShop,
)
from sr_od.application.currency_war.telemetry import state as cw_state


class _SentinelExit(Exception):
    """驱动哨兵:防御支之后的第一个机械触达点抛出,截断后续识别面。"""


class _NoSleepTime:
    """模块级 ``time`` 替身:sleep 记录 no-op、其余属性透传真模块。"""

    def __init__(self, real_module) -> None:
        self._real = real_module

    def sleep(self, seconds: float) -> None:
        pass

    def __getattr__(self, name: str):
        return getattr(self._real, name)


@pytest.fixture
def shop_env(test_context: SrTestContext,
             monkeypatch: pytest.MonkeyPatch) -> SrTestContext:
    """防御支夹具:controller 桩 + 遥测 run 态簇前后复位 + ctx 挂拆还原。"""
    cw_state.reset_run_state()
    monkeypatch.setattr(test_context, 'controller',
                        FixtureController(ctx=test_context))
    monkeypatch.setattr(test_context, 'cw_match', None, raising=False)
    monkeypatch.setattr(test_context, 'cw_selected_difficulty', None,
                        raising=False)
    yield test_context
    cw_state.reset_run_state()


def test_defensive_rebuild_passes_takeover(
        shop_env: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """无对局态防御支:discard+establish(takeover)→ 容器字段 = 缺口
    接管语义(opened_via/created_run_id/probed 一次写入)。"""
    # 防御支之后的识别/等待面全桩;park_cursor 抛哨兵截断驱动。
    monkeypatch.setattr(cw_screen_shop, 'shop_card_click_points',
                        lambda ctx: [SimpleNamespace()] * 5)
    monkeypatch.setattr(cw_screen_shop, 'area_center',
                        lambda ctx, name, screen_name=None: SimpleNamespace())
    monkeypatch.setattr(cw_screen_shop, 'time', _NoSleepTime(cw_screen_shop.time))
    monkeypatch.setattr(CwScreenShop, 'park_cursor',
                        lambda self, **kwargs: (_ for _ in ()).throw(
                            _SentinelExit()))

    op = CwScreenShop(shop_env)
    with pytest.raises(_SentinelExit):
        op.observe()

    container = shop_env.cw_match
    assert container is not None, '无对局态防御支应兜底建核'
    assert container.opened_via == 'takeover', \
        (f'局外兜底 = 缺口接管语义应写 takeover,'
         f'实际 {container.opened_via!r}')
    assert container.created_run_id == cw_state.current_run_id(), \
        '防御建核容器应经漏斗记 created_run_id'
    assert container.probed is False, '新建容器探针去重标志应缺省 False'
