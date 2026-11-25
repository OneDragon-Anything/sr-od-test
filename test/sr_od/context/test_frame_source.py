"""帧来源信号 ``frame_source`` 单元测试。

锁的设计约定(契约正文 = ``sr_od/context/frame_source.py`` 模块 docstring):

- 缺省实时:不进 ``offline_frame()`` 时 ``frame_is_live()`` 恒 True(对局运行链与
  直调读链的测试 / 脚本读到的就是这个缺省值);
- 离线进入 / 退出:``with offline_frame():`` 内 False,退出后 True;
- 异常退出复位:块内抛异常,异常传到块外后信号已复位(不留半开的标记);
- 嵌套复位:内层退出不清外层标记,外层退出才回实时;
- 并发隔离两例(信号是上下文变量,隔离依赖「一次调用一个任务 / 一份上下文副本」,
  不是语言保证,各自锁这一点):主例 = anyio 任务组内两任务(生产 MCP 路径:同步工具在
  事件循环线程上直接执行、每条消息一个任务),一个任务在 ``offline_frame()`` 内阻塞
  (await 一个事件)、另一个同时读到 True;辅例 = 经 ``anyio.to_thread.run_sync`` 起
  同样两任务(覆盖 HTTP 路由与 SDK 将来改为线程池的情形)。
"""
from __future__ import annotations

import threading

import anyio
import pytest

from sr_od.context.frame_source import frame_is_live, offline_frame


def test_default_is_live() -> None:
    """缺省实时:不进 offline_frame() 时恒 True。"""
    assert frame_is_live() is True


def test_offline_enter_and_exit() -> None:
    """with 内 False,退出后 True。"""
    with offline_frame():
        assert frame_is_live() is False
    assert frame_is_live() is True


def test_offline_resets_on_exception() -> None:
    """异常退出复位:块内抛异常,异常传到块外后信号已复位。"""
    with pytest.raises(RuntimeError, match='boom'):
        with offline_frame():
            raise RuntimeError('boom')
    assert frame_is_live() is True


def test_offline_nested_reset() -> None:
    """嵌套:内层退出不清外层标记,外层退出才回实时。"""
    with offline_frame():
        with offline_frame():
            assert frame_is_live() is False
        assert frame_is_live() is False, '内层退出不得把外层标记也清掉'
    assert frame_is_live() is True


@pytest.mark.asyncio
async def test_concurrent_isolation_in_task_group() -> None:
    """主例(anyio 任务组,生产 MCP 路径):一任务在 offline_frame() 内阻塞,
    另一任务同时读到 True。"""
    entered = anyio.Event()
    observed: dict[str, bool] = {}

    async def offline_task() -> None:
        with offline_frame():
            entered.set()
            await anyio.sleep(0.05)
            observed['offline'] = frame_is_live()   # 自己的上下文里仍是离线

    async def live_task() -> None:
        await entered.wait()
        observed['live'] = frame_is_live()         # 别的任务的上下文里仍是实时

    async with anyio.create_task_group() as tg:
        tg.start_soon(offline_task)
        tg.start_soon(live_task)

    assert observed == {'live': True, 'offline': False}


@pytest.mark.asyncio
async def test_concurrent_isolation_via_thread() -> None:
    """辅例(anyio.to_thread.run_sync,HTTP 路由 / 线程池形态):线程里包
    offline_frame() 阻塞,另一线程同时读到 True。"""
    entered = threading.Event()
    release = threading.Event()
    observed: dict[str, bool] = {}

    def offline_thread() -> None:
        with offline_frame():
            entered.set()
            release.wait(timeout=5)
            observed['offline'] = frame_is_live()

    def live_thread() -> None:
        entered.wait(timeout=5)
        observed['live'] = frame_is_live()
        release.set()

    async with anyio.create_task_group() as tg:
        tg.start_soon(lambda: anyio.to_thread.run_sync(offline_thread))
        tg.start_soon(lambda: anyio.to_thread.run_sync(live_thread))

    assert observed == {'live': True, 'offline': False}
    assert frame_is_live() is True   # 事件循环线程的上下文未被线程里的置位影响
