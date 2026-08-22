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

import inspect
import os
import warnings
from collections.abc import Iterator
from functools import cached_property
from pathlib import Path

import pytest
from cv2.typing import MatLike

from one_dragon.base.controller.controller_base import ControllerBase
from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.application.plugin_info import PluginSource
from one_dragon.base.push.push_config import PushProxy
from one_dragon.envs.env_config import ProxyTypeEnum
from one_dragon.utils import cv2_utils, file_utils
from sr_od.config.game_config import GameConfig
from sr_od.context.sr_context import SrContext


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


@pytest.fixture(scope='session')
def test_context() -> SrTestContext:
    """创建 session 级模拟 ctx(复用,避免每个 test 重新 init)。"""
    ctx = SrTestContext()

    ctx.env_config.is_debug = True
    ctx.current_instance_idx = 99  # 使用特定的实例 id
    ctx.init_by_config()
    ctx.load_instance_config()
    ctx.ocr.init_model()
    ctx.controller = MockController(
        game_config=ctx.game_config,
        standard_width=ctx.project_config.screen_standard_width,
        standard_height=ctx.project_config.screen_standard_height,
    )

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
