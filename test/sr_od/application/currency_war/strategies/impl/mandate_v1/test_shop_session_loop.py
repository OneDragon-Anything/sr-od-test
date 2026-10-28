"""商店会话重排批 3.6 行为测试(判据唯一源 = shop_session.md §1-§5;
迭代 2026-10-12-prep-shop-workflow-redesign)。

测试面(landing 3.6 完成判据):

1. **读数协议测试**(§4.2):失效触发族逐项(选卡/合成/晶矿/升 9 级/
   计数达阈)+ 会话入口再锚定 + 多卖循环第二笔起账面判缺口(禁逐笔
   开店重读)+ 动作伴生入金记账(漏账偏差侦测的账面侧);
2. **六序承继测试**(§2.2):未锁定期序 1 候选态(贯穿件恒囤)/场况
   插件会话累计额度;
3. **三段式刷新判据 + 停留门**(§2.4):P1 恒零主动付费刷新 / 段边界
   (P2 未锁窗口候选缺件驱动 / 锁定后星级目标)/ 停留门等级 < 带下界
   → 升级优先不刷;
4. **重开触发测试**(§4.2 解拦复核):席位空出解拦 / 金位解除解拦
   (义务件破息豁免形态)/ 读数开门形态;升级意图出口形态(转场关店
   不置标记/待付窗返回 None 会话继续/资格门逐道拒因)由本文件
   TestUpgradeIntentExit 承载,翻转行为差对照由 test_intention +
   test_levelup_prob_axis 承载,不双测;
5. **刷新终结语义回归**(§1):刷新(op 级重进)仍属同一会话——
   会话标记与清单不受扰动,收工后置标记;
6. **商店期动作面形态帧测试**(原 test_cw_shop_action_face_contraction
   并入;2026-09-14 收缩裁定随 3.6 会话重写废止,用户裁定 2026-10-13):
   各形态帧首动作 ∈ 闭集 {买牌, 刷新, 关店, 卖备战席};席满买入 =
   店内置换账/恒买腾位/筹资(「关店→备战卖→重开」腾位链废止);牌面
   持久契约(节点内卖出腾位 → 买入原在店件,牌面不因店内卖出/重开
   刷新,research/economy.md §2.1);筹资兜底穷尽机会清单。

实机观察点登记(3.5 风险传递,实机首跑 reconcile 显影):
- 出售区拖拽落点(R1 显隐成因;R2 拖拽高亮 (108,786) 亮团是否激活
  证据)——拖拽 no-op 时按 no_method 坐标区直接 MCP 改 rect;
- 账面-实读偏差(漏账侦测信号)。
"""
from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_comps import (
    COMP_LIBRARY,
    CORE_SINGLE_CARD_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    XP_TO_NEXT_LEVEL,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    NodeKey,
    ShopCard,
    ShopPayload,
    ShopSlot,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    CwActionCloseShopParam,
    CwActionOpenShopParam,
    CwActionRefreshShopParam,
    CwActionSellBenchParam,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    entry,
    session_scope,
    shop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    shop_session as shop_sess,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.protection import (
    four_system_members,
)
from sr_od.application.currency_war.strategies.mandate_v1_strategy import (
    MandateV1Live,
)

_LOGIC_SIG = ChannelSig(family='logic_action', actor='cw-36-loop',
                        mode='compute')
_OBS_SIG = ChannelSig(family='obs', actor='cw-36-loop',
                      mode='synthesized')

_LINE = set(COMP_LIBRARY[0].core_chars) | set(COMP_LIBRARY[0].shared_chars)
_MEMBER = COMP_LIBRARY[0].core_chars[0]


def _fuel(count: int, exclude: tuple[str, ...] = ()) -> list[str]:
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    out = [n for n in CHARACTERS
           if n not in _LINE and n not in exclude
           and n not in CORE_SINGLE_CARD_REGISTRY
           and n not in four_system_members()]
    return out[:count]


def _frame(*, gold: int = 60, bench=(), deployed=(), shop_cards=(),
           level: int = 3, plane: int = 1, round_num: int = 3,
           node_kind: str = 'reward', comp=None, hist=None,
           hp: int = 60, actives: tuple = (), xp: tuple | None = None):
    """商店决策帧(直构;金位账面/边界判重随种子稳态钉位;hist 直赋
    node_hist_pos 位面水位线;hp/actives/xp 供资格门逐道用例构帧)。"""
    sess = StrategySession(rng=random.Random('cw-36-loop'))
    st = state_of(sess)
    st.cw4_counters = {}
    st.target_comp = comp if comp is not None else COMP_LIBRARY[0]
    gs = game_state_of(sess)
    gs.write_logic(gs.node, NodeKey(plane=plane, round_num=round_num,
                                    kind=node_kind),
                   produced_by='cw-36-loop', sig=_LOGIC_SIG)
    gs.write_logic(gs.level, level, produced_by='cw-36-loop',
                   sig=_LOGIC_SIG)
    from sr_od.application.currency_war.kernel.cw_economy import (
        XP_TO_NEXT_LEVEL,
    )
    if xp is not None:
        gs.write_logic(gs.xp, xp, produced_by='cw-36-loop',
                       sig=_LOGIC_SIG)
    elif level in XP_TO_NEXT_LEVEL:
        gs.write_logic(gs.xp, (0, XP_TO_NEXT_LEVEL[level]),
                       produced_by='cw-36-loop', sig=_LOGIC_SIG)
    gs.write_logic(gs.gold, gold, produced_by='cw-36-loop',
                   sig=_LOGIC_SIG)
    gs.observe(gs.hp, hp, evidence='cw-36-loop', sig=_OBS_SIG)
    if actives:
        gs.observe(gs.active_strategies, list(actives),
                   evidence='cw-36-loop', sig=_OBS_SIG)
    slots = [BenchSlot(kind='unit', unit=Unit(char_id=n, star=s))
             for n, s in bench]
    gs.write_logic(gs.bench, BenchView(slots=slots, capacity=9),
                   produced_by='cw-36-loop', sig=_LOGIC_SIG)
    gs.write_logic(gs.deployed, _dvs([Unit(char_id=n, star=1)
                                      for n in deployed], []),
                   produced_by='cw-36-loop', sig=_LOGIC_SIG)
    cards = [ShopSlot(kind='content',
                      card=ShopCard(name=n, faction='', cost=c,
                                    star=s, slot=i + 1))
             for i, (n, c, s) in enumerate(shop_cards)]
    cards += [ShopSlot(kind='empty')] * (5 - len(cards))
    gs.write_logic(gs.shop, ShopPayload(cards=cards, refresh_probs={}),
                   produced_by='cw-36-loop', sig=_LOGIC_SIG)
    gs.observe(gs.node_pos, (plane, round_num), evidence='cw-36-loop',
               sig=_OBS_SIG)   # 标记写入的节点号读面(生产观察链)
    if hist is not None:
        gs.node_hist_pos = hist
    live = _live(gs, st)   # 状态接线先行(gs 宿主统一,边界写入同状态)
    gs.strategy_state = st   # 宿主归一:session_scope 函数族经 gs 取态
    st.node_boundary_last_pos = None   # 边界执行态(plane2/窗口谓词置位)
    session_scope.handle_node_boundary(gs)
    st.gold_ledger = gold   # 边界重置清账面后再锚定(种子稳态)
    return live, sess, gs, st


def _live(gs, st):
    from sr_od.application.currency_war.strategies.mandate_v1_strategy import (
        MandateV1Live,
    )
    live = MandateV1Live(gs, SimpleNamespace(strategy_seed=None))
    live.state = st
    return live


def _decide_once(sess, cfg=None):
    gs = game_state_of(sess)
    return shop.decide_shop_action(
        gs, sess, cfg or SimpleNamespace(ev_arm='full'),
        registry=DEFAULT_REGISTRY)


# ============================================================ 读数协议测试


class TestGoldLedgerProtocol:

    def test_invalidation_families(self):
        """失效触发族逐项(§4.2 协议②):选卡帧/合成结果帧/晶矿/升
        9 级/计数达阈——事件帧置 None(账面失效),计数键族归因。"""
        live, sess, gs, st = _frame()
        assert st.gold_ledger == 60
        shop_sess.note_pick_frame(gs)
        assert st.gold_ledger is None
        assert st.cw4_counters.get('gold_ledger_invalidated_pick') == 1
        st.gold_ledger = 60
        shop_sess.note_ore_click(gs)
        assert st.gold_ledger is None
        st.gold_ledger = 60
        shop_sess.note_levelup_emission(gs, 9)
        assert st.gold_ledger is None
        assert st.cw4_counters.get('gold_ledger_invalidated_level9') == 1
        st.gold_ledger = 60
        shop_sess.note_levelup_emission(gs, 5)   # 非 9 级:只伴生不清账面
        assert st.gold_ledger == 60
        st.gold_ledger = 60
        gs.effects.refresh_total = 19
        shop_sess.note_refresh_counters(gs, 2)
        assert st.gold_ledger is None   # 总刷 20 达阈(二手市场)

    def test_merge_result_frame_detection(self):
        """合成族:持有 3★ 集合帧差出现新增 ⇒ 失效(任何 3★ 合成结果
        帧不分源);无变化帧不失效。"""
        live, sess, gs, st = _frame(bench=[('花火', 3)])
        st.gold_ledger = 60
        assert shop_sess.detect_merge_result_frame(gs) is False
        assert st.gold_ledger == 60   # 首帧建基线不清账面
        gs.write_logic(gs.bench,
                       BenchView(slots=[BenchSlot(
                           kind='unit', unit=Unit(char_id='花火', star=3)),
                           BenchSlot(
                           kind='unit', unit=Unit(char_id='符玄', star=3))],
                           capacity=9),
                       produced_by='cw-36-loop', sig=_LOGIC_SIG)
        assert shop_sess.detect_merge_result_frame(gs) is True
        assert st.gold_ledger is None

    def test_anchor_on_new_visit(self):
        """会话入口再锚定(§4.2 协议③):visit 序号推进帧以实读重锚
        账面(消除累积漂移);失效帧的决策入口先锚定后消费。"""
        live, sess, gs, st = _frame()
        st.gold_ledger = None
        live.decide_shop_action()
        assert st.gold_ledger == 60   # 首帧锚定
        # 失效后重进(刷新重进序号 +1):再锚定。
        st.gold_ledger = None
        st.cw4_segment_serial += 1
        gs.write_logic(gs.gold, 58, produced_by='cw-36-loop',
                       sig=_LOGIC_SIG)
        live.decide_shop_action()
        assert st.gold_ledger == 58

    def test_multisell_gap_uses_ledger_no_reopen(self):
        """多卖循环第二笔起账面判缺口(§4.2 协议④):筹资序列逐笔卖出
        期间零开店动作(禁逐笔重读;session_funding 卖到缺口闭合)。"""
        fuels = _fuel(3)
        live, sess, gs, st = _frame(gold=1, node_kind='reward',
                                    bench=[(n, 1) for n in fuels],
                                    deployed=[fuels[0]],
                                    shop_cards=[(_MEMBER, 3, 1)])
        acts = []
        for _ in range(6):
            a = live.decide_shop_action()
            acts.append(a)
            if isinstance(a, CwActionCloseShopParam):
                break
            if isinstance(a, CwActionSellBenchParam):
                # 卖出落地投影:bench 清槽 + 回金入账面(上报链写
                # gs.gold,账面同步 = 同值)。
                slots = list(gs.bench.value.slots)
                slots[a.bench_idx] = BenchSlot(kind='empty')
                gs.write_logic(gs.bench,
                               BenchView(slots=slots, capacity=9),
                               produced_by='cw-36-loop', sig=_LOGIC_SIG)
                gs.write_logic(gs.gold, gs.gold.value + (a.income or 0),
                               produced_by='cw-36-loop', sig=_LOGIC_SIG)
                st.gold_ledger = gs.gold.value
        assert not [a for a in acts
                    if isinstance(a, CwActionOpenShopParam)], \
            '会话内筹资序列禁逐笔开店重读'
        sells = [a for a in acts if isinstance(a, CwActionSellBenchParam)]
        buys = [a for a in acts if isinstance(a, CwActionBuyCardParam)]
        assert len(sells) >= 2 and sells[0].reason == 'session_funding'
        assert buys and buys[0].card.name == _MEMBER, \
            '凑够即买(缺口闭合后下一帧买入接手)'

    def test_anchor_drift_counter(self):
        """锚定位漏账偏差留痕(R1):锚定前账面 ≠ 实读 ⇒ drift 计数
        + 末次差值;无偏差帧零计数(伴生记账正确的对照面)。"""
        live, sess, gs, st = _frame(gold=60)
        st.gold_ledger = 55   # 假设漏账:账面 55 vs 实读 60
        st.cw4_segment_serial += 1
        shop_sess.anchor_gold_ledger_if_new_visit(gs)
        ct = st.cw4_counters
        assert ct.get('gold_ledger_drift') == 1
        assert ct.get('gold_ledger_drift_last_delta') == 5
        # 对照:账面对齐帧零新增。
        st.cw4_segment_serial += 1
        shop_sess.anchor_gold_ledger_if_new_visit(gs)
        assert ct.get('gold_ledger_drift') == 1

    def test_companion_gold_accounted(self):
        """伴生入金记账(§4.2 协议① 单卡型):返利族 5 费第三笔买入
        ⇒ +3 双写(账面 + gs.gold 期望态投影扩展)——漏账偏差侦测的
        账面侧。"""
        from sr_od.application.currency_war.data.cw_chars import CHARACTERS
        five_cost = next(n for n in CHARACTERS if CHARACTERS[n].cost == 5)
        live, sess, gs, st = _frame(
            gold=60, node_kind='reward',
            bench=[(n, 1) for n in _fuel(3)],
            deployed=[_fuel(4)[0]],
            shop_cards=[(five_cost, 5, 1)])
        gs.observe(gs.active_strategies, ['返利'], evidence='cw-36-loop',
                   sig=_OBS_SIG)
        act = live.decide_shop_action()
        assert isinstance(act, CwActionBuyCardParam) \
            and act.card.name == five_cost
        assert st.shop_five_cost_buys == 1, \
            '返利族 5 费购买计数未随发射位登记'
        st.gold_ledger = gs.gold.value
        # 再两笔 5 费买入(同会话):第三笔触发 +3。
        g0 = gs.gold.value
        led0 = st.gold_ledger
        card = ShopCard(name=five_cost, faction='', cost=5, star=1, slot=2)
        for _i in range(2):
            shop_sess.account_buy_companion_gold(gs, card)
        assert gs.gold.value == g0 + 3
        assert st.gold_ledger == led0 + 3, '双写同步:账面与容器同额入金'


# ============================================================ 六序承继测试


class TestOrderInheritance:

    def test_unlocked_cross_line_keep_buys(self):
        """未锁定期序 1 候选态:贯穿件恒囤层(全线路通用贯穿件,
        stage_transitions Q1 真贯穿层)在店 → 序 1 买入(m2 买因),
        无锁定/候选也命中。"""
        live, sess, gs, st = _frame(
            gold=60, node_kind='reward', comp=None,
            bench=[(n, 1) for n in _fuel(2)],
            deployed=[_fuel(3)[0]],
            shop_cards=[('三月七', 5, 1)])
        st.target_comp = None   # 空窗:候选空
        act = live.decide_shop_action()
        assert isinstance(act, CwActionBuyCardParam), act
        assert act.card.name == '三月七'
        assert act.reason.startswith('m2_'), act.reason

    def test_scene_plugin_budget_cap(self):
        """场况插件会话累计额度(§2.2 序 2):额度 = 会话开始帧
        deploy_cap − deployed 快照;额度尽即停(被拦插件不进机会清单
        ——上阵空位非节点内可解除资源)。"""
        from sr_od.application.currency_war.data.cw_chars import CHARACTERS
        from sr_od.application.currency_war.data.cw_factions import FACTIONS
        # 插件件选择约束:身份必须非保护集非核心(序 1 义务面/囤货臂都
        # 不辖——本测试专辖序 2 额度门,不被前序臂掩蔽)。档位约束:
        # tier_next > 阈档 3(等级 3 帧的 deploy_cap 采信下限),使
        # 「板面差一人进下一档」与「deployed == deploy_cap(额度 0)」
        # 可以同时成立。
        pick = None
        for faction_tag, fac in FACTIONS.items():
            members = [n for n, ch in CHARACTERS.items()
                       if faction_tag in getattr(ch, 'factions', ())
                       and ch.cost
                       and n not in CORE_SINGLE_CARD_REGISTRY
                       and n not in four_system_members()]
            if len(fac.tiers) and fac.tiers[0] == 3 \
                    and len(members) >= 3:
                pick = (faction_tag, fac, members)
                break
        assert pick is not None, '注册表无 3 档无关身份羁绊(数据漂移?)'
        faction_tag, fac, members = pick
        tier_next = fac.tiers[0]
        plugin = members[0]
        deployed = members[1:tier_next]   # 2 人(差一人进 3 档)
        live, sess, gs, st = _frame(
            gold=60, level=2, node_kind='reward', comp=None,
            bench=[(n, 1) for n in _fuel(3)], deployed=deployed,
            shop_cards=[(plugin, 3, 1)])
        gs.observe(gs.deploy_cap, len(deployed), evidence='cw-36-loop',
                   sig=_OBS_SIG)
        st.target_comp = None
        st.cw4_segment_serial += 1   # 触发额度快照(cap − deployed = 0)
        act = live.decide_shop_action()
        assert not (isinstance(act, CwActionBuyCardParam)
                    and act.card.name == plugin), \
            '额度尽即停:场况插件不得越会话累计额度买入'
        assert state_of(sess).cw4_counters.get(
            'scene_plugin_budget_exhausted', 0) >= 1
        recs = st.shop_opportunities
        assert not [r for r in recs if r.card_name == plugin], \
            '被拦插件不进机会清单(拦因在 {席满,金不足} 闭集外)'


# ============================================================ 三段式刷新判据


class TestThreeStageRefresh:

    def _warrant(self, live, sess, gs):
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
            refresh as crit_refresh,
        )
        return crit_refresh.refresh_warranted(gs, sess)

    def test_p1_never_paid_refresh(self):
        """P1 恒不主动付费刷新(§2.4 段边界;阶段优先于锁定态——P1
        硬规则锁定局同样不刷)。"""
        live, sess, gs, st = _frame(gold=60, plane=1, hist=None,
                                    node_kind='reward')
        ok, key = self._warrant(live, sess, gs)
        assert (ok, key) == (False, 'p1_no_refresh')
        acts = []
        for _ in range(4):
            a = live.decide_shop_action()
            acts.append(a)
            if isinstance(a, (CwActionCloseShopParam,)):
                break
        assert not [a for a in acts
                    if isinstance(a, CwActionRefreshShopParam)
                    and a.cost > 0], 'P1 帧零主动付费刷新'

    def test_p2_unlocked_gap_drives(self):
        """P2 未锁窗口:候选缺件驱动(候选快照 = 本判据申报输入面,
        直种锁定语义免耦合评分内核——评分面主题测试在 test_line_select)。

        - 候选线缺员且等级 ≥ 其概率带下界 → 可刷;
        - 候选线全员持有(缺员 ∅)→ 不刷(fail-closed)。
        (批 3.7 键面归一:target_comp 非空 = 锁定线槽,未锁窗口帧须显式
        置 None + 直种候选快照。)"""
        comp = COMP_LIBRARY[0]
        members = list(comp.core_chars) + list(
            getattr(comp, 'shared_chars', None) or [])
        # 缺员帧:候选线成员全不在手 ⇒ 缺员存在(等级 3 ≥ 1-2 费带下界)。
        live, sess, gs, st = _frame(gold=60, plane=2, hist=(2, 1),
                                    node_kind='reward',
                                    bench=[(n, 1) for n in _fuel(2)],
                                    deployed=[_fuel(3)[0]])
        st.target_comp = None
        st.line_candidates = (comp.name,)
        ok, key = self._warrant(live, sess, gs)
        assert (ok, key) == (True, ''), '候选缺员 + 带内 → 可刷'
        # 全员持有帧:缺员 ∅ ⇒ 不刷。
        live2, sess2, gs2, st2 = _frame(
            gold=60, plane=2, hist=(2, 1), node_kind='reward',
            bench=[(m, 1) for m in members[:9]],
            deployed=members[9:] or [members[0]])
        st2.target_comp = None
        st2.line_candidates = (comp.name,)
        ok2, key2 = self._warrant(live2, sess2, gs2)
        assert (ok2, key2) == (False, 'unlocked_no_qualified_gap'), (
            '候选全员持有时刷新无目标(候选缺件驱动 fail-closed)')

    def test_locked_star_target_and_stay_gate(self):
        """锁定后星级目标驱动:停留目标存在 ∧ 等级 ≥ 带下界 → 可刷;
        等级 < 带下界 → 升级优先不刷(停留门辖,主式纯真值式)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
            levelup,
        )
        comp = COMP_LIBRARY[0]
        # 锁定线 + 停留目标:辅助达标(2★)+ CARRY 缺 3★。
        carry = comp.core_chars[0]
        aux = [m for m in sorted(_LINE) if m != carry][:2]
        need = (comp.need_star or {}).get(carry, 2)
        bench = [(m, need) for m in aux]
        live, sess, gs, st = _frame(
            level=5, plane=2, hist=(2, 1), node_kind='reward', comp=comp,
            bench=bench, deployed=[aux[0]], shop_cards=[(carry, 3, 1)])
        session_scope.write_line_lock(gs, comp.name)
        target = levelup.stay_target_of(gs)
        assert target is not None
        lo, _hi = levelup.prob_band_of_cost(target[2])
        if lo <= 5:
            assert self._warrant(live, sess, gs)[0] is True
        else:
            ok, key = self._warrant(live, sess, gs)
            assert (ok, key) == (False, 'stay_gate_upgrade_first')


def _skip_member(name: str) -> bool:
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    ch = CHARACTERS.get(name)
    return ch is None or not ch.cost


# ============================================================ 重开触发测试


class TestReopenTriggers:

    def _close_with_gold_short(self, live, sess, gs, st, *, name, price):
        """金不足收工:金 < 价 ∧ bench 空仓(筹资无候选)→ 记录
        gold_short 机会清单 + 收工关店(§4.2 清单闭环的写入端)。"""
        act = live.decide_shop_action()
        assert isinstance(act, CwActionCloseShopParam), act
        assert any(r.card_name == name and r.blocked_by == 'gold_short'
                   for r in st.shop_opportunities), \
            f'金不足机会清单记录缺席: {st.shop_opportunities}'
        assert st.shop_handled is not None
        return act

    def _close_with_bench_full(self, live, sess, gs, st, *, name):
        """席满收工:bench 全持有件(置换无可让位候选)+ 缺员件在店 →
        记录 bench_full 机会清单 + 收工关店。"""
        act = live.decide_shop_action()
        assert isinstance(act, CwActionCloseShopParam), act
        assert any(r.card_name == name and r.blocked_by == 'bench_full'
                   for r in st.shop_opportunities), \
            f'席满机会清单记录缺席: {st.shop_opportunities}'
        return act

    def test_seat_freed_reopens_session(self):
        """席位空出解拦:席满记录 → 备战腾出一席 → 第 4 步入口复核
        解拦(清标记开店);未解拦时第 4 步按标记跳过。"""
        aux = [m for m in sorted(_LINE) if m != _MEMBER]
        holds = (aux * 3)[:9]   # 2★ 线内达标件铺满(置换价值比较拒)
        live, sess, gs, st = _frame(gold=60, node_kind='reward',
                                    bench=[(n, 2) for n in holds],
                                    deployed=[holds[0]],
                                    shop_cards=[(_MEMBER, 3, 1)])
        self._close_with_bench_full(live, sess, gs, st, name=_MEMBER)
        assert st.shop_handled is not None   # 收工置标记
        # 席位未空出:复核不解拦,第 4 步跳过(标记辖)。
        assert entry._step4_shop_session_pending(sess, gs) is False
        # 备战腾席(bench 移除一件):
        slots = list(gs.bench.value.slots)
        slots[0] = BenchSlot(kind='empty')
        gs.write_logic(gs.bench, BenchView(slots=slots, capacity=9),
                       produced_by='cw-36-loop', sig=_LOGIC_SIG)
        assert entry._step4_shop_session_pending(sess, gs) is True
        assert st.shop_handled is None   # 解拦清标记

    def test_gold_released_reopens_session(self):
        """金位解除解拦(义务件破息豁免形态):金不足记录 + 账面达
        解除线 → 解拦(义务类金不足入清单合法,解拦购买允许破息)。"""
        live, sess, gs, st = _frame(gold=1, node_kind='reward',
                                    bench=[],
                                    deployed=[_fuel(3)[0]],
                                    shop_cards=[(_MEMBER, 3, 1)])
        self._close_with_gold_short(live, sess, gs, st,
                                    name=_MEMBER, price=3)
        # 账面不足:不解拦。
        assert entry._step4_shop_session_pending(sess, gs) is False
        # 节点收入进账(账面 5 ≥ 价 3):解拦。
        st.gold_ledger = 5
        gs.write_logic(gs.gold, 5, produced_by='cw-36-loop',
                       sig=_LOGIC_SIG)
        assert entry._step4_shop_session_pending(sess, gs) is True

    def test_gold_short_stale_ledger_read_opens(self):
        """读数开门形态(路径③):金不足记录在场 ∧ 账面失效 → 第 4 步
        开店读金(标记不动——锚定后标记门即关,下帧复核继续)。"""
        live, sess, gs, st = _frame(gold=1, node_kind='reward',
                                    bench=[],
                                    deployed=[_fuel(3)[0]],
                                    shop_cards=[(_MEMBER, 3, 1)])
        self._close_with_gold_short(live, sess, gs, st,
                                    name=_MEMBER, price=3)
        st.gold_ledger = None   # 失效(晶矿/选卡等事件后)
        assert st.shop_handled is not None
        assert entry._step4_shop_session_pending(sess, gs) is True
        assert st.shop_read_intent is True   # 读数会话意图标记
        assert st.shop_handled is not None   # 读数分支不清标记

    def test_read_session_close_without_processing_no_mark(self):
        """读数会话零处理收工不置标记(§1 路径③:同节点后续真实会话
        不受污染);命中处理需求转正常会话(标记照写)。"""
        live, sess, gs, st = _frame(gold=60, node_kind='reward',
                                    bench=[(n, 1) for n in _fuel(2)],
                                    deployed=[_fuel(3)[0]],
                                    shop_cards=[])
        st.shop_read_intent = True
        act = live.decide_shop_action()
        assert isinstance(act, CwActionCloseShopParam)
        assert st.shop_handled is None, '读数会话零处理不置标记'
        assert st.shop_read_intent is False
        # 对照:正常会话收工置标记。
        live2, sess2, gs2, st2 = _frame(gold=60, node_kind='reward',
                                        bench=[(n, 1) for n in _fuel(2)],
                                        deployed=[_fuel(3)[0]],
                                        shop_cards=[])
        act2 = live2.decide_shop_action()
        assert isinstance(act2, CwActionCloseShopParam)
        assert st2.shop_handled is not None


# ============================================================ 升级意图出口
# (迭代 2026-10-17-levelup-shop-transition design §2.1 三分支:商店
# 会话不再执行店内升级——命中 ∧ 可发射 → 关店转场不置标记;命中 ∧
# 待付窗 / 未命中 → None 会话继续;资格门逐道拒因在册。)


class TestUpgradeIntentExit:

    def _stay_frame(self, *, gold: int, level: int = 5,
                    hp: int = 60, actives: tuple = (),
                    xp: tuple | None = None):
        """停留门构帧:锁定线(列车同行)+ 辅助达标(三月七 2★/瓦尔特
        1★/花火 2★),唯一未完成星级目标 = 姬子·启行(3 费,概率带
        (7,7))——level 5 < 带下界 → 停留门升级优先臂确定触发
        (非奖励帧,资格门①不拦)。hp/actives/xp 供资格门④⑤⑥构帧(击数/支付门/资金线门)。"""
        comp = COMP_LIBRARY[0]
        carry = comp.core_chars[0]
        aux = [m for m in sorted(_LINE) if m != carry]
        need = comp.need_star or {}
        return _frame(level=level, gold=gold, plane=2, hist=(2, 1),
                      node_kind='battle', comp=comp,
                      bench=[(m, need.get(m, 1)) for m in aux],
                      deployed=[aux[0]],
                      shop_cards=[], hp=hp, actives=actives, xp=xp)

    def test_hit_emissible_transition_close_without_mark(self):
        """命中 ∧ 可发射 → 关店转场且不置 handled 标记(design §2.1
        分支一):金充裕带滞后帧(等级 < 带下界,现金 − 批 ≥ 线)资格门
        全链通过 → 首动作 = 关店;标记未置(转场帧的后继 = 备战升级执行,
        商店未「事情办完」);转场计数在册;零店内卖出/店内升级发射。"""
        live, sess, gs, st = self._stay_frame(gold=80)
        act = live.decide_shop_action()
        assert isinstance(act, CwActionCloseShopParam), act
        assert st.shop_handled is None, '转场关店不置 handled 标记'
        ct = st.cw4_counters
        assert ct.get('levelup_transition_close') == 1
        assert ct.get('levelup_trigger_stay_gate') == 1
        assert not [k for k in ct if k.startswith('levelup_liquidate')], \
            '店内侧变现场景消费点已退役(凑金归备战侧)'

    def test_hit_gold_short_returns_none_session_continues(self):
        """命中 ∧ 不可发射(待付窗)→ 检查返回 None,会话照常继续:
        停留门触发 ∧ 花后破线 ∧ 凑金不可达(无活期可变现)→ 资金线
        defer 拒因在册(资金面拒因统一键);会话走 §2.5 正常收工置标记
        (「等节点收入」形态成立),非转场关店。"""
        live, sess, gs, st = self._stay_frame(gold=30)
        act = live.decide_shop_action()
        ct = st.cw4_counters
        assert ct.get('levelup_trigger_stay_gate') == 1
        assert ct.get('levelup_fund_line_defer') == 1, \
            '金不足帧资格门拒因在册(资金线 defer 统一键)'
        assert ct.get('levelup_transition_close', 0) == 0, '待付窗不转场'
        assert isinstance(act, CwActionCloseShopParam), act
        assert st.shop_handled is not None, \
            '待付窗会话经正常收工置标记(出店→战斗→节点收入→备战凑金)'

    def test_gate_level_cap_frame_rejects(self):
        """资格门②等级帽帧:满级帧判据不发射(拒因在册),会话照常
        收工置标记(正常收工,非转场)。"""
        live, sess, gs, st = _frame(gold=100, level=10, plane=1,
                                    node_kind='battle', shop_cards=[])
        act = live.decide_shop_action()
        assert st.cw4_counters.get('levelup_reject_level_cap') == 1
        assert st.cw4_counters.get('levelup_transition_close', 0) == 0
        assert isinstance(act, CwActionCloseShopParam)
        assert st.shop_handled is not None

    def test_gate_reward_frame_defers(self):
        """资格门①奖励帧抑制:奖励帧(非扑满环境)不发射(拒因在册,
        抑制先于触发判定),会话照常收工置标记。"""
        live, sess, gs, st = _frame(gold=100, level=5, plane=1,
                                    node_kind='reward', shop_cards=[])
        act = live.decide_shop_action()
        assert st.cw4_counters.get('levelup_reward_node_defer') == 1
        assert st.cw4_counters.get('levelup_transition_close', 0) == 0
        assert isinstance(act, CwActionCloseShopParam)
        assert st.shop_handled is not None

    def test_gate_crisis_frame_no_hp_defer_negative_guard(self):
        """「无 hp 支」负向守卫(hp-purge 迭代 3.1):命中 ∧ 濒死带
        (hp 10)帧零 hp 拒因键——危机带拦截门已删(门序 7→6),该帧
        defer 归资金线门(金 30 花后破线 ∧ 凑金不可达),拒因键域闭集
        断言(键域 = 触发 + 资金线 defer);会话照常收工置标记。"""
        live, sess, gs, st = self._stay_frame(gold=30, hp=10)
        act = live.decide_shop_action()
        ct = st.cw4_counters
        assert ct.get('levelup_trigger_stay_gate') == 1
        _lv_keys = {k for k in ct if k.startswith('levelup_')}
        assert _lv_keys == {'levelup_trigger_stay_gate',
                            'levelup_fund_line_defer'}, \
            f'濒死帧 levelup 键域闭集(无 hp 支,门序 6 道):{sorted(_lv_keys)}'
        assert isinstance(act, CwActionCloseShopParam)
        assert st.shop_handled is not None

    def test_gate_xp_batch_payment_frame_defers_and_control(self):
        """资格门⑤经验批支付门(R-1 币种通式):血本位局(奋斗协议,
        6 血/击)∧ 血余额 < 整级血成本 → 不发射(xp_batch_payment_defer
        拒因在册);对照血足帧 → 可发射转场关店。构帧注:lv6 血批 =
        10 击 × 6 = 60,hp 45 不足血批(支付能力检查——币种余额 ≥
        整批成本;金本位局本门直通,金侧归资金线门)。"""
        live, sess, gs, st = self._stay_frame(level=6, gold=80, hp=45,
                                              actives=('奋斗协议',))
        live.decide_shop_action()
        assert st.cw4_counters.get('xp_batch_payment_defer') == 1
        assert st.cw4_counters.get('levelup_transition_close', 0) == 0
        assert st.shop_handled is not None
        # 对照:血余额足 → 全链通过 → 转场关店(不置标记)。
        live2, sess2, gs2, st2 = self._stay_frame(level=6, gold=80, hp=100,
                                                  actives=('奋斗协议',))
        act2 = live2.decide_shop_action()
        assert isinstance(act2, CwActionCloseShopParam), act2
        assert st2.cw4_counters.get('levelup_transition_close') == 1
        assert st2.shop_handled is None

    def test_gate_zero_clicks_frame_defers(self):
        """资格门④击数 > 0:XP 已满当前级(击数 0)→ 无批可发(拒因
        在册),会话照常收工置标记。"""
        live, sess, gs, st = self._stay_frame(gold=80, xp=(20, 20))
        act = live.decide_shop_action()
        assert st.cw4_counters.get('levelup_zero_clicks_defer') == 1
        assert st.cw4_counters.get('levelup_transition_close', 0) == 0
        assert isinstance(act, CwActionCloseShopParam)
        assert st.shop_handled is not None


# ============================================================ 备战随机态重开位
# (迭代 2026-10-17-levelup-shop-transition design §2.2 第 1 步/§2.4:
# 信号宿主 = GameState 簿记槽 shop_randomized_pending;写端 = T-3 商业
# 间谍升级回调,本阶段恒 False = 零行为,读端 + 清位先行。)


class TestPrepRandomizedReopen:

    def test_signal_reopens_shop_clearing_mark_and_signal(self):
        """信号在 → 清 handled 标记 + 开店进店 + 清信号(第 1 步重开位,
        置于溢出自救之后、资源动作之前);无信号帧零重开行为(不截胡
        工序,开店仍由第 5 步商店会话承接)。"""
        live, sess, gs, st = _frame(gold=60, node_kind='reward',
                                    shop_cards=[])
        # 无信号:零重开行为(首段 emit 无重开位开店铺)。
        out0 = entry.emit(sess, None)
        assert not [e for e in out0
                    if e.reason == 'step1_shop_randomized_reopen'], out0
        # 信号在(测试直种;生产写端 = T-3 商业间谍升级回调):重开位消费。
        session_scope.mark_shop_handled(gs)
        assert session_scope.shop_handled_for_current_node(gs)
        gs.shop_randomized_pending = True
        out = entry.emit(sess, None)
        assert out and out[0].reason == 'step1_shop_randomized_reopen', out
        assert isinstance(out[0].action, CwActionOpenShopParam)
        assert st.shop_handled is None, '重开位清 handled 标记'
        assert gs.shop_randomized_pending is False, '重开位消费后清信号'
        assert st.cw4_counters.get('shop_randomized_reopen') == 1, \
            '重开触发计数键在册(§2.6③ 随机态闭环取数口)'

    def test_node_boundary_sweeps_signal(self):
        """节点边界清扫:信号残留跨节点 = 旧牌面语义死亡,边界函数清位
        (design §2.4 清位两出口之二)。"""
        _live, _sess, gs, _st = _frame(gold=60, node_kind='reward',
                                       shop_cards=[])
        gs.shop_randomized_pending = True
        gs.write_logic(gs.node, NodeKey(plane=1, round_num=4,
                                        kind='reward'),
                       produced_by='cw-36-loop', sig=_LOGIC_SIG)
        gs.observe(gs.node_pos, (1, 4), evidence='cw-36-loop',
                   sig=_OBS_SIG)
        session_scope.handle_node_boundary(gs)
        assert gs.shop_randomized_pending is False, '节点边界清信号'


# ============================================================ 凑金等待帧刷新让位
# (资金序 = 升级优先于刷新:凑金等待帧的刷新让位由判据①支「升级优先」
# 直接承载——带互斥下升级触发态与刷新放行态天然分离;整级预留防御层已
# 随刷新链三组件批删除,本节测试 = 资金序声明的行为面锁定。)


class TestLevelupReserveGuard:

    def test_gold_short_wait_frame_no_refresh(self):
        """凑金等待帧零刷新(升级资金不被刷新烧):带滞后触发 ∧ 花后
        破线 ∧ 活期可补(凑金可达域)→ 资格门 gold_short 在册;刷新
        判据带互斥不批(等级 < 带下界)→ 零刷新动作,会话正常收工置
        标记(「等节点收入/备战凑金」形态成立)。"""
        comp = COMP_LIBRARY[0]
        carry = comp.core_chars[0]
        aux = [m for m in sorted(_LINE) if m != carry][:2]
        need = comp.need_star or {}
        bench = [(m, need.get(m, 1)) for m in aux] \
            + [(n, 1) for n in _fuel(4)]
        live, sess, gs, st = _frame(
            level=5, gold=68, plane=2, hist=(2, 1), node_kind='battle',
            comp=comp, bench=bench, deployed=[aux[0]], shop_cards=[])
        act = live.decide_shop_action()
        assert isinstance(act, CwActionCloseShopParam), act
        assert st.cw4_counters.get('levelup_stockpile_wait') == 1, \
            '凑金可达域帧在册(花后破线 ∧ 活期可补,待付窗)'
        assert st.cw4_counters.get('levelup_fund_line_defer', 0) == 0
        assert not isinstance(act, CwActionRefreshShopParam), \
            '凑金等待帧零刷新(升级资金完整性优先)'
        assert st.shop_handled is not None, \
            '凑金等待帧经正常收工置标记(备战侧每帧一卖收敛发射)'

    def test_in_band_frame_refresh_proceeds(self):
        """带内对照帧:等级 ∈ 带(升级判据不触发,verdict MISS 无预留)
        → 刷新照常发出(基线预算门过,reason star_target)——升级-刷新
        判据带互斥的行为面对照。"""
        bench = [(n, 1) for n in ('花火', '花火', '瓦尔特', '符玄', '缇宝',
                                   '刻律德菈', '三月七', '姬子·启行',
                                   '千冶·刃')]
        live, sess, gs, st = _frame(level=8, gold=56, plane=2, hist=(2, 1),
                                    node_kind='battle',
                                    bench=bench, deployed=['瓦尔特'],
                                    shop_cards=[])
        act = live.decide_shop_action()
        assert isinstance(act, CwActionRefreshShopParam), \
            f'带内帧(升级不触发)刷新照常(基线预算门过): {act!r}'
        assert act.reason == 'star_target'
        assert st.cw4_counters.get('levelup_stockpile_wait', 0) == 0


# ============================================================ 刷新终结语义回归


class TestRefreshTerminationSession:

    def test_refresh_reentry_same_session_mark_untouched(self):
        """刷新 = 访问终结但同一会话(§1):刷新发射 → op 级重进
        (visit 序号 +1)→ 会话继续(标记未置);收工后标记才置——
        刷新不扰动会话标记与清单。"""
        live, sess, gs, st = _frame(gold=60, plane=2, hist=(2, 1),
                                    node_kind='reward',
                                    bench=[(n, 1) for n in _fuel(2)],
                                    deployed=[_fuel(3)[0]],
                                    shop_cards=[])   # 空面隔离买面
        # 免费刷新在册 → 刷新发射(免费腿同过目标可买检查——金线不适用;
        # 本帧有空位腿,目标可买为真,刷新照发)。
        gs.write_logic(gs.free_refresh_left, 2, produced_by='cw-36-loop',
                       sig=_LOGIC_SIG)
        a1 = live.decide_shop_action()
        assert isinstance(a1, CwActionRefreshShopParam), a1
        assert st.shop_handled is None   # 刷新非收工:标记不受扰动
        # op 级重进:visit 序号 +1,新牌面(空店),继续会话——余下免费
        # 次数逐次耗尽(每 visit 一刷)后收工;会话全程标记未置。
        cards = [ShopSlot(kind='empty')] * 5
        gs.write_logic(gs.shop, ShopPayload(cards=cards,
                                            refresh_probs={}),
                       produced_by='cw-36-loop', sig=_LOGIC_SIG)
        a2 = None
        for i in range(4):
            st.cw4_segment_serial += 1
            if i >= 2:
                # 免费次数耗尽后压金归零(付费刷新的 R2 预算门拦),
                # 会话走收工——刷新终结语义在标记面上验证。
                gs.write_logic(gs.free_refresh_left, 0,
                               produced_by='cw-36-loop', sig=_LOGIC_SIG)
                gs.write_logic(gs.gold, 0, produced_by='cw-36-loop',
                               sig=_LOGIC_SIG)
                st.gold_ledger = 0
            a2 = live.decide_shop_action()
            if isinstance(a2, CwActionCloseShopParam):
                break
            assert isinstance(a2, CwActionRefreshShopParam), a2
            assert st.shop_handled is None, '刷新重进不得扰动会话标记'
            gs.write_logic(gs.free_refresh_left,
                           max(0, int(gs.free_refresh_left.value or 0) - 1),
                           produced_by='cw-36-loop', sig=_LOGIC_SIG)
        assert isinstance(a2, CwActionCloseShopParam), a2
        assert st.shop_handled is not None   # 收工才置标记


# ============================================================
# 商店期动作面形态帧测试(原 test_cw_shop_action_face_contraction 并入;
# 3.6 重排后的店内动作边界,shop_session §1 能力面)
# ============================================================

_FACE_LOGIC_SIG = ChannelSig(family='logic_action', actor='cw-36-test',
                             mode='compute')
_FACE_OBS_SIG = ChannelSig(family='obs', actor='cw-36-test',
                           mode='synthesized')


def _fuel_names(count: int, exclude: tuple[str, ...] = ()) -> list[str]:
    """非保护非核心燃料名(非线内 ∧ 注册表核心外 ∧ 四体系成员外;
    注册表现算防漂移,身份单一源 = protection.four_system_members)。"""
    out = [n for n in CHARACTERS
           if n not in _LINE and n not in exclude
           and n not in CORE_SINGLE_CARD_REGISTRY
           and n not in four_system_members()]
    assert len(out) >= count, '非保护非核心燃料名不足'
    return out[:count]


def _core_out_of_line() -> str:
    """线外 registry_core 名(C1 恒买夹具;现算防漂移)。"""
    return next(n for n in CORE_SINGLE_CARD_REGISTRY
                if n not in _LINE and CHARACTERS.get(n))


def _frame_session(*, bench_units: list[str], deployed_units: list[str],
                   card_names: list[tuple[str, int]], gold: int,
                   hp: int = 60, node_kind: str = 'prep'):
    """通用最小商店决策帧(bench/上场/店面卡/金/血可参)。deployed_
    units 非空 = 板空帧语义独立(本测试断言域不辖)。金位账面随种子锚定
    (读数协议③稳态;失效行为测试显式置 None)。"""
    comp = COMP_LIBRARY[0]
    sess = StrategySession(rng=random.Random('cw-36'))
    gs = game_state_of(sess)
    gs.write_logic(gs.node, NodeKey(plane=1, round_num=3, kind=node_kind),
                   produced_by='cw-36-test', sig=_FACE_LOGIC_SIG)
    gs.write_logic(gs.level, 3, produced_by='cw-36-test',
                   sig=_FACE_LOGIC_SIG)
    gs.write_logic(gs.xp, (0, XP_TO_NEXT_LEVEL[3]),
                   produced_by='cw-36-test', sig=_FACE_LOGIC_SIG)
    gs.write_logic(gs.gold, gold, produced_by='cw-36-test',
                   sig=_FACE_LOGIC_SIG)
    gs.observe(gs.hp, hp, evidence='cw-36-test', sig=_FACE_OBS_SIG)
    slots = [BenchSlot(kind='unit',
                       unit=Unit(char_id=n, star=1))
             for i, n in enumerate(bench_units)]
    gs.write_logic(gs.bench, BenchView(slots=slots, capacity=9),
                   produced_by='cw-36-test', sig=_FACE_LOGIC_SIG)
    gs.write_logic(gs.deployed, _dvs([Unit(char_id=n, star=1)
                     for i, n in enumerate(deployed_units)], []),
                   produced_by='cw-36-test', sig=_FACE_LOGIC_SIG)
    cards = [ShopSlot(kind='content',
                      card=ShopCard(name=n, faction='', cost=c,
                                    star=1, slot=i + 1))
             for i, (n, c) in enumerate(card_names)]
    cards += [ShopSlot(kind='empty')] * (5 - len(cards))
    gs.write_logic(gs.shop, ShopPayload(cards=cards, refresh_probs={}),
                   produced_by='cw-36-test', sig=_FACE_LOGIC_SIG)
    state_of(sess).target_comp = comp
    st = state_of(sess)
    st.gold_ledger = gold
    st.node_boundary_last_pos = (1, 3)
    live = MandateV1Live(gs, SimpleNamespace(strategy_seed=None))   # 终态契约:构造注入
    live.state = st   # 状态同源接线:会话播种对象(零参口决策读 self.state)
    return live, sess, SimpleNamespace(ev_arm='full')


# ---- 形态帧(席满置换/恒买腾位/凑息/筹资;3.6 重排后语义)----

def _frame_m4_missing_vacate():
    """M2 缺员遇席满:席满(9 燃料)+缺员(member 不在场)+店有缺员件
    → 置换账:卖首燃料(value(X) 线成员 > value(Y) 燃料,同口径直比
    成立)。"""
    fuels = [n for n in CHARACTERS if n not in _LINE][:9]
    assert len(fuels) == 9
    return _frame_session(
        bench_units=fuels,
        deployed_units=list(COMP_LIBRARY[0].core_chars[1:4]),
        card_names=[(_MEMBER, 3)], gold=60, node_kind='reward')


def _frame_m2_stockpile_vacate():
    """囤分支遇席满:成员持有恰 1 张,店刷同员 1★ 第二张 → 置换账卖燃料。"""
    fuels = _fuel_names(8)
    return _frame_session(
        bench_units=[_MEMBER] + fuels,
        deployed_units=list(COMP_LIBRARY[0].core_chars[1:4]),
        card_names=[(_MEMBER, 3)], gold=60, node_kind='reward')


def _frame_core_unlocked_vacate():
    """C1 恒买遇席满:店刷线外 registry_core 名,金可足、席满 → 恒买
    豁免价值比较(c1_make_room 直接卖首位让位候选)。"""
    fuels = _fuel_names(8)
    return _frame_session(
        bench_units=[_MEMBER] + fuels,
        deployed_units=list(COMP_LIBRARY[0].core_chars[1:4]),
        card_names=[(_core_out_of_line(), 3)], gold=45, node_kind='reward')


def _frame_interest_sell():
    """凑息回拉形态:金贴息线下、席不满、缺员件不在店 → 店内零凑息
    卖射(凑息 = 备战第 7 步接线),收工关店交回备战。"""
    return _frame_session(
        bench_units=_fuel_names(5),
        deployed_units=list(COMP_LIBRARY[0].core_chars[1:2]),
        card_names=[], gold=47)


def _frame_funding_support_sell():
    """筹资形态(主路径):缺员在店 + 金不足 + bench 活期件在场 →
    会话内筹资卖出(session_funding;凑够即买下一帧接手)。"""
    fuels = _fuel_names(8, exclude=(_fuel_names(1)[0],))
    return _frame_session(
        bench_units=fuels,
        deployed_units=_fuel_names(1),
        card_names=[(_MEMBER, 3)], gold=1, hp=10)


def _frame_funding_hold_fallback():
    """筹资穷尽形态:缺员在店 + 金不足 + bench 空仓(活期/兜底池全
    空)→ 候选与兜底双穷尽 → 记录金不足机会清单收工(shop_session
    §2.3;义务类兜底可卖持有件〔分支①〕的形态由卖出面测试辖,本帧
    校验穷尽边界)。"""
    return _frame_session(
        bench_units=[],
        deployed_units=_fuel_names(1),
        card_names=[(_MEMBER, 3)], gold=1, hp=10)


_FORM_FRAMES = {
    'm4_missing_vacate': _frame_m4_missing_vacate,
    'm2_stockpile_vacate': _frame_m2_stockpile_vacate,
    'core_unlocked_vacate': _frame_core_unlocked_vacate,
    'interest_pullback': _frame_interest_sell,
    'funding_support': _frame_funding_support_sell,
    'funding_hold_fallback': _frame_funding_hold_fallback,
}

#: 3.6 重排后的商店域动作面闭集(店内卖备战席启用;购买经验整批随
#: 升级转场退役——2026-10-17 迭代 T-1,升级执行位迁备战画面,
#: shop_session §1 店内动作边界)。
_SHOP_ACTION_FACE = {'CwActionBuyCardParam', 'CwActionRefreshShopParam',
                     'CwActionCloseShopParam', 'CwActionSellBenchParam'}

#: 席满买入三形态(置换账/恒买腾位/筹资)的首动作 = 店内卖出。
_SELL_FIRST_FORMS = {'m4_missing_vacate', 'm2_stockpile_vacate',
                     'core_unlocked_vacate', 'funding_support'}


@pytest.mark.parametrize('case', list(_FORM_FRAMES))
def test_shop_forms_stay_in_reordered_action_face(case: str):
    """动作面测试(六形态逐一;参数化纪律沿袭):各形态帧首动作 ∈
    闭集(买/刷/关/卖备战席)——席满置换/筹资为在产形态;店内购买
    经验整批已随升级转场退役(2026-10-17 迭代 T-1,发射位迁备战);
    闭集外类型(部署/卖场上/购买经验等店内禁做面)发射即红。"""
    strategy, sess, config = _FORM_FRAMES[case]()
    action = strategy.decide_shop_action()
    name = type(action).__name__
    assert name in _SHOP_ACTION_FACE, (
        f'{case} 首动作 {name} 越出商店期动作面闭集 '
        f'{sorted(_SHOP_ACTION_FACE)}(店内禁做面 = 卖场上/点消耗品/'
        '拖角色上阵,发射即策略面回退)')


@pytest.mark.parametrize('case', sorted(_SELL_FIRST_FORMS))
def test_bench_blocked_forms_sell_in_shop(case: str):
    """席满/缺金形态的店内卖出测试:置换账(value 比较)与恒买豁免
    (c1_make_room)与筹资(session_funding)首动作 = CwActionSellBenchParam,
    「关店→备战卖→重开」腾位链废止——帧内一步完成,不再产生
    wanted 残差跨段状态(S2 机器退役)。"""
    strategy, sess, config = _FORM_FRAMES[case]()
    action = strategy.decide_shop_action()
    assert type(action).__name__ == 'CwActionSellBenchParam', (
        f'{case} 席满/缺金形态首动作 {type(action).__name__} 非店内卖出'
        '(置换账/筹资/恒买腾位未接产)')
    assert action.reason in ('shop_swap', 'session_funding', 'c1_make_room'), \
        action.reason
    # (原 wanted 残差断言已随 S2 字段族退役删除——批 3.7 死码清理,
    #  会话循环无跨段残差形态。)


def test_vacate_chain_reopen_keeps_shop_face_and_buys():
    """牌面持久契约测试(置换形态;承继 research/economy.md §2.1):同一
    session/同一店面 payload 下:席满帧置换卖出(bench 移除一件,
    店面 payload 不动)→ 下帧重判,原缺员件在店且被买入。牌面若被
    卖出/重开刷新(跨节点语义误用到节点内),缺员件不在店,本测试红。"""
    strategy, sess, config = _frame_m4_missing_vacate()
    act1 = strategy.decide_shop_action()
    assert type(act1).__name__ == 'CwActionSellBenchParam'
    gs = game_state_of(sess)
    # 置换卖出的落地建模:bench 移除被卖槽(逻辑态直写,同容器转移
    # 函数通道);店面 payload 与 gold/缺员语境全不动。
    kept_idx = act1.bench_idx
    slots = list(gs.bench.value.slots)
    slots[kept_idx] = BenchSlot(kind='empty')
    gs.write_logic(gs.bench, BenchView(slots=slots, capacity=9),
                   produced_by='cw-36-test', sig=_FACE_LOGIC_SIG)
    # 卖出上报(筹资/置换卖出分支的容器投影;回金入账面)
    gs.write_logic(gs.gold, gs.gold.value + (action_income(act1) or 0),
                   produced_by='cw-36-test', sig=_FACE_LOGIC_SIG)
    state_of(sess).gold_ledger = gs.gold.value
    act2 = strategy.decide_shop_action()
    assert type(act2).__name__ == 'CwActionBuyCardParam', (
        f'腾位后未恢复买入(得 {type(act2).__name__})= 牌面持久被破坏'
        '或置换链断')
    assert act2.card.name == _MEMBER, (
        f'腾位后买入 {act2.card.name!r} 非原在店缺员件 = 牌面被刷新'
        '(跨节点自动刷新语义误用到节点内)')


def action_income(act) -> int:
    """卖出动作的预期回金(income 记录字段;未标 = 0 保守)。"""
    return int(getattr(act, 'income', 0) or 0)


def test_funding_hold_fallback_records_opportunity():
    """筹资兜底分支②拒形态:核心件持有账 > 0 → 不卖;该牌进未消费机会
    清单(拦因 = 金不足),收工关店(读数协议 §4.2 清单闭环)。"""
    strategy, sess, config = _frame_funding_hold_fallback()
    action = strategy.decide_shop_action()
    assert type(action).__name__ == 'CwActionCloseShopParam'
    st = state_of(sess)
    ct = st.cw4_counters
    assert ct.get('session_funding_exhausted', 0) >= 1, \
        '筹资候选穷尽分键缺席(兜底分支②拒后应记录)'
    recs = st.shop_opportunities
    assert any(r.card_name == _MEMBER and r.blocked_by == 'gold_short'
               for r in recs), \
        f'金不足机会清单记录缺席:实际 {recs}'
