"""进入游戏 op:同意按钮位置测试(旧/新登录画面)+ 版本更新日登录弹窗分支。"""
from __future__ import annotations

from pathlib import Path

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
