"""进入游戏 op:同意按钮位置测试(旧/新登录画面)+ 版本更新日登录弹窗分支 +
战斗退出链恢复态分支(暂停面板/退出确认弹窗/结算页)。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from one_dragon.base.matcher.ocr import ocr_utils
from one_dragon.utils import cv2_utils
from sr_od.operations.enter_game.enter_game import (
    STORY_REMINDER_WORDS,
    UNKNOWN_FALLBACK_ROUNDS,
    EnterGame,
)
from test.harness.fixture_controller import FixtureController


def test_agree(test_context, test_image_dir: Path) -> None:
    """测试同意按钮的位置。"""
    op = EnterGame(test_context)

    screen = cv2_utils.read_image(str(test_image_dir / 'old_login.png'))
    r1 = op.round_by_find_area(screen, '进入游戏', '文本-同意-旧')
    assert r1.is_success
    r2 = op.round_by_find_area(screen, '进入游戏', '文本-同意-新')
    assert not r2.is_success

    screen = cv2_utils.read_image(str(test_image_dir / 'new_login.png'))
    r1 = op.round_by_find_area(screen, '进入游戏', '文本-同意-旧')
    assert not r1.is_success
    r2 = op.round_by_find_area(screen, '进入游戏', '文本-同意-新')
    assert r2.is_success


def _make_fixture_controller(
    test_context,
    monkeypatch: pytest.MonkeyPatch,
) -> FixtureController:
    """构造记录点击的假控制器并注入 test_context(测试结束自动还原)。"""
    ctrl = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    return ctrl


def test_story_reminder_skip(
    test_context,
    test_image_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """版本剧情提醒弹窗:「稍后再看」「观看前情提要」双词同现 → 点「稍后再看」跳过。

    fixture:剧情提醒弹窗整帧实机截图。「稍后再看」按钮真值矩形约
    (543,730)-(928,800),点击应落在其中。
    """
    ctrl = _make_fixture_controller(test_context, monkeypatch)

    op = EnterGame(test_context)
    screen = cv2_utils.read_image(str(test_image_dir / 'story_reminder.webp'))
    result = op.check_story_reminder(test_context.ocr.run_ocr(screen))

    assert result is not None and not result.is_success, '命中弹窗应返回重试结果'
    assert len(ctrl.recorded_clicks) == 1, f'应恰好点击一次:{ctrl.recorded_clicks}'
    click = ctrl.recorded_clicks[0]
    assert 543 <= click.x <= 928 and 730 <= click.y <= 800, (
        f'点击应落在「稍后再看」按钮真值矩形内:{click}'
    )


def test_story_reminder_requires_both_words(
    test_context,
    test_image_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """双词判据:判定词只出现一个时不得动作(防他屏同位文字误配触发误点击)。

    输入 = 同一张弹窗帧的 OCR 结果过滤掉「观看前情提要」条目(模拟单按钮
    被遮挡/漏识别的形态);前置断言确保过滤前后判定词数量真的从 2 变 1,
    防止 OCR 本身漏识别造成假绿。
    """
    ctrl = _make_fixture_controller(test_context, monkeypatch)

    op = EnterGame(test_context)
    screen = cv2_utils.read_image(str(test_image_dir / 'story_reminder.webp'))
    ocr_map = test_context.ocr.run_ocr(screen)

    # 前置验证走 ocr_utils 工具(零副作用):整帧 OCR 确实同时识别出两词,
    # 防止 fixture 图 OCR 质量退化造成本测试假绿。不走被测方法——它命中会点击。
    match_map = ocr_utils.match_all_words(ocr_map, STORY_REMINDER_WORDS)
    assert len(match_map) == len(STORY_REMINDER_WORDS), (
        '前置失效:整帧 OCR 未同时识别出两个判定词,fixture 失效'
    )

    filtered_map = {
        text: mrl for text, mrl in ocr_map.items() if '观看前情提要' not in text
    }
    assert any('稍后再看' in text for text in filtered_map), (
        '前置失效:过滤后「稍后再看」不在 OCR 结果中,无法构造单词场景'
    )

    result = op.check_story_reminder(filtered_map)
    assert result is None, '单词出现时不得动作'
    assert len(ctrl.recorded_clicks) == 0, f'不得有点击:{ctrl.recorded_clicks}'


def test_version_promo_right_top_fallback(
    test_context,
    test_image_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未知画面(新角色跃迁宣传页)兜底:登录已过闸 + 连续未知轮达标 → 点「菜单-右上角返回」。

    fixture:版本宣传页整帧实机截图(整屏宣传画 + 右上角关闭钮,无登录区/角色图标,
    OCR 无登录页标志词)。
    """
    ctrl = _make_fixture_controller(test_context, monkeypatch)

    op = EnterGame(test_context)
    op._login_clicked = True  # 闸①:登录页已通过(测试构造场景直设内部计数,常规工作面)
    op._unknown_rounds = UNKNOWN_FALLBACK_ROUNDS - 1  # 闸②:本轮结束后达到门槛
    op.last_screenshot = cv2_utils.read_image(str(test_image_dir / 'version_promo.webp'))
    result = op.check_screen()

    assert not result.is_success, '未知画面应返回重试结果'
    assert ctrl.click_hit_area('菜单', '右上角返回'), (
        f'应点击「菜单-右上角返回」区域:{ctrl.recorded_clicks}'
    )


