"""SR 测试公共脚手架:MockController + SrTestContext + test_context fixture。

从 ZZZ(`zzz-od-test/test/conftest.py`)同步、SrContext 适配。供 fixture-driven op
流程测试(`test/harness/fixture_controller.py`)使用 —— 跑多节点 op 的完整 ``execute()``。

所有测试用 pytest 函数风格 + 本文件 fixture(``test/__init__.py`` 的 ``SrTestBase`` 已废弃移除):

- ``test_context``(session):session 级 ``SrTestContext``,ctx/OCR 只 init 一次复用
  (替代旧 ``SrTestBase`` 每 test 方法重初始化 —— 那是测试慢的根因);
- ``test_image_dir``:测试模块所在目录,读本地 png(替代旧 ``SrTestBase.get_test_image``);
- 端到端 flow 测试(``test/harness/fixture_controller.py``)也用 ``test_context``。

适配 ZZZ 的主要差异:

- ``ZContext`` → ``SrContext``;``ctx.init()`` → SR 的分步
  (``init_by_config`` + ``load_instance_config`` + ``ocr.init_model``);
- ``MockController.get_screenshot`` 返回 ``mock_screenshot``(经基类 ``screenshot``
  包成 ``(time, img)`` 元组,匹配 ``ControllerBase`` 签名)。
"""

import hashlib
import inspect
import logging
import os
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
# 测试进程日志分流(conftest 导入期生效,早于任何测试/ctx 初始化)
# --------------------------------------------------------------------------- #
# 职责划分(文件即进程身份):GUI/调度器→log.txt;MCP server→mcp_server.log;
# pytest→test.log。修前测试继承 log_utils 默认配置,一趟全量往 .log/log.txt
# 写 1w+ 行 fixture 回放的 op 流转(格式与真实运行完全相同),污染运行日志
# 排查(2026-08-24 实证:fixture 测试的「切账号」链被误读为真进程)。
# console handler 关闭:pytest 有自己的捕获体系,stdout 噪声纯浪费;
# 要看测试内框架日志查 .log/test.log。
configure_logger(
    framework_log,
    LoggerConfig(
        log_file_path=get_log_file_path(default_name='test.log'),
        add_console_handler=False,
        propagate=False,
    ),
)
# 降噪(模块级,对**所有**测试生效——cw sim 等纯逻辑测试不依赖 test_context
# fixture,放 fixture 里单独跑它们时拦不住):sim 逐决策 INFO 一轮全量写
# 100MB+ test.log(2026-08-25 实测:line_strategy/cw_economy 占 75%+)。
# 排查具体测试时临时注释本行重跑(日志仍走 .log/test.log,恢复 INFO 量级)。
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
# 背景:生产 OCR 缓存按 ``id(image)`` 键控、容量 5(ocr_service),语义是
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
    #: 同对象 → 内容哈希的身份缓存(持引用防 GC 后 id 复用;bounded 防涨)。
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
# ``ctx.run_context = _FakeRunCtx()``)且不还原,污染会泄漏到**后续别的测试
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
#: 守卫的共享 ctx 属性(整对象替换 = 高危;None 表示属性原本缺失)。
_GUARDED_CTX_ATTRS: tuple[str, ...] = ('run_context', 'controller')


# --------------------------------------------------------------------------- #
# 真实外网连接守卫(README 测试纪律 5 的机检层)
# --------------------------------------------------------------------------- #
# 拦 ``socket.connect``:非 loopback 地址直接 AssertionError(带定位指引),防
# 测试静默触网——慢(单次秒级)+ 不确定(断网/代理 = 假 flaky)。判例:曾发现
# ctx 初始化链路真实请求 ghproxy.link ~1s/次(已短路,本守卫防同型回归)。
# 放行 loopback(127.0.0.1/::1/localhost):进程内 TestClient 虽不走 socket,
# 本地 server 类测试不受影响。逃生口:环境变量 ``SR_TEST_ALLOW_NET=1``
# (fresh 环境首次下载 OCR 模型等合法场景)。

#: 放行的回环地址(socket.connect 的 address 可能是 tuple 或裸 str)。
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
