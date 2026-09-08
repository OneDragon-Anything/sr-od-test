"""SR 测试公共脚手架:MockController + SrTestContext + test_context fixture。

从 ZZZ(`zzz-od-test/test/conftest.py`)同步、SrContext 适配。供 fixture-driven op
流程测试(`test/harness/fixture_controller.py`)使用 —— 跑多节点 op 的完整 ``execute``。

所有测试用 pytest 函数风格 + 本文件 fixture(``test/__init__.py`` 的 ``SrTestBase`` 已废弃移除):

- ``test_context``(session):session 级 ``SrTestContext``,ctx/OCR 只 init 一次复用
  (替代旧 ``SrTestBase`` 每 test 方法重初始化 —— 那是测试慢的根因);
- ``test_image_dir``:测试模块所在目录,读本地 png(替代旧 ``SrTestBase.get_test_image``);
- 端到端 flow 测试(``test/harness/fixture_controller.py``)也用 ``test_context``。

适配 ZZZ 的主要差异:

- ``ZContext`` → ``SrContext``;``ctx.init`` → SR 的分步
  (``init_by_config`` + ``load_instance_config`` + ``ocr.init_model``);
- ``MockController.get_screenshot`` 返回 ``mock_screenshot``(经基类 ``screenshot``
  包成 ``(time, img)`` 元组,匹配 ``ControllerBase`` 签名)。
"""

import hashlib
import inspect
import logging
import os
import time
import warnings
from collections import OrderedDict
from collections.abc import Iterator
from functools import cached_property
from pathlib import Path

import pytest
from cv2.typing import MatLike

from one_dragon.base.controller.controller_base import ControllerBase
from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.ocr.ocr_match_result import OcrMatchResult
from one_dragon.base.operation.application.plugin_info import PluginSource
from one_dragon.base.push.push_config import PushProxy
from one_dragon.envs.env_config import ProxyTypeEnum
from one_dragon.envs.ghproxy_service import GhProxyService
from one_dragon.utils import cv2_utils, file_utils
from one_dragon.utils.log_utils import (
    LoggerConfig,
    configure_logger,
    get_log_file_path,
)
from one_dragon.utils.log_utils import log as framework_log
from sr_od.config.game_config import GameConfig
from sr_od.context.sr_context import SrContext

# --------------------------------------------------------------------------- #
# 测试进程日志隔离(conftest 导入期生效,早于任何测试/ctx 初始化)
# --------------------------------------------------------------------------- #
# 职责划分(文件即进程身份):GUI/调度器→log.txt;MCP server→mcp_server.log。
# pytest 进程默认**不写任何共享日志文件**(挂一个框架持有的 NullHandler 占位,
# 防止后续 import 侧的 ``log = get_logger`` 重新挂默认 log.txt 句柄):
#
#   治理(WinError 32 四度实证):轮转型 FileHandler 的换名在 Windows 上
#   只要文件被任何进程打开即抛 PermissionError(32)。修前 pytest 全部进程共用
#   .log/test.log,与并行的 sim 批/regen 进程在午夜轮转窗口互踩 → 测试随机红
#   (非代码错误)。测试日志无运维价值(排查时临时开),最彻底的隔离 =
#   测试进程退出「共享日志写入方」集合 —— 零句柄,零竞态面。
#
# 逃生口:设环境变量 ``SR_TEST_LOG_FILE=1`` 时仍走旧路径(.log/test.log,
# 现已换 SafeTimedRotatingFileHandler,轮转被占用会退避重试+推迟而非报错),
# 用于排查具体测试的框架日志流向。
_test_keep_file_log = bool(os.environ.get('SR_TEST_LOG_FILE'))
if _test_keep_file_log:
    configure_logger(
        framework_log,
        LoggerConfig(
            log_file_path=get_log_file_path(default_name='test.log'),
            add_console_handler=False,
            propagate=False,
        ),
    )
else:
    # 默认分支:本进程不落盘。用「关闭全部框架托管 handler + 挂框架持有的
    # NullHandler」表达;占位 owner 标记让 get_or_create_logger 认为
    # 'OneDragon' 已初始化,后续 import 不再挂默认 log.txt 的 handler。
    from one_dragon.utils.log_utils import _close_managed_handlers

    _close_managed_handlers(framework_log)
    _null_handler = logging.NullHandler()
    _null_handler._one_dragon_logger_owner = framework_log.name  # noqa: SLF001
    framework_log.addHandler(_null_handler)
    framework_log.propagate = False