def test_fallback_skipped_before_login_clicked(
    test_context,
    test_image_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """闸①:登录页未通过(_login_clicked=False)时,未知画面不得点右上角。

    登录阶段不存在版本宣传页,兜底整体不启用——防登录页/转场帧误触右上角
    「公告」等菜单按钮热区(其坐标与返回钮重叠)。
    """
    ctrl = _make_fixture_controller(test_context, monkeypatch)

    op = EnterGame(test_context)
    op._unknown_rounds = UNKNOWN_FALLBACK_ROUNDS  # 计数给足,只差登录闸
    op.last_screenshot = cv2_utils.read_image(str(test_image_dir / 'version_promo.webp'))
    op.check_screen()

    assert len(ctrl.recorded_clicks) == 0, f'登录未过闸不得点右上角:{ctrl.recorded_clicks}'


def test_fallback_skipped_on_login_page(
    test_context,
    test_image_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """闸③:本轮 OCR 有登录页标志词「公告」时不得点右上角(该位置是公告按钮热区)。

    fixture:旧登录画面(账号密码页,OCR 含「公告」)。场景构造 = 已点过点击进入
    (弹回登录页) + 连续未知轮达标——正是曾误开公告的现场形态。
    """
    ctrl = _make_fixture_controller(test_context, monkeypatch)

    op = EnterGame(test_context)
    op._login_clicked = True
    op._unknown_rounds = UNKNOWN_FALLBACK_ROUNDS - 1
    op.last_screenshot = cv2_utils.read_image(str(test_image_dir / 'old_login.png'))
    op.check_screen()

    assert len(ctrl.recorded_clicks) == 0, f'登录页上不得点右上角:{ctrl.recorded_clicks}'


# --------------------------------------------------------------------------- #
# 战斗退出链恢复态分支(三分支:确认弹窗 → 暂停面板 → 结算页)。
#
# 背景:客户端重启恢复中断战斗直接落在战斗画面族(暂停面板/确认弹窗/结算页),
# 三类画面无正面识别分支时全部落未知兜底——兜底右上角点击位与暂停面板关闭X
# 同位,陷入「点X关面板→回战斗→再点→再弹面板」循环。三分支插入在未知兜底
# 之前,分支序固定弹窗先于面板(弹窗态下面板锚是否可见随玩法形态而异,防御侧
# 排序)。恢复态光标可能锁定:所有退出链点击必须 pc_alt=True。
# --------------------------------------------------------------------------- #


def _spy_pc_alt(
    ctrl: FixtureController,
    monkeypatch: pytest.MonkeyPatch,
) -> list[bool]:
    """包装 ctrl.click 记录每次点击的 pc_alt(恢复态锁光标加固锁)。"""
    alts: list[bool] = []
    real_click = ctrl.click

    def _spy(pos=None, press_time=0, pc_alt=False, gamepad_key=None):
        alts.append(bool(pc_alt))
        return real_click(pos=pos, press_time=press_time, pc_alt=pc_alt,
                          gamepad_key=gamepad_key)

    monkeypatch.setattr(ctrl, 'click', _spy)
    return alts


def _assert_single_click_at_area_center(
    test_context,
    ctrl: FixtureController,
    alts: list[bool],
    screen_name: str,
    area_name: str,
) -> None:
    """恰一次点击、落在指定 area 中心、且带 pc_alt=True。"""
    area = test_context.screen_loader.get_area(screen_name, area_name)
    assert area is not None, f'{screen_name}/{area_name} area 未建档'
    clicks = ctrl.recorded_clicks
    assert len(clicks) == 1 and len(alts) == 1, (
        f'应恰一次点击:{clicks} / pc_alt 账:{alts}'
    )
    click = clicks[0]
    assert (int(click.x), int(click.y)) == (int(area.center.x), int(area.center.y)), (
        f'点击应为 {screen_name}/{area_name} 中心({area.center.x},{area.center.y}):{click}'
    )
    assert alts[0], f'恢复态点击必须带 pc_alt=True:{alts}'


def test_battle_pause_panel_exit_branch(
    test_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """暂停面板帧:命中暂停面板分支,点「退出位」area 中心(pc_alt=True)。

    退出位按位置不按文案(末日幻影/虚构叙事/货币战争同位异文案),fixture =
    末日幻影形态实机帧。退出操作不可逆但零消耗(TL 系列免费挑战),且只在登录
    恢复语境触发,无「有效战斗被误杀」风险。
    """
    if not test_context.has_screen('战斗-暂停面板', '末日幻影形态'):
        pytest.skip('存档截图缺失:screens/战斗-暂停面板/末日幻影形态.webp')

    ctrl = _make_fixture_controller(test_context, monkeypatch)
    alts = _spy_pc_alt(ctrl, monkeypatch)

    op = EnterGame(test_context)
    op.last_screenshot = test_context.load_screen('战斗-暂停面板', '末日幻影形态')
    result = op.check_screen()

    assert not result.is_success, '命中分支应 round_retry 逐帧重识别'
    assert result.status == '战斗暂停面板', f'分支状态漂移:{result.status}'
    _assert_single_click_at_area_center(
        test_context, ctrl, alts, '战斗-暂停面板', '按钮-结束战斗并结算',
    )


def test_battle_exit_confirm_dialog_branch(
    test_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """确认弹窗帧:分支B 双锚命中,点「按钮-确认」area 中心(pc_alt=True)。

    分支B 的启用条件 = 既有「确认」词 OCR 分支未命中但弹窗存在(OCR 漏识兜底),
    故桩掉 check_screen_to_interact 模拟 OCR 未命中,双锚正面识别照真跑。
    弹窗盖面板(模态):同时断言不点退出位——弹窗先于面板判定,面板分支不得
    对被弹窗遮住的退出位重复点击。
    """
    if not test_context.has_screen('战斗-退出确认弹窗', '末日幻影形态'):
        pytest.skip('存档截图缺失:screens/战斗-退出确认弹窗/末日幻影形态.webp')

    ctrl = _make_fixture_controller(test_context, monkeypatch)
    alts = _spy_pc_alt(ctrl, monkeypatch)
    monkeypatch.setattr(EnterGame, 'check_screen_to_interact', lambda self, screen: None)

    op = EnterGame(test_context)
    op.last_screenshot = test_context.load_screen('战斗-退出确认弹窗', '末日幻影形态')
    result = op.check_screen()

    assert not result.is_success, '命中分支应 round_retry 逐帧重识别'
    assert result.status == '战斗退出确认弹窗', f'分支状态漂移:{result.status}'
    _assert_single_click_at_area_center(
        test_context, ctrl, alts, '战斗-退出确认弹窗', '按钮-确认',
    )
    # 弹窗盖面板:退出位零点击(点它会被模态挡住,形成死循环)
    assert not ctrl.click_hit_area('战斗-暂停面板', '按钮-结束战斗并结算'), (
        f'弹窗态不得点退出位:{ctrl.recorded_clicks}'
    )


def test_battle_settle_page_exit_branch(
    test_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """结算页帧:命中结算页分支,点「退出」OCR 文字中心(pc_alt=True)。

    结算页右上角无按钮、无「确认」词,是退出链必经中间站;点击目标 = OCR 命中
    文字本身(免建 area)。fixture 用节点结算形态(底部 退出/重新挑战/前往节点二,
    「退出」真值矩形 = 节点结算.按钮-退出 建档矩形)——登录恢复退出链实测走
    此形态;判定词「挑战结束」为结算页独有标题,「挑战成功/战斗失败」不撞。
    """
    if not test_context.has_screen('末日幻影-节点结算', '节点结算-退出按钮'):
        pytest.skip('存档截图缺失:screens/末日幻影-节点结算/节点结算-退出按钮.webp')

    ctrl = _make_fixture_controller(test_context, monkeypatch)
    alts = _spy_pc_alt(ctrl, monkeypatch)

    op = EnterGame(test_context)
    op.last_screenshot = test_context.load_screen(
        '末日幻影-节点结算', '节点结算-退出按钮')
    result = op.check_screen()

    assert not result.is_success, '命中分支应 round_retry 逐帧重识别'
    assert result.status == '战斗退出结算页', f'分支状态漂移:{result.status}'
    exit_area = test_context.screen_loader.get_area('末日幻影-节点结算', '按钮-退出')
    assert exit_area is not None, '末日幻影-节点结算/按钮-退出 area 未建档'
    assert len(ctrl.recorded_clicks) == 1 and len(alts) == 1, (
        f'应恰一次点击:{ctrl.recorded_clicks}'
    )
    rect = exit_area.pc_rect
    click = ctrl.recorded_clicks[0]
    assert rect.x1 <= click.x <= rect.x2 and rect.y1 <= click.y <= rect.y2, (
        f'点击应落在「退出」文字真值矩形内({rect.x1},{rect.y1})-({rect.x2},{rect.y2}):{click}'
    )
    assert alts[0], f'恢复态点击必须带 pc_alt=True:{alts}'


def test_battle_settle_page_without_exit_word_no_action(
    test_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """结算页无「退出」词的形态(总结算:重新挑战/返回末日幻影):分支C 不动作。

    「挑战结束」命中但「退出」未命中(形态差异)→ 不点击、落未知兜底(兜底
    闸未开则零点击)——有界失败优于误点「重新挑战」重启战斗。
    """
    if not test_context.has_screen('末日幻影-节点结算', '最终结算'):
        pytest.skip('存档截图缺失:screens/末日幻影-节点结算/最终结算.webp')

    ctrl = _make_fixture_controller(test_context, monkeypatch)

    op = EnterGame(test_context)
    op.last_screenshot = test_context.load_screen('末日幻影-节点结算', '最终结算')
    result = op.check_screen()

    assert len(ctrl.recorded_clicks) == 0, (
        f'无「退出」词形态不得有动作(防误点重新挑战):{ctrl.recorded_clicks}'
    )
    assert not result.is_success, '未动作应继续重试等待兜底'


def test_confirm_dialog_takes_priority_over_pause_panel(
    test_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """弹窗+面板同帧(双识别锚同现的最坏形态):分支B 先于分支A。

    mock 识别零识别成本:三类锚全部命中时,check_screen 必须路由到确认弹窗分支
    (点确认钮中心),暂停面板分支不得再触达(否则对被弹窗遮住的退出位重复
    点击形成死循环)。识别层真值由 test_id_mark 与上两条真帧测试锁定。
    """
    ctrl = _make_fixture_controller(test_context, monkeypatch)
    alts = _spy_pc_alt(ctrl, monkeypatch)

    hit_set = {
        ('战斗-退出确认弹窗', '标识-提示'),
        ('战斗-退出确认弹窗', '按钮-确认'),
        ('战斗-暂停面板', '标识-战斗暂停'),
    }

    def _fake_find_area(self, screen, s_name, a_name, *args, **kwargs):
        if (s_name, a_name) in hit_set:
            return self.round_success(status=a_name)
        return self.round_wait(status=f'未找到 {a_name}')

    monkeypatch.setattr(EnterGame, 'round_by_find_area', _fake_find_area)
    monkeypatch.setattr(
        EnterGame, 'round_by_find_and_click_area',
        lambda self, screen, s_name, a_name, *a, **k: self.round_wait(
            status=f'未找到 {a_name}'),
    )
    monkeypatch.setattr(EnterGame, 'check_screen_to_interact', lambda self, screen: None)

    op = EnterGame(test_context)
    op.last_screenshot = np.zeros((1080, 1920, 3), dtype=np.uint8)
    result = op.check_screen()

    assert not result.is_success, '命中分支应 round_retry 逐帧重识别'
    assert result.status == '战斗退出确认弹窗', f'应路由到确认弹窗分支:{result.status}'
    _assert_single_click_at_area_center(
        test_context, ctrl, alts, '战斗-退出确认弹窗', '按钮-确认',
    )


def test_normal_frames_not_caught_by_battle_exit_branches(
    test_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """大世界帧/普通登录帧:新分支零误触发,原路由照常成功。

    大世界帧 → 「角色图标」分支直接 SUCCESS(零点击);登录帧 → 登录分支接管
    (唯一点击 = 「文本-点击进入」)。战斗退出链点击落空 = 误触发回归。
    """
    ctrl = _make_fixture_controller(test_context, monkeypatch)

    # 大世界帧:原路由 SUCCESS,零点击
    op = EnterGame(test_context)
    op.last_screenshot = test_context.load_screen('大世界', '普通')
    result = op.check_screen()
    assert result.is_success and result.status == '大世界', (
        f'大世界帧应直接成功:{result.status}'
    )
    assert len(ctrl.recorded_clicks) == 0, (
        f'大世界帧不得有任何点击(含战斗退出链):{ctrl.recorded_clicks}'
    )

    # 登录帧:原路由(登录分支)接管
    if test_context.has_screen('进入游戏', '点击进入'):
        ctrl.recorded_clicks.clear()
        op2 = EnterGame(test_context)
        op2.last_screenshot = test_context.load_screen('进入游戏', '点击进入')
        result2 = op2.check_screen()
        assert result2.status == '文本-点击进入', (
            f'登录帧应由登录分支接管:{result2.status}'
        )
        assert ctrl.click_hit_area('进入游戏', '文本-点击进入'), (
            f'登录帧应点击「文本-点击进入」:{ctrl.recorded_clicks}'
        )
        assert len(ctrl.recorded_clicks) == 1, (
            f'登录帧只应有一次登录点击:{ctrl.recorded_clicks}'
        )
