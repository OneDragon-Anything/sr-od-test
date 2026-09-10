"""test_cw_telemetry_contract 主题锁——遥测合同:唯一 schema 锁 + 写端行为锁 + supply_pick 链路锁。

覆盖面(四类承重件):
- 唯一 schema 锁(OBS_KEYS 登记门):观测分键计数容器缺席 → 惰性建空 dict,
  且全部键落在 LOCK_PATH_OBS_KEY_PREFIXES 登记前缀族内(一键族一锁,
  schema/注册表级守卫——新增键未登记即红);
- 写端行为锁 1 条:败局页补录(ADR-0583 拆两半)——落一行 source='loss_page',
  观察半/策略半零写入(telemetry-only 边界);
- supply_pick 链路锁:消费权边界否定墓碑(禁回退空壳帧形态 extra={'phase':
  'supply_pick'} 单键字典;节点侧禁 consume 暂存槽,消费权=cw_loop 合成结算行)。

来源指针(2026-09-09 目标形态重建批,断言零改动迁移):
- test_cw_lock_path_obs_keys.py@工作树(schema 登记门段);
- test_cw_telemetry_collect.py@HEAD(写端行为锁;文件在飞 M,以已提交内容为
  搬水源,其退役随并行批落地后二轮);
- test_cw_telemetry_batch.py(supply_pick 消费权否定墓碑,该源随迁退役)。
挂起(二轮吸收):D4 供给写入端全链断言(test_do_action_pick_writes_supply_pick_
decision_frame)现存于 telemetry_collect 在飞工作树增量(未提交,禁搬)——
并行批落地后迁入本文件补齐「经生产 _do_action 全链」半边,本文件现持
消费权否定墓碑为已提交侧代表。
其余历史锁已退役(git 可复活)。
"""
from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

from sr_od.application.currency_war.kernel import cw_intention as ci
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    update_intention,
)
from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

# ==================== 唯一 schema 锁:OBS_KEYS 登记门(自 test_cw_lock_path_obs_keys.py 迁入) ====================

def _plain_session() -> SimpleNamespace:
    """无 cw4_counters 容器的 session(缺省形态;helper 应惰性建空 dict)。"""
    return SimpleNamespace(plane_node_table=[1] * 7)   # P2 位面轮数真值(ADR-0366 语料:P2=7)


def test_default_session_counter_container_lazily_created():
    """容器缺席 → 惰性建空 dict 再计数(先例 = mandate_v1/entry 初始化面);
    全部键落在登记前缀族内(与既有键族零交集,设计稿 §4 条款③)。"""
    sess = _plain_session()
    update_intention(GameState(plane=2), IntentionState(), sess, None)
    ct = getattr(state_of(sess), 'cw4_counters', None)
    assert isinstance(ct, dict) and ct
    for k in ct:
        assert k.startswith(ci.LOCK_PATH_OBS_KEY_PREFIXES), f'未登记键:{k}'


# ==================== 写端行为锁 1 条(自 test_cw_telemetry_collect.py@HEAD 迁入) ====================

class _OcrItem(SimpleNamespace):
    """OCR 结果桩(.data 文本 + .y 坐标,fp 指纹需要)。"""


