"""P86 无目标期三臂·收编对照锁(迭代 2026-10-12-prep-shop-workflow-redesign
批 3.6;shop_session §5 承继清单 P86 行)。

原发射面锁(乙臂五前件合取/甲臂强锁门 G>ε 触发闸/丙臂守息缺省三臂
仲裁)随三臂收编退役——本文件改锁收编后的目标形态(收编完成判据 =
本文件 + 对照表,禁静默失活):

- **甲臂**(方向囤货):触发闸退役(囤货义务化——不依赖期望保证),
  方向采购集经 K 空窗回退(语义保留、判定源切换 = 候选空,
  line_and_upgrade §1.6)进序 1 成员面 → M2 义务买因;位面辖域维持
  原命题(位面 2,P86 已证辖域字面量);
- **乙臂**(枢纽件跨线期权):发射位收编进序 1 候选集——多线骨架件
  ∈ 候选线骨架身份自然命中;贯穿件恒囤层直接命中;跨线覆盖数期权不
  再单独计分(偏差申报:覆盖信息由 3.7 选线函数候选体系承载);hub_
  option_buy 买因与 hub_option_* 拒因族不得复现;
- **丙臂**(无目标期守息缺省):并入统一金约束门——无候选帧零买入
  零付费刷新(三段式刷新判据在无合格缺口帧 fail-closed),不设独立
  守息分支键。

kernel 判据本体(cw_intention.no_target_arms/k_empty_window_fallback
等)保留为空窗回退的单一源——真值表直锁(纯函数面)随批保留。
(原 test_refund_backing_face_retained 背书面两行断言删:全额退背书门
refund_full_star_ok 的 (2,2) 拒 /(1,2) 过真值已由
test_sell_window_launch::test_hold_registration_qualification_
conjunction 的资格合取锁完整辖住——子集断言不留。)
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box as _kbridge,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_gs,
)

from sr_od.application.currency_war.kernel import cw_intention
from sr_od.application.currency_war.kernel.cw_comps import (
    get_comp,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    ChannelSig,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    k_empty_window_fallback,
)
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BENCH_CAPACITY,
    CwActionBuyCardParam,
    CwActionCloseShopParam,
    CwActionRefreshShopParam,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import shop
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

# ===== 基建 =====


def _cfg():
    return SimpleNamespace(ev_arm='full')


def _card(name: str, cost: int, star: int = 1, x: int = 0) -> ShopCard:
    return ShopCard(name=name, faction='', cost=cost, star=star, x=x)


def _bc(name: str, star: int = 1) -> BenchSlot:
    return BenchSlot(kind='unit', unit=Unit(char_id=name, star=star))


def _state(gold: int = 45, level: int = 5, plane: int = 2,
           shop_cards=(), bench=(), deployed=(), hp: int = 60,
           round_num: int = 2, node_kw: str = '') -> dict:
    """无目标帧(P2+ 位面辖域)通用种子轴(口径沿旧三臂锁:gold=45/
    level=5/round=2;target/ist 皆空 = 空窗),店面/持有按参。
    ``node_kw`` 直填节点 kind('reward' = 升级抑制帧,翻转行为差隔离)。"""
    st = {'gold': gold, 'level': level, 'plane': plane,
          'round_num': round_num,
          'hp': hp, 'node': node_kw or 'battle',
          'shop': list(shop_cards), 'bench': list(bench),
          'front_row': list(deployed), 'active_strategies': []}
    return st


def _session(ist=None) -> StrategySession:
    sess = StrategySession()
    state_of(sess).cw4_counters = {}
    if ist is not None:
        state_of(sess).v3_intention = ist
    return sess


def _decide(st: dict, sess: StrategySession):
    """商店单动作决策直调(3.6 会话循环;账面稳态钉位随种子 +
    node_hist_pos 位面水位线按种子平面落位——plane2_started 窗口谓词
    的单调历史输入,P2+ 帧须显式置位)。"""
    gs = cw4_gs(sess, **st)
    gs.node_hist_pos = (int(st.get('plane', 2)), int(st.get('round_num', 2)))
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        session_scope as _ss,
    )
    _ss.handle_node_boundary(gs)
    state_of(gs).gold_ledger = int(st.get('gold', 45))
    act = shop.decide_shop_action(
        gs, sess, _cfg(), registry=DEFAULT_REGISTRY)
    return act


def _ct(sess) -> dict:
    return state_of(sess).cw4_counters


# ===== kernel 判据真值面(空窗回退单一源;纯函数直锁)=====


class TestFallbackKernelTruth:
    def test_k_empty_window_fallback_bands(self):
        """空窗回退三带真值(单一源 = cw_intention;序 1 成员面的空窗
        供给):未锁 ist 的空窗帧按带回退非空(甲臂方向采购集承接),
        带归属键可辨。"""
        comp = get_comp('希儿量子')
        st = _state(hp=100,
                    bench=[_bc(m) for m in comp.core_chars],
                    deployed=[Unit(char_id='板上件锚', star=1)])
        gs = _kbridge(**st)
        sess = _session(IntentionState())
        fb, band = k_empty_window_fallback(gs, state_of(sess).v3_intention)
        assert fb, '空窗帧回退集为空(序 1 成员面失去供给)'
        assert band


# ===== 甲臂收编:方向采购集经回退进序 1(锁:买因 m2)=====


class TestArmAAdoptedViaFallback:

    def test_fallback_members_reach_m2(self):
        """甲臂判活帧:回退方向成员在店 → 序 1 义务买(m2_line_member/
        m2_locked_member 买因;旧 shop_no_target_arm_a_adopted 计数键
        随触发闸退役不得复现)。"""
        comp = get_comp('希儿量子')
        chars, _eq = cw_intention._line_hoard(comp)
        missing_piece = sorted(m for m in chars
                               if m not in comp.core_chars)[0]
        st = _state(hp=100, shop_cards=[_card(missing_piece, cost=1)])
        st['bench'] = [_bc(m) for m in comp.core_chars]
        st['front_row'] = [Unit(char_id='板上件锚', star=1)]
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert isinstance(act, CwActionBuyCardParam), f'甲臂成员未买: {act!r}'
        assert act.reason in ('m2_line_member', 'm2_locked_member')
        assert act.card.name == missing_piece
        assert 'shop_no_target_arm_a_adopted' not in _ct(sess), \
            '甲臂采用计数键已随触发闸退役(收编)'

    def test_plane1_fallback_domain_guard(self):
        """位面辖域维持原命题(P86 已证辖域 = 位面 2;宪法第 2 条豁免
        登记):位面 1 空窗帧回退支不触发序 1 甲臂采购(P1 板面恒过渡
        体系,与方向正交)——序 1 源①候选集构建处的显式辖域守卫。"""
        comp = get_comp('希儿量子')
        chars, _eq = cw_intention._line_hoard(comp)
        missing_piece = sorted(m for m in chars
                               if m not in comp.core_chars)[0]
        st = _state(plane=1, hp=100,
                    shop_cards=[_card(missing_piece, cost=1)])
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert not (isinstance(act, CwActionBuyCardParam)
                    and act.card.name == missing_piece), \
            'P1 帧甲臂方向采购越辖(位面辖域字面量守卫失效)'


# ===== 乙臂收编:枢纽件经序 1 身份命中(锁:无 hub_option 买因)=====


class TestHubFoldedIntoOrderOne:

    def test_hub_piece_bought_via_membership(self):
        """枢纽自然帧(花火 1★ 在店,空窗):贯穿件恒囤层/候选骨架
        身份命中序 1 → m2 买因发射;hub_option_buy 买因与 hub_option_*
        拒因族不得复现(乙臂发射位收编申报)。"""
        st = _state(gold=60, plane=2, node_kw='reward',
                    shop_cards=[_card('花火', cost=2)])
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert isinstance(act, CwActionBuyCardParam), \
            f'枢纽件未经序 1 命中: {act!r}'
        assert act.card.name == '花火'
        assert act.reason.startswith('m2_'), act.reason
        ct = _ct(sess)
        assert not [k for k in ct if k.startswith('hub_option_')], \
            '乙臂发射位已收编,hub_option_* 键族不得复现'

    def test_hub_reject_family_retired_not_silent(self):
        """乙臂拒因族(merge_material/seats/interest/unaffordable)收编
        后由序 1 自身门序承载(席→置换账/金→筹资/素材对→M2b 合成完成
        与 G-S1 守卫)——拒因不再以 hub_option_* 分键显影,席位/金不足
        形态照常拦截(非静默放行)。"""
        # 席满(9 占位)帧:非合成素材、无让位候选 → 不买。
        st = _state(gold=60, plane=2, shop_cards=[_card('花火', cost=2)],
                    bench=[_bc(f'注册表外高价值件{i}', star=2)
                           for i in range(BENCH_CAPACITY)],
                    deployed=[Unit(char_id='板上件锚', star=1)])
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert not isinstance(act, CwActionBuyCardParam) or act.card.name \
            != '花火' or _ct(sess).get('shop_swap_sell_hit', 0) >= 1, \
            '席满帧应经置换账(价值比较拒)或合成通道,不得无门放行'
        assert not [k for k in _ct(sess) if k.startswith('hub_option_')]

    def test_hub_hold_registration_face(self):
        """乙臂持有段(获取 = 免费期权持有语义)的卖面保护随装配 A
        存活:hub_acquired_names_of 并集(identity_exclusions 单一源)。
        正负锁:登记名入集;未登记名不入。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            sell_gate,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
            state_of,
        )
        sess = _session(IntentionState())
        # 写点载体 = StrategyState 属性(sell_gate.HUB_ACQUIRED_ATTR
        # duck-typed 契约;发射位原写点已随乙臂收编退役,持有段读面
        # 仍消费本属性——收编后的写者 = 3.7 候选体系持有登记,过渡期
        # 由测试直写载体验证读面)。
        setattr(state_of(sess), sell_gate.HUB_ACQUIRED_ATTR, ['花火'])
        assert '花火' in sell_gate.hub_acquired_names_of(sess)
        assert '三月七' not in sell_gate.hub_acquired_names_of(sess)
        # 排除集消费位(装配 A 单一源):登记名入 identity 排除并集。
        assert '花火' in sell_gate.identity_exclusions(sess, ())


