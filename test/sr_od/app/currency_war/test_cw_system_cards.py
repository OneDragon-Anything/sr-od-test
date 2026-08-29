"""体系卡+组合规则(契约包 C2,步 4 第一批)单帧锁测试。

契约来源:`.debug/temp/currency_war/cw_dev/deep_read/契约包_C1-C7.md` C2 节
+ `p1_definition.md`(体系卡判据/组合规则教义,逐字对齐)。

验收落地(对应 C2「验收测试想法」):
1. 判据穷举锁:四卡正/反例板面(含希儿 OR 分支、仙舟缺藿藿=空壳);
2. tie-break 可审计:同分构造下 ``pick_card_combination`` 返回裁决记录非空;
3. 空窗期:无体系+店有目标件 → 只买目标件;无目标件 → 费用带内购买,
   不为凑数 D;
4. readiness 统一维度(ADR-0311:门槛低=容易被先凑出,不是优先级特权)
   + 行为等价性四项(铁三角胜/仅 DOT 件胜/同 readiness 裁决/空窗不变)。
"""
from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
    _recount_board,
)
from sr_od.application.currency_war.cw_system_cards import (
    _WEIGHT_PIECE,
    _WEIGHT_READINESS,
    SYSTEM_CARDS,
    blank_window_policy,
    card_active,
    card_engine_complete,
    card_pieces,
    card_state_of,
    engine_missing,
    pick_card_combination,
)


def _char(name: str, slot: int = 0, row: str = 'back') -> BenchChar:
    """注册表真值构造 BenchChar(faction/cost 单一源;同 test_cw_action_v2 模式)。"""
    c = CHARACTERS[name]
    return BenchChar(slot=slot, char_id=name,
                     faction=(c.factions or ['?'])[0],
                     position_pref=row)


def _state_with_deployed(names: list[str]) -> GameState:
    """构造 deployed + 同步 board 的单帧(char 身份=注册表真值)。

    ADR-0312(W50):_recount_board 已是**全集口径**(factions+flows+
    independent)——旧「首阵营聚合后手工补多阵营」的补丁循环随之删除
    (保留会双计)。"""
    st = GameState()
    st.deployed = [_char(n, slot=i) for i, n in enumerate(names)]
    st.board = _recount_board(st.deployed)
    return st


def _shop(names_factions: list[tuple[str, str]]) -> list[ShopCard]:
    return [ShopCard(x=i * 100, faction=f, name=n, cost=1)
            for i, (n, f) in enumerate(names_factions)]


# ---------- 1. 判据穷举锁(四卡正/反例) ----------

def test_xianzhou3_active_and_inactive():
    card = SYSTEM_CARDS['xianzhou3']
    # 正例:仙舟 ≥3(铁三角三人组)
    st = _state_with_deployed(['爻光', '藿藿', '丹恒·饮月'])
    assert card_active(card, st) is True
    # 反例:仙舟 2 人(档位未到)
    st2 = _state_with_deployed(['爻光', '藿藿'])
    assert card_active(card, st2) is False


def test_dot2_active_and_inactive():
    card = SYSTEM_CARDS['dot2']
    st = _state_with_deployed(['卡芙卡', '桑博'])
    assert card_active(card, st) is True
    st2 = _state_with_deployed(['卡芙卡'])
    assert card_active(card, st2) is False


def test_train2_active_and_inactive():
    card = SYSTEM_CARDS['train2']
    st = _state_with_deployed(['三月七', '姬子·启行'])
    assert card_active(card, st) is True
    st2 = _state_with_deployed(['三月七'])
    assert card_active(card, st2) is False


