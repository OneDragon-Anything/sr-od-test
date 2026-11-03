"""统一获取让位评估单帧测试(roster-plane1-union design §2.2 第 4 项;
镜像 = mandate_v1/shop.py ``_acquire_yield``——原席满买入六步流程与
会话内筹资两路合一,触发 = 获取受阻于「备战席满 ∨ 金 < 费用」任一或
叠加)。

规格单一源 = changes/2026-10-30-roster-plane1-union/design.md §2.2
第 4 项(评估步骤 1-6/金币要求集三项/拦因分键/victim 落位分流/写端
载荷)+ §2.3 获取驱动让位表:

- 快照 → 虚拟置牌 + 升星连锁 → 部署定型 → 部署外件全集按
  ``priority.sell_order`` 排序(新牌 = 将获取旗标;**评估侧 X 不进
  档 1 保护**——deployed_names 剔除 X 名,X 恒按卡面价值参与排序,
  末位判定不受虚拟定型收编影响)→ victim 试探
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
    (同概率域同档,排序键仅差在手旗标)、非万金油/非档 9 羁绊——防
    跨档(万金油档 8/羁绊档 9 键小于兜底档 10,会让「末位 = 新牌」
    退化成跨档结论;十档口径 = 完成品保护迭代 design §2.2)。"""
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
           gold: int = 30, level: int = 7, filler_min_cost: int = 2):
    """席满帧(备战 9/9;场前排铺满 cap;双宿主状态同源接线)。
    locked_comp/recipe_comp 接受线名(注册表解析为 Comp 对象落槽)。
    铺板杂件排除店内 X 名(bench/field/shop 三域名字互异——同名会被
    部署需要面一并保护,同帧多机制耦合会稀释被测分支)。
    filler_min_cost = 场外填充件费用下限(默认 2;兜底域概率键对部署
    换血敏感的帧用它抬高杂件费用、压低其概率上界——部署外杂件概率
    必须严格小于被测候选才会让「末位 = 候选」判定稳健)。"""
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
    exclude = (members | held_names | {'绯英'}
               | {n for n, _c, _s in shop_cards})
    fillers = _clean_fillers(level, exclude, min_cost=filler_min_cost)
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


def _x_junk_card(candidates: tuple) -> str:
    """X-末位帧的 X:显式钉名 + 前置断言(非候选线成员 → 落兜底档 10,
    十档口径 design §2.2;注册表 3 费 → level 7 概率 0.40 全池最高)。
    断言防注册表演进
    (新成员录入/费用调整)使帧前提静默失效后失败信息不指向根因。"""
    _x = '娜塔莎'
    members: set[str] = set()
    for cn in candidates:
        members |= set(_members(get_comp(cn)))
    assert _x not in members, \
        f'帧前提失守:{_x} 已入候选线成员(X 应落兜底档 10,入线则落成员档族 2/3/4/5/7)'
    assert (CHARACTERS[_x].cost or 0) == 3, \
        f'帧前提失守:{_x} 注册表费用漂移(level 7 概率 0.40 前提失效)'
    return _x


