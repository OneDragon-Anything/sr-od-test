"""C1 直通核心卡支配性支通道单帧锁(ADR-0569)。

出处 = 设计《直通核心卡信号层入口》(设计-C1直通核心入口.md v3):
- §2 案A:并列支配通道挂 dominance 邻位(既有 dominance_buy 之后、M3
  之前);发射判据 = registry 名单核心卡 ∧ 1★ 全额退(refund_full_star_ok
  共享单一源)∧ 不破息带(t5_p1_false,L 项零损)∧ bench 空槽
  (check_seats 共享单一源);动作形态默认 = 囤。
- §4 意向状态机行:non_line 拒因拆键 core_candidate_rejected。
- §7 三键分账:候补支触发(core_candidate_seen)/支配性支命中
  (core_dominance_buy_hit)/数值支 fail-closed(core_numeric_fail_closed)。

锁语义不锁巧合:断言通道判据行为与分键可辨性,不锁具体牌面坐标。
金币构帧口径:L 项 = P47 loss_exact 现算(gold=45 买 3 金跨轨迹同息档
⇒ L=0 放行;gold=50 买 3 金跨息档 ⇒ L≥1 拒),锚定零参数语义本体。
"""
from __future__ import annotations
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import state_of

from types import SimpleNamespace

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_comps import (
    CORE_SINGLE_CARD_REGISTRY,
    get_comp,
)
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import shop
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    contracts,
)

# ===== 基建(idiom 同 test_cw_locked_buy_membership_split)=====

_LOCK_COMP = '列车同行'          # 病灶局锁定线(g_20260906_182456)


def _cfg():
    return SimpleNamespace(ev_arm='full')


def _session(target_comp, ist: IntentionState | None) -> StrategySession:
    s = StrategySession()
    state_of(s).cw4_counters = {}
    state_of(s).target_comp = target_comp
    if ist is not None:
        state_of(s).v3_intention = ist
    return s


def _locked_ist(comp_name: str = _LOCK_COMP) -> IntentionState:
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = comp_name
    ist.lock_plane = 2
    return ist


def _state(gold: int, shop_cards: list[ShopCard],
           bench: list[BenchChar] | None = None) -> GameState:
    st = GameState(gold=gold, level=7, round_num=2, hp=60)
    st.plane = 2
    st.shop = shop_cards
    st.bench = bench if bench is not None else []
    st.deployed = []
    return st


def _card(name: str, cost: int = 3, star: int = 1) -> ShopCard:
    return ShopCard(x=100, name=name, cost=cost, star=star)


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _core_buys(actions) -> list[BuyCard]:
    return [a for a in actions if isinstance(a, BuyCard)
            and a.reason == 'core_single_card_buy']


def _counters(sess) -> dict:
    return state_of(sess).cw4_counters or {}


# ===== 通道判据行为(设计 §2 案A 发射式逐件)=====