# 降噪(模块级,对**所有**测试生效——cw sim 等纯逻辑测试不依赖 test_context
# fixture,放 fixture 里单独跑它们时拦不住):sim 逐决策 INFO 一轮全量写
# 100MB+ test.log(2026-08-25 实测:line_strategy/cw_economy 占 75%+)。
# 排查具体测试时临时设 SR_TEST_LOG_FILE=1 并把本行改回 logging.INFO 重跑
# (日志仍走 .log/test.log,恢复 INFO 量级)。
framework_log.setLevel(logging.WARNING)


class MockController(ControllerBase):
    """测试用假控制器。

    ``click`` 返回是否落在标准画面内;``get_screenshot`` 返回 ``mock_screenshot``
    (基类 ``screenshot`` 会包成 ``(time, img)`` 元组)。其余方法(``drag_to`` /
    ``input_str`` / ``scroll`` / ``close_game`` 等)沿用基类 ``pass`` 默认。

    op 会触达的 ``keyboard_controller`` / ``btn_controller`` / ``game_win`` 不在
    ``ControllerBase`` 上(属 ``SrPcController``),由 ``FixtureController``
    (``test/harness``)补全 stub。
    """

    def __init__(
        self,
        game_config: GameConfig,
        standard_width: int = 1920,
        standard_height: int = 1080,
    ) -> None:
        ControllerBase.__init__(self)
        self.game_config: GameConfig = game_config
        self.standard_width: int = standard_width
        self.standard_height: int = standard_height
        self.mock_screenshot: MatLike = None

    def click(
        self,
        pos: Point = None,
        press_time: float = 0,
        pc_alt: bool = False,
        gamepad_key: str | None = None,
    ) -> bool:
        if pos is None:
            return True
        return 0 <= pos.x < self.standard_width and 0 <= pos.y < self.standard_height

    def park_cursor(self, game_pos: Point,
                    before_wait: float = 0.0, after_wait: float = 0.2) -> None:
        """no-op(光标 parking 是真机 IO,测试无光标)。"""

    def get_screenshot(self, independent: bool = False) -> MatLike:
        return self.mock_screenshot


class SrTestContext(SrContext):
    """测试用 ``SrContext``:加存档截图读取。

    ``application_plugin_dirs`` 覆盖父类 —— 用 ``SrContext`` 的文件位置定位
    ``sr_od/application``(父类 ``OneDragonContext`` 默认按自身位置定位
    ``one_dragon``,测试会找错目录)。
    """

    def __init__(self) -> None:
        SrContext.__init__(self)
        self.controller: MockController | None = None

    @cached_property
    def application_plugin_dirs(self) -> list[tuple[Path, PluginSource]]:
        """覆盖父类,用 ``SrContext`` 文件位置定位 ``sr_od/application``。"""
        dirs: list[tuple[Path, PluginSource]] = []

        cls_file = inspect.getfile(SrContext)
        # sr_context.py → context/ → sr_od/
        parent_dir = Path(cls_file).parent.parent

        application_dir = parent_dir / 'application'
        if application_dir.is_dir():
            dirs.append((application_dir, PluginSource.BUILTIN))

        src_dir = file_utils.find_src_dir(cls_file)
        if src_dir is not None:
            project_root = src_dir.parent
            plugins_dir = project_root / 'plugins'
            if plugins_dir.is_dir():
                dirs.append((plugins_dir, PluginSource.THIRD_PARTY))

        return dirs

    def load_screen(self, screen_name: str, state: str) -> MatLike:
        """从中央存档 ``screens/<screen_name>/<state>.webp`` 读一张截图。

        Args:
            screen_name: 画面名(对应 docs/game/screens/ + screen_info,如 ``进入游戏``)。
            state: 子态可读名(如 ``点击进入``、``退出登录弹窗``),即存档文件名(不带后缀)。

        Returns:
            RGB 图像;底层 ``cv2_utils.read_image`` 支持中文路径 + webp。
        """
        screens_dir = Path(__file__).parent.parent / 'screens'
        path = screens_dir / screen_name / f'{state}.webp'
        assert path.exists(), f'存档截图不存在: {path}'
        return cv2_utils.read_image(str(path))

    def has_screen(self, screen_name: str, state: str) -> bool:
        """存档截图 ``screens/<screen_name>/<state>.webp`` 是否存在。

        缺 fixture 的用例用它 skip(而非 error);fixture 采到后自动恢复运行,无需改代码。
        """
        screens_dir = Path(__file__).parent.parent / 'screens'
        return (screens_dir / screen_name / f'{state}.webp').exists()

    def mock_screen(self, screen_name: str, state: str) -> None:
        """从存档读截图并设为 controller 下一帧(= ``load_screen`` + ``add_mock_screenshot``)。"""
        screen = self.load_screen(screen_name, state)
        assert screen is not None and isinstance(screen, MatLike)
        self.controller.mock_screenshot = screen


