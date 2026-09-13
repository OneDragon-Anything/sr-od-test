"""武装箱选卡序数分档行为锁(armory-box-value landing 3.2;design 出处 =
changes/2026-09-12-armory-box-value/design.md §2.2-§2.6)。

B 组 = design §2.6 行为变化表逐行变化锚点(1/2/3/4a/4c/7a/7b/7c/8a/8b/
8c/10,行 10 回落锁在 test_cw_screens_ops),R1 = 等价回归帧(2b/4b/5/
6/8c/9)。tier 语义帧打在 ``equip_tier``/``pick_equipment`` 纯函数上
(输入全参自定、注册表实名;design §2.6 锁落位声明),wrapper 接线另由
一条含 locked_comp + 三本账的集成帧钉住。纯逻辑帧,零副作用。
"""
from sr_od.application.currency_war.kernel.cw_equip_value import (
    equip_tier,
    pick_equipment,
)
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.kernel.cw_vocab import CwSimFrame
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

# 实名 key 序列(注册表真值;反甲白厄含重复需求帧)
_KEYS_BAIYU = ['以牙还牙甲', '以牙还牙甲', '高周波电锯', '以牙还牙甲·特权',
               '热血沸腾拳']
_KEYS_DIANGUANG = ['电光履']            # 材料 = (光能电池, 轮滑鞋),mv 6=6
_KEYS_PIFENG = ['反重力皮靴']           # 自对配方:轮滑鞋 ×2


def _sess_locked(locked_comp: str, *, spare: list[str] | None = None):
    s = StrategySession()
    state_of(s).v3_intention = IntentionState(locked_comp=locked_comp)
    if spare is not None:
        s.last_owned_equips = list(spare)
    return s


# ===== 变化行(设计 §2.6;各行号对 design 表)=====


def test_row1_unlocked_output_prior_beats_material() -> None:
    """行 1(用户指令锚点):未锁态输出先验压过材料通用性——旧制幸运星
    (mv 3>0)胜,新制火力风暴潮(base 6>0)胜。"""
    assert pick_equipment(['幸运星', '火力风暴潮']) == 1


def test_row2_unlocked_mv_all_zero_base_decides() -> None:
    """行 2:全部 mv 表外帧,旧制恒取先,新制 base 决胜。"""
    assert pick_equipment(['垃圾袋', '火力风暴潮']) == 1


def test_row3_locked_within_material_tier_base_flips() -> None:
    """行 3:材料档内序翻转——旧制 mv 梯度(花7>鞋6)取花,新制 base
    (鞋4>花0)取轮滑鞋(虚构梯度退役,输出值入基)。"""
    assert pick_equipment(['生命之花', '轮滑鞋'],
                          key_equips=['热血沸腾拳', '反重力皮靴']) == 1


def test_row4a_locked_material_beats_generic_despite_base() -> None:
    """行 4a/6:材料档(tier1)压通用档(tier0),base 不倒挂档间。"""
    assert pick_equipment(['幸运星', '火力风暴潮'],
                          key_equips=_KEYS_BAIYU) == 0


def test_row4c_locked_equal_mv_base_decides() -> None:
    """行 4c:mv 相等(6=6)帧旧制取先(光能电池),新制 base(4>3)
    取轮滑鞋——电光履双材料帧。"""
    assert pick_equipment(['光能电池', '轮滑鞋'],
                          key_equips=_KEYS_DIANGUANG) == 1


def test_row7a_cross_pair_near_redeem_beats_plain_material() -> None:
    """行 7a:交叉近兑现(持量产型装甲,幸运星解锁首件以牙还牙甲)
    tier2 压同 comp 另一 mv 更高材料(tier1 生命之花)——旧制取花。"""
    assert pick_equipment(['幸运星', '生命之花'],
                          key_equips=_KEYS_BAIYU,
                          owned_spare=['量产型装甲']) == 0
    assert equip_tier('幸运星', key_equips=_KEYS_BAIYU,
                      owned_spare=['量产型装甲']) == 2


