"""SrBackendContext 生命周期与就绪校验的单元测试。

测试使用 MagicMock 伪造 SrContext，避免触发真实的 onnx 模型加载。
"""

from unittest.mock import MagicMock

import pytest

from sr_od.backend.backend_context import (
    AnalyzeScreenError,
    BackendNotReadyError,
    ScreenWriteBusyError,
    SrBackendContext,
)


def _backend(ready: bool = True, controller: MagicMock | None = None) -> SrBackendContext:
    """构造一个使用伪造 ctx 的 SrBackendContext。

    Args:
        ready: ctx.ready_for_application 的取值，默认 True。
        controller: ctx.controller 的取值，默认 None。

    Returns:
        绑定了伪造 ctx 的 SrBackendContext 实例。
    """
    ctx = MagicMock()
    ctx.ready_for_application = ready
    ctx.controller = controller
    return SrBackendContext(ctx)


@pytest.mark.asyncio
async def test_start_runs_init_in_thread() -> None:
    """start() 应当在线程池中调用 ctx.init() 完成初始化。"""
    ctx = MagicMock()
    backend = SrBackendContext(ctx)
    await backend.start()
    ctx.init.assert_called_once()


@pytest.mark.asyncio
async def test_shutdown_runs_after_app_shutdown_in_thread() -> None:
    """shutdown() 应当在线程池中调用 ctx.after_app_shutdown() 释放资源。"""
    ctx = MagicMock()
    backend = SrBackendContext(ctx)
    await backend.shutdown()
    ctx.after_app_shutdown.assert_called_once()


def test_ensure_ready_raises_when_not_ready() -> None:
    """ctx 未就绪时，_ensure_ready() 应抛出 BackendNotReadyError。"""
    backend = _backend(ready=False)
    with pytest.raises(BackendNotReadyError):
        backend._ensure_ready()


def test_check_window_returns_status_no_rect() -> None:
    game_win = MagicMock(
        win_title="星穹铁道", is_win_valid=True, is_win_active=False, is_win_scale=True, win_rect=None
    )
    backend = _backend(ready=True, controller=MagicMock(game_win=game_win))
    status = backend.check_window()
    assert status.win_title == "星穹铁道"
    assert status.is_win_valid is True
    assert status.x is None


def test_check_window_with_rect() -> None:
    rect = MagicMock(x1=1, y1=2, width=3, height=4)
    game_win = MagicMock(win_title="t", is_win_valid=True, is_win_active=True, is_win_scale=True, win_rect=rect)
    backend = _backend(ready=True, controller=MagicMock(game_win=game_win))
    status = backend.check_window()
    assert (status.x, status.y, status.width, status.height) == (1, 2, 3, 4)


def test_analyze_maps_ocr_results() -> None:
    r1 = MagicMock(data="体力", x=1, y=2, w=3, h=4)
    r2 = MagicMock(data="设定", x=5, y=6, w=7, h=8)
    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = object()
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.controller = controller
    ctx.ocr_service.get_ocr_result_list.return_value = [r1, r2]
    backend = SrBackendContext(ctx)
    result = backend.analyze(include_ocr=True)
    assert [t.text for t in result.ocr_texts] == ["体力", "设定"]
    assert result.ocr_texts[0].pc_rect == [1, 2, 4, 6]   # [x1,y1,x2,y2] = 引擎框(x=1,y=2,w=3,h=4)换算


def test_analyze_raises_when_screenshot_none() -> None:
    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = None
    backend = _backend(ready=True, controller=controller)
    with pytest.raises(AnalyzeScreenError, match='截图失败'):
        backend.analyze()


def test_analyze_returns_screens_and_writes_back_on_precise(monkeypatch) -> None:
    """analyze 精准命中 → 返回 screens[0].is_precise=True,并回写 current_screen_name。"""
    import sr_od.backend.backend_context as bc
    from one_dragon.base.screen.screen_match import ScreenMatch

    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = MagicMock()
    backend = _backend(ready=True, controller=controller)

    # mock find_screen_matches 返精准
    precise = ScreenMatch(screen_name='菜单', is_precise=True, areas=[])
    monkeypatch.setattr(bc, 'find_screen_matches', lambda ctx, screen, top_n=5: [precise])
    # mock ocr_service 返空(ocr_texts 走全图 OCR)
    backend.ctx.ocr_service.get_ocr_result_list.return_value = []
    # 建档:菜单画面锁光标(pc_alt=true)
    backend.ctx.screen_loader.screen_info_map = {'菜单': MagicMock(pc_alt=True)}

    result = backend.analyze()
    assert len(result.screens) == 1
    assert result.screens[0].is_precise is True
    assert result.pc_alt is True   # 精准命中建档锁光标画面 → True
    # 回写
    backend.ctx.screen_loader.update_current_screen_name.assert_called_once_with('菜单')


