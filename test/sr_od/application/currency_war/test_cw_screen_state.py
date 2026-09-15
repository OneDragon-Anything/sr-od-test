"""cw_screen_state 对局中名单契约锁(前缀自动收集 + 大厅态白名单排除)。

出处:cw-exit-dispatch 迭代 3.1——5 张对局前画面/图鉴查询页移出对局中
名单(前缀误收修正)。机制:对局中态屏名 = screen_info 全集中带
``货币战争-`` 前缀者,减去 ``LOBBY_STATE_SCREENS`` 白名单;新对局画面
建档(命名带前缀)自动进判定列表,白名单必须显式排除非对局屏——漏加 =
带前缀的非对局屏在场即误判「已在对局中」,入口导航被跳过。

锁两点(输入为合成屏名桩,零 IO):
- **移出锁**:难度确认/数据银行/装备图鉴/竞争对手图鉴列表与详情 5 张
  不得出现在 ``in_match_screen_names`` 输出(白名单漏加即复发);
- **在册锁 + 自动收集锁**:既有对局中屏(备战/备战-免战)仍在输出,
  未知前缀新屏照常自动进输出(白名单不得误伤前缀机制本体)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.cw_screen_state import (
    in_match_screen_names,
)

# 移出清单(对局前画面/图鉴查询页,带前缀会被自动误收的形态)
_REMOVED_FROM_IN_MATCH: tuple[str, ...] = (
    '货币战争-难度确认',
    '货币战争-数据银行',
    '货币战争-装备图鉴',
    '货币战争-竞争对手图鉴列表',
    '货币战争-竞争对手图鉴详情',
)


def _si(name: str) -> SimpleNamespace:
    """screen_info 桩:判定函数只读 ``screen_name`` 字段。"""
    return SimpleNamespace(screen_name=name)


def test_removed_lobby_screens_not_in_match():
    """5 张移出屏不入对局中输出;备战/备战-免战等在册对局屏不受影响。"""
    names = [*_REMOVED_FROM_IN_MATCH, '货币战争-备战', '货币战争-备战-免战']
    out = in_match_screen_names([_si(n) for n in names])
    assert not (set(_REMOVED_FROM_IN_MATCH) & set(out))
    assert '货币战争-备战' in out
    assert '货币战争-备战-免战' in out


def test_prefixed_new_screen_auto_collected():
    """白名单不误伤前缀自动收集:未知前缀新屏照常进对局中输出。"""
    out = in_match_screen_names([_si('货币战争-未来新屏')])
    assert out == ['货币战争-未来新屏']
