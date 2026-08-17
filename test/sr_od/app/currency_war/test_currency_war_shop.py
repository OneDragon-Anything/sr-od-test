"""货币战争 商店牌读取测试。

``read_shop_cards`` **D-55 由 OCR 改 SIFT**(裁 商店牌-1..5 肖像区 → SIFT 立绘库 → 规范名;
OCR 对开拓者等自定义名读不到)。``read_game_state`` 的 HUD(gold/hp/level/plane)仍 OCR。
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from cv2.typing import MatLike

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import cv2_utils
from sr_od.application.currency_war.cw_evaluate import HP_DANGER
from sr_od.application.currency_war.cw_factions import FACTIONS
from sr_od.application.currency_war.cw_observation import (
    read_game_state,
    read_hp,
    read_shop_cards,
)

if TYPE_CHECKING:
    from test.conftest import SrTestContext


def _has_text(ctx: SrTestContext, screen: MatLike, kw: str) -> bool:
    """全屏 OCR,判断关键词是否出现(子串,容 OCR 分词差异)。"""
    texts = [m.data for m in
             ctx.ocr_service.get_ocr_result_list(image=screen, rect=Rect(0, 0, 1920, 1080))]
    return any(kw in t for t in texts)


def test_read_shop_cards_sift(test_context) -> None:
    """商店屏 → SIFT 读出 5 张牌名 + roster 派生 faction/cost(D-55 OCR→SIFT)。

    read_shop_cards 裁 ``商店牌-1..5`` 肖像区(VLM 定位)→ SIFT ``currency_war/portrait_plaza`` 官方立绘库
    → 规范名;faction/cost 从 roster 派生。fixture ``shop_open.webp`` GT:翡翠/丹恒·腾荒/不死途/飞霄/三月七。
    """
    if not test_context.has_screen('货币战争-备战', 'shop_open'):
        pytest.skip('存档截图缺失:screens/货币战争-备战/shop_open.webp')
    screen = test_context.load_screen('货币战争-备战', 'shop_open')
    cards = read_shop_cards(test_context, screen)
    gt = ['翡翠', '丹恒·腾荒', '不死途', '飞霄', '三月七']
    assert [c.name for c in cards] == gt, f'SIFT 牌名错,实际 {[c.name for c in cards]}'
    assert all(c.faction in FACTIONS for c in cards), f'阵营应 roster 派生 ∈ FACTIONS,实际 {[c.faction for c in cards]}'
    assert all(c.cost >= 1 for c in cards), f'cost 应 roster 派生 ≥1,实际 {[c.cost for c in cards]}'


def test_read_game_state_prep(test_context, test_image_dir: Path) -> None:
    """备战屏 → read_game_state 读 gold/plane/round/board/shop + level 启发式(打印实测值)。"""
    screen = cv2_utils.read_image(str(test_image_dir / 'currency_war_shop.png'))
    state = read_game_state(test_context, screen)
    print(f'\n[game state] gold={state.gold} hp={state.hp} level={state.level} '
          f'plane={state.plane} round={state.round_num} board={state.board}')
    assert 0 <= state.gold <= 400, f'gold 越界 {state.gold}'
    assert 1 <= state.level <= 10, f'level 越界 {state.level}'
    assert 1 <= state.plane <= 3, f'plane 越界 {state.plane}'


def test_read_hp_shop_state(test_context, test_image_dir: Path) -> None:
    """HP 只在 shop **关闭**态显示右上角(shop 开启态该区空 → 默认 100)。

    多样本确认(2026-08-03):5 张 shop-关闭态全读到真 HP(80/80/80/29/84)、shop-开启态该区空。
    回归 guard:锁住 ``BuyShopCards``「shop 关闭帧读 hp 覆盖 state.hp」修复的前提 —— 改 read_hp /
    shop 流程后重跑本测试,确保 HP 读取行为不回归。
    """
    closed = cv2_utils.read_image(str(test_image_dir / 'currency_war_prep_closed.png'))        # shop 关,hp=84
    lowhp = cv2_utils.read_image(str(test_image_dir / 'currency_war_prep_closed_lowhp.png'))  # shop 关,hp=29
    open_shop = cv2_utils.read_image(str(test_image_dir / 'currency_war_shop.png'))           # shop 开,hp 区空
    assert read_hp(test_context, closed) == 84
    assert read_hp(test_context, lowhp) == 29
    assert read_hp(test_context, lowhp) < HP_DANGER, '低血(< HP_DANGER)应能让保血触发'
    assert read_hp(test_context, open_shop) == 100, 'shop 开 → HP 区空 → 默认 100'


def test_prep_anchor_buyexp_present_on_prep_absent_elsewhere(test_context, test_image_dir: Path) -> None:
    """``BuyShopCards`` 非备战屏守卫(2026-08-04 plane2 投资策略叠层实测)的前提:

    备战锚点「购买经验」在**备战屏有**(→ 守卫不触发,正常买牌)、**非备战屏无**(→ 守卫
    round_fail 快速退出,交主循环 loop 接手处理事件叠层;否则 round_retry 在非商店屏浪费
    max_retry 次后才恢复)。用可靠 fixture(备战 shop 屏 + 大厅)锁守卫检测前提,改守卫/OCR
    后重跑确保不回归。
    """
    prep = cv2_utils.read_image(str(test_image_dir / 'currency_war_shop.png'))        # 备战屏(shop 开,底部有「购买经验」)
    assert _has_text(test_context, prep, '购买经验'), '备战屏应有「购买经验」→ 守卫不触发,正常买牌'
    lobby = cv2_utils.read_image(str(test_image_dir / 'currency_war_lobby.png'))      # 货币战争大厅(非备战)
    assert not _has_text(test_context, lobby, '购买经验'), '非备战屏无「购买经验」→ 守卫应 round_fail 退出,交主循环处理'


def test_read_deploy_paddle_cap_and_count(test_context, test_image_dir: Path) -> None:
    """D-139:「区域-部署数」paddle「X/Y」→ read_deployed_count=X、read_deploy_cap=Y(同源)。

    回归 guard:refactor(read_deployed_count → _read_deploy_paddle[0])不破坏 X 读取;新增
    read_deploy_cap 给真 cap(非 level 估,deploy_bench D-139 用)。paddle 在小 stylized 区偶 OCR 漏 →
    读不到=None 合法(调用方 fallback),故只断言「读到则 sane」+ X<=Y。打印实测值供多样本核实。
    """
    from sr_od.application.currency_war.cw_observation import (
        read_deploy_cap,
        read_deployed_count,
    )
    for name in ('currency_war_shop.png', 'currency_war_prep_closed.png',
                 'currency_war_prep_herta.png'):
        screen = cv2_utils.read_image(str(test_image_dir / name))
        x = read_deployed_count(test_context, screen)
        y = read_deploy_cap(test_context, screen)
        print(f'\n[deploy paddle {name}] deployed={x} cap={y}')
        if x is not None:
            assert 0 <= x <= 9, f'deployed 越界 {x}'
        if y is not None:
            assert 1 <= y <= 9, f'cap 越界 {y}'
        if x is not None and y is not None:
            assert x <= y, f'deployed({x}) > cap({y})'


def test_tracked_bench_chars_seeds_identity() -> None:
    """D-84:tracked_bench(buy OCR 名)→ BenchChar(跨轮 seed state.bench)。

    SIFT 屏幕识别立绘不可行(主游脸库 + 图鉴立绘都不 match 备战 half-body)→ 用 buy 时
    read_shop_cards OCR 的规范名持久化,跨轮 seed bench。锁 helper:名 → BenchChar 保身份 + roster 阵营。
    """
    from sr_od.application.currency_war.operations.prep.shop import _tracked_bench_chars
    bcs = _tracked_bench_chars(['飞霄', '三月七', ''])
    assert [bc.char_id for bc in bcs] == ['飞霄', '三月七']   # 空名跳过
    assert all(bc.faction in FACTIONS or bc.faction == '?' for bc in bcs)   # 阵营 roster 派生 or '?'
    assert all(bc.char_id for bc in bcs)   # 身份非空
