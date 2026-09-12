"""C1 直通核心卡支配性支通道单帧锁(ADR-0569)。

出处 = 设计《直通核心卡信号层入口》
(docs/develop/sr_od/application/currency_war/design/设计-C1直通核心入口.md,持久正本):
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

from types import SimpleNamespace

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_comps import (
    COMP_LIBRARY,
    CORE_SINGLE_CARD_REGISTRY,
    V2_FAMILIES,
    get_comp,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    intention_core,
)
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
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bs,
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
    """核心卡买入(锁线 core_single_card_buy ∧ 未锁线恒买 :unlocked)。"""
    return [a for a in actions if isinstance(a, BuyCard)
            and (a.reason == 'core_single_card_buy'
                 or a.reason == 'core_single_card_buy:unlocked')]


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
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        buys = _core_buys([act])
        assert len(buys) == 1 and buys[0].card.name == '希儿'
        ct = _counters(sess)
        assert ct.get('core_candidate_seen') == 1
        assert ct.get('core_dominance_buy_hit') == 1
        assert 'core_numeric_fail_closed' not in ct

    def test_unlocked_frame_always_buy_release(self):
        """T-115 规则③ 恒买放行(ADR-0580;用户裁定 410):未锁线帧
        registry 核心卡在售 ⇒ 恒买入,席/金物理硬闸继承,息纪律/星级
        不继承;auth_basis unlocked 形态 + 独立计数键与锁线路径不混桶。
        旧锁「未锁帧行为零漂移」钉的锁线前置语义已被裁定 410 取代——
        「C1 锁线前置使 1-3 未锁线不触发」即本裁定病灶本体。"""
        st = _state(gold=45, shop_cards=[_card('希儿', 3)])
        sess = _session(get_comp(_LOCK_COMP), IntentionState())
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        buys = _core_buys([act])
        assert len(buys) == 1 and buys[0].card.name == '希儿'
        assert buys[0].reason == 'core_single_card_buy:unlocked'
        ct = _counters(sess)
        assert ct.get('core_candidate_seen') == 1
        assert ct.get('core_unlocked_buy_hit') == 1
        assert 'core_dominance_buy_hit' not in ct

    def test_unlocked_frame_star2_also_bought(self):
        """规则③ 负向锁:恒买不限星级——未锁线 2★ 核心直出卡照放行
        (refund_full_star_ok 不继承;2★ 买入价按店面现价过金闸,
        可逆性是 dominance 族语义、恒买语义 = 持有价值,ADR-0580)。"""
        st = _state(gold=45, shop_cards=[_card('希儿', 9, star=2)])
        sess = _session(get_comp(_LOCK_COMP), IntentionState())
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        buys = _core_buys([act])
        assert len(buys) == 1 and buys[0].card.name == '希儿'
        assert _counters(sess).get('core_unlocked_buy_hit') == 1

    def test_p1_early_form_core_bought(self):
        """1-3 形态(P1 未锁线,希儿在售、不在目标线)⇒ 恒买 BuyCard
        (裁定 410 病灶帧形:「现 C1 通道锁线前置条件使 1-3 未锁线时
        不触发」;红证 = 移除恒买旁路 → 帧落 core_candidate_rejected
        拒因——旧锁 test_unlocked_frame_channel_inert 的语义,其失效
        即病灶复现,ADR-0580)。"""
        st = _state(gold=45, shop_cards=[_card('希儿', 3)])
        st.plane = 1
        sess = _session(get_comp(_LOCK_COMP), IntentionState())
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        buys = _core_buys([act])
        assert len(buys) == 1 and buys[0].card.name == '希儿'
        assert buys[0].reason == 'core_single_card_buy:unlocked'

    def test_membership_member_not_candidate(self):
        """候补前件(c ∉ locked_buy_membership):锁「希儿量子」帧希儿属
        锁定采购集 ⇒ 非候补,归 M2 义务(m2_line_member),通道零触发。"""
        st = _state(gold=45, shop_cards=[_card('希儿', 3)])
        sess = _session(get_comp('希儿量子'), _locked_ist('希儿量子'))
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
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
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
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
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert not _core_buys([act])
        ct = _counters(sess)
        assert ct.get('core_numeric_fail_closed') == 1
        assert 'core_dominance_buy_hit' not in ct

    def test_bench_full_frame_gate_blocks(self):
        """席满帧入循环走腾席支(T-115 恒买腾席批 A1 重推;ADR-0580):
        资格门席位维已下放循环内(mandate.core_single_card_buy_eligible
        收窄为锁线态单判),满栏帧过星→息→金三门后在席门走腾席支——
        垫栏件 = 线成员三月七(列车同行 core_chars,义务基座身份排除)
        ⇒ 无合法燃料 victim ⇒ 诚实停摆(权限模型:骨架义务 M2 族 > 裁定
        族买,禁卖义务件凑恒买)。判锁层订正:旧 docstring「帧级门拦」
        的拦截面在帧内席门,非帧门;四条旧断言全保持(不买 ✓/seen==1 ✓/
        无 dominance_hit ✓/无 numeric_fail_closed ✓——for-else:席满
        break 跳过尾键,消「no_fuel 与 numeric_fail_closed 共火」)+
        新增 core_locked_no_fuel == 1。出处 = 恒买腾席方案 v2 §5.1/§5.5
        /§10。"""
        bench = [_bc('三月七', slot=i + 1) for i in range(BENCH_CAPACITY)]
        st = _state(gold=45, shop_cards=[_card('希儿', 3)], bench=bench)
        sess = _session(get_comp(_LOCK_COMP), _locked_ist())
        act = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert not _core_buys([act])
        ct = _counters(sess)
        assert ct.get('core_candidate_seen') == 1
        assert ct.get('core_locked_no_fuel') == 1
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
        shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert state_of(sess).cw4_shopped_phase == (2, 2)
        assert not [k for k in _counters(sess)
                    if k.startswith('shop_latch_skip_')]


# ===== 拒因拆键(设计 §4 意向状态机行)=====


def test_reject_split_core_candidate_vs_non_line():
    """non_line 拆键:registry 核心卡在售未买 = core_candidate_rejected,
    普通线外件保持 non_line(判读可辨;sim 检查器归机会错失类)。"""
    st = _state(gold=45, shop_cards=[_card('希儿', 3), _card('景元', 3)])
    # W6 波 4:shop_unbought_reasons 切容器签名,帧经 cw4_bs 喂入。
    out = shop.shop_unbought_reasons(
        cw4_bs(st, _session(get_comp(_LOCK_COMP), None)),
        get_comp(_LOCK_COMP), (), [])
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


def test_registry_names_are_intention_core_of_some_v2_comp():
    """registry ↔ 意向核心派生对齐锁(单一源交点的可执行对账)。

    断言:每个在册核心卡 = 至少一条 v2 家族套(c.family ∈ V2_FAMILIES)
    的意向核心——cw_intention.intention_core(c) == name(派生序:
    plaza_carry ∈ core_chars 优先,否则 core_chars 首位)且 name 在该套
    core_chars 内。失配即红。

    依据(持久索引):
    - 设计《直通核心卡信号层入口》§2 案B 否决理由③(粒度错配:见到核心卡
      的第一反应是囤,换线归换线机器第三触发辖)——通道不改换线语义,
      两机器仅共用名单,互不代管;
    - 同文 §4 合取表「换线状态机」行:唯一交点 = 共用
      CORE_SINGLE_CARD_REGISTRY 单一源(防「入口说它是核心、换线机器
      说它不是」的双源漂移);
    - R197 影子面判例的豁免依据(先例 = ADR-0518 表 R197 同槽防线的
      发射侧影子通道退役):登记面无人消费即成影子面;本登记的豁免 =
      双消费交点(C1 通道候选身份 ∧ 换线机器意向核心派生)真实存在,
      由本锁持续证明——registry 名一旦无任何 v2 套意向认领,交点断裂,
      名单退化为 C1 通道单边影子面。
    """
    for name in CORE_SINGLE_CARD_REGISTRY:
        claim = [
            c for c in COMP_LIBRARY
            if c.family in V2_FAMILIES
            and intention_core(c) == name
            and name in c.core_chars
        ]
        assert claim, (
            f'在册核心卡 {name!r} 无任何 v2 家族套以它为意向核心'
            f'(intention_core ∧ core_chars 双条件)——registry ↔ 换线'
            f'机器单一源交点断裂(设计 §4 交点表行);先核名单与 '
            f'COMP_LIBRARY core_chars/plaza_carry 数据,禁为保绿改锁')


if __name__ == '__main__':
    import pytest
    pytest.main([__file__])
