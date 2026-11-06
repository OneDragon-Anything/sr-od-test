"""stop_running 停机截图留证单测(save_screenshot 契约)。

锁定三点:
① 运行态下 save_screenshot=True → 独立抓帧一次、落证一次,
   文件名前缀 = stop_<reason>(reason 非法字符已替换),stop_source 照常记录;
② 缺省(不传/False)→ 零截图(用户主动停机行为不变);
③ 证据失败(落盘返回空串/抓帧抛错)不拦截停机,stop_source 照常收尾。
"""
from unittest.mock import MagicMock

from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunContext,
    ApplicationRunContextStateEnum,
)
from one_dragon.utils import debug_utils


def _patch_save(monkeypatch, impl):
    """桩掉证据落盘(实现走函数级导入,patch 落在 debug_utils 模块本体)。"""
    monkeypatch.setattr(debug_utils, 'save_debug_image', impl)


def _make_run_context(screenshot_img=object()) -> ApplicationRunContext:
    """真实 ApplicationRunContext + mock ctx;controller 已就绪并回帧。

    直接置 RUNNING:本测试的被测对象就是该类自身(字段属它私有);公开入口
    start_running 会取真实跨进程锁文件(文件系统副作用),测试纪律禁。
    """
    rc = ApplicationRunContext(MagicMock(name='OneDragonContext'))
    rc._run_state = ApplicationRunContextStateEnum.RUNNING
    rc.ctx.controller.is_game_window_ready = True
    rc.ctx.controller.screenshot.return_value = (0.0, screenshot_img)
    return rc


def test_stop_screenshot_evidence_taken_and_logged(monkeypatch, caplog):
    """① True → 抓帧一次 + 落证前缀含净化 reason;日志带 reason 与文件名。"""
    saved: list[str] = []

    def fake_save(image, file_name=None, prefix='', copy_screenshot=False):
        saved.append(prefix)
        return f'{prefix}_1700000000000'

    _patch_save(monkeypatch, fake_save)
    rc = _make_run_context()
    with caplog.at_level('WARNING'):
        result = rc.stop_running(reason='hook:shop_unknown_card',
                                 save_screenshot=True)
    assert saved == ['stop_hook_shop_unknown_card']   # ':' 已替换,前缀可入文件名
    assert rc.ctx.controller.screenshot.call_count == 1
    assert result.stop_source == 'hook:shop_unknown_card'
    assert any('[stop]' in r.message and 'shop_unknown_card' in r.message
               and '1700000000000' in r.message for r in caplog.records)


def test_stop_screenshot_off_by_default(monkeypatch):
    """② 缺省不传 → 不抓帧不落证(用户主动停机行为不变)。"""

    def _fail(*a, **k):  # pragma: no cover  被调用即测试红
        raise AssertionError('缺省停机不应触发截图')

    _patch_save(monkeypatch, _fail)
    rc = _make_run_context()
    result = rc.stop_running(reason='gui:hotkey')
    assert rc.ctx.controller.screenshot.call_count == 0
    assert result.stop_source == 'gui:hotkey'


def test_stop_screenshot_failure_not_blocking(monkeypatch):
    """③ 证据链失败(落盘空串/抓帧抛错)→ 停机照常收尾,reason 不丢。"""
    _patch_save(monkeypatch, lambda *a, **k: '')
    rc = _make_run_context()
    result = rc.stop_running(reason='hook:x', save_screenshot=True)
    assert result.stop_source == 'hook:x'
    assert result.finish_reason.value == 'STOPPED'

    rc2 = _make_run_context()
    rc2.ctx.controller.screenshot.side_effect = RuntimeError('窗口没了')
    result2 = rc2.stop_running(reason='hook:y', save_screenshot=True)
    assert result2.stop_source == 'hook:y'
    assert result2.finish_reason.value == 'STOPPED'
