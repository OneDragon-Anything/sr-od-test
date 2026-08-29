"""W501 金读数稳定门 + gold_delta 分级告警测试。

背景(实机 12 局 20 条 gold_delta 冲突,4 条大额 16-40 金,W489 审计感知面):
局收入在轮/位面切换后入账计数器仍在跳,单帧读金拿入账前旧值 → 开店金系统性
偏低(息线/花金义务整体错位)。修 = ``read_gold_settled`` 多帧稳定门 + 大额
冲突升级 warning 告警行(检索锚 ``[cw!][alarm][gold_delta]``)。
"""
import sys
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

import sr_od.application.currency_war.cw_observation as observation  # noqa: E402
import sr_od.application.currency_war.kernel.cw_observe as obs_mod  # noqa: E402


class _RecordingLog:
    """替身 logger:记录 warning 调用(真实 log_utils 写全局文件,不便断言)。"""

    def __init__(self):
        self.warnings: list[str] = []

    def warning(self, msg, *args):
        self.warnings.append(msg % args if args else msg)

    def info(self, msg, *args):
        pass


class _FakeController:
    """按序吐预置帧的假控制器(screenshot() 返回队列头,空则复用末帧)。"""

    def __init__(self, frames):
        self.frames = list(frames)

    def screenshot(self):
        return self.frames.pop(0) if self.frames else self.frames[-1] if self.frames else None


class _Ctx:
    def __init__(self, controller=None):
        self.controller = controller


# ===== read_gold_settled 稳定门 =====


def test_gold_settled_no_controller_single_read(monkeypatch):
    """无控制器(离线/单测)→ 单帧读原值,不轮询(行为与修前一致)。"""
    reads = iter([75])
    monkeypatch.setattr(observation, 'read_gold_opt', lambda ctx, screen: next(reads))
    assert observation.read_gold_settled(_Ctx(controller=None), None) == 75


def test_gold_settled_static_two_frames_agree(monkeypatch):
    """静止屏:第二帧一致 → 直接采信(无冲突行、无告警)。"""
    monkeypatch.setattr(observation, 'read_gold_opt', lambda ctx, screen: 60)
    conflicts: list[tuple] = []
    monkeypatch.setattr(observation, 'obs_conflict', lambda *a, **kw: conflicts.append(a))
    monkeypatch.setattr(observation, 'time', type('T', (), {'sleep': staticmethod(lambda s: None)}))
    ctx = _Ctx(controller=_FakeController([None, None, None]))
    assert observation.read_gold_settled(ctx, None) == 60
    assert conflicts == []


def test_gold_settled_ticking_takes_last_and_conflicts(monkeypatch):
    """漂移帧复现锁:首帧 75(入账前)→ 末帧 115(入账后)= 实机 P3 r1 漂移序列。

    采末帧 + obs_conflict 留证(不静默给错值:采了哪个值判读侧可见)。
    """
    monkeypatch.setattr(observation, 'read_gold_opt',
                        lambda ctx, screen: ctx.controller.screenshot())
    conflicts: list[tuple] = []
    monkeypatch.setattr(observation, 'obs_conflict', lambda *a, **kw: conflicts.append(a))
    monkeypatch.setattr(observation, 'time', type('T', (), {'sleep': staticmethod(lambda s: None)}))
    ctx = _Ctx(controller=_FakeController([75, 115, 115]))
    assert observation.read_gold_settled(ctx, None) == 115, '计数器在跳时取末帧(入账后真值)'
    assert len(conflicts) == 1
    assert conflicts[0][0] == 'gold' and conflicts[0][1] == 75 and conflicts[0][2] == 115


def test_gold_settled_ticking_timeout_still_takes_last(monkeypatch):
    """计数器跳满补采窗仍未停 → 仍取末帧并留证(不无限轮询)。"""
    seq = iter([75, 90, 100, 110])
    monkeypatch.setattr(observation, 'read_gold_opt', lambda ctx, screen: next(seq))
    conflicts: list[tuple] = []
    monkeypatch.setattr(observation, 'obs_conflict', lambda *a, **kw: conflicts.append(a))
    monkeypatch.setattr(observation, 'time', type('T', (), {'sleep': staticmethod(lambda s: None)}))
    ctx = _Ctx(controller=_FakeController([]))
    assert observation.read_gold_settled(ctx, None) == 110
    assert len(conflicts) == 1


# ===== gold_delta 分级告警 =====


def _run_conflict(monkeypatch, tmp_path, old, new):
    """跑一次真实 obs_conflict(落盘指到 tmp_path),返回告警行列表。"""
    fake_log = _RecordingLog()
    monkeypatch.setattr(obs_mod, '_log', fake_log)
    monkeypatch.setattr(obs_mod, '_CONFLICT_JOURNAL', tmp_path / 'conf.jsonl')
    obs_mod.obs_conflict('gold_delta', old, new, None,
                         verdict='留证-动作账vs读数不等', source='shop_spend_audit')
    return fake_log.warnings


def test_gold_delta_big_gap_alarms(monkeypatch, tmp_path):
    """|gap|>10 → warning 告警行(检索锚 [cw!][alarm][gold_delta]),W489 实测大额漂移 39→79。"""
    warns = _run_conflict(monkeypatch, tmp_path, 39, 79)
    assert len(warns) == 1
    assert '[cw!][alarm][gold_delta]' in warns[0]
    assert 'gap=40' in warns[0]


def test_gold_delta_small_gap_stays_evidence_only(monkeypatch, tmp_path):
    """|gap|≤10 维持留证不告警(边界 gap=10 不告警,gap=11 告警)。"""
    assert _run_conflict(monkeypatch, tmp_path, 5, 7) == []
    assert _run_conflict(monkeypatch, tmp_path, 32, 42) == []
    warns = _run_conflict(monkeypatch, tmp_path, 32, 44)
    assert len(warns) == 1 and '[cw!][alarm][gold_delta]' in warns[0]


def test_gold_delta_none_values_no_alarm(monkeypatch, tmp_path):
    """非数值(None 等)不告警也不崩(best-effort hook 契约)。"""
    assert _run_conflict(monkeypatch, tmp_path, None, 20) == []


# ===== 3 位数金读取能力锁(漂移方向防线) =====


def test_gold_opt_reads_3_digit_value():
    """历史帧锁:备战帧 3 位数金(201)完整读出,不被裁成 2 位。

    帧 = sr-od-test/screens/currency_war/gold_3digit_prep.png(实机备战屏存档,
    离线回放 read_gold_opt=201;防未来 area 收紧/OCR 回归把 3 位数金读低 ——
    W489 漂移方向即「金被读低」)。
    """
    from one_dragon.base.geometry.rectangle import Rect
    from one_dragon.base.matcher.ocr.ocr_service import OcrService
    from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
    from one_dragon.utils import cv2_utils as cvu

    screen = cvu.read_image(str(_REPO / 'screens/currency_war/gold_3digit_prep.png'))
    assert screen is not None

    class _A:
        def __init__(self, name, rect):
            self.area_name = name
            self.pc_rect = rect

    class _SI:
        area_list = [_A('文本-金币数', Rect(1610, 890, 1690, 945))]

    class _Loader:
        def get_screen(self, screen_name):
            return _SI()

    class _Ctx:
        def __init__(self):
            self.ocr_service = OcrService(OnnxOcrMatcher())
            self.screen_loader = _Loader()

    ctx = _Ctx()
    ctx.ocr_service.ocr_matcher.init_model()
    v = observation.read_gold_opt(ctx, screen)
    assert v == 201, f'3 位数金被误读为 {v}(裁首位/OCR 回归)'
    assert np is not None