# ===== 丙臂收编:守息缺省并入统一金约束门 =====


class TestArmCHoldDefault:

    def test_no_candidate_frame_zero_buy_zero_paid_refresh(self):
        """丙臂守息缺省(合并原三面):甲乙候选皆空帧(p2plus 无目标、
        店面无资格件)零买入 + 零付费刷新(三段式刷新判据在无合格缺口
        帧 fail-closed;旧 R1 no_chaseable_member 键随判据面退役);
        收工关店(合法空帧)。"""
        # 金 45 < 息线 50:②(b) 奖励帧死金压库不辖(非奖励节点)、
        # 溢余段不辖——丙臂缺省守息面(零买入零付费刷新)。
        st = _state(gold=45, plane=2,
                    shop_cards=[_card('注册表外散件Z', cost=1)])
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert not isinstance(act, (CwActionBuyCardParam,
                                    CwActionRefreshShopParam)), act
        assert isinstance(act, CwActionCloseShopParam)
        ct = _ct(sess)
        assert 'shop_no_target_hold_default' not in ct, \
            '丙臂独立守息分支键已收编(统一金约束门)'
        assert 'shop_r1_no_chaseable_member' not in ct, \
            'R1 判据键随路径总账退役'

    def test_upgrade_not_frozen_by_hold_default(self):
        """升级不冻结面(辖域切分腿承继):k_members 空帧升级既有授权
        照常发射——空窗帧不因丙臂缺省冻结发展。"""
        from sr_od.application.currency_war.kernel.cw_vocab import (
            CwActionLevelUpParam,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            entry,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            session_scope as _ss3,
        )
        sess_m3 = _session(IntentionState())
        cw4_gs(sess_m3, gold=80, level=4, round_num=2, node='battle',
               bench=[BenchSlot(kind='unit',
                                unit=Unit(char_id='注册表外散件A', star=1))],
               front_row=[Unit(char_id=f'注册表外散件{i}', star=2)
                          for i in range(4)], deploy_cap=4)
        cw4_gs(sess_m3).observe(
            cw4_gs(sess_m3).node_pos, (2, 2),
            sig=ChannelSig(family='obs', actor='cw4_seed',
                           mode='synthesized'))
        _ss3.mark_shop_handled(cw4_gs(sess_m3))
        out = entry.emit(sess_m3, None)
        assert [e for e in out if isinstance(e.action, CwActionLevelUpParam)], \
            '丙臂守息不得冻结升级既有授权(发展优先不变量,01 §8-2)'


