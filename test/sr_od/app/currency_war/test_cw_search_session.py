"""cw_search_session(38 号搜牌会话)v0 测试:J0 零漂移 + 停止语义 + J2 计数器投资。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_search_session import (  # noqa: E402
    DISCOUNT_AT_REFRESH,
    SearchState,
    decide_shop_face,
)


def test_j0_degenerate_equals_greedy() -> None:
    """J0 零漂移锚:hit_p=0(永不命中)→ 刷纯烧金 → 必停(=单步贪心「不值就停」)。"""
    s = SearchState(gold=40, refresh_count=0, target_left=2, hit_p=0.0)
    d = decide_shop_face(s)
    assert d['stop'] and not d['refresh']


def test_stop_when_gold_low_or_hit_low() -> None:
    """停止语义:金不足刷价 → 停;命中率高+进度差多+金足 → 刷。"""
    assert decide_shop_face(SearchState(1, 0, 3, 0.4))['stop']
    d = decide_shop_face(SearchState(50, 0, 3, 0.5))
    assert d['refresh']


def test_high_hit_and_rich_keeps_searching() -> None:
    """富金+高命中:持续搜索(远未集齐,期望值高)。"""
    d = decide_shop_face(SearchState(80, 5, 4, 0.6))
    assert d['refresh']


def test_j2_counter_investment_before_discount_line() -> None:
    """J2 切片:计数器注入——降价线前 1-2 刷处,「跨线后价降」应使刷决策比无计数器基线
    更积极(跨刷次投资行为;单步估值结构上只看当前价 2,看不见线后 1)。"""
    # 无计数器视角(把价固定 2、刷次设 0 = 看不到降价线)
    s_far = SearchState(30, 0, 2, 0.12)          # 低命中,离降价线远
    s_near = SearchState(30, DISCOUNT_AT_REFRESH - 1, 2, 0.12)   # 差 1 刷解锁
    d_far = decide_shop_face(s_far)
    d_near = decide_shop_face(s_near)
    # 线前 1 刷:下一刷即触线,后续刷全 1 金 → 边际序列价值抬升;远侧纯按 2 金算
    assert d_near['edge'] >= d_far['edge'], (
        f"跨线投资未涌现: near={d_near} far={d_far}")
    # 且存在构造:远侧停、近侧刷(投资涌现的最强形态)
    assert (not d_far['refresh']) or d_near['refresh']


def test_after_discount_cheaper_search_continues() -> None:
    """降价线后:同金位低命中下,价 1 比价 2 更能持续搜索(计数器经济变现)。"""
    s_normal = SearchState(12, 0, 2, 0.2, refresh_price=2)
    s_discount = SearchState(12, DISCOUNT_AT_REFRESH, 2, 0.2, refresh_price=1)
    d_n = decide_shop_face(s_normal)
    d_d = decide_shop_face(s_discount)
    assert d_d['edge'] >= d_n['edge']
