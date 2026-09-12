"""star 回退留证钩子测试(用户 2026-08-17:预估升星 vs 实机读回不符 → 排查)。

路径:①首节点回退保旧防抖(疑 3合1 合成动画窗:不写回、不计数);②连续确认 →
采新写回 + 计数,每 5 次确认留证一张 sentinel(r17 降级:留证不 stop);③读回恢复
→ 计数清零(不再累积)。附 r58 回归两面:同名多副本防抖只抬一个;角色离场清 pending。


出处:被测模块本体——现行基建锁(星级回归钩子;执行侧状态迁移表
docs/develop/sr_od/application/currency_war/flow/session.md §2.4 star_regression_count 行)
(2026-08-31 测试瘦身批考证补记)。"""
from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
import sys
from pathlib import Path
from types import SimpleNamespace

_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.kernel.cw_reconcile import reconcile_tracking  # noqa: E402


class _Ctx:
    """停机钩子 ctx:stop_running 置位即可。sentinel 写盘相对 CWD
    (.debug/temp/currency_war/star_regression_hook.flag),经 monkeypatch.chdir
    隔离进 tmp_path——monkeypatch 自动还原,防 setup 抛错把进程 CWD 泄漏进
    已删目录(旧 os.chdir+finally 版在构造与 try 之间有裸窗)。"""

    def __init__(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        self.stopped = False
        self.run_context = SimpleNamespace(
            stop_running=lambda reason='': setattr(self, 'stopped', True))


def _sess(tracked_2star: bool):
    bench = [SimpleNamespace(char_id='万敌', star=2, slot=1, position_pref='back')] if tracked_2star else []
    s = SimpleNamespace(star_pending_regression={})
    # tracking 字段已迁执行侧载体 ExecState(经 exec_state_of 惰性建,桩同效)
    ex = exec_state_of(s)
    ex.tracked_bench_chars = bench
    ex.tracked_deployed = []
    ex.star_regression_count = {}
    return s


def _read(star: int):
    return [SimpleNamespace(char_id='万敌', star=star, slot=1, position_pref='back')]


def test_first_regression_no_stop(tmp_path, monkeypatch) -> None:
    """首节点 2★→1★:**保旧防抖**(2026-08-18:274 存证复现 36/40 同图重读 2★,
    live 读 1★ = 3合1 合成动画窗)—— 留证 + pending 挂起,不停机不计数不毒化 tracking。"""
    import sr_od.application.currency_war.kernel.cw_reconcile as cr
    monkeypatch.setattr(cr, '_conflict', lambda *a, **k: None)
    ctx = _Ctx(monkeypatch, tmp_path)
    s = _sess(True)
    reconcile_tracking(s, _read(1), [], None, source='t', ctx=ctx)
    assert not ctx.stopped
    assert s.star_pending_regression.get('万敌') == 1, 'pending 挂起(下帧确认)'
    assert not exec_state_of(s).star_regression_count.get('万敌'), '首次不计数(防抖)'
    assert exec_state_of(s).tracked_bench_chars[0].star == 2, '首次回退 star 保旧(动画窗不毒化)'


def test_second_regression_files_evidence_without_stop(tmp_path, monkeypatch) -> None:
    """连续第 2 帧 2★→1★(pending 已挂起):确认真回退 → 采新写回 + 计数(r17 降级:
    留证不 stop,SIFT 身份域排查中)。"""
    import sr_od.application.currency_war.kernel.cw_reconcile as cr
    monkeypatch.setattr(cr, '_conflict', lambda *a, **k: None)
    ctx = _Ctx(monkeypatch, tmp_path)
    s = _sess(True)
    exec_state_of(s).star_regression_count = {'万敌': 1}   # 上一节点已确认过一次
    s.star_pending_regression = {'万敌': 1}   # 上帧已防抖挂起 → 本帧第二次
    reconcile_tracking(s, _read(1), [], None, source='t', ctx=ctx)
    # r17 降级:确认回退只留证不停机(每 5 次才留证一次);
    assert not ctx.stopped, 'r17 降级:star 回退留证不停机'
    # 计数持续累积
    assert exec_state_of(s).star_regression_count.get('万敌', 0) >= 2
    assert exec_state_of(s).tracked_bench_chars[0].star == 1, '连续 2 次确认采新'


def test_fifth_regression_leaves_evidence_no_stop(tmp_path, monkeypatch) -> None:
    """r17 降级语义:第 5 次**确认**回退留证(sentinel+截图)但不 stop。"""
    import sr_od.application.currency_war.kernel.cw_reconcile as cr
    monkeypatch.setattr(cr, '_conflict', lambda *a, **k: None)
    ctx = _Ctx(monkeypatch, tmp_path)
    s = _sess(True)
    exec_state_of(s).star_regression_count = {'万敌': 4}
    s.star_pending_regression = {'万敌': 1}   # 本帧 = 第 5 次确认
    reconcile_tracking(s, _read(1), [], None, source='t', ctx=ctx)
    flag = tmp_path / '.debug' / 'temp' / 'currency_war' / 'star_regression_hook.flag'
    assert flag.exists(), '第 5 次回退应留证 sentinel'
    assert not ctx.stopped, '降级:留证不 stop'


def test_recovered_star_resets_count(tmp_path, monkeypatch) -> None:
    """读回恢复(2★ 读回 2★):pending 与计数双清零,不累积误判。"""
    import sr_od.application.currency_war.kernel.cw_reconcile as cr
    monkeypatch.setattr(cr, '_conflict', lambda *a, **k: None)
    ctx = _Ctx(monkeypatch, tmp_path)
    s = _sess(True)
    exec_state_of(s).star_regression_count = {'万敌': 1}
    s.star_pending_regression = {'万敌': 1}
    reconcile_tracking(s, _read(2), [], None, source='t', ctx=ctx)
    assert not ctx.stopped
    assert '万敌' not in exec_state_of(s).star_regression_count
    assert '万敌' not in s.star_pending_regression


def test_debounce_bumps_only_one_copy(tmp_path, monkeypatch) -> None:
    """r58 review P1 回归:同名多副本(2★+1★)动画窗误读 → 防抖保旧只抬**一个**
    副本(数量守恒);旧循环把所有 star==_s 副本集体抬到旧最大星 → 真实 1★ 副本
    变假 2★,污染 merge/卖牌决策。"""
    import sr_od.application.currency_war.kernel.cw_reconcile as cr
    monkeypatch.setattr(cr, '_conflict', lambda *a, **k: None)
    ctx = _Ctx(monkeypatch, tmp_path)
    # tracking: 万敌 2★(板上)+ 万敌 1★(bench)
    s = _sess(True)
    exec_state_of(s).tracked_bench_chars.append(SimpleNamespace(char_id='万敌', star=1, slot=2,
                                                 position_pref='back'))
    # 读回:两副本都被动画窗读成 1★
    read = [SimpleNamespace(char_id='万敌', star=1, slot=1, position_pref='back'),
            SimpleNamespace(char_id='万敌', star=1, slot=2, position_pref='back')]
    reconcile_tracking(s, read, [], None, source='t', ctx=ctx)
    # T-308/ADR-0646 S2:tracked 恒 pad 态槽位表(定长 9 含 None)——迭代走占用滤 None
    stars = sorted(bc.star for bc in exec_state_of(s).tracked_bench_chars
                   if bc is not None)
    assert stars == [1, 2], f'只抬一个副本(数量守恒),got {stars}'


def test_pending_cleared_when_char_leaves(tmp_path, monkeypatch) -> None:
    """r58 review P2① 回归:角色离场(卖出/上场后读不到)→ pending 清除,防
    「下次登场时单次动画误读被误判连续第二次确认」。"""
    import sr_od.application.currency_war.kernel.cw_reconcile as cr
    monkeypatch.setattr(cr, '_conflict', lambda *a, **k: None)
    ctx = _Ctx(monkeypatch, tmp_path)
    s = _sess(True)
    # 首帧:万敌回退 → pending 挂起
    reconcile_tracking(s, _read(1), [], None, source='t', ctx=ctx)
    assert s.star_pending_regression.get('万敌') == 1
    # 次帧:万敌不在读数中(离场;双真读)→ pending 清除
    gone = [SimpleNamespace(char_id='藿藿', star=1, slot=1, position_pref='back')]
    reconcile_tracking(s, gone, [], None, source='t', ctx=ctx)
    assert '万敌' not in s.star_pending_regression, '离场清除 pending'
