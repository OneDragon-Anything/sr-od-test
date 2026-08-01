"""模拟宇宙 选择类 op 的识别覆盖测试(祝福 / 奇物 / 事件选项)。

覆盖各选择 op 依赖的核心识别函数:
- ``bless_utils.get_bless_pos``:OCR 全屏 → difflib 匹配祝福名 + 正下方命途 → 筛出可选祝福。
- ``SimUniChooseCurio._get_curio_pos``:按固定奇物名框 OCR → ``match_best_curio_by_ocr`` 匹配奇物。
- ``SimUniEvent._get_opt_list``:``event_option_icon`` 模板匹配 ``OPT_RECT`` 内选项(事件 / 交易商店)。

整 op ``execute`` 因 MockController 画面不变 + 重置 / 选择循环不具备确定性,故此处测「识别」层
(最稳定、价值最高);优先级选取为纯逻辑,不在此测。
"""

from one_dragon.utils.i18_utils import gt
from sr_od.application.sim_universe.operations.bless import bless_utils
from sr_od.application.sim_universe.operations.bless.sim_uni_choose_path import (
    SimUniChoosePath,
)
from sr_od.application.sim_universe.operations.curio.sim_uni_choose_curio import (
    SimUniChooseCurio,
)
from sr_od.application.sim_universe.operations.sim_uni_event import SimUniEvent
from sr_od.application.sim_universe.sim_uni_data import SimUniPath
from test import SrTestBase


class TestSimUniChoose(SrTestBase):

    def __init__(self, *args, **kwargs):
        SrTestBase.__init__(self, *args, **kwargs)

    def test_get_bless_pos(self):
        """选择祝福画面:OCR + difflib 识别 3 个祝福 + 各自命途(正下方)。"""
        screen = self.get_test_image('sim_uni_choose_bless.png')
        result = bless_utils.get_bless_pos(self.ctx, screen)

        self.assertEqual(len(result), 3, '应识别到 3 个祝福')

        titles = {gt(p.bless.title, 'game') for p in result}
        self.assertEqual(titles, {'明澈琉璃身', '雷车动地', '哨戒卫星'}, '祝福名称应匹配')

        paths = {p.bless.path for p in result}
        self.assertEqual(paths, {SimUniPath.ABUNDANCE, SimUniPath.HUNT, SimUniPath.DESTRUCTION},
                         '祝福命途应匹配:丰饶 / 巡猎 / 毁灭')

        for p in result:
            self.assertTrue(p.find_path, f'祝福 {p.bless.title} 应在正下方匹配到命途')

    def test_get_curio_pos(self):
        """选择奇物画面:按固定名框 OCR 识别 3 个奇物。"""
        screen = self.get_test_image('sim_uni_choose_curio.png')
        op = SimUniChooseCurio(self.ctx, config=None)
        op.handle_init()
        op.last_screenshot = screen
        result = op._get_curio_pos(screen)

        self.assertEqual(len(result), 3, '应识别到 3 个奇物')

        names = {r.data.name for r in result}
        self.assertEqual(names, {'繁育火漆', '龋齿星系模型', '信仰债券'}, '奇物名称应匹配')

    def test_get_event_opt_list(self):
        """事件 / 交易商店画面:`event_option_icon` 模板匹配 OPT_RECT 内 4 个选项(需确定型)。"""
        screen = self.get_test_image('sim_uni_event_store.png')
        op = SimUniEvent(self.ctx, config=None)
        op.last_screenshot = screen
        opt_list = op._get_opt_list(screen)

        self.assertEqual(len(opt_list), 4, '交易商店应识别到 4 个选项')
        for o in opt_list:
            self.assertIsNotNone(o.confirm_rect, '商店选项为需确定型,应有 confirm_rect')

        titles = ''.join(o.title for o in opt_list)
        for kw in ('购买', '奇物', '强化', '离开'):
            self.assertIn(kw, titles, f'选项标题应包含 {kw}')

    def test_choose_target_path(self):
        """命途选择画面:OCR 入口-命途区域 找到目标命途(巡猎)并点击。"""
        screen = self.get_test_image('sim_uni_choose_path.png')
        op = SimUniChoosePath(self.ctx, path=SimUniPath.HUNT)
        op.last_screenshot = screen
        result = op._choose_target_path()
        self.assertTrue(result.is_success, f'应识别到巡猎命途: {result.status}')
