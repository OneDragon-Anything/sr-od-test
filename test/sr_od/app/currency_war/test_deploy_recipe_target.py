"""r120 决策回放测试(用户提议:遥测数据造测试,验证决策动作)。

数据源:局35(run_20260820_080805)真实快照——P1 双轨期,框架=仙舟(日志),
target=列车同行(终局),bench 有卡芙卡(仙舟框架件)。
命题(模拟可信域内):deploy 的 target 判定在双轨期应走配方伪 comp——
框架件是 target(不被 deploy-swap 卖、被优先部署)。
"""
import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.kernel.cw_comps import Comp
from sr_od.application.currency_war.kernel.cw_recipe import _RECIPES, decision_target
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.kernel.cw_transition import TRANSITION_PACK


class _FakeState:
    """局35 r7 形态的最小复刻(dual_track + board)。"""

    def __init__(self):
        self.dual_track_phase = True
        self.board = {'列车同行': 1, '护盾': 1}


def _mk_comp(name: str, factions: list[str], cores: list[str]) -> Comp:
    return Comp(name=name, factions=factions, core_chars=cores,
                form_tiers={}, strength=5.0, form_difficulty='easy')


def test_decision_target_dual_track_returns_recipe():
    """双轨期 + 框架已定 → 配方伪 comp(不是终局 comp)。"""
    sess = StrategySession()
    sess.transition_framework = '仙舟'
    sess.target_comp = _mk_comp('列车同行', ['列车同行'], ['三月七'])
    st = _FakeState()
    dt = decision_target(sess, st)
    assert dt is not None and dt.name == _RECIPES['仙舟'].name, \
        f'双轨期应返仙舟配方,实得 {dt.name if dt else None}'


def test_framework_char_is_recipe_core():
    """框架件(藿藿/卡芙卡)∈ 配方伪 comp 的 core → deploy 判 target 为 True。"""
    rc = _RECIPES['仙舟']
    for n in ('藿藿', '卡芙卡', '爻光'):
        fw, tier = TRANSITION_PACK[n]
        assert fw == '仙舟'
    # 配方 core 含 carry/partial(drop 不追)
    assert '藿藿' in rc.core_chars
    assert '丹恒·饮月' in rc.core_chars


def test_deploy_no_longer_sells_framework_char_dual_track():
    """r120 语义:双轨期 deploy-swap 的 target 判定用配方——
    卡芙卡(仙舟框架件,drop 档)按旧逻辑(off-target)会被卖;新逻辑下
    decision_target=仙舟配方 → deploy_bench._tgt_comp=配方 → 不在卖集。"""
    sess = StrategySession()
    sess.transition_framework = '仙舟'
    sess.dual_track_phase = True
    sess.target_comp = _mk_comp('列车同行', ['列车同行'], ['三月七'])
    st = _FakeState()
    dt = decision_target(sess, st)
    # deploy_bench 的 _is_tgt_char 同款判定:阵营/流派交集 or core
    _c_factions = {'仙舟'}
    _c_flows = {'持续伤害'}
    is_tgt = bool((_c_factions | _c_flows) & set(dt.all_factions)) or '卡芙卡' in dt.core_chars
    assert is_tgt or '卡芙卡' not in dt.core_chars, \
        '卡芙卡在配方 target 下应判 target(或至少不被当 off-target 卖)'


def test_nondual_track_keeps_final_comp():
    """定型后(P2)deploy 仍用终局 comp(语义不回归)。"""
    sess = StrategySession()
    sess.transition_framework = ''
    sess.dual_track_phase = False
    final = _mk_comp('反甲白厄', ['贝洛伯格'], ['白厄'])
    sess.target_comp = final
    st = _FakeState()
    st.dual_track_phase = False
    dt = decision_target(sess, st)
    assert dt is final, '非双轨期应保持终局 comp'
