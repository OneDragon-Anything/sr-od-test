"""席满买入六步流程单帧测试(统一让位优先级迭代 3.2;店内置换账整段
替换,镜像 = mandate_v1/shop.py ``_acquire_swap``)。

规格单一源 = changes/2026-10-29-unified-priority/details/acquisition-
and-sell.md §2 + 总纲 §2.3:

- 快照 → 虚拟置牌 → 升星连锁模拟(同名同星计数场上+备战混合达 3
  合成、向三星推进、连锁到不再触发)→ ``select_deployment`` 部署定型
  → 部署外持牌按 ``priority.sell_order`` 排序(新牌 = 将获取旗标)→
  末位 = 新牌 → 放弃买入;末位 = 存量牌 → 卖旧(单动作契约:卖与买
  分两帧);
- 合成净释放备战位 → 无需让路直接买(总纲 §2.3 步骤 2);
- 拒绝语义 = 机会清单拦因改「优先级不足」(席位空出即失效,与席满类
  同轴解拦,criteria/shop_session ``shop_unblock_recheck``)。

构帧纪律:场上前排以互异高费干净名铺满 cap(统一序列前置 = 部署重排
定型,板满帧备战位件全部为部署外);bench/field 名字互异(档 1 按名
命中,同名会被部署需要面一并保护)。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc,
    cw4_card,
    cw4_gs,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_members as _members,
)

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_comps import (
    get_comp,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    CwActionCloseShopParam,
    CwActionSellBenchParam,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.priority import (
    TIER7_BOND_NAMES,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.protection import (
    CROSS_LINE_KEEP_NAMES,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    decide_shop_action,
)

_TARGET = '姬子·启行'   # 列车同行 need_star 3(3★ 追到底目标)
_LOGIC_SIG = ChannelSig(family='logic_action', actor='cw-acquire-swap',
                        mode='compute')
_OBS_SIG = ChannelSig(family='obs', actor='cw-acquire-swap',
                      mode='synthesized')


def _clean_fillers(count: int, exclude: set[str], *, min_cost: int = 2
                   ) -> list[str]:
    """互异高费干净名(注册表现查防漂移):非万金油/非 exclude/费用
    ≥ min_cost(Lv3+ 帧概率 0 = 让位序靠后;registry 核心规避面已随
    统一让位优先级迭代 3.4 退役——C1 支删除)。"""
    out: list[str] = []
    for n, c in CHARACTERS.items():
        if len(out) >= count:
            break
        if n in exclude or (c.cost or 0) < min_cost:
            continue
        if n in CROSS_LINE_KEEP_NAMES:
            continue
        out.append(n)
    assert len(out) >= count, f'测试前提:干净填充名不足({len(out)})'
    return out


def _same_cost_fillers(count: int, cost: int) -> list[str]:
    """互异同费干净名(同档帧构取;注册表现查防漂移):费用恰 = cost
    (同概率域同档,排序键仅差在手旗标)、非万金油/非档 7 羁绊——防
    跨档(档 6/7 键小于档 8,会让「末位 = 新牌」退化成跨档结论)。"""
    out: list[str] = []
    for n, c in CHARACTERS.items():
        if len(out) >= count:
            break
        if (c.cost or 0) != cost or n in CROSS_LINE_KEEP_NAMES:
            continue
        ch = CHARACTERS[n]
        if (set(ch.factions) | set(ch.flows)) & TIER7_BOND_NAMES:
            continue
        out.append(n)
    assert len(out) >= count, f'测试前提:同费干净名不足({len(out)})'
    return out


def _frame(bench: list[tuple[str, int]],
           shop_cards: list[tuple[str, int, int]], *,
           locked_comp=None, recipe_comp=None, candidates: tuple = (),
           gold: int = 30, level: int = 7):
    """席满帧(备战 9/9;场前排铺满 cap;双宿主状态同源接线)。
    locked_comp/recipe_comp 接受线名(注册表解析为 Comp 对象落槽)。"""
    sess = StrategySession()
    st = state_of(sess)
    st.cw4_counters = {}
    st.v3_intention = IntentionState()
    st.target_comp = get_comp(locked_comp) \
        if isinstance(locked_comp, str) else locked_comp
    st.opening_recipe_comp = get_comp(recipe_comp) \
        if isinstance(recipe_comp, str) else recipe_comp
    st.line_candidates = tuple(candidates)
    held_names = {n for n, _s in bench}
    members: set[str] = set()
    for comp in (locked_comp, recipe_comp, *candidates):
        if comp:
            members |= set(_members(get_comp(comp) if isinstance(comp, str)
                                    else comp))
    exclude = members | held_names | {'绯英'}
    fillers = _clean_fillers(level, exclude)
    gs = cw4_gs(sess, plane=1, round_num=3, node='battle',
                gold=gold, level=level, hp=80, deploy_cap=level,
                bench=[cw4_bc(n, star=s) for n, s in bench],
                front_row=[Unit(char_id=n, star=1) for n in fillers],
                shop=[cw4_card(n, cost=c, star=s, x=i)
                      for i, (n, c, s) in enumerate(shop_cards)])
    # 节点位观察(收工位 mark_shop_handled 的写入前提 = 生效节点号可读;
    # 未观察 = no-op,会话标记不落,解拦复核面失锚)。
    gs.observe(gs.node_pos, (1, 3), evidence='cw-acquire-swap',
               sig=_OBS_SIG)
    gs.strategy_state = st   # 宿主归一:session_scope 族与判据读口同源
    return gs, sess, SimpleNamespace(ev_arm='full')


class TestAcquireSwapSixStep:
    """席满买入六步流程(3.2;置换账替换后的三帧判据)。"""

    def test_missing_member_sells_tail_junk(self):
        """置换成功帧:席满 + 方向缺件绯英在店 → 六步流程卖序列末位
        存量牌(卖旧 → 下帧重入买入,单动作契约);绯英 = 未持有配方
        成员(档 3,序列保护面)永不入让位末位。"""
        recipe = get_comp('绯英欢愉')
        junk = _clean_fillers(9, {'绯英'})
        gs, sess, cfg = _frame(
            bench=[(n, 1) for n in junk],
            shop_cards=[('绯英', 2, 1)],
            recipe_comp=recipe)
        act = decide_shop_action(gs, sess, cfg)
        assert isinstance(act, CwActionSellBenchParam), f'非卖旧动作: {act!r}'
        assert act.reason == 'shop_swap'
        assert act.expect != '绯英' and act.expect in junk, \
            f'让位件非存量杂件: {act.expect!r}'
        ct = state_of(sess).cw4_counters
        assert ct.get('acquire_swap_sell') == 1
        # 取用观测键(统一让位优先级迭代 3.5;键表 = telemetry/schema.py
        # 键表节):档位分布恰一落账(尾牌 = 干净杂件,档 7/8 由注册表
        # 羁绊归属定——断言计数和,不钉死注册表事实的档号);键互异帧
        # 随机尾键命中不落账。
        assert sum(v for k, v in ct.items()
                   if k.startswith('acquire_swap_sell_tier_')) == 1
        assert not ct.get('acquire_swap_sell_rng_tail_hit')
        assert not ct.get('acquire_swap_declined')

    def test_tail_is_new_card_declines_buy(self):
        """末位 = 新牌放弃帧(M6 臂承载;统一让位优先级迭代 3.4 后语义):
        席满持牌全为缺口成员(档 2)+ 压牌库候选 = 档 4 追费件(优先级
        低于全部档 2 持牌 = 虚拟序列末位 = 新牌自己)→ 放弃买入零动作,
        记录「优先级不足」拦因,收工关店。(原万金油星期日帧已随万金油
        退出义务买入面退役——总纲 §2.7 申报②:序 1 不再评估万金油,
        拒绝语义改由 M6 臂 order_4 通道承载。)"""
        bench = [('姬子·启行', 1), ('姬子·启行', 1), ('三月七', 1),
                 ('三月七', 1), ('花火', 1), ('万敌', 1),
                 ('千冶·刃', 1), ('卡芙卡', 1), ('桑博', 1)]
        gs, sess, cfg = _frame(
            bench=bench,
            shop_cards=[('希儿', 3, 1)],
            candidates=('列车同行', '万敌单C', '专家桑博DOT'),
            gold=100)
        act = decide_shop_action(gs, sess, cfg)
        assert isinstance(act, CwActionCloseShopParam), f'非收工: {act!r}'
        ct = state_of(sess).cw4_counters
        assert ct.get('acquire_swap_declined', 0) >= 1
        assert not ct.get('acquire_swap_sell'), \
            '末位 = 新牌帧不得发出卖旧(拒绝语义)'
        assert any(r.card_name == '希儿'
                   and r.blocked_by == 'priority_insufficient'
                   for r in state_of(sess).shop_opportunities), \
            f'优先级不足机会清单缺席: {state_of(sess).shop_opportunities}'

    def test_same_tier_stock_card_declines_in_hand_priority(self):
        """同档压库牌不换手帧(总纲 §2.10 第三断言:让位对象正确 =
        在手优先维度生效):席满持牌与店内压库候选同费同星(全池落档 8
        同概率域,排序键仅差在手旗标)→ 新牌 = 序列末位 → 放弃买入
        (同优先级不换手,priority-model §4)。跨档拒绝由上一测试承载,
        本帧把拒绝归因收窄到在手旗标单一维度——旗标缺失时等价牌群键
        前缀全同,随机尾键会随机换手(卖旧买同档 = 纯损耗)。"""
        junk = _same_cost_fillers(10, 1)
        gs, sess, cfg = _frame(
            bench=[(n, 1) for n in junk[:9]],
            shop_cards=[(junk[9], 1, 1)],
            gold=100)
        act = decide_shop_action(gs, sess, cfg)
        assert isinstance(act, CwActionCloseShopParam), f'非收工: {act!r}'
        ct = state_of(sess).cw4_counters
        assert ct.get('acquire_swap_declined', 0) >= 1
        assert not ct.get('acquire_swap_sell'), \
            '同档在手优先帧不得发出卖旧(不换手)'
        assert not ct.get('acquire_swap_sell_rng_tail_hit'), \
            '店牌已被在手旗标区分出等价牌群,随机尾键不参与末位判定'
        assert any(r.card_name == junk[9]
                   and r.blocked_by == 'priority_insufficient'
                   for r in state_of(sess).shop_opportunities), \
            f'优先级不足机会清单缺席: {state_of(sess).shop_opportunities}'

    def test_priority_insufficient_unblocks_on_seat_freed(self):
        """优先级不足拦因 = 席满语境拦阻:席位空出后买入不再经六步
        (正常买入路径无优先级门)→ 解拦复核同席满类放行。(帧构造同
        上,M6 臂 order_4 通道承载拒绝语义。)"""
        bench = [('姬子·启行', 1), ('姬子·启行', 1), ('三月七', 1),
                 ('三月七', 1), ('花火', 1), ('万敌', 1),
                 ('千冶·刃', 1), ('卡芙卡', 1), ('桑博', 1)]
        gs, sess, cfg = _frame(
            bench=bench,
            shop_cards=[('希儿', 3, 1)],
            candidates=('列车同行', '万敌单C', '专家桑博DOT'),
            gold=100)
        act = decide_shop_action(gs, sess, cfg)
        assert isinstance(act, CwActionCloseShopParam)
        assert state_of(sess).shop_handled is not None
        # 席位未空出:复核不解拦。
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            entry,
        )
        assert entry._step4_shop_session_pending(sess, gs) is False
        # 备战腾席(bench 移除一件)→ 优先级不足记录随席满语境失效 → 解拦。
        from sr_od.application.currency_war.kernel.cw_game_state import (
            BenchSlot,
            BenchView,
        )
        slots = list(gs.bench.value.slots)
        slots[0] = BenchSlot(kind='empty')
        gs.write_logic(gs.bench, BenchView(slots=slots, capacity=9),
                       produced_by='cw-acquire-swap',
                       sig=_LOGIC_SIG)
        assert entry._step4_shop_session_pending(sess, gs) is True
        assert state_of(sess).shop_handled is None

    def test_merge_frees_seat_buys_directly(self):
        """升星释放免让路帧:锁定追 3★(姬子 2★×2 在席)+ 店内 2★ 姬子
        → 虚拟置入合成 3★ 净释放备战位 → 无需让路直接买(总纲 §2.3
        步骤 2;发射器 = 臂内正常买入,登记族语义随臂)。"""
        junk = _clean_fillers(7, {_TARGET, '瓦尔特', '三月七', '花火'})
        bench = [(_TARGET, 2), (_TARGET, 2)] + [(n, 1) for n in junk]
        gs, sess, cfg = _frame(
            bench=bench,
            shop_cards=[(_TARGET, 3, 2)],
            locked_comp='列车同行')
        act = decide_shop_action(gs, sess, cfg)
        assert isinstance(act, CwActionBuyCardParam), f'非直买: {act!r}'
        assert act.card.name == _TARGET
        # 缺件臂买因按 k_members 命中分叉(姬子 ∈ 锁定线名单 →
        # m2_line_member);锁定/未锁分支的臂语义本体不在本测试面。
        assert act.reason in ('m2_line_member', 'm2_locked_member')
        ct = state_of(sess).cw4_counters
        assert ct.get('acquire_swap_merge_free_buy') == 1
        assert not ct.get('acquire_swap_sell'), \
            '合成净释放帧不得让路(直接买语义)'
