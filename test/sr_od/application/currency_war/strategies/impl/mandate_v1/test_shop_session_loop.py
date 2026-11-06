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
    mark_shop_randomized_pending,
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
           if n not in _LINE and n not in exclude]
    return out[:count]


def _frame(*, gold: int = 60, bench=(), deployed=(), shop_cards=(),
           level: int = 3, plane: int = 1, round_num: int = 3,
           node_kind: str = 'reward', comp=None, hist=None,
           hp: int = 60, actives: tuple = (), xp: tuple | None = None,
           candidates: tuple = (), direction: bool = True):
    """商店决策帧(直构;金位账面/边界判重随种子稳态钉位;hist 直赋
    node_hist_pos 位面水位线;hp/actives/xp 供资格门逐道用例构帧;
    candidates = 候选快照线名;direction=False = 无方向帧,未锁口径)。"""
    sess = StrategySession(rng=random.Random('cw-36-loop'))
    st = state_of(sess)
    st.cw4_counters = {}
    st.target_comp = (COMP_LIBRARY[0] if comp is None and direction
                      else comp)
    st.line_candidates = tuple(candidates)
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
        """多卖循环第二笔起账面判缺口(§4.2 协议④):让位序列逐笔卖出
        期间零开店动作(禁逐笔重读;统一获取让位卖到缺口闭合——阶段 3
        起原 session_funding 取用并入 acquire_swap 键族,reason 同款
        统一为 'shop_swap')。
        构帧 = 板满(场前排 3 件铺满 cap):备战位燃料件全部为部署外
        (统一序列前置 = 部署重排定型,空位帧备战件会被 M1 补位收进
        部署需要面而整体 sheltered,筹资无候选)。"""
        pool = _fuel(6)
        live, sess, gs, st = _frame(gold=1, node_kind='reward',
                                    bench=[(n, 1) for n in pool[3:]],
                                    deployed=pool[:3],
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
        assert len(sells) >= 2 and sells[0].reason == 'shop_swap', \
            '统一获取让位收编后取用 reason = shop_swap(旧 session_' \
            'funding 键停产)'
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

    def test_unlocked_cross_line_keep_not_in_obligation_face(self):
        """万金油退出义务买入面(统一让位优先级迭代 3.4,总纲 §2.7 申报②;
        原「贯穿件恒囤层序 1 买入」测试随万金油项删除改判):空窗帧的
        万金油件(三月七)不走序 1 义务买(m2_* 买因不复现)——手里持有
        的未到两星前受万金油层档 8 保护(旧八档档 6,十档口径 =
        完成品保护迭代 design §2.2)、无自动补货通道;若被其他结构臂
        (序 4 垫件补位等)买入,买因为非义务臂。"""
        live, sess, gs, st = _frame(
            gold=60, node_kind='reward', comp=None,
            bench=[(n, 1) for n in _fuel(2)],
            deployed=[_fuel(3)[0]],
            shop_cards=[('三月七', 5, 1)])
        st.target_comp = None   # 空窗:候选空
        act = live.decide_shop_action()
        if isinstance(act, CwActionBuyCardParam) and act.card.name == '三月七':
            assert not act.reason.startswith('m2_'), \
                f'万金油件经义务面买入(3.4 申报②失效): {act.reason}'

    def test_scene_plugin_budget_cap(self):
        """场况插件会话累计额度(§2.2 序 2):额度 = 会话开始帧
        deploy_cap − deployed 快照;额度尽即停(被拦插件不进机会清单
        ——上阵空位非节点内可解除资源)。"""
        from sr_od.application.currency_war.data.cw_chars import CHARACTERS
        from sr_od.application.currency_war.data.cw_factions import FACTIONS
        # 插件件选择约束:身份必须非线内(序 1 义务面不辖——本测试专辖
        # 序 2 额度门,不被前序臂掩蔽;核心/保护身份规避面已随统一让位
        # 优先级迭代 3.4 退役)。档位约束:
        # tier_next > 阈档 3(等级 3 帧的 deploy_cap 采信下限),使
        # 「板面差一人进下一档」与「deployed == deploy_cap(额度 0)」
        # 可以同时成立。
        pick = None
        for faction_tag, fac in FACTIONS.items():
            members = [n for n, ch in CHARACTERS.items()
                       if faction_tag in getattr(ch, 'factions', ())
                       and ch.cost
                       and n not in _LINE]
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
        # (换轴后过渡层键域 = 见即买并集〔点名集〕,仙舟凑数件退出线内
        # 集合——dominance 邻位通道(1★ 全额退净成本 0,自有金/席门)
        # 对同名件放行为现行为,断言收窄到场况插件通道本身。)
        assert not (isinstance(act, CwActionBuyCardParam)
                    and act.card.name == plugin
                    and act.reason == 'scene_plugin_buy'), \
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
        """金不足收工(阶段 3 分键后形态):金 < 价 ∧ 让位池无可行件
        (板上件 ∈ 部署定型档 1 不入池,X 自己 = 排序末位)→ 记录
        priority_insufficient_gold 机会清单(带三字段解拦载荷)+ 收工
        关店(§4.2 清单闭环的写入端;roster-plane1-union design §2.2
        第 4 项步 6 分键)。"""
        act = live.decide_shop_action()
        assert isinstance(act, CwActionCloseShopParam), act
        rec = next((r for r in st.shop_opportunities
                    if r.card_name == name), None)
        assert rec is not None and \
            rec.blocked_by == 'priority_insufficient_gold', \
            f'金不足机会清单记录缺席/分键失真: {st.shop_opportunities}'
        assert rec.gold_snapshot is not None and rec.gold_gap is not None \
            and rec.shelf_signature is not None, '解拦分轴三字段缺失'
        assert st.shop_handled is not None
        return act

    # (席位空出解拦的六步流程形态测试 = shop/test_acquire_swap.py 的
    # test_priority_insufficient_unblocks_on_seat_freed——bench_full 拦因
    # 写端已随置换账替换退役(3.2),新拦因 priority_insufficient 的
    # 解拦复核分支在该专测承载;本类保留金位解除/读数开门两形态——
    # 阶段 3 起金不足语境记录 priority_insufficient_gold,解拦轴 =
    # 金位增量 ≥ 缺口绝对值,同帧内验证。)

    def test_gold_released_reopens_session(self):
        """金位解除解拦(义务件破息豁免形态):金不足记录 + 账面相对
        记录快照增量 ≥ 缺口绝对值 → 解拦(义务类金不足入清单合法,
        解拦购买允许破息;阶段 3 分轴 = priority_insufficient_gold
        的金位增量轴)。"""
        live, sess, gs, st = _frame(gold=1, node_kind='reward',
                                    bench=[],
                                    deployed=[_fuel(3)[0]],
                                    shop_cards=[(_MEMBER, 3, 1)])
        self._close_with_gold_short(live, sess, gs, st,
                                    name=_MEMBER, price=3)
        # 账面增量 1(2 − 1) < 缺口 2:不解拦。
        st.gold_ledger = 2
        assert entry._step4_shop_session_pending(sess, gs) is False
        # 节点收入进账(账面 4:增量 3 ≥ 缺口 2):解拦。
        st.gold_ledger = 4
        gs.write_logic(gs.gold, 4, produced_by='cw-36-loop',
                       sig=_LOGIC_SIG)
        assert entry._step4_shop_session_pending(sess, gs) is True

    def test_gold_short_stale_ledger_read_opens(self):
        """读数开门形态(路径③):金不足类记录在场 ∧ 账面失效 → 第 4 步
        开店读金(标记不动——锚定后标记门即关,下帧复核继续;
        priority_insufficient_gold 与 gold_short 同走 need_gold_read)。"""
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

    def test_signature_axis_drops_on_new_face(self):
        """签名轴(阶段 3 重开店帧首评;S7-5——关门态读不到货架,签名
        对比在开店后首帧):priority_insufficient_gold 记录的货架签名
        ≠ 当前牌面(刷新/换货架)→ 记录销项(新货架必重评,买入臂照常
        自评);签名相同 → 记录保持。"""
        live, sess, gs, st = _frame(gold=1, node_kind='reward',
                                    bench=[],
                                    deployed=[_fuel(3)[0]],
                                    shop_cards=[(_MEMBER, 3, 1)])
        self._close_with_gold_short(live, sess, gs, st,
                                    name=_MEMBER, price=3)
        # 同货架重进(刷新重进/读数重开形态):签名相同 → 记录保持。
        st.cw4_segment_serial += 1
        live.decide_shop_action()
        assert any(r.card_name == _MEMBER
                   and r.blocked_by == 'priority_insufficient_gold'
                   for r in st.shop_opportunities), \
            '同货架帧签名轴不得销项'
        # 新货架形态(节点边界后新牌面;此处以签名字段不等模拟换货架
        # ——轴语义 = 签名对比现读):记录销项。
        from dataclasses import replace
        _kept = tuple(
            replace(r, shelf_signature=('别的牌面',))
            if r.blocked_by == 'priority_insufficient_gold' else r
            for r in st.shop_opportunities)
        st.shop_opportunities = _kept
        dropped = shop_sess.shop_recheck_face_signature(gs)
        assert dropped >= 1, f'新货架签名轴应销项: {dropped}'
        assert not [r for r in st.shop_opportunities
                    if r.blocked_by == 'priority_insufficient_gold']


# ============================================================ 升级意图出口
# (迭代 2026-10-17-levelup-shop-transition design §2.1 出口 + 凑金链
# 整删收敛:商店会话不执行店内升级——命中 ∧ 可发射 → 关店转场不置
# 标记;金不足(恒 defer)/未命中 → None 会话继续;资格门逐道拒因
# 已登记。)


class TestUpgradeIntentExit:

    def _stay_frame(self, *, gold: int, level: int = 5,
                    hp: int = 60, actives: tuple = (),
                    xp: tuple | None = None):
        """停留门构帧:锁定线(列车同行·反震)+ 辅助达标(三月七 2★/瓦尔特
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
        商店未「事情办完」);转场计数已登记;零店内卖出/店内升级发射。"""
        live, sess, gs, st = self._stay_frame(gold=80)
        act = live.decide_shop_action()
        assert isinstance(act, CwActionCloseShopParam), act
        assert st.shop_handled is None, '转场关店不置 handled 标记'
        ct = st.cw4_counters
        assert ct.get('levelup_transition_close') == 1
        assert ct.get('levelup_trigger_stay_gate') == 1

    def test_hit_gold_short_returns_none_session_continues(self):
        """命中 ∧ 金不足(花后破线恒 defer)→ 检查返回 None,会话照常
        继续:停留门触发 ∧ 花后破线 → 资金线 defer 拒因已登记(资金面
        拒因统一键);会话走 §2.5 正常收工置标记(「等节点收入」形态
        成立),非转场关店。凑金链已整删(用户裁定 2026-10-30:不
        存在升级卖牌凑金,保持最大压牌库,钱够了再升)。"""
        live, sess, gs, st = self._stay_frame(gold=30)
        act = live.decide_shop_action()
        ct = st.cw4_counters
        assert ct.get('levelup_trigger_stay_gate') == 1
        assert ct.get('levelup_fund_line_defer') == 1, \
            '金不足帧资格门拒因已登记(资金线 defer 统一键)'
        assert ct.get('levelup_transition_close', 0) == 0, '金不足不转场'
        assert isinstance(act, CwActionCloseShopParam), act
        assert st.shop_handled is not None, \
            '金不足帧会话经正常收工置标记(出店→战斗→节点收入→资金线自然过线)'

    def test_gate_level_cap_frame_rejects(self):
        """资格门②等级帽帧:满级帧判据不发射(拒因已登记),会话照常
        收工置标记(正常收工,非转场)。"""
        live, sess, gs, st = _frame(gold=100, level=10, plane=1,
                                    node_kind='battle', shop_cards=[])
        act = live.decide_shop_action()
        assert st.cw4_counters.get('levelup_reject_level_cap') == 1
        assert st.cw4_counters.get('levelup_transition_close', 0) == 0
        assert isinstance(act, CwActionCloseShopParam)
        assert st.shop_handled is not None

    def test_gate_reward_frame_defers(self):
        """资格门①奖励帧抑制:奖励帧(非扑满环境)不发射(拒因已登记,
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
        拒因已登记);对照血足帧 → 可发射转场关店。构帧注:lv6 血批 =
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
        已登记),会话照常收工置标记。"""
        live, sess, gs, st = self._stay_frame(gold=80, xp=(20, 20))
        act = live.decide_shop_action()
        assert st.cw4_counters.get('levelup_zero_clicks_defer') == 1
        assert st.cw4_counters.get('levelup_transition_close', 0) == 0
        assert isinstance(act, CwActionCloseShopParam)
        assert st.shop_handled is not None


# ============================================================ 备战随机态重开位
# (迭代 2026-10-17-levelup-shop-transition design §2.2 第 1 步/§2.4:
# 信号宿主 = GameState 簿记槽 shop_randomized_pending(None = 无信号,
# 非 None = 带来源代次戳,迭代 2026-09-23-invest-effects-calc T-434);
# 写端 = 升级值变更回调经 mark_shop_randomized_pending 盖戳,读端 +
# 清位先行。)


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
        # 信号在(测试直种带代次戳的真值;生产写端 = 商业间谍升级回调经
        # mark_shop_randomized_pending 盖戳):重开位消费。
        session_scope.mark_shop_handled(gs)
        assert session_scope.shop_handled_for_current_node(gs)
        gs.shop_randomized_pending = (1, 3)
        out = entry.emit(sess, None)
        assert out and out[0].reason == 'step1_shop_randomized_reopen', out
        assert isinstance(out[0].action, CwActionOpenShopParam)
        assert st.shop_handled is None, '重开位清 handled 标记'
        assert gs.shop_randomized_pending is None, '重开位消费后清信号'
        assert st.cw4_counters.get('shop_randomized_reopen') == 1, \
            '重开触发计数键已登记(§2.6③ 随机态闭环取数口)'

    def test_node_boundary_sweeps_stale_generation_signal(self):
        """节点边界清扫(过期代次):信号戳 ≠ 当前生效序位 = 旧节点牌面
        语义死亡,边界函数清位(design §2.4 清位两出口之二;代次判据 =
        迭代 2026-09-23-invest-effects-calc T-434,真旧源清扫旧语义保持)。"""
        _live, _sess, gs, _st = _frame(gold=60, node_kind='reward',
                                       shop_cards=[])
        gs.shop_randomized_pending = (1, 3)   # 上一节点内置位未消费的戳
        gs.write_logic(gs.node, NodeKey(plane=1, round_num=4,
                                        kind='reward'),
                       produced_by='cw-36-loop', sig=_LOGIC_SIG)
        gs.observe(gs.node_pos, (1, 4), evidence='cw-36-loop',
                   sig=_OBS_SIG)
        session_scope.handle_node_boundary(gs)
        assert gs.shop_randomized_pending is None, '过期代次信号边界清位'

    def test_node_boundary_keeps_fresh_generation_signal(self):
        """来源代次锁(T-434):节点推进时点置位的新源(戳 = 当前生效序位;
        生产形态 = T-432 advance 尾排空置位,恰在进入新节点的同一次
        advance 内盖新节点戳)不被边界清扫清掉——清扫只清过期代次,新源
        信号保留交本帧重开位消费(守恒式重开腿对节点时点源恢复)。"""
        _live, _sess, gs, _st = _frame(gold=60, node_kind='reward',
                                       shop_cards=[])
        gs.write_logic(gs.node, NodeKey(plane=1, round_num=4,
                                        kind='reward'),
                       produced_by='cw-36-loop', sig=_LOGIC_SIG)
        gs.observe(gs.node_pos, (1, 4), evidence='cw-36-loop',
                   sig=_OBS_SIG)
        # 节点推进时点置位(生产写端盖戳路径,stamp = effective_node_pos)。
        mark_shop_randomized_pending(gs)
        assert gs.shop_randomized_pending == (1, 4), \
            '置位盖来源代次戳 = 当前生效节点序位'
        session_scope.handle_node_boundary(gs)
        assert gs.shop_randomized_pending is not None, \
            '新源信号(代次戳 = 当前序位)不被节点边界清扫清掉'


# ============================================================ 等钱帧刷新让位
# (资金序 = 升级优先于刷新:金不足帧的刷新让位由判据①支「升级优先」
# 直接承载——带互斥下升级触发态与刷新放行态天然分离;整级预留防御层已
# 随刷新链三组件批删除,凑金待付窗分支已随凑金链整删〔用户裁定
# 2026-10-30:不存在升级卖牌凑金,钱够了再升〕,本节测试 = 资金序
# 声明的行为面锁定。)


class TestLevelupReserveGuard:

    def test_gold_short_wait_frame_no_refresh(self):
        """等钱帧零刷新(升级资金不被刷新烧):带滞后触发 ∧ 花后破线
        (金 68,批 20,花后 48 < 线 50;bench 活期充足——原凑金可达域
        形态)→ 资格门 defer 已登记(levelup_fund_line_defer 统一键,
        待付窗分键 levelup_stockpile_wait 已停产);刷新判据带互斥
        不批(等级 < 带下界)→ 零刷新动作,会话正常收工置标记
        (「等节点收入」形态成立)。"""
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
        assert st.cw4_counters.get('levelup_fund_line_defer') == 1, \
            '花后破线帧 defer 已登记(资金面统一键——原凑金可达帧同形)'
        assert not isinstance(act, CwActionRefreshShopParam), \
            '等钱帧零刷新(升级资金完整性优先)'
        assert st.shop_handled is not None, \
            '等钱帧经正常收工置标记(资金线自然过线再发射)'

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
        assert st.cw4_counters.get('levelup_fund_line_defer', 0) == 0, \
            '带内帧无资金面拒因(verdict MISS 不经资金线门)'


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
        # 免费刷新已登记 → 刷新发射(免费腿同过目标可买检查——金线不适用;
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
    """非线内燃料名(注册表现算防漂移;核心/保护身份规避面已随统一让位
    优先级迭代 3.4 退役,非线内即可)。"""
    out = [n for n in CHARACTERS
           if n not in _LINE and n not in exclude]
    assert len(out) >= count, '非线内燃料名不足'
    return out[:count]


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


# (_frame_core_unlocked_vacate 恒买腾位形态帧已随 C1 支退役删除——
#  统一让位优先级迭代 3.4,C1 单卡核心囤积规则作废,dismantle §2。)


def _frame_interest_sell():
    """凑息回拉形态:金贴息线下、席不满、缺员件不在店 → 店内零凑息
    卖射(凑息 = 备战第 7 步接线),收工关店交回备战。"""
    return _frame_session(
        bench_units=_fuel_names(5),
        deployed_units=list(COMP_LIBRARY[0].core_chars[1:2]),
        card_names=[], gold=47)


def _frame_funding_support_sell():
    """金不足让位形态(主路径;阶段 3 语义):缺员在店 + 金不足 +
    bench 活期件在场 → 统一获取让位卖出(reason = shop_swap;凑够
    即买下一帧接手——原 session_funding 取用已并入 acquire_swap
    键族)。"""
    fuels = _fuel_names(8, exclude=(_fuel_names(1)[0],))
    return _frame_session(
        bench_units=fuels,
        deployed_units=_fuel_names(1),
        card_names=[(_MEMBER, 3)], gold=1, hp=10)


def _frame_funding_exhausted():
    """筹资穷尽形态:缺员在店 + 金不足 + bench 空仓(活期件全空)→
    候选穷尽 → 记录金不足机会清单收工(shop_session §2.3;P78-5 兜底
    豁免通道已随身份段退役删除——统一让位优先级迭代 3.4,本帧校验
    穷尽边界)。"""
    return _frame_session(
        bench_units=[],
        deployed_units=_fuel_names(1),
        card_names=[(_MEMBER, 3)], gold=1, hp=10)


_FORM_FRAMES = {
    'm4_missing_vacate': _frame_m4_missing_vacate,
    'm2_stockpile_vacate': _frame_m2_stockpile_vacate,
    'interest_pullback': _frame_interest_sell,
    'funding_support': _frame_funding_support_sell,
    'funding_exhausted': _frame_funding_exhausted,
}

#: 3.6 重排后的商店域动作面闭集(店内卖备战席启用;购买经验整批随
#: 升级转场退役——2026-10-17 迭代 T-1,升级执行位迁备战画面,
#: shop_session §1 店内动作边界)。
_SHOP_ACTION_FACE = {'CwActionBuyCardParam', 'CwActionRefreshShopParam',
                     'CwActionCloseShopParam', 'CwActionSellBenchParam'}

#: 席满买入两形态(席满六步流程置换/筹资)的首动作 = 店内卖出。
_SELL_FIRST_FORMS = {'m4_missing_vacate', 'm2_stockpile_vacate',
                     'funding_support'}


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
    """席满/缺金形态的店内卖出测试:席满置换(优先级末位让路)与
    金不足让位首动作 = CwActionSellBenchParam,「关店→备战卖→重开」
    腾位链废止——帧内一步完成,不再产生 wanted 残差跨段状态(S2 机器
    退役;阶段 3 起两形态取用 reason 统一 = shop_swap)。"""
    strategy, sess, config = _FORM_FRAMES[case]()
    action = strategy.decide_shop_action()
    assert type(action).__name__ == 'CwActionSellBenchParam', (
        f'{case} 席满/缺金形态首动作 {type(action).__name__} 非店内卖出'
        '(统一获取让位未接产)')
    assert action.reason == 'shop_swap', action.reason
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


def test_funding_exhausted_records_opportunity():
    """金不足穷尽形态(阶段 3 分键后语义):缺员在店 + 金不足 + 让位池
    无可行件(bench 空仓,板上件 ∈ 部署定型档 1 不入池 → X 自己 =
    排序末位)→ 放弃买入,该牌进未消费机会清单(拦因 =
    priority_insufficient_gold,带三字段解拦载荷),收工关店(读数协议
    §4.2 清单闭环;roster-plane1-union design §2.2 第 4 项步 6——旧
    session_funding 键族停产,池穷尽不可足的 gold_short 分键由
    shop/test_acquire_yield 的池穷尽用例承载)。"""
    strategy, sess, config = _frame_funding_exhausted()
    action = strategy.decide_shop_action()
    assert type(action).__name__ == 'CwActionCloseShopParam'
    st = state_of(sess)
    ct = st.cw4_counters
    assert ct.get('acquire_swap_declined', 0) >= 1, \
        '末位 = X 放弃分键缺席(统一获取让位拒绝应记录)'
    recs = st.shop_opportunities
    assert any(r.card_name == _MEMBER
               and r.blocked_by == 'priority_insufficient_gold'
               for r in recs), \
        f'金不足机会清单记录缺席:实际 {recs}'


# ============================================================
# 货架资格臂 + 冷启动臂(11 号稿 §1 序 1 扩展臂条款;
# 序 1 层内扩展臂):资格判据(CARRY 级 ∧ 虚拟
# top3)/义务类管线/子序(missing 后、冷启动次之、资格臂殿后)/双空窗
# 完备性(1 费三羁绊见即买,会话内现算退出);
# 过渡资格臂(语义权威版本 = strategy-docs/12_line_and_intention.md §3):
# 序 1 层内终局资格臂之后殿后——过渡组合计分域成员的虚拟 top3 资格,
# 触发窗 = 未终局锁定 ∧ 未过渡锁定,零持久化。
#
# 构帧纪律:未锁 + line_candidates/transition_candidates 双空(资格
# 判据的虚拟评估只作资格器,零持久化);货架件身份注册表现算防漂移
# (飞霄 = 追击飞霄 CARRY〔1 费非三羁绊〕;丹恒·饮月 = 龙丹战技点
# CARRY〔2 费三羁绊,非列车成员〕;刃 = 黄泉减益插件级〔1 费非三羁绊〕;
# 艾丝妲 = 纯过渡件〔1 费持续伤害,不在任何终局线〕;三月七 = 列车
# CARRY〔1 费列车同行〕;佩拉 = 希儿贝2 块计分域纯过渡件〔贝洛伯格,
# 全库无 carry 归属〕)。
# ============================================================


class TestShelfQualifyArm:
    """货架资格臂(单张买入估值;§2.2-2:虚拟评估作资格器,买入转实
    后整线跟进)。"""

    def test_carry_card_on_shelf_qualifies(self):
        """CARRY 触发:零持有开局 + 货架飞霄(追击飞霄 CARRY,1 费非
        三羁绊——冷启动域外)→ 虚拟评估(在手∪货架)追击飞霄证据非零
        进虚拟 top3 → 资格买入,reason = shelf_qualify_buy(义务类)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            sell_gate,
        )
        live, sess, gs, st = _frame(
            gold=60, node_kind='reward', direction=False,
            shop_cards=[('飞霄', 1, 1)])
        act = live.decide_shop_action()
        assert isinstance(act, CwActionBuyCardParam), f'非资格买入: {act!r}'
        assert act.card.name == '飞霄'
        assert act.reason == 'shelf_qualify_buy'
        assert sell_gate.launch_cause_of(act.reason) == 'obligation', \
            '资格臂 = 义务类(τ=∞ 义务账,§2.2-3)'

    def test_non_carry_card_on_shelf_does_not_qualify(self):
        """资格域外件不触发终局资格买入(反向):货架椒丘(原骨架级单卡,
        全库唯一无任何 CARRY 身份者——不在任何线的 carry_set)→ 虚拟
        top3 线的资格集(CARRY 级单源)不含椒丘 → 终局资格臂零对象;
        持有飞霄(追击锚)点亮实候选挡冷启动臂且椒丘 ∉ 追击成员域挡
        m2。椒丘的过渡侧身份(DOT2 计分域)由过渡资格臂独立承载——
        若发生买入,reason 不得是终局资格通道 shelf_qualify_buy。"""
        from sr_od.application.currency_war.kernel.cw_comps import (
            carry_set,
            get_comp,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            line_select,
        )
        _virt = line_select.compute_candidates(
            frozenset({'椒丘'}), line_select.OpeningCtx())
        assert all('椒丘' not in carry_set(get_comp(n)) for n in _virt), \
            f'帧前提失守:椒丘获得 CARRY 身份: {_virt!r}'
        live, sess, gs, st = _frame(
            gold=60, node_kind='reward', direction=False,
            bench=[('飞霄', 1)],
            shop_cards=[('椒丘', 1, 1)])
        act = live.decide_shop_action()
        if isinstance(act, CwActionBuyCardParam):
            assert act.reason != 'shelf_qualify_buy', \
                f'资格域外件(椒丘)不得触发终局资格买入: {act.reason}'

    def test_plugin_card_on_shelf_does_not_qualify(self):
        """插件不触发(同帧对照):货架 [刃(槽1,黄泉减益插件级),
        黄泉(槽2,黄泉减益 CARRY)]——黄泉减益经货架虚拟证据进虚拟
        top3,但刃只是插件级(members − CARRY)不入资格域 →
        槽序在前的刃被跳过,首资格件 = 黄泉(CARRY 触发)。"""
        live, sess, gs, st = _frame(
            gold=60, node_kind='reward', direction=False,
            shop_cards=[('刃', 1, 1), ('黄泉', 5, 1)])
        act = live.decide_shop_action()
        assert isinstance(act, CwActionBuyCardParam), f'非资格买入: {act!r}'
        assert act.card.name == '黄泉', \
            f'插件级刃(槽序在前)须被跳过,首资格件 = CARRY 黄泉: {act!r}'
        assert act.reason == 'shelf_qualify_buy'

    def test_line_outside_virtual_top3_does_not_qualify(self):
        """虚拟 top3 资格(线外不触发):货架四件(黑塔 = 大黑塔 core/
        姬子·启行 = 列车 anchor/符玄+花火 = 多线 core)——虚拟评估
        (在手∅∪货架)下 top3 = 列车 A(锚 8000+花火 4000+165)/列车 B
        (同证据+70,批 3 拆分双席)/第三席 = 火花星间(花火锚 8000+40)
        与希儿量子(双 core 8000+38)heat 微差之争(2 分差不锚定),
        大黑塔银河学者(黑塔 4000+38)恒落榜 → 黑塔(槽1)无资格
        被跳过,首动作 = 槽序内首个在榜资格件姬子·启行(A/B 共锚 CARRY)。
        前置断言 = 注册表演进使帧前提失守时响亮暴露(统一阵容评分后
        排序 = 数值单值和,锚档支配)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            line_select,
        )
        _face = {'黑塔', '姬子·启行', '符玄', '花火'}
        _virt = line_select.compute_candidates(
            frozenset(_face), line_select.OpeningCtx())
        assert '大黑塔银河学者' not in _virt, \
            f'帧前提失守:挤出线意外入虚拟 top3: {_virt!r}'
        assert '列车同行·反震' in _virt and '列车同行·直伤' in _virt, \
            f'A/B 双席(同 core 同证据,heat 差序): {_virt!r}'
        live, sess, gs, st = _frame(
            gold=60, node_kind='reward', direction=False,
            shop_cards=[('黑塔', 1, 1), ('姬子·启行', 3, 1),
                        ('符玄', 4, 1), ('花火', 2, 1)])
        act = live.decide_shop_action()
        assert isinstance(act, CwActionBuyCardParam), f'非资格买入: {act!r}'
        assert act.card.name == '姬子·启行', \
            f'虚拟 top3 外线的货架件(黑塔)须被跳过,首资格件 = 列车 anchor 姬子·启行: {act!r}'
        assert act.reason == 'shelf_qualify_buy'

    def test_missing_loop_precedes_qualify_arm(self):
        """子序(序 1 层内 missing 循环之后、资格臂殿后):实候选直种
        列车同行 + 持有部分成员(证据点亮)+ 货架 [花火(列车 CARRY,
        missing 件), 飞霄(资格件)] → 缺件循环先买花火
        (m2_line_member),资格件飞霄殿后不抢序。"""
        live, sess, gs, st = _frame(
            gold=60, node_kind='reward', direction=False,
            bench=[('姬子·启行', 1)], deployed=[],
            shop_cards=[('花火', 2, 1), ('飞霄', 1, 1)],
            candidates=('列车同行·反震',))
        act = live.decide_shop_action()
        assert isinstance(act, CwActionBuyCardParam), f'非买入: {act!r}'
        assert act.card.name == '花火', \
            f'missing 缺件(列车 CARRY 花火)须先于资格臂: {act!r}'
        assert act.reason.startswith('m2_'), \
            f'缺件循环通道(m2 族)先于资格臂殿后: {act.reason}'

    def test_qualify_buy_lights_real_candidates_next_frame(self):
        """买入转实链路(§2.2-2 闭环):资格买入飞霄 → 持有写入 → 方向
        签名变 → refresh 重算 → 实候选经证据门点亮追击飞霄 → 义务面
        跟进(下一帧货架追击线件知更鸟经 m2 义务通道买入)。"""
        live, sess, gs, st = _frame(
            gold=60, node_kind='reward', direction=False,
            shop_cards=[('飞霄', 1, 1)])
        act1 = live.decide_shop_action()
        assert act1.reason == 'shelf_qualify_buy'
        # 落地投影:买入写持有(bench 紧凑条目追加),签名变
        from sr_od.application.currency_war.kernel.cw_game_state import (
            BenchSlot,
            BenchView,
        )
        slots = list(gs.bench.value.slots) \
            + [BenchSlot(kind='unit', unit=Unit(char_id='飞霄', star=1))]
        gs.write_logic(gs.bench, BenchView(slots=slots, capacity=9),
                       produced_by='cw-36-loop', sig=_LOGIC_SIG)
        session_scope.refresh_line_if_needed(gs)
        assert '追击飞霄' in st.line_candidates, \
            '资格买入写持有 → 签名变 → 实候选经证据门点亮(§2.1-1 闭环)'
        # 下一帧:追击飞霄线件知更鸟在货架 → 义务面跟进(m2 通道)
        cards = [ShopSlot(kind='content',
                          card=ShopCard(name='知更鸟', faction='', cost=4,
                                        star=1, slot=1))]
        cards += [ShopSlot(kind='empty')] * 4
        gs.write_logic(gs.shop, ShopPayload(cards=cards, refresh_probs={}),
                       produced_by='cw-36-loop', sig=_LOGIC_SIG)
        st.cw4_segment_serial += 1
        st.shop_handled = None
        act2 = live.decide_shop_action()
        assert isinstance(act2, CwActionBuyCardParam), f'非义务买入: {act2!r}'
        assert act2.card.name == '知更鸟'
        assert act2.reason.startswith('m2_'), \
            '实候选点亮后整线义务面跟进(m2 义务通道;资格臂只作首件资格器)'

    def test_empty_shelf_degrades_to_close(self):
        """货架消失退化:空货架帧资格臂零对象(虚拟评估无货架面)→
        正常收工(无买入无异常)。"""
        live, sess, gs, st = _frame(
            gold=60, node_kind='reward', direction=False, shop_cards=[])
        act = live.decide_shop_action()
        assert isinstance(act, CwActionCloseShopParam), act


