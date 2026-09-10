"""P1 配方对平铺遥测(sess_p1_pair)回归锁(删除波 1 重写)。

背景(W473 复盘,P1 观测盲区):决策层 P1 锁定的「配方对」产物
(IntentionState.p1_pair / transition_pair 过渡体系键二元组)的平铺标签
派生(p1_pair_label)是配对完成度买牌信号 A/B 的关键度量上游。

删除波 1(用户 2026-09-10 直迁裁定):sess_p1_pair 的 decisions 行落盘
面(record 站点/步进行接线)已随旧流写入端退役;本锁现辖——
- ``schema.p1_pair_label`` 派生口径(配方锁 p1_pair 优先,
  ①锁局 transition_pair 次选;空窗/无意向 = '');
- cw_screen_prep._record_step 退役壳(零写入,防半删);
- 旧台账兼容:无 sess_p1_pair 键的历史行经 cw_replay_reader 读取
  不炸(dataclass 已知字段过滤 + 缺省 '')。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    serialize_intention,
)
from sr_od.application.currency_war.telemetry import schema
from sr_od.application.currency_war.telemetry.cw_replay_reader import from_dict
from sr_od.application.currency_war.telemetry.schema import DecisionTrace

# ===== 派生口径:p1_pair_label =====


def test_label_recipe_lock_pair() -> None:
    """配方锁局:p1_pair 二元组 → 'A+B' 体系键串。"""
    ist = IntentionState(phase='locked', p1_pair=('仙舟', '列车同行'))
    assert schema.p1_pair_label(ist) == '仙舟+列车同行'


def test_label_transition_pair_fallback() -> None:
    """①资格锁局:p1_pair 空、transition_pair 非空 → 取副方向。"""
    ist = IntentionState(phase='locked', transition_pair=('持续伤害', '贝洛伯格'))
    assert schema.p1_pair_label(ist) == '持续伤害+贝洛伯格'


def test_label_empty_when_unlocked_or_absent() -> None:
    """空窗(未锁)/空意向状态机/None/非 dataclass 一律空串(纯观测不阻塞)。"""
    assert schema.p1_pair_label(IntentionState()) == ''
    assert schema.p1_pair_label(None) == ''
    assert schema.p1_pair_label(object()) == ''


# ===== record 站点:extra 透传 → decisions 行(删除波 1 退役)=====
# 原 4 锁(record 行透传非空/空串、_record_step 接线两支)钉的是 decisions
# 写入端形态,已随删除波 1 退役(git 可复活)。派生口径(p1_pair_label)
# 与读端兼容面继续由下方锁承——离线判读/sim 分析仍消费该标签派生。


# ===== 派生口径回归(签名面守卫)=====


def test_label_signature_stable() -> None:
    """派生签名面守卫:label 接受 dataclass/None/异型对象三态,纯观测不阻塞。"""
    assert schema.p1_pair_label(IntentionState(phase='locked',
                                               p1_pair=('仙舟', '列车同行'))) \
        == '仙舟+列车同行'
    assert schema.p1_pair_label(None) == ''


# ===== cw_screen_prep._record_step 退役壳 =====


def test_record_step_is_retired_noop_shell() -> None:
    """_record_step = no-op 壳(删除波 1):步进 decisions 行写入端退役,
    方法在场只为 harness 桩面契约;壳内零写入(防半删)。"""
    from pathlib import Path as _Path

    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_prep,
    )
    src = _Path(cw_screen_prep.__file__).read_text(encoding='utf-8')
    i_step = src.index('def _record_step')
    assert 'record_decision' not in src[i_step:i_step + 600], \
        '_record_step 壳内不得残留 decisions 写入(防半删)'


# ===== 旧台账兼容(cw_replay_reader 已知字段过滤)=====


def test_old_ledger_row_without_key_reads_fine() -> None:
    """历史行(无 sess_p1_pair 键)→ DecisionTrace 缺省空串,不炸。"""
    old_row = {'schema_version': 1, 'run_id': 'legacy', 'round_num': 3,
               'plane': 1, 'target_comp': ''}
    trace = from_dict(DecisionTrace, old_row)
    assert isinstance(trace, DecisionTrace)
    assert trace.sess_p1_pair == ''


def test_new_ledger_row_with_key_preserved() -> None:
    """新行(带键)读回不丢值——读端过滤是「滤未知」不是「滤新增」。"""
    new_row = {'run_id': 'r', 'sess_p1_pair': '仙舟+列车同行',
               'unknown_future_key': 1}   # 未知键被滤,新增键保留
    trace = from_dict(DecisionTrace, new_row)
    assert trace.sess_p1_pair == '仙舟+列车同行'


@pytest.mark.parametrize('pair', [('仙舟', '列车同行'), ()])
def test_label_matches_intention_serialization_source(pair: tuple) -> None:
    """标签与 serialize_intention 全量序列化中的 p1_pair 同源同值。"""
    ist = IntentionState(phase='locked' if pair else 'unlocked', p1_pair=pair)
    d = serialize_intention(ist)
    assert schema.p1_pair_label(ist) == '+'.join(d['p1_pair'])