def test_analyze_pc_alt_false_on_precise_unlocked_screen(monkeypatch) -> None:
    """analyze 精准命中建档 pc_alt=false 的画面 → pc_alt=False(自由光标画面)。"""
    import sr_od.backend.backend_context as bc
    from one_dragon.base.screen.screen_match import ScreenMatch

    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = MagicMock()
    backend = _backend(ready=True, controller=controller)

    precise = ScreenMatch(screen_name='邮件', is_precise=True, areas=[])
    monkeypatch.setattr(bc, 'find_screen_matches', lambda ctx, screen, top_n=5: [precise])
    backend.ctx.ocr_service.get_ocr_result_list.return_value = []
    backend.ctx.screen_loader.screen_info_map = {'邮件': MagicMock(pc_alt=False)}

    result = backend.analyze()
    assert result.screens[0].is_precise is True
    assert result.pc_alt is False


def test_analyze_offline_pc_alt_follows_archive(monkeypatch, tmp_path) -> None:
    """离线模式锁光标标记同规则:锁光标是画面建档属性,与实时/离线无关。

    离线精准命中建档 pc_alt=true 的画面 → pc_alt=True。
    """
    import cv2
    import numpy as np

    import sr_od.backend.backend_context as bc
    from one_dragon.base.screen.screen_match import ScreenMatch

    img_path = tmp_path / 'shot.png'
    cv2.imwrite(str(img_path), np.zeros((4, 4, 3), dtype=np.uint8))
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.screen_loader.screen_info_map = {'邮件': MagicMock(pc_alt=True)}
    backend = SrBackendContext(ctx)

    precise = ScreenMatch(screen_name='邮件', is_precise=True, areas=[])
    monkeypatch.setattr(bc, 'find_screen_matches', lambda ctx, screen, top_n=5: [precise])

    result = backend.analyze(screenshot=str(img_path))
    assert result.pc_alt is True


def test_analyze_no_precise_does_not_write_back(monkeypatch) -> None:
    """analyze 无精准(模糊 top_n)→ 不回写 current_screen_name。"""
    import sr_od.backend.backend_context as bc
    from one_dragon.base.screen.screen_match import ScreenMatch

    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = MagicMock()
    backend = _backend(ready=True, controller=controller)

    fuzzy = ScreenMatch(screen_name='某画面', is_precise=False, areas=[])
    monkeypatch.setattr(bc, 'find_screen_matches', lambda ctx, screen, top_n=5: [fuzzy])
    backend.ctx.ocr_service.get_ocr_result_list.return_value = []

    result = backend.analyze()
    assert result.screens[0].is_precise is False
    assert result.pc_alt is False   # 模糊候选未确认画面 → 恒 False
    backend.ctx.screen_loader.update_current_screen_name.assert_not_called()


def test_analyze_exception_no_writeback(monkeypatch) -> None:
    """匹配中途异常 → 抛 AnalyzeScreenError,不回写。"""
    import sr_od.backend.backend_context as bc

    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = MagicMock()
    backend = _backend(ready=True, controller=controller)

    def boom(ctx, screen, top_n=5):
        raise RuntimeError('ocr boom')
    monkeypatch.setattr(bc, 'find_screen_matches', boom)

    with pytest.raises(AnalyzeScreenError, match='ocr boom'):
        backend.analyze()
    backend.ctx.screen_loader.update_current_screen_name.assert_not_called()


# (2026-09-14 瘦身:原 start_run/query_status/stop 三条 mock 委托测试删除——
#  与 test_run_slot.py 的 SrBackendContext 委托族逐条重复(纪律 7 跨文件择一);
#  后者用真 run_slot 走全链,行为层覆盖转发事实。)


