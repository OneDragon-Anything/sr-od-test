"""商店刷新钮按钮态三态读数测试(read_shop_refresh_button 真帧真值)。

锁的设计约定(obs/cw_shop_refresh_obs.py,三态渲染规格证据帧 =
sr-od-test/screens/货币战争-备战-开商店/ 目录):
- 免费态:「免费刷新」识别标志命中,剩余次数从「文本-刷新价格」rect
  现读(免费帧该区渲染次数非标价;正常亮度试用四连帧真值 = 4);
- 付费耗尽态:识别标志未中∧标价读出(刷新耗尽付费态帧真值 = 2);
- 不可用灰态:渲染同付费,affordable = 金现读 ≥ 标价(灰态帧金 1 < 价 2
  → False)。

真帧测试走 test_context 真实 OCR(conftest 磁盘 memo 温缓存);三帧
断言共享同一条测试内的一次读链执行(慢计算只算一次)。纯函数边界
(标价 0 拒信/次数越界拒信)独立一条,锁解析层防线。
"""

from __future__ import annotations

from test.conftest import SrTestContext

from sr_od.application.currency_war.obs.cw_shop_refresh_obs import (
    _parse_free_count,
    _parse_price_digit,
    read_shop_refresh_button,
)

_SCREEN: str = '货币战争-备战-开商店'


def test_refresh_button_three_states_real_frames(
        test_context: SrTestContext) -> None:
    """三态真帧真值:免费态次数=4 / 付费态价=2 / 灰态 affordable=False。"""
    free_frame = test_context.load_screen(_SCREEN, '正常亮度试用四连帧')
    free_btn = read_shop_refresh_button(test_context, free_frame, gold=53)
    assert free_btn.free is True
    assert free_btn.free_remaining == 4
    assert free_btn.price is None
    assert free_btn.affordable is True

    paid_frame = test_context.load_screen(_SCREEN, '刷新耗尽付费态')
    paid_btn = read_shop_refresh_button(test_context, paid_frame, gold=61)
    assert paid_btn.free is False
    assert paid_btn.free_remaining is None
    assert paid_btn.price == 2
    assert paid_btn.affordable is True

    gray_frame = test_context.load_screen(_SCREEN, '刷新不可用灰态')
    gray_btn = read_shop_refresh_button(test_context, gray_frame, gold=1)
    assert gray_btn.free is False
    assert gray_btn.price == 2
    assert gray_btn.affordable is False


def test_parse_digit_guards() -> None:
    """解析层防线:标价 0 拒信(免费帧次数数字混入不可当标价)、越界拒信;
    次数 0 拒信(免费钮在场即余额>0)、越界拒信。"""
    assert _parse_price_digit(['0']) is None
    assert _parse_price_digit(['GO0']) is None
    assert _parse_price_digit(['GO2']) == 2
    assert _parse_price_digit(['12']) is None   # 上界 9:钮内标价一位数
    assert _parse_free_count(['0']) is None
    assert _parse_free_count(['4']) == 4
    assert _parse_free_count(['10000']) is None   # 上界 = 注册表最大额度 9999
    assert _parse_free_count(['免费刷新']) is None
