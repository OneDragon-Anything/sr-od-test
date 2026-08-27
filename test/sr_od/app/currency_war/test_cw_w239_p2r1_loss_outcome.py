"""行为锁:P2r1 死亡局 outcome 的 plane 归属与落账(遥测缺口)。

缺口两形态(replay 实证,44 例 P2r1 死亡局复算):
- **败局行结构性缺失**(主导):输轮 outcome 写入点挂分支3b(「前往结算」OCR 文本门),
  但失败结算页主通道是分支1f(模板门,先于 3b)——1f 命中即翻页返回,从不落行;
  只有 1f 模板偶然 miss 才漏到 3b 落行 → 行落账取决于模板竞争。
- **plane 错归属 P1**:plane/round 取 read_phase_round last-known 缓存,P1→P2 过场后
  首个结算前若无帧成功读到「2-1」,缓存停在 (1,9) → 行落 (1,9) + node_type=普通战斗
  (P1r9 恒为 boss,不可能;run_20260825_145641 等两例实锤)。

修复(观测链零行为变更,同 先例):
- 1f 翻页前补 telemetry-only 记录(不喂 on_round_end/last_hp/summary 链);
- 结算屏头部「X-Y」屏面真值升级为全路径采纳(W28 残留专用 → 单调门内恒采纳)。

纯逻辑/桩测试(monkeypatch 构造结算帧;不写真实 .debug)。
"""
from __future__ import annotations

import inspect
import time
from types import SimpleNamespace

from sr_od.application.currency_war.cw_performance import RoundOutcome
from sr_od.application.currency_war.cw_state import GameState


class _OcrItem(SimpleNamespace):
    """OCR 结果桩(.data 文本 + .y 坐标,fp 指纹需要)。"""


