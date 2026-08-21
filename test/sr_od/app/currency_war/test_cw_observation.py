"""货币战争 OCR 观测层测试。

纯逻辑(parse_settlement_hp;P1.5 结算屏 hp_after 解析)+ 集成(read_affixes 简报词缀,
需 fixture + ctx.ocr_service)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war import cw_briefing_obs, cw_observation
from sr_od.application.currency_war.cw_briefing_obs import (
    parse_enemy_difficulty,
    read_briefing_enemy_difficulty,
)
from sr_od.application.currency_war.cw_observation import (
    parse_selected_difficulty,
    parse_settlement_hp,
    read_affix_effect,
    read_affixes,
    read_board,
    read_board_next_tier,
    read_bosses,
    read_deploy_cap,
    read_deployed_count,
    read_enemy_difficulty,
    read_level_up_cost,
    read_node_type,
    read_selected_difficulty,
    read_shop_refresh_cost,
    read_streak,
    read_xp_progress,
)
from sr_od.application.currency_war.cw_settlement_obs import parse_streak
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


def test_parse_hp_garble_missing_sheng() -> None:
    """OCR garble「生命值」→「命值」(missing 生)→ 仍解析(2026-08-07 hp garble fix e440e496)。

    on_round_end 结算屏 OCR 偶 garble「生命值」→「命值」→ parse_settlement_hp 旧版失败 → hp 0 →
    PerformanceTracker trend 噪声。garble fix 容忍「命值」→ 准确 hp → comp_viability 输入可信。
    """
    assert parse_settlement_hp(['小队命值74i']) == 74
    assert parse_settlement_hp(['挑战结束', '小队命值58', '继续挑战']) == 58


def test_parse_streak_win_loss_direction() -> None:
    """结算「连胜×N」/「连败×N」前缀=方向:连胜 + / 连败 −;未读到 0(fixture 核实 2026-08-11)。"""
    assert parse_streak(['连胜×0']) == 0
    assert parse_streak(['挑战结束', '连胜×3', '继续挑战']) == 3
    assert parse_streak(['连败×2']) == -2
    assert parse_streak(['连胜x5']) == 5               # × 读成 x 也容忍
    assert parse_streak(['挑战结束', '数据统计']) == 0   # 无 streak 文本


def test_parse_streak_from_real_settlement_ocr() -> None:
    """实跑结算屏 OCR(_SETTLEMENT_OCR 含 '连胜×0')→ streak 0。"""
    assert parse_streak(_SETTLEMENT_OCR) == 0


# ===== 挑战进度/胜负真值(2026-08-18 用户点破:「扣血=战斗失败,游戏内有记录」) =====

def test_parse_settlement_progress_live_forms() -> None:
    """挑战进度三 live 形态:后随 +N(赢)/ 前置 -N(输,M41 战败屏)/ 无符号累计值不取。"""
    from sr_od.application.currency_war.cw_settlement_obs import (
        parse_settlement_progress,
    )
    # live 11:32 样本(遭遇赢):分离 token '+2' 跟后
    assert parse_settlement_progress(['28', '挑战结束', '遭遇', '挑战进度', '+2', '基础伤害']) == 2
    # M41 战败屏实锤形态:数字前置
    assert parse_settlement_progress(['2-1战斗', '-22', '挑战进度', '前往结算']) == -22
    # 同 token 粘连
    assert parse_settlement_progress(['挑战进度+3']) == 3
    assert parse_settlement_progress(['挑战进度-15']) == -15
    # live 11:33 样本(挑战成功屏):「挑战进度」'46' 无符号 = 累计值非 delta → None(防 -22 记成 +46)
    assert parse_settlement_progress(['31', '挑战成功', '奖励', '挑战进度', '46', '点击空白加速']) is None
    # 无进度文本
    assert parse_settlement_progress(['挑战成功', '继续挑战']) is None


def test_parse_settlement_won_live_forms() -> None:
    """胜负真值:挑战成功→True / 挑战失败→False / 负进度→False / 无据→None。"""
    from sr_od.application.currency_war.cw_settlement_obs import parse_settlement_won
    assert parse_settlement_won(['31', '挑战成功', '挑战进度', '46']) is True
    assert parse_settlement_won(['挑战失败', '下一步']) is False
    # 轮败屏(活着):挑战结束 + 负进度,无成功/失败字样
    assert parse_settlement_won(['挑战结束', '-22', '挑战进度', '前往结算']) is False
    assert parse_settlement_won(['挑战结束', '挑战进度', '+2', '继续挑战']) is True
    assert parse_settlement_won(['数据统计', '继续挑战']) is None


def test_round_outcome_carries_killed_and_progress() -> None:
    """read_round_outcome 填 killed/progress_delta(胜负真值进 outcomes.jsonl)。"""
    from sr_od.application.currency_war.cw_settlement_obs import read_round_outcome

    class _FakeOcr:
        def __init__(self, texts):
            self._texts = texts

        def get_ocr_result_list(self, image, rect, crop_first):
            from types import SimpleNamespace
            return [SimpleNamespace(data=t, y=i) for i, t in enumerate(self._texts)]

    class _FakeCtx:
        ocr_service = None

        def __init__(self, texts):
            _FakeCtx.ocr_service = _FakeOcr(texts)

    # 输轮屏:挑战结束 -22 → killed=False, progress_delta=-22
    ctx = _FakeCtx(['2-1战斗', '-22', '挑战进度', '前往结算'])
    obs = read_round_outcome(ctx, None, plane=2, round_num=1, comp_tag='x')
    assert obs.killed is False and obs.progress_delta == -22
    # 赢轮屏:挑战成功 → killed=True
    ctx2 = _FakeCtx(['31', '挑战成功', '挑战进度', '46', '继续挑战'])
    obs2 = read_round_outcome(ctx2, None, plane=1, round_num=8, comp_tag='x')
    assert obs2.killed is True


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


def test_read_briefing_enemy_difficulty(test_context: SrTestContext) -> None:
    """简报「敌人难度N」(标识-敌人难度 area OCR → parse_enemy_difficulty)→ int。

    fixture ``screens/货币战争-简报/default.webp``:左下「敌人难度N」(N 为数值,如 108)。
    read_briefing_enemy_difficulty OCR 区域 → parse → int(0<N≤300)。下游
    ctx.cw_enemy_difficulty → session.enemy_difficulty → state(3.5.2,diagnostic;danger_d
    未实现 dormant)。值跨局随职级/词缀叠算变,只校验读到合法 int(非 specific 值)。
    对照 sibling reader:test_read_affixes_briefing / test_read_bosses_briefing。
    """
    if not test_context.has_screen('货币战争-简报', 'default'):
        pytest.skip('存档截图缺失:screens/货币战争-简报/default.webp')
    screen = test_context.load_screen('货币战争-简报', 'default')
    difficulty = read_briefing_enemy_difficulty(test_context, screen)
    assert difficulty is not None, '未读到敌人难度(标识-敌人难度 area OCR 应含「敌人难度N」)'
    assert 0 < difficulty <= 300, f'敌人难度越界(应 0<N≤300),实际 {difficulty}'


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
    """造 OCR result(data + center + x/w),给 read_affix_effect / _node_type_label mock 用。

    x/w 以「center=x」补齐(x-20 宽40 → x+w/2 = x):真实 OcrMatchResult 有 x/w 属性
    (r80 read_node_type 位置化后消费),mock 对齐。"""
    return SimpleNamespace(data=text, center=Point(x, y), x=x - 20, w=40)


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


def test_read_xp_progress_xy(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """购买经验下方 "X/Y" → (cur_xp, xp_to_next);越界/无 → None(D-69 备战字段采集)。"""
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [_ocr('4/20', 282, 935)])
    assert read_xp_progress(test_context, None) == (4, 20)
    # 越界(cur>next)→ None
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [_ocr('20/4', 282, 935)])
    assert read_xp_progress(test_context, None) is None
    # 无 "X/Y" → None
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [_ocr('购买经验', 282, 935)])
    assert read_xp_progress(test_context, None) is None


def test_read_node_type_keyword(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """顶部节点类型标签 → node_type(首领→boss 等);无已知关键词 → None(D-72 备战字段采集)。"""
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [_ocr('首领', 1337, 82)])
    assert read_node_type(test_context, None) == 'boss'
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [_ocr('补给', 1200, 82)])
    assert read_node_type(test_context, None) == 'supply'
    # 无已知节点类型关键词(如只读到 "1-9" 轮次)→ None
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [_ocr('1-9', 441, 59)])
    assert read_node_type(test_context, None) is None


def test_read_prep_numeric_fields(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """备战左上/购买经验/商店区数字字段:enemy_difficulty/level_up_cost/shop_refresh_cost/streak(D-74)。

    各字段 OCR 其 screen_info area → int(越界/空 → None 或默认)。shop_refresh_cost 默认 2。
    """
    # enemy_difficulty(文本-难度,stylized 但能读到时):"108" → 108
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [_ocr('108', 136, 70)])
    assert read_enemy_difficulty(test_context, None) == 108
    # level_up_cost(文本-购买经验金币数):"4" → 4
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [_ocr('4', 296, 990)])
    assert read_level_up_cost(test_context, None) == 4
    # shop_refresh_cost(文本-刷新金币数):"2" → 2;空 → 默认 2
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [_ocr('2', 1621, 855)])
    assert read_shop_refresh_cost(test_context, None) == 2
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', lambda **kw: [])
    assert read_shop_refresh_cost(test_context, None) == 2   # 空 → 默认 2
    # streak(文本-连胜数):"3" → 3;空 → None
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [_ocr('3', 1523, 875)])
    assert read_streak(test_context, None) == 3
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', lambda **kw: [])
    assert read_streak(test_context, None) is None
    # enemy_difficulty 越界(>300)→ None
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [_ocr('999', 136, 70)])
    assert read_enemy_difficulty(test_context, None) is None


def test_write_affix_effects_merge(tmp_path) -> None:
    """merge updates 进 affix_effects_data.py:新名新增、**不一致不覆盖(D-81:静态数据现有值更可信)**、
    空 updates 不写(写回仍是合法 py + 中文)。

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
        assert cw_briefing_obs.write_affix_effects({                              # D-81:旧词缀 divergent 不覆盖 + 新名追加
            '旧词缀': '旧效果改', '词缀2': '效果C',
        }) is True
        # 写回的文件仍是合法 py(exec 能解析)+ 内容正确(旧词缀保留旧效果,未被 divergent 覆盖)
        ns: dict = {}
        exec(py_file.read_text(encoding='utf-8'), ns)   # noqa: S102
        assert ns['AFFIX_EFFECTS'] == {'旧词缀': '旧效果', '新词缀': '效果A', '词缀2': '效果C'}
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


