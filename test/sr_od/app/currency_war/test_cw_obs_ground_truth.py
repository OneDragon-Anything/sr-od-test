"""obs 识别层·真实图片识别锚(重建合同 ⑤;测试纪律第 21 条)。

识别类测试以真实截图为准,禁止合成图片。每条锚 = 一张真实正常帧 + 一次读取
一次识别 + 人工确认的真值(注释注明来源与确认方式);一图一测聚合该图全部
检查面。样本事故驱动增量:识别出错的实况帧每种情况补 1 张,不预先铺满。

挂账(正常样本待裁剪入库,按第 21 条随重建/改函数补):
find_bookcards(待 gold_card 语义核对后判定,疑似已有主)。
已锚并划掉:read_merge_preview(本文件 TestMergePreviewGroundTruth);
detect_bench_avatars / detect_empty_slots /
detect_board_slots / detect_slot_centers——生产零外部消费死码已删,不补样本。
read_merge_preview 已锚(本文件 TestMergePreviewGroundTruth:正样本 =
shop_open_preview_star 帧 card5 ✦=2 看图确认,负样本 = shop_open 帧全 0);
find_bookcards 待 gold_card 语义核对后判定(疑似已有主)。
read_star(find_tomes/find_supply_boxes)由 test_cw_data_registry 现役主题件
(装备识别与身份真值锚)辖;prep_stall 帧的 SIFT 身份+星级真值对已并入
test_cw_identity_funnel(一图一测:该帧全库 SIFT 只在那里跑一次;
真值 2026-09-12 看图核对 + 用户裁决:花火 1★)。
"""
from pathlib import Path

import pytest

from one_dragon.utils import cv2_utils
from one_dragon.utils.file_utils import get_project_root

_DIR = Path(__file__).resolve().parent
_SCREEN_DIR = get_project_root() / 'sr-od-test' / 'screens' / '货币战争-备战'


def _read(rel: Path):
    img = cv2_utils.read_image(str(rel))
    assert img is not None, f'真帧缺失: {rel}(cv2_utils 全 RGB)'
    return img


# ===== 节点行 CV/Hu(cw_node_reader;真帧 = 1-1 备战整行裁片) =====

class TestNodeRowGroundTruth:
    """节点行真帧锚:三态着色 + Hu 矩未来节点类型 + boss 位置判(SIFT)。"""

    @pytest.fixture(scope='class')
    def templates(self):
        from sr_od.application.currency_war.obs.cw_node_reader import (
            load_node_type_templates,
        )
        tpls = load_node_type_templates(
            get_project_root() / 'assets' / 'game_data' / 'cw_node_types')
        assert tpls, '节点类型模板缺失(assets/game_data/cw_node_types)'
        return tpls

    def test_clean_row_8_slots(self, templates):
        # 1-1 备战 8 槽:1 当前 + 7 未来;未来类型序列为该帧真值
        # (确认方式:2026-08-12 单对局实证 + 2026-02-02 复跑识别一致)
        img = _read(_DIR / 'cw_node_row_clean.png')
        from sr_od.application.currency_war.obs.cw_node_reader import classify_node_row
        slots = classify_node_row(img, templates)
        assert [s.state for s in slots] == (
            ['current'] + ['upcoming'] * 7)
        assert [s.node_type for s in slots[1:]] == (
            ['reward', 'battle', 'battle', 'supply', 'battle',
             'encounter', 'encounter'])

    def test_boss_row_9_slots_last_is_boss(self, templates):
        # 9 槽帧(人身意外险+1):位面最后节点 = boss,按位置判 + SIFT 认身份;
        # 未来类型序列真值同上口径
        img = _read(_DIR / 'cw_node_row_boss.png')
        from sr_od.application.currency_war.obs.cw_node_reader import (
            classify_node_row,
            load_boss_templates,
        )
        boss_tpls = load_boss_templates(
            get_project_root() / 'assets' / 'template' / 'currency_war' / 'boss_avatar')
        slots = classify_node_row(img, templates, boss_templates=boss_tpls)
        assert len(slots) == 9
        assert slots[-1].boss == '巨鹿生物制药'   # SIFT boss 身份(真帧确认)
        assert [s.node_type for s in slots[1:8]] == (
            ['reward', 'battle', 'battle', 'supply', 'battle',
             'encounter', 'reward'])


# ===== 槽位占用判据(currency_war_cv.slot_occupied;现役唯一 CV 消费面) =====

