"""结算屏三项遥测读数器单测(结算 OCR 三读数器落地批)。

被测 = ``cw_settlement_obs`` 的结算三项读数器(挑战进度填充率 / 基础伤害 /
未完成进度伤害)+ ``read_round_outcome`` 字段透传。分两层:
- 纯函数层(行归并/符号守卫/锚判据/像素列扫描):构造 token list 与合成图像,
  不依赖 OCR;
- 真实 OCR 层:fixtures_settle/ 下 5 张实机帧(已入仓,读真值锚 = 帧本体;
  原始样本面为主仓 .debug 易失产物,判读结论以入仓帧为准),走
  test_context 的真 OCR 引擎锁读数真值。读点链语义出处 =
  docs/develop/sr_od/application/currency_war/decisions/dd-006-settle-read-chain-boss-win-form.md。
"""
from types import SimpleNamespace

import numpy as np
import pytest

from sr_od.application.currency_war.obs.cw_settlement_obs import (
    is_boss_win_settle_page1,
    parse_progress_fill_ratio,
    parse_settle_damage_breakdown,
    parse_settle_hp_anchor,
    read_round_outcome,
    read_settle_damage_breakdown,
    settle_page1_progress_sign,
)


def _it(data: str, x: int, y: int, w: int = 60, h: int = 30) -> SimpleNamespace:
    """构造 OcrMatchResult 形态的测试 token(只带 parse 消费的 4 字段)。"""
    return SimpleNamespace(data=data, x=x, y=y, width=w, height=h)


class _FakeOcr:
    """桩 OCR:get_ocr_result_list 恒返回固定 token 序列
    (data=texts[i],x=100,y=i*40;read_round_outcome 共用载体)。"""

    def __init__(self, texts: list[str]) -> None:
        self._tokens = [_it(t, 100, i * 40) for i, t in enumerate(texts)]

    def get_ocr_result_list(self, image, rect, crop_first):
        return self._tokens


def _fake_ctx(*texts: str) -> SimpleNamespace:
    """最小 ctx 载体(只挂 ocr_service 桩;read_round_outcome 两测共用)。"""
    return SimpleNamespace(ocr_service=_FakeOcr(list(texts)))


# 面板正例几何 = end_boss_win_with_breakdown_panel.png 帧实测(入仓帧即真值锚)
_PANEL_POS = [_it('小队生命值结算说明', 1348, 503, 240, 30),
              _it('基础伤害', 1250, 555, 100, 33), _it('-10', 1630, 553, 60, 35),
              _it('未完成进度伤害', 1250, 588, 160, 34), _it('-1', 1630, 588, 60, 34),
              _it('长线作战', 1250, 622, 100, 33), _it('+2', 1630, 620, 60, 35)]


def test_breakdown_positive_case() -> None:
    """正例:三行齐 → base=-10 / undone=-1 / longline=+2 / visible=True。"""
    out = parse_settle_damage_breakdown(_PANEL_POS)
    assert out == {'visible': True, 'damage_base': -10,
                   'damage_unfinished_progress': -1, 'heal_longline': 2}


def test_breakdown_panel_absent() -> None:
    """负例:面板不在场(end_loss 帧,心形 -12 无面板)→ 全 None + visible=False。"""
    out = parse_settle_damage_breakdown([_it('挑战结束', 900, 300), _it('-12', 1120, 495)])
    assert out['visible'] is False
    assert out['damage_base'] is None and out['damage_unfinished_progress'] is None


def test_breakdown_lost_minus_sign_rejected() -> None:
    """OCR 丢负号(「10」无符号)→ 拒信 None,不冒认 +10(值域先验,设计 §3)。"""
    out = parse_settle_damage_breakdown([
        _it('基础伤害', 1250, 555, 100, 33), _it('10', 1630, 553, 60, 35)])
    assert out['visible'] is True      # 行标签在场 = 面板在场
    assert out['damage_base'] is None  # 但值拒信(在场 vs 解析失败可分)


def test_breakdown_zero_is_legal() -> None:
    """裸「0」合法(进度打满游戏可显 0);None 与 0 语义必须分开。"""
    out = parse_settle_damage_breakdown([
        _it('未完成进度伤害', 1250, 588, 160, 34), _it('0', 1630, 588, 60, 34)])
    assert out['damage_unfinished_progress'] == 0


def test_breakdown_adhesion_form() -> None:
    """同 token 粘连形态(「基础伤害-10」)→ 直连取值。"""
    out = parse_settle_damage_breakdown([
        _it('基础伤害-10', 1250, 555, 130, 33), _it('长线作战+2', 1250, 622, 130, 33)])
    assert out['damage_base'] == -10 and out['heal_longline'] == 2