def test_read_deploy_cap_equals_level(test_context: SrTestContext) -> None:
    """区域-部署数 'X/Y' → cap(Y)恒= level(无钻石时);D-53 实测核正 + 修复 reader 回归。

    旧 reader 全 None(区域-部署数 pc_rect 终点 y240 切在文字 y244 上方 + 无 padding → paddle det
    拆斜杠 + 3x 放大进一步碎化)。D-53 修:pc_rect 给足 padding(右留余量容 'X/10')+ 原生 OCR
    (不放大,字体够大)+ 斜杠 normalize + X>Y guard。fixture 跨 lv3/4/5/7 核 cap=level。
    """
    if not test_context.has_screen('货币战争-备战', 'deployed_p1r9'):
        pytest.skip('存档截图缺失:screens/货币战争-备战/deployed_p1r9.webp')
    # deployed_p1r9:5/5@lv5(全部署)
    screen = test_context.load_screen('货币战争-备战', 'deployed_p1r9')
    assert cw_observation.read_level(test_context, screen, 1, 9) == 5
    assert read_deploy_cap(test_context, screen) == 5
    assert read_deployed_count(test_context, screen) == 5
    # prep_1-6:4/4@lv4
    screen2 = test_context.load_screen('货币战争-备战', 'prep_1-6_all_positions')
    assert read_deploy_cap(test_context, screen2) == 4
    assert read_deployed_count(test_context, screen2) == 4
    # a8_start:真值 0/3@lv3,OCR 噪声 "10/3"(slash 致 X 虚高)→ X>Y guard 兜:cap=3,deployed=None
    screen3 = test_context.load_screen('货币战争-备战', 'shop_closed_a8_start')
    assert read_deploy_cap(test_context, screen3) == 3
    assert read_deployed_count(test_context, screen3) is None
    # lowhp:6/7@lv7
    screen4 = test_context.load_screen('货币战争-备战', 'shop_closed_lowhp')
    assert read_deploy_cap(test_context, screen4) == 7
    assert read_deployed_count(test_context, screen4) == 6