def _make_loop(monkeypatch, *, ocr_texts: list[str], read_phase: tuple[int, int],
               killed=None, hp_confidence: float = 0.0):
    """构 battle_loop 桩:bypass __init__,喂 _record_round_outcome/_record_loss_page 依赖面。

    read_phase_round 桩返 ``read_phase``(模拟 last-known 缓存态);read_round_outcome
    桩按入参回显 plane/round 并可控 killed/hp_confidence;cw_telemetry 写端 monkeypatch
    捕获(自动还原);strategy.on_round_end 记调用次数(telemetry-only 面断言用)。
    """
    from sr_od.application.currency_war.operations import battle_loop as bl

    captured: list[dict] = []
    on_round_end_calls: list[int] = []

    def _fake_record_outcome(outcome, source: str = '') -> None:
        captured.append({'outcome': outcome, 'source': source})

    monkeypatch.setattr(bl.cw_telemetry, 'record_outcome', _fake_record_outcome)
    monkeypatch.setattr(bl.cw_telemetry, 'record_exogenous', lambda *a, **k: None)
    monkeypatch.setattr(bl, 'read_phase_round', lambda ctx, screen: read_phase)

    def _fake_read_outcome(ctx, screen, *, plane, round_num, comp_tag,
                           node_type='普通战斗'):
        return RoundOutcome(round_num=round_num, plane=plane, node_type=node_type,
                            comp_tag=comp_tag, hp_after=0, hp_confidence=hp_confidence,
                            killed=killed)

    monkeypatch.setattr(bl, 'read_round_outcome', _fake_read_outcome)

    class _Loop(bl.CurrencyWarRunLoop):
        def __init__(self):  # noqa: D107  桩:bypass SrOperation.__init__
            self._iter = 1
            self._is_new_match = True
            self._run_start_ts = time.monotonic() - 9999.0   # 超宽限:非残留
            self._first_settlement_seen = False
            self._settle_page1_progress = None
            self._battle_ts = object()   # 哨兵值:断言 telemetry-only 不清它
            self.ctx = SimpleNamespace(
                cw_match=SimpleNamespace(
                    session=SimpleNamespace(target_comp=None,
                                            last_state=GameState(),
                                            last_hp=None, last_hp_t=None),
                    strategy=SimpleNamespace(
                        on_round_end=lambda *a, **k: on_round_end_calls.append(1)),
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

    return _Loop(), captured, on_round_end_calls


# ===== 修复②:结算屏「X-Y」屏面真值全路径(根因=last-known 缓存位面切换滞后) =====


def test_win_settlement_screen_truth_overrides_stale_p1_cache(monkeypatch) -> None:
    """P1→P2 过场后首结算:缓存停在 (1,9),屏面「2-1」→ 行落 plane=2/r1。

    即 replay 实锤的错归属形态(run_20260825_145641:node_type=普通战斗 落在 (1,9),
    P1r9 恒为 boss 不可能)——屏面真值在读时点,不依赖过场后是否有帧读到「2-1」。
    """
    op, captured, _ = _make_loop(
        monkeypatch, read_phase=(1, 9),
        ocr_texts=['挑战成功', '2-1', '战斗', '小队生命值78i', '继续挑战'],
        hp_confidence=1.0)
    op._record_round_outcome(screen=None)
    assert captured[0]['outcome'].plane == 2
    assert captured[0]['outcome'].round_num == 1


def test_screen_truth_equal_to_cache_no_op(monkeypatch) -> None:
    """屏面真值与 last-known 一致(位面内常规轮)→ 原值原样,不引入新行为。"""
    op, captured, _ = _make_loop(
        monkeypatch, read_phase=(1, 6),
        ocr_texts=['挑战成功', '1-6', '战斗'], hp_confidence=1.0)
    op._record_round_outcome(screen=None)
    assert (captured[0]['outcome'].plane, captured[0]['outcome'].round_num) == (1, 6)


def test_screen_truth_behind_cache_rejected(monkeypatch) -> None:
    """屏面解析落后 last-known(OCR 假阳形态,如把 '1-4' 误读在 (1,6) 帧)→ 拒,保缓存。

    单调门镜像 read_phase_round 的单调守卫;位面前进 (1,9)→(2,1) 合法不受影响
    (t 序 (2-1)*9+1=10 > 9,见 test_win_settlement_screen_truth_overrides_stale_p1_cache)。
    """
    op, captured, _ = _make_loop(
        monkeypatch, read_phase=(1, 6),
        ocr_texts=['挑战成功', '1-4', '战斗'], hp_confidence=1.0)
    op._record_round_outcome(screen=None)
    assert captured[0]['outcome'].round_num == 6


def test_screen_unparseable_keeps_last_known(monkeypatch) -> None:
    """屏面解析不出(无头部词/噪声)→ last-known 兜底,零回归。"""
    op, captured, _ = _make_loop(
        monkeypatch, read_phase=(2, 1),
        ocr_texts=['??', 'xx'], hp_confidence=1.0)
    op._record_round_outcome(screen=None)
    assert (captured[0]['outcome'].plane, captured[0]['outcome'].round_num) == (2, 1)


# ===== 修复①:失败结算页(1f)telemetry-only 补录 =====


def test_loss_page_records_row_telemetry_only(monkeypatch) -> None:
    """败局页(killed=False)→ 落一行 source='loss_page';零策略/循环状态面。

    断言面:on_round_end 不被调(不喂 performance/last_hp → prep 行为面零变更)、
    _battle_ts 不清(ADR-0250 战斗窗口维持 1f 原语义)、_last_outcome_t 不写
    (killed 兜底对比链不受新路径扰动)。
    """
    op, captured, on_round_end_calls = _make_loop(
        monkeypatch, read_phase=(2, 1),
        ocr_texts=['挑战结束', '2-1', '战斗', '-22', '挑战进度', '前往结算'],
        killed=False)
    _battle_ts_sentinel = op._battle_ts
    op._record_loss_page(screen=None)
    assert len(captured) == 1
    assert captured[0]['source'] == 'loss_page'
    o = captured[0]['outcome']
    assert o.plane == 2 and o.round_num == 1
    assert o.killed is False
    assert on_round_end_calls == []                    # 策略面零变更
    assert op._battle_ts is _battle_ts_sentinel        # ADR-0250 窗口语义不变
    assert getattr(op, '_last_outcome_t', None) is None   # killed 对比链不扰动
    assert getattr(op, '_last_outcome_hp', None) is None  # summary 真值链不扰动


def test_loss_page_fingerprint_dedupe(monkeypatch) -> None:
    """同屏指纹防重:同帧重入只记一次(与 3b 共用 _last_loss_fp);换帧再记。"""
    op, captured, _ = _make_loop(
        monkeypatch, read_phase=(2, 1),
        ocr_texts=['挑战结束', '2-1', '战斗', '-22'], killed=False)
    op._record_loss_page(screen=None)
    op._record_loss_page(screen=None)   # 同屏(点击未生效停留)→ 不重复
    assert len(captured) == 1
    op.ctx.ocr_service.get_ocr_result_list = lambda image, rect=None, color_range=None, crop_first=False: [
        _OcrItem(data=t, y=i * 20) for i, t in enumerate(
            ['挑战结束', '2-2', '战斗', '-7'])]
    op._record_loss_page(screen=None)   # 新败局帧 → 新行
    assert len(captured) == 2
    assert captured[1]['outcome'].round_num == 2


def test_loss_page_non_defeat_killed_gate(monkeypatch) -> None:
    """killed 非 False(位面通关过渡页误入 1f 门/OCR 未判)→ 不落行,防伪行进语料。"""
    op, captured, _ = _make_loop(
        monkeypatch, read_phase=(1, 9),
        ocr_texts=['挑战结束', '1-9首领', '战斗'], killed=None)
    op._record_loss_page(screen=None)
    assert captured == []


def test_loss_page_failures_do_not_raise(monkeypatch) -> None:
    """OCR 服务抛错 → 补录吞异常不阻塞对局(观测为辅)。"""
    op, captured, _ = _make_loop(
        monkeypatch, read_phase=(2, 1), ocr_texts=[], killed=False)
    def _boom(**kw):
        raise RuntimeError('ocr down')
    op.ctx.ocr_service.get_ocr_result_list = _boom
    op._record_loss_page(screen=None)   # 不抛
    assert captured == []


# ===== 弱锁保底:1f 真接线、3b 原路径保留 =====


def test_branch_wiring_in_source() -> None:
    """loop 源码弱锁:1f 分支调 _record_loss_page;3b 原输轮记录仍在。"""
    from sr_od.application.currency_war.operations import battle_loop
    src = inspect.getsource(battle_loop.CurrencyWarRunLoop.loop)
    # 1f(失败结算页)翻页前补录
    assert '_record_loss_page(screen)' in src
    # 3b 原「前往结算」输轮记录路径保留(fp 防重共用,1f miss 时兜底)
    assert "btn == '前往结算'" in src
    assert '_record_round_outcome(screen)   # killed/progress_delta 由屏文本判定' in src