def test_seele_or_branch_and_amplifier_not_independent():
    card = SYSTEM_CARDS['seele']
    # 正例A(量子分支):希儿在场 + 量子 ≥2(希儿自身=量子1,符玄=量子2)
    st = _state_with_deployed(['希儿', '符玄'])
    assert card_active(card, st) is True
    # 正例B(贝洛伯格分支):希儿在场 + 贝洛伯格 ≥2(希儿自身=贝1,桑博=贝2)
    st2 = _state_with_deployed(['希儿', '桑博'])
    assert card_active(card, st2) is True
    # 反例:放大器不能独立(无希儿时量子 2 不当过渡;p1_definition 卡4)
    st3 = _state_with_deployed(['符玄', '花火'])
    assert card_active(card, st3) is False
    # 反例:希儿单卡无放大器(量子 1/贝 1 均不足;停云=仙舟,两分支都不沾)
    st5 = _state_with_deployed(['希儿', '停云'])
    assert card_active(card, st5) is False


def test_seele_belly_branch_with_jepard():
    """OR 分支独立验证:希儿+杰帕德(贝洛伯格 2 档,无量子)。"""
    card = SYSTEM_CARDS['seele']
    st = _state_with_deployed(['希儿', '杰帕德'])
    assert card_active(card, st) is True


# ---------- 2. 引擎完备度(铁三角不可拆/缺一=空壳) ----------

def test_engine_complete_xianzhou_trio_undividable():
    card = SYSTEM_CARDS['xianzhou3']
    trio = {'爻光', '藿藿', '丹恒·饮月'}
    assert card_engine_complete(card, trio) is True
    # 缺藿藿 = 空壳(功能链:饮月输出/爻光叠段/藿藿保血,各占一环不可拆)
    missing_one = trio - {'藿藿'}
    assert card_engine_complete(card, missing_one) is False
    assert engine_missing(card, missing_one) == ['藿藿']


def test_engine_complete_no_engine_cards_always_ok():
    for cid in ('dot2', 'train2'):
        assert SYSTEM_CARDS[cid].engine_required == []
        assert card_engine_complete(SYSTEM_CARDS[cid], set()) is True


def test_engine_required_and_star_goal_registry():
    """注册表教义锁:铁三角名单/星级目标(铁三角 2★、希儿 3★、其余不追)。"""
    xz = SYSTEM_CARDS['xianzhou3']
    assert set(xz.engine_required) == {'爻光', '藿藿', '丹恒·饮月'}
    assert xz.star_goal == {'爻光': 2, '藿藿': 2, '丹恒·饮月': 2}
    assert SYSTEM_CARDS['dot2'].star_goal == {}
    assert SYSTEM_CARDS['train2'].star_goal == {}
    assert SYSTEM_CARDS['seele'].star_goal == {'希儿': 3}
    assert SYSTEM_CARDS['seele'].engine_required == ['希儿']


# ---------- 3. 组合选择(来牌主判据/readiness 统一维度/意向/词条/等价性四项) ----------

def test_pick_dot2_wins_by_score_when_only_dot_pieces():
    """等价性②:仅 2 张 DOT 件在手 → DOT2 胜(原来靠首站加成,现在靠分;
    readiness=2/2 满格,其余系 0)。"""
    st = GameState()
    st.bench = [_char('卡芙卡'), _char('桑博')]
    st.board = {}
    dec = pick_card_combination(st)
    assert dec.blank_window is False
    assert dec.chosen[0] == 'dot2'
    assert dec.scores['dot2'] == (2 * _WEIGHT_PIECE + 1.0 * _WEIGHT_READINESS)
    assert not any('首站' in r for r in dec.ruling)   # 特权措辞已删


def test_equiv_trio_full_hand_beats_dot():
    """等价性①:铁三角全在手+DOT2 可达 → 仙舟3 仍胜
    (原来靠例外条款直取,现在靠分:pieces 3>2 且 readiness 双满格)。"""
    st = GameState()
    st.bench = [_char('卡芙卡'), _char('桑博')]   # DOT 也可达,制造竞争
    st.deployed = [_char('爻光', slot=0, row='back'),
                   _char('藿藿', slot=1, row='back'),
                   _char('丹恒·饮月', slot=2, row='back')]
    st.board = _recount_board(st.deployed)
    dec = pick_card_combination(st)
    assert dec.chosen[0] == 'xianzhou3'
    assert dec.scores['xianzhou3'] > dec.scores['dot2']
    assert not any('例外' in r or '一轮成型' in r for r in dec.ruling)   # 例外条款已删