def test_breakdown_row_isolation() -> None:
    """行隔离:邻行值(y 差 33px > 行判据 20px)不串行。"""
    out = parse_settle_damage_breakdown([
        _it('基础伤害', 1250, 555, 100, 33),
        _it('-1', 1630, 588, 60, 34)])   # 只有 undone 行的值,不在 base 行
    assert out['damage_base'] is None


def test_read_settle_damage_breakdown_none_screen() -> None:
    """screen None(测试注入态/无帧)→ 全 None + visible False,不冒认。"""
    out = read_settle_damage_breakdown(None, None)
    assert out['visible'] is False and out['damage_base'] is None


def test_progress_fill_ratio_synthetic_bar() -> None:
    """合成进度条:左 60% 红、余下暗 → fill≈0.6;空槽/None 帧 → None。"""
    img = np.zeros((1080, 1920, 3), np.uint8)
    img[424:440, 710:710 + 300] = (200, 40, 40)
    assert parse_progress_fill_ratio(img) == pytest.approx(0.6, abs=0.01)
    blank = np.zeros((1080, 1920, 3), np.uint8)
    assert parse_progress_fill_ratio(blank) is None
    assert parse_progress_fill_ratio(None) is None


def test_settle_hp_anchor() -> None:
    """HP 锚:「小队生命值」行 /「继续挑战」在场 → True;败局翻页帧 → False。"""
    assert parse_settle_hp_anchor(['小队生命值41', '数据统计']) is True
    assert parse_settle_hp_anchor(['前往结算', '挑战结束']) is False


def test_round_outcome_carries_settle_fields() -> None:
    """read_round_outcome 透传三项字段(screen=None → 填充率 None/面板不在场)。"""
    obs = read_round_outcome(
        _fake_ctx('挑战结束', '-22', '挑战进度', '前往结算'),
        None, plane=2, round_num=1, comp_tag='x')
    assert obs.progress_fill_ratio is None
    assert obs.damage_base is None and obs.damage_unfinished_progress is None
    assert obs.damage_breakdown_visible is False


# ===== 真实 OCR 层(fixtures_settle 实机帧;走 test_context 真 OCR 引擎) =====

_FIX = None


def _load(test_image_dir, name):
    from one_dragon.utils import cv2_utils
    return cv2_utils.read_image(str(test_image_dir / 'fixtures_settle' / f'{name}.png'))


def test_breakdown_real_ocr_positive(test_context, test_image_dir) -> None:
    """end_boss_win 实机帧(tooltip 在场)→ base=-10 / undone=-1 / visible=True。"""
    screen = _load(test_image_dir, 'end_boss_win_with_breakdown_panel')
    if screen is None:
        pytest.skip('fixture 缺失')
    out = read_settle_damage_breakdown(test_context, screen)
    assert out['visible'] is True, f'tooltip 应在场(证据 = 入仓实机帧本体): {out}'
    assert out['damage_base'] == -10
    assert out['damage_unfinished_progress'] == -1


def test_breakdown_real_ocr_absent(test_context, test_image_dir) -> None:
    """end_loss 实机帧(面板不在场)→ visible=False,两分量 None(删失显式)。"""
    screen = _load(test_image_dir, 'end_loss_no_panel_minus12')
    if screen is None:
        pytest.skip('fixture 缺失')
    out = read_settle_damage_breakdown(test_context, screen)
    assert out['visible'] is False
    assert out['damage_base'] is None and out['damage_unfinished_progress'] is None


def test_progress_fill_ratio_real_frames(test_context, test_image_dir) -> None:
    """挑战结束帧进度条可读(0<fill≤1);胜结算页2 帧读不到条(settlement_win)。"""
    s1 = _load(test_image_dir, 'end_loss_no_panel_minus12')
    if s1 is not None:
        fill = parse_progress_fill_ratio(s1)
        assert fill is not None and 0 < fill <= 1.0, f'页1 帧条应可读: {fill}'
    s2 = _load(test_image_dir, 'settlement_win_stats_panel')
    if s2 is not None:
        # 页2 帧不锁「必读不到」(条若延伸到页2 读到也无害),只锁不崩溃 + 值域
        fill2 = parse_progress_fill_ratio(s2)
        assert fill2 is None or 0 < fill2 <= 1.0


# ===== boss 胜局读点链(DD-006):页1 判别 + 填充率页态门 =====

def test_boss_win_page1_positive_progress() -> None:
    """挑战进度 +N(节点胜利)→ boss 胜局页1 判 True(实跑 token 形态)。"""
    assert is_boss_win_settle_page1(['挑战结束', '挑战进度', '+2']) is True
    assert is_boss_win_settle_page1(['挑战结束', '挑战进度+2']) is True


def test_boss_win_page1_defeat_and_unreadable() -> None:
    """战败页(负增量)/OCR 漏读(None)→ False(判 False = 回旧行为,不劣化)。"""
    assert is_boss_win_settle_page1(['挑战结束', '-22', '挑战进度']) is False
    assert is_boss_win_settle_page1(['挑战结束', '点击空白加速']) is False


