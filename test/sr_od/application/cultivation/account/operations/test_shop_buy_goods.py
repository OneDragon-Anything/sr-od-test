"""ExchangeShopBuyGoods 流程测试(fixture 剧本,不连真游戏)。

锁设计约定(见 src op 模块 docstring 与探索稿 nodes.md):
- 拉满购买主链:切tab → 首屏定位点卡 → 弹窗读月限/单价 → 拉满两轮同值判到顶
  → 确认 → 奖励弹窗安全点关闭 → 余额差值终验 + 月限角标软读数;
- count 超月限剩余:fail 不截断,不触确认按钮;
- scroll_search=False 且首屏无目标:fail,不滚动零消耗;
- 滚动扫描命中不可购卡(已售罄角标):列表页拦截,不点卡不进弹窗;
- 弹窗重入(售罄横条):商品名放行 → 横条分支点取消诚实失败。

画面事实出处:实机走查 2026-11-12 余烬兑换页购买链(通票/命运足迹实购、
售罄专票只读),素材 = 实拍帧 screens/商店*/ 下对应 webp。
"""

from __future__ import annotations

import pytest

from sr_od.application.cultivation.account.operations.shop_buy_goods import (
    ExchangeShopBuyGoods,
    parse_monthly_left,
)
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

_FIRST_SCREEN = ('商店', '余烬兑换-首屏通票')
_POPUP_PASS = ('商店-兑换弹窗', '星轨通票')
_REWARD_FRAME = ('商店', '余烬兑换-奖励弹窗')
_FIRST_SCREEN_BOUGHT = ('商店', '余烬兑换-首屏通票-已购')
_BOTTOM_FRAME = ('商店', '余烬兑换-底部')
_POPUP_SOLD_OUT = ('商店-兑换弹窗', '星轨专票-已售罄')

_CARD_SLOT_RECT = [325, 215, 540, 500]
"""第 1 行第 1 列卡槽(网格基准,商品-星轨专票卡 area 同 rect)"""
_REWARD_SAFE_RECT = [0, 900, 300, 1080]
"""奖励弹窗安全点 (100,1000) 的落点矩形"""


class _WatchedBuy(WatchdogOperationMixin, ExchangeShopBuyGoods):
    """带看门狗 + 关闭游戏窗口前置(MockController 环境无真实窗口)。"""

    watchdog_max_rounds: int = 80

    def __init__(self, ctx, goods, count=None, tab=None,
                 scroll_search=True) -> None:
        ExchangeShopBuyGoods.__init__(
            self, ctx, goods, count=count, tab=tab, scroll_search=scroll_search)
        self.need_check_game_win = False