# --------------------------------------------------------------------------- #
# OCR 内容哈希 memo(测试侧性能层,不动生产代码)
# --------------------------------------------------------------------------- #
# 背景:生产 OCR 缓存按 ``id(image)`` 键控、容量 32(ocr_service;color_range
# 裁剪化后按 (图片,颜色,区域) 分条,单帧 heavy 4-6 条,32 防同帧自逐出),语义是
# 「同一帧多区域查询复用」。测试里同一张 fixture webp 被多个测试文件反复
# ``load_screen`` —— 每次都是新对象/新 id → 每个文件都对同一张图重跑
# 全图 OCR(det+rec 逐行,~0.5s/张)。本 memo 按图片**内容哈希**记两层缓存:
#
# 1. 进程内 dict(原层):session 内每张不同内容的图只推理一次;
# 2. 磁盘层(.pytest_cache/v/ocr_memo/,经 pytest cache 目录):跨 pytest
#    会话复用——id_mark 的 ~112 张 fixture 每轮全量都是同样的图,冷轮推理
#    ~50s,warm 轮直接命中(键含 OCR 模型文件指纹,模型更新自动失效;
#    ``pytest --cache-clear`` 即清)。CI 每次全新环境 → 恒冷路径,无收益
#    也无额外成本(读写各一次小 pickle)。
#
# 正确性前提(2026-08-25 实测):同 provider 同图推理确定(DML 三次自洽)、
# CPU 与 DML 文本集一致;键含 provider 标志。任何读/写失败按 miss 处理,
# 坏缓存最坏代价 = 重算一次,不影响断言。命中返回浅拷贝(防原地改污染)。


def _ocr_model_fingerprint(matcher) -> str:
    """模型文件指纹(det/rec 的 size+mtime)+ provider → 缓存键前缀。"""

    parts = [f'gpu={matcher.is_use_gpu()}']
    for attr in ('det_model_dir', 'rec_model_dir'):
        path = Path(getattr(matcher._ocr_param, attr, ''))  # noqa: SLF001
        try:
            st = path.stat()
            parts.append(f'{path.name}:{st.st_size}:{int(st.st_mtime)}')
        except OSError:
            parts.append(f'{path.name}:missing')
    raw = '|'.join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _pytest_cache_dir(request: pytest.FixtureRequest) -> Path | None:
    """pytest cache 下的 ocr_memo 目录(不存在 cache 机制时返 None)。"""
    try:
        return request.config.cache.mkdir('ocr_memo')  # type: ignore[union-attr]
    except Exception:
        return None


