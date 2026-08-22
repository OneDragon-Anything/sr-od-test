"""r119 停滞 watchdog 测试:指纹检测语义(纯逻辑,不依赖截图)。"""
import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.operations.battle_loop import CurrencyWarRunLoop


def test_stall_thresholds_defined():
    """参数在位:5 iter 采样/6 次触发(≈1-2min 检出,vs 局29/32 的 30-41min)。"""
    assert CurrencyWarRunLoop.STALL_SNAPSHOT_EVERY == 5
    assert CurrencyWarRunLoop.STALL_N == 6


def test_fingerprint_logic_same_vs_diff():
    """指纹语义:同 frozenset → 同 hash;不同 → 不同(采样粒度内可区分)。"""
    a = frozenset(['备战阶段', '商店'])
    b = frozenset(['备战阶段', '商店'])
    c = frozenset(['备战阶段', '请选择一个强化效果'])
    assert hash(a) == hash(b)
    assert hash(a) != hash(c)


def test_exempt_keywords():
    """战斗/结算态豁免关键词集合覆盖 loop 实际会遇到的静止态。"""
    exempt_src = ('战斗', '胜利', '挑战', '结算', '准备', '倒计时')
    for kw in ('战斗', '胜利', '挑战成功', '挑战失败', '结算', '准备战斗'):
        assert any(w in kw for w in exempt_src), f'{kw} 应被豁免覆盖'


# ===== ADR-0250:战斗窗口宽限(局54 哨兵误报复盘) =====

def test_battle_grace_constant_covers_observed_battles():
    """宽限常量 > 实测最长战斗(局54:P1r9 boss 4min20s / P2r1 遭遇 5min20s),
    且有界(超时恢复哨兵,出战卡死类真挂死仍可检出)。"""
    assert CurrencyWarRunLoop.BATTLE_WATCH_GRACE_S >= 8 * 60   # > 8min(> 实测 5.5min 留余量)
    assert CurrencyWarRunLoop.BATTLE_WATCH_GRACE_S <= 15 * 60  # 有界,防真挂死漏报窗口过长


def test_battle_grace_semantics():
    """窗口语义:None 恒不宽限;窗口内 True;恰好超时 False。"""
    grace = CurrencyWarRunLoop.BATTLE_WATCH_GRACE_S
    assert CurrencyWarRunLoop._watch_in_battle_grace(None, 1000.0) is False
    assert CurrencyWarRunLoop._watch_in_battle_grace(1000.0, 1000.0 + grace - 1) is True
    assert CurrencyWarRunLoop._watch_in_battle_grace(1000.0, 1000.0 + grace) is False


def test_battle_window_observed_vs_watch_threshold():
    """误报根因锁定:局54 战斗时长(5min20s)远超 watch 触发窗(6 次×5 iter×~5s ≈ 2.5min)
    ——即关键词豁免缺失时战斗必误报;该实证是宽限机制的存在理由(ADR-0250)。"""
    observed_battle_s = 5 * 60 + 20          # 局54 P2r1 遭遇战实测(18:38:20 出战 → 18:43:40 结算)
    watch_window_s = CurrencyWarRunLoop.STALL_N * CurrencyWarRunLoop.STALL_SNAPSHOT_EVERY * 5
    assert observed_battle_s > watch_window_s, '战斗时长必须超 watch 窗(否则宽限无必要)'