@pytest.fixture()
def fixture_controller(
    test_context: SrTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> FixtureController:
    ctrl = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    monkeypatch.setattr(ctrl, 'mouse_move', lambda pos: None, raising=False)
    return ctrl


def _run_execute(test_context: SrTestContext, op) -> object:
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            return op.execute()
    finally:
        reset_running_state(test_context, op)


def _require_screens(test_context: SrTestContext, frames: list[tuple[str, str]]) -> None:
    for frame in frames:
        if not test_context.has_screen(*frame):
            pytest.skip(f'存档截图缺失:screens/{frame[0]}/{frame[1]}.webp')


def test_parse_monthly_left_slash_pair() -> None:
    """「可兑换 X/Y」斜杠对解析;get_positive_digits 对 5/5 取 55 是已知坑。"""
    assert parse_monthly_left('可兑换 5/5') == 5
    assert parse_monthly_left('可兑换：1/2') == 1
    assert parse_monthly_left('5/5') == 5
    assert parse_monthly_left(None) is None
    assert parse_monthly_left('') is None
    assert parse_monthly_left('已售罄') is None


def test_unknown_goods_raises(test_context: SrTestContext) -> None:
    """未注册商品标识符构造即抛 ValueError 并带可用值(调用方自纠)。"""
    with pytest.raises(ValueError, match='未注册的商品标识符'):
        ExchangeShopBuyGoods(test_context, 'nonexistent_goods')
    with pytest.raises(ValueError, match='count'):
        ExchangeShopBuyGoods(test_context, 'pass', count=0)


def test_buy_pass_max_flow(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """拉满主链:定位 → 弹窗读数 → 拉满到顶 → 确认 → 奖励弹窗关闭 → 终验通过。"""
    frames = [_FIRST_SCREEN, _POPUP_PASS, _REWARD_FRAME, _FIRST_SCREEN_BOUGHT]
    _require_screens(test_context, frames)
    fixture_controller.set_phases([
        # 首屏:切tab点击(until 在同帧命中冒险记录锚)→扫描点通票卡→推进弹窗帧
        {'frame': _FIRST_SCREEN,
         'exit': ('on_click_in', _CARD_SLOT_RECT)},
        # 弹窗:拉满两轮同值判到顶(bought=1)→点确认推进奖励弹窗帧
        {'frame': _POPUP_PASS,
         'exit': ('on_click_in', '商店-兑换弹窗', '按钮-确认')},
        # 奖励弹窗:安全点关闭推进终验帧
        {'frame': _REWARD_FRAME,
         'exit': ('on_click_in', _REWARD_SAFE_RECT)},
        {'frame': _FIRST_SCREEN_BOUGHT},
    ])
    op = _WatchedBuy(test_context, 'pass', count=None, scroll_search=False)
    result = _run_execute(test_context, op)

    assert result.success, (
        f'主链未成功:status={result.status!r} '
        f'phase_idx={fixture_controller.phase_idx} '
        f'clicks={fixture_controller.recorded_clicks}')
    data = result.data
    assert data['bought'] == 1, f'拉满后实际数量应为 1(素材余额上限): {data}'
    assert data['unit_price'] == 90, f'单价应读 90: {data}'
    assert data['balance_left'] == 41862, f'终验余额应 41952-90: {data}'
    assert data['monthly_left'] == 4, f'购买后角标应 4/5: {data}'
    assert fixture_controller.click_hit_area('商店', 'tab-余烬兑换'), '切tab点击缺失'
    assert fixture_controller.click_hit_area('商店', '卡槽-网格基准'), \
        f'通票卡(第1行第1列槽位)点击缺失:{fixture_controller.recorded_clicks}'
    assert fixture_controller.click_hit_area('商店-兑换弹窗', '按钮-拉满'), \
        '拉满按钮点击缺失'
    assert fixture_controller.click_hit_area('商店-兑换弹窗', '按钮-确认'), \
        '确认按钮点击缺失'


def test_count_over_monthly_fails(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """count 超月限剩余:弹窗内读月限后 fail 不截断,不触确认按钮。"""
    frames = [_FIRST_SCREEN, _POPUP_PASS]
    _require_screens(test_context, frames)
    fixture_controller.set_phases([
        {'frame': _FIRST_SCREEN,
         'exit': ('on_click_in', _CARD_SLOT_RECT)},
        {'frame': _POPUP_PASS},
    ])
    op = _WatchedBuy(test_context, 'pass', count=99, scroll_search=False)
    result = _run_execute(test_context, op)

    assert not result.success, '超月限应显式失败而非截断执行'
    assert '超本期限剩余' in (result.status or ''), \
        f'失败原因应指明月限超限:{result.status!r}'
    assert not fixture_controller.click_hit_area('商店-兑换弹窗', '按钮-确认'), \
        '超限场景不得触碰确认按钮'


def test_first_screen_not_found_fails(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """scroll_search=False 且首屏无目标:fail 不滚动(零消耗,不改列表滚动位)。"""
    _require_screens(test_context, [_FIRST_SCREEN])
    fixture_controller.set_phases([{'frame': _FIRST_SCREEN}])
    op = _WatchedBuy(test_context, 'harmonic_tune', count=1,
                     scroll_search=False)
    result = _run_execute(test_context, op)

    assert not result.success, '首屏模式未命中应显式失败'
    assert '首屏未找到' in (result.status or ''), \
        f'失败原因应指明首屏未找到:{result.status!r}'
    assert not fixture_controller.click_hit_area('商店', '卡槽-网格基准'), \
        '未命中目标不得点击任何商品卡'


def test_scroll_then_sold_out_intercept(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """滚动扫描命中已售罄卡:列表页角标拦截,不点卡不进弹窗。"""
    frames = [_FIRST_SCREEN, _BOTTOM_FRAME]
    _require_screens(test_context, frames)
    fixture_controller.set_phases([
        {'frame': _FIRST_SCREEN, 'exit': ('on_polls', 1)},
        {'frame': _BOTTOM_FRAME},
    ])
    op = _WatchedBuy(test_context, 'key_of_knowledge', count=1,
                     scroll_search=True)
    result = _run_execute(test_context, op)

    assert not result.success, '已售罄卡应拦截失败'
    assert '已售罄' in (result.status or ''), \
        f'失败原因应指明已售罄角标:{result.status!r}'
    assert not fixture_controller.click_hit_area('商店', '卡槽-网格基准'), \
        '不可购卡不得点击(防进弹窗误触确认)'
    assert not fixture_controller.click_hit_area('商店-兑换弹窗', '按钮-确认')


def test_popup_reentry_sold_out_bar(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """弹窗重入起点:商品名放行 → 售罄横条分支点取消诚实失败。"""
    _require_screens(test_context, [_POPUP_SOLD_OUT])
    fixture_controller.set_phases([{'frame': _POPUP_SOLD_OUT}])
    op = _WatchedBuy(test_context, 'special_pass', count=1, tab='embers')
    result = _run_execute(test_context, op)

    assert not result.success, '售罄横条应显式失败'
    assert '已售罄' in (result.status or ''), \
        f'失败原因应指明售罄横条:{result.status!r}'
    assert fixture_controller.click_hit_area('商店-兑换弹窗', '按钮-取消'), \
        '横条分支应点取消关闭弹窗'
    assert not fixture_controller.click_hit_area('商店-兑换弹窗', '按钮-确认'), \
        '售罄弹窗不得触碰确认按钮'


_CONTRACT_FRAME = ('商店-协议商店', 'default')
_GIFT_DIALOG_FRAME = ('商店-礼包弹窗', '黑塔冒险共享协议')
_STELLAR_FRAME = ('商店-聚灵铸星', '角色兑换')


def test_contract_gift_flow(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """协议商店礼包链:单页跳过回顶 → 扫描点卡 → 礼包弹窗数量恒 1 → 确认 → 终验。"""
    frames = [_CONTRACT_FRAME, _GIFT_DIALOG_FRAME, _CONTRACT_FRAME]
    _require_screens(test_context, frames)
    fixture_controller.set_phases([
        {'frame': _CONTRACT_FRAME,
         'exit': ('on_click_in', '商店-协议商店', '卡槽-网格基准')},
        {'frame': _GIFT_DIALOG_FRAME,
         'exit': ('on_click_in', '商店-礼包弹窗', '按钮-确认')},
        {'frame': _CONTRACT_FRAME},
    ])
    op = _WatchedBuy(test_context, 'herta_contract_quest_sharing', count=1)
    result = _run_execute(test_context, op)

    assert result.success, (
        f'礼包链未成功:status={result.status!r} '
        f'phase_idx={fixture_controller.phase_idx} '
        f'clicks={fixture_controller.recorded_clicks}')
    data = result.data
    assert data['bought'] == 1, f'礼包数量恒 1: {data}'
    assert data['tab'] is None, f'协议商店无 tab: {data}'
    assert fixture_controller.click_hit_area('商店-协议商店', '卡槽-网格基准'), \
        '协议商品卡点击缺失'
    assert fixture_controller.click_hit_area('商店-礼包弹窗', '按钮-确认'), \
        '礼包确认按钮点击缺失'


def test_stellar_navigation(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """跨子商店导航:兑换商店页起点 → 点左侧菜单进聚灵铸星 → 扫描点卡。

    红线对应:mock 无真实消耗,流程到「已点商品卡待弹窗验证」即止
    (末帧不推进,confirm 前的导航/扫描/点卡链路已完整覆盖)。
    """
    frames = [('商店', '余烬兑换-首屏通票'), _STELLAR_FRAME]
    _require_screens(test_context, frames)
    fixture_controller.set_phases([
        {'frame': frames[0],
         'exit': ('on_click_in', '商店', '菜单-聚灵铸星')},
        {'frame': _STELLAR_FRAME},
    ])
    op = _WatchedBuy(test_context, 'jiaoqiu', count=1)
    result = _run_execute(test_context, op)

    assert not result.success or result.status is not None  # 末帧停在点卡后重试,允许 retry 超限
    assert fixture_controller.click_hit_area('商店', '菜单-聚灵铸星'), \
        '左侧菜单导航点击缺失'
    assert fixture_controller.click_hit_area('商店-聚灵铸星', '卡槽-网格基准'), \
        f'聚灵铸星商品卡点击缺失:{fixture_controller.recorded_clicks}'
    assert not fixture_controller.click_hit_area('商店-礼包弹窗', '按钮-确认'), \
        '只读验证不得触碰任何确认按钮'
