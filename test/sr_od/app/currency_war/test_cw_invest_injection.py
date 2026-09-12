"""投资剧本迁装锁(T-204;T-120 批 3 落地审 F1 立项的独立实施批)。

出处 = T-120 方案 v2(``.debug/temp/currency_war/_archive_20260908/
t120_sim_redesign/方案.md``,**易失产物**)§6.1 处置表「投资注入」行
(剧本 → 假游戏浮层栈/持卡注入,替换 engine_p1 装配点)+ §6.2 批 3
判据③「投资剧本注入假局 vs 实机带卡局分布对拍在带」;立项凭据 =
批 3 落地审 ``reviews/T-120-batch3-r1.md`` F1 条。

锁的语义(测试纪律 7 自检):

- **迁装锁** = SimInvestProfile 剧本经 FakeMatch 装配后,日程点
  (plane, round) 备战期收入后压 'invest' 浮层(3 候选实机屏语义,
  剧本名在负载内)、``pick_invest_strategy`` 选卡承接 = 持卡登记
  (state.active_strategies,handler 去重语义)+ instant_gold 选卡时点
  入账(生产游戏引擎同点,engine_p1 注入段同位)+ 弹栈。红 = 剧本
  注入面缺位或选卡承接旁路状态机。
- **持卡收入锁** = rules.income_for_round 消费持卡聚合(单一源 =
  kernel ``aggregate_economy``/``interest_cap_resolved``):息帽覆写
  (含买断制 0 = 有效覆写,ADR-0598 陷阱)+ flat 息 + gold_per_node
  ('invest' 键,engine_p1 账本行形状同构)。期望值全部注册表现算
  (纪律 9),红 = 假环境收入面与 kernel 聚合链分叉。
- **零漂移锁** = 无剧本路径(缺省)收入分解恒 4 键、无 'invest' 键、
  无 invest 浮层、state.active_strategies 恒空、环境指纹
  invest_injected=0——与既有保真度锁(轨迹锚)共同承载「缺省主路径
  逐位零漂移」契约(engine_p1 注入参数同款纪律)。
- **确定性锁** = 同 seed + 同剧本两次全程重放,收入分解/金轨迹/持卡
  演进逐位相等(重放 = seed + 环境指纹契约的注入域扩形)。
- **0e 分支锁** = harness 外循环分支序按 outer_loop §2.2 表序在 0i
  之前检 0e(投资策略三选一),真 ``CwScreenInvestStrategy`` op 驱动
  (决策半边 = 剧本名直注入,直注入语义 = cw_sim_invest 模块头
  「显式点名 = 直注入」契约),session/state 双侧持卡登记落。
- **对拍锚** = 注入批三面:①日程点持卡落位;②收入 'invest' 分量
  合计 = 注册表期望现算(gold_per_node × 持有轮数);③对拍件形状
  (bands_from_trajectories 单一源)。分布带 vs 实机带 = 离线 runner
  (批报告类,不进测试网;实机档案读数当断言锚违测试纪律)。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    enter_running_state,
    reset_running_state,
)

#: 迁装锁种子(显式固定保确定性;本批新段,与既有锁种子集无重叠)。
_SEED: int = 204001

#: 对拍锚批种子(3 局最小批;覆盖日程多轮触发与位面内持有演进)。
_ANCHOR_SEEDS: tuple[int, ...] = (204011, 204012, 204013)

#: 迁装锁代表剧本:3 节点日程 + (1,3) 选卡(实机主选卡时点,extract
#: 分布 (1,3)=136/145 局);环境带 轮岗(条件位既有锁域的注入侧对位)。
_PROFILE_SCRIPT: list[str] = ['battle', 'battle', 'battle', 'battle']


def _profile():
    from sr_od.application.currency_war.sim.cw_sim_invest import (
        SimInvestProfile,
    )
    return SimInvestProfile(active_env='轮岗', picks=((1, 3, '开源节流'),))


# ============================================================ 迁装锁


def test_invest_profile_schedules_overlay_and_pick_lands_held_card() -> None:
    """剧本日程 → 浮层压栈 → 选卡承接 = 持卡 + instant_gold + 弹栈。

    红时语义:F1 缺口本体——FakeMatch 无 invest_profile 装配位、无
    pick_invest_strategy 承接(迁装前 TypeError/AttributeError)。
    """
    from fixtures.cw_fake_game.fake_match import FakeMatch

    from sr_od.application.currency_war.kernel.cw_investments import (
        economy_effect_of,
    )
    from sr_od.application.currency_war.sim.cw_sim_invest import (
        SimInvestProfile,
    )

    m = FakeMatch(seed=_SEED, node_sequence=list(_PROFILE_SCRIPT),
                  invest_profile=SimInvestProfile(
                      active_env='', picks=((1, 3, '开源节流'),)))
    # r1/r2:日程未到,无浮层、无持卡
    for _ in range(2):
        inc = m.apply_income()
        assert 'invest' not in inc
        assert m.top_overlay('invest') is None, '日程未到不应压选卡浮层'
        m.advance_node()
    # r3:日程点 → 收入后压浮层,剧本名在负载内(实机 3 候选屏语义)
    m.apply_income()
    frame = m.top_overlay('invest')
    assert frame is not None, '(1,3) 日程点未压选卡浮层(迁装缺位)'
    assert '开源节流' in frame.payload, '剧本名不在浮层负载内'
    # 选卡承接:非法名显式拒绝;剧本名 = 持卡 + instant_gold + 弹栈
    assert not m.pick_invest_strategy('不在负载的名字'), \
        '负载外名被采纳(环境承接缺验证门)'
    gold_pre = m.state.gold
    assert m.pick_invest_strategy('开源节流'), '剧本选卡被环境拒绝'
    assert m.state.active_strategies == ['开源节流'], '持卡未登记(handler append 语义)'
    assert m.state.gold == gold_pre + economy_effect_of('开源节流').instant_gold, \
        'instant_gold 未按选卡时点入账(注册表值)'
    assert m.top_overlay('invest') is None, '选卡后浮层未弹栈'
    # r4:日程已消费,不再重复压栈;持卡去重(handler 语义)
    m.advance_node()
    m.apply_income()
    assert m.top_overlay('invest') is None, '已消费日程点重复压栈'


def test_invest_pick_dedup_and_env_carry() -> None:
    """重名不重复入列(handler 去重语义)+ 剧本环境名落 active_env 条件位。"""
    from fixtures.cw_fake_game.fake_match import FakeMatch

    from sr_od.application.currency_war.sim.cw_sim_invest import (
        SimInvestProfile,
    )

    m = FakeMatch(seed=_SEED, node_sequence=['battle'],
                  invest_profile=SimInvestProfile(
                      active_env='轮岗', picks=((1, 1, '开源节流'),)))
    assert m.active_env == '轮岗', '剧本环境名未落环境事实位(select_invest_env 同字段)'
    m.apply_income()
    frame = m.top_overlay('invest')
    assert frame is not None
    assert m.pick_invest_strategy('开源节流')
    m.push_overlay('invest', ['开源节流'])
    gold_pre = m.state.gold
    assert m.pick_invest_strategy('开源节流'), '已持名选卡被拒(实机屏可重发已持名)'
    assert m.state.active_strategies == ['开源节流'], '重名重复入列(去重语义破缺)'
    assert m.state.gold == gold_pre, '重名选卡重复入账 instant_gold'


# ============================================================ 畸形剧本防御锁(T-209/G5)


def test_same_key_multi_pick_assembly_rejects() -> None:
    """装配侧校验锁:同键多 pick = 畸形剧本,装配拒绝(fail-loud)。

    行为定义(T-209 先写测试):SimInvestProfile 契约「同一 (plane, round)
    至多一条」(主仓 docstring);装配位 FakeMatch.__init__ 对畸形输入
    (同键两条)必须显式拒绝——原实现经 dict 推导静默保留后名,畸形
    输入被折叠成「合法剧本」继续重放,污染对拍/确定性读数且无披露。
    拒绝(不静默去重)的裁决:畸形剧本 = 提取端 bug 的信号,吞掉它 =
    把上游缺陷藏进装配层;调用人应修提取,不是让装配替他选一张。
    """
    from fixtures.cw_fake_game.fake_match import FakeMatch

    from sr_od.application.currency_war.sim.cw_sim_invest import (
        SimInvestProfile,
    )

    for bad in (((1, 3, '开源节流'), (1, 3, '按劳分配')),   # 同键异名
                ((1, 3, '开源节流'), (1, 3, '开源节流'))):  # 同键同名重复
        with pytest.raises(ValueError, match=r'同键多.*pick|3.*3') as ei:
            FakeMatch(seed=_SEED, node_sequence=list(_PROFILE_SCRIPT),
                      invest_profile=SimInvestProfile(
                          active_env='', picks=bad))
        # 报错点名冲突键(可行动:提取端按键定位坍缩行)
        assert '1' in str(ei.value) and '3' in str(ei.value), \
            '报错未点名冲突 (plane, round) 键'


def test_cross_key_same_name_assembly_still_legal() -> None:
    """反过度拒绝守卫:跨键重名 = 契约内合法(主仓 docstring「重名跨轮
    出现时按 handler 去重语义忽略」),装配不得误拒;运行期由既有
    handler 去重语义(重名不重复入列/不重复入账)承接。"""
    from fixtures.cw_fake_game.fake_match import FakeMatch

    from sr_od.application.currency_war.sim.cw_sim_invest import (
        SimInvestProfile,
    )

    m = FakeMatch(seed=_SEED, node_sequence=['battle', 'battle', 'battle'],
                  invest_profile=SimInvestProfile(
                      active_env='',
                      picks=((1, 1, '开源节流'), (1, 3, '开源节流'))))
    m.apply_income()
    assert m.pick_invest_strategy('开源节流'), '首轮选卡被拒'
    m.advance_node()
    m.apply_income()
    m.advance_node()
    m.apply_income()
    # r3 重发已持名:推侧跳过(已持不压浮层),持卡不重复
    assert m.top_overlay('invest') is None, '已持名日程点重复压选卡浮层'
    assert m.state.active_strategies == ['开源节流'], '跨键重名重复入列'


# ============================================================ 持卡收入锁


def _income_with_held(gold: int, held: list[str]) -> dict:
    from fixtures.cw_fake_game import rules
    from fixtures.cw_fake_game.fake_match import FakeMatch

    m = FakeMatch(seed=_SEED, node_sequence=['battle'])
    m.state.gold = gold
    m.state.active_strategies = list(held)
    return rules.income_for_round(m.state, m._rng_grant, None, False)


def test_held_cards_interest_cap_override_from_registry() -> None:
    """息帽覆写走 kernel 聚合单一源;买断制 0 = 有效覆写(ADR-0598 陷阱)。

    期望值全部注册表现算(纪律 9):cap = interest_cap_resolved(
    aggregate_economy(held).interest_cap_override)。
    """
    from sr_od.application.currency_war.kernel.cw_economy import (
        DEFAULT_INTEREST_CAP,
        interest,
        interest_cap_resolved,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        aggregate_economy,
        economy_effect_of,
    )

    # 注册表锚自检(锁红时先区分「注册表值变了」还是「消费链断」)
    assert economy_effect_of('开源节流').interest_cap_override == 9
    assert economy_effect_of('利息上调').interest_cap_override == 10
    assert economy_effect_of('买断制').interest_cap_override == 0
    gold = 100
    for held in (['开源节流'], ['利息上调'], ['买断制'],
                 ['开源节流', '利息上调']):
        inc = _income_with_held(gold, held)
        cap = interest_cap_resolved(
            aggregate_economy(list(held)).interest_cap_override)
        assert inc['interest'] == interest(gold, cap), \
            f'{held}: 息帽覆写未走 kernel 聚合单一源'
    assert _income_with_held(gold, ['买断制'])['interest'] == 0, \
        '买断制 cap=0 被真值折叠回缺省(ADR-0598 陷阱复潮)'
    # 无覆写持卡(按劳分配)→ 缺省帽
    inc = _income_with_held(gold, ['按劳分配'])
    assert inc['interest'] == interest(gold, DEFAULT_INTEREST_CAP)


def test_held_cards_flat_interest_and_gold_per_node() -> None:
    """flat 息与 gold_per_node:'invest' 键只在有持卡且有值时出现
    (engine_p1 账本行形状同构,缺省路径行形状不变)。"""
    from sr_od.application.currency_war.kernel.cw_economy import interest
    from sr_od.application.currency_war.kernel.cw_investments import (
        economy_effect_of,
    )

    assert economy_effect_of('狸财经狸').interest_flat_per_node == 2
    assert economy_effect_of('按劳分配').gold_per_node == 1
    gold = 100
    inc = _income_with_held(gold, ['狸财经狸'])
    assert inc['interest'] == interest(gold) + 2, 'flat 息未入账(与息帽无关语义)'
    assert 'invest' not in inc
    inc2 = _income_with_held(gold, ['按劳分配'])
    assert inc2['invest'] == 1, "gold_per_node 未落 'invest' 键(engine 账本行形状)"
    # 复合:flat + per_node 同现
    inc3 = _income_with_held(gold, ['狸财经狸', '按劳分配'])
    assert inc3['interest'] == interest(gold) + 2
    assert inc3['invest'] == 1


def _income_state(node: str, rn: int, streak: int, held: list[str],
                  prev_node: str | None = None,
                  prev_lost: bool = False) -> dict:
    """持卡收入锁构造器(node/轮/连胜可控;金库恒 0 = 利息零发,
    连胜分量隔离断言)。"""
    from fixtures.cw_fake_game import rules
    from fixtures.cw_fake_game.fake_match import FakeMatch

    m = FakeMatch(seed=_SEED, node_sequence=['battle'])
    m.state.gold = 0
    m.state.node_type = node
    m.state.round_num = rn
    m.state.streak = streak
    m.state.active_strategies = list(held)
    return rules.income_for_round(m.state, m._rng_grant,
                                  prev_node, prev_lost)


def test_held_win_reward_mult_scales_streak_component() -> None:
    """伟大征服 ×3 施于假环境连胜分量(fields.md §4.1「收入修饰」:
    施于连胜分量**含奖励轮**;T-64 切源后与引擎消费缝同源
    round_start_income,GameState「sim 修正随之」桶闭合)。

    补给槽零发、败补槽按 ADR-0439 类型表连胜槽替换(均不乘倍率);
    期望值注册表现算(纪律 9,kernel _streak_component 同式)。红 =
    假环境连胜面与 kernel 单一源分叉(切源回退或倍率未入缝)。"""
    from sr_od.application.currency_war.kernel.cw_economy import (
        LOSS_GOLD_BY_NODE,
        streak_gold,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        economy_effect_of,
    )

    # 注册表锚自检(锁红时先区分「注册表值变了」还是「接线断了」)
    assert economy_effect_of('伟大征服').win_reward_mult == 3.0
    mult = economy_effect_of('伟大征服').win_reward_mult
    # 常规战斗槽与奖励轮 ×3(奖励轮含 counter0=1 表值同乘)
    assert _income_state('battle', 5, 2, ['伟大征服'])['streak'] \
        == int(round(streak_gold(2) * mult)), '常规战斗槽未乘倍率'
    assert _income_state('reward', 8, 3, ['伟大征服'])['streak'] \
        == int(round(streak_gold(3) * mult)), '奖励轮未乘倍率(fields §4.1)'
    assert _income_state('reward', 2, 0, ['伟大征服'])['streak'] \
        == int(round(streak_gold(0) * mult)), '奖励轮 counter0 表值未乘倍率'
    # 补给槽零发、败补槽类型表替换(连胜槽替换语义,倍率不生效)
    assert _income_state('supply', 5, 2, ['伟大征服'])['streak'] == 0, \
        '补给轮连胜槽被倍率路径改写'
    assert _income_state('battle', 4, -1, ['伟大征服'],
                         prev_node='encounter',
                         prev_lost=True)['streak'] \
        == LOSS_GOLD_BY_NODE['encounter'], '败补槽被误乘倍率'
    # 无持卡缺省 = 纯表值(mult 恒 1.0,逐位等价零漂移)
    assert _income_state('battle', 5, 2, [])['streak'] == streak_gold(2)


def test_default_path_income_shape_unchanged() -> None:
    """零漂移锁:无持卡收入恒 4 键、无 'invest' 键;无剧本装配面全中性。"""
    from fixtures.cw_fake_game.fake_match import FakeMatch

    from sr_od.application.currency_war.kernel.cw_economy import interest

    inc = _income_with_held(100, [])
    assert set(inc) == {'base', 'interest', 'streak', 'event'}, \
        '缺省路径收入分解键形状漂移'
    assert inc['interest'] == interest(100)

    m = FakeMatch(seed=_SEED, node_sequence=['battle'])
    assert m.state.active_strategies == [], '缺省路径出现持卡'
    m.apply_income()
    assert m.top_overlay('invest') is None, '缺省路径压出了选卡浮层'
    fp = m.env_fingerprint()
    assert fp.get('invest_injected') == 0, '缺省路径环境指纹未标未注入'


def test_same_seed_profile_replay_is_deterministic() -> None:
    """确定性锁:同 seed + 同剧本两次重放,金轨迹/收入分解/持卡演进逐位相等。"""
    from fixtures.cw_fake_game.fake_match import FakeMatch

    from sr_od.application.currency_war.sim.cw_sim_invest import (
        SimInvestProfile,
    )

    prof = SimInvestProfile(active_env='轮岗',
                            picks=((1, 2, '开源节流'), (1, 4, '按劳分配')))

    def _replay() -> tuple[list[int], list[dict], list[list[str]]]:
        m = FakeMatch(seed=_SEED, node_sequence=list(_PROFILE_SCRIPT),
                      invest_profile=prof)
        golds: list[int] = []
        incomes: list[dict] = []
        helds: list[list[str]] = []
        for _round in range(1, len(_PROFILE_SCRIPT) + 1):
            m.apply_income()
            golds.append(m.state.gold)
            frame = m.top_overlay('invest')
            if frame is not None:
                m.pick_invest_strategy(frame.payload[0])
            incomes.append(dict(m.last_income_breakdown))
            helds.append(list(m.state.active_strategies))
            m.advance_node()
        return golds, incomes, helds

    g1, i1, h1 = _replay()
    g2, i2, h2 = _replay()
    assert g1 == g2 and i1 == i2 and h1 == h2, '同 seed 同剧本重放漂移'
    assert h1[1] == ['开源节流'] and h1[3] == ['开源节流', '按劳分配'], \
        '剧本日程未按 (plane, round) 落位'


# ============================================================ 0e 分支锁(真 op)


def test_branch_order_drives_invest_pick_op(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path) -> None:
    """harness 0e 分支:真 ``CwScreenInvestStrategy`` 驱动,剧本名直注入,
    session/state 双侧持卡落(§2.2 表序 0e 先于 0i 先于 1)。"""
    from fixtures.cw_harness import fake_p1_run

    enter_running_state(test_context)
    try:
        with fake_p1_run(test_context, monkeypatch, tmp_path, _SEED,
                         node_sequence=['battle', 'battle'],
                         initial_gold=60,
                         invest_profile=_profile()) as run:
            # r1:日程 (1,3) 未到,无 0e;3 节点局验证 r3 触发与双侧登记
            r1 = run.run_round_branch_order(monkeypatch)
            assert '0e_invest_pick' not in r1['dispatch']
        with fake_p1_run(test_context, monkeypatch, tmp_path, _SEED,
                         node_sequence=['battle', 'battle', 'battle'],
                         initial_gold=60,
                         invest_profile=_profile()) as run:
            run.run_round_branch_order(monkeypatch)
            run.run_round_branch_order(monkeypatch)
            r3 = run.run_round_branch_order(monkeypatch)
            assert r3['dispatch'][0] == '0e_invest_pick', \
                f"日程点回合未派 0e 分支(序表缺位): {r3['dispatch']}"
            assert run.match.state.active_strategies == ['开源节流'], \
                '环境侧持卡未落(状态机真值)'
            sess_held = list(run.cw_match.session.active_strategies)
            assert sess_held == ['开源节流'], \
                f'会话侧持卡未落(生产 op 尾块 append 域): {sess_held}'
            assert run.match.top_overlay('invest') is None
    finally:
        reset_running_state(test_context, test_context.cw_match)


# ============================================================ 对拍锚


def test_injected_batch_anchor_schedule_effects_bands(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path) -> None:
    """注入批三面锚(分布带 vs 实机 = 离线 runner,不进测试网):
    ①日程点持卡落位;②'invest' 收入分量合计 = 注册表期望现算;
    ③对拍件形状(bands 单一源)。"""
    from fixtures.cw_harness import (
        bands_from_trajectories,
        fake_p1_run,
    )

    from sr_od.application.currency_war.kernel.cw_investments import (
        economy_effect_of,
    )
    from sr_od.application.currency_war.sim.cw_sim_invest import (
        SimInvestProfile,
    )

    # 代表剧本 = 实机带卡局高频形态:(1,3) 经济卡 + (1,7) 每节点金卡
    # (extract 分布:主选卡 (1,3);次选卡稀有档以 (1,7) 代表内轮持卡演进)
    prof = SimInvestProfile(
        active_env='',
        picks=((1, 3, '开源节流'), (1, 7, '按劳分配')))
    script = ['battle'] * 8
    per_game: list = []
    enter_running_state(test_context)
    try:
        for i, seed in enumerate(_ANCHOR_SEEDS):
            with fake_p1_run(test_context, monkeypatch, tmp_path, seed,
                             node_sequence=script, initial_gold=30,
                             archive_dir_name=f'anchor_{seed}_{i}',
                             invest_profile=prof) as run:
                res = run.run_p1()
                per_game.append((run.match, res))
    finally:
        reset_running_state(test_context, test_context.cw_match)

    rounds_held_gold_per_node = 0
    per_node_gold = economy_effect_of('按劳分配').gold_per_node
    for m, res in per_game:
        # ①日程点持卡落位(终态;逐轮落位由确定性锁辖,本锚锁终态 + 分量)
        assert '开源节流' in m.state.active_strategies
        assert '按劳分配' in m.state.active_strategies
        # ②'invest' 分量合计 = 注册表期望现算:注入点在收入后(engine_p1
        #    同位)→ (1,7) 选卡当轮收入不含量值,r8 收入起按劳分配生效
        #    → 合计 = gold_per_node × 1
        invest_total = 0
        for r in sorted(res.rounds):
            invest_total += res.rounds[r]['income'].get('invest', 0)
        assert invest_total == per_node_gold, (
            f"'invest' 收入分量合计 {invest_total} ≠ 注册表期望 "
            f'{per_node_gold}(选卡次轮起 × gold_per_node)')
        rounds_held_gold_per_node += invest_total
    assert rounds_held_gold_per_node == per_node_gold * len(_ANCHOR_SEEDS)
    # ③对拍件形状(bands 单一源;与保真基线锁同一 helper)
    bands = bands_from_trajectories(
        [res.trajectory() for _m, res in per_game])
    assert set(bands) == set(range(1, len(script) + 1))
    for band in bands.values():
        med, p90 = band['gold']
        assert med is not None and p90 is not None and med <= p90


def test_fake_match_income_breakdown_exposed_for_anchor() -> None:
    """FakeMatch 逐回合收入分解留证位(对拍锚/离线 runner 的真值源;
    apply_income 返回值在分支驱动路径被 _open_branch_round 消费后
    需可回读)。"""
    from fixtures.cw_fake_game.fake_match import FakeMatch

    m = FakeMatch(seed=_SEED, node_sequence=['battle'])
    m.apply_income()
    assert isinstance(m.last_income_breakdown, dict) and 'base' in \
        m.last_income_breakdown, '收入分解留证位缺位'