def test_list_applications_no_refresh(monkeypatch) -> None:
    """list_applications 是只读路径,不应调用 _refresh_runtime_config。"""
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.standalone_app_config.active_app_id = ''
    ctx.standalone_app_config.app_list = []
    group_config = MagicMock()
    group_config.app_list = []
    ctx.app_group_manager.get_one_dragon_group_config.return_value = group_config
    ctx.run_context.is_app_registered.return_value = False
    ctx.run_context.default_group_apps = []
    ctx.current_instance_idx = 0
    backend = SrBackendContext(ctx)

    called: list = []
    monkeypatch.setattr(backend, '_refresh_runtime_config', lambda: called.append(True))

    result = backend.list_applications()
    assert result.applications == []
    assert called == []                          # 只读路径不刷新配置


# (2026-09-03 攻击性排查:原 test_close_game_delegates 删除——与
#  test_close_game.py::test_close_game_delegates_and_returns_text 逐字重复
#  (纪律 7 跨文件择一;独立文件另有 not-ready 异常门更全)。)


def test_analyze_save_image_persists_and_returns_path(monkeypatch) -> None:
    """analyze(save_image=True) 实时模式:存盘 + screenshot_path 回传路径。"""
    import numpy as np

    import sr_od.backend.backend_context as bc

    saved_args: list = []

    def fake_save(image):
        saved_args.append(image)
        return '/tmp/fake_screenshot.png'

    monkeypatch.setattr(bc, '_save_screenshot', fake_save)
    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = np.zeros((4, 4, 3), dtype=np.uint8)
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.controller = controller
    ctx.ocr_service.get_ocr_result_list.return_value = []
    backend = SrBackendContext(ctx)
    result = backend.analyze(save_image=True)
    assert result.screenshot_path == '/tmp/fake_screenshot.png'
    assert len(saved_args) == 1


def test_analyze_save_image_false_does_not_persist(monkeypatch) -> None:
    """analyze() 默认 save_image=False:不存盘,screenshot_path=None。"""
    import sr_od.backend.backend_context as bc

    called: list = []
    monkeypatch.setattr(bc, '_save_screenshot', lambda img: called.append(img) or '/tmp/x.png')
    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = object()
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.controller = controller
    ctx.ocr_service.get_ocr_result_list.return_value = []
    backend = SrBackendContext(ctx)
    result = backend.analyze()
    assert result.screenshot_path is None
    assert called == []


def test_analyze_offline_ignores_save_image(monkeypatch, tmp_path) -> None:
    """analyze(screenshot=path) 离线模式:save_image 被忽略,screenshot_path=None。"""
    import cv2
    import numpy as np

    import sr_od.backend.backend_context as bc

    called: list = []
    monkeypatch.setattr(bc, '_save_screenshot', lambda img: called.append(img) or '/tmp/x.png')
    img_path = tmp_path / 'shot.png'
    cv2.imwrite(str(img_path), np.zeros((4, 4, 3), dtype=np.uint8))
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.ocr_service.get_ocr_result_list.return_value = []
    backend = SrBackendContext(ctx)
    result = backend.analyze(screenshot=str(img_path), save_image=True)
    assert result.screenshot_path is None
    assert called == []


def test_analyze_save_image_capture_fails_no_path() -> None:
    """实时捕获失败(get_screenshot None)→ 抛 AnalyzeScreenError。"""
    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = None
    backend = _backend(ready=True, controller=controller)
    with pytest.raises(AnalyzeScreenError, match='截图失败'):
        backend.analyze(save_image=True)


def test_analyze_save_image_then_ocr_fail_raises_with_path(monkeypatch) -> None:
    """存盘成功但后续异常 → 抛 AnalyzeScreenError,已存路径带进消息(排障不丢)。

    include_ocr=True 才走散落 OCR 回传(include_ocr=False 时散落 OCR 不回传,
    OCR 异常只可能来自画面匹配链路,同样兜成异常)。
    """
    import numpy as np

    import sr_od.backend.backend_context as bc

    monkeypatch.setattr(bc, '_save_screenshot', lambda img: '/tmp/fake.png')
    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = np.zeros((4, 4, 3), dtype=np.uint8)
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.controller = controller
    ctx.ocr_service.get_ocr_result_list.side_effect = RuntimeError('ocr boom')
    backend = SrBackendContext(ctx)
    with pytest.raises(AnalyzeScreenError, match=r'ocr boom.*fake\.png'):
        backend.analyze(save_image=True, include_ocr=True)


