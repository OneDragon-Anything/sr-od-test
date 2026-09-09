"""T-193 dominance_buy 买后金下限地板(结算线地板)单帧锁 + 发射级断言端到端。

设计出处(锁纪律:新锁必引设计出处;持久载体 = ADR-0624,
docs/develop/currency_war/decisions/0624-dominance-settlement-line-floor.md):
- ADR-0624 决策 1/2/3:结算线地板谓词单一源(``shop.check_settlement_line``,
  gold − cost ≥ g*,g* = saturation_line(cap_resolved) 派生禁字面)/
  dominance 臂消费位与候选级分键 ``dominance_settlement_floor_reject``/
  档 1 内联地板同谓词迁移(行为不变)。
- ADR-0604 §3-2:档 1 press_buy_deployable 同形地板先例(本批迁谓词);
  ADR-0580 ③:C1:unlocked 恒买语义(残余击穿面,本批不动,见 F5)。
- 息律正本:利息 = min(⌊轮末裸金/10⌋, cap)×1金/轮,bench 资产不计息(P47);
  溢余带(买后金 ≥ g*)= 已证零损域(P70)——地板保留的全部行为在带内。

锁清单(方案 v3 §7 新锁①-⑤ + §8 主判据载体;编号 = 方案编号):
- F1 穿线笔截断+分键:拒 3 金穿线笔、continue 试下一更便宜候选;
  变异 = 摘地板谓词(恒放行)则穿线笔先手发射,本锁红。
- F2 预算内顺序贪心贴线:54 金 [3金,3金,1金] ⇒ 买 3 金到 51,地板拒
  第二张 3 金(48<50)换 1 金到 50 贴线停——单动作契约下逐笔买后检查
  ≡ 溢余带预算(g_visit − g*)封顶,零批状态。
- F3 买断制 no-op:cap_resolved=0 ⇒ g*=0,地板被 check_affordable
  (g ≥ c ⇒ g−c ≥ 0)蕴含,发射行为与旧世界逐位同。
- F4 档 1 迁移等价:同谓词同值,拒笔行为与分键不变;
  变异 = 谓词恒放行 ⇒ 发射(证明迁移后谓词承重,非空转)。
- F5 息损单调边界锁(冻结口径反例):残余击穿 visit(下游 C1:unlocked
  恒买 2★ 核心可穿线)中地板只少花钱不改息档——钉住「息损严格减少的
  充分条件 = 该 visit 无残余击穿」,防把单调性命题误读成逐帧保证。
- E2E 发射级断言(ADR-0624 验收主判据的实现批载体):离线重放路径
  (快照 dict → cw_replay._rebuild_state → 部署驱动器 decide_shop_screen)
  断言:全部 dominance 发射笔中买后金 < g* 的发射数 = 0。

构造声明:候选名一律注册表实名(线外非核心/转线层,程序化选取,禁巧合
锁名);ev_arm=full;息帽走缺省解析链(无持卡覆写 ⇒ cap=5 ⇒ g*=50),
买断制锁显式持「买断制」策略名(kernel overlay 单一源)。快照席位构造
= 板上 level−1 人(cap 缺省 = level)使升级臂 level≥cap 短路防 M3 抢
发射;快照 level 缺省 3 使塌缩窗 = [1]、M6 压库臂静默(F2 序列纯度
前提,窗口现查非拍定);档 1 锁复用 test_cw_leak_ladder 的锁线夹具。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_card_identity import (
    TIER_REGISTRY_CORE,
    TIER_TRANSITION,
    line_identity_tier,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BuyCard,
    LevelUpShop,
    RefreshShop,
)
from sr_od.application.currency_war.sim import cw_replay
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    shop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    decide_shop_action,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.interest import (
    saturation_line,
)
from test.sr_od.app.currency_war.test_cw_leak_ladder import (
    _off_name as _lad_off_name,
)
from test.sr_od.app.currency_war.test_cw_leak_ladder import (
    _session_stub as _lad_session,
)
from test.sr_od.app.currency_war.test_cw_leak_ladder import (
    _st as _lad_st,
)
from test.sr_od.app.currency_war.test_cw_sell_window_launch import (
    _FUEL,
    _card,
    _sess,
)

_CFG = SimpleNamespace(ev_arm='full')
#: 缺省息帽链的饱和线(无持卡覆写 ⇒ cap_resolved=5)。
_G_STAR = saturation_line(5)


def _off_name(cost: int, exclude: tuple[str, ...] = ()) -> str:
    """线外非核心/转线层的注册表实名(指定费档;程序化选取防巧合锁)。"""
    for n, ch in CHARACTERS.items():
        if n in exclude or (ch.cost or 0) != cost:
            continue
        if line_identity_tier(n) in (TIER_REGISTRY_CORE, TIER_TRANSITION):
            continue
        return n
    raise AssertionError(f'注册表缺少费档 {cost} 的线外实名(锁前提失效)')


def _deployed_units(n: int) -> list[dict]:
    """板上 n 人快照单元(2★;席位构造使升级臂 level≥cap 短路)。"""
    return [{'slot': i + 1, 'char_id': f'板上垫件{i}', 'faction': '?',
             'star': 2, 'position_pref': 'back'} for i in range(n)]


def _snapshot(gold: int, shop_units: list[tuple[str, int, int]],
              *, level: int = 3) -> dict:
    """decisions.jsonl state 字段形态的快照 dict(重放数据路入口)。

    level 缺省 3:塌缩窗 = [1](tier_search_window 现查),3 金候选恒不
    档匹配 ⇒ M6 压库臂静默,plan 只含 dominance/C1 动作(F2 序列纯度
    断言的前提);板上 level−1 人防升级臂抢发射。"""
    return {
        'gold': gold, 'hp': 60, 'level': level, 'plane': 2, 'round_num': 3,
        'node_type': 'battle', 'board': {},
        'deployed': _deployed_units(max(level - 1, 0)),
        'bench': [],
        'shop': [{'x': 100 + 10 * i, 'faction': '?', 'name': n, 'cost': c,
                  'star': s} for i, (n, c, s) in enumerate(shop_units)],
    }


def _fresh_sess() -> tuple[MandateV1Strategy, object]:
    """部署驱动器 + 冷建 session(与 cw_replay 同路),K 方向 = 单成员
    测试线(候选线外实名恒 zero_overlap 通过)。form_tiers 空档 =
    form_progress 鸭型桩契约(kernel 直读该键,空 dict = 未成型 0.0)。"""
    strat = MandateV1Strategy()
    sess = strat.create_session(None)
    state_of(sess).target_comp = SimpleNamespace(
        name='测试线', core_chars=('目标件',), shared_chars=(),
        form_tiers={})
    return strat, sess


def _replay_plan(snap: dict) -> tuple[object, object, list]:
    """离线重放一步:快照 → _rebuild_state → 部署驱动器出 visit 序列。
    返回 (重建态, session, plan)——session 供拒因分键读数。"""
    strat, sess = _fresh_sess()
    st = cw_replay._rebuild_state(snap)
    sess.shop_state_frame = st
    return st, sess, strat.decide_shop_screen(sess, _CFG)


def _walk_gold(gold: int, plan: list) -> int:
    """visit 序列的金账(单动作契约:金 = 期望态现值,序列口径)。"""
    for a in plan:
        if isinstance(a, BuyCard):
            gold -= a.card.cost if a.card.cost else 3
        elif isinstance(a, (RefreshShop, LevelUpShop)):
            gold -= a.cost
    return gold


# ===== F1/F2/F3:dominance 臂结算线地板 =====


class TestDominanceSettlementFloor:

    def test_f1_threading_note_rejected_cheap_candidate_bought(self):
        """锁 F1(ADR-0624 决策 2):52 金帧、店序 [3 金穿线笔, 1 金带内笔]
        ⇒ 3 金笔被结算线地板拒(候选级分键 dominance_settlement_floor_
        reject),continue 试下一更便宜候选 ⇒ 1 金笔发射(买后 51 ≥ g*)。
        变异红证见 test_f1_mutation_floor_removed_red。"""
        c3 = _off_name(3, exclude=(_FUEL,))
        st = cw_replay._rebuild_state(_snapshot(
            52, [(c3, 3, 1), (_FUEL, 1, 1)]))
        sess = _sess()
        act = decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, BuyCard) and act.reason == 'dominance_buy'
        assert act.card.name == _FUEL, \
            '穿线笔未被地板拦截(买后 49 < g* = 病灶复发)'
        ct = state_of(sess).cw4_counters
        assert ct.get('dominance_settlement_floor_reject') == 1

    def test_f1_mutation_floor_removed_red(self, monkeypatch):
        """F1 变异红证(在册变异,ADR-0624 验证节):地板谓词恒放行
        (等价「无地板」旧世界)⇒ 3 金穿线笔先手发射、买后 49 < g*——
        证明 dominance 发射路径确受谓词辖,F1 不是空绿。"""
        monkeypatch.setattr(shop, 'check_settlement_line',
                            lambda gold, cost, g_star: (True, ''))
        c3 = _off_name(3, exclude=(_FUEL,))
        st = cw_replay._rebuild_state(_snapshot(
            52, [(c3, 3, 1), (_FUEL, 1, 1)]))
        sess = _sess()
        act = decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, BuyCard) and act.reason == 'dominance_buy'
        assert act.card.name == c3
        assert 52 - (act.card.cost or 3) < _G_STAR
        assert state_of(sess).cw4_counters.get(
            'dominance_settlement_floor_reject', 0) == 0

    def test_f2_sequential_greedy_budget_cap(self):
        """锁 F2(ADR-0624 决策 2 顺序贪心等价):54 金、店序 [3 金, 3 金,
        1 金] 带内候选 ⇒ 序列 = 3 金(54→51)→ 地板拒第二张 3 金
        (51−3=48 < g*,分键 =1)→ continue 换 1 金(51→50 贴线停)
        ——溢余带预算(54 − g*)花满即停,拒笔后继者成本 ≤ 剩余预算,
        零批状态载体(每帧金现读,逐笔检查 ≡ 预算封顶)。"""
        n1 = _off_name(3)
        n2 = _off_name(3, exclude=(n1,))
        st, sess, plan = _replay_plan(_snapshot(
            54, [(n1, 3, 1), (n2, 3, 1), (_FUEL, 1, 1)]))
        dom = [a for a in plan
               if isinstance(a, BuyCard) and a.reason == 'dominance_buy']
        assert len(dom) == 2, f'带内预算应恰花两笔,plan={plan!r}'
        assert all(isinstance(a, BuyCard) for a in plan), \
            '本帧形状不应有他臂动作混入'
        assert dom[0].card.name == n1 and dom[1].card.name == _FUEL, \
            '拒笔后应换更便宜候选(顺序贪心),不应跳过整臂'
        assert state_of(sess).cw4_counters.get(
            'dominance_settlement_floor_reject') == 1
        assert _walk_gold(54, plan) == 50
        # 发射级断言(逐笔):每笔 dominance 买后金 ≥ g*
        g = 54
        for a in dom:
            cost = a.card.cost if a.card.cost else 3
            assert g - cost >= _G_STAR
            g -= cost

    def test_f3_buymode_cap_zero_noop(self):
        """锁 F3(ADR-0624 边界:cap_resolved=0 ⇒ g*=0):买断制语境
        (overlay「买断制」interest_cap_override=0)下地板恒被
        check_affordable 蕴含——52 金帧 3 金笔照常发射、零拒键,与
        旧世界逐位同(零行为变更申报)。"""
        c3 = _off_name(3, exclude=(_FUEL,))
        st = cw_replay._rebuild_state(_snapshot(52, [(c3, 3, 1)]))
        sess = _sess()
        sess.active_strategies = ['买断制']
        act = decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, BuyCard) and act.reason == 'dominance_buy'
        assert state_of(sess).cw4_counters.get(
            'dominance_settlement_floor_reject', 0) == 0


# ===== F4:档 1 迁移等价 =====


class TestLadder1MigrationEquivalence:

    def test_f4_below_floor_rejected_same_key(self, monkeypatch):
        """锁 F4(ADR-0624 决策 3):档 1 地板迁同谓词后行为不变——
        52 金锁线必花域帧、3 金 2★ 可上件 ⇒ 52−3=49 < g* 拒,分键
        press_buy_deployable_below_floor 与内联实现同键同值。"""
        monkeypatch.setattr(shop, 'can_deploy_single',
                            lambda *a, **kw: (True, ''))
        cand = _lad_off_name()
        st = _lad_st(52, [_card(cand, cost=3, star=2)])   # 2★=非垫件非支配候选
        sess = _lad_session(locked=True)
        act = decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert not (isinstance(act, BuyCard)
                    and act.reason == 'press_buy_deployable')
        ct = state_of(sess).cw4_counters
        assert ct.get('press_buy_deployable_below_floor') == 1

    def test_f4_mutation_predicate_pass_through_red(self, monkeypatch):
        """F4 变异红证:谓词恒放行 ⇒ 3 金 2★ 可上件发射(52−3=49 < g*)
        ——证明档 1 发射路径迁谓词后仍受其辖,迁移非空转。"""
        monkeypatch.setattr(shop, 'can_deploy_single',
                            lambda *a, **kw: (True, ''))
        monkeypatch.setattr(shop, 'check_settlement_line',
                            lambda gold, cost, g_star: (True, ''))
        cand = _lad_off_name()
        st = _lad_st(52, [_card(cand, cost=3, star=2)])
        sess = _lad_session(locked=True)
        act = decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, BuyCard) \
            and act.reason == 'press_buy_deployable'
        assert 52 - (act.card.cost or 3) < _G_STAR


# ===== F5:息损单调边界(冻结口径反例)=====


class TestInterestMonotonicityBoundary:

    def test_f5_residual_penetration_same_tier(self, monkeypatch):
        """锁 F5(ADR-0624 §边界):52 金帧、dominance 唯一候选 3 金
        穿线笔 + 下游 C1:unlocked 恒买 2★ 核心(希儿,registry_core
        身份,ADR-0580 ③ 恒买不继承息线,店面现价)⇒ 有地板世界拒笔
        (金 52)后 C1 买入终金 49;无地板世界(变异恒放行)dominance
        3 金照买后 C1 买入终金 46。两世界轮末息档同为 4(⌊49/10⌋ =
        ⌊46/10⌋)——地板在该形态只少花钱不改息损,本锁钉住「息损严格
        减少的充分条件 = 该 visit 无残余击穿」边界,禁把单调性命题读
        成逐帧保证。"""
        c3 = _off_name(3, exclude=(_FUEL,))
        # 有地板世界(部署行为)
        st, sess, plan = _replay_plan(_snapshot(
            52, [(c3, 3, 1), ('希儿', 3, 2)]))
        assert state_of(sess).cw4_counters.get(
            'dominance_settlement_floor_reject') == 1, \
            '有地板世界应拒穿线笔(分键缺席 = 地板未生效)'
        end_gold_floor = _walk_gold(52, plan)
        # 无地板世界(变异 = 谓词恒放行)
        monkeypatch.setattr(shop, 'check_settlement_line',
                            lambda gold, cost, g_star: (True, ''))
        st2, sess2, plan2 = _replay_plan(_snapshot(
            52, [(c3, 3, 1), ('希儿', 3, 2)]))
        dom2 = [a for a in plan2
                if isinstance(a, BuyCard) and a.reason == 'dominance_buy']
        assert len(dom2) == 1, '无地板世界穿线笔应照买(病灶形态)'
        end_gold_nofloor = _walk_gold(52, plan2)
        # 两世界息档相同:地板未降低本 visit 息损(边界形态,非净优主张)
        assert end_gold_nofloor < _G_STAR < 52
        assert end_gold_nofloor // 10 == end_gold_floor // 10, (
            f'息档改变 = 冻结口径边界破(地板 {end_gold_floor} vs '
            f'无地板 {end_gold_nofloor})')
        assert end_gold_floor > end_gold_nofloor   # 地板世界只少花钱


# ===== E2E:发射级断言(ADR-0624 验收主判据,实现批载体)=====


class TestLaunchAssertionReplay:

    def test_no_dominance_emission_below_settlement_line(self):
        """发射级断言(离线重放逐 BuyCard):三个快照帧(穿线拒笔形态/
        预算买满形态/残余击穿形态)经 _rebuild_state 重建 → 部署驱动器
        决策,全部 dominance 发射笔中买后金 < g* 的发射数 = 0。"""
        c3 = _off_name(3, exclude=(_FUEL,))
        c3b = _off_name(3, exclude=(_FUEL, c3))
        cases = [
            # 形态 1:穿线笔 + 更便宜带内笔(逐笔顺序贪心)
            {'gold': 52, 'shop': [(c3, 3, 1), (_FUEL, 1, 1)]},
            # 形态 2:拒笔换更便宜候选,预算贴线花满(54→51→50)
            {'gold': 54, 'shop': [(c3, 3, 1), (c3b, 3, 1), (_FUEL, 1, 1)]},
            # 形态 3:残余击穿 visit(dominance 拒笔,下游 C1 恒买)
            {'gold': 52, 'shop': [(c3, 3, 1), ('希儿', 3, 2)]},
        ]
        dom_emissions = 0
        violations: list[str] = []
        for d in cases:
            st, _sess_r, plan = _replay_plan(_snapshot(d['gold'], d['shop']))
            gold = int(st.gold)
            for a in plan:
                if not isinstance(a, BuyCard):
                    continue
                cost = a.card.cost if a.card.cost else 3
                if a.reason == 'dominance_buy':
                    dom_emissions += 1
                    if gold - cost < _G_STAR:
                        violations.append(
                            f"gold={d['gold']} name={a.card.name} "
                            f'cost={cost} 买后={gold - cost} < g*')
                gold -= cost
        assert dom_emissions >= 2, \
            '发射笔过少 = 夹具失准(形态 1/2 应有 dominance 发射)'
        assert not violations, \
            f'dominance 发射级穿线 {len(violations)} 笔(主判据破):{violations}'