def test_equiv_same_readiness_no_dot_privilege():
    """等价性③(按裁定改变):2 列车件 vs 2 DOT 件(同 pieces 同 readiness)→
    来牌/词条/意向裁决,不再有 DOT 特权(旧 +1 首站加成下意向翻不过)。"""
    st = GameState()
    st.bench = [_char('三月七'), _char('姬子·启行'), _char('卡芙卡'), _char('桑博')]
    dec = pick_card_combination(st)
    assert dec.scores['train2'] == dec.scores['dot2']
    assert any('tie-break' in r for r in dec.ruling)   # 同分如实记录可审计
    # 意向同向裁决:列车意向 → train2 胜(旧特权语义下 DOT 恒胜,此为行为变化)
    dec_intent = pick_card_combination(st, intent='姬子列车')
    assert dec_intent.chosen[0] == 'train2'
    # 词条裁决:敌方频动旺 → DOT 权重升 → dot2 胜
    dec_affix = pick_card_combination(st, affixes=['忍无可忍'])
    assert dec_affix.chosen[0] == 'dot2'


def test_readiness_unified_across_cards():
    """readiness 统一维度:全卡按 pieces/激活件数折算(仙舟3=3、DOT2/列车2=2、
    希儿系≈3),门槛低=分高,无任何卡专属 if。"""
    # 2 仙舟件(readiness 2/3)vs 1 列车件(readiness 1/2):
    # pieces 2>1 主判据胜;readiness 0.667>0.5 同向
    st = GameState()
    st.bench = [_char('爻光'), _char('藿藿'), _char('三月七')]
    dec = pick_card_combination(st)
    assert dec.chosen[0] == 'xianzhou3'
    assert dec.scores['xianzhou3'] == (2 * _WEIGHT_PIECE + 2 / 3 * _WEIGHT_READINESS)


def test_pick_arrival_is_primary_signal():
    """来牌主判据:无词条无意向时,件数多的体系胜出。"""
    st = GameState()
    st.bench = [_char('三月七'), _char('姬子·启行'), _char('卡芙卡')]
    dec = pick_card_combination(st)
    assert dec.chosen[0] == 'train2'   # 列车 2 件 > DOT 1 件


def test_pick_tie_break_ruling_nonempty_and_intent_breaks_tie():
    """同分构造:裁决记录非空;意向同向 tie-break 定向(非一票否决)。"""
    st = GameState()
    st.bench = [_char('三月七'), _char('桑博')]   # 列车 1 件 vs DOT 1 件 = 同分
    dec = pick_card_combination(st)
    assert dec.scores['train2'] == dec.scores['dot2']
    assert dec.ruling, '同分构造下裁决记录必须非空(C2 冻结要求)'
    assert any('tie-break' in r for r in dec.ruling)
    # 意向同向(希儿量子家族→seele 的映射没有;用 DOT 家族验证):
    dec2 = pick_card_combination(st, intent='DOT卡芙卡')
    assert dec2.chosen[0] == 'dot2'
    # 意向非同向 = 不否决(列车仍可因来牌胜出/或 DOT 因意向翻越——只锁非崩溃+有记录)
    dec3 = pick_card_combination(st, intent='希儿量子')
    assert any('非同向' in r for r in dec3.ruling)


def test_pick_affix_input_adjusts_dot():
    """词条前置输入:敌方频动旺(忍无可忍)→ DOT 权重升;净化身心 → DOT 权重降。"""
    st = GameState()
    st.bench = [_char('三月七'), _char('桑博')]   # 平分底
    dec_like = pick_card_combination(st, affixes=['忍无可忍'])
    assert dec_like.chosen[0] == 'dot2'
    dec_fear = pick_card_combination(st, affixes=['净化身心'])
    assert dec_fear.chosen[0] == 'train2'
    assert any('词条输入' in r for r in dec_fear.ruling)