def test_analyze_include_ocr_default_off(monkeypatch) -> None:
    """include_ocr=False(默认)→ 散落 OCR 不回传(ocr_texts 恒空)。"""
    import numpy as np

    import sr_od.backend.backend_context as bc

    monkeypatch.setattr(bc, '_save_screenshot', lambda img: '/tmp/fake.png')
    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = np.zeros((4, 4, 3), dtype=np.uint8)
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.controller = controller
    ctx.ocr_service.get_ocr_result_list.return_value = []
    backend = SrBackendContext(ctx)
    result = backend.analyze()
    assert result.ocr_texts == []


# ---------- analyze extras(画面额外识别器)----------

def _precise_analyze_backend(monkeypatch, screen_name: str) -> SrBackendContext:
    """构造一个 analyze 精准命中 ``screen_name`` 的 backend(mock find_screen_matches + OCR)。"""
    from one_dragon.base.screen.screen_match import ScreenMatch

    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = MagicMock()
    backend = _backend(ready=True, controller=controller)

    precise = ScreenMatch(screen_name=screen_name, is_precise=True, areas=[])
    monkeypatch.setattr(
        'sr_od.backend.backend_context.find_screen_matches',
        lambda ctx, screen, top_n=5: [precise],
    )
    backend.ctx.ocr_service.get_ocr_result_list.return_value = []
    return backend


def test_analyze_extras_filled_on_precise_with_recognizer(monkeypatch) -> None:
    """精准命中 + 该画面有 recognizer → extras 填 recognizer 返回的 dict。"""
    import sr_od.backend.backend_context as bc

    backend = _precise_analyze_backend(monkeypatch, '货币战争-备战')

    fake_recognizer = MagicMock()
    fake_recognizer.recognize.return_value = {'gold': 50, 'phase': [1, 3]}
    monkeypatch.setattr(bc, 'get_recognizer', lambda ctx, name: fake_recognizer)

    result = backend.analyze()
    assert result.extras == {'gold': 50, 'phase': [1, 3]}
    fake_recognizer.recognize.assert_called_once()


def test_analyze_extras_none_when_recognizer_raises(monkeypatch) -> None:
    """recognizer 抛异常 → extras=None,analyze 仍正常返回主结果(错误隔离)。"""
    import sr_od.backend.backend_context as bc

    backend = _precise_analyze_backend(monkeypatch, '货币战争-备战')

    fake_recognizer = MagicMock()
    fake_recognizer.recognize.side_effect = RuntimeError('recognizer boom')
    monkeypatch.setattr(bc, 'get_recognizer', lambda ctx, name: fake_recognizer)

    result = backend.analyze()
    assert result.screens[0].is_precise is True   # 主结果(OCR + 匹配)照常
    assert result.extras is None             # recognizer 异常被兜成 None


def test_analyze_extras_none_when_no_recognizer(monkeypatch) -> None:
    """精准命中但该画面无注册 recognizer → extras=None(get_recognizer 返 None)。"""
    import sr_od.backend.backend_context as bc

    backend = _precise_analyze_backend(monkeypatch, '某无识别器画面')
    monkeypatch.setattr(bc, 'get_recognizer', lambda ctx, name: None)

    result = backend.analyze()
    assert result.extras is None


def test_analyze_extras_none_when_no_precise(monkeypatch) -> None:
    """无精准命中(模糊 top_n)→ 不跑 recognizer,extras=None。"""
    from one_dragon.base.screen.screen_match import ScreenMatch

    controller = MagicMock()
    controller.is_game_window_ready = True
    controller.get_screenshot.return_value = MagicMock()
    backend = _backend(ready=True, controller=controller)

    fuzzy = ScreenMatch(screen_name='某画面', is_precise=False, areas=[])
    monkeypatch.setattr(
        'sr_od.backend.backend_context.find_screen_matches',
        lambda ctx, screen, top_n=5: [fuzzy],
    )
    backend.ctx.ocr_service.get_ocr_result_list.return_value = []

    result = backend.analyze()
    assert result.extras is None


