"""「X/Y」部署计数读链测试(团队规模超限态放行;既有夹具读数不变)。

锁的设计约定(契约正文 = ``cw_observation._validate_paddle_xy`` /
``_confirm_over_cap`` docstring;来源 = 备战屏团队规模超限态诊断:
选「高傲巨人」(持有者占 2 点团队规模)后画面红色 6/5,游戏静默拒绝出战):

- 约束验证器:X > Y 合法——超限态是游戏自己的红字告警态,旧先验 X ≤ Y 把它
  当误读拒信 → 读数持续 null、机器人看不见;绝对域 0 ≤ X ≤ 13、1 ≤ Y ≤ 13、
  Y ≥ level(14 = 斜杠字形丢失时枚举切分的前缀幻影形态,仍拒);
- 真实帧:局 43 三张保留帧(选光环后 / 卖出两次后 / 停留 2 小时后;红色「6/5」
  四源互证)离线读出 X=6 / Y=5;既有夹具读数不变(茶歇预告帧 4/5、
  deployed_2star 帧 4/4、shop_closed 帧 3/4、rail_badge_prep_r4 帧 6/7);
- 超限读数双帧确认门(与 cap 防抖同一条「域外读数跨帧**同值**才采信」纪律:超限是
  持续态、误读是瞬态):重读与首读同值且仍超限 → 采信 + 留证;重读超限但不同值
  (两次不同的瞬态误读)→ X 置 None 不按超限采信;重读不超限 → 采重读值(首读按
  误读);重读不可得 → X 置 None(cap 保留);
- 观察写端(``read_game_state`` 全量路径,生产 heavy 观察走的路):超限帧落
  状态容器 ``team_size_used``=6 / ``deploy_cap``=5;
- 证据行时机:``_read_deploy_paddle`` 的拒信证据只在两级解析都失败、且至少一级走到约束出口后发 1 条(带两级 OCR 文本);无字形 / 无数字的帧零证据;level 先验放宽成功的披露行照发;解析函数本身不发证据。
"""
from __future__ import annotations

import types
from typing import TYPE_CHECKING

import numpy
import pytest

import sr_od.application.currency_war.obs.cw_observation as mod
from sr_od.application.currency_war.obs.cw_observation import (
    DEPLOY_CAP_ABS_MAX,
    _confirm_over_cap,
    _validate_paddle_xy,
    read_deploy_cap,
    read_deployed_count,
)

if TYPE_CHECKING:
    from test.conftest import SrTestContext

#: 局 43 超限态保留帧(红色 6/5;归档自机器人拒信留证截图,三张跨 2.5 小时读数不变)。
_OVER_CAP_FRAMES: list[str] = [
    '超限6比5-选光环后', '超限6比5-卖出两次后', '超限6比5-停留2小时后',
]
#: 既有夹具基线(画面名, 子态, X, Y)——改约束前实测读数,改后必须逐位不变。
_BASELINE_FRAMES: list[tuple[str, str, int, int]] = [
    ('货币战争-备战-茶歇预告', '茶歇预告态', 4, 5),
    ('货币战争-备战', 'deployed_2star', 4, 4),
    ('货币战争-备战', 'shop_closed', 3, 4),
    ('货币战争-备战', 'rail_badge_prep_r4', 6, 7),
]


@pytest.mark.parametrize(('x', 'y', 'level', 'ok'), [
    (6, 5, 5, True),       # 超限态:占用 6 > 上限 5(本迭代要放行的形态)
    (6, 5, None, True),
    (5, 5, None, True),    # 板满
    (0, 3, None, True),    # 空板
    (DEPLOY_CAP_ABS_MAX, DEPLOY_CAP_ABS_MAX, None, True),
    (14, 5, 5, False),     # 斜杠丢失枚举切分的前缀幻影形态,超绝对上界仍拒
    (-1, 5, None, False),
    (5, 0, None, False),   # cap 不可能为 0
    (5, 14, None, False),  # cap 超板面物理上界
    (3, 4, 5, False),      # cap < level 不可能
    (6, 5, 6, False),
])
def test_validate_paddle_xy_domain(x: int, y: int, level: int | None,
                                   ok: bool) -> None:
    """约束验证器:X > Y 合法,绝对域与 level 先验不变。"""
    assert _validate_paddle_xy(x, y, level) is ok


