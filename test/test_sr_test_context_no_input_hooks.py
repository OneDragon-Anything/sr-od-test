"""锁:测试 ctx 构造后不持有 pynput 全局输入钩子(2026-10-24 实机事故锁)。

``OneDragonContext.__init__`` 会启动 pynput 全局 mouse/keyboard 监听 ——
Windows 上是低级输入钩子,全系统每个鼠标/键盘事件都要先过本进程的钩子线程。
测试进程 GIL 一忙(sim 整局 / 模板匹配 / OCR 后处理),钩子线程被饿 →
全系统鼠标键盘冻结而游戏画面正常(实机实测:跑测试时游戏内鼠标不可操作,
CPU/GPU 均未打满)。conftest 的 ``SrTestContext`` 在构造后立即 ``stop``;
本测试锁该约定,防止重构时静默丢掉摘钩。
"""

from test.conftest import SrTestContext


def test_test_context_holds_no_global_input_hooks(test_context: SrTestContext) -> None:
    """pynput 全局监听在测试 ctx 构造后必须是停止态(钩子已摘除)。"""
    listener = test_context.btn_listener
    assert not listener.mouse_listener.running
    assert not listener.keyboard_listener.running
