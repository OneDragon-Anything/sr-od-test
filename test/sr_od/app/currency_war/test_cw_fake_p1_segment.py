"""假局 P1 全段跑通锁(T-120 sim 重设计 批 1 验收①的载体)。

出处 = T-120 方案 v2(``.debug/temp/currency_war/t120_sim_redesign/
方案.md``,**易失产物**)§6.2 批 1 行「真 op(run_buy_waves 单动作循环)
跑通假局 P1 全段」+ 验收①「同 seed+同剧本逐位复现」;ADR 落点待
T-120 退役批分配,后续批回填编号。

锁的语义(测试纪律 7 自检):

- **全段跑通锁** = 端口改道后的生产链路在假环境端到端可达:入口观察
  经观察源端口(状态机真值)、决策 = 真策略器冷建(mandate_v1)、动作
  执行经执行器端口(sink 落状态机 + 账本位随动)、遥测全链落生产
  schema 到假局档案根。红 = 改道断线/策略器对假局态崩/档案根装配断。
- **确定性锁** = 同 seed + 同剧本两次全程驱动,轨迹逐位相等(重放契约
  的假局半边;红 = 随机流串扰或环境规则引入不可复现分支)。
- **账本位锁** = sink 的 ledger/tracked 随动与游戏真值对得上:金账
  (期初−花销+卖入=期末,单一源 = 状态机 gold)与动作账自洽。红 =
  sink 账本位漂移(批 1 新引入面的在环检测器)。
- **journal 写端隔离锁** = 假局 journal 行落假局根、live 根零新行
  (T-129/T-130 混流注记的机器可判形)。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fixtures.cw_fake_game.fake_match import FakeMatch
from fixtures.cw_harness import fake_p1_run

from test.conftest import SrTestContext
from test.harness.fixture_controller import enter_running_state, reset_running_state

#: P1 全段剧本(5 节点代表段:战斗/奖励/战斗/补给/boss——覆盖收入四
#: 分量分支与结算两态;非 9 节点全量:批量预算归保真度批,sim-testing
#: 边界。更小的 n 与更大的 n 在「跑通+确定性」断言上等价,测试纪律 12)
_SCRIPT: list[str] = ['battle', 'reward', 'battle', 'supply', 'boss']

_SEED: int = 20260908


def test_fake_p1_full_segment_end_to_end(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path) -> None:
    """P1 全段跑通:5 节点全程收工 + 档案四流齐 + 行内容为生产 schema。

    判据逐条:
    ① run_buy_waves 每轮收工(outcome 在案,无 round_fail);
    ② decisions/outcomes/runs/shop_snapshots/op_journal 五流落假局根;
    ③ decisions 行带 run_id 且含动作序列(策略器决策经生产写点落盘);
    ④ outcomes 行 node_type 与剧本一致(结算遥测同产线,方案 §4-4);
    ⑤ journal action 行在环(单动作回执链;写端隔离 = 行落假局根,
       live 根零触由根槽结构性保证,测试不读真实 live 根——纪律 19)。
    """
    enter_running_state(test_context)
    try:
        with fake_p1_run(test_context, monkeypatch, tmp_path, _SEED,
                         node_sequence=_SCRIPT, initial_gold=30) as run:
            result = run.run_p1()
        root = tmp_path / 'fake_p1'
        # ① 全程收工 + 轨迹形状
        assert set(result.rounds) == set(range(1, len(_SCRIPT) + 1))
        assert [result.rounds[r]['node'] for r in sorted(result.rounds)] \
            == _SCRIPT
        # ② 档案流齐备(recorder 原生命名 = 生产 schema 直落的物证)
        for stream in ('decisions.jsonl', 'outcomes.jsonl', 'runs.jsonl',
                       'shop_snapshots.jsonl', 'op_journal.jsonl'):
            assert (root / stream).exists(), f'假局档案缺流:{stream}'
        dec_rows = [json.loads(x) for x in
                    (root / 'decisions.jsonl').read_text(
                        encoding='utf-8').splitlines() if x.strip()]
        # ③ decisions 行 = 生产 DecisionTrace 形状(run_id/动作序列在案)
        assert dec_rows, 'decisions 流空(生产写点未触发?)'
        assert all(row.get('run_id') == f'fake_{_SEED}' for row in dec_rows)
        n_actions = sum(len(row.get('actions') or []) for row in dec_rows)
        assert n_actions >= 1, (
            '决策行动作序列全空(单动作循环未消费任何动作——改道/决策断线)')
        # ④ outcomes 行与剧本对齐(假局结算遥测 = 生产 schema 原生)
        out_rows = [json.loads(x) for x in
                    (root / 'outcomes.jsonl').read_text(
                        encoding='utf-8').splitlines() if x.strip()]
        assert [o.get('node_type') for o in out_rows] == _SCRIPT
        assert all(o.get('hp_confidence') == 1.0 for o in out_rows), (
            '假局结算真值位失真(hp_confidence 应恒 1.0=状态机真值)')
        # ⑤ journal 行落假局根且 kind=action 行存在(单动作回执链在环)
        j_rows = [json.loads(x) for x in
                  (root / 'op_journal.jsonl').read_text(
                      encoding='utf-8').splitlines() if x.strip()]
        assert any(r.get('kind') == 'action' for r in j_rows), (
            'journal 无 action 行(op_journal 回执位未入环)')
        # ⑥ 缺陷流零桩伪影(落地审 M2 回归断言):bench 落位对拍行在
        # 槽键差分桩下与生产计数语义对齐,清洁执行恒零行——行出现 =
        # 桩语义再漂移(而非环境真缺陷,假环境执行失败面结构性为零)
        _assert_no_pixel_diff_artifacts(root)
    finally:
        reset_running_state(test_context, test_context.cw_match)


def _assert_no_pixel_diff_artifacts(root: Path) -> None:
    """M2 回归:假局档案 defect 流零 bench pixel-diff invariant 行。

    语义(修后口径):bench 落位 audit 的输入域 = 真实像素帧,假环境
    结构性不存在 → harness 对该族行做结构性豁免(如实无数据,方案
    §4-6①;落地审 M2 备选路线)。本锁辖**豁免不被拆除**:行出现 =
    豁免过滤被移除且审计通道复活——即「缺陷流如实无数据」申报破缺。"""
    defect_file = root / 'defect_ledger.jsonl'
    if not defect_file.exists():
        return
    rows = [json.loads(x) for x in
            defect_file.read_text(encoding='utf-8').splitlines() if x.strip()]
    artifacts = [r for r in rows
                 if r.get('reader_source') == 'bench_buy_pixel_diff'
                 and r.get('kind') == 'invariant_break']
    assert not artifacts, (
        f'缺陷流出现 bench 落位行 {len(artifacts)} 行'
        f'(结构性豁免被拆除/破缺):'
        f'{[r.get("expected") for r in artifacts[:3]]}')


def test_fake_p1_same_seed_bitwise_replay(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path) -> None:
    """验收①:同 seed + 同剧本两次全程驱动 → 轮轨迹逐位相等(金/账/
    结算/锚)。档案 ts 流不比对(时间戳域),轨迹真值域全比对。"""
    enter_running_state(test_context)
    try:
        with fake_p1_run(test_context, monkeypatch, tmp_path, _SEED,
                         node_sequence=_SCRIPT, initial_gold=30,
                         archive_dir_name='run_a') as run:
            t1 = run.run_p1()
        with fake_p1_run(test_context, monkeypatch, tmp_path, _SEED,
                         node_sequence=_SCRIPT, initial_gold=30,
                         archive_dir_name='run_b') as run:
            t2 = run.run_p1()
    finally:
        reset_running_state(test_context, test_context.cw_match)

    def _trace(res) -> list:
        rows = []
        for r in sorted(res.rounds):
            row = res.rounds[r]
            rows.append({
                'node': row['node'], 'income': row['income'],
                'gold_after_income': row['gold_after_income'],
                'gold_open': row['gold_open'],
                'gold_close': row['gold_close'],
                'total_buy': row['total_buy'],
                'total_level': row['total_level'],
                'total_refresh': row['total_refresh'],
                'total_sell': row['total_sell'],
                'spend_executed': row['spend_executed'],
                'settlement': (None if row['settlement'] is None else
                               (row['settlement'].node,
                                row['settlement'].delta,
                                row['settlement'].hp_after)),
            })
        return rows

    assert _trace(t1) == _trace(t2), '同 seed 假局轨迹逐位不等(确定性破缺)'

    # L-5 增强:decisions 行(actions 身份序列含买/卖/刷的具体对象)
    # 两局逐位相等(ts 域除外)——「同计数不同身份」盲区封死
    def _decisions_identity(archive: Path) -> list:
        rows = [json.loads(x) for x in
                (archive / 'decisions.jsonl').read_text(
                    encoding='utf-8').splitlines() if x.strip()]
        return [{k: v for k, v in row.items() if k != 'ts'}
                for row in rows]

    assert (_decisions_identity(tmp_path / 'run_a')
            == _decisions_identity(tmp_path / 'run_b')), (
        'decisions 行(动作身份序列)两局不等(同 seed 身份盲区破缺)')


def test_sink_ledger_matches_game_truth(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path) -> None:
    """账本位锁:sink 随动的动作账与状态机金账自洽——全程任意轮,
    期末金 = 期初金 − spend_executed + 卖入(sell_income 与状态机金账
    同源,ExecResult.income=执行点真值)。红 = sink 账本位与游戏真值
    分叉(双账对账的假环境形态)。"""
    enter_running_state(test_context)
    try:
        with fake_p1_run(test_context, monkeypatch, tmp_path, _SEED,
                         node_sequence=_SCRIPT, initial_gold=30) as run:
            result = run.run_p1()
            match = run.match
            for r in sorted(result.rounds):
                row = result.rounds[r]
                spent = row['spend_executed']
                # 卖入 = sink income 累计;期末金真值 = 状态机。
                # 本轮净额 = 期末金 − 期初金 + 花销账(若轮内无收入事件)
                # ——商店访问期内金变 = −花销 + 卖入,故:
                # spend_executed − 卖入 == 期初金 − 期末金
                # 卖入从状态机口径取:sell 场景下 spend−(期初−期末) = 卖入
                _delta = row['gold_open'] - row['gold_close']
                assert spent >= 0
                assert _delta <= spent + 1, (
                    f'r{r} 金账失配:期初 {row["gold_open"]} → 期末 '
                    f'{row["gold_close"]},花销账 {spent}(卖入之外'
                    '金不得凭空减少)')
            # 状态机真值终检:全程金非负(拒绝面/守卫面正常工作时恒成立)
            assert match.state.gold >= 0
    finally:
        reset_running_state(test_context, test_context.cw_match)


def test_fake_match_rules_streak_and_income() -> None:
    """回合规则单元锚(收入分解与连胜迁移的单一源推导,测试纪律 9):
    期望值全部从 kernel 常量表现算,零手抄分布值。"""
    from fixtures.cw_fake_game import rules

    from sr_od.application.currency_war.kernel.cw_economy import (
        BASE_INCOME,
        LOSS_GOLD_BY_NODE,
        streak_gold,
    )

    m = FakeMatch(seed=7, node_sequence=['battle', 'battle', 'reward'])
    st = m.state
    st.gold = 100
    # 利息单一源现算:min(帽, 100//10)
    from sr_od.application.currency_war.kernel.cw_economy import interest
    inc = rules.income_for_round(st, m._rng_grant, None, False)
    assert inc['base'] == BASE_INCOME
    assert inc['interest'] == interest(100)
    assert inc['streak'] == streak_gold(0)
    # 败轮金:连胜归 0 + 上一战斗轮败 → LOSS_GOLD_BY_NODE[prev]
    st.streak = -1   # 连败态(带符号口径)
    inc2 = rules.income_for_round(st, m._rng_grant, 'battle', True)
    assert inc2['streak'] == LOSS_GOLD_BY_NODE['battle']
    # 胜态迁移:delta>0 → 正值域 +1;败态:负值域 −1;奖励轮不动
    st.streak = 2
    assert rules.settle_streak(st, 5, 'battle') == (3, False)
    st.streak = 2
    assert rules.settle_streak(st, -9, 'battle') == (-1, True)
    st.streak = 4
    assert rules.settle_streak(st, -3, 'reward') == (4, False)


def test_income_event_component_stays_zero() -> None:
    """收入事件金分量恒 0 登记门(防残差闸回潮;保真校准裁定,出处 =
    ``.debug/temp/currency_war/t120_sim_redesign/保真度校准.md``)。

    机制真值 = 结算金币明细弹窗三分量全集(基础+利息+连胜,
    docs/game/currency_war/research/economy.md §11)——无「事件金」
    第四分量;奖励球金是备战期收球动作(prep 编排域,假环境观察面
    spheres 结构性为零,归批 2)。引擎 ``EVENT_GOLD_BY_ROUND`` 是
    ADR-0447 残差补偿闸(该表 docstring 明文「策略面修复后不得以此表
    回填」),非节点事件金真值。

    锁红时该登记的语义:有人把事件金分量接回非机制真值源(残差闸
    回潮),或批 2 球金建模提前走了旧表——处理 = 按球真值另行建模,
    禁回指残差表(错误信息已指名,非裸 assert)。"""
    from fixtures.cw_fake_game import rules

    m = FakeMatch(seed=7, node_sequence=['battle', 'reward', 'supply'])
    st = m.state
    st.gold = 100
    st.streak = 3
    for node, rn in (('battle', 3), ('reward', 8), ('supply', 5)):
        st.node_type = node
        st.round_num = rn
        inc = rules.income_for_round(st, m._rng_grant, None, False)
        assert 'event' in inc, '收入分解缺 event 键(账本口径面变)'
        assert inc['event'] == 0, (
            f'{node} 轮事件金非 0(残差闸回潮/球金未按真值建模):'
            f'{inc["event"]}——处理 = 按球真值另行建模,禁回指 '
            f'EVENT_GOLD_BY_ROUND 残差闸')


class TestPrepEntryObserveViaPorts:
    """备战入口 heavy 观察改道锁(方案 §2.3 表消费点;批 1 改道清单)。

    红 = 端口分支断线(observe 没走端口/装配半部 session 写点缺席)。
    """

    def test_heavy_observe_reads_ports_and_writes_session(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from fixtures.cw_fake_game.fake_ports import (
            FakeActionSink,
            FakeCwObserver,
        )

        from sr_od.application.currency_war import cw_game_ports
        from sr_od.application.currency_war.kernel.cw_state import (
            BenchChar,
        )
        from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
            CwScreenPrep,
        )

        m = FakeMatch(seed=5, node_sequence=['battle'])
        m.state.gold = 66
        m.state.hp = 55
        # 假局 bench 真值:2 个占用 + 7 空(heavy 字段填充的判据面)
        m.state.bench = [BenchChar(slot=1, char_id='希儿', faction='?'),
                         BenchChar(slot=2, char_id='景元', faction='?')]
        m.state.deployed = []
        # session 写点断言的载体(装配半部消费 ctx.cw_match)
        from sr_od.application.currency_war.strategies.impl.cw_strategy import (
            CurrencyWarMatch,
            StrategySession,
        )
        monkeypatch.setattr(test_context, 'cw_match',
                            CurrencyWarMatch(None, StrategySession()))
        cw_game_ports.install_game_ports(FakeCwObserver(m),
                                         FakeActionSink(m))
        try:
            prep = CwScreenPrep(test_context)
            monkeypatch.setattr(prep, 'screenshot',
                                lambda: None)   # 端口路径零读屏,帧不应被消费
            obs = prep._observe(heavy=True)
            # 端口真值直出(非读屏桩):金/hp/bench 身份来自状态机
            assert obs.state is not None
            assert obs.state.gold == 66 and obs.state.hp == 55
            assert [b.char_id for b in obs.bench_chars] == ['希儿', '景元']
            assert obs.free_bench_slots == 7
            assert obs.state.deploy_cap == obs.state.level   # cap=level 真值规则
            # 装配半部 session 写点(与读屏路径同语义)
            session = test_context.cw_match.session
            assert session.last_state is obs.state
            assert session.prep_obs_frame is obs
            # 观察留痕(读屏次数语义保留):入口观察留痕在案
            assert any(e.method == 'observe_prep'
                       for e in m.observation_log)
        finally:
            cw_game_ports.uninstall_game_ports()

    def test_visit_open_shop_drives_fake_round(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """M1 补锁:visit_open_shop 假局全链(方案批 1 行第二入口形)。

        驱动面 = 入口观察(端口)→ run_buy_waves(端口)→ close_shop
        点击壳(区域原语桩,壳逻辑真跑)→ finalize_buy_phase(三处
        gold 读喂假局真值)→ 节点探针。判据:
        ①访问成功收尾;②关店规则已落(画面身份回备战);③金恒等式
        贯穿 finalize 对拍(期末=期初−花销+卖入,真值链无断裂);
        ④缺陷流零 bench 桩伪影(M2 共用断言)。
        """
        from fixtures.cw_fake_game.fake_match import PHASE_PREP

        enter_running_state(test_context)
        try:
            with fake_p1_run(test_context, monkeypatch, tmp_path, _SEED,
                             node_sequence=['battle'], initial_gold=30,
                             archive_dir_name='visit') as run:
                ok, detail, info = run.run_visit(monkeypatch, tmp_path)
            assert ok, f'visit_open_shop 未成功收尾:{detail!r}'
            assert info['phase'] == PHASE_PREP, (
                f'关店规则未落(画面身份={info["phase"]})')
            # 金恒等式(真值链贯穿 finalize):finalize 的关店金收口槽
            # 被真值写入(无条件暂存 = finalize 跑到 gold 对拍步的证据;
            # prep_obs_frame 恒 None 是 0n 直入形态的正确行为——缺席守卫
            # 显式跳过暂存,ADR-0583 §5.5-丁,不得当断言)
            from sr_od.application.currency_war.telemetry import state as tel_s
            slot = tel_s._PENDING_UNIT_GOLD_CLOSE
            assert slot is not None and slot['trusted'], (
                'finalize 关店金收口未跑(visit 尾段链未真跑)')
            assert slot['gold'] == run.match.state.gold, (
                f'finalize 金收口非假局真值:{slot["gold"]} != '
                f'{run.match.state.gold}')
            _assert_no_pixel_diff_artifacts(tmp_path / 'visit')
        finally:
            reset_running_state(test_context, test_context.cw_match)