def test_over_cap_frames_read_6_over_5(test_context: SrTestContext) -> None:
    """三张超限态保留帧离线读出 X=6 / Y=5(旧读链读出 None)。"""
    for state in _OVER_CAP_FRAMES:
        if not test_context.has_screen('货币战争-备战', state):
            pytest.skip(f'存档截图缺失:screens/货币战争-备战/{state}.webp')
    for state in _OVER_CAP_FRAMES:
        img = test_context.load_screen('货币战争-备战', state)
        assert read_deployed_count(test_context, img) == 6, \
            f'{state}: X 应读出规模占用 6'
        assert read_deploy_cap(test_context, img) == 5, f'{state}: Y 应读出上限 5'
        assert read_deploy_cap(test_context, img, level=5) == 5, \
            f'{state}: 带 level 先验 cap 仍应读出 5'


def test_baseline_frames_unchanged(test_context: SrTestContext) -> None:
    """既有夹具读数逐位不变(含 X == Y 板满帧与 X < Y 帧)。"""
    for screen, state, exp_x, exp_y in _BASELINE_FRAMES:
        if not test_context.has_screen(screen, state):
            pytest.skip(f'存档截图缺失:screens/{screen}/{state}.webp')
    for screen, state, exp_x, exp_y in _BASELINE_FRAMES:
        img = test_context.load_screen(screen, state)
        assert read_deployed_count(test_context, img) == exp_x, f'{state}: X 变了'
        assert read_deploy_cap(test_context, img) == exp_y, f'{state}: Y 变了'