def test_parse_selected_difficulty() -> None:
    """难度确认 OCR 文字 → 职级(A\\d+(-\\d+)?);过滤非职级(财富造物主 等)。"""
    assert parse_selected_difficulty(['A8', '财富造物主']) == 'A8'
    assert parse_selected_difficulty(['A5']) == 'A5'
    assert parse_selected_difficulty(['A8-1']) == 'A8-1'
    assert parse_selected_difficulty(['A8-50']) == 'A8-50'
    assert parse_selected_difficulty(['财富造物主', '当前职级难度效果']) == ''
    assert parse_selected_difficulty([]) == ''


def test_read_selected_difficulty_a8_a5(test_context: SrTestContext) -> None:
    """难度确认屏 fixture → 职级(a8→A8 / a5→A5;AX label 左上 OCR → effective_hp_threshold D-32)。"""
    if not test_context.has_screen('货币战争-难度确认', 'a8'):
        pytest.skip('fixture 未采:screens/货币战争-难度确认/a8')
    screen = test_context.load_screen('货币战争-难度确认', 'a8')
    assert read_selected_difficulty(test_context, screen) == 'A8'
    if test_context.has_screen('货币战争-难度确认', 'a5'):
        screen5 = test_context.load_screen('货币战争-难度确认', 'a5')
        assert read_selected_difficulty(test_context, screen5) == 'A5'


