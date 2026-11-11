"""位面情报写门随机态分支测试(镜像 src =
kernel/cw_screen_report/plane_intel.py 的 report_screen_plane_intel_obs;
按 src 镜像规范落位——存量平铺 test_screen_report_ports.py 保留现役分支
回归,本文件只辖 T-45 新增分支)。

测试面依据 = T-45 敌后破坏设计稿(原件已退役;§ 号 = 原稿节序)§2.2 接入调用 3 + §4 锁 3(attack-v2
S3/C3 扩):词缀写门三分支的**随机态支**——
- 随机态状态容器 + 非空读数 → observe 覆盖转正、差异落 logic_rand_outcome、
  等值零台账(被覆盖对象是猜测不是真值,「空表覆写抹掉已有真值」的
  幂等门理由在本分支不适用);
- 随机态状态容器(删后空)+ 空列表读数 → observe 写空表转正(删尽态闭环:
  单词缀局删后名单 = [],读数 [] 是 obs 契约有效语义读数「空列表 =
  无词缀」,转正后补观察谓词解除);
- 随机态状态容器 + None 读数 → 不写、维持随机态(None = 本轮无此面/失读,
  非语义读数不进写门);
- obs 族新签名与现役 logic_action 签名并存(各分支各语义)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_screen_report.plane_intel import (
    CwScreenPlaneIntelObs,
    report_screen_plane_intel_obs,
)

_SIG_LA = ChannelSig(family='logic_action', actor='TestWriter', mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='TestWriter')


class _RowSink:
    """缺陷台账行收集(set_defect_sink 缺省关,fixture 装配 + 必达收尾;
    先例 = kernel/cw_gain_chain/test_on_env_gained.py 同族 fixture)。"""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        set_defect_sink(self.rows.append)

    def close(self) -> None:
        set_defect_sink(None)
        consume_defect_sink()

    def kinds(self) -> list[str]:
        return [r['kind'] for r in self.rows]


@pytest.fixture
def rows_sink() -> _RowSink:
    s = _RowSink()
    try:
        yield s
    finally:
        s.close()


def _rand_affix_gs(value: list[str]) -> GameState:
    """随机态词缀状态容器(删除分支猜测名单形态:logic_rand 来源直写)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic_rand(gs.enemy_affixes, list(value), produced_by='Test',
                        evidence='t:rand', sig=_SIG_LA)
    return gs


def test_rand_container_nonempty_reading_observes_through(
        rows_sink: _RowSink) -> None:
    """随机态状态容器 + 非空读数 → observe 覆盖转正(设计 §4 锁 3 主分支):
    来源翻 observation(谓词解除)、差异落 logic_rand_outcome 台账
    (随机效果落地预期内,无告警无停机)。"""
    gs = _rand_affix_gs(['开局不利', '库藏生锈'])
    report_screen_plane_intel_obs(gs, CwScreenPlaneIntelObs(
        on_screen=True, enemy_affixes=['库藏生锈']))
    assert gs.enemy_affixes.value == ['库藏生锈'], '实采值入状态容器'
    assert gs.enemy_affixes.source == 'observation', '覆盖转正(非 logic 直写)'
    assert rows_sink.kinds() == ['logic_rand_outcome'], \
        f'差异 = 随机效果落地台账行: {rows_sink.kinds()}'


def test_rand_container_equal_reading_zero_ledger(
        rows_sink: _RowSink) -> None:
    """随机态状态容器 + 等值读数 → 覆盖转正零台账(等值 = 零新信息不产行,
    来源仍翻 observation 转正)。"""
    gs = _rand_affix_gs(['库藏生锈'])
    report_screen_plane_intel_obs(gs, CwScreenPlaneIntelObs(
        on_screen=True, enemy_affixes=['库藏生锈']))
    assert gs.enemy_affixes.value == ['库藏生锈']
    assert gs.enemy_affixes.source == 'observation', '等值覆盖仍转正'
    assert rows_sink.kinds() == [], f'等值零台账: {rows_sink.kinds()}'


def test_rand_container_empty_reading_full_wipe_affirm(
        rows_sink: _RowSink) -> None:
    """删尽态闭环(设计 §4 锁 3 子锁,attack-v2 S3):随机态状态容器删后空([])
    + 空列表读数 → observe 写空表转正——被覆盖对象是猜测不是真值,
    空表覆写在本分支合法;转正后补观察谓词解除、闭环收敛。"""
    gs = _rand_affix_gs([])
    report_screen_plane_intel_obs(gs, CwScreenPlaneIntelObs(
        on_screen=True, enemy_affixes=[]))
    assert gs.enemy_affixes.value == [] and \
        gs.enemy_affixes.source == 'observation', '空表转正(删尽态闭环)'


def test_rand_container_none_reading_keeps_random_state() -> None:
    """随机态状态容器 + None 读数 → 不写、维持随机态(None = 本轮无此面/
    失读,非语义读数不进写门;补观察谓词下帧继续命中)。"""
    gs = _rand_affix_gs(['开局不利'])
    seq_before = gs.write_seq
    report_screen_plane_intel_obs(gs, CwScreenPlaneIntelObs(
        on_screen=True, enemy_affixes=None))
    assert gs.enemy_affixes.value == ['开局不利'], '值不变'
    assert gs.enemy_affixes.source == 'logic_rand', '维持随机态'
    assert gs.write_seq == seq_before, '零写'


def test_obs_branch_channel_sig_shape(monkeypatch) -> None:
    """随机态分支走 obs 族新签名(定死形状:obs/CwScreenPlaneIntel/
    货币战争-位面详情/read;与现役 logic_action 落账族签名并存),经
    状态流水捕获行断言。"""
    rows: list[dict] = []
    gs = _rand_affix_gs(['开局不利'])   # 前置写入在装 sink 之前,不入捕获
    from sr_od.application.currency_war.kernel import cw_game_state as gs_mod
    monkeypatch.setattr(gs_mod, '_STATE_JOURNAL_SINK', rows.append)
    monkeypatch.setattr(gs_mod, '_RUN_ID_PROVIDER', lambda: 'test-run')
    report_screen_plane_intel_obs(gs, CwScreenPlaneIntelObs(
        on_screen=True, enemy_affixes=['库藏生锈']))
    affix_rows = [r for r in rows
                  if r['row'] == 'write' and r['field'] == 'enemy_affixes']
    assert len(affix_rows) == 1, f'词缀行恰一笔: {len(affix_rows)}'
    sig = affix_rows[0]['sig']
    assert (sig['family'], sig['actor'], sig['screen'], sig['mode']) == \
        ('obs', 'CwScreenPlaneIntel', '货币战争-位面详情', 'read'), \
        f'obs 族新签名定死形状: {sig}'
    assert gs.enemy_affixes.evidence == 'plane_intel_affixes', \
        'evidence 沿实采语义段(分支只换渠道签名)'