class TestColdStartArm:
    """冷启动臂(双空窗完备性;§2.3-8 键域改造:见即买并集 1 费 1★
    见即买,退出判据 = 候选槽形成〔与新计分同源〕;序位 = missing 后、
    资格臂前)。"""

    def test_dual_empty_window_buys_three_bond_one_cost(self):
        """双空窗触发:实候选空 ∧ 过渡候选空 ∧ 三羁绊现算全 0 + 货架
        艾丝妲(1 费 1★,持续伤害标签纯过渡件)→ 见即买,reason =
        cold_start_buy(义务类)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            sell_gate,
        )
        live, sess, gs, st = _frame(
            gold=60, node_kind='reward', direction=False,
            shop_cards=[('艾丝妲', 1, 1)])
        assert st.transition_candidates == ()   # 双空窗前置(未种槽)
        act = live.decide_shop_action()
        assert isinstance(act, CwActionBuyCardParam), f'非冷启动买入: {act!r}'
        assert act.card.name == '艾丝妲'
        assert act.reason == 'cold_start_buy'
        assert sell_gate.launch_cause_of(act.reason) == 'obligation'

    def test_candidate_slot_formed_stops_arm_within_session(self):
        """候选槽形成即停(换轴后退出判据,与新计分同源——旧「三羁绊
        支持度会话内现算」判据随体系对机器退役):持有艾丝妲(DOT2 块
        计分域成员)→ 过渡候选机器驱动后候选槽非空 → 冷启动停;
        货架三月七(1 费,冷启动域内件)不被冷启动买入——同帧它经
        资格臂(列车 CARRY + 虚拟 top3)买入,reason 通道分离即退出
        判据生效证据。"""
        from sr_od.application.currency_war.kernel.cw_intention import (
            IntentionState,
            update_transition_candidates,
        )
        live, sess, gs, st = _frame(
            gold=60, node_kind='reward', direction=False,
            bench=[('艾丝妲', 1)], deployed=[],
            shop_cards=[('三月七', 1, 1)])
        if st.v3_intention is None:
            st.v3_intention = IntentionState()
        update_transition_candidates(
            gs, st.v3_intention, st=st)   # 方向节拍贵段同参驱动(槽点亮)
        # 艾丝妲只在 DOT2 块域 → 含 DOT2 的组合同分 1,tie-break 注册序
        assert st.transition_candidates == (
            '仙舟3+DOT2', 'DOT2+列车2', 'DOT2+希儿量2'), '候选槽形成前置'
        act = live.decide_shop_action()
        assert isinstance(act, CwActionBuyCardParam), f'非买入: {act!r}'
        assert act.reason != 'cold_start_buy', \
            '候选槽形成即停冷启动(退出判据与新计分同源)'

    def test_cold_start_precedes_qualify_arm_in_order(self):
        """序位(missing 后、资格臂前):货架 [飞霄(槽1,资格件),
        艾丝妲(槽2,冷启动件)] 双空窗 → 冷启动先触发(序位在资格臂
        前),首动作买艾丝妲而非槽序在前的资格件飞霄。"""
        live, sess, gs, st = _frame(
            gold=60, node_kind='reward', direction=False,
            shop_cards=[('飞霄', 1, 1), ('艾丝妲', 1, 1)])
        act = live.decide_shop_action()
        assert isinstance(act, CwActionBuyCardParam), f'非买入: {act!r}'
        assert act.card.name == '艾丝妲', \
            f'冷启动臂须先于资格臂(槽序在前的飞霄不抢序): {act!r}'
        assert act.reason == 'cold_start_buy'

    def test_non_three_bond_card_not_bought_by_cold_start(self):
        """三羁绊限定:货架乱破(1 费非三羁绊——黄泉减益/巡海击破
        CARRY)→ 冷启动域外;乱破经其线虚拟 top3 资格(资格臂)买入,
        reason 通道分离即三羁绊限定证据(护盾/希儿系件同域外)。"""
        live, sess, gs, st = _frame(
            gold=60, node_kind='reward', direction=False,
            shop_cards=[('乱破', 1, 1)])
        act = live.decide_shop_action()
        assert isinstance(act, CwActionBuyCardParam), f'非买入: {act!r}'
        assert act.reason == 'shelf_qualify_buy', \
            '非三羁绊 1 费件不走冷启动(经资格臂通道=限定证据)'


class TestTransitionShelfQualifyArm:
    """过渡货架资格臂(语义权威版本 = strategy-docs/12_line_and_
    intention.md §3):过渡组合计分域成员的虚拟 top3 资格
    ——transition_scores(在手 ∪ 货架, 简报克制源)前 3 条组合的
    transition_member_set 并集 = 资格名单;触发窗 = 未终局锁定 ∧
    未过渡锁定;即算即用零持久化(虚拟结果不落候选槽,锁定域语义
    不受污染)。"""

    def _frame_seeded(self, *, bench=(('爻光', 1),), shop_cards=(('佩拉', 2, 1),)):
        """构帧 + 方向节拍驱动(持爻光 → 实候选槽点亮仙舟3 组合;
        佩拉 ∈ 希儿贝2 计分域但 ∉ 实候选并集——虚拟评估点亮的正是
        实候选看不见的差一张件)。"""
        from sr_od.application.currency_war.kernel.cw_intention import (
            IntentionState,
            update_transition_candidates,
        )
        live, sess, gs, st = _frame(
            gold=60, node_kind='reward', direction=False,
            bench=list(bench), deployed=[], shop_cards=list(shop_cards))
        if st.v3_intention is None:
            st.v3_intention = IntentionState()
        update_transition_candidates(gs, st.v3_intention, st=st)
        return live, sess, gs, st

    def test_transition_domain_member_on_shelf_qualifies(self):
        """资格买入:持爻光(仙舟3 块 1/3)+ 候选槽已点亮
        (方向节拍驱动后实候选 = 仙舟3 组合)+ 货架佩拉(希儿贝2 块
        计分域)→ 虚拟计分(在手∪货架)下仙舟3+希儿贝2 以 2 分居首
        进 top3 → 佩拉 ∈ 资格名单,义务类买入,reason =
        transition_shelf_qualify_buy。前置断言 = 佩拉 ∉ 实候选并集
        (虚拟评估点亮实候选看不见的牌——臂的存在理由);
        后置断言 = 零持久化(候选槽/过渡锁定态在资格评估帧后不变)。"""
        from sr_od.application.currency_war.kernel import cw_intention
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            sell_gate,
        )
        live, sess, gs, st = self._frame_seeded()
        assert st.transition_candidates == (
            '仙舟3+DOT2', '仙舟3+列车2', '仙舟3+希儿量2'), '构帧前置'
        assert '佩拉' not in cw_intention.transition_member_union(st), \
            '佩拉须在实候选并集外(否则经 m2 义务面买,测不到资格臂)'
        act = live.decide_shop_action()
        assert isinstance(act, CwActionBuyCardParam), f'非资格买入: {act!r}'
        assert act.card.name == '佩拉'
        assert act.reason == 'transition_shelf_qualify_buy'
        assert sell_gate.launch_cause_of(act.reason) == 'obligation', \
            '过渡资格臂 = 义务类(方向投资件 τ=∞ 义务账)'
        assert st.transition_candidates == (
            '仙舟3+DOT2', '仙舟3+列车2', '仙舟3+希儿量2'), \
            '零持久化:虚拟评估不得写候选槽'
        assert not st.v3_intention.transition_locked, \
            '零持久化:虚拟评估不得立过渡锁定'

    def test_shelf_card_outside_virtual_top3_not_bought(self):
        """虚拟计分域外不触发(反向):货架遐蝶(全库无羁绊块
        归属)∉ 任何虚拟 top3 组合计分域 → 过渡资格臂零买入(遐蝶若被
        买入只能是富余金兜底等其他通道;虚拟评估帧同样零持久化)。"""
        live, sess, gs, st = self._frame_seeded(
            shop_cards=[('遐蝶', 4, 1)])
        _cand = tuple(st.transition_candidates)
        act = live.decide_shop_action()
        assert not (isinstance(act, CwActionBuyCardParam)
                    and act.card.name == '遐蝶'
                    and act.reason == 'transition_shelf_qualify_buy'), \
            f'计分域外货架件不得经过渡资格臂买入: {act!r}'
        assert st.transition_candidates == _cand, '零持久化(未买路径)'

    def test_transition_locked_disarms_arm(self):
        """触发窗①:过渡锁定(transition_locked 非空)后
        买面 = 锁定条目成员域——资格臂的方向点亮语义与「锁后不换」
        互斥,佩拉(虚拟计分下仍资格)零行为。"""
        live, sess, gs, st = self._frame_seeded()
        st.v3_intention.transition_locked = '仙舟3+DOT2'
        act = live.decide_shop_action()
        assert not (isinstance(act, CwActionBuyCardParam)
                    and act.card.name == '佩拉'
                    and act.reason == 'transition_shelf_qualify_buy'), \
            f'过渡锁定帧资格臂不得发射: {act!r}'

    def test_final_lock_disarms_arm(self):
        """触发窗②:终局锁定 → 过渡层整体退役态,臂不触发。
        单变量构帧(终局锁 ∧ 过渡锁空):臂守卫是合取,叠加残留过渡锁
        会使断言对「实现漏写终局锁分量」的突变零分辨力(另一分量照样
        拦截)——过渡锁半边由 test_transition_locked_disarms_arm 单独
        钉住,本用例只验终局锁分量独立生效。生产链终局锁定写入点同点
        清空过渡层,位面切换不触发。"""
        live, sess, gs, st = self._frame_seeded()
        st.target_comp = COMP_LIBRARY[0]   # 终局锁定帧(target_comp 非空)
        assert not st.v3_intention.transition_locked, '构帧前置:过渡锁空'
        act = live.decide_shop_action()
        assert not (isinstance(act, CwActionBuyCardParam)
                    and act.card.name == '佩拉'
                    and act.reason == 'transition_shelf_qualify_buy'), \
            f'终局锁定帧资格臂不得发射: {act!r}'

    def test_final_qualify_arm_precedes_transition_arm(self):
        """并存序:同帧终局资格件(飞霄,槽 2)与过渡资格件
        (佩拉,槽 1)并存 → 终局臂先消费(臂序优先于货架槽序),
        首动作 = 飞霄 shelf_qualify_buy;两层信号互补不互斥。"""
        live, sess, gs, st = self._frame_seeded(
            shop_cards=[('佩拉', 2, 1), ('飞霄', 1, 1)])
        act = live.decide_shop_action()
        assert isinstance(act, CwActionBuyCardParam), f'非买入: {act!r}'
        assert act.card.name == '飞霄', \
            f'终局资格臂须先于过渡资格臂(槽序在前的佩拉不抢序): {act!r}'
        assert act.reason == 'shelf_qualify_buy'

    def test_triangle_third_piece_dual_qualification_routes_to_final(self):
        """铁三角例(双资格路由例):手握铁三角
        二人(爻光+丹恒·饮月)+ 货架第三点名件(藿藿)→ 虚拟计分下含
        仙舟3 块的组合条目以 3 分进 top3(过渡侧资格成立)∧ 终局侧
        双王圣杯在虚拟 top3(藿藿 ∈ 其 CARRY 域,终局侧资格
        亦成立)→ 双资格并存时终局臂先消费,买入 reason =
        shelf_qualify_buy——过渡资格臂是终局侧不点亮牌的追加面。"""
        from sr_od.application.currency_war.kernel.cw_comps import (
            carry_set,
            get_comp,
        )
        from sr_od.application.currency_war.kernel.cw_intention import (
            transition_scores,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            line_select,
        )
        _virt = frozenset({'爻光', '丹恒·饮月', '藿藿'})
        _t_top3 = transition_scores(_virt, ())[:3]
        assert all(n.startswith('仙舟3') for n, _s in _t_top3), \
            f'前置失守:含仙舟3 块组合未进虚拟 top3: {_t_top3!r}'
        _f_top3 = line_select.compute_candidates(
            _virt, line_select.OpeningCtx())
        _f_qual = set()
        for _n in _f_top3:
            _c = get_comp(_n)
            if _c is not None:
                _f_qual |= carry_set(_c)
        assert '藿藿' in _f_qual, \
            f'前置失守:终局虚拟 top3 未点亮藿藿: {_f_top3!r}'
        live, sess, gs, st = _frame(
            gold=60, node_kind='reward', direction=False,
            bench=[('爻光', 1), ('丹恒·饮月', 1)], deployed=[],
            shop_cards=[('藿藿', 1, 1)])
        act = live.decide_shop_action()
        assert isinstance(act, CwActionBuyCardParam), f'非买入: {act!r}'
        assert act.card.name == '藿藿'
        assert act.reason == 'shelf_qualify_buy', \
            f'双资格并存时终局臂先消费: {act!r}'


def test_opening_empty_buy_face_zero_m2_buys():
    """开局空买面(§2.6-1:零信号期义务面收窄):零持有双空窗 + 货架
    遐蝶(万敌单C 插件级——虚拟 top3 线在但插件级不获资格)→ 义务面
    空,序 1 全臂(missing/stockpile/m2b/冷启动/资格)零买入;若任何
    买入发生,reason 不得是义务/资格/冷启动通道。"""
    live, sess, gs, st = _frame(
        gold=60, node_kind='reward', direction=False,
        shop_cards=[('遐蝶', 4, 1)])
    act = live.decide_shop_action()
    if isinstance(act, CwActionBuyCardParam):
        assert not act.reason.startswith('m2_'), \
            f'空买面帧义务通道不得买入: {act.reason}'
        assert act.reason not in ('shelf_qualify_buy', 'cold_start_buy'), \
            f'插件级货架件不获资格/冷启动: {act.reason}'
