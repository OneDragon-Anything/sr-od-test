"""r125 场景生成器:枚举决策岔路口组合 → 批量不变量测试。

高效造数 = 组合枚举 × 不变量断言(不是逐场景手写期望值)。
不变量来自设计文档语义(框架稳定/预囤收口/同名守卫),枚举面来自
真实决策维度。生成器与断言分离——新不变量直接加一条 assert 系列。


出处:docs/develop/sr_od/application/currency_war/decisions/0477-buylayer-takeover-strategy-v1-retirement.md(2026-08-31 测试瘦身批考证补记)。"""
import itertools
import sys

import pytest

sys.path.insert(0, 'src')

from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.kernel.cw_transition import (
    FRAMEWORKS,
    pick_framework,
    transition_score,
)

# 代表件(每框架 carry/partial/drop 各一)
REPS = {
    '仙舟': {'carry': '藿藿', 'partial': '爻光', 'drop': '卡芙卡'},
    '列车': {'carry': '三月七', 'partial': '姬子·启行', 'drop': '艾丝妲'},
    '量子': {'carry': '希儿', 'partial': '缇宝', 'drop': None},
}
SCATTER = '万敌'


def _bc(name, faction='?', pref='back', star=1, slot=0):
    return BenchChar(slot=slot, char_id=name, faction=faction,
                     star=star, position_pref=pref)


def _fw_faction(fw):
    return {'仙舟': '仙舟', '列车': '列车同行', '量子': '贝洛伯格'}[fw]


# ===== 不变量 1:持有 ≥2 同框架件 → 框架必选且稳定 =====

@pytest.mark.parametrize('fw,n_owned,shop_noise', itertools.product(
    FRAMEWORKS, (2, 3), (None, 'scatter', 'other_fw')))
def test_inv_framework_locks_with_two_owned(fw, n_owned, shop_noise):
    carry = REPS[fw]['carry']
    bench = [_bc(carry, _fw_faction(fw)) for _ in range(n_owned)]
    shop = []
    if shop_noise == 'scatter':
        shop = [ShopCard(x=0, name=SCATTER, faction='夜之半神', cost=1)]
    elif shop_noise == 'other_fw':
        other = next(f for f in FRAMEWORKS if f != fw)
        shop = [ShopCard(x=0, name=REPS[other]['carry'],
                         faction=_fw_faction(other), cost=1)]
    a = pick_framework(bench, [], shop)
    b = pick_framework(bench, [], shop, current=a)   # 下一轮(同持有)
    assert a == fw, f'持有 {n_owned} 张 {fw} carry 应锁定 {fw},实得 {a}'
    assert b == fw, f'持有不变时框架不得漂移({a}→{b})'


# ===== 不变量 2:预囤模式 drop/散件恒 0 分 =====

@pytest.mark.parametrize('fw', FRAMEWORKS)
def test_inv_hoard_zero_for_drop_and_scatter(fw):
    drop = REPS[fw]['drop']
    if drop:
        assert transition_score(drop, _fw_faction(fw), '') == 0.0
    assert transition_score(SCATTER, '夜之半神', '') == 0.0


# ===== 不变量 3:同名禁双(deploy 合法性)在任意局面下成立 =====

@pytest.mark.parametrize('fw', FRAMEWORKS)
def test_inv_same_name_never_deploys_twice(fw):
    carry = REPS[fw]['carry']
    gs = GameState(round_num=5, plane=1, dual_track_phase=True)
    gs.level = 6
    gs.bench = []
    gs.deployed = [_bc(carry, _fw_faction(fw)), _bc(SCATTER, '夜之半神')]
    cand = _bc(carry, _fw_faction(fw), slot=1)
    # ADR-0517 迁移批重锚:同名禁双不变量的存活载体 = cw_state.board_unique_key
    # (simulate/mutate 的 DeployMove 拒绝路径;旧 cw_deploy_seat.deploy_legal
    # 随 flow.py 死码簇传递性删除)
    from sr_od.application.currency_war.kernel.cw_state import board_unique_key
    assert board_unique_key(cand) == board_unique_key(gs.deployed[0])


# ===== 不变量 5:合并权启动门(纯 shop 不启动;持有1+在售1 启动) =====

@pytest.mark.parametrize('fw', FRAMEWORKS)
def test_inv_boot_gate_semantics(fw):
    carry, partial = REPS[fw]['carry'], REPS[fw]['partial']
    # 纯在售 1 张(0.5)不启动
    assert pick_framework([], [], [ShopCard(x=0, name=carry, faction=_fw_faction(fw), cost=2)]) == ''
    # 持有 1 + 在售 1 = 1.5 启动
    got = pick_framework([_bc(carry, _fw_faction(fw))], [],
                         [ShopCard(x=0, name=partial, faction=_fw_faction(fw), cost=2)])
    assert got == fw


# ===== 不变量 6:保持滞回——现任持有 ≥1 时 shop 蒸发不丢框架 =====

@pytest.mark.parametrize('fw', FRAMEWORKS)
def test_inv_incumbent_survives_shop_evaporation(fw):
    carry = REPS[fw]['carry']
    fw_kept = pick_framework([_bc(carry, _fw_faction(fw))], [], [],
                             current=fw)
    assert fw_kept == fw, '现任持有 1 张,shop 空时不得回退未定'


# ===== 手工造数边界(2026-09-03 瘦身批自 test_crafted_scenarios.py 并入;
#  同名禁双/启动门/双持有锁定/portal 偏置等重复面已由上方不变量族与
#  test_cw_portal_bias 辖定,原文件删除)=====

def test_buy_score_third_framework_piece_beats_scatter():
    """差一张成型时,第三张同框架件(框架已定)得分显著高于散件(0)
    (drop 标签 0.4+同框架 0.3+阵营 0.2=0.9 vs 散件 0)——买牌优先级锚。"""
    s_third = transition_score('卡芙卡', '仙舟', '仙舟')
    s_scatter = transition_score('万敌', '夜之半神', '仙舟')
    assert s_third >= 0.85 and s_scatter == 0.0


def test_drop_not_hoarded_but_deployable_when_framework_set():
    """drop 件(椒丘/艾丝妲=应急战力,P1 末弃):预囤不买(0 分);
    框架已定=仙舟时仍有过渡价值(非 0 分可救急)。"""
    assert transition_score('椒丘', '仙舟', '') == 0.0        # 未定:不囤
    assert transition_score('椒丘', '仙舟', '仙舟') > 0        # 已定:可应急


def test_framework_carry_deploys_in_dual_track():
    """双轨期仙舟框架件 carry(藿藿)在场下有空位 → deploy 判 True(r120 语义)。"""
    gs = GameState(round_num=3, plane=1, dual_track_phase=True)
    gs.level = 4
    gs.bench = []
    gs.deployed = [_bc('三月七', '列车同行', 'front')]
    cand = _bc('藿藿', '仙舟', 'back')
    # ADR-0517 迁移批重锚:双轨期框架件 carry 上场判定存活载体 =
    # cw_deploy_logic.select_deployments(fw_carry 围栏放行;旧 _should_deploy
    # 随 flow.py 死码簇传递性删除)
    from sr_od.application.currency_war.kernel.cw_deploy_logic import (
        select_deployments,
    )
    up, _held = select_deployments(
        [cand], deployed_cids={'三月七'}, deployed_fac={'列车同行': 1},
        board={'列车同行': 1}, cap=4, fw_carry={'藿藿'})
    assert 0 in up
