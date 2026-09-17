"""外环 boss 简报帧误派位面过渡防线锁(第五局 1-9 形态根治批)。

病理(第五局 1-9 实锤):boss 简报帧与位面过渡共享交互文案「点击空白处
继续」,但两屏位置不同(boss y≈770 波段 / 位面过渡 y≈930 波段)。boss 帧
标题「强敌来袭」被 OCR 误读(「强敌米」)击穿阶段一身份后,旧全帧裸文本
兜底被 boss 帧的共享文案命中 → 误派 CwScreenPlaneTransition 空 fail 循环
(「提示未出现」fail 每 2s 无限循环)。

修与锁(两件事;0p/0q 兜底已于 2026-09-16 随裁定退役——未建档实证的
故障形态不作兜底理由,身份 miss 的真实帧走未知兜底重试):
1. 阶段一位面过渡身份帧含 boss 判别片段(判别单一源消费)→ 接管派发
   BOSS 简报,不派位面过渡——位面节点锚可读 + 标题误读帧的排他;
2. boss 帧(位面锚 miss ∧ 判别片段 miss 的劣化形态)→ 全 loop 零派发,
   落未知兜底 retry(终端 = UNKNOWN_FAIL_THRESHOLD 重试耗尽 round_fail
   框架失败——不为无法追溯的形态预建兜底)。

驱动 = CwLoop 裸实例(``__new__`` 跳过 telemetry run 铸造/分配器构造
——测试零真实副作用)+ 全桩面(身份识别单点/OCR 读链/画面原语/决策帧
落盘/[cw-op] 行/两屏 op 替身);boss 判别用真单一源(is_boss_briefing_
texts)只桩 OCR 读链——锁的是「判别片段进不进派发裁决」,不是判别面
本身(判别面语义归 op 层锁)。
"""
from __future__ import annotations

from types import SimpleNamespace

from one_dragon.base.operation.operation_round_result import (
    OperationRoundResultEnum,
)
from test.sr_od.application.currency_war._cw_helpers import (
    Area as _Area,
)
from test.sr_od.application.currency_war._cw_helpers import (
    run_node as _run_node,
)

from sr_od.application.currency_war.operations import cw_loop as cw_loop_mod
from sr_od.application.currency_war.operations.cw_loop import CwLoop
from sr_od.application.currency_war.operations.cw_screen import (
    cw_screen_boss_briefing as bb_mod,
)

_FRAME = object()   # 稳定帧哨兵(读链桩只验判定,不断言内容)


class _StubScreenOp:
    """两屏 op 替身:构造记 ctx,execute 吐 success(排除通用网/重试干扰)。"""

    journal = ''

    def __init__(self, ctx):
        self.ctx = ctx

    def execute(self):
        return SimpleNamespace(success=True, status='stub-ok')


class _StubBoss(_StubScreenOp):
    journal = 'BOSS简报'


class _StubTransition(_StubScreenOp):
    journal = '位面过渡'


def _make_loop(test_context, monkeypatch, *, match_name, ocr_texts,
               transition_prompt_hit):
    """CwLoop 裸装配 + 全桩面(见模块头)。返回 (op, [cw-op] 行序列)。

    ``transition_prompt_hit`` = 位面过渡提示区桩命中(阶段一位面过渡身份
    miss 场景下,该区已无独立兜底分支消费——保留桩位防回归复活静默消费)。
    """
    op = CwLoop.__new__(CwLoop)
    op.ctx = test_context
    op._iter = 3                # 3+1=4:跳过 iter1 预检/焦点检查/首读分支
    op._stop_at_prep = False
    op._max_rounds = None
    op._battle_wait_active = False
    op._battle_ts = None
    op._settle = SimpleNamespace(battle_ts=None, saw_settlement=False,
                                 rounds_done=0)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_ocr',
                        lambda scr, text, **k: _Area(False))
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(
                            transition_prompt_hit
                            and s == '货币战争-位面过渡'
                            and a == '提示-点击空白继续'))
    monkeypatch.setattr(cw_loop_mod, 'get_match_screen_name',
                        lambda ctx, scr, screen_name_list=None: match_name)
    monkeypatch.setattr(cw_loop_mod, 'save_decision_frame',
                        lambda *a, **k: None)   # 留证面 no-op(零落盘)
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(cw_loop_mod, '_log_cw_op',
                        lambda name, pos, dur, outcome, detail='':
                        calls.append((name, outcome)))
    # boss 判别单一源保持真函数,只桩 OCR 读链(锁「片段进派发裁决」)
    monkeypatch.setattr(bb_mod, 'read_ocr_texts',
                        lambda ctx, scr: list(ocr_texts))
    monkeypatch.setattr(cw_loop_mod, 'CwScreenBossBriefing', _StubBoss)
    monkeypatch.setattr(cw_loop_mod, 'CwScreenPlaneTransition',
                        _StubTransition)
    return op, calls


def test_stage1_transition_identity_boss_frame_takeover(test_context,
                                                        monkeypatch) -> None:
    """锁1 阶段一排他:位面过渡身份帧含「强敌」片段(标题误读形态)→
    接管派发 BOSS 简报,零位面过渡派发。"""
    op, calls = _make_loop(
        test_context, monkeypatch, match_name='货币战争-位面过渡',
        ocr_texts=['强敌米', '点击空白处继续'], transition_prompt_hit=False)
    rs = _run_node(test_context, op, op.loop)
    assert calls == [('BOSS简报', 'ok')], f'boss 帧应接管派发 BOSS 简报:{calls}'
    assert rs.result == OperationRoundResultEnum.WAIT   # 替身成功 → 默认映射


def test_boss_frame_without_anchors_falls_to_unknown_fallback(
        test_context, monkeypatch) -> None:
    """锁2 劣化形态终端:boss 帧位面锚 miss ∧ 判别片段 miss(全帧只剩
    共享文案)→ 零派发,落未知兜底 retry(终端 = 停机留证,不为未建档
    形态预建兜底)。"""
    op, calls = _make_loop(
        test_context, monkeypatch, match_name=None,
        ocr_texts=['点击空白处继续'], transition_prompt_hit=False)
    rs = _run_node(test_context, op, op.loop)
    assert calls == [], f'boss 帧零派发(不误派位面过渡/BOSS):{calls}'
    assert rs.result == OperationRoundResultEnum.RETRY   # 未知兜底(streak 1)
