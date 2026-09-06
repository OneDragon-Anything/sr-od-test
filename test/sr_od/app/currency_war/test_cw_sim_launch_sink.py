"""sim 决策下沉两小批锁面(判据核上收 + 发射短路行为消费 + 反假阴性哨兵)。

背景(裁决 = ADR-0557,docs/develop/currency_war/decisions/
0557-sim-sink-launch-criteria-kernel.md):生产达标臂判据(线成型 fp≥1.0 ∧
战斗就绪)原散在 cw_loop 备战分支与 engine_p1 发射观测块两处内联 = 双
消费面双实现漂移面;发射帧的「短路备战动作链」语义 sim 原先不消费 ⇒
金出口族改动在严格同池 A/B 上 pre/post 逐位一致 = 结构性假阴性
(form_ok 镜像族无写者同族事故,已两次实证)。

本批锁:
1. 等价锁(小批①):kernel ``readiness_launch_decision`` 的 armed 判定
   与上收前内联语义快照逐位一致(状态扫描 + 边界帧:None 输入/fp 恰
   1.0/admission best-effort None)——上收零策略语义变化;
2. 消费面单一源锁(小批①):两消费面(cw_loop/engine_p1)源内均无
   ``form_progress(`` 内联调用、均经判据核单一函数;engine 行为随判据
   核注入翻转(消费证明,非仅 import 面);
3. 短路行为锁(小批②):真 sim 账本发射帧 short_circuited=True、
   actions 空、spend 全零(金不花 = 生产短路语义对齐);
4. 哨兵锁(小批②):check_sim_launch_short_circuit 对「分键缺位/发射
   帧决策照常/金照花」三形态逐个红,真账本绿——守卫移除即红;
5. armed 单键锁(三审整改):admission 异常吞 None 时发射帧仍短路
   (victim=None 观测位不拦门——admission 缺失也拦会留「生产短路金不
   花、sim 决策照常」的假阴性残留,ADR-0557 §4)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel import cw_launch_admission
from sr_od.application.currency_war.kernel.cw_comps import form_progress
from sr_od.application.currency_war.sim.checks.launch import (
    check_sim_launch_short_circuit,
)
from sr_od.application.currency_war.sim.engine_p1 import simulate_p1

_SEED_CACHE: dict[int, object] = {}


def _seeded_result(seed: int):
    """同 seed 单局结果同次运行只算一次(昂贵计算共享,README 纪律)。"""
    if seed not in _SEED_CACHE:
        _SEED_CACHE[seed] = simulate_p1(seed, pool='snapshot')
    return _SEED_CACHE[seed]


def _launch_rows(result) -> list[dict]:
    return [row for row in result.ledger if row.get('launch') is not None]


class _FakeComp:
    """最小 Comp 形状(form_progress 只读 form_tiers)。"""

    def __init__(self, tiers: dict[str, int]):
        self.form_tiers = tiers
        self.core_chars: list[str] = []
        self.shared_chars: list[str] = []
        self.all_factions: set[str] = set(tiers) | {'仙舟'}


def _fake_state(board: dict[str, int]):
    """最小 GameState 形状(form_progress 只读 board;准入读 bench/
    deployed 定长表——空表 = 无 victim/bench,合法输入)。"""
    return SimpleNamespace(board=board, bench=[None] * 9,
                           deployed=[None] * 10)


def _legacy_armed(state, comp) -> bool:
    """上收前内联语义快照(cw_loop 备战分支/engine_p1 观测块原式)。

    等价锁的参照实现:两消费面原内联式逐字同构——输入齐备
    (comp/state 非 None)∧ form_progress(comp, state) >= 1.0。
    """
    return (comp is not None and state is not None
            and form_progress(comp, state) >= 1.0)


def _line_members(comp):
    from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
        line_members,
    )
    return line_members(comp)


class TestKernelEquivalenceLock:
    """锁 1(小批①):判据核 armed 与上收前内联语义逐位一致。"""

    def test_armed_bitwise_equal_on_state_sweep(self):
        """状态扫描:全输入域上核输出 ≡ 旧内联式(逐位零变化)。"""
        boards = [{}, {'仙舟': 0}, {'仙舟': 1}, {'仙舟': 3},
                  {'仙舟': 3, '贝洛伯格': 1}, {'仙舟': 9}]
        comps = [None, _FakeComp({}), _FakeComp({'仙舟': 0}),
                 _FakeComp({'仙舟': 3}), _FakeComp({'仙舟': 4})]
        checked = 0
        for tiers in boards:
            st = _fake_state(tiers)
            for comp in comps:
                core = cw_launch_admission.readiness_launch_decision(
                    st, comp, line_members=_line_members)
                assert core['armed'] is _legacy_armed(st, comp), (
                    tiers, comp)
                checked += 1
        assert checked == 30

    def test_armed_none_input_short_circuits(self):
        """None 输入边界:comp/state 任一 None ⇒ armed False(旧式短路序
        保持,form_progress 不被触达,不炸)。"""
        assert cw_launch_admission.readiness_launch_decision(
            None, _FakeComp({'仙舟': 3}),
            line_members=_line_members)['armed'] is False
        assert cw_launch_admission.readiness_launch_decision(
            _fake_state({'仙舟': 3}), None,
            line_members=_line_members)['armed'] is False

    def test_boundary_fp_exactly_1_and_below(self):
        """阈值边界:fp 恰 1.0 武装、0.999… 不武装(零新阈值,唯一面 =
        form_progress 语义)。"""
        full = _fake_state({'仙舟': 3})           # 3/3 = 1.0
        comp3 = _FakeComp({'仙舟': 3})
        below = _fake_state({'仙舟': 2})          # 2/3 < 1.0
        assert cw_launch_admission.readiness_launch_decision(
            full, comp3, line_members=_line_members)['armed'] is True
        assert cw_launch_admission.readiness_launch_decision(
            below, comp3, line_members=_line_members)['armed'] is False

    def test_admission_equals_direct_report_when_armed(self):
        """admission 位 = launch_admission_report 同输入直调逐位一致
        (单一源内聚,禁核内第二套三元)。"""
        st = _fake_state({'仙舟': 3})
        comp = _FakeComp({'仙舟': 3})
        core = cw_launch_admission.readiness_launch_decision(
            st, comp, line_members=_line_members)
        direct = cw_launch_admission.launch_admission_report(
            st, comp, line_members=_line_members)
        assert core['admission'] == direct
        assert core['auth_basis'] == 'readiness_form_ok'


class TestConsumerSingleSourceLock:
    """锁 2(小批①):两消费面单一源(无内联判据第二实现)。"""

    def test_consumers_reference_kernel_core_only(self):
        """cw_loop/engine_p1 源内均无 ``form_progress(`` 直调(判据唯一
        实现 = kernel),且均经 readiness_launch_decision 消费。"""
        from one_dragon.utils.file_utils import get_project_root
        root = get_project_root()
        for rel in ('src/sr_od/application/currency_war/operations/cw_loop.py',
                    'src/sr_od/application/currency_war/sim/engine_p1.py'):
            src = (root / rel).read_text(encoding='utf-8')
            assert 'form_progress(' not in src, (
                f'{rel} 残留内联成型判据(判据核单一源锁)')
            assert 'readiness_launch_decision' in src, (
                f'{rel} 未消费判据核单一源')

    def test_engine_behavior_follows_kernel_core(self, monkeypatch):
        """消费证明(行为面,非 import 面):判据核强制武装 ⇒ sim 发射帧
        出现且全部短路(决策段零执行)——engine 行为随核翻转。"""
        real = cw_launch_admission.readiness_launch_decision

        def _force_armed(state, comp, *, line_members):
            out = real(state, comp, line_members=line_members)
            if comp is not None and state is not None:
                out['armed'] = True
            return out

        monkeypatch.setattr(cw_launch_admission,
                            'readiness_launch_decision', _force_armed)
        result = simulate_p1(0, pool='snapshot')
        launch_rows = _launch_rows(result)
        assert launch_rows, '强制武装后零发射帧(engine 未消费判据核)'
        for row in launch_rows:
            assert row['launch']['short_circuited'] is True
            assert row['actions'] == []

    def test_admission_none_does_not_block_short_circuit(self, monkeypatch):
        """armed 单键锁(三审整改,ADR-0557 §4):admission 预估异常吞
        None 时发射帧仍短路(victim=None 只作观测位)——若 None 拦门,
        该帧族留「生产短路金不花、sim 决策照常」假阴性残留。"""
        def _boom(*a, **kw):
            raise RuntimeError('准入预估不可得(注入异常)')

        monkeypatch.setattr(cw_launch_admission,
                            'launch_admission_report', _boom)
        result = simulate_p1(0, pool='snapshot')
        launch_rows = _launch_rows(result)
        assert launch_rows, 'admission 全异常时零发射帧(None 拦门残留)'
        for row in launch_rows:
            assert row['launch']['victim'] is None
            assert row['launch']['short_circuited'] is True
            assert row['actions'] == []
            spend = (row.get('sim') or {}).get('spend') or {}
            assert all(int(v or 0) == 0 for v in spend.values())


class TestShortCircuitBehaviorLock:
    """锁 3(小批②):真 sim 账本发射帧短路形态(金不花)。"""

    def test_launch_frames_short_circuited_in_real_ledger(self):
        seen = False
        for seed in range(6):
            for row in _launch_rows(_seeded_result(seed)):
                seen = True
                assert row['launch']['short_circuited'] is True
                assert row['actions'] == [], row['round_num']
                spend = (row.get('sim') or {}).get('spend') or {}
                assert all(int(v or 0) == 0 for v in spend.values())
        assert seen, '采样 6 seed 零发射事件(采样缺陷,需换 seed 窗口)'


class TestAntiFalseNegativeSentinel:
    """锁 4(小批②):反假阴性哨兵(守卫移除即红)。"""

    @staticmethod
    def _row(launch, actions=(), spend=None):
        return {'launch': launch, 'actions': list(actions),
                'sim': {'spend': spend or {}}}

    def test_clean_ledger_green(self):
        ledgers = [[self._row({'__type__': 'LaunchBattle',
                               'short_circuited': True}),
                    self._row(None, actions=[{'__type__': 'BuyCard'}],
                              spend={'buys': {'x': 3}})]]
        out = check_sim_launch_short_circuit(ledgers)
        assert out['violations'] == 0
        assert out['launch_frames'] == 1
        assert out['short_circuited_frames'] == 1

    def test_missing_short_circuited_key_red(self):
        """分键缺位 = 旧观测面形态(两小批②接线被拆),红。"""
        ledgers = [[self._row({'__type__': 'LaunchBattle', 'ok': True})]]
        out = check_sim_launch_short_circuit(ledgers)
        assert out['violations'] == 1

    def test_actions_on_launch_frame_red(self):
        """发射帧决策照常 = pre/post 回到逐位一致 = 假阴性形态,红。"""
        ledgers = [[self._row({'short_circuited': True},
                              actions=[{'__type__': 'RefreshShop'}])]]
        assert check_sim_launch_short_circuit(ledgers)['violations'] == 1

    def test_spend_on_launch_frame_red(self):
        """发射帧金仍在花 = 假阴性形态,红。"""
        ledgers = [[self._row({'short_circuited': True},
                              spend={'levelup': 4})]]
        assert check_sim_launch_short_circuit(ledgers)['violations'] == 1

    def test_nested_buys_spend_on_launch_frame_red(self):
        """嵌套 buys 形状红锁(落地审阻断项回归):真实账本 spend.buys
        = {通道: 金} 嵌套 dict,且恰在发射帧 buys 非空(第三假阴性形态)
        时触发——修复前嵌套位走标量 int() TypeError 崩整批报告(结构化
        红变崩),修复后展平求和落结构化红;嵌套全零不误红。"""
        ledgers = [[self._row(
            {'short_circuited': True},
            spend={'buys': {'m2': 3, 'fuel_filler_stall': 2},
                   'refresh': 2, 'sell_income': 0})]]
        out = check_sim_launch_short_circuit(ledgers)
        assert out['violations'] == 1, '嵌套 buys 非空须落金照花红'
        clean = [[self._row({'short_circuited': True},
                            spend={'buys': {}, 'refresh': 0})]]
        assert check_sim_launch_short_circuit(clean)['violations'] == 0

    def test_mixed_batch_only_legacy_games_red(self):
        """批内有发射帧但某局全为旧形态(无分键)⇒ 仅该局红;含真短路
        帧的局绿。全批零短路帧时逐局全红(batch_bad 分支)。"""
        rows = [self._row({'short_circuited': True})]
        legacy = [self._row({'__type__': 'LaunchBattle'})]   # 无分键
        out = check_sim_launch_short_circuit([rows, legacy])
        assert out['violations'] == 1 and out['games'] == [1]
        legacy_all = [self._row({'__type__': 'LaunchBattle'})] * 2
        out2 = check_sim_launch_short_circuit([legacy_all, legacy_all])
        assert out2['violations'] == 2   # 全批零短路帧 → 全红

    def test_real_seeded_batch_sentinel_green(self):
        """真账本哨兵绿:有发射帧且全部短路(与锁 3 同源对账)。"""
        ledgers = [_seeded_result(seed).ledger for seed in range(3)]
        out = check_sim_launch_short_circuit(ledgers)
        assert out['launch_frames'] > 0, '零发射帧(采样缺陷,需换 seed)'
        assert out['violations'] == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
