"""prep 域实体化锁(T-120 sim 重设计 批 2 验收载体)。

出处 = T-120 方案 v2(``.debug/temp/currency_war/_archive_20260908/
t120_sim_redesign/方案.md``)§6.2 批 2 行 + 批 1 落地审
(同目录 ``落地审批1.md``)登记给批 2 的义务;义务清单 = 批 2 任务书
伴生产物 ``.debug/temp/currency_war/T-120-batch2-批2义务清单.md``。

锁的语义(测试纪律 7 自检):

- **逐动作落点锁**(验收②) = prep 动作经真 op 执行缝落在假游戏后,
  逐动作审计链相邻衔接(前一步 post 真值 == 后一步 pre 真值)且链尾
  == 状态机终态——红 = 动作落地旁路了审计或真值转移有旁路写。
- **围栏迁移等价锁**(验收③) = 同一 bench 态下,kernel
  ``select_deployments`` 直调的 up 集(映射物理槽)与真链 RunDeploy
  落地后的 deployed 终态身份一致——红 = 假环境部署语义偏离围栏
  单一源(迁移等价证据破缺)。
- **投影一致性锁**(验收②) = 生产投影链 ``_project_prep_obs`` 对已
  建模域(OpenBox/ClickSpheres/SellBench)的投影与假游戏规则真值
  逐字段一致——红 = 假游戏规则与生产投影模型分叉(两边必有一错)。
- **三保真裂口对拍显式项锁**(批 1 落地审 §2.1/§7 登记):
  ①轮岗概率表:假环境 refresh_probs 恒基线 None(建模归批 3);
  ②血购 HP 支付:LevelUp 只扣金不动 hp(环境边界申报);
  ③sold 名字源:商店 sink 卖出登记名 = 转移前状态机真值(期望帧
  陈旧不再漂)。
- **球域真值锁** = 收球金经收球动作入账、收入分解 event 分量恒 0
  (残差闸禁回潮,批 1 锁的批 2 延伸面)。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from test.conftest import SrTestContext
from test.harness.fixture_controller import enter_running_state, reset_running_state

#: prep 域代表剧本(节点类型覆盖:部署触发面 battle + 球域 reward +
#: 供给 supply;非全量,批量预算归保真度批,同批 1 口径)。
_SCRIPT: list[str] = ['battle', 'reward', 'supply']

_SEED: int = 20260910


def _bench_digest(match) -> dict[int, tuple]:
    """bench 物理槽位真值摘要(槽 → (身份, 星, 物品槽位));审计比较用。"""
    return {
        b.slot: (b.char_id, b.star, bool(b.is_item_slot))
        for b in match.state.bench if b is not None
    }


def _deployed_digest(match) -> dict[int, tuple]:
    return {
        i: (d.char_id if d is not None else None,
            d.star if d is not None else None)
        for i, d in enumerate(match.state.deployed)
    }


# ============================================================ 逐动作落点锁(验收②)


def test_prep_landing_audit_chain_links_to_terminal(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path) -> None:
    """逐动作审计链相邻衔接且链尾 == 状态机终态(方案批 2 验收②)。

    驱动 = 真 op 备战访问(实机策略器决策)落假游戏;审计由执行缝
    逐动作记录。红 = 动作旁路审计 / 旁路写真值。
    """
    from fixtures.cw_harness import fake_p1_run

    enter_running_state(test_context)
    try:
        with fake_p1_run(test_context, monkeypatch, tmp_path, _SEED,
                         node_sequence=_SCRIPT, initial_gold=30) as run:
            run.run_p1()
            audit = run.prep_audit
            assert audit, 'prep 动作审计为空(真链备战访问未发生或未落地)'
            # 链相邻衔接:前一步 post == 后一步 pre(同一状态机真值轴)。
            # 分组口径 = 回合标签(跨回合收入段是域外金动,链轴按组内)。
            groups: list[list[dict]] = []
            for e in audit:
                if groups and groups[-1][0].get('node') == e.get('node'):
                    groups[-1].append(e)
                else:
                    groups.append([e])
            for gi, group in enumerate(groups):
                for a, b in zip(group, group[1:], strict=False):
                    assert a['post'] == b['pre'], (
                        f'审计链断裂(组{gi}):{a["action"]} post != '
                        f'{b["action"]} pre')
            # 链尾 == 终态(审计覆盖全部真值转移,无旁路写)
            tail = audit[-1]['post']
            assert tail['bench'] == _bench_digest(run.match)
            assert tail['deployed'] == _deployed_digest(run.match)
            assert tail['gold'] == run.match.state.gold
    finally:
        reset_running_state(test_context, test_context.cw_match)


# ============================================================ 围栏迁移等价锁(验收③)


def test_rundeploy_landing_matches_fence_single_source() -> None:
    """RunDeploy 落地 == kernel select_deployments 同输入直调(迁移等价)。

    批 1 harness 围栏代理退役后的迁移等价证据(方案批 2 验收③):
    同一 bench/deployed/board/cap 态,假环境真链部署的终态与围栏
    纯函数 up 集一致。红 = 假环境部署语义第二实现漂移。
    """
    from fixtures.cw_fake_game.fake_match import FakeMatch
    from fixtures.cw_harness import FakeP1Run

    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_battle_calib import (
        _board_counts_of,
    )
    from sr_od.application.currency_war.kernel.cw_prep_actions import (
        RunDeploy,
    )
    from sr_od.application.currency_war.kernel.cw_state import (
        BenchChar,
    )

    m = FakeMatch(seed=41, node_sequence=['battle'])
    # 场景:3 件 bench(开局补给)+空板;换成立即可判身份的真名
    m.state.bench = [None] * 9
    names: list[str] = []
    for cid in ('希儿', '停云', '三月七'):
        ch = CHARACTERS[cid]
        names.append(cid)
        m._deal_bench_char(BenchChar(
            slot=0, char_id=cid,
            faction=(ch.factions or ['散'])[0],
            position_pref=ch.position_pref()))
    m.state.deployed = [None] * 10
    pre_bench = _bench_digest(m)

    # 围栏单一源直调(与假环境部署装配同输入构造,harness 内单一函数复用)
    up_slots = FakeP1Run.fence_up_slots_for(m)
    # 真链落地(RunDeploy 动作,经 apply_prep)
    res = m.apply_prep(RunDeploy())
    assert res.applied, 'RunDeploy 未落地(围栏计划空或装配断线)'
    # 终态 == 围栏 up 集(身份集合一致;物理槽由 kernel 落位语义承载)
    up_names = set()
    for i in up_slots:
        # fence_up_slots_for 返回物理槽位号
        up_names.add(pre_bench[i][0])
    landed_names = {d.char_id for d in m.state.deployed if d is not None}
    assert landed_names == up_names, (
        f'部署终态偏离围栏单一源:落地 {sorted(landed_names)} != '
        f'围栏 up {sorted(up_names)}')
    # 上场件已出 bench(ADR-0271 上阵即出)
    for slot in up_slots:
        assert slot not in _bench_digest(m), f'槽 {slot} 上场后未出 bench'
    # board = deployed 主阵营聚合(单一源现算)
    assert m.state.board == _board_counts_of(m.state.deployed)


# ============================================================ 投影一致性锁(验收②)


def test_projection_matches_fake_truth_on_modeled_domains() -> None:
    """生产投影链 vs 假游戏规则真值(已建模三域逐字段一致)。

    ``_project_prep_obs`` 是生产对动作后果的建模;假游戏规则是环境
    真值。两者分叉 = 两边必有一错(方案 §2.4 双账检测力②的投影半边)。
    """

    from fixtures.cw_fake_game.fake_match import FakeMatch
    from fixtures.cw_fake_game.fake_ports import FakeCwObserver

    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_prep_actions import (
        ClickSpheres,
        OpenBox,
        SellBench,
    )
    from sr_od.application.currency_war.kernel.cw_state import BenchChar

    class _PrepHost:
        """投影链宿主最小桩(_project_prep_obs 只用 self,无 ctx 依赖)。"""

        from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
            CwScreenPrep,
        )

        _project_prep_obs = CwScreenPrep._project_prep_obs

    m = FakeMatch(seed=9, node_sequence=['reward'])
    m.state.bench = [None] * 9
    ch = CHARACTERS['希儿']
    m._deal_bench_char(BenchChar(slot=0, char_id='希儿',
                                 faction=(ch.factions or ['散'])[0]))
    obs = FakeCwObserver(m).observe_prep(None, 'prep_clean').prep

    # —— SellBench 槽 1:投影 bench 摘除 + 金账回金 == 真值 ——
    gold_pre = m.state.gold
    proj = _PrepHost()._project_prep_obs(SellBench(slot=1), obs)
    res = m.apply_prep(SellBench(slot=1))
    assert res.applied
    truth = FakeCwObserver(m).observe_prep(None, 'prep_clean').prep
    assert [b.slot for b in proj.bench_chars] == [], '投影 bench 未摘除'
    assert proj.bench_chars == truth.bench_chars, (
        'SellBench 投影 bench 与真值分叉')
    assert proj.state.gold == truth.state.gold == (
        gold_pre + res.income), 'SellBench 投影金账与真值分叉'

    # —— OpenBox:投影 boxes 摘件 == 真值(箱离席) ——
    m2 = FakeMatch(seed=10, node_sequence=['reward'])
    m2.state.bench = [None] * 9
    m2.spawn_box()   # 箱占一空席(环境规则)
    obs2 = FakeCwObserver(m2).observe_prep(None, 'prep_clean').prep
    assert obs2.boxes, '场景前置:箱未出现在观察面'
    box_slot = obs2.boxes[0][0]
    proj2 = _PrepHost()._project_prep_obs(OpenBox(slot=box_slot), obs2)
    res2 = m2.apply_prep(OpenBox(slot=box_slot))
    assert res2.applied
    truth2 = FakeCwObserver(m2).observe_prep(None, 'prep_clean').prep
    assert [b[0] for b in proj2.boxes] == [b[0] for b in truth2.boxes], (
        'OpenBox 投影 boxes 与真值分叉')
    assert all(bc.char_id != '' or not bc.is_item_slot
               for bc in truth2.bench_chars), '开箱后箱仍占席(腾席规则缺)'

    # —— ClickSpheres:投影 = 保守清空申报(_project_prep_obs 注:执行器
    #    内验早停/掉箱即停 ⇒ 残球数不可静态精确预测,收敛由重观察承担)
    #    ——断言口径 = 投影清空 + 真值单调进展(残球 < 收球前),非字面
    #    相等;字面相等反而 = 假环境把早停语义建模成了全收。 ——
    m3 = FakeMatch(seed=11, node_sequence=['reward'])
    m3.spawn_balls(2)
    obs3 = FakeCwObserver(m3).observe_prep(None, 'prep_clean').prep
    assert obs3.spheres, '场景前置:球未出现在观察面'
    proj3 = _PrepHost()._project_prep_obs(ClickSpheres(max_k=3), obs3)
    res3 = m3.apply_prep(ClickSpheres(max_k=3))
    assert res3.applied
    truth3 = FakeCwObserver(m3).observe_prep(None, 'prep_clean').prep
    assert proj3.spheres == [], 'ClickSpheres 投影未按保守清空申报'
    assert len(truth3.spheres) < len(obs3.spheres), '收球零进展(球域规则断)'


# ============================================================ 三保真裂口对拍显式项


def test_refresh_probs_stay_baseline_in_fake_env() -> None:
    """裂口①:假环境轮岗概率条恒基线 None(建模归批 3,显式边界)。

    批 1 落地审 §2.1①:轮岗翻倍概率表恒 None = 基线概率,真实缺口
    已申报、归批 3 概率条建模。本锁辖「边界如实」:刷新后概率条仍
    None = 基线抽牌(非静默换真值);批 3 建模时本锁按新申报改写。
    """
    from fixtures.cw_fake_game.fake_match import FakeMatch

    from sr_od.application.currency_war.kernel.cw_state import (
        REFRESH_COST_BASE,
        RefreshShop,
    )

    m = FakeMatch(seed=13, node_sequence=['battle'])
    m.open_shop()
    assert m.state.refresh_probs is None, (
        '假环境概率条非基线 None(轮岗建模提前且未申报——批 3 义务,'
        '本批边界为恒基线)')
    m.state.gold = 50
    res = m.apply(RefreshShop(cost=REFRESH_COST_BASE))
    assert res.applied
    assert m.state.refresh_probs is None, '刷新后概率条漂移(裂口①边界破缺)'


def test_levelup_pays_gold_not_hp() -> None:
    """裂口②:血购 HP 支付在假环境结构性为零(环境边界申报)。

    simulate LevelUp 分支只扣金(cw_state.py :1508 区间,批 1 落地审
    亲核);prep 域 LevelUp 组合(clicks × 单击价)同判。hp 变化 =
    环境批回归信号,非本锁语义。
    """
    from fixtures.cw_fake_game.fake_match import FakeMatch

    from sr_od.application.currency_war.kernel.cw_prep_actions import (
        LevelUp,
    )

    m = FakeMatch(seed=17, node_sequence=['battle'])
    m.state.gold = 200
    hp_pre = m.state.hp
    level_pre = m.state.level
    res = m.apply_prep(LevelUp())
    assert res.applied, '升级未落地(金/经验面断)'
    assert m.state.hp == hp_pre, 'LevelUp 动了 hp(血购边界破缺,须回申报面)'
    assert (m.state.level > level_pre
            or m.state.xp_progress[0] > 0), '升级/经验零推进'


def test_sold_name_source_is_pre_transition_truth(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path) -> None:
    """裂口③:商店 sink 卖出登记名 = 转移前状态机真值(批 2 收敛)。

    批 1 落地审 §2.1③:登记名取自期望帧槽位,期望帧陈旧时登记名可漂。
    修后语义 = 取自状态机转移前真值;本锁以「期望帧与真值刻意错位」
    的构造场景钉死收敛(漂移形态在修前必现)。
    """
    from fixtures.cw_fake_game.fake_match import FakeMatch
    from fixtures.cw_fake_game.fake_ports import FakeActionSink

    from sr_od.application.currency_war.kernel.cw_exec_state import (
        exec_state_of,
    )
    from sr_od.application.currency_war.kernel.cw_state import (
        BenchChar,
        GameState,
        SellBench,
    )
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )

    m = FakeMatch(seed=19, node_sequence=['battle'])
    m.state.bench = [None] * 9
    m._deal_bench_char(BenchChar(slot=0, char_id='希儿', faction='?'))
    sink = FakeActionSink(m)
    session = StrategySession()
    # 轮键接线(register_round_sold 带轮键自校验;同轮形态)
    exec_state_of(session).v2_round_key = (
        m.state.plane, m.state.round_num)
    # 期望帧刻意陈旧:槽 0 指向「景元」,真值 = 希儿——修前登记名随期望帧漂
    stale_frame = GameState(plane=m.state.plane,
                            round_num=m.state.round_num)
    stale_frame.bench = [BenchChar(slot=1, char_id='景元', faction='?')]

    class _Ledger:
        total_sell = 0
        total_sell_income = 0
        buy_has_sell = False

    class _Env:
        pass

    env = _Env()
    env.state = stale_frame
    env.ledger = _Ledger()

    class _Match:
        pass

    env.match = _Match()
    env.match.session = session
    res = sink.execute_action(None, SellBench(bench_idx=0), env)
    assert res.applied
    sold = getattr(exec_state_of(session), 'v2_round_sold', None)
    assert sold == {'希儿'}, (
        f'卖出登记名非转移前真值:{sold}(裂口③收敛破缺)')


# ============================================================ 球域真值锁


def test_ball_gold_flows_via_collection_not_income_event() -> None:
    """球金 = 收球动作入账;收入分解 event 分量恒 0(残差闸禁回潮)。

    rules.py 头注 + 批 1 锁 test_income_event_component_stays_zero 的
    批 2 延伸:球金建模走收球域真值(BALL_GOLD 校准常量),不回指
    引擎 EVENT_GOLD_BY_ROUND 残差闸。
    """
    from fixtures.cw_fake_game import rules
    from fixtures.cw_fake_game.fake_match import FakeMatch

    from sr_od.application.currency_war.kernel.cw_prep_actions import (
        ClickSpheres,
    )

    m = FakeMatch(seed=23, node_sequence=['reward'])
    m.spawn_balls(2)
    gold_pre = m.state.gold
    res = m.apply_prep(ClickSpheres(max_k=2))
    assert res.applied, '收球未落地'
    gained = m.state.gold - gold_pre
    assert gained >= rules.BALL_GOLD, (
        f'收球金未入账(+{gained} < 单球 {rules.BALL_GOLD})')
    # 收入分解 event 分量仍恒 0(球金不走收入事件通道)
    inc = rules.income_for_round(m.state, m._rng_grant, None, False)
    assert inc['event'] == 0, '球金回流收入 event 分量(残差闸回潮形态)'


def test_box_open_frees_slot_and_pick_fills_char() -> None:
    """开箱腾席 + 选卡落席(环境保真件规则;方案 §2.2 F6 行)。"""
    from fixtures.cw_fake_game.fake_match import FakeMatch

    from sr_od.application.currency_war.kernel.cw_prep_actions import (
        OpenBox,
        PickBoxCard,
    )

    m = FakeMatch(seed=29, node_sequence=['reward'])
    m.state.bench = [None] * 9
    m.spawn_box()
    slot = m.boxes[0]
    occupied_pre = sum(1 for b in m.state.bench if b is not None)
    res = m.apply_prep(OpenBox(slot=slot))
    assert res.applied, '开箱未落地'
    assert m.boxes == [], '开箱后箱仍在观察面(腾席规则缺)'
    assert sum(1 for b in m.state.bench if b is not None) == occupied_pre - 1
    # 选卡:overlay 栈顶载荷 4 选项,点选后角色落席
    top = m.top_overlay('box')
    assert top is not None and len(top.payload) == 4, (
        '武装箱 overlay 选项载荷形状非 4 选 1')
    res2 = m.apply_prep(PickBoxCard(card_idx=1))
    assert res2.applied, '选卡未落地'
    assert m.top_overlay('box') is None, '选卡后 overlay 未消'
    occ_post = [b for b in m.state.bench if b is not None]
    assert any(b.char_id for b in occ_post), '选卡后无角色落席'
    # 牌池守恒:选中件 take、未选件 ret(净 0 副本差由池账自洽承载)


# ============================================================ 发射核真链锁


def test_launch_core_lands_via_real_chain(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path) -> None:
    """真发射核端到端(cw_loop.launch_prepared_battle = C1 单一发射函数)。

    方案批 2「发射帧走真 cw_loop 备战分支」的机器可判形:真发射核的
    RunDeploy+StartBattle 两发射位经执行缝落假游戏,逐动作审计在环。
    (达标臂全序的 armed 判据消费归 e2e 锁③;本锁钉发射核落地半边。)
    """
    from fixtures.cw_harness import fake_p1_run

    from test.harness.fixture_controller import (  # noqa: F401
        enter_running_state,
    )

    enter_running_state(test_context)
    try:
        with fake_p1_run(test_context, monkeypatch, tmp_path, _SEED,
                         node_sequence=['battle'], initial_gold=30,
                         archive_dir_name='launch_core') as run:
            # 开局态直驱(开局 bench 4 件/空板/cap=lv3 → 围栏必有权可上,
            # RunDeploy 与 StartBattle 两发射位均有落地语义)
            run._install_prep_patches(monkeypatch)
            from sr_od.application.currency_war.operations import cw_loop
            ok, detail = cw_loop.launch_prepared_battle(
                run._launch_host_stub(), test_context)
            names = [e['action'] for e in run.prep_audit if e['applied']]
            assert 'StartBattle' in names, (
                f'发射核 StartBattle 未落地({detail!r};落地序列 {names})')
            assert 'RunDeploy' in names, (
                f'发射核 RunDeploy 未落地({detail!r};落地序列 {names})')
    finally:
        reset_running_state(test_context, test_context.cw_match)


# ============================================================ e2e:真 op 备战全链(验收①)


def test_prep_phase_end_to_end_via_real_op(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path) -> None:
    """真 op 备战全链 e2e(方案批 2 内容行:prep 画面全链在假环境跑)。

    驱动 = 真 CwScreenPrep(lifecycle 路径,实机策略器)+ 执行缝落假
    游戏;商店域(OpenShop→run_buy_waves)走批 1 已验证链。判据:
    ①decisions 档案载 prep 动作序列(prep 域指标首次有实体真值源);
    ②逐动作审计在环且部署域有落地(围栏代理退役后的真链部署);
    ③发射面真实发生(策略出战出口或达标臂真链二者其一);
    ④缺陷流零 prep 域 invariant_break(执行缝语义与生产投影对齐)。
    """
    from fixtures.cw_harness import fake_p1_run

    enter_running_state(test_context)
    try:
        with fake_p1_run(test_context, monkeypatch, tmp_path, _SEED,
                         node_sequence=_SCRIPT, initial_gold=30) as run:
            result = run.run_p1()
        root = tmp_path / 'fake_p1'
        # ①prep 动作入生产决策档案(序列化键 = __type__,schema.serialize_action)
        dec_rows = [json.loads(x) for x in
                    (root / 'decisions.jsonl').read_text(
                        encoding='utf-8').splitlines() if x.strip()]
        prep_acts = [a for row in dec_rows for a in (row.get('actions') or [])
                     if isinstance(a, dict)
                     and a.get('__type__', '') in (
                         'RunDeploy', 'SellBench', 'DeployMove', 'LevelUp',
                         'ClickSpheres', 'OpenBox', 'StartBattle', 'RunEquip')]
        assert prep_acts, (
            'decisions 档案无 prep 域动作(prep 画面全链未在假环境跑)')
        # ②真链部署落地(围栏代理退役的载体面)
        assert run.prep_audit, 'prep 审计为空(执行缝未在环)'
        dep_events = [e for e in run.prep_audit
                      if e['action'].startswith('RunDeploy')
                      and e['applied']]
        assert dep_events, '无 RunDeploy 落地(部署域未实体化)'
        # ③armed 判据核真实消费(达标臂面可达;发射核落地归
        # test_launch_core_lands_via_real_chain 专项)
        assert result.armed_evaluated, (
            'armed 判据核未被消费(达标臂面未接通)')
        # ④缺陷流零 prep 域伪影
        defect_file = root / 'defect_ledger.jsonl'
        if defect_file.exists():
            rows = [json.loads(x) for x in
                    defect_file.read_text(encoding='utf-8').splitlines()
                    if x.strip()]
            prep_defects = [r for r in rows
                            if r.get('kind') == 'invariant_break'
                            and r.get('reader_source', '') in (
                                'paddle_action_audit',)]
            assert not prep_defects, (
                f'prep 域即拍对拍伪影 {len(prep_defects)} 行'
                f'(执行缝与生产对拍面分叉):'
                f'{[r.get("expected") for r in prep_defects[:3]]}')
    finally:
        reset_running_state(test_context, test_context.cw_match)
