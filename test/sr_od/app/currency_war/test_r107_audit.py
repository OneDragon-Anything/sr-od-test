"""r107 审计修复测试:A 框架保持滞回 / B 预囤不含 drop / C 量子 deploy 窗口 / D 双计。"""
import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.cw_transition import pick_framework, transition_score


class BC:
    def __init__(self, n, faction='?'):
        self.char_id = n
        self.faction = faction


class Card:
    def __init__(self, n):
        self.name = n


def test_a_framework_survives_shop_evaporation():
    """审计A:现任持有 1,shop 半权蒸发(合并权<1.5)→ 仍保持现任,不回退 ''。"""
    # 持有三月七 1 张,shop 无框架件 → 合并权 1.0 < 1.5,但现任=列车持有 1
    fw = pick_framework([BC('三月七')], [], [], current='列车')
    assert fw == '列车', f'shop 蒸发后现任应保持,实得 {fw!r}'


def test_a_flip_needs_owned_lead():
    """审计A:翻转需挑战者持有领先 ≥1(纯 shop 噪声翻不动)。"""
    # 现任列车持有 1;挑战者仙舟 shop 在售 3(1.5)——纯 shop 不翻
    fw = pick_framework([BC('三月七')], [], [Card('藿藿'), Card('卡芙卡'), Card('椒丘')],
                        current='列车')
    assert fw == '列车', 'shop 半权不得翻转现任'


def test_a_flip_with_owned_lead():
    """审计A:挑战者持有 2 vs 现任 1 → 翻转(真金白银)。"""
    fw = pick_framework([BC('三月七'), BC('藿藿'), BC('丹恒·饮月')], [], [],
                        current='列车')
    assert fw == '仙舟', '持有领先 ≥1 应翻转'


def test_b_hoard_excludes_drop():
    """审计B:预囤模式 drop 档返 0(椒丘/卡芙卡/艾丝妲不囤)。"""
    assert transition_score('椒丘', '仙舟', '') == 0.0
    assert transition_score('卡芙卡', '仙舟', '') == 0.0
    # r107b 散件锁(合并自 test_stash_compensation.py,原文件已删)
    assert transition_score('艾丝妲', '?', '') == 0.0
    # carry 仍有分
    assert transition_score('藿藿', '仙舟', '') >= 1.0


def test_c_quantum_deploy_window():
    """审计C:_should_deploy 框架白名单含量子(希儿双轨期可上场)。"""
    from sr_od.application.currency_war.cw_plan import _should_deploy
    from sr_od.application.currency_war.cw_state import BenchChar, GameState
    st = GameState(round_num=4, plane=1, dual_track_phase=True, level=4)
    st.deployed = []
    st.bench = []
    bc = BenchChar(slot=1, char_id='希儿', faction='贝洛伯格', star=1, position_pref='front')
    assert _should_deploy(bc, st, None) is True, '量子 carry 双轨期应可上场(窗口④)'


def test_d_no_double_count_main_faction():
    """审计D:bench 单件主阵营恰计 1(不双计)。"""
    from sr_od.application.currency_war.cw_economy import _char_synergies
    from sr_od.application.currency_war.cw_plan import _bench_faction_counts
    from sr_od.application.currency_war.cw_state import BenchChar, GameState
    st = GameState()
    st.bench = [BenchChar(slot=1, char_id='藿藿', faction='仙舟', star=1, position_pref='back')]
    counts = _bench_faction_counts(st)
    assert counts.get('仙舟', 0) == 1, f'主阵营应恰计 1,实得 {counts}'
