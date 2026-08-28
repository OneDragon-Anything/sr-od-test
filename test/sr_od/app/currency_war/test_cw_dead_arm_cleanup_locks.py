"""死臂清理守卫锁(ADR-0305 件3 / ADR-0402 / ADR-0408 定谳清理)。

锁定对象(清理后语义,策略开关生命周期第 4 态「删码留 ADR」的防复活门):
1. registry 字段面:goldrich_buy_bias/goldrich_min_gold/goldrich_buy_tags
   (ADR-0305 三窗否决 + ADR-0408 同构复证)、filler_star_unit/
   pair_copy_direction_exempt(ADR-0402 W504 开臂 A/B wash)、
   early_pace_enabled/min_round/max_round/bias/val_max(ADR-0408 三窗
   无一致正方向)共 10 字段全部不存在;
2. 源码面:decision_v2 全部 .py 去注释/去 docstring 后不含四臂任一
   符号(复活须先过各自 ADR 的复活条件论证,硬拦静默回流);
3. 行为面:score_state 分项表无 filler_star 维;方向阵营门现行为保持
   ——方向外 bench-only 同名副本在默认 registry 仍不生成候选
   (豁免只由末窗承接门 gap 条件化承载,ADR-0405,锁线帧 gap=0)。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from sr_od.application.currency_war.cw_state import GameState, ShopCard
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import (
    _buy_tag,
    generate_candidates,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.scoring import score_state

_DELETED_FIELDS = (
    'goldrich_buy_bias', 'goldrich_min_gold', 'goldrich_buy_tags',
    'filler_star_unit', 'pair_copy_direction_exempt',
    'early_pace_enabled', 'early_pace_min_round', 'early_pace_max_round',
    'early_pace_bias', 'early_pace_val_max',
)
_SYMBOLS = ('goldrich', 'early_pace', 'filler_star',
            'pair_copy_direction')


def _decision_v2_dir() -> Path:
    return (Path(__file__).resolve().parents[5]
            / 'src' / 'sr_od' / 'application' / 'currency_war'
            / 'decision_v2')


def _strip_comments_and_docstrings(text: str) -> str:
    """去 # 注释行与三引号 docstring(守卫只看活代码,定谳墓碑注释放行)。"""
    out: list[str] = []
    in_doc: str | None = None
    for line in text.splitlines():
        if in_doc is not None:
            if in_doc in line:
                in_doc = None
            continue
        stripped = line.strip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            quote = stripped[:3]
            # 单行 docstring(含收尾引号)直接放行
            if not (stripped.endswith(quote) and len(stripped) >= 6):
                in_doc = quote
            continue
        if stripped.startswith('#'):
            continue
        out.append(line)
    return '\n'.join(out)


def test_registry_dead_arm_fields_absent() -> None:
    """字段面:四臂 10 字段全部不存在(hasattr=False)。"""
    for f in _DELETED_FIELDS:
        assert not hasattr(DEFAULT_REGISTRY, f), f


def test_decision_v2_source_symbols_absent() -> None:
    """源码面:decision_v2 活代码不含四臂任一符号(注释/docstring 中
    的定谳墓碑指针放行;复活须先过各自 ADR 复活条件论证)。"""
    for py in sorted(_decision_v2_dir().glob('*.py')):
        code = _strip_comments_and_docstrings(
            py.read_text(encoding='utf-8'))
        for sym in _SYMBOLS:
            assert sym not in code, f'{py.name} 含死臂符号 {sym}'


def _sess() -> StrategySession:
    from sr_od.application.currency_war.cw_intention import (
        HoardTarget,
        IntentionState,
    )
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '姬子列车'
    s.v3_intention = ist
    s.v3_hoard = HoardTarget(
        frozenset({'姬子·启行', '三月七', '花火', '瓦尔特'}),
        frozenset(), 'locked')
    s.v3_core_names = {'姬子·启行'}
    s.target_comp = SimpleNamespace(factions=('列车同行',),
                                    core_chars=('姬子·启行',))
    return s


def test_score_state_has_no_filler_star_key() -> None:
    """行为面:score_state 分项表无 filler_star 维(死臂评分通道
    不再有半步残迹;merge_progress/core_star 等存活维不受影响)。"""
    st = GameState(plane=1, round_num=5, gold=30, level=5,
                   board={'列车同行': 2}, deployed=[], bench=[],
                   shop=[], hp=50)
    bd = score_state(st, DEFAULT_REGISTRY, _sess())
    assert 'filler_star' not in bd
    assert 'merge_progress' in bd and 'core_star' in bd


def test_direction_gate_default_behavior_kept() -> None:
    """行为面:方向阵营门现行为保持——方向外 bench-only 同名副本在
    默认 registry 下不生成买候选、_buy_tag 判 None(原方案B 豁免已删,
    同域放行只由末窗承接门 gap 条件化承载,ADR-0405;锁线帧 gap=0)。"""
    filler, fac = '娜塔莎', '贝洛伯格'
    dep = SimpleNamespace(char_id='姬子·启行', faction='列车同行',
                          star=1, position_pref='back', equips=(), slot=0)
    st = GameState(plane=1, round_num=7, gold=60, level=5,
                   board={'列车同行': 2},
                   deployed=[dep],
                   bench=[],
                   shop=[ShopCard(x=1, faction=fac, name=filler, cost=3)],
                   hp=80)
    sess = _sess()
    assert _buy_tag(st.shop[0], st, sess, DEFAULT_REGISTRY) is None
    names = [getattr(getattr(c.action, 'card', None), 'name', '')
             for c in generate_candidates(st, sess, DEFAULT_REGISTRY)]
    assert filler not in names