def test_pick_seele_affix_fear_counter():
    """希儿系怕量子熄火(counter 警惕):3 件的领先被 fear(-3.0) 抵成落后。"""
    st = GameState()
    st.bench = [_char('希儿'), _char('符玄')]   # seele 件数 2(希儿引擎+符玄放大器,去重)
    dec = pick_card_combination(st, affixes=['量子熄火'])
    assert SYSTEM_CARDS['seele'].affix_fears == ['量子熄火']
    assert card_pieces(SYSTEM_CARDS['seele'], st) == 2
    assert dec.scores['seele'] == (2 * _WEIGHT_PIECE + 2 / 3 * _WEIGHT_READINESS - 3.0)
    #   # 2 件(readiness 2/3)+ fear -3.0 = -0.33(counter 压制)


def test_pick_blank_when_nothing_arrived():
    """等价性④:空窗行为不变——四系 0 件(readiness 恒 0)→ blank_window=True,chosen=[]。"""
    st = GameState()
    # 灵砂=狼狩+治疗,不沾四系任一判据阵营(瓦尔特含列车同行,不可用)
    st.bench = [_char('灵砂')]
    dec = pick_card_combination(st)
    assert dec.blank_window is True
    assert dec.chosen == []
    assert any('空窗' in r for r in dec.ruling)


def test_card_state_of_pieces_and_flags():
    st = _state_with_deployed(['爻光', '藿藿'])
    cs = card_state_of(SYSTEM_CARDS['xianzhou3'], st)
    assert cs.pieces == 2
    assert cs.active is False          # 仙舟 2 < 3
    assert cs.engine_complete is False  # 缺饮月
    cs_dot = card_state_of(SYSTEM_CARDS['dot2'], st)
    assert cs_dot.engine_complete is True   # 无引擎卡恒 OK


# ---------- 4. 空窗期规则(目标件/费用带/不 D 牌) ----------

def test_blank_window_buy_target_only():
    """无体系+店有目标件 → 只买目标件;off-target 不进 buy_idx([31] 不为凑数 D)。"""
    st = GameState()
    st.bench = [_char('桑博')]   # 来牌方向=持续伤害(1 件)
    st.shop = _shop([('藿藿', '仙舟'),      # 引擎件(铁三角)→ 买
                     ('卡芙卡', '持续伤害'),  # 来牌方向件 → 买
                     ('停云', '仙舟'),        # 仙舟无来牌方向但停云=仙舟阵营……
                     ('瓦尔特', '星核猎手')])
    dec = blank_window_policy(st)
    assert dec.is_blank is True
    assert dec.target_factions == ['持续伤害']
    assert '藿藿' in dec.target_char_ids and '希儿' in dec.target_char_ids
    assert 0 in dec.buy_idx and 1 in dec.buy_idx
    assert 3 not in dec.buy_idx          # off-target(星核猎手)绝不 D
    # 槽2 停云:阵营=仙舟 ∉ target_factions → 不买(仙舟无来牌迹象)
    assert 2 not in dec.buy_idx


def test_blank_window_cost_band_and_no_direction():
    """无来牌方向:仅引擎件见即买;费用带=引擎件费用众数(铁三角 1,1,2 + 希儿 3 → 1)。"""
    st = GameState()
    st.shop = _shop([('瓦尔特', '星核猎手')])
    dec = blank_window_policy(st)
    assert dec.is_blank is True
    assert dec.target_factions == []
    assert dec.buy_idx == []            # 无目标件 → 不买(off-target 不 D)
    assert dec.cost_band == 1
    assert any('不为凑数' in r for r in dec.ruling)


def test_blank_window_not_blank_when_any_system_active():
    st = _state_with_deployed(['卡芙卡', '桑博'])   # DOT2 已激活
    dec = blank_window_policy(st)
    assert dec.is_blank is False
    assert dec.buy_idx == []