# ===== k_members 下游同源(锁 6 承继;换源 = 回退集)=====


class TestKMembersDownstream:

    def test_fallback_members_reach_m2_and_rejects(self):
        """换源申报承继:回退方向成员整体进 k_members——M2 义务买缺员
        成员;线外件维持 non_line 拒因;卖免面:燃料候选排除回退成员
        (zero_overlap 排除集换源,成员在 bench 不出燃料候选)。"""
        comp = get_comp('希儿量子')
        chars, _eq = cw_intention._line_hoard(comp)
        missing_piece = sorted(m for m in chars
                               if m not in comp.core_chars)[0]
        st = _state(hp=100, shop_cards=[_card(missing_piece, cost=1),
                                        _card('注册表外散件Z', cost=1,
                                              x=1)])
        st['bench'] = [_bc(m) for m in comp.core_chars]
        st['front_row'] = [Unit(char_id='板上件锚', star=1)]
        sess = _session(IntentionState())
        act = _decide(st, sess)
        assert isinstance(act, CwActionBuyCardParam) \
            and act.reason.startswith('m2_')
        rejects = getattr(state_of(sess), 'cw4_shop_rejects', {})
        assert str(rejects.get('注册表外散件Z', '')).startswith('non_line')
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            mandate as m,
        )
        gs = cw4_gs(sess)
        k_members = tuple(sorted(set(chars)))
        fuel = m.fuel_sell_candidates(
            st['bench'], k_members, state=gs, counters={}, dedup_names=set())
        for c in fuel:
            assert m._slot_cid(c) not in k_members, \
                '回退成员不得入燃料候选(卖免面换源失效)'
