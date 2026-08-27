"""升星预览✦(商店牌头顶 merge preview)单帧锁。

信号语义(发现 / ADR-0416):商店牌 art 顶部✦数 = 已持同名同星副本份数,
买第 3 张即 3合1 升星——bot tracking merge_progress 的视觉印证(观测层冗余信号)。
读取器 ``read_merge_preview``(cw_identity_obs)挂 ``read_shop_cards`` → ``ShopCard.merge_preview``。

fixture ``shop_open_preview_star.webp`` 真值(2026-09-05 亲读帧):5 张牌中仅
card5 万敌(试用)头顶 2 颗✦,card1-4 无✦。评分层消费方未备(decision_v2 的
merge_progress 走 bot tracking,未接视觉源)→ 本批只落观测值+遥测,接线待排期。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from sr_od.application.currency_war.cw_identity_obs import (
    _load_preview_sparkle_tmpl,
    read_merge_preview,
)
from sr_od.application.currency_war.cw_observation import read_shop_cards
from sr_od.application.currency_war.cw_state import ShopCard

if TYPE_CHECKING:
    from test.conftest import SrTestContext

SCREEN = '货币战争-备战-开商店'
STATE = 'shop_open_preview_star'
# 商店牌-1..5 area(assets/game_data/screen_info/currency_war_battle_prep_shop_open.yml)
CARD_RECTS = [(392, 70, 610, 260), (645, 70, 863, 260), (898, 70, 1116, 260),
              (1151, 70, 1369, 260), (1405, 70, 1623, 260)]


def test_sparkle_template_asset_exists() -> None:
    """模板资产在库(缺 = read_merge_preview 恒 0,信号静默失能)。"""
    assert _load_preview_sparkle_tmpl() is not None, \
        'assets/template/currency_war/star/shop_preview_sparkle_tmpl.png 缺失'


def test_read_merge_preview_fixture_lock(test_context: SrTestContext) -> None:
    """fixture 单帧锁:card5 万敌头顶 2✦ → 读 2;card1-4 无✦ → 读 0。

    直接裁 area rect 调读取器(锁视觉算法本体,不经 SIFT/OCR 门)。
    """
    if not test_context.has_screen(SCREEN, STATE):
        pytest.skip(f'存档截图缺失:screens/{SCREEN}/{STATE}.webp')
    screen = test_context.load_screen(SCREEN, STATE)
    got = [read_merge_preview(screen[y1:y2, x1:x2]) for (x1, y1, x2, y2) in CARD_RECTS]
    assert got == [0, 0, 0, 0, 2], f'升星预览✦读取错,实际 {got}(期望仅 card5=2)'


def test_read_shop_cards_fills_merge_preview(test_context: SrTestContext) -> None:
    """生产路径锁:read_shop_cards 全链(收起门+SIFT+✦读取)→ card5.merge_preview=2。

    兼锁字段默认与 0 双义语义:无✦牌 merge_preview=0(未观测,勿当「确认无副本」)。
    """
    if not test_context.has_screen(SCREEN, STATE):
        pytest.skip(f'存档截图缺失:screens/{SCREEN}/{STATE}.webp')
    screen = test_context.load_screen(SCREEN, STATE)
    cards = read_shop_cards(test_context, screen)
    assert len(cards) == 5, f'应读满 5 张牌,实际 {len(cards)}'
    assert cards[4].name == '万敌', f'card5 应 SIFT 识别为万敌,实际 {cards[4].name!r}'
    assert [c.merge_preview for c in cards] == [0, 0, 0, 0, 2]
    assert ShopCard(x=1).merge_preview == 0, '新字段默认 0(旧构造点零改动)'


def test_read_merge_preview_template_missing_failsilent(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """模板缺失 → 返 0(fail-silent),不抛异常不误报✦。"""
    if not test_context.has_screen(SCREEN, STATE):
        pytest.skip(f'存档截图缺失:screens/{SCREEN}/{STATE}.webp')
    screen = test_context.load_screen(SCREEN, STATE)
    x1, y1, x2, y2 = CARD_RECTS[4]
    monkeypatch.setattr(
        'sr_od.application.currency_war.cw_identity_obs._load_preview_sparkle_tmpl',
        lambda: None)
    assert read_merge_preview(screen[y1:y2, x1:x2]) == 0
