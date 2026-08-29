"""牌池压缩买测试(r52;ADR-0209 用户指导)。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.kernel.cw_comps import get_comp  # noqa: E402
from sr_od.application.currency_war.strategy_v1.cw_plan import _hunt_tier_set  # noqa: E402
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState  # noqa: E402


def test_missing_core_tier_hunted() -> None:
    """①+②:core 未到 2★ 的费级入追猎(希儿 3 费缺 → 3 入集)。"""
    st = GameState(deployed=[], bench=[])
    tiers = _hunt_tier_set(st, (get_comp('希儿量子'), None))
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    expect = {int(CHARACTERS[c].cost) for c in get_comp('希儿量子').core_chars}
    assert tiers == expect


def test_completed_2star_core_not_hunted_for_2star() -> None:
    """core 已 2★ → 不再走「缺 2★」分支,但走「3★ 机会追猎」(同费仍在集)。"""
    st = GameState(deployed=[BenchChar(slot=1, char_id='希儿', faction='量子同频', star=2)])
    tiers = _hunt_tier_set(st, (get_comp('希儿量子'), None))
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    assert int(CHARACTERS['希儿'].cost) in tiers   # 3★ 追猎(③)


def test_field_2star_support_adds_tier() -> None:
    """③牌运:场上 2★ 辅助(非 core)费级入追猎(3费辅助 2★ → 追 3★)。"""
    st = GameState(deployed=[BenchChar(slot=1, char_id='藿藿', faction='仙舟', star=2)])
    tiers = _hunt_tier_set(st, (None, None))
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    assert int(CHARACTERS['藿藿'].cost) in tiers


def test_dual_comp_union() -> None:
    """target+stash 两边的缺 core 费级都入集(过渡与最终都有目标)。"""
    st = GameState(deployed=[], bench=[])
    tiers = _hunt_tier_set(st, (get_comp('列车同行'), get_comp('希儿量子')))
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    assert int(CHARACTERS['瓦尔特'].cost) in tiers   # 双方共有
    assert int(CHARACTERS['花火'].cost) in tiers


def test_two_1star_copies_still_hunted() -> None:
    """3合1 等价回归(2026-08-18 修):持 2 张 1★(差 1 张合并到 2★)→ 仍算
    「core 未到 2★」在追。旧 ``sum(bc.star)``=2 配 ``<2`` 阈值误判「已到 2★」
    → 希儿费级(3,core 中唯一)被移出追猎集,压缩买少覆盖一类该买的费级。"""
    st = GameState(
        deployed=[BenchChar(slot=1, char_id='希儿', faction='量子同频', star=1)],
        bench=[BenchChar(slot=1, char_id='希儿', faction='量子同频', star=1)])
    tiers = _hunt_tier_set(st, (get_comp('希儿量子'), None))
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    assert int(CHARACTERS['希儿'].cost) in tiers, '2张1★ ≠ 2★(3合1 需 3 张)→ 3 费在追'


def test_equiv_copies_one_2star_equals_three() -> None:
    """等价折算量纲:1张2★(=3 张 1★ 等价)= 恰到 2★ → ①分支不再追(③的 3★
    机会追猎仍会加回同费,故断言用「①语义」:等价副本数 ≥3 不走缺 2★ 分支)。"""
    from sr_od.application.currency_war.strategy_v1.cw_plan import _hunt_tier_set as hunt
    # 3 张 1★ 等价(用 1张2★ 表达同一等价量)→ 不走①;板上 2★ 触发③ → 同费仍在集
    st = GameState(deployed=[BenchChar(slot=1, char_id='希儿', faction='量子同频', star=2)])
    tiers = hunt(st, (get_comp('希儿量子'), None))
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    assert int(CHARACTERS['希儿'].cost) in tiers   # ③:2★ 在场 → 3★ 机会追猎


# ===== r61/r62 压缩面扩全(用户 §7-1/§7-15:「买便宜 1/2 星 = 过渡阵容的牌库压缩」) =====
# 判定纯函数单测(plan() 端到端有非确定源[ADR-0168 rng 未种子实证],不做脆断言)。

def test_compress_release_tiers() -> None:
    """压缩放行**统一保息门**(r64 review P1 修:1 费「净0」只对买卖往返成立,持有跨
    轮末在金=10 边界损 1 金息 —— 用户「保息前提下多买」统一适用):1/2 费+追猎费级
    都要求买后利息档不降;3 费非追猎恒拒。"""
    from sr_od.application.currency_war.strategy_v1.cw_plan import _compress_release as rel
    # 1 费:同守息门(r64 修,旧「恒放行」在边界损息)
    assert rel(1, 11, set()) is True       # 11→10 同 1 档
    assert rel(1, 10, set()) is False      # 10→9 降 1→0 档 = 损息 → 拒
    # 2 费保息放行
    assert rel(2, 12, set()) is True       # 12→10 同 1 档
    assert rel(2, 22, set()) is True       # 22→20 同 2 档
    assert rel(2, 20, set()) is False      # 20→18 降 2→1 档 → 拒
    # 追猎费级同门
    assert rel(3, 33, {3}) is True         # 33→30 同 3 档
    assert rel(3, 30, {3}) is False        # 30→27 降 3→2 档 → 拒
    # 3 费非追猎恒拒
    assert rel(3, 50, set()) is False


def test_compress_tail_sweep_dualtrack_buys_cheap() -> None:
    """r66 压缩扫尾(序列面):双轨期 best 后追加纯 BuyCard,息门内 1 费基本买齐
    (r1 live 实证旧版 5 张只买 2);已 commit(dual=False)不扫(t97:off-target=spread)。"""
    import random
    from types import SimpleNamespace

    from sr_od.application.currency_war.data.cw_chars import get_char
    from sr_od.application.currency_war.strategy_v1.cw_plan import plan
    from sr_od.application.currency_war.kernel.cw_state import GameState, ShopCard

    def _shop() -> list[ShopCard]:
        names = ['大丽花', '黑塔', '阿格莱雅', '乱破', '远坂凛']
        return [ShopCard(
            x=400 + i * 220,
            faction=(get_char(n).factions[0]
                     if get_char(n) and get_char(n).factions else '公司'),
            name=n, cost=1, star=1) for i, n in enumerate(names)]

    cfg = SimpleNamespace(character_priority=[], event_whitelist={})
    # 双轨期金 13:3 张买后 10(第 4 张 10→9 破息档拒)→ 恰 3 张(边界语义)
    st = GameState(plane=1, round_num=1, gold=13, level=3, dual_track_phase=True)
    st.shop = _shop()
    acts = plan(st, cfg, faction_priority=[], target_comp=None, stash_comp=None,
                rng=random.Random(42))
    buys = [a.card.name for a in acts if type(a).__name__ == 'BuyCard']
    assert len(buys) >= 3, f'双轨扫尾应把息门内 1 费买齐(13→10 恰 3 张),got {buys}'
    # 已 commit(dual_track_phase=False)无扫尾
    st2 = GameState(plane=2, round_num=3, gold=13, level=6, dual_track_phase=False)
    st2.shop = _shop()
    acts2 = plan(st2, cfg, faction_priority=[], target_comp=None, stash_comp=None,
                 rng=random.Random(42))
    buys2 = [a.card.name for a in acts2 if type(a).__name__ == 'BuyCard']
    assert len(buys2) < len(buys), f'commit 后不扫(off-target=spread,t97),got {buys2}'
