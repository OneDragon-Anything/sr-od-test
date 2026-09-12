"""CW 商店决策测试(#8):decide_shop 七面代表行 + refresh 真值 +
rejects fail-closed 代表。

收缩注记(CUT9 二次收缩:原 13 测试→8 测试;同分支变体砍,git 可复活):
- 买面留 M2 线成员义务买 1 代表(金不足不买/支配买两变体砍);
- 卖面(M4 腾席)/升级面(整买纪律)/刷新面(合格集空 fail-closed)
  各留 1 代表;M6 压库面与 ev_arm 值域护栏变体砍;
- rejects 留词表外 fail-closed + R197 同槽防线两代表;
- refresh 真值留多波对拍金闭合(金钱净守恒锚)+ refresh_effective
  真值表;刷费 0/None 分道行砍(None 口径由对账跳过路径承载)。

覆盖面:
- decide_shop 真值:买面(M2 线成员义务买)/卖面(M4 腾席卖出+单帧
  闭环)/升级面(D-BUYNOTE 整买纪律行为)/刷新面(合格集空
  fail-closed 不刷)各 1 代表;
- refresh 真值(自 test_cw_shop_refresh 并入):多波刷新对拍金闭合
  (刷费单次计数,金钱不变量)+ refresh_effective 判据纯函数真值表;
- rejects:词表外动作 shop_action_op_for 断言炸出(ADR-0517 决策 9
  fail-closed)+ R197 同槽防线(同一 bench_idx 至多一笔卖出,结构性
  保证;R197 症3 防线继任不变量)。

来源:shop_line(mv 主干,保留代表行;spend_unified 段迁 #9)/
shop_refresh 核三行(2026-09-09 套件重建批 A,#8;来源文件已退役;
CUT9 二次收缩见收缩注记)。其余历史锁已退役(git 可复活)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_vocab import (
    BENCH_CAPACITY,
    BuyCard,
    LevelUpShop,
    PickEvent,
    RefreshShop,
    SellBench,
)
from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import (
    expected_gold_after_actions,
    refresh_effective,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_card as _card,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_comp as _comp,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_decide as _decide,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_members as _members,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_session as _session,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_state as _state,
)

# ==================== ① decide_shop 七面代表行(每面判据式行为锚)====================


class TestCriteriaShopFaces:

    def test_buy_face_m2_line_member(self):
        """买面:M2 线成员义务买入(黑板店面 → BuyCard,reason 可归因)。"""
        comp = _comp()
        m = _members(comp)[0]
        st = _state(gold=30, shop=[_card(m, cost=3)])
        acts = _decide(st, _session(comp))
        buys = [a for a in acts if isinstance(a, BuyCard)]
        assert any(b.card.name == m for b in buys)
        assert all(b.reason == 'm2_line_member' for b in buys
                   if b.card.name == m)

    def test_sell_face_m4_fuel_sell_when_bench_full(self):
        """卖面:M4 腾席——bench 满 ∧ 有线成员可买 ⇒ 卖 1★ 零重叠件。"""
        comp = _comp()
        members = _members(comp)
        m0 = members[0]
        bench = [_bc(m) for m in members[1:]]     # 缺 m0,其余占满
        while len(bench) < BENCH_CAPACITY:
            bench.append(_bc(f'填充件{len(bench)}'))
        st = _state(gold=30, shop=[_card(m0, cost=3)], bench=bench,
                    deployed=[_bc('板上件锚', slot=1)])   # T-32 守卫前置
        acts = _decide(st, _session(comp))
        sells = [a for a in acts if isinstance(a, SellBench)]
        buys = [a for a in acts if isinstance(a, BuyCard)]
        assert sells and buys          # 先腾席后买入,单帧闭环

    def test_levelup_face_batch_discipline(self):
        """升级面:D-BUYNOTE 整买纪律——整批够升级才放行(散买拦截)。
        (夹具补 hp=100:候选③批起 M3 消费血预算停升级门,门对 hp 无真值
        帧 fail-closed 拒升级——旧夹具在门未接线的栈上写就,真值帧才是
        本锁要钉的语义。)"""
        # arm1_existence 需板满(10)+ bench 等待件共享阵营/流派:
        # 板/bench 同名件(爻光)必然共享 ⇒ 谓词真
        deployed = [_bc('爻光') for _ in range(10)]
        bench = [_bc('爻光')]
        # 整批不够:金 3 < clicks×cost
        st = _state(gold=3, bench=bench, deployed=deployed, level=3,
                    xp=(0, 4), hp=100)
        acts = _decide(st, _session(_comp()))
        assert not [a for a in acts if isinstance(a, LevelUpShop)]
        # 整批够:金 8 ≥ 1 click × 4(LEVEL up xp(0,4) → 1 click)
        st2 = _state(gold=8, bench=bench, deployed=deployed, level=3,
                     xp=(0, 4), hp=100)
        acts2 = _decide(st2, _session(_comp()))
        lv = [a for a in acts2 if isinstance(a, LevelUpShop)]
        assert lv and all(a.auth_basis.startswith('m3_batch:')
                          for a in lv)   # 三臂分键后带臂后缀(可归因)

    def test_refresh_face_fail_closed(self):
        """刷新面 fail-closed(真空合格集):全体线成员 2★ 成型 ⇒ 合格
        集空 ⇒ 不刷 + ``shop_r1_no_chaseable_member`` 分键(P40 R0-1;
        ADR-0516 形式二)。

        锁语义重推(ADR-0571):旧帧钉的「高费成员不可追 ⇒
        no_chaseable_member」是 inf 污染缺陷的病理形态——部分不可追被
        错判全空;修复后「空」只剩真空来源,帧改全 2★ 成型钉面。"""
        comp = _comp()
        bench = [_bc(m, star=2) for m in _members(comp)]
        st = _state(gold=60, bench=bench)
        sess = _session(comp)
        acts = _decide(st, sess)
        assert state_of(sess).cw4_counters.get('shop_r1_no_chaseable_member', 0) >= 1
        assert not [a for a in acts if isinstance(a, RefreshShop)]


# ==================== ② rejects:fail-closed 代表行 ====================


class TestShopRejects:

    def test_word_table_violation_fail_closed(self):
        """词表外动作(PickEvent/任意类型)⇒ shop_action_op_for 断言炸出
        (ADR-0517 决策 9:非法返回 = 策略器 bug 响亮暴露,禁静默跳过——
        旧 §3.3 截断 fail-closed 的单动作继任形态)。"""
        from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
            shop_action_op_for,
        )
        with pytest.raises(AssertionError, match='词表外'):
            shop_action_op_for(PickEvent(option_idx=0))
        with pytest.raises(AssertionError, match='词表外'):
            shop_action_op_for(object())   # type: ignore[arg-type]

    def test_no_same_slot_double_sell_structurally(self):
        """R197 场景(金 0 + 满席 + 缺件):驱动器全部卖出对同一
        bench_idx 至多一笔——单动作结构保证,无丢弃计数参与。
        (R197 症3 防线语义重推:波批多动作「先到先得丢弃 + ev_conflict_
        dropped 计数」随单动作迁移退役,继任不变量 = 结构性至多一笔。)"""
        comp = _comp()
        members = _members(comp)
        m0 = members[0]
        bench = [_bc(m, slot=i + 1) for i, m in enumerate(members[1:])]
        while len(bench) < BENCH_CAPACITY:
            bench.append(_bc(f'填充件{len(bench)}', slot=len(bench) + 1))
        st = _state(gold=0, shop=[_card(m0, cost=3)], bench=bench,
                    deployed=[_bc('板上件锚', slot=1)])   # T-32 守卫前置
        sess = _session(comp)
        acts = _decide(st, sess)
        sells = [a for a in acts if isinstance(a, SellBench)]
        assert sells, 'M4 腾席卖出应存在'
        idxs = [s.bench_idx for s in sells]
        assert len(idxs) == len(set(idxs)), idxs   # 无同 idx 双卖
        assert 'ev_conflict_dropped' not in state_of(sess).cw4_counters


# ==================== ③ refresh 真值(自 test_cw_shop_refresh 并入)====================


def test_multiwave_refresh_expected_closes_per_accounting():
    """多波刷新对拍闭合语义(瘦身后;原自抄复刻主体已删)。

    波间语义(3 波场景,开店金 60;刷费 2/波,买 3/波 ×3):对拍期望 =
    开店金 − **逐波执行侧花金合计**(每次刷新的当次刷价只计一次) =
    60 − (3+2+3+2+3) = 47 = 实读。修复前口径(末波重读金当基线 +
    跨波刷新费重复扣)= 43,差 4 = 波1+波2 刷费重复扣——真函数若改回
    「以中段重读金为基线」类口径,本断言的锚值即不再闭合。
    """
    gold_open = 60
    spend_whole_run = 3 + 2 + 3 + 2 + 3   # 买+刷×2波 + 末波买(场景参数,非复刻 op 分支)
    assert expected_gold_after_actions(gold_open, spend_whole_run, 0) == 47, (
        '多波花金合计口径下对拍期望应与实读闭合(刷费单次计数)')
    # 卖入腿同式可见(对拍口径单一源:− 花出 + 卖入)
    assert expected_gold_after_actions(gold_open, spend_whole_run, 5) == 52


def test_refresh_effective_truth_table():
    """集合不等=生效;全同=未生效嫌疑;任一侧含未识别槽('')或空读=None 不猜。"""
    assert refresh_effective(['A', 'B', 'C', 'D', 'E'],
                             ['B', 'A', 'C', 'D', 'E']) is False  # 集合语义:同 5 牌换位=全同(DESIGN §2.5 口径;真刷出同 5 牌是组合级小概率,判据容忍)
    assert refresh_effective(['A', 'B', 'C', 'D', 'E'],
                             ['A', 'B', 'C', 'D', 'E']) is False   # 全同=未生效
    assert refresh_effective(['A', 'B', 'C', 'D', 'E'],
                             ['A', '', 'C', 'D', 'E']) is None     # 刷后读含未识别槽
    assert refresh_effective(['A', 'B', 'C', '', 'E'],
                             ['A', 'B', 'C', 'D', 'E']) is None    # 刷前(plan 帧)含未识别槽
    assert refresh_effective([], ['A', 'B']) is None               # 空读不可判
    assert refresh_effective(['A'], []) is None

