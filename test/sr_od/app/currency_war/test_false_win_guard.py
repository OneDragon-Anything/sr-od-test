"""假 win 守卫测试(M70 事故回归):plane 毒化/见过战败屏均不得判 win。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.obs.cw_observation import read_phase_round  # noqa: E402


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
    """单数字 fallback:仅 1(开局 1-1)合法;"8" 拒。"""
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
