"""遭遇双槽标定闸锁(P64 定谳批:补强通道标定注入)。

标定方法定谳(math_proofs P64,结构已证):ENCOUNTER_DSTAT_MAP 静态
dict[旗牌→stat] 标定域 = ∅——机制公式 stat=B+q+L+s(−m) 的自由项
未定界,带别(界 108)不是旗牌的函数,任何非空静态注入 = 假真值
(R29-6);ENCOUNTER_G_GOLD 金额非机制常量(节点收入=基础+息+连胜,
运行时变)且 ≥3 局观察值定带门未过(存量仅 1 可信单例 +8)。两槽
诚实缺省 None,数值 argmax 臂保持结构性不可达(双槽互锁,ADR-0536 §3)。

锁面:
1. dstat 缺省锁——双 4 费帧(绕过奖励闸)dstat=None ⇒ λ 键观测量
   缺失 fail 向选低难(拒因 dstat_map_none),禁置零续比;
2. 部分子集缺省锁——注入含部分旗牌键的映射时,未登记旗牌 ⇒
   dstat_missing fail-closed(诚实缺省逐键生效,禁拿其他键值冒充);
3. 复原链锚——provisional 注入→槽内可见→复位→缺席(测试注入复原
   纪律的执行面,provisional 槽为生产标定供给通道;生产缺省
   fail-closed 判读由锁 1 辖)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_events import EncounterOption
from sr_od.application.currency_war.kernel.cw_vocab import CwWorkFrame
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import encounter
from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import (
    provisional,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    lambda_death,
)

_FEE_L = EncounterOption(idx=0, difficulty=1, rewards=['随机4费角色×3'])
_FEE_H = EncounterOption(idx=1, difficulty=3, rewards=['随机4费角色×3'])


def _cell() -> lambda_death.LambdaCell:
    return lambda_death.LambdaCell(n=5, mono=0.3, ci_lo=0.30, ci_hi=0.31,
                                   label='可消费')


def _session() -> StrategySession:
    s = StrategySession()
    state_of(s).cw4_counters = {}
    return s


def _state() -> CwWorkFrame:
    return CwWorkFrame(gold=20, hp=100, plane=1, round_num=2)


@pytest.fixture()
def dstat_slot():
    """dstat 槽操作台:用后复位(测试纪律:改全局态必须复原)。"""
    yield
    provisional.reset('ENCOUNTER_DSTAT_MAP')


class TestDstatCalibrationGate:

    def test_dstat_none_default_fail_low(self, monkeypatch):
        """dstat 缺省锁(P64:静态标定域 ∅,生产恒 None):双 4 费帧
        绕过奖励闸后,λ 键观测量缺失 ⇒ 整体不可判 fail 向选低难——
        禁「拿旗牌值冒充 stat」续比(R29-6)。守卫移除(判据侧改从
        旗牌直推 stat)即红:拒因不再是 dstat_map_none。"""
        provisional.reset('ENCOUNTER_DSTAT_MAP')
        monkeypatch.setattr(lambda_death, '_LAMBDA_TABLE', {
            'D0|hp>40|P1|encounter': _cell(),
            'D1|hp>40|P1|encounter': _cell(),
        })
        sess = _session()
        pick = encounter.decide_encounter_ev([_FEE_L, _FEE_H], _state(),
                                             sess)
        assert pick.idx == _FEE_L.idx
        assert not pick.refresh
        assert 'dstat_map_none' in pick.reason
        assert state_of(sess).cw4_counters.get(
            'encounter_ev_fail_low_lambda_undecidable') == 1
        assert 'encounter_ev_pick' not in state_of(sess).cw4_counters

    def test_dstat_partial_map_missing_key_fail_closed(self, dstat_slot,
                                                        monkeypatch):
        """部分子集缺省锁:未来条件表注入含部分旗牌键(只 1→100)时,
        未登记旗牌(3)⇒ dstat_missing fail-closed——缺省逐键生效,
        已登记键不外溢冒充未登记键的真值。"""
        provisional.inject('ENCOUNTER_DSTAT_MAP', provisional.CalibValue(
            value={1: 100}, injected_form=True))
        monkeypatch.setattr(lambda_death, '_LAMBDA_TABLE', {
            'D0|hp>40|P1|encounter': _cell(),
            'D1|hp>40|P1|encounter': _cell(),
        })
        sess = _session()
        pick = encounter.decide_encounter_ev([_FEE_L, _FEE_H], _state(),
                                             sess)
        assert pick.idx == _FEE_L.idx
        assert not pick.refresh
        assert 'dstat_missing(diff=3)' in pick.reason

    def test_provisional_inject_reset_roundtrip(self, dstat_slot):
        """复原链锚:provisional 注入→槽内可见→复位→缺席(测试注入复原
        纪律的执行面;provisional 槽是生产标定供给通道,注入/复位失守在本
        文件内精确定位,跨文件消费方只会表现为难以归因的污染红)。复位后
        的生产 fail-closed 判读由 test_dstat_none_default_fail_low 辖。"""
        provisional.inject('ENCOUNTER_DSTAT_MAP', provisional.CalibValue(
            value={1: 100, 3: 150}, injected_form=True))
        assert provisional.get('ENCOUNTER_DSTAT_MAP') is not None
        provisional.reset('ENCOUNTER_DSTAT_MAP')
        assert provisional.get('ENCOUNTER_DSTAT_MAP') is None


if __name__ == '__main__':
    pytest.main([__file__])