def _install_ocr_content_memo(ocr_service, cache_dir: Path | None) -> None:
    """给 ``ocr_service.get_ocr_result_list`` 包内容哈希 memo(进程内 + 磁盘)。

    仅测试侧安装(conftest fixture 内调用);不改变 ``OcrService`` 行为语义,
    未命中时原样透传全部参数。
    """
    import pickle

    orig_get = ocr_service.get_ocr_result_list
    memo: dict[tuple, list[OcrMatchResult]] = {}
    model_fp = _ocr_model_fingerprint(ocr_service.ocr_matcher)  # noqa: SLF001
    #同对象 → 内容哈希的身份缓存(持引用防 GC 后 id 复用;bounded 防涨)。
    _digest_by_obj: OrderedDict[int, tuple[MatLike, str]] = OrderedDict()
    _DIGEST_CACHE_MAX = 8

    def _content_digest(image: MatLike) -> str:
        cached = _digest_by_obj.get(id(image))
        if cached is not None and cached[0] is image:
            _digest_by_obj.move_to_end(id(image))
            return cached[1]
        digest = hashlib.sha256(image.tobytes()).hexdigest()
        _digest_by_obj[id(image)] = (image, digest)
        while len(_digest_by_obj) > _DIGEST_CACHE_MAX:
            _digest_by_obj.popitem(last=False)
        return digest

    def _disk_path(key: tuple) -> Path | None:
        if cache_dir is None:
            return None
        khash = hashlib.sha256(repr(key).encode()).hexdigest()[:40]
        return cache_dir / f'{khash}.pkl'

    def _memo_get_ocr_result_list(
        image: MatLike,
        color_range: list[list[int]] | None = None,
        rect: Rect | None = None,
        crop_first: bool = False,
        threshold: float = 0,
        merge_line_distance: float = -1,
    ) -> list[OcrMatchResult]:
        if image is None:
            return orig_get(
                image=image, color_range=color_range, rect=rect,
                crop_first=crop_first, threshold=threshold,
                merge_line_distance=merge_line_distance,
            )
        key = (
            model_fp,
            _content_digest(image),
            image.shape, image.dtype.str,
            None if color_range is None else tuple(tuple(c) for c in color_range),
            bool(crop_first),
            rect,
            threshold, merge_line_distance,
        )
        if key not in memo:
            hit = None
            dpath = _disk_path(key)
            if dpath is not None and dpath.exists():
                try:
                    with dpath.open('rb') as f:
                        hit = pickle.load(f)
                except Exception:
                    hit = None  # 坏缓存按 miss,最坏代价=重算
            if hit is None:
                hit = orig_get(
                    image=image, color_range=color_range, rect=rect,
                    crop_first=crop_first, threshold=threshold,
                    merge_line_distance=merge_line_distance,
                )
                if dpath is not None:
                    try:
                        tmp = dpath.with_suffix('.tmp')
                        with tmp.open('wb') as f:
                            pickle.dump(hit, f)
                        tmp.replace(dpath)
                    except Exception:
                        pass  # 写失败只影响下次 warm 命中,不影响正确性
            memo[key] = hit
        return list(memo[key])

    ocr_service.get_ocr_result_list = _memo_get_ocr_result_list  # type: ignore[method-assign]


@pytest.fixture(scope='session')
def test_context(request: pytest.FixtureRequest) -> SrTestContext:
    """创建 session 级模拟 ctx(复用,避免每个 test 重新 init)。"""
    ctx = SrTestContext()

    ctx.env_config.is_debug = True
    ctx.current_instance_idx = 99  # 使用特定的实例 id

    # 测试不开真实网络:init_by_config 在 is_gh_proxy 时会请求 ghproxy.link
    # 拉免费代理地址(~1s + 不确定性),测试环境无意义 → 临时短路,init 后还原。
    _real_update_proxy = GhProxyService.update_proxy_url
    GhProxyService.update_proxy_url = lambda self: False  # type: ignore[assignment, method-assign]
    try:
        ctx.init_by_config()
    finally:
        GhProxyService.update_proxy_url = _real_update_proxy  # type: ignore[assignment, method-assign]

    ctx.load_instance_config()

    # OCR 设备统一:有 DirectML 就用(实测快 ~27%:553 vs 759ms/张;两种设备
    # 文本集一致、DML 自洽,详见 sr-od-test/README「运行速度」);无 DML(如 CI)
    # 维持 CPU。显式覆盖本地配置,避免测试速度取决于开发机的 model.yml。
    # 坏驱动护栏:DML 初始化失败则回退 CPU 重载,不让整批 OCR 测试静默空结果。
    _switched_to_dml = False
    try:
        import onnxruntime as _ort

        _has_dml = 'DmlExecutionProvider' in _ort.get_available_providers()
    except Exception:
        _has_dml = False
    if _has_dml and not ctx.ocr.is_use_gpu():
        ctx.ocr.update_use_gpu(True)
        _switched_to_dml = True
    if not ctx.ocr.init_model() and _switched_to_dml:
        ctx.ocr.update_use_gpu(False)
        ctx.ocr.init_model()
    ctx.controller = MockController(
        game_config=ctx.game_config,
        standard_width=ctx.project_config.screen_standard_width,
        standard_height=ctx.project_config.screen_standard_height,
    )

    _install_ocr_content_memo(ctx.ocr_service, cache_dir=_pytest_cache_dir(request))

    # 部分配置统一使用 mock,不把运行过程的值写入本地配置
    ctx.push_service.push_config.file_path = None
    ctx.env_config.file_path = None

    # 根据环境变量进行设置
    proxy_url = os.getenv('ENV_PERSONAL_PROXY', '')
    if len(proxy_url) > 0:
        ctx.env_config.proxy_type = ProxyTypeEnum.PERSONAL.value.value
        ctx.env_config.personal_proxy = proxy_url
    ctx.push_service.push_config.proxy = os.getenv(
        'PUSH_PROXY', PushProxy.NONE.value.value
    )

    return ctx