class TestCoreChannelLaunch:

    def test_locked_frame_core_candidate_bought_as_free_option(self):
        """病灶形态直译(锁「列车同行」+ 希儿在售,g=45):候选身份 = 名单
        ∧ ∉ 锁定采购集;1★ 全额退 + L=0(45 买 3 金不跨息档,P47 现算)
        + 席位足 ⇒ 支配性支放行,买因 core_single_card_buy。放行即三键
        之二:候补支触发 + 支配性支命中(§7 分账)。"""
        st = _state(gold=45, shop_cards=[_card('希儿', 3)])
        sess = _session(get_comp(_LOCK_COMP), _locked_ist())
        act = shop.decide_shop_action(st, sess, _cfg())
        buys = _core_buys([act])
        assert len(buys) == 1 and buys[0].card.name == '希儿'
        ct = _counters(sess)
        assert ct.get('core_candidate_seen') == 1
        assert ct.get('core_dominance_buy_hit') == 1
        assert 'core_numeric_fail_closed' not in ct

    def test_unlocked_frame_channel_inert(self):
        """前件守卫(设计 §2 判据式):未锁帧 locked_buy_membership 返回
        None ⇒ 通道不评估,连候补支触发键都不落(未锁帧行为零漂移)。"""
        st = _state(gold=45, shop_cards=[_card('希儿', 3)])
        sess = _session(get_comp(_LOCK_COMP), IntentionState())
        act = shop.decide_shop_action(st, sess, _cfg())
        assert not _core_buys([act])
        assert 'core_candidate_seen' not in _counters(sess)

    def test_membership_member_not_candidate(self):
        """候补前件(c ∉ locked_buy_membership):锁「希儿量子」帧希儿属
        锁定采购集 ⇒ 非候补,归 M2 义务(m2_line_member),通道零触发。"""
        st = _state(gold=45, shop_cards=[_card('希儿', 3)])
        sess = _session(get_comp('希儿量子'), _locked_ist('希儿量子'))
        act = shop.decide_shop_action(st, sess, _cfg())
        assert isinstance(act, BuyCard) and act.card.name == '希儿'
        assert act.reason == 'm2_line_member'
        ct = _counters(sess)
        assert 'core_candidate_seen' not in ct
        assert 'core_dominance_buy_hit' not in ct

    def test_interest_break_frame_not_fired(self):
        """不破息带(L 项零损):g=50 买 3 金跨息档(50 档 5 → 47 档 4,
        P47 损 ≥1)⇒ 不放行;帧落数值支域(fail-closed 未落码)显影键。"""
        st = _state(gold=50, shop_cards=[_card('希儿', 3)])
        sess = _session(get_comp(_LOCK_COMP), _locked_ist())
        act = shop.decide_shop_action(st, sess, _cfg())
        assert not _core_buys([act])
        ct = _counters(sess)
        assert ct.get('core_candidate_seen') == 1
        assert ct.get('core_numeric_fail_closed') == 1
        assert 'core_dominance_buy_hit' not in ct

    def test_star2_direct_sale_not_fired(self):
        """支配性背书仅全额可退 1★(refund_full_star_ok 共享单一源):
        2★ 直出卡帧不放行,落数值支域显影键。"""
        st = _state(gold=45, shop_cards=[_card('希儿', 3, star=2)])
        sess = _session(get_comp(_LOCK_COMP), _locked_ist())
        act = shop.decide_shop_action(st, sess, _cfg())
        assert not _core_buys([act])
        ct = _counters(sess)
        assert ct.get('core_numeric_fail_closed') == 1
        assert 'core_dominance_buy_hit' not in ct

    def test_bench_full_frame_gate_blocks(self):
        """席位前件(bench 空槽,V_slot=0):满栏帧帧级门拦 ⇒ 候补触发
        键落、命中/数值域键均不落(§6 V_slot>0 = 支配性支失效域,如实
        不放行)。垫栏件用线成员(非燃料)防 M4 腾席改写帧。"""
        bench = [_bc('三月七', slot=i + 1) for i in range(BENCH_CAPACITY)]
        st = _state(gold=45, shop_cards=[_card('希儿', 3)], bench=bench)
        sess = _session(get_comp(_LOCK_COMP), _locked_ist())
        act = shop.decide_shop_action(st, sess, _cfg())
        assert not _core_buys([act])
        ct = _counters(sess)
        assert ct.get('core_candidate_seen') == 1
        assert 'core_dominance_buy_hit' not in ct
        assert 'core_numeric_fail_closed' not in ct

    def test_contract_violation_frame_abstains(self):
        """契约核验(可核验派生形态):消费位必须传 locked_buy_membership
        实解析物——裸 frozenset() 空集冒充 = 违例弃权 + 违例计数,
        通道不发射(禁字面量冒充解析结果)。"""
        ct: dict = {}
        assert not contracts.ensure_contract(
            ('mandate', 'core_single_card_buy_eligible'),
            contracts.ContractCtx(locked_buy_members=frozenset()), ct)
        assert ct.get('criteria_contract_violation:'
                      'mandate.core_single_card_buy_eligible') == 1
        assert not contracts.ensure_contract(
            ('mandate', 'core_single_card_buy_eligible'),
            contracts.ContractCtx(locked_buy_members=None), ct)
        # None = 未锁帧合法输入(fail 方向),不算违例
        assert len(ct) == 1

    def test_shop_latch_not_consumed_by_channel(self):
        """开店闩申报(设计 §2 落码批核对项):通道在商店决策访问位下游,
        不消费备战期开店闩——命中帧闩照常由入口置位一次、零
        shop_latch_skip_* 跳过计数、通道零闩读/写。"""
        st = _state(gold=45, shop_cards=[_card('希儿', 3)])
        sess = _session(get_comp(_LOCK_COMP), _locked_ist())
        shop.decide_shop_action(st, sess, _cfg())
        assert state_of(sess).cw4_shopped_phase == (2, 2)
        assert not [k for k in _counters(sess)
                    if k.startswith('shop_latch_skip_')]


# ===== 拒因拆键(设计 §4 意向状态机行)=====


def test_reject_split_core_candidate_vs_non_line():
    """non_line 拆键:registry 核心卡在售未买 = core_candidate_rejected,
    普通线外件保持 non_line(判读可辨;sim 检查器归机会错失类)。"""
    st = _state(gold=45, shop_cards=[_card('希儿', 3), _card('景元', 3)])
    out = shop.shop_unbought_reasons(st, get_comp(_LOCK_COMP), (), [])
    assert out['希儿'] == 'core_candidate_rejected'
    assert out['景元'] == 'non_line'


# ===== 名单锚定(设计 §3【修订·B3】谓词式唯一规则的登记落地)=====


def test_core_single_card_registry_entries():
    """名单单一源锚:谓词式唯一规则的在册成员 = 希儿 + 银狼LV.999
    (B3 命中集;出处指针随行)。排除面(设计 §3 B3 逐条排除举证)不得
    在册——尤其量子同频 4 费「银狼」是另一张卡;过渡体系功能链/凑档件
    (非单卡依赖结构)不入册。"""
    assert set(CORE_SINGLE_CARD_REGISTRY) == {'希儿', '银狼LV.999'}
    for name in CORE_SINGLE_CARD_REGISTRY:
        assert name in CHARACTERS, f'名单卡 {name} 不在角色注册表'
        assert CORE_SINGLE_CARD_REGISTRY[name], f'名单卡 {name} 缺出处指针'
    excluded = (
        '银狼',        # 量子同频 4 费卡,非欢愉线信号卡(注册名混淆防线)
        '千冶·刃',     # 星核=副产品凑数位(B3 排除)
        '花火', '缇宝',  # 希儿系放大器(非伤害主体)
        '爻光', '藿藿', '丹恒·饮月',   # 仙舟DOT 功能链三人组(B3 排除)
        '万敌',        # 燃血数量型信号(B3 排除)
        '黄泉',        # 减益/巡海多件档位线(B3 排除)
    )
    for name in excluded:
        assert name not in CORE_SINGLE_CARD_REGISTRY, \
            f'{name} 应被 B3 谓词排除,禁误扩'


if __name__ == '__main__':
    import pytest
    pytest.main([__file__])