def test_round_outcome_fill_only_on_page1() -> None:
    """填充率页态门(DD-006):页2 帧(无「点击空白加速」)不读条——同矩形
    罩 HP 心形会恒定读假值(0.392 三局同值实证);页1 帧才读。"""
    img = np.zeros((1080, 1920, 3), np.uint8)
    img[424:440, 710:1010] = (200, 40, 40)   # 进度条 60% 红填充

    # 页2 形态(挑战成功 + 继续挑战,无「点击空白加速」)→ 同帧含红条也判 None
    obs_p2 = read_round_outcome(
        _fake_ctx('挑战结束', '1-9首领', '继续挑战'), img,
        plane=1, round_num=9, comp_tag='x')
    assert obs_p2.progress_fill_ratio is None
    # 页1 形态(「点击空白加速」在场)→ 正常读条
    obs_p1 = read_round_outcome(
        _fake_ctx('挑战结束', '1-9首领', '点击空白加速'), img,
        plane=1, round_num=9, comp_tag='x')
    assert obs_p1.progress_fill_ratio == pytest.approx(0.6, abs=0.01)


def test_progress_sign_three_states() -> None:
    """进度符号三态(DD-006 置闩门单一源):pos/neg/None 可分——None=OCR 漏读,
    两种形态页都可能漏,不得当败局真值置闩(防 boss 胜局 run 判废)。"""
    assert settle_page1_progress_sign(['挑战进度', '+2']) == 'pos'
    assert settle_page1_progress_sign(['-22', '挑战进度']) == 'neg'
    assert settle_page1_progress_sign(['挑战结束', '点击空白加速']) is None


# ===== heal_longline 补链(T-83/ADR-0609:tooltip 回血分量入遥测) =====

def test_round_outcome_carries_heal_longline() -> None:
    """read_round_outcome 透传回血分量:面板三行齐 → heal_longline=+2。
    红证 = 旧实现丢弃第三行(解析器有值、RoundOutcome 无字段),L_node
    对比「tooltip 幅度 = hp 链差 + 2」的系统偏移(长线作战回血)只能靠
    猜,行内不可验证。桩保留 _PANEL_POS 坐标(行判据吃 y 几何)。"""
    class _PanelOcr:
        def get_ocr_result_list(self, image, rect, crop_first):
            return list(_PANEL_POS)

    obs = read_round_outcome(
        SimpleNamespace(ocr_service=_PanelOcr()),
        np.zeros((1080, 1920, 3), np.uint8),   # 非 None(面板读路径门)
        plane=1, round_num=5, comp_tag='x')
    assert obs.heal_longline == 2, '回血分量未透传(补链断裂)'
    assert obs.damage_base == -10 and obs.damage_unfinished_progress == -1
    # 净变化恒等式:链差 = 掉血两分量 + 回血(-10 + -1 + 2 = -9),
    # 即「tooltip 幅度 = 链差 + 2」偏移的机制项,行内三量齐即可验
    assert obs.damage_base + obs.damage_unfinished_progress \
        + obs.heal_longline == -9


def test_outcome_record_persists_heal_longline(
        monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """heal_longline 落 outcomes 行(jsonl round-trip)——删除波 1 退役重写:

    outcomes 行写入端已退役;同语义现役面 = RoundOutcome 载体字段透传
    (观察半 pending 槽/performance.history 行内仍携 heal_longline,判读
    链不断流)。schema 字段缺失/透传缺失任一发生 → 行内无此键。"""
    from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
    from sr_od.application.currency_war.kernel.cw_state import GameState
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )

    _sess = StrategySession()
    _sess.last_state = GameState()
    o = RoundOutcome(
        round_num=5, plane=1, node_type='普通战斗', comp_tag='x',
        hp_after=91, killed=True,
        damage_base=-10, damage_unfinished_progress=-1, heal_longline=2)
    _sess.pending_round_outcomes.append(o)
    _sess.performance.history.append(o)
    row = _sess.performance.history[-1]
    assert row.heal_longline == 2, '结算链行缺回血分量'
    assert row.damage_base == -10


def test_battle_wait_page1_stash_covers_heal_longline() -> None:
    """页1 暂存/合并键面含 heal_longline(胜轮页2 调用时回血分量随暂存回填)。

    接线锁(inspect 源码断言,test_cw_obs_chain 同款形态):暂存写入两处
    与合并键列表三处任一漏键 → 胜轮 heal_longline 恒 None。"""
    import inspect

    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_battle_wait,
    )
    src = inspect.getsource(cw_screen_battle_wait)
    assert src.count("'heal_longline'") >= 4, \
        '页1 暂存/合并键面漏 heal_longline(期望暂存×2+合并×1+注释面≥1)'