@pytest.fixture
def test_image_dir(request) -> Path:
    """测试模块所在目录(替代 ``SrTestBase.sub_package_path``):读测试自带的本地 png。

    迁移自 ``SrTestBase.get_test_image`` —— 后者靠 TestCase 实例的 ``sub_package_path``
    (子类模块所在目录)定位 png;去掉 TestCase 后改用 ``request.module.__file__`` 定位。

    用法::

        def test_x(test_image_dir: Path) -> None:
            img = cv2_utils.read_image(str(test_image_dir / '0.png'))
    """
    return Path(request.module.__file__).parent


# --------------------------------------------------------------------------- #
# 共享态守卫(session 级 test_context 的污染防线,autouse)
# --------------------------------------------------------------------------- #
# 背景:``test_context`` 是 session 级共享,测试若裸赋值替换其属性(如
# ``ctx.run_context = _FakeRunCtx``)且不还原,污染会泄漏到**后续别的测试
# 文件**才炸(单跑必过/全量必挂的假 flaky;实锤:test_cw_back_layout 裸赋值
# run_context → test_enter_currency_war_flow 的 op 初始化读 run_context.event_bus
# AttributeError,曾被误诊为并发干扰)。
#
# 守卫语义:记录守卫属性的「对象身份」,测试后若被换成别的对象 → 还原 + 警告
# (还原让后续测试不被拖垮;警告让污染点当场可见,而非几周后遥遥挂别处)。
#
# 合法替换姿势不受扰:``monkeypatch.setattr``。同 scope 下 autouse fixture
# 先 setup 后 teardown —— 本守卫的对比发生在 monkeypatch 还原**之后**,
# 用 monkeypatch 的测试看到的一定是已还原的原对象,零误报。
#
# 新增守卫属性:改 ``_GUARDED_CTX_ATTRS``(只守「整个对象被替换」类污染;
# 对象内部可变状态(如 mock_screenshot)是测试的常规工作面,不在守卫范围)。
#守卫的共享 ctx 属性(整对象替换 = 高危;None 表示属性原本缺失)。
_GUARDED_CTX_ATTRS: tuple[str, ...] = ('run_context', 'controller')

# 内部态守卫(w505 全集假红实证):run_context 的**运行残留**字段——生产停机
# 路径(rc.stop_running)会写 last_run_result,monkeypatch 只还原被 patch 的
# 模块属性,这类副作用无主残留 → 后续一切 execute() 入口撞 W209j 刹车
# (单跑必过/全量必挂的同族假 flaky)。守卫语义:测试后遗留非 None → 警告
# +复位(定位靠警告,不靠下游测试莫名红)。
_RUN_LEFTOVER_ATTRS: tuple[str, ...] = ('last_run_result',)


# --------------------------------------------------------------------------- #
# 真实外网连接守卫(README 测试纪律 5 的机检层)
# --------------------------------------------------------------------------- #
# 拦 ``socket.connect``:非 loopback 地址直接 AssertionError(带定位指引),防
# 测试静默触网——慢(单次秒级)+ 不确定(断网/代理 = 假 flaky)。判例:曾发现
# ctx 初始化链路真实请求 ghproxy.link ~1s/次(已短路,本守卫防同型回归)。
# 放行 loopback(127.0.0.1/::1/localhost):进程内 TestClient 虽不走 socket,
# 本地 server 类测试不受影响。逃生口:环境变量 ``SR_TEST_ALLOW_NET=1``
# (fresh 环境首次下载 OCR 模型等合法场景)。

