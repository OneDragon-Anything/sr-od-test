"""test_cw_hoard 主题锁——预囤(hoard)期框架语义四面(r106 蒙特卡洛结论代码级锁)。

2026-09-09 合并批:原 test_cw_hoard_boot.py 承接纯 shop 拒启动(1.0 边界)、
预囤模式框架件档位分、滞后不翻转三面;test_scatter_ts_zero_hoard(散件恒 0 分)
自原 test_cw_hoard_no_refresh.py(r110 预囤期金闲置行为锁)迁入——该文件头
「被其他测试文件引用防断链」的引用方即本文件 tombstone 注释,合并后断链消除,
其模块头遗留的 ``sys.path.insert(0, 'src')`` 一并去除(conftest 已统一路径)。
启动门「持有1+在售1=1.5 → 启动」等价面由
test_cw_scenario_gen::test_inv_boot_gate_semantics 三框架参数化族承载
(原 test_boot_gate_1p5 与其列车腿同输入同断言,2026-09-09 等价取一删除)。
"""
from sr_od.application.currency_war.kernel.cw_transition import (
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


# (原 test_hoard_score_scatter_zero 散件 0 分断言已并入本文件
#  test_scatter_ts_zero_hoard(同事实更全:万敌+
#  远坂凛 双载体);滞后不翻转语义单一源 = 本文件 test_hysteresis_unchanged
#  (framework_boot 同断言已并入此处);原 test_boot_gate_1p5 列车启动腿
#  已并入 test_cw_scenario_gen::test_inv_boot_gate_semantics。
#  README 纪律 8:重复构成删并理由。)


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
