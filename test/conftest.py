"""SR 测试公共脚手架:MockController + SrTestContext + test_context fixture。

从 ZZZ(`zzz-od-test/test/conftest.py`)同步、SrContext 适配。供 fixture-driven op
流程测试(`test/harness/fixture_controller.py`)使用 —— 跑多节点 op 的完整 ``execute()``。

与现有 ``test/__init__.py`` 的 ``SrTestBase``(unittest 风格、单步 ``round_by_find_area``)
并存:

- 老的单步测试继续用 ``SrTestBase``(各自 ``__init__`` 建 ctx);
- 新的端到端 flow 测试用本文件的 ``test_context`` fixture(session 复用 ctx,更快)。

适配 ZZZ 的主要差异:

- ``ZContext`` → ``SrContext``;``ctx.init()`` → SR 的分步
  (``init_by_config`` + ``load_instance_config`` + ``ocr.init_model``,对齐 ``SrTestBase``);
- ``MockController.get_screenshot`` 返回 ``mock_screenshot``(经基类 ``screenshot``
  包成 ``(time, img)`` 元组,匹配 ``ControllerBase`` 签名)。
"""

import inspect
import os
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
