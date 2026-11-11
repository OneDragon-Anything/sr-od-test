"""check_env_pick_grants 取卡触发发放检查测试(镜像 src =
kernel/cw_env_grants.py 的该被测函数;按被测方法拆目录规范落位,先例 =
同目录 test_check_env_merge_grants.py)。

测试面依据 = 原稿锁面
原稿锁面§4 锁 2(§2.1(b) 落地形态):
- 条件矩阵:表外环境 / env 未激活 → 0 零写;
- gold None → 零写 + 缺陷台账留证(DEFECT_ENV_PICK_GRANT_SKIPPED;
  取卡事件不可重放,静默放弃 = 永久假账,用户裁定 2026-10-26);
- 含本张口径:held_after=1 → 金 +2(首张 2 金口径锁);held_after=3 →
  金 +6(金额 = coef×k 线性锁)。
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from sr_od.application.currency_war.kernel.cw_env_grants import (
    DEFECT_ENV_PICK_GRANT_SKIPPED,
    check_env_pick_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    consume_defect_sink,
    set_defect_sink,
)

_ENV = '策略大师'

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_SIG = ChannelSig(family='logic_action', actor='EnvPickGrantTest',
                  mode='compute')


class _RowSink:
    """缺陷台账行收集(set_defect_sink 缺省关,fixture 装配 + 必达收尾;
    先例 = 同目录 test_check_env_merge_grants.py 同名 helper)。"""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        set_defect_sink(self.rows.append)

    def close(self) -> None:
        set_defect_sink(None)
        consume_defect_sink()

    def kinds(self) -> list[str]:
        return [r['kind'] for r in self.rows]


@pytest.fixture
def rows_sink() -> Iterator[_RowSink]:
    s = _RowSink()
    try:
        yield s
    finally:
        s.close()


def _make_gs(*, env: str | None = _ENV, gold: int | None = 30) -> GameState:
    """观察面按参组装(gold None = 未观察形态,供缺陷留证分支)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if env is not None:
        gs.observe(gs.active_env, env, sig=_SIG_OBS)
    if gold is not None:
        gs.observe(gs.gold, gold, sig=_SIG_OBS)
    return gs


def test_short_circuit_off_table_and_env_free(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """条件矩阵前两序短路(T-46 设计 §4 锁 2):env 未激活(None/空链
    形态)/不在登记表(表外环境)→ 返回 0 且零写。"""
    for label, gs in (('env 未选择(None 形态)', _make_gs(env=None)),
                      ('env 空链', _make_gs(env='')),
                      ('表外环境', _make_gs(env='蓝海'))):
        seq_before = gs.write_seq
        assert check_env_pick_grants(gs, 1, sig=_SIG) == 0, label
        assert gs.write_seq == seq_before, f'{label} 零写'


def test_gold_unobserved_zero_write_defect_row(
        monkeypatch: pytest.MonkeyPatch,
        rows_sink: _RowSink) -> None:
    """gold None(T-46 设计 §4 锁 2 条件 3):零写 + 缺陷台账留证 kind
    落账(取卡事件不可重放,静默放弃 = 永久假账,用户裁定 D)。"""
    gs = _make_gs(gold=None)
    assert gs.gold.value is None
    seq_before = gs.write_seq
    assert check_env_pick_grants(gs, 2, sig=_SIG) == 0, '零写'
    assert gs.write_seq == seq_before, '金账零写'
    assert rows_sink.kinds() == [DEFECT_ENV_PICK_GRANT_SKIPPED], \
        f'缺陷 kind 落账: {rows_sink.kinds()}'


def test_first_pick_two_gold_inclusive_self(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """首张 2 金口径锁(T-46 设计 §4 锁 2;用户裁定 2026-10-26 含本张):
    在场 + held_after=1 → 金 +2,evidence =
    ``env_grant#策略大师#pick1``,通道 = logic(确定发放)。"""
    gs = _make_gs(gold=30)
    seq_before = gs.write_seq
    amount = check_env_pick_grants(gs, 1, sig=_SIG)
    assert amount == 2, f'首张 coef×1 = 2 金: {amount}'
    assert gs.gold.value == 32, '金账入账'
    assert gs.gold.source == 'logic', '确定发放走 logic 通道'
    assert gs.write_seq - seq_before == 1, '恰一笔字段写操作'
    assert gs.gold.evidence == f'env_grant#{_ENV}#pick1', 'evidence 形态'


def test_amount_linear_coef_times_held(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """金额 = coef×k 线性锁(T-46 设计 §4 锁 2):held_after=3 → 金 +6
    (第 3 张到手发 2×3)。"""
    gs = _make_gs(gold=30)
    assert check_env_pick_grants(gs, 3, sig=_SIG) == 6, 'coef×k = 2×3'
    assert gs.gold.value == 36, '金账入账'
    assert gs.gold.evidence == f'env_grant#{_ENV}#pick3', 'evidence 携 k'