#放行的回环地址(socket.connect 的 address 可能是 tuple 或裸 str)。
_LOOPBACK_HOSTS = frozenset({'127.0.0.1', '::1', 'localhost', ''})


@pytest.fixture(autouse=True, scope='session')
def _block_external_network() -> Iterator[None]:
    """测试进程内禁止真实外网 TCP 连接(见上方注释;autouse 全测试生效)。"""
    if os.environ.get('SR_TEST_ALLOW_NET'):
        yield
        return

    import socket as _socket

    _orig_connect = _socket.socket.connect

    def _guarded_connect(self, address):  # noqa: ANN001, ANN202
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host not in _LOOPBACK_HOSTS:
            raise AssertionError(
                f'测试禁止真实外网连接: {address!r}。'
                '触网链路应在测试入口 mock(README 测试纪律 5);'
                '确需联网(如 fresh 环境下载模型)设 SR_TEST_ALLOW_NET=1。'
            )
        return _orig_connect(self, address)

    _socket.socket.connect = _guarded_connect  # type: ignore[method-assign]
    try:
        yield
    finally:
        _socket.socket.connect = _orig_connect  # type: ignore[method-assign]


@pytest.fixture(autouse=True)
def _guard_shared_ctx(test_context: SrTestContext) -> Iterator[None]:
    """session 级 ctx 属性替换守卫(见上方注释;autouse 全测试生效)。"""
    before: dict[str, object | None] = {
        name: getattr(test_context, name, None)
        if hasattr(test_context, name) else None
        for name in _GUARDED_CTX_ATTRS
    }
    had_attr = {name: hasattr(test_context, name) for name in _GUARDED_CTX_ATTRS}
    yield
    for name, orig in before.items():
        cur_has = hasattr(test_context, name)
        cur = getattr(test_context, name, None) if cur_has else None
        polluted = (cur_has != had_attr[name]) or (cur is not orig)
        if polluted:
            warnings.warn(
                f'test_context.{name} 被本测试替换且未还原(已自动还原)。'
                f'合法替换请用 monkeypatch.setattr(自动还原,不触发本守卫)。',
                stacklevel=2,
            )
            if had_attr[name]:
                setattr(test_context, name, orig)
            else:
                delattr(test_context, name)
    # 运行残留守卫(见 _RUN_LEFTOVER_ATTRS 注释):生产停机路径的副作用复位。
    rc = getattr(test_context, 'run_context', None)
    if rc is not None:
        for field in _RUN_LEFTOVER_ATTRS:
            if getattr(rc, field, None) is not None:
                warnings.warn(
                    f'run_context.{field} 被本测试遗留(生产停机路径写入?已自动'
                    f'复位)——残留会让后续 execute() 撞 W209j 刹车(全集假红)。',
                    stacklevel=2,
                )
                setattr(rc, field, None)
        # 停机中断闩残留(同族:走真实生产停机路径的测试置位后无收口点清,
        # 泄漏会让后续所有轮间等待被 _interruptible_sleep 静默短路)。此处是
        # 防线不是许可——用 reset_running_state 的测试已在 harness 层复位,
        # 报警的是绕过 harness 的泄漏点。
        if getattr(rc, 'is_stop_interrupted', False):
            warnings.warn(
                'run_context 停机中断闩被本测试遗留置位(真实停机路径触发?'
                '已自动复位)——泄漏会让后续测试的轮间等待被静默短路(全集假红)。',
                stacklevel=2,
            )
            rc._stop_interrupted = False  # noqa: SLF001


# --------------------------------------------------------------------------- #
# 调试图落盘隔离(README 测试纪律 2 的机检层)
# --------------------------------------------------------------------------- #
# 背景:op 框架的异常 handler(``Operation.execute`` catch 后 ``save_screenshot``)
# 与部分业务代码直接调 ``debug_utils.save_debug_image``,测试进程中会写真实
# ``.debug/images/``。判例:fixture 流程测试里 op 节点抛 AttributeError 被框架
# 吞成 round_retry 重试,每次异常落一张 2.4MB 图(单跑一条测试即写 3 张,
# 反复跑累积 30+ 张),测试还照样绿 —— 盘脏了且无人察觉。
# 隔离:``save_debug_image`` 重定向到 pytest tmp_path,真实 .debug/ 零写入;
# 文件保留在 tmp(诊断时仍可看),文件名返回值语义不变。


