"""P1 过渡双框架模型测试(r37-r38)。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.kernel.cw_transition import (  # noqa: E402
    COMMIT_MIN_T,
    COMMIT_SIGNAL_THRESHOLD,
    FRAMEWORK_FACTIONS,
    FRAMEWORKS,
    TRANSITION_PACK,
    CommitSignals,
    t_of,
    transition_score,
)


def test_pack_covers_data_driven_cards() -> None:
    """plaza 实证牌全在包内且归属正确框架。"""
    for name in ('藿藿', '丹恒·饮月', '爻光', '卡芙卡', '椒丘'):
        assert TRANSITION_PACK[name][0] == '仙舟', f'{name} 应属仙舟框架'
    for name in ('三月七', '姬子·启行', '花火'):
        assert TRANSITION_PACK[name][0] == '列车', f'{name} 应属列车框架'
    assert TRANSITION_PACK['千冶·刃'][0] == '通用'


def test_framework_factions_defined() -> None:
    """三框架的目标羁绊(仙舟+DOT / 列车 / 量子+贝;r102 统一化)。"""
    assert set(FRAMEWORKS) == {'仙舟', '列车', '量子'}
    assert '仙舟' in FRAMEWORK_FACTIONS['仙舟']
    assert '列车同行' in FRAMEWORK_FACTIONS['列车']
    assert '量子同频' in FRAMEWORK_FACTIONS['量子']


def test_same_framework_bonus() -> None:
    """同框架牌 > 通用插件 > 散件(集中买一包)。"""
    assert transition_score('藿藿', 'x', '仙舟') > transition_score('千冶·刃', 'x', '仙舟')
    assert transition_score('千冶·刃', 'x', '仙舟') > transition_score('艾丝妲', 'x', '仙舟')
    # 跨框架:藿藿在列车框架下无加成
    assert transition_score('藿藿', 'x', '列车') < transition_score('藿藿', 'x', '仙舟')


def test_carry_beats_drop_same_tier_base() -> None:
    """同框架内 carry > drop。"""
    assert transition_score('藿藿', 'x', '仙舟') > transition_score('卡芙卡', 'x', '仙舟')


# (test_early_phase_gate 已随 in_early_phase 退役删除——调用点唯一=dv 框架
#  启动分支,ADR-0468;Early 判定语义由消费方内联,无独立函数可锁。)


# ===== r39 定型信号管线 =====

def test_commit_signals_accumulate_and_lead() -> None:
    """信号累积(r56 阈值 3.0→5.0:双源 3.5 不再 ready,双轨期不被 r1-r2 早期
    证据提前终结;三源 4.5 仍不够,叠加节点产出类信号(supply_reward 0.8)才达 5.0)。"""
    sig = CommitSignals()
    sig.add('briefing_affix', {'列车同行': 0.8, 'DOT队': 0.3})   # 1.5×1.0 = 1.5
    sig.add('invest_strategy', {'列车同行': 0.9, 'DOT队': 0.1})  # 2.0×1.0 = 2.0
    lead = sig.leader()
    assert lead is not None and lead[0] == '列车同行'
    assert abs(lead[1] - 3.5) < 1e-9
    assert not sig.ready(t_of(1, 7)), f'双源 3.5 < {COMMIT_SIGNAL_THRESHOLD}(r56)→ 不 ready'
    sig.add('invest_env', {'列车同行': 1.0, 'DOT队': 0.2})       # +1.0 = 4.5
    assert not sig.ready(t_of(1, 7)), '三源 4.5 < 5.0 → 仍不 ready(需持续积累)'
    sig.add('supply_reward', {'列车同行': 1.0})                  # +0.8 = 5.3
    assert sig.ready(t_of(1, 7)), '5.3 ≥ 5.0 且 t=7 达轮门 → ready'


def test_commit_signals_weak_not_ready() -> None:
    """单弱信号(shop_supply 0.5)不达标(双轨期继续囤)。"""
    sig = CommitSignals()
    sig.add('shop_supply', {'DOT队': 1.0})
    assert not sig.ready()


def test_commit_ready_round_gate() -> None:
    """r56 轮门:信号分达标但 t < COMMIT_MIN_T(7)不 ready(P1 早期证据不足,
    强制双轨观察);t≥7 放行;t=0 缺省不设门(兼容旧行为)。live 接线:
    default_strategy 两调用点传 t_of(plane, round)。"""
    sig = CommitSignals()
    for src, name in (('briefing_affix', '列车同行'), ('invest_strategy', '列车同行'),
                      ('invest_env', '列车同行'), ('supply_reward', '列车同行'),
                      ('shop_supply', '列车同行')):
        sig.add(src, {name: 1.0})
    assert sig.leader()[1] >= COMMIT_SIGNAL_THRESHOLD
    assert not sig.ready(t_of(1, COMMIT_MIN_T - 1)), f't={COMMIT_MIN_T - 1} < {COMMIT_MIN_T} → 轮门拦'
    assert sig.ready(t_of(1, COMMIT_MIN_T)), f't={COMMIT_MIN_T} 达轮门且信号足 → ready'
    assert sig.ready(), 't=0 缺省不设门(兼容)'


def test_commit_boundary_t_of() -> None:
    """定型边界(2026-08-18 收口):消费方 ``plane >= 2`` 即定型(t=10,P2-r1,
    严于文档口径 P2-3);旧 past_commit_deadline(t≥12)分支被 plane>=2 恒短路
    = 死代码已删。本测试锁 t_of 量纲供轮门消费。"""
    assert t_of(1, 1) == 1 and t_of(1, 9) == 9
    assert t_of(2, 1) == 10 and t_of(2, 3) == 12
    assert t_of(3, 1) == 19
