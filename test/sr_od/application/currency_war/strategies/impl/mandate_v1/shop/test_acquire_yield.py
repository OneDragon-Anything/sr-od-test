"""统一获取让位评估单帧测试(roster-plane1-union design §2.2 第 4 项;
镜像 = mandate_v1/shop.py ``_acquire_yield``——原席满买入六步流程与
会话内筹资两路合一,触发 = 获取受阻于「备战席满 ∨ 金 < 费用」任一或
叠加)。

规格单一源 = changes/2026-10-30-roster-plane1-union/design.md §2.2
第 4 项(评估步骤 1-6/金币要求集三项/拦因分键/victim 落位分流/写端
载荷)+ §2.3 获取驱动让位表:

- 快照 → 虚拟置牌 + 升星连锁 → 部署定型 → 部署外件全集按
  ``priority.sell_order`` 排序(新牌 = 将获取旗标)→ victim 试探
  (末位起前缀增长):末位 = 新牌 → 放弃分键;victim = 存量 → 按
  落位分流(bench 件店内卖 / 场上件跨画面计划 + 关店不置标记);
- 虚拟金币 = gold − cost(X) + Σ前缀退金;金币要求集三项(可购性/
  饱和线重放/凑息纪律判类门单一承载);
- 池穷尽不可足 → 机会清单(gold_short)。

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


# ============================================================
# 统一获取让位评估(阶段 3:金不足并入;roster-plane1-union design
# §2.2 第 4 项——虚拟阵容 + 虚拟金币 + 统一优先级单判据)
# ============================================================

_GIL, _SBR, _FUX = '吉尔伽美什', 'Saber', '符玄'
#: 场上 3 费杂件(档 8 内概率 0.2 > bench 件 → 场上件稳定让位序末位)。
_F3 = ('娜塔莎', '姬子·启行', '刻律德菈', '镜流')
#: bench 杂件(5 费 ×7 + 4 费 ×1;档 8 概率 0/0.02 均低于场上 3 费)。
_B5 = ('流萤', '昔涟', '布洛妮娅', '云璃', '景元',
       '托帕&账账', 'Archer', '大黑塔')
#: 4 费垫件(≠ 升星目标实费档 → 落档 8;饱和线/池穷尽帧的让位垫件)。
_B4 = ('海瑟音', '火花', '长夜月', '波提欧', '大黑塔', '遐蝶')
#: 窗口关的跨线成员(锁定双王圣杯帧的上阵窗口适用范围全部挡——
#: 非锁定线成员 ∧ 终局库成员 ∧ 锁定线信号表无行 = 窗口未开)。
_WIN_BLOCKED = ('银枝', '翡翠', '知更鸟', '飞霄', '那刻夏', '不死途',
                '乱破', '忘归人', '波提欧')


def _frame_locked(bench: list, shop_cards: list[tuple[str, int, int]], *,
                  gold: int = 30, level: int = 5, front=(), back=(),
                  ist_locked: bool = True):
    """双王圣杯锁定帧(板上含杂件的板满形态;Saber 3★ 在 bench 触发
    换阵定型 → 场上杂件 = 部署外)。ist_locked=False 提供无锁定对照。"""
    from sr_od.application.currency_war.kernel.cw_game_state import Unit
    from sr_od.application.currency_war.kernel.cw_intention import (
        IntentionState,
    )
    sess = StrategySession()
    st = state_of(sess)
    st.cw4_counters = {}
    st.v3_intention = (IntentionState(locked_comp='双王圣杯')
                       if ist_locked else IntentionState())
    st.target_comp = get_comp('双王圣杯')
    gs = cw4_gs(sess, plane=1, round_num=3, node='battle',
                gold=gold, level=level, hp=80, deploy_cap=level,
                bench=bench,
                front_row=[Unit(char_id=n, star=1) for n in front],
                back_row=[Unit(char_id=n, star=1) for n in back],
                shop=[cw4_card(n, cost=c, star=s, x=i)
                      for i, (n, c, s) in enumerate(shop_cards)])
    gs.observe(gs.node_pos, (1, 3), evidence='cw-acquire-yield',
               sig=_OBS_SIG)
    gs.strategy_state = st
    return gs, sess, SimpleNamespace(ev_arm='full')


class TestAcquireYieldUnified:
    """统一获取让位评估(design §2.2 第 4 项:金不足/席满同一评估,
    victim 落位分流,金币要求集三项,拦因分键)。"""

    @staticmethod
    def _field_victim_frame(gold: int = 30, bench_extra=None):
        """席满 + 板满(场上杂件部署外)+ 缺件符玄在店:4 费场上杂件 =
        统一序末位(档 8 内概率 0.02 > bench 5 费件 0.0)→ victim =
        场上件 → 跨画面计划 + 关店。"""
        bench = [cw4_bc(_SBR, star=3)] \
            + [cw4_bc(n) for n in (bench_extra or _B5)]
        return _frame_locked(
            bench, [(_FUX, 3, 1)], gold=gold,
            front=[_GIL, *_F3[:3]], back=(_F3[3],))

    def test_gold_short_sells_pad_then_buys(self):
        """金不足 ∧ X 高于末位 → 卖垫件、下帧买 X(design §3 获取让位
        评估行第一断言;席位空 → 纯金让位,虚拟金币 = gold − cost +
        前缀退金 ≥ 0 判定)。"""
        pad = _clean_fillers(4, {_FUX})   # 档 8 垫件(退金 ≥ 缺口)
        from sr_od.application.currency_war.kernel.cw_game_state import (
            BenchSlot,
            BenchView,
        )
        gs, sess, cfg = _frame_locked(
            [cw4_bc(n) for n in pad], [(_FUX, 3, 1)], gold=1,
            front=(_GIL, _SBR, '远坂凛'), ist_locked=False)
        # 帧改锁定:非锁定帧 Saber 不触发换阵(板上件全定型内)——本帧
        # 板上成员满 3(cap 3),池 = bench 垫件 + X。
        act = decide_shop_action(gs, sess, cfg)
        assert isinstance(act, CwActionSellBenchParam), f'非卖垫件: {act!r}'
        assert act.reason == 'shop_swap'
        # 卖出落地投影 → 下帧金足直买 X。
        slots = list(gs.bench.value.slots)
        slots[act.bench_idx] = BenchSlot(kind='empty')
        gs.write_logic(gs.bench, BenchView(slots=slots, capacity=9),
                       produced_by='cw-acquire-yield', sig=_LOGIC_SIG)
        gs.write_logic(gs.gold, gs.gold.value + (act.income or 0),
                       produced_by='cw-acquire-yield', sig=_LOGIC_SIG)
        state_of(gs).gold_ledger = gs.gold.value
        act2 = decide_shop_action(gs, sess, cfg)
        assert isinstance(act2, CwActionBuyCardParam) \
            and act2.card.name == _FUX, f'凑够未买 X: {act2!r}'

    def test_gold_short_x_is_tail_declines_with_gold_key(self):
        """金不足 ∧ X 是全池末位 → 零动作 + 拦因分键
        priority_insufficient_gold(design §3「禁沿用旧键断言钉死分键」
        ——金不足语境含叠加态记新键,非席满键 priority_insufficient);
        机会清单带三字段解拦载荷(gold 快照/缺口值/货架签名)。"""
        gs, sess, cfg = _frame_locked(
            [], [(_FUX, 3, 1)], gold=1,
            front=(_GIL, _SBR, '远坂凛'), ist_locked=False)
        act = decide_shop_action(gs, sess, cfg)
        # 池 = {X}(板上成员全定型内)→ 末位 = X → 放弃;收工关店。
        assert isinstance(act, CwActionCloseShopParam), f'非收工: {act!r}'
        ct = state_of(sess).cw4_counters
        assert ct.get('acquire_swap_declined') == 1
        assert not ct.get('acquire_swap_sell'), '末位 = X 帧禁发出卖出'
        recs = state_of(sess).shop_opportunities
        rec = next(r for r in recs if r.card_name == _FUX)
        assert rec.blocked_by == 'priority_insufficient_gold', \
            f'金不足语境分键失真: {rec.blocked_by!r}'
        assert rec.gold_snapshot == 1 and rec.gold_gap == 2
        assert rec.shelf_signature == (_FUX,)

    def test_unmet_member_tail_sold_no_interest_exemption(self):
        """凑息豁免不适用被迫类(design §2.2 第 5 项动机二分/§3 凑息
        豁免测试第四用例):获取让位帧(金不足触发;与席满同一评估,
        §2.2 第 4 项「两类受阻走同一评估,不分流」)线内未达标成员排
        统一序末位 → 照卖。瓦尔特 = 列车同行候选线成员(need 1,持有
        1★ 未到两星 = 档 5 形态,凑息场景不可卖件;未锁帧部署不拉
        候选成员上场 → 瓦尔特部署外在池);X = 姬子·启行(need 3 未
        持有 = 档 2,优先级高于瓦尔特)→ victim = 瓦尔特(虚拟金币
        1 − 3 + 5 = 3 ≥ 0)——获取动机让位全员参与统一序列,无豁免。"""
        bench = [('瓦尔特', 1)]
        gs, sess, cfg = _frame(
            bench=bench,
            shop_cards=[('姬子·启行', 3, 1)],
            candidates=('列车同行',),
            gold=1, level=5)
        act = decide_shop_action(gs, sess, cfg)
        assert isinstance(act, CwActionSellBenchParam), \
            f'被迫类让位帧应照卖线内未达标成员: {act!r}'
        assert act.reason == 'shop_swap'
        assert act.expect == '瓦尔特', \
            'victim = 统一序末位(线内未达标成员),豁免只挂利息动机场景'
        ct = state_of(sess).cw4_counters
        assert ct.get('acquire_swap_sell') == 1
        assert ct.get('acquire_swap_sell_tier_5') == 1, \
            'victim 档位观测键 = 档 5(未达标成员形态)'

    def test_prefix_pool_exhausted_records_gold_short(self):
        """池穷尽不可足 → 机会清单拦因 gold_short(design §2.2 第 4 项
        步 6 末行):让位序低于 X 的存量件全部入前缀仍不可足(虚拟后
        局态受限 → 花后金 < 饱和线,饱和线不过逐件次末位)→ 存量域
        耗尽(acquire_yield_exhausted)。
        构帧 = 命运圣杯红A 成型局(板上三成员配方完备 + 板面支撑满额
        → 虚拟后局态 armed)+ 金 1:全部垫件退金合计 < g* − 缺口 →
        饱和线恒不过 → 池穷尽。"""
        from sr_od.application.currency_war.kernel.cw_intention import (
            IntentionState,
        )
        sess = StrategySession()
        st = state_of(sess)
        st.cw4_counters = {}
        st.v3_intention = IntentionState(locked_comp='命运圣杯红A')
        st.target_comp = get_comp('命运圣杯红A')
        pads = _B4[:6]   # 4 费垫件 ×6(档 8;退金合计 24 < 饱和线缺口)
        gs = cw4_gs(sess, plane=1, round_num=3, node='battle',
                    gold=1, level=3, hp=80, deploy_cap=3,
                    bench=[cw4_bc(n) for n in pads],
                    front_row=[Unit(char_id=n, star=1) for n in
                               ('Archer', '远坂凛', 'Saber')],
                    board={'命运圣杯': 3},
                    shop=[cw4_card('瓦尔特', cost=5, star=1, x=0)])
        gs.observe(gs.node_pos, (1, 3), evidence='cw-acquire-yield',
                   sig=_OBS_SIG)
        gs.strategy_state = st
        act = decide_shop_action(gs, sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, CwActionCloseShopParam), f'非收工: {act!r}'
        ct = st.cw4_counters
        assert ct.get('acquire_yield_exhausted', 0) >= 1, \
            '池穷尽分键缺席'
        assert not ct.get('acquire_swap_sell'), \
            '饱和线不过帧禁发出卖出(次末位分流至池尽)'
        rec = next(r for r in st.shop_opportunities
                   if r.card_name == '瓦尔特')
        assert rec.blocked_by == 'gold_short'

    def test_field_victim_writes_plan_and_closes_without_mark(self):
        """席满 ∧ victim = 场上部署外件 → 写跨画面计划(步骤序列 +
        目标板 T + 语境 seat + 节点戳)+ 关店不置标记(design §2.2
        第 4 项写端 PV-2/4/8/9/10:决策一次定型;净腾校验在商店写端,
        可达才写槽)。"""
        gs, sess, cfg = self._field_victim_frame()
        act = decide_shop_action(gs, sess, cfg)
        assert isinstance(act, CwActionCloseShopParam), f'非关店: {act!r}'
        assert act.reason == 'yield_plan'
        st = state_of(sess)
        # 关店不置标记(shop_handled 未置 = 返程语义,备战前置步消化
        # 计划后第 5 步常规机制开店)。
        assert st.shop_handled is None, '计划关店误置会话标记'
        plan = st.yield_plan
        assert plan is not None, '场上件 victim 未写计划槽'
        sells = [s.name for s in plan.steps if s.kind == 'sell']
        assert sells == ['娜塔莎'], f'前缀场上件失真: {sells}'
        assert any(s.kind == 'deploy' for s in plan.steps), \
            '席位语境计划缺驱板步骤'
        assert plan.context == 'seat'
        assert plan.target_board is not None
        assert _SBR in plan.target_board and _GIL in plan.target_board, \
            'T =「当前 − 前缀」定型板面(SF-2:非步 3 的 +X 定型)'
        assert _FUX not in (plan.target_board or ()), \
            'T 面板不含 X(买 X 帧时点,X 未购)'
        assert plan.node_stamp == (1, 3)
        assert st.cw4_counters.get('yield_plan_written') == 1
        assert st.cw4_counters.get('acquire_swap_field_victim') == 1

    def test_field_victim_net_seat_unreachable_falls_to_bench(self):
        """净腾校验不可达 → 次末位承接(PV-4:写端「当前 − 前缀」定型
        后 bench 占用较当前降 ≥ 1;不可达 = 该 victim 路径不成立 →
        次末位,不写槽):bench 全为上阵窗口外件(窗口谓词挡上场不挡
        卖出)→ 卖场上件级联无 bench 件可补 → 净腾 0 → 场上 victim
        不成立 → 次末位 = bench 件店内卖出(直接腾位恒可达)。"""
        gs, sess, cfg = _frame_locked(
            [cw4_bc(n) for n in _WIN_BLOCKED], [(_FUX, 3, 1)], gold=30,
            front=[_GIL, *_F3[:3]], back=(_F3[3],))
        # Saber 不在 bench:板上杂件仍部署外?——无换阵触发时定型 =
        # 现板(场上件全档 1)→ 池 = bench 窗口关件 + X。末位 = bench
        # 件(窗口谓词不挡卖出)→ 店内卖。此帧验证「窗口关 bench 件
        # 可卖」的对照面(净腾不可达的场上件路径已由上一用例的可达
        # 形态对照承载,本帧锁定席满语境 bench victim 恒可达分支)。
        act = decide_shop_action(gs, sess, cfg)
        assert isinstance(act, CwActionSellBenchParam), f'非店内卖: {act!r}'
        assert state_of(sess).yield_plan is None, \
            'bench victim 帧不得写计划槽'

    def test_saturation_line_blocks_armed_and_passes_unarmed(self):
        """饱和线项(design §2.2 第 4 项步 5 金币要求集②):虚拟后局态
        受限(命运圣杯红A 成型 + 板面支撑满额 → armed)→ 花后金 ≥
        饱和线追加要求——花后金 < 线的 victim 全部不成立(次末位至
        池尽);同金位的非受限局态(配方不完备 → 非 armed)无追加
        要求 → 卖垫件。armed 判据不满足帧的对照 = 受限追加要求仅在
        虚拟后局态进入出战准备态时成立(裁定二)。"""
        for board, expect_sell in (
                (('Archer', '远坂凛', 'Saber'), False),   # 成型 → armed
                (('Archer', '远坂凛', '青雀'), True)):     # 未成型 → 放行
            sess = StrategySession()
            st = state_of(sess)
            st.cw4_counters = {}
            st.v3_intention = IntentionState(
                locked_comp='命运圣杯红A')
            st.target_comp = get_comp('命运圣杯红A')
            _board_counts = ({'命运圣杯': 3} if not expect_sell
                             else {'命运圣杯': 2, '仙舟': 1})
            gs = cw4_gs(sess, plane=1, round_num=3, node='battle',
                        gold=1, level=3, hp=80, deploy_cap=3,
                        bench=[cw4_bc(n) for n in _B4[:3]],
                        front_row=[Unit(char_id=n, star=1) for n in board],
                        board=_board_counts,
                        shop=[cw4_card('瓦尔特', cost=5, star=1, x=0)])
            gs.observe(gs.node_pos, (1, 3), evidence='cw-acquire-yield',
                       sig=_OBS_SIG)
            gs.strategy_state = st
            act = decide_shop_action(gs, sess, SimpleNamespace(ev_arm='full'))
            if expect_sell:
                # 非受限局态:饱和线无追加要求 → victim 成立卖垫件
                # (1★ 5 费退金 5,虚拟金币 1 − 5 + 5 = 1 ≥ 0)。
                assert isinstance(act, CwActionSellBenchParam), \
                    f'板面 {board} 帧应卖垫件: {act!r}'
                assert act.reason == 'shop_swap'
            else:
                # 受限局态:花后金 1 < 饱和线 50 → 逐件次末位至池尽。
                assert isinstance(act, CwActionCloseShopParam), \
                    f'板面 {board} 帧应池穷尽收工: {act!r}'
                assert st.cw4_counters.get('acquire_yield_exhausted', 0) \
                    >= 1

    def test_pure_gold_context_plan_has_no_deploy_step(self):
        """语境定格(design §3 计划变量行:纯金语境无驱板步骤):席位
        空 + 金不足 + victim = 场上件 → 计划 context='gold'、T=None、
        步骤全 sell(场位缺口由常规部署步自然补)。"""
        bench = [cw4_bc(_SBR, star=3)] + [cw4_bc(n) for n in _B5[:6]]
        gs, sess, cfg = _frame_locked(
            bench, [(_FUX, 3, 1)], gold=1,
            front=[_GIL, *_F3[:3]], back=(_F3[3],))
        act = decide_shop_action(gs, sess, cfg)
        assert isinstance(act, CwActionCloseShopParam), f'非关店: {act!r}'
        assert act.reason == 'yield_plan'
        plan = state_of(sess).yield_plan
        assert plan is not None and plan.context == 'gold'
        assert plan.target_board is None, '纯金语境 T = None'
        assert [s.kind for s in plan.steps] == ['sell'], \
            f'纯金语境计划不得含驱板步骤: {plan.steps}'

    def test_x_path_failed_excludes_field_victims(self):
        """X 路径失败标记(PV-8):标记置位帧场上件 victim 全部不成立
        (本节点内 X 的场上件路径已失败)→ 只走 bench 件路径——对照帧
        (未置位)同一局面写计划,置位帧改卖 bench 件。"""
        gs, sess, cfg = self._field_victim_frame()
        state_of(sess).x_path_failed = True
        act = decide_shop_action(gs, sess, cfg)
        assert isinstance(act, CwActionSellBenchParam), \
            f'失败标记帧应走 bench 件路径: {act!r}'
        assert state_of(sess).yield_plan is None, \
            '失败标记在场禁写场上件计划'

    def test_restricted_frame_skips_yield_eval(self):
        """受限会话前置(S7-4/S9-6):出战就绪 ∧ 金达利息线的受限帧
        不进让位评估(获取延后)——触发面 = 席满(受限帧金 ≥ g* 恒 ≥
        费用,金不足触发结构性不可达);受限帧零让位动作,不写计划。"""
        from sr_od.application.currency_war.kernel.cw_economy import (
            cap_resolved_of_session,
            saturation_line,
        )
        sess = StrategySession()
        st = state_of(sess)
        st.cw4_counters = {}
        st.v3_intention = IntentionState(locked_comp='命运圣杯红A')
        st.target_comp = get_comp('命运圣杯红A')
        _g_star = saturation_line(cap_resolved_of_session(sess))
        pads = _clean_fillers(9, {_FUX})
        gs = cw4_gs(sess, plane=1, round_num=3, node='battle',
                    gold=_g_star, level=3, hp=80, deploy_cap=3,
                    bench=[cw4_bc(n) for n in pads],
                    front_row=[Unit(char_id=n, star=1) for n in
                               ('Archer', '远坂凛', 'Saber')],
                    board={'命运圣杯': 3},
                    shop=[cw4_card('瓦尔特', cost=5, star=1, x=0)])
        gs.observe(gs.node_pos, (1, 3), evidence='cw-acquire-yield',
                   sig=_OBS_SIG)
        gs.strategy_state = st
        decide_shop_action(gs, sess, SimpleNamespace(ev_arm='full'))
        ct = st.cw4_counters
        assert ct.get('acquire_yield_restricted_skip', 0) >= 1, \
            '受限帧应跳过让位评估(获取延后)'
        assert not ct.get('acquire_swap_sell'), \
            '受限帧禁让位卖出(0≤花后<g* 白卖面)'
        assert st.yield_plan is None, '受限帧禁写跨画面计划'