@pytest.fixture(autouse=True)
def _isolate_debug_images(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """把 ``debug_utils.save_debug_image`` 的写入重定向到 tmp_path(见上方注释)。"""
    from one_dragon.utils import debug_utils

    debug_dir = tmp_path / 'debug_images'
    debug_dir.mkdir(exist_ok=True)

    def _save_to_tmp(image, file_name=None, prefix: str = '', copy_screenshot: bool = False) -> str:  # noqa: ANN001, ANN202
        # 与原实现同名生成规则;copy_screenshot(剪贴板)在测试中跳过
        if file_name is None:
            file_name = f'{prefix}_{round(time.time() * 1000)}'
        cv2_utils.save_image(image, str(debug_dir / f'{file_name}.png'))
        return file_name

    monkeypatch.setattr(debug_utils, 'save_debug_image', _save_to_tmp)


# --------------------------------------------------------------------------- #
# 安灯停线通道隔离(README 测试纪律 2 的机检层:零真实副作用)
# --------------------------------------------------------------------------- #
# 背景:L0 安灯 handler 是 ``telemetry.state._L0_ANDON_HANDLER`` 模块级单例,
# 生产武装点 = CurrencyWarApp.__init__ 显式 ``set_l0_andon_handler``——同进程
# 先跑的测试只要构造过 App,真 handler 就泄漏到后续所有测试:任何测试触发
# L0 判级(决策关键面 ∧ gap_large ∧ 复现计数 ≥2)都会经真 handler 把停机
# flag 写进真实 ``.debug/temp/currency_war/``,被值班误判成实机停线现场。
# 判例(2026-09-03):test_cw_prep_director 构造 App 泄漏真 handler →
# test_cw_shop_refresh 的台账分级测试(run_id='rt',牌名 'A'-'E' 测试桩字面量)
# 升 L0 时真写 l0_andon_hook.flag,同进程另一测试真写 launch_dead_hook.flag
# ——两条「实机停线」均无对应台账行/决策流,纯测试侧假停线。
# 隔离:autouse 把 handler 钉回缺省 None(缺省关语义与生产一致,见
# test_cw_infra_locks 锁1);需要真通道语义的测试用
# ``monkeypatch.setattr(..., '_L0_ANDON_HANDLER', ...)`` 自行显式开启,
# 其 setattr 晚于本 fixture 执行、正常覆盖。


@pytest.fixture(autouse=True)
def _isolate_l0_andon_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """每条测试前把安灯停线 handler 钉回缺省 None(见上方注释)。"""
    from sr_od.application.currency_war.telemetry import state as cw_telemetry_state

    monkeypatch.setattr(cw_telemetry_state, '_L0_ANDON_HANDLER', None)


# --------------------------------------------------------------------------- #
# 停机 flag 族 / exec_fail 族通道隔离(测试纪律 4 机检层:桩化整条副作用链)
# --------------------------------------------------------------------------- #
# 背景(进度账本 2026-08-31 迭代 :64 行余项):telemetry.state 的模块级单例簇
# 是安灯/缺陷台账/暂存槽的唯一拥有者,缺省 enabled=True 且写**真实**
# .debug/currency_war/telemetry/live/(2026-09-07 布局裁定前的旧根
# .debug/temp/currency_war/replay 已退役)。测试只桩 run_id 不桩 _RECORDER 时
# (实证:test_cw_telemetry_collect 的 run_id='w323-run' 桩),台账行照落真实
# defect_ledger.jsonl——单日累积 2290 行测试残渣混进实机台账,离线按 run_id
# 聚合时把测试行当真实局读。同族通道一并钉桩:
# - _RECORDER:重定向到 tmp(保留 enabled=True 缺省语义,只换落盘域);
# - _CURRENT_RUN_ID:钉回空串(record_defect 等便捷入口空 run_id 门控 no-op;
#   防某测试泄漏 run_id 后,后续测试的旁路写入带错局归属);
# - _L0_ANDON_FIRED_RUNS(局级闩锁)/ _defect_seen+_defect_seen_run(复现
#   计数器):进程内状态,残留会让后续测试的 L0 判级/复现升级场景静默变形;
# - 简报缓冲与三个暂存槽(_PENDING_BRIEFING_ROWS/_LAST_SUPPLY_PICK/
#   _PENDING_UNIT_GOLD_CLOSE/_PENDING_UNIT_EXEC):消费即清是常规路径,但
#   异常路径的残留会串到下一个测试的落账行。
# - flag 路径常量(defects._L0_ANDON_FLAG_RELPATH / run_state
#   ._EXEC_FAIL_FLAG_RELPATH):两常量经 get_project_root() / relpath 求路径,
#   pathlib 与绝对路径相接取右侧——钉成 tmp 绝对路径即把安灯/执行失败停机
#   flag 的真实落盘域整体移出仓根 .debug/(测试触发钩子也不落真 flag)。
# 需要真通道语义的测试照旧 monkeypatch 覆盖(setattr 晚于本 fixture 生效)。
# 判别出处:README 测试纪律 1/2/4(模块级全局沿调用链全桩,非只桩被调物)。


@pytest.fixture(autouse=True)
def _isolate_cw_stop_flag_channels(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """每条测试前把 CW 停机 flag 族与 exec_fail 族的生产模块级全局钉桩(见上注释)。"""
    from sr_od.application.currency_war import run_state
    from sr_od.application.currency_war.telemetry import defects as cw_defects
    from sr_od.application.currency_war.telemetry import recorder as cw_recorder
    from sr_od.application.currency_war.telemetry import state as cw_state

    monkeypatch.setattr(
        cw_state, '_RECORDER',
        cw_recorder.TelemetryRecorder(enabled=True,
                                       replay_dir=tmp_path / 'replay'))
    monkeypatch.setattr(cw_state, '_CURRENT_RUN_ID', '')
    # ADR-0588:run 铸造 token 与 _CURRENT_RUN_ID 同簇——mint 路径会模块级
    # 赋值,不钉桩会跨测试残留(下一测试换容器判定被上局容器污染)。
    monkeypatch.setattr(cw_state, '_RUN_MATCH', None)
    # _RUN_CLOSED 是同簇第三件(record_run_summary 局终置位/start_run 铸造
    # 复位,均为模块级裸写;ensure 门与 recorder 简报缓冲分流都消费该位):
    # 残留 True 会把后续测试的 open run 误判「上局已收口」走重铸假分支
    # (出处:.debug/temp/currency_war/attacks/three_review_20260908/
    # 三审报告-第二波.md F1,易失产物待 ADR 回填;正规复位入口 =
    # cw_state.reset_run_state,本钉桩是会话级兜底,两道防线不同层)。
    monkeypatch.setattr(cw_state, '_RUN_CLOSED', False)
    # _CURRENT_DIFFICULTY 是同簇第四件(start_run 与 _CURRENT_RUN_ID 同语句
    # 铸造,消费 = recorder decision 行难度列):残留会让仅桩 run_id 的
    # 测试写出带前局难度的决策行(遥测内容污染,无分支翻转;出处:
    # .debug/temp/currency_war/attacks/three_review_20260908/
    # 三审报告-第三波.md F3,易失产物待 ADR 回填;正规复位入口 =
    # cw_state.reset_run_state,本钉桩是会话级兜底,两道防线不同层,
    # 与 _RUN_CLOSED 同款分层)。
    monkeypatch.setattr(cw_state, '_CURRENT_DIFFICULTY', '')
    monkeypatch.setattr(cw_state, '_L0_ANDON_FIRED_RUNS', set())
    monkeypatch.setattr(cw_state, '_defect_seen', {})
    monkeypatch.setattr(cw_state, '_defect_seen_run', '')
    monkeypatch.setattr(cw_state, '_PENDING_BRIEFING_ROWS', [])
    monkeypatch.setattr(cw_state, '_LAST_SUPPLY_PICK', None)
    monkeypatch.setattr(cw_state, '_PENDING_UNIT_GOLD_CLOSE', None)
    monkeypatch.setattr(cw_state, '_PENDING_UNIT_EXEC', None)
    monkeypatch.setattr(cw_defects, '_L0_ANDON_FLAG_RELPATH',
                        str(tmp_path / 'l0_andon_hook.flag'))
    monkeypatch.setattr(run_state, '_EXEC_FAIL_FLAG_RELPATH',
                        tmp_path / 'cw_exec_fail_hook.flag')