def test_parse_enemy_difficulty() -> None:
    """简报「敌人难度N」OCR → int;过滤词缀/首领;越界(>300)→ None(3.5.2)。"""
    assert parse_enemy_difficulty(['敌人难度108', '随从强化']) == 108
    assert parse_enemy_difficulty(['敌人难度 50']) == 50
    assert parse_enemy_difficulty(['随从强化', '开局不利']) is None  # 无难度文字
    assert parse_enemy_difficulty(['敌人难度999']) is None  # 越界(>300)
    assert parse_enemy_difficulty([]) is None


def test_parse_damage_value() -> None:
    """伤害值文本 parse(万/亿/纯数字;无数字/异常 → None;3.5.4 战斗总伤害)。"""
    from sr_od.application.currency_war.cw_observation import parse_damage_value
    assert parse_damage_value('126.5万') == 1_265_000
    assert parse_damage_value('89.8万') == 898_000
    assert parse_damage_value('83.7万') == 837_000
    assert parse_damage_value('1439282') == 1_439_282
    assert parse_damage_value('1.5亿') == 150_000_000
    assert parse_damage_value('0') == 0
    assert parse_damage_value('') is None
    assert parse_damage_value('abc') is None
    assert parse_damage_value('试用') is None  # 战斗屏噪声


def test_read_total_damage() -> None:
    """战斗右侧「伤害」列 OCR → 求和(126.5万+89.8万+83.7万=3,000,000;噪声「羁绊/试用」过滤)。"""
    import numpy as np

    from sr_od.application.currency_war.cw_observation import read_total_damage
    screen = np.zeros((1080, 1920, 3), dtype=np.uint8)
    # OCR 返 3 角色伤害 + 噪声(羁绊/试用)→ 只求和伤害(parse_damage_value 过滤噪声)
    _ocr = [SimpleNamespace(data=d) for d in ['羁绊', '126.5万', '89.8万', '83.7万', '试用']]
    ctx = SimpleNamespace(ocr_service=SimpleNamespace(
        get_ocr_result_list=lambda image=None: _ocr))
    assert read_total_damage(ctx, screen, (1680, 240, 1820, 420)) == 1_265_000 + 898_000 + 837_000
    # 空区域(crop.size==0)→ None
    assert read_total_damage(ctx, screen, (0, 0, 0, 0)) is None
    # 无伤害数字(全噪声)→ None
    _ocr_noise = [SimpleNamespace(data=d) for d in ['试用', '羁绊', '伤害']]
    ctx2 = SimpleNamespace(ocr_service=SimpleNamespace(
        get_ocr_result_list=lambda image=None: _ocr_noise))
    assert read_total_damage(ctx2, screen, (1680, 240, 1820, 420)) is None


# ===== ADR-0129 XP 分母反推真等级 =====
def test_level_from_xp_inverse_table() -> None:
    """XP 条分母 = 当前级→下一级门槛(用户实测表):反查得真等级;表外值/None 安全返 None。"""
    from sr_od.application.currency_war.cw_observation import _level_from_xp
    assert _level_from_xp((0, 4)) == 3      # 3→4 需 4
    assert _level_from_xp((18, 20)) == 5    # 5→6 需 20(M15 位面 2 真实 lv5 实锤)
    assert _level_from_xp((2, 40)) == 6
    assert _level_from_xp((0, 52)) == 7
    assert _level_from_xp((0, 2)) is None   # 1-2 级门槛不在表 → 不覆盖
    assert _level_from_xp(None) is None

