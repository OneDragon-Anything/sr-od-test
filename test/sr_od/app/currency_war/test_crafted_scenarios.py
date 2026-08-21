"""r123 游戏理解造数测试(第三层模拟:手工构造局面 → 断言决策)。

与另两层的关系:
- r106 蒙特卡洛(牌池概率)回答"启动多快";
- r121 遥测回放(历史快照)回归"已发生的局面";
- 本层(游戏理解造数)覆盖"该发生但遥测里还没有"的边界——fixture 的每个
  字段都来自玩法文档/用户口述的确定知识,不猜战斗胜负(只断言决策反应)。

游戏理解来源:docs/game/gameplay/currency_war.md(配方框架/form_tiers)、
cw_transition TRANSITION_PACK(档位)、cw_factions(激活档位)。
"""
import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.cw_plan import _should_deploy
from sr_od.application.currency_war.cw_state import BenchChar, GameState, ShopCard
from sr_od.application.currency_war.cw_transition import (
    TRANSITION_PACK,
    pick_framework,
    transition_score,
)


def _bc(name, faction, pref='back', star=1, slot=0):
    return BenchChar(slot=slot, char_id=name, faction=faction,
                     star=star, position_pref=pref)


# ===== 局面1:仙舟双件在手,商店刷出第三件(经典"差一张成型") =====

def test_xianzhou_two_owned_shop_third():
    """游戏理解:藿藿/饮月是仙舟 carry,3 仙舟激活配方主档。
    手里 2 张 + 店里第 3 张 → 框架应稳定仙舟(合并权 2+0.5=2.5)。"""
    fw = pick_framework(
        [_bc('藿藿', '仙舟'), _bc('丹恒·饮月', '仙舟')],
        [],
        [ShopCard(x=0, name='卡芙卡', faction='仙舟', cost=2)],
    )
    assert fw == '仙舟'


def test_buy_score_third_xianzhou_beats_scatter():
    """差一张成型时,第三张仙舟件的框架分(drop 0.4+同框架 0.3+阵营 0.2=0.9)
    应明显高于散件(0)。"""
    s_third = transition_score('卡芙卡', '仙舟', '仙舟')
    s_scatter = transition_score('万敌', '夜之半神', '仙舟')
    assert s_third >= 0.85 and s_scatter == 0.0


# ===== 局面2:三框架各 1 张的稀释窗口(审计A 场景) =====

def test_dilution_no_boot_but_no_lock():
    """三框架各 1 张(仙舟/列车/量子各 carry×1)→ 不启动(1.0<1.5 门),
    但也不锁死——下一张谁出现谁启动(合并权可越门)。"""
    bench = [_bc('藿藿', '仙舟'), _bc('三月七', '列车同行'), _bc('希儿', '贝洛伯格')]
    fw = pick_framework(bench, [], [])
    assert fw == ''   # 未定(不误锁)
    # 店里再出一张藿藿 → 仙舟 2.0 越门
    fw2 = pick_framework(bench, [], [ShopCard(x=0, name='藿藿', faction='仙舟', cost=2)])
    assert fw2 == '仙舟'


# ===== 局面3:drop 件的正确处理(应急不上不下) =====

def test_drop_not_hoarded_but_deployable_when_framework_set():
    """游戏理解:椒丘/艾丝妲是 drop(应急战力,P1 末弃)。
    预囤不买(0 分);但框架已定=仙舟时它仍有过渡价值(非 0 分可救急)。"""
    assert transition_score('椒丘', '仙舟', '') == 0.0        # 未定:不囤
    assert transition_score('椒丘', '仙舟', '仙舟') > 0        # 已定:可应急


# ===== 局面4:量子 portal 局(ADR-0214 通道) =====

def test_quantum_portal_boot_dominates():
    """游戏理解:量子契约环境=量子线全速信号。portal+3 应压过 2 张仙舟持有。"""
    fw = pick_framework(
        [_bc('藿藿', '仙舟'), _bc('丹恒·饮月', '仙舟')],
        [], [], portal='量子同频契约',
    )
    assert fw == '量子'   # 3 > 2,偏置可被真持有翻越的语义另一测试覆盖


# ===== 局面5:deploy 的排位语义(前后台) =====

def test_framework_carry_deploys_in_dual_track():
    """双轨期仙舟框架件 carry(藿藿)在场下有空位 → deploy 判 True(r120 语义)。"""
    gs = GameState(round_num=3, plane=1, dual_track_phase=True)
    gs.level = 4
    gs.bench = []
    gs.deployed = [_bc('三月七', '列车同行', 'front')]
    cand = _bc('藿藿', '仙舟', 'back')
    assert _should_deploy(cand, gs, None) is True


def test_same_name_guard_blocks_second_copy():
    """场上已有藿藿 → bench 第二张藿藿不 deploy(同名禁双,等 3 合 1)。"""
    gs = GameState(round_num=3, plane=1, dual_track_phase=True)
    gs.level = 4
    gs.bench = []
    gs.deployed = [_bc('藿藿', '仙舟')]
    cand = _bc('藿藿', '仙舟')
    assert _should_deploy(cand, gs, None) is False
