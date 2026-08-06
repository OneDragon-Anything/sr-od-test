"""货币战争 OCR 观测层测试。

纯逻辑(parse_settlement_hp;P1.5 结算屏 hp_after 解析)+ 集成(read_affixes 简报词缀,
需 fixture + ctx.ocr_service)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war import cw_briefing_obs, cw_observation
from sr_od.application.currency_war.cw_observation import (
    parse_settlement_hp,
    read_affix_effect,
    read_affixes,
    read_board,
    read_board_next_tier,
    read_bosses,
)
from test.conftest import SrTestContext

# 2026-08-05 实跑结算屏 OCR(战斗后「挑战结束」屏):小队生命值=71(战前 84,本战损 13)。
_SETTLEMENT_OCR = [
    '19', '挑战结束', '战斗', '216', '小队生命值71i', '获得金币总览', '数据统计', '基础奖励',
    '5', '试用', '98.3万', '利息C', '试用', '连胜×0', '67.4万', '62.4万', '继续挑战',
]
# 投资策略屏 OCR(含陷阱文本「每损失20点小队生命值获得5」——「生命值」后非紧邻数字,不该误取)。
_INVEST_STRATEGY_OCR = [
    '攻略', '返回备战界面', '请选择投资策略', '正能量', '保险', '幸运喷雾',
    '每损失20点小队生命值获得5', '同于能量上限20%的能量。', '确认',
]


def test_parses_hp_from_settlement() -> None:
    """结算屏「小队生命值71i」→ 71(尾部噪声 'i' 容忍)。"""
    assert parse_settlement_hp(_SETTLEMENT_OCR) == 71


def test_clean_hp_no_noise() -> None:
    """无噪声「小队生命值84」→ 84。"""
    assert parse_settlement_hp(['挑战结束', '小队生命值84', '继续挑战']) == 84


def test_rejects_non_adjacent_digits() -> None:
    """投资策略描述「每损失20点小队生命值获得5」→ 「生命值」后非紧邻数字 → None(不误取 20/5)。"""
    assert parse_settlement_hp(_INVEST_STRATEGY_OCR) is None


def test_no_lifespan_text_returns_none() -> None:
    """无「生命值」文本 → None。"""
    assert parse_settlement_hp(['挑战结束', '数据统计', '继续挑战']) is None


def test_out_of_bounds_rejected() -> None:
    """越界(> HP_MAX)→ 丢弃(防 OCR 垃圾级联)。HP_MIN=0,故 0 允许(见下条)。"""
    assert parse_settlement_hp(['小队生命值999']) is None   # > HP_MAX(200)


def test_zero_hp_allowed_at_min() -> None:
    """HP=0(阵亡)边界允许(HP_MIN=0)。"""
    assert parse_settlement_hp(['小队生命值0']) == 0


def test_read_affixes_briefing(test_context: SrTestContext) -> None:
    """简报词缀行 → 4 个词缀(A8 最高 4)。

    fixture ``screens/货币战争-简报/default.webp``:随从强化/开局不利/变宝为废/丢失幸运。
    read_affixes OCR 区域-词缀行 → 4 词缀 OCR 原名(下游 AFFIX_MECHANIC_MAP 映射机制 tag)。
    """
    if not test_context.has_screen('货币战争-简报', 'default'):
        pytest.skip('存档截图缺失:screens/货币战争-简报/default.webp')
    screen = test_context.load_screen('货币战争-简报', 'default')
    affixes = read_affixes(test_context, screen)
    assert len(affixes) == 4, f'期望 4 词缀(A8 最高),实际 {affixes}'
    # OCR 原名透传(下游匹配在 AFFIX_MECHANIC_MAP);校验读到预期词缀(容 OCR 小差异,查关键词)
    joined = '/'.join(affixes)
    assert any(k in joined for k in ('强化', '不利', '废', '幸运', '熄火', '行动')), (
        f'未读到预期词缀,实际 {affixes}'
    )


def test_read_bosses_briefing(test_context: SrTestContext) -> None:
    """简报首领行 → 3 个位面 boss 名。

    fixture ``screens/货币战争-简报/default.webp``:3 boss 横排卡片(立绘 + 阵营标签 + 名字)。
    read_bosses OCR 区域-首领行 → 3 boss 名(下游 state.bosses → boss_fit)。boss 名跨局会变
    (每局 3 位面随机首领),只校验数量 + 中文,不写死名字。
    """
    if not test_context.has_screen('货币战争-简报', 'default'):
        pytest.skip('存档截图缺失:screens/货币战争-简报/default.webp')
    screen = test_context.load_screen('货币战争-简报', 'default')
    bosses = read_bosses(test_context, screen)
    assert len(bosses) == 3, f'期望 3 boss(3 位面),实际 {bosses}'
    # boss 名中文 4-8 字(如 增熵能源集团/火线动力机甲/银甲武装公司)
    assert all(4 <= len(b) <= 8 for b in bosses), f'boss 名长度异常,实际 {bosses}'


def test_read_invest_env_options(test_context: SrTestContext) -> None:
    """投资环境 3 卡名读取(HandleInvestEnv._read_options by NAME_CY 行过滤)。

    fixture ``screens/货币战争-投资环境/default.webp``。NAME_CY [360,410] 容卡名 y 随立绘变
    (修前 [378,408] 漏 y<378 的卡名,实机 3 卡名 y 375-378)。
    """
    if not test_context.has_screen('货币战争-投资环境', 'default'):
        pytest.skip('存档截图缺失:screens/货币战争-投资环境/default.webp')
    from sr_od.application.currency_war.operations.handlers.handle_invest_env import (
        HandleInvestEnv,
    )
    screen = test_context.load_screen('货币战争-投资环境', 'default')
    op = HandleInvestEnv(test_context)
    opts = op._read_options(screen)
    assert len(opts) == 3, f'期望 3 卡名,实际 {opts}'


def test_read_select_partner_candidates(test_context: SrTestContext) -> None:
    """选择伙伴 候选阵营 label 读取(HandleSelectPartner._read_candidates by 中央 x + y 行过滤)。

    D-60:硬编码 STAGE_PORTRAIT 落候选间隙 flat-loop → 改 OCR 定位候选。fixture
    ``screens/货币战争-选择伙伴/default.webp``(1-7 节点 2 候选 护盾/能量)。
    **关键回归**:候选必须只在中央 overlay(x>450),不含左侧备战面板 board label
    (仙舟/列车同行/能量 在 x~106 同 y 行)—— D-60 初版漏 x 过滤会把 board label 当候选。
    """
    if not test_context.has_screen('货币战争-选择伙伴', 'default'):
        pytest.skip('存档截图缺失:screens/货币战争-选择伙伴/default.webp')
    from sr_od.application.currency_war.operations.handlers.handle_select_partner import (
        HandleSelectPartner,
    )
    screen = test_context.load_screen('货币战争-选择伙伴', 'default')
    op = HandleSelectPartner(test_context)
    cands = op._read_candidates(screen)
    names = [c[0] for c in cands]
    xs = [c[1] for c in cands]
    assert len(cands) >= 2, f'期望 ≥2 候选,实际 {names}'
    assert '护盾' in names and '能量' in names, f'应命中中央候选 护盾/能量,实际 {names}'
    assert all(x > 400 for x in xs), f'候选都应在中央(x>400),实际 x={xs} —— 左侧 board label 漏进来了'


# ===== read_affix_effect:点词缀后 tooltip → 效果原文(mock OCR;2026-08-05 A8 实机数据)=====

def _ocr(text: str, x: int, y: int) -> SimpleNamespace:
    """造 OCR result(data + center),给 read_affix_effect mock 用。"""
    return SimpleNamespace(data=text, center=Point(x, y))


def test_read_affix_effect_tooltip(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """点词缀后 tooltip → 效果原文(标题下方紧邻连续行 dy≤45,遇大 gap 停)。

    mock 软弱无力 tooltip:标题 y859 + 描述 y885 + 数值 y908 + 词缀行同名 y967(应排除)。
    read_affix_effect 找标题(同名最上方 y859)→ 取下方连续(885 dy26 + 908 dy23)→ 964 dy55 gap 停。
    """
    ocr = [
        _ocr('阵营', 229, 651), _ocr('智识实验室', 194, 708), _ocr('本场对局首领', 1442, 742),
        _ocr('软弱无力', 627, 859),        # tooltip 标题(同名最上方)
        _ocr('没有穿戴3件装备的角色及其忆灵，造成的伤害为原伤害的', 628, 885),  # 描述
        _ocr('80%.', 624, 908),           # 数值
        _ocr('i敌人难度108', 46, 964),
        _ocr('第三位面强化', 305, 968), _ocr('软弱无力', 822, 967),  # 词缀行(同名,下方,排除)
        _ocr('下一步', 1474, 967),
    ]
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', lambda **kw: ocr)
    effect = read_affix_effect(test_context, None, '软弱无力')
    assert '没有穿戴3件装备' in effect, f'效果缺失,实际 {effect!r}'
    assert '80%' in effect, f'数值缺失,实际 {effect!r}'


def test_read_affix_effect_multi_line_edge(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """多行效果(第三位面强化:描述+续句)拼接 + 边缘词缀 tooltip(x98 不出屏)。"""
    ocr = [
        _ocr('第三位面强化', 98, 857),     # tooltip 标题(最左词缀,tooltip 贴左边 x98)
        _ocr('第三位面中的敌人获得强化，速度提高60%，生命上限提', 98, 884),  # 描述
        _ocr('高30%。', 98, 910),         # 续句
        _ocr('敌人难度108', 46, 964),
        _ocr('第三位面强化', 305, 968),   # 词缀行同名(下方,排除)
    ]
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', lambda **kw: ocr)
    effect = read_affix_effect(test_context, None, '第三位面强化')
    assert '速度提高60%' in effect and '生命上限提高30%' in effect, f'拼接缺失,实际 {effect!r}'


def test_read_affix_effect_no_tooltip(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """tooltip 未弹(无 y<词缀行的同名标题,只词缀行本身)→ ''(调用方写 yml 待采)。"""
    ocr = [_ocr('阵营', 229, 651), _ocr('软弱无力', 822, 967), _ocr('下一步', 1474, 967)]
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', lambda **kw: ocr)
    assert read_affix_effect(test_context, None, '软弱无力') == ''


def test_read_board_xy_count_and_next_tier(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """左面板 'X/Y' → count=X + next_tier=Y(doc 13 FactionState;D-68 备战字段采集)。

    聚焦 OCR 读对 "X/Y"(全屏密度把 "2/3" 误读 "213";区域裁切/mock 读对)。count 走 X(read_board
    回归),next_tier 走 Y(read_board_next_tier 新)。裸数字(tier 链残留)不当 count。
    """
    ocr = [
        _ocr('能量', 105, 222), _ocr('2/3', 108, 259),       # count=2, next_tier=3
        _ocr('仙舟', 106, 310), _ocr('1/3', 108, 342),       # count=1, next_tier=3
        _ocr('贝洛伯格', 108, 476), _ocr('1/2', 108, 513),   # count=1, next_tier=2
    ]
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', lambda **kw: ocr)
    assert read_board(test_context, None) == {'能量': 2, '仙舟': 1, '贝洛伯格': 1}
    assert read_board_next_tier(test_context, None) == {'能量': 3, '仙舟': 3, '贝洛伯格': 2}


def test_write_affix_effects_merge(tmp_path) -> None:
    """merge updates 进 affix_effects_data.py:新名新增、不一致覆盖、空 updates 不写(写回仍是合法 py + 中文)。

    _AFFIX_EFFECTS_PATH + write_affix_effects 在 cw_briefing_obs(D-70 拆分);函数 read 其模块全局,
    故 monkeypatch cw_briefing_obs._AFFIX_EFFECTS_PATH(不是 cw_observation 的 re-export 绑定)。
    """
    py_file = tmp_path / 'affix_effects_data.py'
    py_file.write_text('AFFIX_EFFECTS = {"旧词缀": "旧效果"}\n', encoding='utf-8')
    original = cw_briefing_obs._AFFIX_EFFECTS_PATH
    cw_briefing_obs._AFFIX_EFFECTS_PATH = py_file
    try:
        assert cw_briefing_obs.write_affix_effects({}) is False                 # 空 → 不写
        assert cw_briefing_obs.write_affix_effects({'新词缀': '效果A'}) is True  # 新名 → 写
        assert cw_briefing_obs.write_affix_effects({                              # 不一致 → 覆盖 + 新名追加
            '旧词缀': '旧效果改', '词缀2': '效果C',
        }) is True
        # 写回的文件仍是合法 py(exec 能解析)+ 内容正确
        ns: dict = {}
        exec(py_file.read_text(encoding='utf-8'), ns)   # noqa: S102
        assert ns['AFFIX_EFFECTS'] == {'旧词缀': '旧效果改', '新词缀': '效果A', '词缀2': '效果C'}
    finally:
        cw_briefing_obs._AFFIX_EFFECTS_PATH = original


def test_load_affix_effects_from_file(tmp_path) -> None:
    """读 affix_effects_data.py → AFFIX_EFFECTS dict(采集对比用);文件不存在 → 空。

    _AFFIX_EFFECTS_PATH 在 cw_briefing_obs(D-70 拆分),monkeypatch 它(非 cw_observation re-export)。
    """
    py_file = tmp_path / 'affix_effects_data.py'
    py_file.write_text('AFFIX_EFFECTS = {"词缀A": "效果A"}\n', encoding='utf-8')
    original = cw_briefing_obs._AFFIX_EFFECTS_PATH
    cw_briefing_obs._AFFIX_EFFECTS_PATH = py_file
    try:
        assert cw_briefing_obs.load_affix_effects_from_file() == {'词缀A': '效果A'}
        cw_briefing_obs._AFFIX_EFFECTS_PATH = tmp_path / 'no_exist.py'          # 文件不存在 → 空
        assert cw_briefing_obs.load_affix_effects_from_file() == {}
    finally:
        cw_briefing_obs._AFFIX_EFFECTS_PATH = original


def test_read_affix_effect_returns_raw_for_compare(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """read_affix_effect 只返回效果原文(纯解析);跟谁比(注册表文件)是 _collect_affix_effects 的事。

    验证返回值原样透传(对比逻辑在 HandleBriefing._collect_affix_effects,跟 affix_effects_data.py 比),这里只确认解析正确。
    """
    ocr = [
        _ocr('软弱无力', 627, 859),
        _ocr('没有穿戴3件装备的角色及其忆灵，造成的伤害为原伤害的', 628, 885),
        _ocr('80%.', 624, 908),
        _ocr('软弱无力', 822, 967),
    ]
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', lambda **kw: ocr)
    effect = read_affix_effect(test_context, None, '软弱无力')
    assert '没有穿戴3件装备' in effect and '80%' in effect


def test_read_round_outcome_failure_hp_zero(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """失败结算屏(挑战失败 + 生命值❤!)→ hp_after=0 conf=1.0(团灭确定,非 conf=0)。D-51。

    parse_settlement_hp 在失败屏读到「生命值❤!」(非数字)→ None,但「挑战失败」= hp 0 确定。
    """
    from sr_od.application.currency_war.cw_observation import read_round_outcome
    ocr = [SimpleNamespace(data=t) for t in ['挑战失败', '小队生命值❤！', '对局评价', '下一步']]
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', lambda **kw: ocr)
    obs = read_round_outcome(test_context, None, plane=1, round_num=9, comp_tag='DOT队')
    assert obs.hp_after == 0, f'失败屏应 hp=0,实际 {obs.hp_after}'
    assert obs.hp_confidence == 1.0, f'失败屏 conf 应 1.0(确定死),实际 {obs.hp_confidence}'
