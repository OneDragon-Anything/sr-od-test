"""cw_screen_state 对局中画面判定测试(白名单钉死)。

白名单契约:带 ``货币战争-`` 前缀的新建档屏默认进对局中判定集
(``in_match_screen_names`` 按前缀自动收录);入口链可达的非对局屏漏排除
= 各消费方(``CurrencyWarApp._in_match`` 第①层 / ``BackToNormalWorldPlus``
对局中委托 / ``CwLoop`` stop_at_prep 停机位)误判「已在对局中」跳过入口导航。
本测试把白名单全集钉死,新增建档屏漏加白名单时在此红。
"""
from types import SimpleNamespace

from sr_od.application.currency_war.cw_screen_state import (
    LOBBY_STATE_SCREENS,
    in_match_screen_names,
)


def _si(screen_name: str):
    """够用的 screen_info 假件(in_match_screen_names 只消费 screen_name)。"""
    return SimpleNamespace(screen_name=screen_name)


class TestInMatchScreenNames:

    def test_whitelist_screens_excluded(self) -> None:
        """白名单全集屏不入对局中判定(含挂起对局入口两屏)。"""
        names = in_match_screen_names(
            [_si(n) for n in sorted(LOBBY_STATE_SCREENS)])
        assert names == [], f'白名单屏漏排除:{names}'

    def test_new_pending_entry_screens_excluded(self) -> None:
        """挂起对局入口两屏(模式选择-进行中/结束结算确认)必须显式排除。

        两屏是入口链可达画面(CwEntryStart 点开始后落地、CwEntryExit route
        ④b 显式点名处置),漏排除会被误判「已在对局中」跳过入口导航。
        """
        names = in_match_screen_names([
            _si('货币战争-模式选择-进行中'),
            _si('货币战争-模式选择-结束结算确认'),
            _si('货币战争-备战'),
        ])
        assert names == ['货币战争-备战'], f'挂起入口两屏漏排除:{names}'

    def test_aura_codex_excluded(self) -> None:
        """主角光环图鉴(对局前图鉴查询页)必须在白名单内。

        建档屏 currency_war_aura_codex 带前缀,与数据银行/装备图鉴同族;
        漏排除会被前缀自动收进对局中判定集,入口链路过该页即误判
        「已在对局中」跳过入口导航。
        """
        assert '货币战争-主角光环图鉴' in LOBBY_STATE_SCREENS

    def test_prefixed_unlisted_screen_auto_included(self) -> None:
        """带前缀且不在白名单的建档屏自动进判定集(新画面零登记生效)。"""
        names = in_match_screen_names([_si('货币战争-某新画面')])
        assert names == ['货币战争-某新画面']
