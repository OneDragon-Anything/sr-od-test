"""test_cw_hoard_quantum 主题锁——框架选择核:预囤(hoard)期语义 + 量子框架注册。

覆盖面(四类承重件):
- 入口 smoke:FRAMEWORKS 三框架注册序 / 纯 shop 拒启动(1.0 边界防噪声);
- 决策真值代表锚:预囤档位分 / 散件恒 0 / 滞后两腿(平凡保持+真判别)/
  量子持有选中 / 平局先验 / 量子配方注册(过渡·量子配方统一化);
- 金钱不变量:shop 在售半权 0.5/张的合并权口径(滞后两腿构造帧现算锚)。

来源指针(2026-09-09 目标形态重建批合并):
- test_cw_hoard.py(原 test_cw_hoard_boot + scatter 面迁入史见其头部,全内容保留);
- test_cw_quantum_hoard.py(原 test_cw_quantum_recipe 并入史见其头部,全内容保留)。
其余历史锁已退役(git 可复活):两源文件本体随本合并退役;启动门 1.5 等价面
单一源在 test_cw_scenario_gen::test_inv_boot_gate_semantics(历史指针,其文件
归属以仓内现状为准)。

出处:被测模块本体 cw_transition.py / cw_recipe.py(plaza 784 篇实证;玩法理解
单一源 = docs/game/gameplay/currency_war.md「玩法策略模型」)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_recipe import recipe_comp
from sr_od.application.currency_war.kernel.cw_transition import (
    FRAMEWORKS,
    TRANSITION_PACK,
    pick_framework,
    transition_score,
)


class BC:
    def __init__(self, n):
        self.char_id = n


class Card:
    def __init__(self, n):
        self.name = n


class _BC:
    def __init__(self, char_id):
        self.char_id = char_id


# ==================== hoard 段(自 test_cw_hoard.py 逐字迁入) ====================

def test_boot_pure_shop_still_blocked():
    """纯 shop(1.0)仍不够——防噪声启动。

    与 test_cw_scenario_gen::test_inv_boot_gate_semantics 纯 shop 面(1 张
    carry=0.5)部分重叠双留:本测输入两张 carry 在售=1.0,是生产点名的
    启动门边界(cw_transition.pick_framework docstring「纯 shop 1.0 仍
    不够格防噪声」)——门值降到 ≤1.0 时唯本测红。framework_boot 同输入
    断言已并入此处(README 纪律 8)。"""
    assert pick_framework([], [], [Card('三月七'), Card('姬子·启行')]) == ''


def test_hoard_score_framework_undefined():
    """预囤:framework='' 时框架件仍有档位分(carry 1.0)。"""
    s = transition_score('三月七', '列车同行', '')
    assert s >= 1.0, f'预囤模式 carry 应有档位分,实得 {s}'


def test_scatter_ts_zero_hoard():
    """预囤模式散件恒 0 分(r106/r107b 语义不变;自 test_cw_hoard_no_refresh.py 迁入)。"""
    assert transition_score('万敌', '夜之半神', '') == 0.0
    assert transition_score('远坂凛', '?', '') == 0.0


# 滞后两腿构造件(框架归属经 TRANSITION_PACK 注册表现算锚,禁手抄:
# 注册表改档时锚先红报「重推构造帧」,不静默失去判别力。权口径 =
# cw_transition._framework_counts docstring「持有整权 + shop 在售半权 0.5/张」)。
_TRAIN_BENCH = ('三月七', '姬子·启行')                        # 全列车件(现任)
_XZ_SHOP = ('藿藿', '丹恒·饮月', '爻光', '卡芙卡', '椒丘')   # 全仙舟件(挑战者)


def test_hysteresis_unchanged():
    """滞后语义回归(两腿,数值锚自 TRANSITION_PACK 现算):

    腿1(平凡保持):现任列车持有 3(整权 3.0),shop 仙舟 2 在售(合并权
    1.0)——挑战者不反超,max 恒落现任,不翻转(shop 半权噪声翻不动)。

    腿2(真判别):现任列车持有 2(整权 2.0)vs shop 满 5 张仙舟件(合并权
    2.5)反超 → max 翻向仙舟,但仍返列车——换门语义「挑战者**持有权**领先
    现任 ≥1 才换」(cw_transition.pick_framework docstring「滞后设计」;
    本帧挑战者持有 0 < 现任持有 2,不得换)。滞后分支缺席时返仙舟,本测红;
    腿1 对该分支零判别力(删分支仍绿,系历史教训面),判别力由腿2 独家供给。
    """
    # 注册表现算锚:构造件框架归属漂移(改档/改名)时在此红,重选框架件。
    assert all(TRANSITION_PACK[n][0] == '列车' for n in _TRAIN_BENCH), \
        '构造帧漂移:现任件不再全属列车,两臂值偏离规格点,重推滞后帧'
    assert all(TRANSITION_PACK[n][0] == '仙舟' for n in _XZ_SHOP), \
        '构造帧漂移:挑战者件不再全属仙舟,两臂值偏离规格点,重推滞后帧'

    # 腿1:3.0 vs 1.0,挑战者不反超——平凡保持(回归面)。
    bench = [BC('三月七'), BC('姬子·启行'), BC('姬子·启行')]
    fw = pick_framework(bench, [], [Card('藿藿'), Card('卡芙卡')], current='列车')
    assert fw == '列车'

    # 腿2:2.0 vs 2.5——前置断言先经生产现算证明挑战者合并权确已反超
    # (fw 真翻向仙舟;权重语义脱同步时此断言先红),滞后分支仍保持现任。
    bench2 = [BC(n) for n in _TRAIN_BENCH]
    shop5 = [Card(n) for n in _XZ_SHOP]
    assert pick_framework(bench2, [], shop5) == '仙舟', \
        '构造帧失效:挑战者合并权未反超现任,滞后判别力失真,重推帧'
    assert pick_framework(bench2, [], shop5, current='列车') == '列车', \
        '滞后分支失守:挑战者仅合并权反超而持有权未领先 ≥1 时必须保持现任'


# ==================== quantum 段(自 test_cw_quantum_hoard.py 逐字迁入) ====================
# ===== 框架注册与序(pick_framework 计数 dict 序/平局先验的载体) =====

def test_three_frameworks():
    assert FRAMEWORKS == ('仙舟', '列车', '量子'), '三框架注册'


def test_quantum_selected_by_ownership():
    """纯量子持有 → 量子配方(希儿线无特判,靠框架计数)。"""
    fw = pick_framework([_BC(n) for n in ('希儿', '缇宝', '符玄')], [])
    assert fw == '量子'


def test_quantum_portal_bias():
    """量子契约 portal → +3 偏置(空板也选量子)。"""
    assert pick_framework([], [], portal='量子同频契约') == '量子'


def test_xianzhou_beats_quantum_tie():
    """量子2 vs 仙舟2 平局 → 仙舟(dict 序主流先验,r102 审计③)。

    平局先验的载体:pick_framework 计数 dict 由 FRAMEWORKS 序生成,
    max 取首个最大 → 平局归 FRAMEWORKS 首位仙舟(cw_transition 注:
    主流先验 32% vs 29%,有意为之)。FRAMEWORKS 序的单一源锁 =
    test_three_frameworks(元组序)。"""
    bench = [_BC('希儿'), _BC('缇宝'), _BC('藿藿'), _BC('丹恒·饮月')]
    assert pick_framework(bench, []) == '仙舟'


# ===== 量子配方注册面(r102 统一化:希儿线无特例通道) =====

def test_recipe_quantum_registered():
    rc = recipe_comp('量子')
    assert rc is not None and rc.name == '过渡·量子配方'
    assert rc.form_tiers == {'量子同频': 3, '贝洛伯格': 2}
    assert '希儿' in rc.core_chars
