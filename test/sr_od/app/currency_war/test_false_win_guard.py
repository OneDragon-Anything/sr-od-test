"""假 win 守卫测试(M70 事故回归):plane 毒化/见过战败屏均不得判 win。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.obs.cw_observation import (  # noqa: E402
    read_phase_round,
)


class _FakeOcr:
    def __init__(self, blob: str):
        self.blob = blob

    def __call__(self, ctx, screen, rect):
        class _R:
            data = self.blob
        return [_R()]


class _Ctx:
    pass


def test_phase_round_rejects_plane_out_of_range(monkeypatch) -> None:
    """plane=8(A8 难度泄漏)必须拒——M70 假 win 根因。"""
    import sr_od.application.currency_war.obs.cw_observation as obs
    monkeypatch.setattr(obs, '_last_phase_round', None)
    monkeypatch.setattr(obs, 'reset_phase_round_cache', obs.reset_phase_round_cache)
    monkeypatch.setattr(obs, '_ocr', _FakeOcr('A8 8-8'))
    monkeypatch.setattr(obs, '_area_rect', lambda ctx, name: None)
    # OCR blob 抓 "8-8" → 值域守卫拒(不进缓存)
    got = read_phase_round(_Ctx(), None)
    assert got == (1, 1), f'plane=8 应被值域守卫拒(回退 1,1),实得 {got}'


def test_phase_round_digits_fallback_only_accepts_one(monkeypatch) -> None:
    """非格式读数(单数字错源如 "Lv.8")不得产出非默认值。

    旧语义「数字 fallback 分支拒非 1」已随 w891 延迟审计候选③退役:该分支
    唯一合法产出 (1,1) 与无历史兜底完全重合(结构零信息),整段删除 = 治本。
    本锁改钉删除后语义:错源单数字走无匹配路径 → last-known/默认兜底 (1,1),
    不再产生 fallback 冲突留证。"""
    import sr_od.application.currency_war.obs.cw_observation as obs
    monkeypatch.setattr(obs, '_last_phase_round', None)
    monkeypatch.setattr(obs, '_ocr', _FakeOcr('Lv.8'))
    monkeypatch.setattr(obs, '_area_rect', lambda ctx, name: None)
    got = read_phase_round(_Ctx(), None)
    assert got == (1, 1), f'单数字 8 应拒(非开局),实得 {got}'


def test_phase_round_normal_parse_unaffected(monkeypatch) -> None:
    """正常 "1-3" 解析不受影响。"""
    import sr_od.application.currency_war.obs.cw_observation as obs
    monkeypatch.setattr(obs, '_last_phase_round', None)
    monkeypatch.setattr(obs, '_ocr', _FakeOcr('回合 1-3'))
    monkeypatch.setattr(obs, '_area_rect', lambda ctx, name: None)
    assert read_phase_round(_Ctx(), None) == (1, 3)


def test_phase_round_digits_fallback_branch_removed() -> None:
    """源码锁:数字 fallback 分支已删(ocr_digits_fallback 全消失)。

    出处:w891 延迟审计候选③——该分支结构零信息(唯一合法产出与默认兜底
    重合),近两日 868 次被拒全为纯浪费;治本 = 删段,不留在证面。"""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[5] / 'src' / 'sr_od' / 'application'
           / 'currency_war' / 'obs' / 'cw_observation.py').read_text(encoding='utf-8')
    assert 'ocr_digits_fallback' not in src


def test_phase_round_wrong_source_digit_keeps_last_known(monkeypatch) -> None:
    """有历史时错源单数字 → 保旧(last-known),不产 (1,1) 毒化。"""
    import sr_od.application.currency_war.obs.cw_observation as obs
    monkeypatch.setattr(obs, '_last_phase_round', (2, 3))
    monkeypatch.setattr(obs, '_ocr', _FakeOcr('Lv.8'))
    monkeypatch.setattr(obs, '_area_rect', lambda ctx, name: None)
    assert read_phase_round(_Ctx(), None) == (2, 3)
