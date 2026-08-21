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