def _w239_p2r1_loss_outcome_make_loop(monkeypatch, *, ocr_texts: list[str], read_phase: tuple[int, int],
               killed=None, hp_confidence: float = 0.0):
    """构 cw_screen_battle_wait 桩:bypass __init__,喂 _record_round_outcome/_record_loss_page 依赖面。

    (W971 05-battle §1 P4:结算链自 cw_loop 收编 CwScreenBattleWait,本桩随迁。)
    read_phase_round 桩返 ``read_phase``(模拟 last-known 缓存态);read_round_outcome
    桩按入参回显 plane/round 并可控 killed/hp_confidence;cw_telemetry 写端已随
    删除波 1 退役(零落盘零零写入);观察半写入面(ADR-0583 拆两半)以真实
    StrategySession 承载,断言 telemetry-only 面零写入(performance.history/
    pending 槽均空)。
    """
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_battle_wait as bwo,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )

    monkeypatch.setattr(bwo, 'read_phase_round', lambda ctx, screen: read_phase)

    def _fake_read_outcome(ctx, screen, *, plane, round_num, comp_tag,
                           node_type='普通战斗'):
        from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
        return RoundOutcome(round_num=round_num, plane=plane, node_type=node_type,
                            comp_tag=comp_tag, hp_after=0, hp_confidence=hp_confidence,
                            killed=killed)

    monkeypatch.setattr(bwo, 'read_round_outcome', _fake_read_outcome)

    class _Op(bwo.CwScreenBattleWait):
        def __init__(self):  # noqa: D107  桩:bypass SrOperation.__init__
            self._st = bwo.SettlementState(
                run_start_ts=time.monotonic() - 9999.0,   # 超宽限:非残留
                is_new_match=True,
                battle_ts=object())   # 哨兵值:断言 telemetry-only 不清它
            self._unknown_streak = 0
            # 观察半直写面(ADR-0583):真实 StrategySession 承载
            #(performance/pending_round_outcomes 等字段齐备,零桩面特判)
            _sess = StrategySession()
            _sess.last_state = GameState()
            state_of(_sess)
            self.ctx = SimpleNamespace(
                cw_match=SimpleNamespace(
                    session=_sess,
                    strategy=SimpleNamespace(),
                ),
                ocr_service=SimpleNamespace(
                    get_ocr_result_list=lambda image, rect=None, color_range=None,
                    crop_first=False: [
                        _OcrItem(data=t, y=i * 20) for i, t in enumerate(ocr_texts)]),
            )
            self._cw_config = None

        def round_by_ocr(self, screen, word, **kw):
            return SimpleNamespace(is_success=False)

        def round_by_find_area(self, screen, screen_name, area_name, **kw):
            return SimpleNamespace(is_success=False)   # T#103:boss 判定改 area(标识-首领)

    return _Op()


def test_loss_page_records_row_telemetry_only(monkeypatch) -> None:
    """败局页(killed=False)→ telemetry-only 补录(删除波 1 后**零落盘零写入**)。

    断言面(ADR-0583 拆两半语义重推):telemetry-only 不写观察半
    (performance.history 空/last_streak 不动/last_hp 不写)也不写策略半
    (pending 槽空)→ prep 行为面零变更;_battle_ts 不清(ADR-0250 战斗
    窗口维持 1f 原语义)、_last_outcome_t 不写(killed 兜底对比链不受新
    路径扰动)。原 source='loss_page' 行来源标记随 outcomes 流写入端退役。
    """
    op = _w239_p2r1_loss_outcome_make_loop(
        monkeypatch, read_phase=(2, 1),
        ocr_texts=['挑战结束', '2-1', '战斗', '-22', '挑战进度', '前往结算'],
        killed=False)
    _battle_ts_sentinel = op._st.battle_ts
    op._record_loss_page(screen=None)
    _sess = op.ctx.cw_match.session
    assert len(_sess.performance.history) == 0         # 观察半零写入
    assert _sess.last_streak == 0                      # streak 不动(缺省)
    assert _sess.last_hp is None
    assert _sess.pending_round_outcomes == []          # 策略半不入槽
    assert op._st.battle_ts is _battle_ts_sentinel     # ADR-0250 窗口语义不变
    assert op._st.last_outcome_t is None               # killed 对比链不扰动
    assert op._st.last_outcome_hp is None              # summary 真值链不扰动


# ==================== supply_pick 链路锁(自 test_cw_telemetry_batch.py 迁入) ====================

def test_run_supply_node_pick_consumption_boundary() -> None:
    """否定墓碑双条(肯定性 `'supply_pick' in src` 在场断言已删——弱接线
    存在性由行为侧 record_decision 测试覆盖):①禁回退空壳帧形态
    (`extra={'phase': 'supply_pick'}` 单键字典,选定快照丢失);②消费权
    边界 = cw_loop 合成结算行,节点侧禁 consume 暂存槽。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_supply_node,
    )
    src = Path(cw_screen_supply_node.__file__).read_text(encoding='utf-8')
    assert "extra={'phase': 'supply_pick'}" not in src, (
        '选定快照应并入 extra 字典(空壳帧=本批改造前形态)')
    assert 'tel_state.consume_last_supply_pick' not in src, (
        '节点侧禁消费暂存槽(消费权=cw_loop 合成结算行)')