class TestSlotOccupiedGroundTruth:
    """占用判据真帧锚:prep_stall 帧槽位占用态(真值 = 看图人工核对——
    前排 4 全有角色 / 后排 1-3 有角色、4-6 空)。rect 单一源 = screen_info。"""

    def test_prep_frame_occupancy_truth(self, test_context):
        from sr_od.application.currency_war.kernel.cw_obs_core import _area_rect
        from sr_od.application.currency_war.obs.currency_war_cv import slot_occupied
        img = _read(_DIR / 'fixtures' / 'prep_stall_1788434979565.png')

        def _center(area_name: str):
            rect = _area_rect(test_context, area_name, '货币战争-备战')
            assert rect is not None, f'area 缺: {area_name}'
            return (rect.x1 + rect.x2) // 2, (rect.y1 + rect.y2) // 2

        occupied = [f'前排-{i}' for i in range(1, 5)] + [f'后排-{i}' for i in (1, 2, 3)]
        empty = [f'后排-{i}' for i in (4, 5, 6)]
        for name in occupied:
            cx, cy = _center(name)
            assert slot_occupied(img, cx, cy) is True, f'{name} 应为已占'
        for name in empty:
            cx, cy = _center(name)
            assert slot_occupied(img, cx, cy) is False, f'{name} 应为空槽'


# ===== 后台格数 CV 通道(cw_back_layout;真帧 = screens/货币战争-备战 布局族) =====

class TestCvBackSlotsGroundTruth:
    """std 剖面三态探针真帧锚(5 代表帧覆盖全部分支 + 越界守卫)。"""

    def test_six_grid_frame(self):
        # run26 崩坏现场(6 格;W292 事故响应批真值帧,事故形态直接回归锚)
        assert cbl_slots('后排6槽-run26崩坏现场.png') == 6

    def test_six_grid_none_branch(self):
        # shop_closed 帧(none,none)→ 6:两端纯背景分支
        assert cbl_slots('shop_closed.webp') == 6

    def test_seven_grid_frame(self):
        # 佩佩局拖测后(7 格;(slice,slice) 切片签名分支;2026-08-26 交互实锤)
        assert cbl_slots('后排7槽-佩佩局-拖测后.png') == 7

    def test_eight_grid_frame(self):
        # 狸猫局(8 格;(full,full) 分支;docstring 标定分布 8 格档 38.8-65.6 来源帧族)
        assert cbl_slots('后排8槽-狸猫局.webp') == 8

    def test_eight_grid_empty_slot_still_full(self):
        # P3 局(cap11):左 1 空槽暗框 = 整格存在证据(占用态门消解旧不可判带)→ 8
        assert cbl_slots('后排8槽-P3局.webp') == 8

    def test_non_1080p_frame_undeterminable(self):
        # 非 1080p 小帧:越界守卫 → None(不可判退公式,不猜)
        import numpy as np

        from sr_od.application.currency_war.obs.cw_back_layout import cv_back_slots
        assert cv_back_slots(np.zeros((600, 900, 3), dtype=np.uint8)) is None


def cbl_slots(name: str):
    from sr_od.application.currency_war.obs.cw_back_layout import cv_back_slots
    return cv_back_slots(_read(_SCREEN_DIR / name))


# ===== 结算页 1 真帧(settlement;像素判据 + 区域 OCR,一图聚合) =====