def test_analyze_extras_none_when_recognizer_returns_non_serializable(monkeypatch) -> None:
    """recognizer 返回非 JSON 可序列化值 → json.dumps 校验拦下 → extras=None(json 守卫)。"""
    import sr_od.backend.backend_context as bc

    backend = _precise_analyze_backend(monkeypatch, '货币战争-备战')

    class _NotJson:
        pass

    fake_recognizer = MagicMock()
    fake_recognizer.recognize.return_value = {'bad': _NotJson()}   # 不可 JSON 序列化
    monkeypatch.setattr(bc, 'get_recognizer', lambda ctx, name: fake_recognizer)

    result = backend.analyze()
    assert result.extras is None             # json.dumps 抛 → 兜成 None



def test_get_screen_detail_wraps_not_found_with_guidance() -> None:
    """画面名未找到统一包装:ScreenInfoError 文案含示例名单 + list_screen_names 指路。

    backend 层包装文案拼装(示例名单 sorted[:10] / 指路句 / 原始错误)的哨兵:
    MCP 层测试 mock 了 backend 方法,拼装逻辑在此直测。
    """
    from sr_od.backend.backend_context import ScreenInfoError

    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.screen_loader.get_screen.side_effect = Exception('未找到画面: 不存在的画面')
    ctx.screen_loader.screen_info_list = [MagicMock(screen_name='主界面'),
                                          MagicMock(screen_name='邮件')]
    backend = SrBackendContext(ctx)
    with pytest.raises(ScreenInfoError) as exc_info:
        backend.get_screen_detail('不存在的画面')
    msg = str(exc_info.value)
    assert '画面名未找到: 不存在的画面' in msg
    assert '主界面' in msg and '邮件' in msg  # 示例名单进文案
    assert 'list_screen_names' in msg  # 指路句进文案
    assert '未找到画面: 不存在的画面' in msg  # 原始错误保留


def test_goto_screen_stop_interrupted_returns_scene(monkeypatch):
    """停机守卫拦截(goto_screen 未豁免,真实可达主路径)转 arrived=False 中断结果,带现场。

    goto_screen 连点可达 max_steps=30 次,不做 stop_guard_exemption——停机后
    「零游戏输入」不变式优先。拦截转结构化结果而非异常:agent 拿
    current_screen/steps 仍可排障(锁 stop_guard 幽灵输入事故同族的故障形态)。
    """
    from one_dragon.base.controller.stop_guard import StopRunInterrupted
    from sr_od.backend.backend_context import SrBackendContext
    from sr_od.backend.schemas import GotoScreenResult

    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.controller.is_game_window_ready = True
    ctx.controller.get_screenshot.return_value = MagicMock(name='image')
    ctx.controller.click.side_effect = StopRunInterrupted('停机')
    ctx.screen_loader.screen_info_list = [MagicMock(screen_name='邮件')]
    ctx.screen_loader.get_screen_route.return_value.can_go = True
    ctx.screen_loader.get_screen_route.return_value.node_list = [MagicMock(from_area='邮件按钮', to_screen='邮件')]
    ctx.screen_loader.get_screen.return_value.pc_alt = False
    ctx.screen_loader.get_area.return_value.pc_alt = False
    backend = SrBackendContext(ctx)
    monkeypatch.setattr('sr_od.backend.backend_context.screen_utils',
                        MagicMock(get_match_screen_name=lambda c, i: '主界面'))
    monkeypatch.setattr(backend, '_find_area_click_point',
                        lambda image, screen_info, area: MagicMock(name='point'))

    result = backend.goto_screen('邮件')
    assert isinstance(result, GotoScreenResult)
    assert result.arrived is False
    assert '停机中断' in result.reason
    assert result.current_screen == '主界面'  # 识别确认的所在画面(现场)
    assert result.steps == []  # 首次点击即被拦,尚无完成步骤


# ---------- 画面档案写档互斥(fail-fast,防 merged 缓存并发重写互相覆盖)----------

