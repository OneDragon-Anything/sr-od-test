"""BackToNormalWorldPlus 测试的目录内共用装置。

同目录三个测试文件(test_check_screen.py / test_check_screen_real_frame.py /
test_check_npc_dialog.py)按被测方法与输入形态拆分后共用的测试替身放这里;只被单个
文件用的桩与夹具留在各自测试文件内。
"""

from test.harness.fixture_controller import WatchdogOperationMixin

from one_dragon.utils.i18_utils import gt
from sr_od.operations.back_to_normal_world_plus import BackToNormalWorldPlus
from sr_od.operations.sr_operation import SrOperation


class _WatchedBackToNormal(WatchdogOperationMixin, BackToNormalWorldPlus):
    """带看门狗的 BackToNormalWorldPlus(防测试自身死循环)。"""

    watchdog_max_rounds: int = 50

    def __init__(self, ctx) -> None:
        """跳过游戏窗口前置节点(MockController 无 game_win,与本测试无关)。"""
        # BackToNormalWorldPlus.__init__ 不透传 need_check_game_win,这里直接走
        # SrOperation 构造(节点注册发生在 __init__,事后翻转属性无效)。
        SrOperation.__init__(
            self, ctx, op_name=gt('返回普通大世界'), need_check_game_win=False,
        )