def _gate_env(monkeypatch: pytest.MonkeyPatch, second_read,
              ) -> tuple[types.SimpleNamespace, list[tuple]]:
    """确认门夹具:门入参首读 6/5(直接传入),重读走 ``second_read``
    (scripted 读链替身);返回 (假 ctx, obs_conflict 捕获列表)。"""
    calls: list[tuple] = []
    seq = iter([second_read])

    def fake_read(ctx, screen, level=None):
        return next(seq)

    def fake_conflict(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(mod, '_read_deploy_paddle', fake_read)
    monkeypatch.setattr(mod, 'obs_conflict', fake_conflict)
    ctrl = types.SimpleNamespace(screenshot=lambda: (0.0, object()))
    return types.SimpleNamespace(controller=ctrl), calls


def test_confirm_over_cap_double_frame_confirmed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """重读与首读同值且仍超限 → 采信重读值,留「超限」证据(不是拒信)。"""
    ctx, calls = _gate_env(monkeypatch, (6, 5))
    assert _confirm_over_cap(ctx, object(), 6, 5) == (6, 5)
    assert len(calls) == 1, f'确认超限应留一条证据,实际 {calls}'
    (field, _old, _new, _screen), kwargs = calls[0]
    assert field == 'team_size_over_cap'
    assert '超限' in kwargs['verdict']


@pytest.mark.parametrize('second', [(7, 6), (5, 4), (6, 4), (7, 5)])
def test_confirm_over_cap_second_read_over_but_differs(
        monkeypatch: pytest.MonkeyPatch, second: tuple[int, int]) -> None:
    """重读超限但与首读不同值(两次不同的瞬态误读)→ 不按超限采信:X 置 None、
    cap 保留——否则守卫会把误读当超限拦下一次合法出战。"""
    ctx, calls = _gate_env(monkeypatch, second)
    assert _confirm_over_cap(ctx, object(), 6, 5) == (None, 5)
    assert len(calls) == 1
    (_field, _old, _new, _screen), kwargs = calls[0]
    assert '未确认' in kwargs['verdict'] and '超限-双帧一致' not in kwargs['verdict']


def test_confirm_over_cap_second_read_not_over(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """重读不超限 → 首读按误读,采重读值 5/5。"""
    ctx, calls = _gate_env(monkeypatch, (5, 5))
    assert _confirm_over_cap(ctx, object(), 6, 5) == (5, 5)
    assert len(calls) == 1, '未确认超限也应留一条证据(判读误读形态)'
    (_field, _old, _new, _screen), kwargs = calls[0]
    assert '未确认' in kwargs['verdict'] and '超限-双帧一致' not in kwargs['verdict']


def test_confirm_over_cap_second_read_unavailable(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """重读不可得 → X 置 None(不按超限采信),cap 保留;留「未确认」证据
    (首读超限 + 重读失读是判读要看的形态,不冒充已确认超限)。"""
    ctx, calls = _gate_env(monkeypatch, (None, None))
    assert _confirm_over_cap(ctx, object(), 6, 5) == (None, 5)
    assert len(calls) == 1
    (_field, _old, _new, _screen), kwargs = calls[0]
    assert '未确认' in kwargs['verdict'] and '超限-双帧一致' not in kwargs['verdict']


def test_confirm_over_cap_in_domain_passthrough(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """首读不超限 → 零重读零证据,原值透传。"""
    ctx, calls = _gate_env(monkeypatch, AssertionError('不应重读'))
    assert _confirm_over_cap(ctx, object(), 5, 5) == (5, 5)
    assert _confirm_over_cap(ctx, object(), None, 5) == (None, 5)
    assert _confirm_over_cap(ctx, object(), 4, None) == (4, None)
    assert calls == []


@pytest.mark.parametrize(('reads', 'expected', 'evidence_n'), [
    ([(6, 5), (6, 5)], (6, 5), 1),   # 首读超限 → 重读同值确认 → 采信
    ([(6, 5), (7, 6)], (None, 5), 1),  # 首读超限 → 重读超限但不同值 → 不采信
    ([(5, 5)], (5, 5), 0),           # 首读不超限 → 不重读
])
def test_read_paddle_pair_confirmed_wiring(monkeypatch: pytest.MonkeyPatch,
                                           reads, expected, evidence_n) -> None:
    """公开口(观察写端 / 出战守卫消费):单读 + 确认门串联——超限读数经
    重读同值确认才出门,不超限单读直出。"""
    calls: list[tuple] = []
    seq = iter(reads)
    monkeypatch.setattr(mod, '_read_deploy_paddle', lambda *a, **k: next(seq))
    monkeypatch.setattr(mod, 'obs_conflict',
                        lambda *a, **k: calls.append((a, k)))
    ctx = types.SimpleNamespace(controller=types.SimpleNamespace(
        screenshot=lambda: (0.0, object())))
    assert mod.read_paddle_pair_confirmed(ctx, object(), level=5) == expected
    assert len(calls) == evidence_n


def test_read_game_state_writes_team_size_used(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """观察写端(生产路径 ``read_game_state`` 全量读):超限帧 → 状态容器
    ``team_size_used``=6 / ``deploy_cap``=5(确认门重读同一帧)。修前超限帧
    两读皆拒信,写端无从落值。常规帧的读数由上方夹具基线锁住,写端分支同一
    条(``_paddle_x is not None`` → observe),不重复付整帧全量读的成本。"""
    from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
    state = _OVER_CAP_FRAMES[0]
    if not test_context.has_screen('货币战争-备战', state):
        pytest.skip(f'存档截图缺失:screens/货币战争-备战/{state}.webp')
    match = types.SimpleNamespace(session=types.SimpleNamespace())
    monkeypatch.setattr(test_context, 'cw_match', match)
    monkeypatch.setattr(mod, 'obs_conflict', lambda *a, **k: None)   # 不落截图
    gs = game_state_of(match.session)
    img = test_context.load_screen('货币战争-备战', state)
    test_context.controller.mock_screenshot = img   # 确认门重读帧
    mod.read_game_state(test_context, img, screen_name='货币战争-备战')
    assert (gs.team_size_used.value, gs.deploy_cap.value) == (6, 5), \
        '超限帧应落 (规模占用 6, cap 5)'


#: 满编帧的字形实测值:两块数字 + 下标 1 处一块细长字形(斜杠),`_paddle_glyph_strip` 的桩。
_FULL_BOARD_GLYPHS = [(89, 37, 45, 772), (137, 27, 46, 346), (173, 38, 45, 773)]
#: 四块数字字形(无细长字形 → 斜杠下标为空 → 走枚举切分)。
_FOUR_DIGIT_GLYPHS = [(89, 37, 45, 772), (130, 37, 45, 771), (173, 38, 45, 773), (215, 38, 45, 774)]


def _paddle_env(monkeypatch: pytest.MonkeyPatch, texts: list[str],
                glyphs: list | None = _FULL_BOARD_GLYPHS,
                ) -> tuple[types.SimpleNamespace, list[tuple], object]:
    """``_read_deploy_paddle`` 桩环境:区域恒为 16×16、字形固定、OCR 按调用顺序给
    ``texts``(耗尽即抛,锁「一级成功不再调二级」);返回 (假 ctx, obs_conflict 捕获列表, 整帧)。"""
    calls: list[tuple] = []
    seq = iter(texts)

    def next_ocr(**kwargs):
        try:
            return [types.SimpleNamespace(data=next(seq))]
        except StopIteration:
            raise AssertionError('不应再调 OCR') from None

    monkeypatch.setattr(mod, '_area_rect', lambda *_a, **_k: types.SimpleNamespace(
        x1=0, y1=0, x2=16, y2=16))
    monkeypatch.setattr(mod, '_paddle_glyph_strip', lambda _crop: glyphs)
    monkeypatch.setattr(mod, 'obs_conflict',
                        lambda *a, **k: calls.append((a, k)))
    ctx = types.SimpleNamespace(ocr_service=types.SimpleNamespace(get_ocr_result_list=next_ocr))
    return ctx, calls, numpy.zeros((16, 16, 3), dtype=numpy.uint8)


def _one_conflict(calls: list[tuple]) -> tuple[dict, str, str]:
    """断言恰好 1 条证据行,返回 (载荷 new, verdict, field)。"""
    assert len(calls) == 1, f'应恰好 1 条证据行,实际 {len(calls)}'
    (field, _old, new, _screen), kwargs = calls[0]
    assert field == 'deploy_paddle'
    return new, kwargs['verdict'], kwargs['source']


def test_read_paddle_full_board_no_reject_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    """一级原生 OCR 读歪 '1616'(满编 6/6 实机形态)、二级读对 '16/6' → 读数 (6, 6),
    零证据行(一级失败是预期内的,不留拒信)。"""
    ctx, calls, screen = _paddle_env(monkeypatch, ['1616', '16/6'])
    assert mod._read_deploy_paddle(ctx, screen, level=6) == (6, 6)
    assert calls == []


def test_read_paddle_both_levels_fail_one_reject_with_both_texts(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """两级都走到约束出口且都落空 → 恰好 1 条拒信,带两级文本;清单都空取最后一级。"""
    ctx, calls, screen = _paddle_env(monkeypatch, ['1414', '1414'])
    assert mod._read_deploy_paddle(ctx, screen, level=6) == (None, None)
    new, verdict, source = _one_conflict(calls)
    assert set(new) == {'text_l1', 'text_l2', 'candidates', 'candidates_from'}
    assert new['text_l1'] == new['text_l2'] == '1414'
    assert new['candidates'] == [] and new['candidates_from'] == 'l2'
    assert verdict.startswith('拒-') and source == 'paddle_positional'
    assert calls[0][0][3] is screen


def test_read_paddle_l2_no_digits_takes_l1_candidates(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """一级有数字落空、二级读空 → 恰好 1 条拒信,清单取自一级(二级提前返回)。"""
    ctx, calls, screen = _paddle_env(monkeypatch, ['1616', ''])
    assert mod._read_deploy_paddle(ctx, screen, level=6) == (None, None)
    new, verdict, _ = _one_conflict(calls)
    assert new['text_l1'] == '1616' and new['text_l2'] == ''
    assert new['candidates_from'] == 'l1' and verdict.startswith('拒-')


def test_read_paddle_no_digits_zero_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    """两级文本都无数字 → 零证据。"""
    ctx, calls, screen = _paddle_env(monkeypatch, ['abc', 'abc'])
    assert mod._read_deploy_paddle(ctx, screen, level=6) == (None, None)
    assert calls == []


@pytest.mark.parametrize(('texts', 'text_l1'), [
    (['16/5'], '16/5'),            # 一级靠 level 放宽读对,二级不应被调用
    (['1414', '16/5'], '1414'),    # 一级落空、二级靠 level 放宽读对 → 只有披露行,无拒信
])
def test_read_paddle_level_relaxed_emits_disclosure(
        monkeypatch: pytest.MonkeyPatch, texts: list[str], text_l1: str) -> None:
    ctx, calls, screen = _paddle_env(monkeypatch, texts)
    assert mod._read_deploy_paddle(ctx, screen, level=6) == (6, 5)
    new, verdict, _ = _one_conflict(calls)
    assert verdict.startswith('采-y<level')
    assert new['text_l1'] == text_l1 and new['text'] == '16/5'


def test_read_paddle_ambiguous_l1_keeps_l1_candidates(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """一级歧义出两个候选、二级读空 → 1 条拒信,带一级的两对候选。"""
    ctx, calls, screen = _paddle_env(monkeypatch, ['1013', ''], glyphs=_FOUR_DIGIT_GLYPHS)
    assert mod._read_deploy_paddle(ctx, screen, level=6) == (None, None)
    new, verdict, _ = _one_conflict(calls)
    assert new['candidates'] == [(1, 13, False), (10, 13, False)]
    assert new['candidates_from'] == 'l1' and verdict.startswith('拒-')


def test_read_paddle_digits_without_glyph_zero_evidence(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """文本带数字但没有合格字形(区域被遮挡) → 两级都提前返回,零证据。"""
    ctx, calls, screen = _paddle_env(monkeypatch, ['1614', '1614'], glyphs=[])
    assert mod._read_deploy_paddle(ctx, screen, level=6) == (None, None)
    assert calls == []
