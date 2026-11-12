"""模拟宇宙 screen_info 文本 area 的 ADR-0215 重叠契约回归锁。

背景:2026-08-22 框架 OCR ``crop_first`` 默认翻转 True→False 后,文本 area 的
pc_rect 必须容纳全图 OCR 检测框 ≥70%,否则 OCR 读到也被静默过滤
(ADR-0122 形态:find 返 FALSE 不报错)。本文件锁 2026-08-25 批量对拍
审计出的两处真失配修复:

- ``差分宇宙-暂离``:旧 rect [1312,876,1391,924] 落在「暂离/结束并结算」
  两按钮之间的空隙(esc菜单 fixture 上 OCR '暂离' 检测框 y=792..830),
  点击/查找全部落空 → 校正为 [1323,782,1786,840](镜像同屏
  ``菜单-结束并结算`` 的 rect 几何)。
- ``怪物上方等级``:全图 OCR 把「等级84+怪物名」并成一个检测框,
  按 rect 过滤(重叠≥70%)恒不过 → 消费点(SimUniFightElite)显式
  ``crop_first=True`` 先裁剪再 OCR(ADR-0215 第 3 条合法场景,同
  中断挑战弹窗「文本-小队生命值」先例)。

候选「点击空白处关闭2」判定为跨子屏同名文本误匹配(fixture 库无该
area 对应的备用布局),不修 —— 见当次审计报告。
"""
from __future__ import annotations

import os

import pytest
from test.conftest import SrTestContext

from one_dragon.base.screen.screen_utils import FindAreaResultEnum, find_area_in_screen

pytestmark = pytest.mark.skipif(
    bool(os.environ.get('CI')),
    reason='需完整 SR 数据栈(screen 配置/模板/OCR),CI clean checkout 无;本地有数据则跑',
)


class TestSimUniAreaRectContract:
    """模拟宇宙文本 area 的 ADR-0215 重叠契约。"""

    def test_esc_menu_temp_leave_area_matches_full_ocr(self, test_context: SrTestContext) -> None:
        """esc菜单「差分宇宙-暂离」rect 须罩住全图 OCR '暂离' 检测框(默认 crop_first=False)。"""
        if not test_context.has_screen('模拟宇宙', 'esc菜单'):
            pytest.skip('缺 fixture: screens/模拟宇宙/esc菜单.webp')
        screen = test_context.load_screen('模拟宇宙', 'esc菜单')
        area = test_context.screen_loader.get_area('模拟宇宙', '差分宇宙-暂离')
        assert area is not None and area.is_text_area
        assert find_area_in_screen(test_context, screen, area) == FindAreaResultEnum.TRUE, (
            '差分宇宙-暂离 未命中:pc_rect 与全图 OCR 检测框重叠率不足(ADR-0215 契约回归;'
            'fixture OCR 检测框 y=792..830)'
        )
        # 同屏邻按钮回归:校正后的 rect 不应误吞「结束并结算」所在 y 带
        area2 = test_context.screen_loader.get_area('模拟宇宙', '菜单-结束并结算')
        assert area2 is not None
        assert find_area_in_screen(test_context, screen, area2) == FindAreaResultEnum.TRUE

    def test_elite_level_area_requires_crop_first(self, test_context: SrTestContext) -> None:
        """「怪物上方等级」:默认全图 OCR 并框漏检,消费点口径 crop_first=True 必须命中。

        精英区 fixture 上全图 OCR 把「等级84蚕食者之影,」并成一个检测框
        (x=852..1082),area rect [804,38,915,75] 只能罩住并框左端
        (~27% 重叠)→ 默认路径静默 FALSE;裁剪后 OCR 读到「等级8」LCS 命中。
        """
        if not test_context.has_screen('模拟宇宙', '区域-精英'):
            pytest.skip('缺 fixture: screens/模拟宇宙/区域-精英.webp')
        screen = test_context.load_screen('模拟宇宙', '区域-精英')
        area = test_context.screen_loader.get_area('模拟宇宙', '怪物上方等级')
        assert area is not None and area.is_text_area
        assert find_area_in_screen(test_context, screen, area, crop_first=True) == FindAreaResultEnum.TRUE, (
            '怪物上方等级 crop_first=True 未命中:精英检测(SimUniFightElite._check_enemy)会退化为纯 YOLO 兜底'
        )
        # 非精英/休整区 fixture:无怪物等级 → 不应命中(防误检)
        for state in ('区域-战斗', '区域-休整'):
            if not test_context.has_screen('模拟宇宙', state):
                continue
            other = test_context.load_screen('模拟宇宙', state)
            assert find_area_in_screen(test_context, other, area, crop_first=True) != FindAreaResultEnum.TRUE, (
                f'{state} 上怪物上方等级 不应命中'
            )