def _screen_write_backend() -> tuple[SrBackendContext, MagicMock, MagicMock]:
    """构造写档互斥测试用 backend:mock ctx + 可配置的 screen_info。

    screen_info.area_list 为真实 list(len() 可用),upsert_area 默认返 'inserted'。
    """
    ctx = MagicMock()
    ctx.ready_for_application = True
    ctx.screen_loader.screen_info_list = []
    backend = SrBackendContext(ctx)
    screen_info = MagicMock()
    screen_info.area_list = [MagicMock()]
    screen_info.upsert_area.return_value = 'inserted'
    ctx.screen_loader.get_screen.return_value = screen_info
    return backend, ctx, screen_info


def test_screen_write_mutex_concurrent_fail_fast() -> None:
    """并发写档 fail-fast:一路写档进行中时,其余写档请求立即失败并提示等待重试。

    用户裁定(2026-11-24):写档互斥语义=快速失败非排队。进行中的
    upsert_screen_area(卡在 save_screen 模拟 merged 重写耗时)须拦住并发到达的
    upsert / delete_screen_area / create_screen(三工具全覆盖),拒绝即返回、
    不等待持锁方完成;文案含「正在被修改」「等待重试」。锁释放后(正常完成)
    后续写档恢复正常。
    """
    import threading

    backend, ctx, screen_info = _screen_write_backend()
    entered_save = threading.Event()
    release_save = threading.Event()

    def slow_save(_screen_info):
        entered_save.set()          # 持锁方已进锁内、卡在 merged 重写处
        release_save.wait(timeout=5)
    ctx.screen_loader.save_screen.side_effect = slow_save

    winner_results: list = []

    def winner() -> None:
        winner_results.append(
            backend.upsert_screen_area('邮件', '标题', [1, 1, 2, 2]))

    t_winner = threading.Thread(target=winner)
    t_winner.start()
    assert entered_save.wait(timeout=5), '持锁方未进入 save_screen'

    # —— 并发 upsert(另线程):立即失败,不排队等持锁方 ——
    busy_errors: list[Exception] = []

    def concurrent_upsert() -> None:
        try:
            backend.upsert_screen_area('邮件', '标题', [3, 3, 4, 4])
            busy_errors.append(AssertionError('并发写档不应成功'))
        except Exception as e:  # noqa: BLE001 线程内捕获转断言
            busy_errors.append(e)

    t_loser = threading.Thread(target=concurrent_upsert)
    t_loser.start()
    t_loser.join(timeout=5)
    assert not t_loser.is_alive(), '并发写档被排队阻塞(应为快速失败)'
    assert len(busy_errors) == 1
    assert isinstance(busy_errors[0], ScreenWriteBusyError)
    assert '正在被修改' in str(busy_errors[0])
    assert '等待重试' in str(busy_errors[0])

    # —— 并发 delete / create(主线程):同受互斥拦下(跨工具互斥面) ——
    with pytest.raises(ScreenWriteBusyError, match='正在被修改'):
        backend.delete_screen_area('邮件', '标题')
    with pytest.raises(ScreenWriteBusyError, match='正在被修改'):
        backend.create_screen('mail', '邮件')

    # —— 持锁方正常完成后锁已释放:后续写档恢复正常 ——
    release_save.set()
    t_winner.join(timeout=5)
    assert not t_winner.is_alive(), '持锁方未完成'
    assert len(winner_results) == 1
    assert winner_results[0].action == 'inserted'

    ctx.screen_loader.save_screen.side_effect = None
    result = backend.upsert_screen_area('邮件', '标题', [1, 1, 2, 2])
    assert result.action == 'inserted'


def test_screen_write_mutex_released_on_error() -> None:
    """持锁方写档中途抛异常 → 锁必释放(finally 兜底),后续写档不误报 busy。

    防死锁不变式:校验 / IO / 内存操作任何环节异常都不留死锁。
    """
    backend, _ctx, screen_info = _screen_write_backend()
    screen_info.upsert_area.side_effect = RuntimeError('写档中途爆炸')

    with pytest.raises(RuntimeError, match='写档中途爆炸'):
        backend.upsert_screen_area('邮件', '标题', [1, 1, 2, 2])

    # 异常后锁已释放:下次写档正常走完,不被误判 busy
    screen_info.upsert_area.side_effect = None
    result = backend.upsert_screen_area('邮件', '标题', [1, 1, 2, 2])
    assert result.action == 'inserted'