class TestSettlePage1GroundTruth:
    """结算页 1 真帧:进度条填充比(纯像素)+ 掉血 tooltip 三分量(区域真 OCR)。

    fill_ratio = 画面确定性读数(进度条填充了几分之几),非分布统计——
    阈值漂移/算法改动会红,红有语义。真值确认方式 = 2026-02-02 看图人工
    核对(红条右缘位置)。
    """

    def test_fail_page1_fill_ratio(self):
        # 战败页 1:红条填充约 36%(看图:填充至条槽 x≈890,槽 710..1210)
        img = _read(_DIR / 'fixtures_settle' / 'end_final_fail_minus17.png')
        from sr_od.application.currency_war.obs.cw_settlement_obs import (
            parse_progress_fill_ratio,
        )
        assert parse_progress_fill_ratio(img) == pytest.approx(0.36, abs=0.01)

    def test_boss_win_page1_fill_and_breakdown(self, test_context):
        # boss 胜局页 1(「1-9 首领」):填充约 82.8%;tooltip 三行真值
        # = 基础伤害 -10 / 未完成进度伤害 -1 / 长线作战 +2(看图肉眼确认)
        img = _read(_DIR / 'fixtures_settle'
                    / 'end_boss_win_with_breakdown_panel.png')
        from sr_od.application.currency_war.obs.cw_settlement_obs import (
            parse_progress_fill_ratio,
            read_settle_damage_breakdown,
        )
        assert parse_progress_fill_ratio(img) == pytest.approx(0.828, abs=0.01)
        panel = read_settle_damage_breakdown(test_context, img)
        assert panel['visible'] is True
        assert panel['damage_base'] == -10
        assert panel['damage_unfinished_progress'] == -1
        assert panel['heal_longline'] == 2

    def test_loss_page1_panel_absent(self, test_context):
        # 事故形态负例(第 21 条 bug 样本):败局页 1 无 tooltip 面板
        # → visible=False + 两分量 None(删失显式,不冒认)
        img = _read(_DIR / 'fixtures_settle' / 'end_loss_no_panel_minus12.png')
        from sr_od.application.currency_war.obs.cw_settlement_obs import (
            read_settle_damage_breakdown,
        )
        panel = read_settle_damage_breakdown(test_context, img)
        assert panel['visible'] is False
        assert panel['damage_base'] is None
        assert panel['damage_unfinished_progress'] is None

    def test_briefing_default_frame_reads(self, test_context):
        # 简报帧三读聚合(一图一测):同一张 default.webp 的词缀行/首领行/难度标识
        # fixture = screens/货币战争-简报/default.webp(A8 局;boss 名跨局随机
        # 只锁数量与形状)
        if not test_context.has_screen('货币战争-简报', 'default'):
            pytest.skip('fixture 缺:screens/货币战争-简报/default.webp')
        screen = test_context.load_screen('货币战争-简报', 'default')
        from sr_od.application.currency_war.obs.cw_briefing_obs import (
            read_affixes,
            read_bosses,
            read_briefing_enemy_difficulty,
        )
        affixes = read_affixes(test_context, screen)
        assert len(affixes) == 4, f'期望 4 词缀(A8 最高),实际 {affixes}'
        assert any(k in '/'.join(affixes)
                   for k in ('强化', '不利', '废', '幸运', '熄火', '行动')), affixes
        bosses = read_bosses(test_context, screen)
        assert len(bosses) == 3, f'期望 3 boss(3 位面),实际 {bosses}'
        assert all(4 <= len(b) <= 8 for b in bosses), bosses   # 中文 4-8 字公司名
        difficulty = read_briefing_enemy_difficulty(test_context, screen)
        assert difficulty is not None and 0 < difficulty <= 300, difficulty


# ===== 升星预览 ✦(cw_identity_obs.read_merge_preview;真帧 = 开商店档) =====

class TestMergePreviewGroundTruth:
    """商店牌头顶 ✦ 数(= 已持同名同星副本份数)真帧锚。

    真值确认 = 看图人工核对(2026-09-12):shop_open_preview_star 帧仅 card5
    (万敌,试用标)头顶 2 个金色 ✦,其余 4 牌无——我方持万敌同名同星副本
    2 份形态。负样本 = shop_open 帧(同店态无副本)全 0,与正样本同测试
    聚合对照(0 是合法语义:该牌无已持副本)。
    """

    def _previews(self, test_context, frame_name: str) -> list[int]:
        from sr_od.application.currency_war.kernel.cw_obs_core import _area_rect
        from sr_od.application.currency_war.obs.cw_identity_obs import (
            read_merge_preview,
        )
        img = _read(_SCREEN_DIR.parent / '货币战争-备战-开商店' / frame_name)
        out = []
        for i in range(1, 6):
            rect = _area_rect(test_context, f'商店牌-{i}', '货币战争-备战-开商店')
            assert rect is not None, f'商店牌-{i} area 缺'
            out.append(read_merge_preview(img[rect.y1:rect.y2, rect.x1:rect.x2]))
        return out

    def test_preview_star_frame(self, test_context):
        assert self._previews(test_context, 'shop_open_preview_star.webp') == \
            [0, 0, 0, 0, 2]

    def test_no_preview_frame_all_zero(self, test_context):
        # 负样本:无副本店帧全 0(0 = 「无✦」合法语义,非失读)
        assert self._previews(test_context, 'shop_open.webp') == [0, 0, 0, 0, 0]