def test_row7b_self_pair_near_redeem() -> None:
    """行 7b:自对近兑现(持 1 轮滑鞋,第 2 只解锁反重力皮靴)tier2。"""
    assert equip_tier('轮滑鞋', key_equips=_KEYS_PIFENG,
                      owned_spare=['轮滑鞋']) == 2


def test_row7c_self_pair_already_synthable_stays_material() -> None:
    """行 7c:持 3 只(已可合成)再得 1 只 = 第 2 对增量,不升 tier2
    (首对解锁语义;增量兑现归 P42 数值化挂账)。"""
    assert equip_tier('轮滑鞋', key_equips=_KEYS_PIFENG,
                      owned_spare=['轮滑鞋', '轮滑鞋', '轮滑鞋']) == 1


def test_row8a_need_met_spare_form_demoted() -> None:
    """行 8a:需求 1 已持 1(备用),唯一件族第二件落 tier 0(冗余守卫)。"""
    assert equip_tier('电光履', key_equips=_KEYS_DIANGUANG,
                      owned_spare=['电光履']) == 0


def test_row8b_need_met_worn_form_demoted() -> None:
    """行 8b:需求 1 已穿 1(备用账 0,总持有账含穿戴)——守卫的合计
    口径,最常见满足态不再提权冗余件。"""
    assert equip_tier('电光履', key_equips=_KEYS_DIANGUANG,
                      owned_spare=[], owned_total=['电光履']) == 0


def test_row9_pseudo_comp_frame_behavior_unchanged() -> None:
    """行 9(等价):伪 comp 帧(P1 配方锁,locked_comp 恒空)——锚切换
    行为无差,未锁态纯 base 排序与旧制该帧实际行为一致(伪 comp
    key_equips 恒空,旧 ①③ 项结构性不触发)。"""
    s = StrategySession()
    state_of(s).v3_intention = IntentionState()   # 伪 comp 帧形态
    state_of(s).target_comp = None
    assert MandateV1Strategy().decide_box_card(
        ['完全无关的垃圾', '火力风暴潮'], CwSimFrame(), s, None) == 1


def test_row8c_duplicate_need_count_semantics() -> None:
    """行 8c(守卫边界,等价):昼神阿雅需 2 反重力皮靴,持 1(备用)
    时总持有 1 < 需求 2——守卫不误伤,tier3 保持。此帧区分原序列
    count 语义(本设计)与 frozenset 去重语义(会误判已满足)。"""
    assert equip_tier('反重力皮靴', key_equips=['反重力皮靴', '反重力皮靴'],
                      owned_spare=['反重力皮靴']) == 3


# ===== R1 等价回归帧(landing 3.2;标准帧)=====


def test_r1_row5_direct_key_beats_material() -> None:
    """R1 行 5:需求未满足标准帧,key 直击(tier3)恒胜材料(tier1)。"""
    assert pick_equipment(['幸运星', '以牙还牙甲'],
                          key_equips=_KEYS_BAIYU) == 1


def test_r1_row6_material_beats_generic() -> None:
    """R1 行 6:材料(tier1)恒胜通用件(tier0)——档间序与现行同构。"""
    assert pick_equipment(['幸运星', '火力风暴潮'],
                          key_equips=_KEYS_BAIYU) == 0


def test_r1_ties_take_first() -> None:
    """R1 行 2b/4b:mv 与 base 均并列 → 取先语义与现行一致。"""
    assert pick_equipment(['垃圾袋', '幸运星']) == 0
    assert pick_equipment(['垃圾袋', '幸运星'],
                          key_equips=_KEYS_DIANGUANG) == 0


# ===== wrapper 集成帧(三本账 + locked_comp 端到端)=====


def test_wrapper_passes_locked_anchor_and_spare_ledger() -> None:
    """集成:locked_comp 锚 + 备用账经薄壳进机器——持量产型装甲时
    幸运星(近兑现)胜同 comp mv 更高材料,证明锚与账真实接线。"""
    st = MandateV1Strategy()
    sess = _sess_locked('反甲白厄', spare=['量产型装甲'])
    assert st.decide_box_card(['幸运星', '生命之花'], CwSimFrame(),
                              sess, None) == 0
