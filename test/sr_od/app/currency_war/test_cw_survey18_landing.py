"""strategy/18 调研落地测试:注册表纠错 + v2 字段 + 台账路由 + 难度账本。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.kernel.cw_difficulty_account import DifficultyAccount  # noqa: E402
from sr_od.application.currency_war.kernel.cw_effect_ledger import (  # noqa: E402
    build_ledger,
    effects_from_strategies,
)
from sr_od.application.currency_war.kernel.cw_investments import get_strategy  # noqa: E402


def test_correction_great_conquest() -> None:
    """纠错:伟大征服注册表曾漏难度耦合与 +12XP —— 三字段齐全。"""
    e = get_strategy('伟大征服').economy
    assert e.win_reward_mult == 3.0
    assert e.difficulty_per_streak == 1
    assert e.xp_instant == 12


def test_correction_foresight() -> None:
    """纠错:远见曾漏「棱彩流 + 难度豁免」两大效果。"""
    e = get_strategy('远见').economy
    assert e.instant_gold == 15
    assert e.future_quality_upgrade == 'prism'
    assert e.difficulty_inflation_exempt is True


def test_v2_new_entries() -> None:
    """v2 新建条目关键字段(抽样)。"""
    assert get_strategy('成长基金').economy.gold_at_level == 40
    assert get_strategy('成长基金').economy.gold_at_level_target == 9
    assert get_strategy('超发货币').economy.gold_at_node == 70
    assert get_strategy('狸财经狸').economy.interest_flat_per_node == 2
    assert get_strategy('不等价交换').economy.hp_gold_swap is True
    assert get_strategy('星际和平保险').economy.gold_per_hp_lost_now is True
    assert get_strategy('简单模式').economy.difficulty_delta == -3
    assert get_strategy('难度修改器').economy.difficulty_node_types == ('遭遇', '首领')


def test_ledger_routing_from_strategies() -> None:
    """路由:注册表 → AggregateEffect → 台账(持卡组合的定制解入口)。"""
    effs = effects_from_strategies(['狸财经狸', '超发货币', '商业间谍'])
    led = build_ledger(effs)
    # 狸狸固定息 → per_node +2;超发货币 +70 覆盖 t=1..5 窗口
    assert led.calendar_at(3) == 70.0 + 2.0
    assert led.calendar_at(1) == 70.0 + 2.0
    assert led.calendar_at(6) == 2.0      # +70 余期(5)外,只剩狸狸息
    # 商业间谍 → xp 单击 −1
    assert led.mutations.xp_click_delta == -1.0


def test_difficulty_account_from_strategies() -> None:
    """难度账本:持卡建账(简单模式 −3/难度修改器 −4/伟大征服动态)。"""
    acc = DifficultyAccount.from_strategies(100.0, ['简单模式', '难度修改器'], streak=3)
    # 静态 −7;伟大征服未持 → streak 项系数 1(默认)
    assert abs(acc.total() - (100 - 7 + 3)) < 1e-9
    acc2 = DifficultyAccount.from_strategies(100.0, ['简单模式', '伟大征服'], streak=5)
    # 伟大征服难度+连胜:per_streak 系数 1 → total 含 +5
    assert abs(acc2.total() - (100 - 3 + 5)) < 1e-9


def test_merge_sell_trigger_family() -> None:
    """合成/出售触发族(strategy/19 P7 修正轮):被动经济,正常评估。"""
    e = get_strategy('砂里淘金').economy
    assert e.gold_per_2star2cost_merge == 2   # 下界=卖价;阵容用砂金则更高
    assert get_strategy('星星相印').economy.gold_per_3star_merge == 5
    assert get_strategy('武力刷新').economy.refresh_per_compose == 2
    assert get_strategy('大裁员').economy.sell_price_mult == 2.0
    assert get_strategy('降本增效').economy.sell_price_mult == 2.0
