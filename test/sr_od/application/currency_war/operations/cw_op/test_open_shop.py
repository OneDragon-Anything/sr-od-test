"""开商店动作原语直调体测试(实机 / sim 双通道发出语义)。

规范出处 = docs/develop/sr_od/application/currency_war/flow/action_ops.md
§1(动作 op = 机械执行 + 发出即记账,禁验证 / 重试 / 判断)+ 迭代设计
docs/develop/sr_od/application/currency_war/changes/
2026-10-16-open-shop-action-spec/design.md §2.1:

- 实机:is_success = 发出事实;定位缺失 = 唯一受阻出口
  (回执 reason=定位缺失(按钮-商店) 申报未发出);
- sim:点击经宿主 round_by_* → 端口 click_answer 受理即已发出(世界推进
  通道);屏门按点击前档名问询的失败是转移后可见性语义,不作发出判读
  ——恒按已发出簿记(reason='')。

桩宿主直驱(零真实 IO);回执断言走真实 kernel 写路径
(``note_action_receipt``),仅 ctx→容器供给口打桩(``game_state_from_ctx``,
kernel 口「无局测试桩静默 None」的正式供给点)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel import cw_game_state as gs_mod
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_obs_core import SCREEN_NAME
from sr_od.application.currency_war.operations.cw_op import cw_op_open_shop
from sr_od.application.currency_war.operations.cw_op.cw_op_open_shop import (
    open_shop,
)
from sr_od.application.currency_war.prep_actions import SHOP_OPEN_ANIM_S
from sr_od.application.currency_war.sim import cw_sim_ports


class _HostOp:
    """直调体宿主替身(桩宿主形态):round_by_* 按剧本应答并记录调用,
    两终端(round_success/round_fail)记录命中供断言。"""

    def __init__(self, click_ok: bool) -> None:
        self.click_ok = click_ok
        self.clicks: list[tuple[str, str]] = []
        self.park_calls = 0
        #: 终端命中记录 (kind, message);None = 两终端都未达。
        self.terminal: tuple[str, str] | None = None
        # 无局 ctx;回执供给由测试桩接管(见 _gs_with_supply)。
        self.ctx = SimpleNamespace(cw_match=None)

    def screenshot(self) -> object:
        return object()

    def round_by_find_and_click_area(self, screen: object,
                                     screen_name: str, area_name: str,
                                     **kw) -> SimpleNamespace:
        self.clicks.append((screen_name, area_name))
        return SimpleNamespace(is_success=self.click_ok)

    def park_cursor(self, **kw) -> None:
        self.park_calls += 1

    def round_success(self, message: str = '', **kw) -> SimpleNamespace:
        self.terminal = ('success', message)
        return SimpleNamespace(is_success=True, message=message)

    def round_fail(self, message: str = '', **kw) -> SimpleNamespace:
        self.terminal = ('fail', message)
        return SimpleNamespace(is_success=False, message=message)


class _NoSleepTime:
    """模块内 ``time`` 替身:固定等待记录不真睡(真机等待节奏非本测试辖面)。"""

    def __init__(self) -> None:
        self.skipped: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.skipped.append(seconds)


class _SimBackendStub:
    """装配占位后端(仅令 mechanical_io_allowed()=False;open_shop 在
    sim 分支不得触后端任何口,触即 AssertionError 响亮)。"""

    def screen_identity(self) -> str:
        raise AssertionError('open_shop 不得触后端读口')

    def observe(self, screen_name: str) -> object:
        raise AssertionError('open_shop 不得触后端观察')

    def visible(self, screen_name: str, area_name: str) -> bool:
        raise AssertionError('open_shop 不得触后端门问询')

    def click_answer(self, op: object, screen_name: str, area_name: str,
                     until_find_all: object, until_not_find_all: object):
        raise AssertionError('open_shop 点击腿在宿主 round_by_*,不经直调触后端')

    def advance(self, decl: object) -> None:
        raise AssertionError('open_shop 非转移集成员,无声明喂入')


@pytest.fixture
def live_io():
    """实机形态:装配槽空(防御性复位,幂等公开口)。"""
    cw_sim_ports.uninstall_sim_backend()
    yield


@pytest.fixture
def sim_installed():
    """sim 形态:装配占位后端;teardown 必卸(模块槽进程全局)。"""
    cw_sim_ports.install_sim_backend(_SimBackendStub())
    yield
    cw_sim_ports.uninstall_sim_backend()


def _gs_with_supply(monkeypatch) -> GameState:
    """空白容器 + 供给口打桩(动作回执走真实 kernel 写路径)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    monkeypatch.setattr(gs_mod, 'game_state_from_ctx', lambda ctx: gs)
    return gs


def _receipts(gs: GameState) -> list[tuple[str, str]]:
    """回执窗投影 (op, reason)(纯动作事实 shape,无成败布尔)。"""
    return [(r['op'], r['reason'])
            for r in (gs.receipts.value or [])]


def test_real_location_miss_is_the_only_blocked_exit(monkeypatch, live_io):
    """实机定位缺失 = 唯一受阻出口:点击未命中 → round_fail + 回执
    reason=定位缺失(按钮-商店);零 park 零等待(动作没发出,无后续
    机械步)。"""
    monkeypatch.setattr(cw_op_open_shop, 'time', _NoSleepTime())
    gs = _gs_with_supply(monkeypatch)
    host = _HostOp(click_ok=False)

    result = open_shop(host)

    assert host.terminal == ('fail', '定位缺失(按钮-商店)')
    assert result.is_success is False
    assert host.clicks == [('货币战争-备战', '按钮-商店')]
    assert host.park_calls == 0
    assert _receipts(gs) == [('CwOpOpenShop', '定位缺失(按钮-商店)')]


def test_real_click_emits_and_books_success(monkeypatch, live_io):
    """实机点击已发 = round_success + 回执 reason=''(已正常发出),
    park 一次 + 固定等待 ``SHOP_OPEN_ANIM_S`` 恰一次(等待不是判效)。"""
    fake_time = _NoSleepTime()
    monkeypatch.setattr(cw_op_open_shop, 'time', fake_time)
    gs = _gs_with_supply(monkeypatch)
    host = _HostOp(click_ok=True)

    result = open_shop(host)

    assert host.terminal == ('success', '开商店已发')
    assert result.is_success is True
    assert host.park_calls == 1
    assert fake_time.skipped == [SHOP_OPEN_ANIM_S]
    assert gs.receipts.value == [
        {'op': 'CwOpOpenShop', 'reason': '',
         'screen': SCREEN_NAME},
    ]


def test_sim_click_accepted_always_books_emitted(monkeypatch, sim_installed):
    """sim 恒按已发出簿记:点击应答的屏门失败(转移后可见性语义)不作
    发出判读——宿主点击腿受理即已发出,round_success + 回执 reason='';
    零 park 零等待。回归锁:旧形态此处误记受阻(复盘 ⚠ 误显根因)。"""
    monkeypatch.setattr(cw_op_open_shop, 'time', _NoSleepTime())
    gs = _gs_with_supply(monkeypatch)
    host = _HostOp(click_ok=False)

    result = open_shop(host)

    assert host.terminal == ('success', '开商店已发')
    assert result.is_success is True
    assert host.park_calls == 0
    assert _receipts(gs) == [('CwOpOpenShop', '')]
