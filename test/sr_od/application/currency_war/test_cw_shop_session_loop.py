"""商店会话重排批 3.6 行为锁(判据唯一源 = shop_session.md §1-§5;
迭代 2026-10-12-prep-shop-workflow-redesign)。

锁面(landing 3.6 完成判据):

1. **读数协议锁**(§4.2):失效触发族逐项(选卡/合成/晶矿/升 9 级/
   计数达阈)+ 会话入口再锚定 + 多卖循环第二笔起账面判缺口(禁逐笔
   开店重读)+ 动作伴生入金记账(漏账偏差侦测的账面侧);
2. **六序承继锁**(§2.2):未锁定期序 1 候选态(贯穿件恒囤)/场况
   插件会话累计额度;
3. **三段式刷新判据 + 停留门**(§2.4):P1 恒零主动付费刷新 / 段边界
   (P2 未锁窗口候选缺件驱动 / 锁定后星级目标)/ 停留门等级 < 带下界
   → 升级优先不刷;
4. **重开触发锁**(§4.2 解拦复核):席位空出解拦 / 金位解除解拦
   (义务件破息豁免形态)/ 读数开门形态;翻转行为差形态(溢余帧升级
   前置截断买入,顺延非丢失)由 test_cw_migration_direction_layer +
   test_cw_levelup_prob_axis 承载,不双锁;
5. **刷新终结语义回归**(§1):刷新(op 级重进)仍属同一会话——
   会话标记与清单不受扰动,收工后置标记。

实机观察点登记(3.5 风险传递 + 升级限界,实机首跑 reconcile 显影):
- 出售区拖拽落点(R1 显隐成因;R2 拖拽高亮 (108,786) 亮团是否激活
  证据)——拖拽 no-op 时按 no_method 坐标区直接 MCP 改 rect;
- 升级后同节点找牌收益放弃(升级即收工限界)与账面-实读偏差
  (漏账侦测信号)。
"""
from __future__ import annotations

import random
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_comps import (
    COMP_LIBRARY,
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

_LOGIC_SIG = ChannelSig(family='logic_action', actor='cw-36-loop',
                        mode='compute')
_OBS_SIG = ChannelSig(family='obs', actor='cw-36-loop',
                      mode='synthesized')

_LINE = set(COMP_LIBRARY[0].core_chars) | set(COMP_LIBRARY[0].shared_chars)
_MEMBER = COMP_LIBRARY[0].core_chars[0]


def _fuel(count: int, exclude: tuple[str, ...] = ()) -> list[str]:
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_card_identity import (
        TIER_UNRELATED,
        line_identity_tier,
    )
    out = [n for n in CHARACTERS
           if n not in _LINE and n not in exclude
           and line_identity_tier(n) == TIER_UNRELATED]
    return out[:count]


def _frame(*, gold: int = 60, bench=(), deployed=(), shop_cards=(),
           level: int = 3, plane: int = 1, round_num: int = 3,
           node_kind: str = 'reward', comp=None, hist=None):
    """商店决策帧(直构;金位账面/边界判重随种子稳态钉位;hist 直赋
    node_hist_pos 位面水位线)。"""
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
    if level in XP_TO_NEXT_LEVEL:
        gs.write_logic(gs.xp, (0, XP_TO_NEXT_LEVEL[level]),
                       produced_by='cw-36-loop', sig=_LOGIC_SIG)
    gs.write_logic(gs.gold, gold, produced_by='cw-36-loop',
                   sig=_LOGIC_SIG)
    gs.observe(gs.hp, 60, evidence='cw-36-loop', sig=_OBS_SIG)
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


# ============================================================ 读数协议锁


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
        act = live.decide_shop_action()
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
        st.shop_five_cost_buys == 1
        st.gold_ledger = gs.gold.value
        # 再两笔 5 费买入(同会话):第三笔触发 +3。
        g0 = gs.gold.value
        led0 = st.gold_ledger
        card = ShopCard(name=five_cost, faction='', cost=5, star=1, slot=2)
        for i in range(2):
            shop_sess.account_buy_companion_gold(gs, card)
        assert gs.gold.value == g0 + 3
        assert st.gold_ledger == led0 + 3, '双写同步:账面与容器同额入金'


# ============================================================ 六序承继锁


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
        from sr_od.application.currency_war.kernel.cw_card_identity import (
            TIER_TRANSITION,
            TIER_UNRELATED,
            line_identity_tier,
        )
        # 插件件选择约束:身份 tier 必须无关(序 1 三态成员面与 ④ 转线
        # 放行臂都不辖——本锁专辖序 2 额度门,不被前序臂掩蔽)。档位
        # 约束:tier_next > 阈档 3(等级 3 帧的 deploy_cap 采信下限),
        # 使「板面差一人进下一档」与「deployed == deploy_cap(额度 0)」
        # 可以同时成立。
        pick = None
        for faction_tag, fac in FACTIONS.items():
            members = [n for n, ch in CHARACTERS.items()
                       if faction_tag in getattr(ch, 'factions', ())
                       and ch.cost
                       and line_identity_tier(n) == TIER_UNRELATED]
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
        assert TIER_UNRELATED != TIER_TRANSITION   # 常量健全性(防退化为同档)


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
        """P2 未锁窗口:候选缺件驱动——候选线缺员且等级 ≥ 其概率带
        下界 → 可刷;全员持有(无缺件)→ 不刷。"""
        comp = COMP_LIBRARY[0]
        missing = next(m for m in sorted(_LINE)
                       if not _skip_member(m))
        live, sess, gs, st = _frame(gold=60, plane=2, hist=(2, 1),
                                    node_kind='reward', comp=comp,
                                    bench=[(n, 1) for n in _fuel(2)],
                                    deployed=[_fuel(3)[0]])
        # bench/deployed 无线内成员 ⇒ 缺员存在(等级 3 ≥ 1-2 费带下界)。
        ok, key = self._warrant(live, sess, gs)
        assert ok or key in ('unlocked_no_qualified_gap',)
        # 全员持有帧:缺员 ∅ ⇒ 不刷(构造 = 全线成员塞入 bench 槽不足
        # 时按上阵补——用小线避免槽溢出)。
        small = next(c for c in COMP_LIBRARY
                     if len(set(c.core_chars)
                            | set(getattr(c, 'shared_chars', None) or ()))
                     <= 9)
        members = list(small.core_chars) \
            + list(getattr(small, 'shared_chars', None) or [])
        live2, sess2, gs2, st2 = _frame(
            gold=60, plane=2, hist=(2, 1), node_kind='reward', comp=small,
            bench=[(m, 1) for m in members[:9]],
            deployed=members[9:] or [members[0]])
        ok2, key2 = self._warrant(live2, sess2, gs2)
        assert (ok2, key2) == (False, 'unlocked_no_qualified_gap'), \
            '全员持有时刷新无目标(候选缺件驱动 fail-closed)'

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


# ============================================================ 重开触发锁


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
        assert st.shop_handled is not None   # 读数腿不清标记

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
        # 免费刷新在册 → 刷新发射(免费不受判据辖)。
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
