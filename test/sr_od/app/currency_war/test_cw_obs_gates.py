# -*- coding: utf-8 -*-
"""test_cw_obs_gates 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- observation: test_cw_observation.py
- observation_gate: test_cw_observation_gate.py
- observe_throttle: test_cw_observe_throttle.py
- identity_obs: test_cw_identity_obs.py
- board_by_row: test_cw_board_by_row.py
- w534_board_center_gate: test_cw_w534_board_center_gate.py
- test_pivot_plane_filter: test_pivot_plane_filter.py
- pivot_invariant: test_cw_pivot_invariant.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== observation ====================

from types import SimpleNamespace

import pytest

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.obs import cw_briefing_obs, cw_observation
from sr_od.application.currency_war.obs.cw_briefing_obs import parse_enemy_difficulty, read_briefing_enemy_difficulty
from sr_od.application.currency_war.obs.cw_briefing_obs import read_affix_effect, read_affixes, read_bosses
from sr_od.application.currency_war.obs.cw_observation import parse_selected_difficulty, read_board, read_board_next_tier, read_deploy_cap, read_deployed_count, read_enemy_difficulty, read_level_up_cost, read_node_type, read_selected_difficulty, read_shop_refresh_cost, read_streak, read_xp_progress
from sr_od.application.currency_war.obs.cw_settlement_obs import parse_settlement_hp, parse_streak
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
    from sr_od.application.currency_war.obs.cw_settlement_obs import parse_settlement_progress
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
    from sr_od.application.currency_war.obs.cw_settlement_obs import parse_settlement_won
    assert parse_settlement_won(['31', '挑战成功', '挑战进度', '46']) is True
    assert parse_settlement_won(['挑战失败', '下一步']) is False
    # 轮败屏(活着):挑战结束 + 负进度,无成功/失败字样
    assert parse_settlement_won(['挑战结束', '-22', '挑战进度', '前往结算']) is False
    assert parse_settlement_won(['挑战结束', '挑战进度', '+2', '继续挑战']) is True
    assert parse_settlement_won(['数据统计', '继续挑战']) is None


def test_round_outcome_carries_killed_and_progress() -> None:
    """read_round_outcome 填 killed/progress_delta(胜负真值进 outcomes.jsonl)。"""
    from sr_od.application.currency_war.obs.cw_settlement_obs import read_round_outcome

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
    """投资环境 3 卡名读取(CwScreenInvestEnv._read_options by NAME_CY 行过滤)。

    fixture ``screens/货币战争-投资环境/default.webp``。NAME_CY [360,410] 容卡名 y 随立绘变
    (修前 [378,408] 漏 y<378 的卡名,实机 3 卡名 y 375-378)。
    """
    if not test_context.has_screen('货币战争-投资环境', 'default'):
        pytest.skip('存档截图缺失:screens/货币战争-投资环境/default.webp')
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_invest_env import CwScreenInvestEnv
    screen = test_context.load_screen('货币战争-投资环境', 'default')
    op = CwScreenInvestEnv(test_context)
    opts = op._read_options(screen)
    assert len(opts) == 3, f'期望 3 卡名,实际 {opts}'


def test_read_select_partner_candidates(test_context: SrTestContext) -> None:
    """选择伙伴 候选阵营 label 读取(CwScreenPartner._read_candidates by 中央 x + y 行过滤)。

    D-60:硬编码 STAGE_PORTRAIT 落候选间隙 flat-loop → 改 OCR 定位候选。fixture
    ``screens/货币战争-列车同行/default.webp``(1-7 节点 2 候选 护盾/能量)。
    **关键回归**:候选必须只在中央 overlay(x>450),不含左侧备战面板 board label
    (仙舟/列车同行/能量 在 x~106 同 y 行)—— D-60 初版漏 x 过滤会把 board label 当候选。
    """
    if not test_context.has_screen('货币战争-列车同行', 'default'):
        pytest.skip('存档截图缺失:screens/货币战争-列车同行/default.webp')
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_partner import CwScreenPartner
    screen = test_context.load_screen('货币战争-列车同行', 'default')
    op = CwScreenPartner(test_context)
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


# ===== board 计数低估修复:徽标优先 + 斜杠丢失容错(mock OCR 锁语义)=====

def test_read_board_badge_digit_wins_over_tier_chain(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """徽标数字优先于档位链:持续伤害行 徽标"3"(x=73,名称列左侧)+ 链"2/4/6"(x=107)
    → count=3(旧链被 "2/4" 误配成 2 或兜底 1);next_tier 走注册表(>3 最小档=4)。"""
    ocr = [
        _ocr('持续伤害', 106, 143),
        _ocr('3', 73, 177),        # 徽标(纯数字,名称列左侧 x<104)
        _ocr('21416', 107, 177),   # 档位链 "2/4/6" 斜杠丢失,不产 count
    ]
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', lambda **kw: ocr)
    assert read_board(test_context, None) == {'持续伤害': 3}
    assert read_board_next_tier(test_context, None) == {'持续伤害': 4}


def test_read_board_slash_lost_rescue(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """斜杠丢失容错:"2/3"→"213"('/'误读'1')→ 删'1'还原 (2,3),Y∈狼狩 tiers(3,5,6,8) 校验过
    → count=2, next_tier=3;徽标缺读(OCR 漏小字)时兜住低估。"""
    ocr = [
        _ocr('狼狩', 106, 227),
        _ocr('213', 110, 261),     # "2/3" 斜杠丢失
    ]
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', lambda **kw: ocr)
    assert read_board(test_context, None) == {'狼狩': 2}
    assert read_board_next_tier(test_context, None) == {'狼狩': 3}


def test_read_board_tier_chain_not_rescued(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """档位链不参与容错还原:持续伤害链 "2/4/6"→"21416" 删单 '1' 拆不出
    (X≤9 且 Y∈tiers 且 Y>X)的合法对 → 拒绝,兜底 count=1 且 honest=False。"""
    from sr_od.application.currency_war.obs.cw_observation import _board_pairs
    ocr = [
        _ocr('持续伤害', 106, 143),
        _ocr('21416', 107, 177),   # 无徽标 token,仅档位链
    ]
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', lambda **kw: ocr)
    pairs, honest = _board_pairs(test_context, None)
    assert pairs == {'持续伤害': (1, 0)}, f'档位链不得还原成 count,实得 {pairs}'
    assert honest is False, '全兜底帧应 honest=False'


def test_read_board_expected_fallback_when_ocr_exhausted(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """OCR 证据穷尽(档位链阵营徽标失读)→ expected(身份 computed)兜底,非恒 1。

    证据帧 86ce9fd1 形态:持续伤害/护盾 真值 2,徽标+X/Y+容错全失读;
    旧链恒 1 = 低估最后一环。expected 兜底不翻 honest(帧 OCR 真值不明)。
    """
    from sr_od.application.currency_war.obs.cw_observation import _board_pairs
    ocr = [
        _ocr('持续伤害', 106, 143),
        _ocr('21416', 107, 177),   # 档位链,无徽标 token
    ]
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', lambda **kw: ocr)
    pairs, honest = _board_pairs(test_context, None, expected={'持续伤害': 2})
    assert pairs == {'持续伤害': (2, 4)}, f'expected 底座应兜底 2(next_tier=4),实得 {pairs}'
    assert honest is False, 'expected 兜底不算 OCR 真解析'
    # expected 越界 → 恒 1 兜底
    pairs2, _ = _board_pairs(test_context, None, expected={'持续伤害': 99})
    assert pairs2 == {'持续伤害': (1, 0)}, f'expected 越界应恒 1,实得 {pairs2}'


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

    各字段 OCR 其 screen_info area → int(越界/空 → None 或默认)。shop_refresh_cost
    放大两级管线,空 → None(W577:读到的是面板徽标=利息数值非刷价,函数仅旁证)。
    """
    # enemy_difficulty(文本-难度,stylized 但能读到时):"108" → 108
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [_ocr('108', 136, 70)])
    assert read_enemy_difficulty(test_context, None) == 108
    # level_up_cost(文本-购买经验金币数):"4" → 4
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [_ocr('4', 296, 990)])
    assert read_level_up_cost(test_context, None) == 4
    # level_up_cost 二级管线:一级(3x 放大)读空 → OTSU 二值化重试兜回
    calls = {'n': 0}

    def _two_stage(**kw):
        calls['n'] += 1
        return [_ocr('4', 296, 990)] if calls['n'] == 2 else []

    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', _two_stage)
    assert read_level_up_cost(test_context, None) == 4
    # shop_refresh_cost(文本-刷新金币数):"2" → 2;空 → None(W577:函数
    # 保留作旁证读数,读到的是面板徽标=利息数值,非刷价——见实帧锁 docstring)
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [_ocr('2', 1621, 855)])
    assert read_shop_refresh_cost(test_context, None) == 2
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', lambda **kw: [])
    assert read_shop_refresh_cost(test_context, None) is None   # 空 → None
    # 刷价金币图标并入前缀('G0'/'GO')→ 归一后读 0
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [_ocr('G0', 1621, 855)])
    assert read_shop_refresh_cost(test_context, None) == 0
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [_ocr('GO', 1621, 855)])
    assert read_shop_refresh_cost(test_context, None) == 0
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
    from sr_od.application.currency_war.obs.cw_settlement_obs import read_round_outcome
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
    # a8_start:真值 0/3@lv3,OCR "10/3"(人形图标并入 X 成前缀 '1')→ 图标前缀守卫
    # 去前缀得 X=0(画面事实,空板;旧 X>Y guard 只能兜 None)。锁值更新。
    screen3 = test_context.load_screen('货币战争-备战', 'shop_closed_a8_start')
    assert read_deploy_cap(test_context, screen3) == 3
    assert read_deployed_count(test_context, screen3) == 0
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
    from sr_od.application.currency_war.obs.cw_observation import parse_damage_value
    assert parse_damage_value('126.5万') == 1_265_000
    assert parse_damage_value('89.8万') == 898_000
    assert parse_damage_value('83.7万') == 837_000
    assert parse_damage_value('1439282') == 1_439_282
    assert parse_damage_value('1.5亿') == 150_000_000
    assert parse_damage_value('0') == 0
    assert parse_damage_value('') is None
    assert parse_damage_value('abc') is None
    assert parse_damage_value('试用') is None  # 战斗屏噪声


