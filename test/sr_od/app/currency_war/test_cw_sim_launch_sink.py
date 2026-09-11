"""sim 决策下沉锁面(判据核上收 + 发射短路行为消费 + 反假阴性哨兵)。

背景(裁决 = ADR-0557,docs/develop/currency_war/decisions/
0557-sim-sink-launch-criteria-kernel.md):生产达标臂发射帧**短路备战动作链**;
判据上收 kernel 单一源 + sim 发射帧短路决策段(消金出口族 A/B 结构性
假阴性)+ 反假阴性哨兵。

**批 1 锁语义重推(非机械跟绿;出处 = 金出口族 DESIGN v1.1 §3.2/§5,
ADR-0566,docs/develop/currency_war/decisions/0566-launch-frame-
arbitrage-batch1.md)**:发射帧仲裁段(出口 B,P70 已证)落地后,发射帧
允许**受限消费**(预算 = g − g*,花后金位 ≥ g*);哨兵断言从「金不花」
升级为「自由决策段零执行 ∧ 仲裁段外零消费」。旧「actions 空 ∧ spend 零」
锁已被新设计取代:短路语义辖的是**自由决策链**(short_circuited 分键),
仲裁段消费不是自由链复 act——判据:带内帧 fail-closed(动作空∧零花)、
溢出帧预算不变量(gold_after ≥ g*)、仲裁披露缺位红(接线被拆=批 0 假
阴性形态回归)。

本文件锁(2026-09-09 瘦身批重整;armed 合取语义/配方腿阈值/推迟支
本体已归并主题文件 test_cw_launch_quality_conjunction.py,此处不再
重复持有——覆盖对账见 reports/_cluster_P.md):
1. armed 判据核边界锁:None 输入保守 False;admission 位 =
   launch_admission_report 同输入直调逐位一致(核内禁第二套三元);
2. 消费面单一源锁(小批①):两消费面(cw_loop/engine_p1)源内均无
   ``form_progress(`` 内联调用;engine 行为随判据核注入翻转(消费
   证明,非仅 import 面;engine 侧接线由本行为锁辖,不另立在场烟雾);
3. 短路+仲裁行为锁(批 1 重推):真 sim 账本发射帧 short_circuited=True
   ∧ 仲裁披露在位;带内帧零消费(fail-closed);溢出帧预算不变量;
4. 哨兵锁(批 1 重推):check_sim_launch_short_circuit 对「分键缺位/
   仲裁披露缺位/带内帧动作/带内帧花费/溢出帧破线」逐个红,真账本绿;
5. armed 单键锁(三审整改):admission 异常吞 None 时发射帧仍短路
   (victim=None 观测位不拦门)。

CUT6 瘦身批(2026-09-09):哨兵边缘变体(zone 域外值/legacy 批归因)
砍除——核心红形态(docstring 第 4 条五枚举)全数保留;判据与保留核
清单 = reports/_cluster_CUT6.md。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel import cw_launch_admission
from sr_od.application.currency_war.kernel.cw_state import BenchChar
from sr_od.application.currency_war.sim.checks.launch import (
    check_sim_launch_short_circuit,
)
from sr_od.application.currency_war.sim.engine_p1 import simulate_p1

_SEED_CACHE: dict[int, object] = {}

# 发射锚种子(README 纪律#12:显式命中代表集+探针记录)。
# 探针背景:奖励帧抑制生效(2026-09-08 奖励帧策略审查·可见性批,sim
# 决策帧填充 node_type)使早期局经济/意向轨迹改变、发射时点位移——
# 旧隐式锚 seed 0-5 中的 0/2/3 零发射事件,锁红为采样缺陷非机制回归。
# 探针窗口 seed 0-39 命中 23/40(全含溢出帧);代表集形态:少发射行
# (1:3 行 r6/7/9;4:2 行)~单发射行(15/23/39)~多发射行含 r3 早发射(5/16/29)。列表失准的红 = 重跑探针更新。
_LAUNCH_SEEDS: tuple[int, ...] = (1, 4, 5, 16, 29)
_LAUNCH_SEED: int = 5   # 单锚:发射行 5(轮 3/4/6/7/9)、溢出帧 4


def _seeded_result(seed: int):
    """同 seed 单局结果同次运行只算一次(昂贵计算共享,README 纪律)。"""
    if seed not in _SEED_CACHE:
        _SEED_CACHE[seed] = simulate_p1(seed, pool='snapshot')
    return _SEED_CACHE[seed]


def _launch_rows(result) -> list[dict]:
    return [row for row in result.ledger if row.get('launch') is not None]


def _spend_total(row) -> int:
    """行 spend 位真金总量(buys 位 = {通道: 金} 嵌套,展平求和)。"""
    total = 0
    for v in ((row.get('sim') or {}).get('spend') or {}).values():
        if isinstance(v, dict):
            total += sum(int(x or 0) for x in v.values())
        else:
            total += int(v or 0)
    return total


def _assert_launch_row_legal(row) -> None:
    """发射帧行为合法性断言(批 1 语义单一断言面,多锁共用)。

    = short_circuited 在位 ∧ 仲裁披露在位;带内帧动作空 ∧ 零消费
    (fail-closed);溢出帧 gold_after ≥ g_star(P70 预算不变量)。
    """
    launch = row['launch']
    assert launch['short_circuited'] is True
    arb = launch.get('arbitrage')
    assert isinstance(arb, dict), '仲裁披露缺位(接线被拆,批 1 新形态)'
    assert arb['zone'] in ('overflow', 'inband_failclosed')
    if arb['zone'] == 'inband_failclosed':
        assert row['actions'] == [], (row['round_num'], row['actions'])
        assert _spend_total(row) == 0, (row['round_num'], _spend_total(row))
    else:
        assert arb['gold_after'] >= arb['g_star'], (
            row['round_num'], arb['gold_after'], arb['g_star'])


class _FakeComp:
    """最小 Comp 形状(form_progress 只读 form_tiers)。"""

    def __init__(self, tiers: dict[str, int]):
        self.form_tiers = tiers
        self.core_chars: list[str] = []
        self.shared_chars: list[str] = []
        self.all_factions: set[str] = set(tiers) | {'仙舟'}


def _fake_state(board: dict[str, int], deployed: list = (),
                bench: list = ()):
    """最小 GameState 形状(form_progress 只读 board;准入/质量维读
    bench/deployed 定长表与 max_units——缺省空表 = 无 victim/bench、
    cap 兜底 10**6,合法输入)。

    slot 统一 1 基物理槽位范式(容器占位由列表下标承载,slot 字段只
    表物理槽位):生产单一源 = cw_state.bench_place 放置归一
    ``slot = 下标+1``(物理槽位 1-9,与 live 读链 read_bench_chars 同
    坐标系);范式参照同仓 test_cw_core_single_card_channel._bc。
    禁 0 基/表基失真——质量维或放置计划按生产归一语义读 slot 时,
    失真帧会静默误判(测试帧不再反映生产形态)。"""
    dep = [None] * 10
    for i, name in enumerate(deployed):
        dep[i] = BenchChar(slot=i + 1, char_id=name, star=1,
                           position_pref='back')
    b = [None] * 9
    for i, name in enumerate(bench):
        b[i] = SimpleNamespace(kind='unit',
                               unit=SimpleNamespace(char_id=name,
                                                    star=1,
                                                    equips=[]))
    _front = [SimpleNamespace(char_id=u.char_id, star=u.star, slot=j + 1,
                              equips=[])
              for j, u in enumerate(x for x in dep[:4] if x is not None)]
    _back = [SimpleNamespace(char_id=u.char_id, star=u.star, slot=j + 1,
                             equips=[])
             for j, u in enumerate(x for x in dep[4:] if x is not None)]

    def _fld(v):
        return SimpleNamespace(value=v)

    return SimpleNamespace(board=_fld(board),
                           front_row=_fld(_front), back_row=_fld(_back),
                           bench=_fld(SimpleNamespace(slots=b, capacity=9)),
                           level=_fld(6), deploy_cap=_fld(6),
                           back_layout=_fld(None),
                           selected_difficulty=_fld(''),
                           shop=_fld(None))


def _line_members(comp):
    from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
        line_members,
    )
    return line_members(comp)


class TestKernelArmedCoreBoundaries:
    """armed 判据核边界锁(合取语义本体已归并主题文件
    test_cw_launch_quality_conjunction.py——真值表/推迟支/配方腿阈值
    由其 TestArmedConjunctionTruthTable 五测承载,亲读证实超集,本类
    只留主题文件所无的两面)。

    历史注(锁的存在性纪律):本类原名 TestKernelEquivalenceLock→
    TestKernelArmedConjunctionLock,先后锁过「armed ≡ form_progress
    单键逐位一致」(ADR-0557 零语义变化证明)与 30 帧合取真值表
    (ADR-0570)——两个用途分别随质量合取入核、随主题文件建立而
    由更超集的载体接管,按覆盖对账纪律移归,非判锁对象退役。
    """

    def test_armed_none_input_short_circuits(self):
        """None 输入边界:comp/state 任一 None ⇒ armed False(旧式短路序
        保持,form_progress 不被触达,不炸)。"""
        assert cw_launch_admission.readiness_launch_decision(
            None, _FakeComp({'仙舟': 3}),
            line_members=_line_members)['armed'] is False
        assert cw_launch_admission.readiness_launch_decision(
            _fake_state({'仙舟': 3}), None,
            line_members=_line_members)['armed'] is False

    def test_admission_equals_direct_report_when_armed(self):
        """admission 位 = launch_admission_report 同输入直调逐位一致
        (单一源内聚,禁核内第二套三元);配方完备帧 quality 报告在位。"""
        st = _fake_state({'仙舟': 3})
        comp = _FakeComp({'仙舟': 3})
        core = cw_launch_admission.readiness_launch_decision(
            st, comp, line_members=_line_members)
        direct = cw_launch_admission.launch_admission_report(
            st, comp, line_members=_line_members)
        assert core['admission'] == direct
        assert core['auth_basis'] == 'readiness_form_ok'
        assert core['quality'] is not None
        assert core['quality']['load_bearing_full'] is True


class TestConsumerSingleSourceLock:
    """锁 2(小批①):两消费面单一源(无内联判据第二实现)。"""

    def test_consumers_reference_kernel_core_only(self):
        """cw_loop/engine_p1 源内均无 ``form_progress(`` 直调(判据唯一
        实现 = kernel,单一源守卫);cw_loop 侧另留一条经核消费在场烟雾
        ——engine 侧接线不再立在场断言:同文件
        test_engine_behavior_follows_kernel_core 已以「判据核注入翻转 ⇒
        engine 行为翻转」行为锁辖(在场断言只会早红且零增量判别力,
        README 纪律 8 烟雾至多 1 条)。"""
        from one_dragon.utils.file_utils import get_project_root
        root = get_project_root()
        for rel in ('src/sr_od/application/currency_war/operations/cw_loop.py',
                    'src/sr_od/application/currency_war/sim/engine_p1.py'):
            src = (root / rel).read_text(encoding='utf-8')
            assert 'form_progress(' not in src, (
                f'{rel} 残留内联成型判据(判据核单一源锁)')
        loop_src = (root / 'src/sr_od/application/currency_war/operations/'
                    'cw_loop.py').read_text(encoding='utf-8')
        assert 'readiness_launch_decision' in loop_src, (
            'cw_loop 未消费判据核单一源')

    def test_engine_behavior_follows_kernel_core(self, monkeypatch):
        """消费证明(行为面,非 import 面):判据核强制武装 ⇒ sim 发射帧
        出现且全部短路 + 仲裁披露在位(带内 fail-closed/溢出预算不变量)
        ——engine 行为随核翻转。"""
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
            _assert_launch_row_legal(row)

    def test_admission_none_does_not_block_short_circuit(self, monkeypatch):
        """armed 单键锁(三审整改,ADR-0557 §4):admission 预估异常吞
        None 时发射帧仍短路(victim=None 只作观测位)——若 None 拦门,
        该帧族留「生产短路金不花、sim 决策照常」假阴性残留。批 1 起
        消费合法性按仲裁语义断言(带内 fail-closed/溢出预算不变量)。"""
        def _boom(*a, **kw):
            raise RuntimeError('准入预估不可得(注入异常)')

        monkeypatch.setattr(cw_launch_admission,
                            'launch_admission_report', _boom)
        result = simulate_p1(_LAUNCH_SEED, pool='snapshot')
        launch_rows = _launch_rows(result)
        assert launch_rows, 'admission 全异常时零发射帧(None 拦门残留)'
        for row in launch_rows:
            assert row['launch']['victim'] is None
            _assert_launch_row_legal(row)


class TestShortCircuitBehaviorLock:
    """锁 3(批 1 重推):真 sim 账本发射帧 = 短路 + 仲裁受限消费形态。"""

    def test_launch_frames_short_circuited_in_real_ledger(self):
        seen = False
        overflow_seen = False
        for seed in _LAUNCH_SEEDS:
            launch_rows = _launch_rows(_seeded_result(seed))
            # 每采样 seed 逐局非空前置(落地审 F7):空账本 = 循环体不执行
            # = 锁空洞绿,防「质量闸把发射帧推迟到视野外」的假绿形态。
            assert launch_rows, (f'seed {seed} 零发射事件'
                                 '(发射锚漂移,重跑探针更新 _LAUNCH_SEEDS)')
            for row in launch_rows:
                seen = True
                _assert_launch_row_legal(row)
                if row['launch']['arbitrage']['zone'] == 'overflow':
                    overflow_seen = True
                    assert row['launch']['arbitrage']['gold_before'] > 0
        assert seen, '采样种子集零发射事件(重跑探针更新 _LAUNCH_SEEDS)'
        assert overflow_seen, '采样种子集零溢出发射帧(仲裁段无行为样本,' \
                              '重跑探针更新 _LAUNCH_SEEDS)'


class TestAntiFalseNegativeSentinel:
    """锁 4(批 1 重推):反假阴性哨兵(守卫移除即红)。"""

    @staticmethod
    def _row(launch, actions=(), spend=None):
        return {'launch': launch, 'actions': list(actions),
                'sim': {'spend': spend or {}}}

    @staticmethod
    def _overflow(gold_before=80, gold_after=60, g_star=50):
        return {'short_circuited': True,
                'arbitrage': {'zone': 'overflow',
                              'gold_before': gold_before,
                              'gold_after': gold_after, 'g_star': g_star,
                              'spent': gold_before - gold_after,
                              'actions': 1, 'segments': 2,
                              'stop_reason': '', 'gate_blocks': 0}}

    @staticmethod
    def _inband(gold=40, g_star=50):
        return {'short_circuited': True,
                'arbitrage': {'zone': 'inband_failclosed',
                              'gold_before': gold, 'gold_after': gold,
                              'g_star': g_star, 'spent': 0,
                              'actions': 0, 'segments': 0,
                              'stop_reason': 'inband', 'gate_blocks': 0}}

    def test_clean_ledger_green_with_arbitration_consume(self):
        """批 1 形态绿:溢出帧仲裁消费(动作+花费非空)+ 带内帧零消费
        + 非发射帧自由决策,全部通过。"""
        ledgers = [[self._row(self._overflow(gold_before=80, gold_after=60),
                              actions=[{'__type__': 'BuyCard'}],
                              spend={'buys': {'m2_merge_completion': 3},
                                     'refresh': 2}),
                    self._row(self._inband()),
                    self._row(None, actions=[{'__type__': 'BuyCard'}],
                              spend={'buys': {'x': 3}})]]
        out = check_sim_launch_short_circuit(ledgers)
        assert out['violations'] == 0
        assert out['launch_frames'] == 2
        assert out['short_circuited_frames'] == 2

    def test_missing_short_circuited_key_red(self):
        """分键缺位 = 旧观测面形态(两小批② 接线被拆),红。"""
        ledgers = [[self._row({'__type__': 'LaunchBattle', 'ok': True,
                               'arbitrage': self._inband()['arbitrage']})]]
        out = check_sim_launch_short_circuit(ledgers)
        assert out['violations'] == 1

    def test_missing_arbitrage_disclosure_red(self):
        """仲裁披露缺位(批 0 形态)= 仲裁段接线被拆 ⇒ 假阴性回归面
        复活,红(批 1 新增断言;红证锚 = 禁用仲裁段后本形态必现)。"""
        ledgers = [[self._row({'short_circuited': True})]]
        out = check_sim_launch_short_circuit(ledgers)
        assert out['violations'] == 1

    def test_actions_on_inband_frame_red(self):
        """带内帧动作非空 = fail-closed 破(L1' 证不出不花),红。"""
        ledgers = [[self._row(self._inband(),
                              actions=[{'__type__': 'RefreshShop'}])]]
        assert check_sim_launch_short_circuit(ledgers)['violations'] == 1

    def test_spend_on_inband_frame_red(self):
        """带内帧金仍在花 = fail-closed 破,红。"""
        ledgers = [[self._row(self._inband(),
                              spend={'levelup': 4})]]
        assert check_sim_launch_short_circuit(ledgers)['violations'] == 1

    def test_overflow_crossing_g_star_red(self):
        """溢出帧花后跌破 g* = P70 辖域破(花穿息线部分出辖,p70 边界 1),
        红——合并多买等投影外成本破线由此响亮暴露。"""
        ledgers = [[self._row(self._overflow(gold_before=80, gold_after=49,
                                             g_star=50),
                              actions=[{'__type__': 'BuyCard'}],
                              spend={'buys': {'m6_stockpile': 31}})]]
        assert check_sim_launch_short_circuit(ledgers)['violations'] == 1

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