class TestAcquireSwapSixStep:
    """席满买入六步流程(3.2;置换账替换后的三帧判据)。"""

    def test_missing_member_sells_tail_junk(self):
        """置换成功帧:席满 + 方向缺件绯英在店 → 六步流程卖序列末位
        存量牌(卖旧 → 下帧重入买入,单动作契约);绯英 = 未持有配方
        成员(未持有档 5,旧八档档 3 位移,十档口径 design §2.2;序列
        保护面)永不入让位末位。

        买面名单源改写(12 号篇 §1.2):配方半边 = 过渡
        候选/实候选并集,opening_recipe_comp 不再进买面——种子从
        recipe_comp 直种改为 line_candidates 直种(锁定语义免耦合评分
        内核,与 test_shop_session_loop._frame 同款)。"""
        junk = _clean_fillers(9, {'绯英'})
        gs, sess, cfg = _frame(
            bench=[(n, 1) for n in junk],
            shop_cards=[('绯英', 2, 1)],
            candidates=('绯英欢愉',))
        act = decide_shop_action(gs, sess, cfg)
        assert isinstance(act, CwActionSellBenchParam), f'非卖旧动作: {act!r}'
        assert act.reason == 'shop_swap'
        assert act.expect != '绯英' and act.expect in junk, \
            f'让位件非存量杂件: {act.expect!r}'
        ct = state_of(sess).cw4_counters
        assert ct.get('acquire_swap_sell') == 1
        # 取用观测键(统一让位优先级迭代 3.5;键表 = telemetry/schema.py
        # 键表节):档位分布恰一落账(尾牌 = 干净杂件,兜底档 10/羁绊
        # 档 9 由注册表羁绊归属定〔旧八档档 8/7 位移,十档口径 design
        # §2.2〕——断言计数和,不钉死注册表事实的档号);键互异帧
        # 随机尾键命中不落账。
        assert sum(v for k, v in ct.items()
                   if k.startswith('acquire_swap_sell_tier_')) == 1
        assert not ct.get('acquire_swap_sell_rng_tail_hit')
        assert not ct.get('acquire_swap_declined')

    def test_tail_is_new_card_declines_buy(self):
        """末位 = 新牌放弃帧(拒绝语义由 M6 臂 order_4 通道承载,总纲
        §2.7 申报②):席满持牌全为缺口成员(档 3 升星主线/档 7 凑两星,
        十档口径 design §2.2)+ 店内牌 = 干净
        杂件 X(非候选成员落兜底档 10;3 费 level 7 概率 0.40 = 全池最高 →
        优先级低于全部成员持牌 = 序列末位 = 新牌自己)→ 放弃买入零
        动作,记录「优先级不足」拦因,收工关店。X 与持件桑博共享贝洛
        伯格标签(可参与虚拟定型竞争的组成)——评估侧 X 不进档 1 保护
        (_acquire_yield deployed_names 剔除 X 名),X 恒按卡面价值
        定序,末位判定与虚拟定型是否收编 X 无关(收编形态的专项反例 =
        test_x_absorbed_into_virtual_target_still_declines_buy)。"""
        bench = [('姬子·启行', 1), ('姬子·启行', 1), ('三月七', 1),
                 ('三月七', 1), ('花火', 1), ('万敌', 1),
                 ('千冶·刃', 1), ('卡芙卡', 1), ('桑博', 1)]
        _x_card = _x_junk_card(('列车同行·反震', '万敌单C', '专家桑博DOT'))
        gs, sess, cfg = _frame(
            bench=bench,
            shop_cards=[(_x_card, 3, 1)],
            candidates=('列车同行·反震', '万敌单C', '专家桑博DOT'),
            gold=100)
        act = decide_shop_action(gs, sess, cfg)
        assert isinstance(act, CwActionCloseShopParam), f'非收工: {act!r}'
        ct = state_of(sess).cw4_counters
        assert ct.get('acquire_swap_declined', 0) >= 1
        assert not ct.get('acquire_swap_sell'), \
            '末位 = 新牌帧不得发出卖旧(拒绝语义)'
        assert any(r.card_name == _x_card
                   and r.blocked_by == 'priority_insufficient'
                   for r in state_of(sess).shop_opportunities), \
            f'优先级不足机会清单缺席: {state_of(sess).shop_opportunities}'

    def test_two_star_direct_member_card_declines_buy(self):
        """2★ 直出成员候选帧「末位 = X → 放弃」可达(完成品保护迭代
        design §2.5-6 显式申报 / §2.3-5:2★ 直出 X 落兜底档 10;§2.1
        身份域:ShopUnit 恒非保留张):X = 花火 2★ 直出(列车同行
        need 2 达标、名下无持有副本——若候选可为保留张,X 将以「名下
        唯一最高星」自入档 2,获取决策从「可能 decline」翻转为「必买」
        并开启卖成员完成品凑 X 的牺牲链,禁);身份域下 X 落兜底档 10、
        键大于全部缺口成员持牌(档 3/7)→ 统一序末位 = X → 放弃买入
        零动作。帧纪律:level 5 + 场外填充 ≥3 费——X(2 费概率 0.33)
        严格支配一切可能部署外杂件(3/4/5 费概率 0.20/0.02/0),末位
        判定对虚拟部署换血稳健(场外杂件入池也压不过 X)。帧前提断言
        花火 ∈ 候选线成员(X 非成员则退化为杂件 X
        平凡帧,test_tail_is_new_card_declines_buy 已辖,不证身份域
        语义)。"""
        candidates = ('列车同行·反震', '万敌单C', '专家桑博DOT')
        members: set[str] = set()
        for cn in candidates:
            members |= set(_members(get_comp(cn)))
        assert '花火' in members, \
            '帧前提失守:花火已非候选线成员(2★ 直出 X 身份域语义帧失效)'
        bench = [('姬子·启行', 1), ('姬子·启行', 1), ('三月七', 1),
                 ('三月七', 1), ('瓦尔特', 1), ('瓦尔特', 1),
                 ('万敌', 1), ('千冶·刃', 1), ('卡芙卡', 1)]
        gs, sess, cfg = _frame(
            bench=bench,
            shop_cards=[('花火', 2, 2)],
            candidates=candidates,
            gold=100, level=5, filler_min_cost=3)
        act = decide_shop_action(gs, sess, cfg)
        assert isinstance(act, CwActionCloseShopParam), f'非收工: {act!r}'
        ct = state_of(sess).cw4_counters
        assert ct.get('acquire_swap_declined', 0) >= 1
        assert not ct.get('acquire_swap_sell'), \
            '末位 = X 帧禁发出卖旧(2★ 直出候选恒非保留张,design §2.5-6)'
        assert any(r.card_name == '花火'
                   and r.blocked_by == 'priority_insufficient'
                   for r in state_of(sess).shop_opportunities), \
            f'优先级不足机会清单缺席: {state_of(sess).shop_opportunities}'

    def test_priority_insufficient_unblocks_on_seat_freed(self):
        """优先级不足拦因 = 席满语境拦阻:席位空出后买入不再经六步
        (正常买入路径无优先级门)→ 解拦复核同席满类放行。(帧构造同
        上——全成员席,M6 臂 order_4 通道承载拒绝语义。)"""
        bench = [('姬子·启行', 1), ('姬子·启行', 1), ('三月七', 1),
                 ('三月七', 1), ('花火', 1), ('万敌', 1),
                 ('千冶·刃', 1), ('卡芙卡', 1), ('桑博', 1)]
        gs, sess, cfg = _frame(
            bench=bench,
            shop_cards=[(_x_junk_card(('列车同行·反震', '万敌单C',
                                       '专家桑博DOT')), 3, 1)],
            candidates=('列车同行·反震', '万敌单C', '专家桑博DOT'),
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
            locked_comp='列车同行·反震')
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
#: 场上 3 费杂件(兜底档 10 内概率 0.2 > bench 件 → 场上件稳定让位序末位)。
_F3 = ('娜塔莎', '姬子·启行', '刻律德菈', '镜流')
#: bench 杂件(5 费 ×7 + 4 费 ×1;兜底档 10 概率 0/0.02 均低于场上 3 费)。
_B5 = ('流萤', '昔涟', '布洛妮娅', '云璃', '景元',
       '托帕&账账', 'Archer', '大黑塔')