# ===== ADR-0129 XP 分母反推真等级 =====
def test_level_from_xp_inverse_table() -> None:
    """XP 条分母 = 当前级→下一级门槛(用户实测表):反查得真等级;表外值/None 安全返 None。"""
    from sr_od.application.currency_war.obs.cw_observation import _level_from_xp
    assert _level_from_xp((0, 4)) == 3      # 3→4 需 4
    assert _level_from_xp((18, 20)) == 5    # 5→6 需 20(M15 位面 2 真实 lv5 实锤)
    assert _level_from_xp((2, 40)) == 6
    assert _level_from_xp((0, 52)) == 7
    assert _level_from_xp((0, 2)) is None   # 1-2 级门槛不在表 → 不覆盖
    assert _level_from_xp(None) is None


# ===== 购买经验费用实帧锁(两级管线:3x 放大 + OTSU 二值化重试) =====
def test_read_level_up_cost_real_fixture(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """真实备战帧锁:费用数字原生分辨率 det 漏检(全语料实读 0% 的失读字段),
    两级管线应恢复读数。锁两帧:shop_closed(3x 放大即可读)+ 双宝钻局(仅 OTSU
    二值化级可读,防二级管线被静默剥除)。模型不可用 / fixture 缺失 → skip。
    """
    from pathlib import Path

    from one_dragon.base.matcher.ocr.ocr_service import OcrService
    from one_dragon.utils import cv2_utils

    fix_dir = Path(__file__).resolve().parents[4] / 'screens' / '货币战争-备战'
    frames = [fix_dir / 'shop_closed.webp', fix_dir / '后排8槽-双宝钻局.webp']
    if not all(p.exists() for p in frames):
        pytest.skip('fixture 缺失')
    try:
        from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
        matcher = OnnxOcrMatcher()
        if not matcher.init_model(download_by_github=False, download_by_gitee=True):
            pytest.skip('OCR 模型不可用')
    except Exception:
        pytest.skip('OCR 模型不可用')
    monkeypatch.setattr(test_context, 'ocr_service', OcrService(ocr_matcher=matcher))
    for p in frames:
        img = cv2_utils.read_image(str(p))
        assert read_level_up_cost(test_context, img) == 4, f'{p.name} 费用应读 4'


# ===== 难度旗牌实帧锁(两级管线:OTSU 反转+徽记剔除为主、4x 放大为辅) =====
def test_read_enemy_difficulty_real_fixture(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """真实备战帧锁:难度数字 stylized(白色艺术字+纹理旗底),原生直读 0/58,
    旗牌管线应恢复读数。锁值覆盖真值分布两端与中段:39/42(低职级局,合理带
    下限附近)+ 108(A8 基准)+ 117(高带);无旗牌帧(区域空白)锁 None。
    模型不可用 / fixture 缺失 → skip。
    """
    from pathlib import Path

    from one_dragon.base.matcher.ocr.ocr_service import OcrService
    from one_dragon.utils import cv2_utils

    fix_dir = Path(__file__).resolve().parents[4] / 'screens'
    expects = {
        '货币战争-备战/shop_closed.webp': 39,
        '货币战争-备战/shop_closed_lowhp.webp': 42,
        '货币战争-备战-角色信息提示/char_detail.webp': 108,
        '货币战争-备战/后排8槽-满级局.webp': 117,
        '货币战争-备战/补给节点.webp': None,   # 无旗牌:区域空白 → None(非默认/兜底值)
        '货币战争-备战/deployed_2star_full.webp': None,
    }
    frames = [fix_dir / n for n in expects]
    if not all(p.exists() for p in frames):
        pytest.skip('fixture 缺失')
    try:
        from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
        matcher = OnnxOcrMatcher()
        if not matcher.init_model(download_by_github=False, download_by_gitee=True):
            pytest.skip('OCR 模型不可用')
    except Exception:
        pytest.skip('OCR 模型不可用')
    monkeypatch.setattr(test_context, 'ocr_service', OcrService(ocr_matcher=matcher))
    for p in frames:
        img = cv2_utils.read_image(str(p))
        assert read_enemy_difficulty(test_context, img) == expects[p.relative_to(fix_dir).as_posix()], \
            f'{p.name} 难度应读 {expects[p.relative_to(fix_dir).as_posix()]}'


# ===== 刷新徽标/连胜 实帧锁(放大两级管线;W577:徽标=利息数值非刷价,ADR-0456) =====
def test_read_refresh_cost_and_streak_real_fixture(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """真实备战帧锁:read_shop_refresh_cost / read_streak 放大管线读数。

    W577 语义翻转(ADR-0456):「文本-刷新金币数」rect 读到的是商店面板
    「↻ N」徽标,N = min(gold//10,5) = 利息数值,**不是刷价**(实付恒基价
    REFRESH_COST_BASE=2,多局干净对账定谳)。期望值 0,0,2,3,2 仍是该 rect
    的正确 OCR 读数——函数保留作旁证,已退出 read_game_state 主链。
    模型不可用 / fixture 缺失 → skip。
    """
    from pathlib import Path

    from one_dragon.base.matcher.ocr.ocr_service import OcrService
    from one_dragon.utils import cv2_utils

    fix_dir = Path(__file__).resolve().parents[4] / 'screens'
    expects = {
        '货币战争-备战/攻略已应用.webp': (0, 1),
        '货币战争-备战/shop_closed.webp': (0, 0),
        '货币战争-备战/deployed_2star.webp': (2, None),
        '货币战争-备战/后排8槽-满级局.webp': (3, 0),
        '货币战争-备战/shop_closed_lowhp.webp': (2, 0),
    }
    frames = [fix_dir / n for n in expects]
    if not all(p.exists() for p in frames):
        pytest.skip('fixture 缺失')
    try:
        from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
        matcher = OnnxOcrMatcher()
        if not matcher.init_model(download_by_github=False, download_by_gitee=True):
            pytest.skip('OCR 模型不可用')
    except Exception:
        pytest.skip('OCR 模型不可用')
    monkeypatch.setattr(test_context, 'ocr_service', OcrService(ocr_matcher=matcher))
    for p in frames:
        img = cv2_utils.read_image(str(p))
        exp_cost, exp_streak = expects[p.relative_to(fix_dir).as_posix()]
        got_cost = read_shop_refresh_cost(test_context, img)
        assert got_cost == exp_cost, f'{p.name} 刷新费应读 {exp_cost},实读 {got_cost}'
        got_streak = read_streak(test_context, img)
        if exp_streak is not None:
            assert got_streak == exp_streak, \
                f'{p.name} 连胜应读 {exp_streak},实读 {got_streak}'


# ===== W577 刷价基价模型锁(ADR-0456:徽标退役出决策链,state 恒基价) =====
def test_shop_refresh_cost_base_price_model_lock() -> None:
    """read_game_state 主链不再 OCR 刷价——state.shop_refresh_cost 恒基价。

    出处:W577 DESIGN 定谳 + ADR-0456(实付恒 2,rect 读数=面板徽标利息
    数值)。源码锁:
    1. cw_observation.read_game_state 里 read_shop_refresh_cost 调用不得
       出现在主链(旁证调用=显式独立)——肯定半(基价赋值字面形状锁)已按
       源码锁瘦身删除;
    2. 决策热路径少一次 OCR 是本改动的效率契约(净减少,禁加回)。
    """
    from pathlib import Path

    import sr_od.application.currency_war.obs.cw_observation as obs_mod
    src = Path(obs_mod.__file__).read_text(encoding='utf-8')
    assert 'state.shop_refresh_cost = read_shop_refresh_cost' not in src, \
        '主链不得再调用 read_shop_refresh_cost(徽标退役,ADR-0456)'
    from sr_od.application.currency_war.kernel.cw_state import REFRESH_COST_BASE
    assert REFRESH_COST_BASE == 2



# ==================== observation_gate ====================

import numpy as np

from sr_od.application.currency_war.obs.cw_observation_gate import wait_stable_frame


class _FakeClock:
    """可推进假时钟;作为 clock 传入时 gate 的 _sleep 也是它驱动。"""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, s: float):
        self.t += s


class _TickingClock(_FakeClock):
    """每次被调用推进 poll 间隔——gate 的 while 轮询天然推进。"""

    def __init__(self, step: float = 0.3):
        super().__init__()
        self._step = step

    def __call__(self):
        self.t += self._step
        return self.t


class _FakeOp:
    """离线 op 桩:r324 后 gate 走 screen_utils.get_match_screen_name
    (框架 id_mark 体系),桩提供 ctx;画面判定用 monkeypatch
    screen_utils(见各测试)。"""

    def __init__(self, frames):
        self._frames = list(frames)
        self.park_calls = 0
        self.ctx = _FakeCtx()

    def park_cursor(self):
        self.park_calls += 1

    def screenshot(self):
        if not self._frames:
            raise RuntimeError('no more frames')
        return self._frames.pop(0)


class _FakeCtx:
    """最小 ctx 桩(gate 只透传给 screen_utils,由 monkeypatch 接管)。"""

    screen_loader = None


def _gray(w=1920, h=1080, v=128):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = v
    return img


def test_returns_stable_frame_when_fingerprint_constant(monkeypatch):
    """静止画面:首尾指纹一致且持续 min_stable_s → 返回帧。"""
    from one_dragon.base.screen import screen_utils as su
    monkeypatch.setattr(su, 'get_match_screen_name',
                        lambda ctx, screen, screen_name_list, crop_first=False:
                        screen_name_list[0])
    clk = _TickingClock(step=0.3)   # 每轮询推进 0.3s
    frames = [_gray(), _gray(), _gray(), _gray(), _gray(), _gray()]
    op = _FakeOp(frames)
    prof = {'screen_list': ['x'], 'expect_screen': 'x',
            'fingerprint_rects': (),
            'timeout_s': 5.0,
            'min_stable_s': 0.5}
    out = wait_stable_frame(op, profile=prof, clock=clk)
    assert out is not None
    assert op.park_calls == 1


def test_timeout_returns_none_when_never_stable(monkeypatch):
    """画面持续变化:超时 → None(None 语义:调用方走旧路径)。"""
    from one_dragon.base.geometry.rectangle import Rect
    from one_dragon.base.screen import screen_utils as su
    monkeypatch.setattr(su, 'get_match_screen_name',
                        lambda ctx, screen, screen_name_list, crop_first=False:
                        screen_name_list[0])
    frames = [_gray(v=v) for v in (10, 20, 30, 40, 50, 60, 70, 80,
                                   90, 100, 110, 120, 130, 140, 150,
                                   160, 170, 180, 190, 200)]
    op = _FakeOp(frames)

    class _Tick:
        def __init__(self):
            self.n = 0

        def __call__(self):
            self.n += 1
            return self.n * 0.3   # 20 帧×0.3=6s > timeout 5s

    prof = {'screen_list': ['x'], 'expect_screen': 'x',
            'fingerprint_rects': (Rect(0, 0, 64, 64),),
            'timeout_s': 5.0,
            'min_stable_s': 0.5}
    out = wait_stable_frame(op, profile=prof, clock=_Tick())
    assert out is None


def test_anchor_blip_recovery_returns_frame(monkeypatch):
    """r327 回归(终审 B):锚短暂 miss 后恢复(指纹未变)→
    稳定窗必须重新达成并返帧——旧 bug 只重置 stable_since
    不重置 first_fp,恢复后 same 成立跳过重设分支 → 永超时
    →(director 站)3-strike 停机。

    ADR-0264 注:fast_confirm 默认开时后续确认轮跳过 OCR,锚
    blip 序列不再被逐轮观测——本锁显式 fast_confirm=False 保持
    「每轮 OCR」旧口径,专锁 r327 锚 miss 重置语义(blip 场景
    下快路径回锚由 test_cw_gate_fast_confirm 覆盖)。"""
    from one_dragon.base.screen import screen_utils as su
    _seq = ['x', None, None, 'x', 'x', 'x', 'x', 'x']   # 1 miss 后恢复
    _i = {'n': 0}

    def _fake(ctx, screen, screen_name_list, crop_first=False):
        v = _seq[min(_i['n'], len(_seq) - 1)]
        _i['n'] += 1
        return v
    monkeypatch.setattr(su, 'get_match_screen_name', _fake)
    frames = [_gray() for _ in range(8)]
    op = _FakeOp(frames)
    prof = {'screen_list': ['x'], 'expect_screen': 'x',
            'fingerprint_rects': (), 'timeout_s': 6.0,
            'min_stable_s': 0.5}
    out = wait_stable_frame(op, profile=prof, clock=_TickingClock(0.3),
                            fast_confirm=False)
    assert out is not None, '锚 blip 恢复后必须能返帧(r327 回归锁)'


def test_screenshot_exception_raises_not_none():
    """终验 P1①:截图异常 → raise(非 None)——异常与超时分流;
    折叠进 None 会被 None 语义表接成 3-strike 停机。"""
    clk = _FakeClock()

    class _Boom(_FakeOp):
        def screenshot(self):
            raise RuntimeError('offline')

    op = _Boom([])
    prof = {'screen_list': ['x'], 'expect_screen': 'x',
            'fingerprint_rects': (),
            'timeout_s': 1.0, 'min_stable_s': 0.3}
    try:
        wait_stable_frame(op, profile=prof, clock=clk)
        raised = False
    except RuntimeError:
        raised = True
    assert raised, '异常必须 raise,不得折叠进 None'


def test_fingerprint_changes_with_pixels():
    """指纹随像素变化(基元在 cv2_utils;r324 下沉)。"""
    from one_dragon.base.geometry.rectangle import Rect
    from one_dragon.utils import cv2_utils
    r = (Rect(0, 0, 64, 64),)
    a = cv2_utils.fingerprint_in_rects(_gray(v=10), r)
    b = cv2_utils.fingerprint_in_rects(_gray(v=10), r)
    c = cv2_utils.fingerprint_in_rects(_gray(v=200), r)
    assert cv2_utils.fingerprint_same(a, b)
    assert not cv2_utils.fingerprint_same(a, c)
    # 阈值容忍:小噪声(±2)视为同帧(局36 diag:字节恒等被
    # 截屏噪声否决)
    noisy = cv2_utils.fingerprint_in_rects(_gray(v=12), r)
    assert cv2_utils.fingerprint_same(a, noisy)


def test_poll_cost_exceeding_budget_returns_frame(monkeypatch):
    """r344 回归锁(局37 停机根因):单轮 poll 成本(截图+OCR)
    超过整个超时预算、画面稳定 → gate 仍必须返帧——旧实现
    `while _now() < deadline` 在首轮 poll 后直接退出,稳定窗
    结构性不可能达成(diag {'screen':0,'fp':1,'ok':0}),
    director 3-strike ping-pong 停机。grace poll 兜底。"""
    from one_dragon.base.screen import screen_utils as su
    monkeypatch.setattr(su, 'get_match_screen_name',
                        lambda ctx, screen, screen_name_list, crop_first=False:
                        screen_name_list[0])
    clk = _FakeClock()
    frames = [_gray(), _gray(), _gray()]
    op = _FakeOp(frames)
    _orig_shot = op.screenshot

    def _slow_shot():
        clk.advance(6.0)   # 单轮 poll 成本 6s > timeout 2s(实机全图 OCR ~5s)
        return _orig_shot()
    op.screenshot = _slow_shot
    prof = {'screen_list': ['x'], 'expect_screen': 'x',
            'fingerprint_rects': (), 'timeout_s': 2.0,
            'min_stable_s': 0.5}
    out = wait_stable_frame(op, profile=prof, clock=clk)
    assert out is not None, 'poll 成本超预算时稳定帧不得被饿死(r344 锁)'


def test_screen_match_uses_fullframe_ocr_for_cache_reuse(monkeypatch):
    """r344 传参锁(用户定调 2026-08-22):gate poll 的屏判定必须
    crop_first=False——全图 OCR 按 id(image) 缓存,同帧多消费者
    (gate 判 4 个 id_mark 区首区触发、后续全缓存命中;gate 末帧
    传 _observe 后 heavy 观察全部命中)共享一次全图 OCR。
    cropped 口径丢弃缓存复用且小 area 易漏字(项目统一 False)。"""
    from one_dragon.base.screen import screen_utils as su
    _seen: list[bool] = []

    def _rec(ctx, screen, screen_name_list, crop_first=False):
        _seen.append(crop_first)
        return screen_name_list[0]
    monkeypatch.setattr(su, 'get_match_screen_name', _rec)
    frames = [_gray(), _gray()]
    op = _FakeOp(frames)
    prof = {'screen_list': ['x'], 'expect_screen': 'x',
            'fingerprint_rects': (), 'timeout_s': 5.0,
            'min_stable_s': 0.5}
    out = wait_stable_frame(op, profile=prof, clock=_TickingClock(0.3))
    assert out is not None
    assert _seen and not any(_seen), \
        f'gate 屏判定必须全图 OCR(crop_first=False)复用缓存,实际 {_seen}'


def test_profile_timeouts_cover_fullframe_ocr_poll_cost():
    """r344 预算锁:profile timeout 必须 ≥2 轮全图 OCR poll
    (~5s/轮实机)+余量——旧 4.5s<单轮成本,稳定窗结构性饿死
    (局37 ping-pong 停机根因)。防未来调回小值忘了成本模型。"""
    from sr_od.application.currency_war.obs.cw_observation_gate import PROFILE_CLOSED, PROFILE_OPEN, PROFILE_POPUP
    for name, prof in (('closed', PROFILE_CLOSED), ('open', PROFILE_OPEN),
                       ('popup', PROFILE_POPUP)):
        assert prof['timeout_s'] >= 12.0, \
            f'{name} timeout={prof["timeout_s"]} 必须 ≥12s(2 轮全图 OCR poll+余量)'


# ==================== observe_throttle ====================

import sys
from pathlib import Path

import numpy as _observe_throttle_np

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

import sr_od.application.currency_war.kernel.cw_observe as obs_mod  # noqa: E402


def test_obs_conflict_shot_throttle(monkeypatch, tmp_path):
    """节流三态:窗内第二张不存(JSONL 照写)/ 异 verdict 不受影响 / 窗口过后恢复。"""
    calls: list[str] = []
    monkeypatch.setattr(obs_mod, 'cw_shot_unique',
                        lambda img, label: (calls.append(label), f'{label}__x.png')[1])
    monkeypatch.setattr(obs_mod, '_CONFLICT_JOURNAL', tmp_path / 'conf.jsonl')
    obs_mod._conflict_shot_ts.clear()
    fake = _observe_throttle_np.zeros((4, 4, 3), dtype=_observe_throttle_np.uint8)
    # 第一张:存
    obs_mod.obs_conflict('deployed_align', 4, 6, fake, verdict='补齐-tracked少计')
    assert len(calls) == 1
    # 同 key 窗内:不存(JSONL 仍追加)
    obs_mod.obs_conflict('deployed_align', 4, 6, fake, verdict='补齐-tracked少计')
    assert len(calls) == 1, '同 (field,verdict) 300s 内节流'
    lines = (tmp_path / 'conf.jsonl').read_text(encoding='utf-8').splitlines()
    assert len(lines) == 2, 'JSONL 证据行不受节流(统计价值保留)'
    # 异 verdict:不受影响
    obs_mod.obs_conflict('deployed_align', 4, 6, fake, verdict='留证-双源不等')
    assert len(calls) == 2, '不同 verdict = 不同慢性态,照存'
    # 窗口过后(monotonic 回拨):恢复存
    obs_mod._conflict_shot_ts[('deployed_align', '补齐-tracked少计')] = -1e9
    obs_mod.obs_conflict('deployed_align', 4, 6, fake, verdict='补齐-tracked少计')
    assert len(calls) == 3, '窗口过后恢复存'


# ==================== identity_obs ====================

import inspect

import pytest as _identity_obs_pytest

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import cv2_utils, file_utils
from sr_od.application.currency_war.obs.currency_war_char_id import load_avatar_templates
from sr_od.application.currency_war.obs.cw_identity_obs import identify_slots, read_deployed_chars, read_star, resolve_char_name
from sr_od.context.sr_context import SrContext
from test.conftest import SrTestContext as _identity_obs_SrTestContext

# character_avatar 脸库在主仓 assets/(sr_od 所在 repo 根;同 conftest.application_plugin_dirs 定位法)
_REPO_ROOT = file_utils.find_src_dir(inspect.getfile(SrContext)).parent
_AVATAR_DIR = _REPO_ROOT / 'assets' / 'template' / 'character_avatar'


def test_resolve_char_name_basic() -> None:
    """avatar_id(主游英文 id)→ 货币战争规范名(直接命中 roster)。"""
    assert resolve_char_name('pela') == '佩拉'
    assert resolve_char_name('herta') == '黑塔'
    assert resolve_char_name('saber') == 'Saber'
    assert resolve_char_name('huohuo') == '藿藿'


def test_resolve_char_name_unknown() -> None:
    """avatar_id 不在主游角色表 → None。"""
    assert resolve_char_name('nonexistent_xyz') is None


@_identity_obs_pytest.fixture(scope='module')
def avatar_templates():
    """加载 character_avatar 脸库(预计算 SIFT 关键点/描述子);模块内复用。"""
    return load_avatar_templates(_AVATAR_DIR)


def test_identify_deployed_front_row(test_context: _identity_obs_SrTestContext, avatar_templates) -> None:
    """identify_slots:实机 fixture(deployed_p1r9)前排 4 槽 → [佩拉,黑塔,Saber,藿藿]。

    硬编码 yml rect(ground truth);D-75 证脸库可匹配备战半身立绘(4/4 强命中)。后排空(VLM 计数
    幻觉,实际无后排部署)→ 不在该断言内。
    """
    if not test_context.has_screen('货币战争-备战', 'deployed_p1r9'):
        _identity_obs_pytest.skip('fixture deployed_p1r9.webp 未采')
    screen = test_context.load_screen('货币战争-备战', 'deployed_p1r9')
    front = [(i, Rect(*r)) for i, r in enumerate([
        [677, 329, 810, 467], [823, 329, 951, 467],
        [969, 329, 1097, 467], [1109, 329, 1241, 467]], start=1)]
    chars = identify_slots(screen, avatar_templates, front, 'front')
    assert [c.char_id for c in chars] == ['佩拉', '黑塔', 'Saber', '藿藿']
    assert all(c.position_pref == 'front' for c in chars)


def test_read_deployed_chars_via_ctx(test_context: _identity_obs_SrTestContext, avatar_templates) -> None:
    """read_deployed_chars:经 ctx.screen_info 取槽位 rect → 前排 4 角色身份(集成,验 screen_info 接线)。

    与 ``test_identify_deployed_front_row`` 互补:前者硬编码 rect 测纯 CV 核心,本测经 ctx screen_loader
    取 rect(= ``_ctx_slots``),验 screen_info area 名(前排-1..4 / 后排-1..6)接线正确。
    """
    if not test_context.has_screen('货币战争-备战', 'deployed_p1r9'):
        _identity_obs_pytest.skip('fixture deployed_p1r9.webp 未采')
    screen = test_context.load_screen('货币战争-备战', 'deployed_p1r9')
    chars = read_deployed_chars(test_context, screen, avatar_templates)
    front = [c.char_id for c in chars if c.position_pref == 'front']
    assert front == ['佩拉', '黑塔', 'Saber', '藿藿']
    # 后排空(fixture 该态无后排部署;VLM 曾幻觉"1 个后排",实为空)
    assert [c for c in chars if c.position_pref == 'back'] == []


def test_read_star_front_row_1star(test_context: _identity_obs_SrTestContext) -> None:
    """read_star:deployed_p1r9 前排 4 槽(佩拉/黑塔/Saber/藿藿,早期 round → 1 星)→ read_star 都=1。

    金星计数(立绘底部金色**四角星** ✦,ADR-0114 TM 法)。1星各槽稳读 1;
    2星见 ``test_read_star_2star_positions``(各位置覆盖)。
    """
    if not test_context.has_screen('货币战争-备战', 'deployed_p1r9'):
        _identity_obs_pytest.skip('fixture deployed_p1r9.webp 未采')
    screen = test_context.load_screen('货币战争-备战', 'deployed_p1r9')
    # 前排-1..4 rect(同 test_identify_deployed_front_row ground truth)= 采 star_front_1..4 的槽位
    front_rects = [Rect(*r) for r in [
        [677, 329, 810, 467], [823, 329, 951, 467],
        [969, 329, 1097, 467], [1109, 329, 1241, 467]]]
    for r in front_rects:
        assert read_star(screen[r.y1:r.y2, r.x1:r.x2]) == 1, f'前排槽 {r} 应为 1 星(1 个金星)'


def test_read_star_2star_positions(test_context: _identity_obs_SrTestContext) -> None:
    """read_star TM:deployed_2star(3 个 2星 + 1星对照)→ 前排-3/后排-3/备战栏-4 读 2,备战栏-1 读 1。

    ADR-0114(2026-08-13):TM + V>150 滤暗金衣服 + thresh 0.50。**前排-3** = 衣服淹没 case(暗金衣服
    V80-150,V>150 滤);**后排-3** = 第2星 val0.511(thresh 0.50 解,原 0.55 漏);备战栏-4 = 2星紧贴。
    """
    if not test_context.has_screen('货币战争-备战', 'deployed_2star'):
        _identity_obs_pytest.skip('fixture deployed_2star.webp 未采')
    screen = test_context.load_screen('货币战争-备战', 'deployed_2star')
    assert read_star(screen[329:467, 969:1097]) == 2, '前排-3 应为 2 星(衣服淹没 case,V>150 解)'
    assert read_star(screen[600:739, 823:953]) == 2, '后排-3 应为 2 星(thresh 0.50:第2星 val0.511)'
    assert read_star(screen[845:979, 757:869]) == 2, '备战栏-4 应为 2 星(紧贴 TM 分离)'
    assert read_star(screen[845:979, 382:495]) == 1, '备战栏-1 应为 1 星(对照,不回归)'


def test_read_star_2star_all_slots_multifixture(test_context: _identity_obs_SrTestContext) -> None:
    """read_star:**全 19 槽 2★ 读 2**(3 个 2★ 角色同时布阵,多 fixture 覆盖各槽)。

    用 DragCwChar op 把飞霄/万敌/椒丘(均 2★)同时布到 3 个不同槽 → 一张 fixture 验 3 个 2★ 槽。
    跨多 fixture 覆盖前排 1-4 / 后排 1-6 / 备战 1-9 全部 2★(各槽 read_star=2,thresh 0.45,ADR-0114/0116)。
    缺 fixture 的项跳过(采到后自动恢复)。配合 ``test_read_star_edge_slots_2star``(边槽)+ 本测(中段/跨排)
    = 2★ 全槽覆盖。
    """
    # (fixture, [(槽位, [x1,y1,x2,y2]), ...]) —— 每 fixture 3 个 2★ 同时在阵
    cases: list[tuple[str, list[tuple[str, list[int]]]]] = [
        ('deployed_2star_3rows',    [('前排-4', [1109, 329, 1241, 467]), ('后排-6', [1245, 600, 1386, 739]), ('备战栏-3', [632, 844, 743, 978])]),
        ('deployed_2star_3rows_b',  [('前排-2', [823, 329, 951, 467]),  ('后排-4', [967, 600, 1097, 739]), ('备战栏-5', [882, 846, 995, 980])]),
        ('deployed_2star_3rows_c',  [('后排-2', [679, 600, 814, 739]),  ('后排-4', [967, 600, 1097, 739]), ('备战栏-6', [1004, 847, 1118, 978])]),
        ('deployed_2star_bench7',   [('备战栏-7', [1132, 846, 1244, 977])]),
        ('deployed_2star_bench8',   [('备战栏-8', [1256, 845, 1368, 979])]),
        ('deployed_2star_bench2',   [('备战栏-2', [507, 844, 620, 978])]),
    ]
    ran = False
    for fx, slots in cases:
        if not test_context.has_screen('货币战争-备战', fx):
            continue
        ran = True
        screen = test_context.load_screen('货币战争-备战', fx)
        for label, (x1, y1, x2, y2) in slots:
            assert read_star(screen[y1:y2, x1:x2]) == 2, f'{fx} {label} 应为 2★'
    if not ran:
        _identity_obs_pytest.skip('multi-fixture 未采(2★ 全槽覆盖用)')


def test_read_star_1star_back_bench_slots(test_context: _identity_obs_SrTestContext) -> None:
    """read_star 1★:后排-2/3/4/5/6 + 备战-9(1★ 单星易 case,补全 1★ 全槽覆盖)。

    1★ 单颗星 val 0.6+ 稳读 1(从未误判)。前排 1-4 见 ``test_read_star_front_row_1star``,
    备战 1-8 见 ``test_read_star_all_rows_2star_full``,后排-1 见 ``test_read_star_all_rows_2star_full``。
    后排-2/4:把 2★ 挪走(deployed→deployed 到空槽)+ 1★(三月七/花火)挪进 —— 无损 shuffle(CW swap/
    sell 拖不生效,但 deployed→deployed 到空槽可行)。至此 1★ 全 19 槽覆盖。
    """
    cases: list[tuple[str, list[tuple[str, list[int]]]]] = [
        ('deployed_2star_3rows',        [('后排-3', [823, 600, 953, 739])]),
        ('deployed_1star_back5_bench9', [('后排-5', [1106, 600, 1241, 739]), ('备战栏-9', [1379, 844, 1493, 980])]),
        ('deployed_1star_back6',        [('后排-6', [1245, 600, 1386, 739])]),
        ('deployed_1star_back24',       [('后排-2', [679, 600, 814, 739]), ('后排-4', [967, 600, 1097, 739])]),
    ]
    ran = False
    for fx, slots in cases:
        if not test_context.has_screen('货币战争-备战', fx):
            continue
        ran = True
        screen = test_context.load_screen('货币战争-备战', fx)
        for label, (x1, y1, x2, y2) in slots:
            assert read_star(screen[y1:y2, x1:x2]) == 1, f'{fx} {label} 应为 1★'
    if not ran:
        _identity_obs_pytest.skip('1★ back/bench fixture 未采')


def test_read_star_all_rows_2star_full(test_context: _identity_obs_SrTestContext) -> None:
    """read_star:deployed_2star_full → 前排/后排/备战栏**三行各覆盖 1★+2★**(各位置广覆盖)。

    单 fixture 同时含三行 × {1,2} 星(ground truth = 实机 analyze extras 双证):前排-3 花火 1★ /
    前排-4 万敌 2★;后排-1 三月七 1★ / 后排-3 椒丘 2★;备战栏 多 1★ + 备战-4 飞霄 2★ + 备战-8 万敌 1★
    (万敌同名异星:2★ 上阵 vs 1★ 备战,证 read_star 看立绘金星非角色身份)。与 ``test_read_star_2star_positions``
    (deployed_2star,各行的**最难单 case**:衣服淹没/thresh/紧贴)互补:本测广覆盖各行多槽位,证 read_star
    对**不同 crop 尺寸**(前排 133×138 / 后排 141×139 / 备战 113×134)的 1★(单星)与 2★(双星)均准。
    """
    if not test_context.has_screen('货币战争-备战', 'deployed_2star_full'):
        _identity_obs_pytest.skip('fixture deployed_2star_full.webp 未采')
    screen = test_context.load_screen('货币战争-备战', 'deployed_2star_full')
    # 前排(crop 133×138):1★ + 2★
    assert read_star(screen[329:467, 969:1097]) == 1, '前排-3 花火 1★'
    assert read_star(screen[329:467, 1109:1241]) == 2, '前排-4 万敌 2★'
    # 后排(crop 141×139):1★ + 2★
    assert read_star(screen[600:739, 534:675]) == 1, '后排-1 三月七 1★'
    assert read_star(screen[600:739, 823:953]) == 2, '后排-3 椒丘 2★'
    # 备战栏(crop 113×134):多 1★ + 2★ + 同名异星对照
    assert read_star(screen[845:979, 382:495]) == 1, '备战-1 艾丝妲 1★'
    assert read_star(screen[844:978, 507:620]) == 1, '备战-2 黑塔 1★'
    assert read_star(screen[844:978, 632:743]) == 1, '备战-3 艾丝妲 1★'
    assert read_star(screen[845:979, 757:869]) == 2, '备战-4 飞霄 2★'
    assert read_star(screen[846:980, 882:995]) == 1, '备战-5 阿格莱雅 1★'
    assert read_star(screen[847:978, 1004:1118]) == 1, '备战-6 赛飞儿 1★'
    assert read_star(screen[846:977, 1132:1244]) == 1, '备战-7 乱破 1★'
    assert read_star(screen[845:979, 1256:1368]) == 1, '备战-8 万敌 1★(同名异星对照,非 2★)'


def test_read_star_bench9_edge_2star(test_context: _identity_obs_SrTestContext) -> None:
    """read_star:deployed_2star_bench9 → 备战-9 飞霄 2★ 读 2(**边槽 circ 边界 case,ADR-0115**)。

    备战-9(最右槽)把飞霄两颗金星之一渲染得偏高 → 该金星 circ 落到 0.34(原 circ>0.35 阈下)被误拒
    → 旧代码读 1(假阴)。``_STAR_CIRC_MIN`` 放宽到 0.25 后读回 2。同 fixture 后排-3 椒丘 / 后排-5 万敌
    亦 2★(对照,非边槽不受影响)。这是「备战每个槽位都要覆盖」发现的边槽回归 —— 锁回归测试。
    """
    if not test_context.has_screen('货币战争-备战', 'deployed_2star_bench9'):
        _identity_obs_pytest.skip('fixture deployed_2star_bench9.webp 未采')
    screen = test_context.load_screen('货币战争-备战', 'deployed_2star_bench9')
    assert read_star(screen[600:739, 823:953]) == 2, '后排-3 椒丘 2★(对照)'
    assert read_star(screen[600:739, 1106:1241]) == 2, '后排-5 万敌 2★(对照)'
    assert read_star(screen[844:980, 1379:1493]) == 2, '备战-9 飞霄 2★(边槽 circ 边界,ADR-0115 解)'


def test_read_star_edge_slots_2star(test_context: _identity_obs_SrTestContext) -> None:
    """read_star:**各排边槽** 2★ 读 2(左右边槽 + 不同角色;用 DragCwChar op 拖到边槽采的 fixture)。

    覆盖 ADR-0115 后的边槽鲁棒性(不同角色 / 不同排的左右边槽):
    - 备战-1(飞霄,最**左**槽)← deployed_2star_bench1(对照 deployed_2star_bench9 最右槽)
    - 前排-1(万敌,左槽)/ 前排-4(万敌,右槽)← deployed_2star_front1 / front4(前排 2★ 边槽)
    每排左右边槽 + 中心(deployed_2star_full)+ 备战-9 bug 槽 → 各排边槽 2★ 全覆盖。
    """
    # 备战-1 左边槽(飞霄 2★)
    if test_context.has_screen('货币战争-备战', 'deployed_2star_bench1'):
        s = test_context.load_screen('货币战争-备战', 'deployed_2star_bench1')
        assert read_star(s[845:979, 382:495]) == 2, '备战-1 飞霄 2★(左边槽)'
    # 前排-1 左槽 + 前排-4 右槽(万敌 2★,跨排 deployed→deployed 拖到)
    if test_context.has_screen('货币战争-备战', 'deployed_2star_front1'):
        s = test_context.load_screen('货币战争-备战', 'deployed_2star_front1')
        assert read_star(s[329:467, 677:810]) == 2, '前排-1 万敌 2★(左槽)'
    if test_context.has_screen('货币战争-备战', 'deployed_2star_front4'):
        s = test_context.load_screen('货币战争-备战', 'deployed_2star_front4')
        assert read_star(s[329:467, 1109:1241]) == 2, '前排-4 万敌 2★(右槽)'
    # 后排-1 左槽(椒丘)/ 后排-6 右槽(椒丘,**边槽第2星 TM 偏低 bug,ADR-0116**)
    if test_context.has_screen('货币战争-备战', 'deployed_2star_back1'):
        s = test_context.load_screen('货币战争-备战', 'deployed_2star_back1')
        assert read_star(s[600:739, 534:675]) == 2, '后排-1 椒丘 2★(左槽)'
    if test_context.has_screen('货币战争-备战', 'deployed_2star_back6'):
        s = test_context.load_screen('货币战争-备战', 'deployed_2star_back6')
        assert read_star(s[600:739, 1245:1386]) == 2, '后排-6 椒丘 2★(右槽,第2星 TM val~0.45-0.50,ADR-0116 thresh 0.45 解)'





# ==================== board_by_row ====================

from sr_od.application.currency_war.kernel.cw_board_by_row import BoardByRow, board_by_row, board_by_row_of
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState


def _char(name: str, slot: int = 0, row: str = 'back',
          char_id: str | None = None, faction: str | None = None) -> BenchChar:
    """直构 BenchChar(char_id/faction 可覆写——开拓者/未识别用例不走注册表)。"""
    return BenchChar(slot=slot, char_id=char_id if char_id is not None else name,
                     faction=faction if faction is not None else '?',
                     position_pref=row)


# ---------- 1. 正例:双排板面聚合与手算对拍 ----------

def test_front_back_split_matches_hand_count():
    """手算板面:三月七/饮月前排,桑博/卡芙卡后排。

    注册表真值(cw_chars):
    - 三月七 = 列车同行 + 护盾(流派);
    - 丹恒·饮月 = 仙舟、列车同行(多羁绊每系都计)+ 战技点;
    - 桑博 = 贝洛伯格、星间旅人 + 持续伤害(流派);
    - 卡芙卡 = 星核猎手 + 持续伤害。
    """
    deployed = [
        _char('三月七', slot=1, row='front'),
        _char('丹恒·饮月', slot=2, row='front'),
        _char('桑博', slot=1, row='back'),
        _char('卡芙卡', slot=2, row='back'),
    ]
    b = board_by_row(deployed)
    assert b.front == {'列车同行': 2, '护盾': 1, '仙舟': 1, '战技点': 1}
    assert b.back == {'贝洛伯格': 1, '星间旅人': 1, '持续伤害': 2, '星核猎手': 1}
    # 全板合计视图 = 两排之和(契约明示的第三视图)
    assert b.total() == {
        '列车同行': 2, '护盾': 1, '仙舟': 1, '战技点': 1,
        '贝洛伯格': 1, '星间旅人': 1, '持续伤害': 2, '星核猎手': 1,
    }


def test_total_is_sum_of_rows_never_loses_count():
    """total 恒等于 front+back 逐标签求和(不丢计数;未知排值计后排)。"""
    deployed = [
        _char('希儿', slot=1, row='front'),
        _char('符玄', slot=1, row='back'),
        _char('桑博', slot=2, row='weird'),   # 异常排值 → 后排(聚合口径)
    ]
    b = board_by_row(deployed)
    for tag in set(b.front) | set(b.back):
        assert b.total()[tag] == b.front.get(tag, 0) + b.back.get(tag, 0)
    assert b.count('量子同频') == 2      # 希儿+符玄(合计视图不分排)
    assert b.count('量子同频', 'front') == 1
    assert b.count('量子同频', 'back') == 1
    assert b.row('front') is b.front


# ---------- 2. 开拓者形态按当前排归一(W21 #13 口径) ----------

def test_trailblazer_form_normalized_by_current_row():
    """欢愉形态拖上前排 → 归一成记忆(欢愉羁绊消失,能量/列车保留);反排同理。

    注册表:开拓者·记忆 = 列车同行 + 能量;开拓者·欢愉 = 列车同行 + 能量、欢愉。
    """
    b = board_by_row([_char('开拓者·欢愉', slot=1, row='front')])
    assert b.front == {'列车同行': 1, '能量': 1}
    assert '欢愉' not in b.total()          # 前排没有欢愉(形态已归一)

    b2 = board_by_row([_char('开拓者·记忆', slot=1, row='back')])
    assert b2.back == {'列车同行': 1, '能量': 1, '欢愉': 1}   # 后台独有欢愉


def test_trailblazer_base_name_normalizes_too():
    """基名「开拓者」(未带形态后缀)同样按排归一。"""
    b = board_by_row([_char('开拓者', slot=1, row='front')])
    assert b.front == {'列车同行': 1, '能量': 1}


# ---------- 3. 未识别角色兜底 / 空板 ----------

def test_unknown_char_falls_back_to_faction_field():
    """char_id 未识别 → 按 BenchChar.faction 计一个标签;空/'?' 不计
    (与 ``_recount_board`` 口径一致)。"""
    b = board_by_row([
        _char('', slot=1, row='front', faction='仙舟'),
        _char('', slot=2, row='back', faction='?'),
        _char('', slot=3, row='back', faction=''),
    ])
    assert b.front == {'仙舟': 1}
    assert b.back == {}


def test_empty_board_gives_empty_aggregate():
    b = board_by_row([])
    assert b.front == {} and b.back == {} and b.total() == {}
    assert board_by_row(None) == BoardByRow()    # None 防御 = 空聚合


def test_board_by_row_of_state_convenience():
    st = GameState()
    st.deployed = [_char('希儿', slot=1, row='front')]
    assert board_by_row_of(st).count('贝洛伯格') == 1
    assert board_by_row_of(st).count('量子同频', 'front') == 1


# ==================== w534_board_center_gate ====================

import sys as _w534_board_center_gate_sys
from pathlib import Path as _w534_board_center_gate_Path

import numpy as _w534_board_center_gate_np
import pytest as _w534_board_center_gate_pytest

_ROOT = _w534_board_center_gate_Path(__file__).resolve().parents[5]          # 仓库根(StarRailOneDragon)
_TEST_ROOT = _w534_board_center_gate_Path(__file__).resolve().parents[4]    # 测试仓根(sr-od-test)
_w534_board_center_gate_sys.path.insert(0, str(_ROOT / 'src'))

from one_dragon.base.geometry.rectangle import Rect as _w534_board_center_gate_Rect  # noqa: E402
from one_dragon.utils import cv2_utils as _w534_board_center_gate_cv2_utils  # noqa: E402
from sr_od.application.currency_war.obs.currency_war_char_id import load_avatar_templates as _w534_board_center_gate_load_avatar_templates
from sr_od.application.currency_war.obs.cw_identity_obs import identify_slots as _w534_board_center_gate_identify_slots

FIXTURES = _TEST_ROOT / 'screens' / '货币战争-备战'
TPL_DIR = _ROOT / 'assets/template/currency_war/portrait_plaza'

# 生产参数(read_deployed_chars 同参)
_PROD = {'min_inliers': 15, 'live_only': True, 'center_gate': True}

# 槽位 rect(1080p,与 screen_info 后排布局档一致;同基准 run_sift 表)
BACK_7 = [(463, 600, 605, 739), (605, 600, 747, 739), (747, 600, 889, 739),
          (889, 600, 1031, 739), (1031, 600, 1173, 739), (1173, 600, 1315, 739),
          (1315, 600, 1457, 739)]
BACK_8 = [(393, 600, 535, 739), (535, 600, 677, 739), (677, 600, 819, 739),
          (818, 600, 960, 739), (960, 600, 1102, 739), (1103, 600, 1245, 739),
          (1245, 600, 1387, 739), (1387, 600, 1529, 739)]
FRONT = [(677, 329, 810, 467), (823, 329, 951, 467),
         (969, 329, 1097, 467), (1109, 329, 1241, 467)]


def _slots(rects):
    return [(i, _w534_board_center_gate_Rect(*r)) for i, r in enumerate(rects, 1)]


@_w534_board_center_gate_pytest.fixture(scope='module')
def templates():
    return _w534_board_center_gate_load_avatar_templates(TPL_DIR)


def _read(name: str):
    for ext in ('.webp', '.png'):
        img = _w534_board_center_gate_cv2_utils.read_image(str(FIXTURES / f'{name}{ext}'))
        if img is not None:
            return img
    raise FileNotFoundError(f'{name}(.webp/.png 均不可读)')


def test_leak_ghost_resolved_by_center_gate(templates):
    """病灶1 锁:渗漏邻卡(花火)按中心归属出局,真身大丽花转正。"""
    frame = _read('后排6槽-P2开局局')
    got = {c.slot: c.char_id for c in _w534_board_center_gate_identify_slots(
        frame, templates, _slots(BACK_7), 'back', **_PROD)}
    assert got.get(1) == '花火' and got.get(2) == '大丽花', got
    assert all(v not in ('花火',) or k == 1 for k, v in got.items()), got


def test_variant_chrome_mask_stops_false_ambiguity(templates):
    """病灶2 锁:那刻夏真命中不再被无掩码变体的卡框内点抬成歧义。"""
    frame = _read('equipped_front1_feixiao_2')
    got = {c.slot: c.char_id for c in _w534_board_center_gate_identify_slots(
        frame, templates, _slots(FRONT), 'front', **_PROD)}
    assert got == {1: '飞霄', 2: '赛飞儿', 3: '那刻夏', 4: '黄泉'}, got


def test_live_only_strong_plaza_main_accepted(templates):
    """病灶3 锁:开拓者·欢愉 plaza 主档强命中(73 内点)过 live_only 门。"""
    frame = _read('后排8槽-全位验证')
    got = {c.slot: c.char_id for c in _w534_board_center_gate_identify_slots(
        frame, templates, _slots(BACK_8), 'back', **_PROD)}
    assert got == {1: '藿藿', 2: '爻光', 6: '开拓者·欢愉',
                   7: '狸小虎', 8: '狸小龙'}, got


def test_pepe_frame_empty_slots_stay_empty(templates):
    """退化 homography 守卫锁:佩佩局(拖测前)空槽 2/4/6 零误检
    (忘归人 21 内点伪假设:19 内点塌缩到单场景点,投影中心蹭进核)。"""
    frame = _read('后排7槽-佩佩局')
    got = {c.slot: c.char_id for c in _w534_board_center_gate_identify_slots(
        frame, templates, _slots(BACK_7), 'back', **_PROD)}
    assert got.get(2) is None and got.get(4) is None and got.get(6) is None, got
    assert got.get(1) == '卡芙卡' and got.get(3) == '万敌' \
        and got.get(5) == '爻光' and got.get(7) == '佩佩', got


def test_variant_mask_file_loaded_per_stem(tmp_path: _w534_board_center_gate_Path) -> None:
    """变体逐文件掩码加载锁:``raw_board.png`` 读 ``mask_board.png``,
    主档 mask 形状失配不影响变体拿到自己的掩码;变体缺专属掩码退 mask.png
    (形状仍须匹配,失配 = 无掩码,同旧语义)。"""
    import cv2

    d = tmp_path / '角色X'
    d.mkdir()
    rng = _w534_board_center_gate_np.random.default_rng(7)
    raw = (rng.random((100, 100, 3)) * 255).astype('uint8')
    cv2.imencode('.png', raw)[1].tofile(str(d / 'raw.png'))
    cv2.imencode('.png', (rng.random((60, 60)) * 255).astype('uint8'))[1] \
        .tofile(str(d / 'mask.png'))                    # 形状失配 → 主档无掩码
    board = (rng.random((40, 40, 3)) * 255).astype('uint8')
    cv2.imencode('.png', board)[1].tofile(str(d / 'raw_board.png'))
    cv2.imencode('.png', _w534_board_center_gate_np.zeros((40, 40), _w534_board_center_gate_np.uint8))[1] \
        .tofile(str(d / 'mask_board.png'))              # 全零掩码 → 变体零关键点

    t = _w534_board_center_gate_load_avatar_templates(tmp_path)
    assert set(t) == {'角色X', '角色X#1'}
    assert len(t['角色X'][1]) > 0, '主档掩码形状失配应按无掩码(全图提特征)'
    assert len(t['角色X#1'][1]) == 0, '变体应读到 mask_board.png(全零 → 零关键点)'


# ==================== test_pivot_plane_filter ====================

import sys as _test_pivot_plane_filter_sys
from pathlib import Path as _test_pivot_plane_filter_Path
from types import SimpleNamespace as _test_pivot_plane_filter_SimpleNamespace

_test_pivot_plane_filter_REPO = _test_pivot_plane_filter_Path(__file__).resolve().parents[4]
_test_pivot_plane_filter_sys.path.insert(0, str(_test_pivot_plane_filter_REPO / 'src'))

from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY, maybe_pivot  # noqa: E402
from sr_od.application.currency_war.kernel.cw_state import GameState as _test_pivot_plane_filter_GameState  # noqa: E402


def test_dot_comp_has_weak_plane_tag() -> None:
    """DOT队 标 P2 乏力(攻略实证)。"""
    dot = next(c for c in COMP_LIBRARY if c.name == 'DOT队')
    assert 2 in dot.weak_planes


def test_pivot_p2_avoids_dot_if_alternative() -> None:
    """P2 保命转型不选当前位面乏力 comp(mock 候选池最小化验证过滤路径)。

    用 monkeypatch select_comp 返回受控候选(DOT队 + 一个非乏力 easy),
    断言 P2 危血时选非乏力那个;P1 时 DOT 仍可选(过滤只按位面)。
    """
    import sr_od.application.currency_war.kernel.cw_comps as cc
    dot = next(c for c in COMP_LIBRARY if c.name == 'DOT队')
    other = next(c for c in COMP_LIBRARY
                 if c.name != 'DOT队' and c.form_difficulty == 'easy'
                 and not c.weak_planes)
    orig = cc.select_comp

    def _fake(state, ctx, config, top_n=None, **kw):
        return [dot, other]

    cc.select_comp = _fake
    try:
        # P2 危血(hp 低):应选 other(非 P2 乏力),不选 DOT
        st2 = _test_pivot_plane_filter_GameState(level=6, plane=2, round_num=1, gold=30, hp=10)
        got = maybe_pivot(st2, None, _test_pivot_plane_filter_SimpleNamespace(), None)
        assert got is None or got.name != 'DOT队', f'P2 保命不应选 P2 乏力 comp,实选 {got and got.name}'
        # P1 危血:DOT 不过滤(P1 是它的强势面,过滤只按当前位面)
        st1 = _test_pivot_plane_filter_GameState(level=6, plane=1, round_num=1, gold=30, hp=10)
        got1 = maybe_pivot(st1, None, _test_pivot_plane_filter_SimpleNamespace(), None)
        # P1 时 DOT(P1强,form 可能更快)允许被选;不 assert 具体,只验证不炸
        assert got1 is None or got1.name in ('DOT队', other.name)
    finally:
        cc.select_comp = orig


# ==================== pivot_invariant ====================

from sr_od.application.currency_war.kernel import cw_comps
from sr_od.application.currency_war.kernel.cw_comps import maybe_pivot as _pivot_invariant_maybe_pivot
from sr_od.application.currency_war.kernel.cw_state import GameState as _pivot_invariant_GameState


class _Sess:
    """假 session:只带 pivot_cooldown_until(守卫读取的唯一字段)。"""

    def __init__(self, cd_until: int = 0):
        self.pivot_cooldown_until = cd_until


class _Ctx:
    def __init__(self, sess):
        self.session = sess


def _state(**kw) -> _pivot_invariant_GameState:
    base = dict(plane=2, round_num=7, hp=20, level=8, gold=30, hp_readable=True)
    base.update(kw)
    return _pivot_invariant_GameState(**base)


def test_cooldown_blocks_crisis_pivot_same_round(monkeypatch):
    """危机信号(信号3)+ 冷却中(同轮已 pivot)→ 必须 None(不变量无例外)。"""
    st = _state(hp=20)   # hp20 < 0.75×阈值 → 危机
    monkeypatch.setattr(cw_comps, 'select_comp', lambda *a, **k: list(cw_comps.COMP_LIBRARY))
    for cd_until in (7, 8, 9):   # 同轮(7)/跨 1-2 轮内:全拦
        ctx = _Ctx(_Sess(cd_until=cd_until))
        assert _pivot_invariant_maybe_pivot(st, ctx, None, None) is None, f'冷却至 r{cd_until} 仍翻转'


def test_cooldown_release_allows_pivot(monkeypatch):
    """冷却过期 → 危机 pivot 放行(守卫不误杀保命通道)。"""
    st = _state(hp=20)
    monkeypatch.setattr(cw_comps, 'select_comp', lambda *a, **k: list(cw_comps.COMP_LIBRARY))
    ctx = _Ctx(_Sess(cd_until=6))   # r7 > 6:冷却过
    piv = _pivot_invariant_maybe_pivot(st, ctx, None, None)
    # 放行(返回某 easy comp)——具体哪个由保命逻辑定,关键是非 None 或有明确保持理由
    # (target=None + 危机 → 应给出落点)
    assert piv is not None
