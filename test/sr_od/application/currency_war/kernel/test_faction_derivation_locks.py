"""faction 三类注册表派生口径测试(benchchar-retirement design §2.1)
+ 线知识卡三字段测试(line_and_upgrade §1.2/§1.4/§1.5)
+ 开拓者形态归一上报测试(§3 不变量 5 哨兵)。

faction/position_pref 不入容器形状,消费点经注册表按 char_id 派生,三类
消费口径(§2.1):
- 类2 板面阵营计数/体系卡身份:注册表派生,未知名 = '?'(不计);
- 类3 羁绊(按排聚合 board_by_row):行归属 + 注册表派生,开拓者形态归一
  随迁(前排=记忆/后排=欢愉,design §3 不变量 5 的计数侧承载体)。

测试面:
① board_by_row 容器行输入:排归属 = 行入参(前排/后排分桶),多羁绊角色
   每系都计,total = 两行之和;
② 开拓者形态按排归一(防御性再归一):前排槽携带后台形态 id 时按前排
   形态取羁绊(欢愉不计),后排照旧;上报侧(swap/deploy_move)同源
   归一核,换排即切换前台记忆/后台欢愉形态(char_id/faction 同步);
③ 未知名/注册表无羁绊名 = 零标签(未知 '?' 不计);
④ 类2 体系卡 _faction_count:身份计数(board_by_row)与 board OCR 兜底
   取 max;未知名不进身份计数;
⑤ char_first_faction 派生式(主阵营单一源):命中 → factions[0],
   注册但无阵营 = '',未注册/空名 = '?'。

知识卡节(统一阵容评分迭代重写,2026-11-03):①schema 全 20 线
need_star/key_items 非空;②名字空间 ⊆ 注册表键(手编建表笔误防线
——写错名 = 分值静默失效);③ CARRY 锚派生(plaza_carry 直用 +
攻略补全登记)与 CARRY 档 = 单名锚 ∪ core_chars 合流;④旧
lock_rules 字段/char_lock_hit/strategy_lock_hit 已随「全部即时锁退役」
整字段退役——替代机制断言 = 投资通道派生(OCR 间隔号形变归一在
cw_invest_channels 查询口承载)。
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import cw4_bview

from sr_od.application.currency_war.data.cw_chars import (
    CHARACTERS,
    char_first_faction,
)
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_move_unit_param,
)
from sr_od.application.currency_war.kernel.cw_board_by_row import (
    board_by_row,
    board_by_row_of,
)
from sr_od.application.currency_war.kernel.cw_comps import (
    CARRY_ANCHOR_FALLBACK,
    COMP_LIBRARY,
    carry_anchor,
    carry_set,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    ChannelSig,
    GameState,
    Unit,
    deployed_rows_of,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionMoveUnitParam,
)


def _unit(cid: str, slot: int, star: int = 1) -> Unit:
    return Unit(char_id=cid, star=star, equips=[])


def _gs(front: list[Unit] | None = None,
        back: list[Unit] | None = None,
        board: dict[str, int] | None = None) -> GameState:
    from sr_od.application.currency_war.kernel.cw_game_state import ChannelSig
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _sig = ChannelSig(family='obs', actor='CwScreenPrep')
    if front is not None or back is not None:
        gs.observe(gs.deployed, _dvs(list(front or []),
                                     list(back or [])), sig=_sig)
    if board is not None:
        gs.observe(gs.board, dict(board), sig=_sig)
    return gs


# ===== ① 行域输入:排归属 + 多羁绊计数 + 合计 =====

def test_board_by_row_rows_bucket_and_multibond_count():
    """前排/后排分桶按行入参;多羁绊角色(桑博=贝洛伯格+星间旅人+持续伤害)
    每系都计;total = 两行之和。"""
    bb = board_by_row([_unit('桑博', 1), _unit('希儿', 2)],
                      [_unit('三月七', 1)])
    assert bb.front == {'贝洛伯格': 2, '星间旅人': 1, '持续伤害': 1,
                        '量子同频': 1}, '前排逐系计数(希儿=贝洛伯格+量子同频)'
    assert bb.back == {'列车同行': 1, '护盾': 1}, '后排逐系计数'
    assert bb.total() == {'贝洛伯格': 2, '星间旅人': 1, '持续伤害': 1,
                          '量子同频': 1, '列车同行': 1, '护盾': 1}
    assert bb.count('列车同行') == 1 and bb.count('列车同行', 'back') == 1 \
        and bb.count('列车同行', 'front') == 0


# ===== ② 开拓者形态按排归一(计数侧) =====

def test_board_by_row_trailblazer_row_normalization():
    """开拓者形态归一随迁(design §3 不变量 5 计数侧):前排槽携带后台
    形态 id(欢愉)→ 按前排形态(记忆)取羁绊——列车同行计入、欢愉不计;
    后排槽携带后台形态照旧计欢愉。"""
    bb = board_by_row([_unit('开拓者·欢愉', 1)],   # 直构未归一态(防御域)
                      [_unit('开拓者·欢愉', 1)])
    assert bb.front == {'列车同行': 1, '能量': 1}, \
        '前排按记忆形态取羁绊(欢愉不计)'
    assert bb.back == {'列车同行': 1, '能量': 1, '欢愉': 1}, \
        '后排按欢愉形态取羁绊'


# ===== ③ 未知名/无羁绊名 = 零标签 =====

def test_board_by_row_unknown_and_bondless_names_not_counted():
    """未注册名(='?' 口径)与注册表无阵营无流派名(白厄,独立羁绊不进
    板面阵营计数)都不产生标签;空行 = 空聚合。"""
    bb = board_by_row([_unit('无名氏', 1), _unit('白厄', 2), _unit('', 3)],
                      [])
    assert bb.front == {} and bb.back == {} and bb.total() == {}


# ===== ④ 类2:体系卡 _faction_count(身份 × board OCR 取 max)=====

def test_system_card_faction_count_identity_and_board_max():
    """身份计数 = board_by_row 全板合计(注册表派生);board OCR 缺漏时
    身份侧兜判,身份缺漏时 OCR 侧兜判(取 max 容错,判激活侧)。"""
    from sr_od.application.currency_war.kernel.cw_system_cards import (
        SYSTEM_CARDS,
        card_active,
    )
    # 身份侧 2 列车(board OCR 未写)→ train2 激活(身份兜判)
    gs = _gs(front=[], back=[_unit('三月七', 1), _unit('姬子', 2)])
    assert card_active(SYSTEM_CARDS['train2'], gs), \
        '身份计数 2/2 → 列车卡激活'
    # 未知名不进身份计数:1 真列车 + 1 未知名 → 未激活
    gs2 = _gs(front=[], back=[_unit('三月七', 1), _unit('无名氏', 2)])
    assert not card_active(SYSTEM_CARDS['train2'], gs2), \
        '未知名(? 口径)不进身份计数'
    # OCR 侧兜判:板面 OCR 报 2 而身份侧 1(重建缺身份)→ 仍激活(max 容错)
    gs3 = _gs(front=[], back=[_unit('三月七', 1)], board={'列车同行': 2})
    assert card_active(SYSTEM_CARDS['train2'], gs3), \
        'board OCR 兜判取 max(漏判激活比多判更伤)'


# ===== ⑤ 主阵营派生式(§2.1 单一源)=====

def test_char_first_faction_derivation():
    """主阵营派生:命中 → factions[0];注册但无阵营登记 = '';未注册/
    空名 = '?'(与退役换形层派生式逐位同值)。"""
    assert char_first_faction('三月七') == '列车同行'
    assert char_first_faction('白厄') == ''
    assert char_first_faction('无名氏') == '?'
    assert char_first_faction('') == '?'


# ===== 便捷入口:容器直读聚合 =====

def test_board_by_row_of_reads_container_rows():
    """board_by_row_of(gs) = deployed_rows_of 现读 + 聚合(便捷入口同口径)。"""
    gs = _gs(front=[_unit('希儿', 1)], back=[_unit('桑博', 1)],
             board={'贝洛伯格': 99})   # board 字段不进行域(行域现读)
    bb = board_by_row_of(gs)
    assert bb.front == {'量子同频': 1, '贝洛伯格': 1}
    assert bb.back == {'贝洛伯格': 1, '星间旅人': 1, '持续伤害': 1}
    assert bb.count('贝洛伯格') == 2


# ============================================================ 线知识卡三字段


def test_knowledge_card_schema_nonempty_all_lines():
    """① 知识卡字段全 20 线非空(need_star 星级目标/key_items 骨架名单
    ——持有证据分与星级目标的机器前提);旧 lock_rules 字段已整字段退役
    (统一阵容评分迭代:全部即时锁退役),不再断言。"""
    assert len(COMP_LIBRARY) == 20
    for comp in COMP_LIBRARY:
        assert not hasattr(comp, 'lock_rules'), \
            f'{comp.name}: lock_rules 字段已整字段退役,禁复活'
        assert comp.need_star, comp.name
        assert comp.key_items, comp.name


def test_knowledge_card_names_in_registries():
    """② 名单/键全落注册表键空间:角色名 ⊆ CHARACTERS。建表是手编数据,
    名字写错 = 证据分/星级目标静默失效。"""
    for comp in COMP_LIBRARY:
        for name in (*comp.need_star, *comp.key_items):
            assert name in CHARACTERS, (comp.name, name)


def test_carry_anchor_plaza_first_fallback_registered():
    """③ 锚派生口径(§1.2):plaza_carry 非空直用;空值线恰为攻略补全登记的
    3 线(银枝/飞霄/桑博,依据 = CARRY_ANCHOR_FALLBACK 就地注释)。"""
    for comp in COMP_LIBRARY:
        anchor = carry_anchor(comp)
        assert anchor, comp.name
        if comp.plaza_carry:
            assert anchor == comp.plaza_carry, comp.name
    assert set(CARRY_ANCHOR_FALLBACK) == {
        c.name for c in COMP_LIBRARY if not c.plaza_carry}
    assert (CARRY_ANCHOR_FALLBACK['银枝群攻'] == '银枝'
            and CARRY_ANCHOR_FALLBACK['追击飞霄'] == '飞霄'
            and CARRY_ANCHOR_FALLBACK['专家桑博DOT'] == '桑博')


def test_carry_set_union_anchor_and_core():
    """③' CARRY 档 = 单名锚 ∪ core_chars 合流(§1.2「plaza_carry ∪ core_chars
    合流」的派生落地;3.7 持有证据按「持有任一档内成员计 CARRY 档」消费)——
    core 全员进档(单名锚窄化会把 core 成员错档到骨架/插件档)。"""
    for comp in COMP_LIBRARY:
        cs = carry_set(comp)
        assert cs, comp.name
        assert set(comp.core_chars) <= cs, comp.name
        assert carry_anchor(comp) in cs, comp.name


def test_lock_rule_machinery_retired_replaced_by_channels():
    """④ 旧锁定机器退役断言(统一阵容评分迭代):lock_rules 字段/
    char_lock_hit/strategy_lock_hit 符号不存在于 kernel——替代 = 投资通道
    派生(策略到手的线关联,`cw_invest_channels.strategy_line_bonus`),
    OCR 间隔号形变归一在通道派生查询口承载(旧 strategy_lock_hit 防线
    同型:形变名经 normalize_invest_name 照常命中)。"""
    import sr_od.application.currency_war.kernel.cw_comps as cw_comps
    assert not hasattr(cw_comps, 'char_lock_hit')
    assert not hasattr(cw_comps, 'strategy_lock_hit')
    assert not hasattr(cw_comps, 'ENV_COMP_AFFINITY')
    assert not hasattr(cw_comps, 'AUGMENT_COMP_AFFINITY')
    assert not hasattr(cw_comps, 'augment_affinity')
    # 替代机制正面锚:旧策略型登记语义(飞光→景元仙舟/黑塔纪元→大黑塔)
    # 由定义卡通道承载;OCR 形变(•→·)归一命中。
    from sr_od.application.currency_war.kernel.cw_comps import get_comp
    from sr_od.application.currency_war.kernel.cw_invest_channels import (
        strategy_line_bonus,
    )
    jing = get_comp('景元仙舟')
    assert strategy_line_bonus('飞光·映月', jing) \
        == strategy_line_bonus('飞光•映月', jing) == 500
    assert strategy_line_bonus('黑塔纪元', get_comp('大黑塔银河学者')) == 500


# ============================================================ 开拓者形态归一(上报侧)
# (换排形态归一归一口唯一:swap 上报与 deploy_move 上报均经同源归一核
#  cw_exec_state.trailblazer_row_identity → trailblazer_row_unit,换排即
#  切换前台记忆/后台欢愉形态;计数侧同构测试 = 本文件
#  test_board_by_row_trailblazer_row_normalization。)

_ST_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')
_ST_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')


def _gs_with_bench_trailblazer(deployed_taken: bool):
    """bench 0 号槽 = 后台形态开拓者;deployed_taken=True 时
    场上前排 1 号 = 普通角色『甲』(swap 场景需要在场交换对象)。"""
    gs = game_state_of(None)
    slots: list[BenchSlot | None] = [None] * 9
    slots[0] = BenchSlot(kind='unit', unit=Unit(char_id='开拓者·欢愉',
                                                star=4))
    gs.observe(gs.bench, cw4_bview(slots),
               evidence='t', sig=_ST_SIG_OBS)
    gs.observe(gs.deployed, _dvs([Unit(char_id='甲', star=1, equips=[])]
               if deployed_taken else [], []),
               evidence='t', sig=_ST_SIG_OBS)
    return gs


def test_move_unit_report_normalizes_trailblazer_form_to_target_row() -> None:
    """``move_unit`` 统一拖动上报有归一(benchchar-retirement P3 缺陷修复
    申报面,design §3 不变量 5;旧 swap/deploy_move 两上报同源归一,随
    戊批收编并入 move_unit):开拓者拖上场 → 排变、形态(char_id)
    同步切目标排;占槽目标 = 交换形态下归一同源。"""
    # 空槽直落形态
    gs = _gs_with_bench_trailblazer(deployed_taken=False)
    out = report_action_move_unit_param(
        gs, CwActionMoveUnitParam(src_domain='bench', src_slot=0,
                                  dst_domain='front', dst_slot=1),
        sig=_ST_SIG)
    assert out.applied, f'部署应成功,实得 {out.reason!r}'
    front, _ = deployed_rows_of(gs)
    assert front and front[0].char_id == '开拓者·记忆', \
        f'换到前排 → 记忆形态(空槽直落),实得 {front[0].char_id!r}'
    # 占槽交换形态(交换对象回 bench 源槽,归一同源)
    gs2 = _gs_with_bench_trailblazer(deployed_taken=True)
    out2 = report_action_move_unit_param(
        gs2, CwActionMoveUnitParam(src_domain='bench', src_slot=0,
                                   dst_domain='front', dst_slot=1),
        sig=_ST_SIG)
    assert out2.applied, f'交换应成功,实得 {out2.reason!r}'
    front2, _ = deployed_rows_of(gs2)
    assert front2 and front2[0].char_id == '开拓者·记忆', \
        f'换到前排 → 记忆形态(占槽交换),实得 {front2[0].char_id!r}'
    # 排归属 = 容器行域承载(前排行成员)