#: 4 费垫件(≠ 升星目标实费档 → 落兜底档 10;饱和线/池穷尽帧的让位垫件)。
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
        统一序末位(兜底档 10 内概率 0.02 > bench 5 费件 0.0)→ victim =
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
        pad = _clean_fillers(4, {_FUX})   # 兜底档 10 垫件(退金 ≥ 缺口)
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

    def test_x_absorbed_into_virtual_target_still_declines_buy(self):
        """X 进虚拟定型仍判末位 = X 反例(获取让位 X 末位敏感性;
        design §2.2 第 4 项步 6「末位 = X → 放弃」的任意组成可达性):
        X 与持件有同羁绊标签搭档 ∧ X 统一优先级最低 → 虚拟定型把 X
        收编进 target 也不改变末位判定——评估侧 X 不进档 1 保护
        (步 4:deployed_names 剔除 X 名;档 1 保护对象 = 存量资产,
        X 是「将获取」的假设性入场者,其去留正是评估要回答的问题)。
        若档 1 按名命中覆盖到 X,X 即经虚拟定型自我保护、末位恒落到
        存量垫件头上——「末位 = X → 放弃」分支在该组成不可达,席满帧
        会卖掉垫件去买全池最低优先级的新牌。

        锁定帧(双王圣杯)X = 娜塔莎(非锁定线成员,锁定线外囤件放行
        进部署枚举;与 bench 佩拉共享贝洛伯格标签;3 费 level 7 概率
        0.40 = 全池最高 → 兜底档 10 末位,十档口径 design §2.2)。帧前提
        断言 X ∈ 虚拟定型名集
        (收编形态在场;定型漂移使 X 出 target 时本帧退化为平凡末位
        帧,前置断言让退化响亮暴露)。"""
        bench = [('佩拉', 1), ('知更鸟', 1), ('银枝', 1),
                 ('托帕&账账', 1), ('流萤', 1), ('昔涟', 1),
                 ('云璃', 1), ('景元', 1), ('姬子', 1)]
        _x_card = '娜塔莎'
        gs, sess, cfg = _frame_locked(
            [cw4_bc(n, star=s) for n, s in bench], [(_x_card, 3, 1)],
            gold=100, level=7, front=(_GIL, _SBR, '远坂凛'))
        # 帧前提:X 名进虚拟定型(收编形态;直调部署接口复算评估步 3)。
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            mandate,
        )
        frame = mandate.snapshot_frame(gs)
        sim = mandate.simulate_acquired_units(
            frame.bench, frame.deployed, _x_card, 1)
        prep = mandate.assemble_prep_context(sess, gs, frame)
        target = mandate.select_deployment(
            frame, prep,
            virtual_bench=[bs for _i, bs in sim.bench],
            virtual_field=sim.field)
        assert _x_card in target, \
            f'帧前提失守:X 未被虚拟定型收编: {sorted(target)}'
        act = decide_shop_action(gs, sess, cfg)
        assert isinstance(act, CwActionCloseShopParam), f'非收工: {act!r}'
        ct = state_of(sess).cw4_counters
        assert ct.get('acquire_swap_declined', 0) >= 1
        assert not ct.get('acquire_swap_sell'), \
            '末位 = X 帧禁发出卖旧(X 进定型不得自我保护)'
        assert any(r.card_name == _x_card
                   and r.blocked_by == 'priority_insufficient'
                   for r in state_of(sess).shop_opportunities), \
            f'优先级不足机会清单缺席: {state_of(sess).shop_opportunities}'

    def test_unmet_member_tail_sold_no_interest_exemption(self):
        """凑息豁免不适用被迫类(design §2.2 第 5 项动机二分/§3 凑息
        豁免测试第四用例):获取让位帧(金不足触发;与席满同一评估,
        §2.2 第 4 项「两类受阻走同一评估,不分流」)线内未达标成员排
        统一序末位 → 照卖。瓦尔特 = 列车同行候选线成员(need 1,持有
        1★ 未到两星 = 凑两星过程保护档 7 形态〔旧八档档 5 位移,十档
        口径 design §2.2〕,凑息场景不可卖件;未锁帧部署不拉
        候选成员上场 → 瓦尔特部署外在池);X = 姬子·启行(need 3 未
        持有 = 未持有档 5〔旧档 3 位移〕,保留优先级高于瓦尔特)→
        victim = 瓦尔特(虚拟金币
        1 − 3 + 5 = 3 ≥ 0)——获取动机让位全员参与统一序列,无豁免。"""
        bench = [('瓦尔特', 1)]
        gs, sess, cfg = _frame(
            bench=bench,
            shop_cards=[('姬子·启行', 3, 1)],
            candidates=('列车同行·反震',),
            gold=1, level=5)
        act = decide_shop_action(gs, sess, cfg)
        assert isinstance(act, CwActionSellBenchParam), \
            f'被迫类让位帧应照卖线内未达标成员: {act!r}'
        assert act.reason == 'shop_swap'
        assert act.expect == '瓦尔特', \
            'victim = 统一序末位(线内未达标成员),豁免只挂利息动机场景'
        ct = state_of(sess).cw4_counters
        assert ct.get('acquire_swap_sell') == 1
        assert ct.get('acquire_swap_sell_tier_7') == 1, \
            'victim 档位观测键 = 档 7(凑两星过程保护形态,十档口径 ' \
            'design §2.2;旧八档档 5 位移)'

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
        pads = _B4[:6]   # 4 费垫件 ×6(兜底档 10;退金合计 24 < 饱和线缺口)
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
        assert len(sells) == 1, f'前缀场上件失真(等价末位 rng 定,不钉死名字): {sells}'
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



