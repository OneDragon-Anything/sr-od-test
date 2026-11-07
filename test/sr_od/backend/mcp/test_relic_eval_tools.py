"""relic_eval_tools.evaluate 规则 1-10 全覆盖单测（fixture 场景制）。

出处：docs/develop/sr_od/backend/changes/relic-substat-eval/design.md
§2.2（出参 schema）/§2.3（计算规则 1-10）/§2.4（归一表与口径包表）；
landing.md 3.1 判据八类场景（别名归一/口径包展开/穿错主词条/阈值达标与
差线/浪费分布与最弱件/verdict 各分支/not_found/结构防御与重复名与空
criteria error）。零副作用纯函数测试，零真实 IO。

fixture 字段形态对照真实名册映射产物：词条 name_cn/value/times 与
``SrPropertyEntry`` 一致（value 为字符串，百分比带 %、平坦值不带；
出处 = sr-od-test/test/fixtures/mys/hkrpg_avatar_info_detail_sample.json
经 sr_mys_client 映射的断言样例——「生命值」'3.4%' 与 '42' 同名两种
形态、「攻击力」'43.2%' 与 '352' 同名两种形态，% 后缀是 flat/% 唯一
判别依据）。词条数值为自造样例。
"""

import pytest

from sr_od.backend.mcp.relic_eval_tools import (
    ROSTER_STRUCTURE_ERROR_MESSAGE,
    evaluate,
)


def _sub(name: str, value: str, times: int) -> dict:
    """副词条 fixture（SrPropertyEntry asdict 形态）。"""
    return {'name_cn': name, 'value': value, 'times': times}


def _piece(
    set_name: str,
    pos_cn: str,
    main: tuple[str, str],
    subs: list[dict],
) -> dict:
    """遗器/饰品单件 fixture（SrRelic asdict 形态，主词条 times 恒 0）。"""
    return {
        'name': f'{set_name}的{pos_cn}件',
        'pos': {'头部': 1, '手部': 2, '躯干': 3, '脚部': 4, '位面球': 5, '连结绳': 6}[pos_cn],
        'pos_cn': pos_cn,
        'rarity': 5,
        'level': 15,
        'main': {'name_cn': main[0], 'value': main[1], 'times': 0},
        'subs': subs,
        'set_name': set_name,
    }


def _roster_character(name: str, pieces: list[dict]) -> dict:
    """CharacterDetail asdict 形态 fixture（本工具只读 name/relics/ornaments）。"""
    return {
        'id': 1001, 'name': name, 'level': 80, 'rarity': 5, 'rank': 0,
        'element': 'lightning', 'element_cn': '雷', 'base_type': 5, 'base_type_cn': '虚无',
        'equip': None,
        'relics': [p for p in pieces if p['pos'] <= 4],
        'ornaments': [p for p in pieces if p['pos'] >= 5],
        'ranks': [], 'skills': [], 'properties': [], 'set_effects': [],
    }


def _ok_roster(*characters: dict) -> list[dict]:
    """结构合法的最小名册（供 error 分支测试用）。"""
    return list(characters)


def test_alias_normalization_and_minimal_verdict() -> None:
    """规则 1/2/4/7/8：别名归一（大攻击→攻击力提高、暴击→暴击率）+ 命中
    计数按强化次数 + 最小 verdict 模板（无主核对/无阈值短句省略）。

    锁：有效集合外的平坦攻击力计入浪费分布；verdict 逐字等于
    「命中 X/Y（Z%）最弱件：S（浪费 N 条）」。"""
    roster = _ok_roster(_roster_character('卡芙卡', [
        _piece('野穗伴行的快枪手', '头部', ('生命值', '705'), [
            _sub('暴击率', '5.5%', 2),
            _sub('攻击力', '21', 1),
        ]),
    ]))
    criteria = [{'character_name': '卡芙卡', 'effective_substats': ['大攻击', '暴击']}]

    envelope = evaluate(roster, criteria)

    assert envelope['status'] == 'success'
    result = envelope['data']['results']['卡芙卡']
    assert result['effective_hits'] == 2
    assert result['total_rolls'] == 3
    assert result['hits_by_stat'] == {'暴击率': {'rolls': 2, 'value_sum': 5.5}}
    assert result['wasted_rolls_by_stat'] == {'攻击力': 1}
    assert result['verdict'] == '命中 2/3（67%）最弱件：头部（浪费 1 条）'


def test_stat_pack_expansion() -> None:
    """规则 1/3/4：口径包「双暴攻」展开为三个标准名；主词条不进命中/
    总次数（规则 3/4 遍历域只数副词条）；包外词条计浪费。"""
    roster = _ok_roster(_roster_character('黄泉', [
        _piece('死水深潜的先驱', '躯干', ('攻击力', '43.2%'), [
            _sub('暴击伤害', '22.0%', 3),
            _sub('生命值', '8.1%', 1),
        ]),
    ]))
    criteria = [{'character_name': '黄泉', 'effective_substats': ['双暴攻']}]

    envelope = evaluate(roster, criteria)

    result = envelope['data']['results']['黄泉']
    assert result['total_rolls'] == 4  # 主词条（攻击力 43.2%）不计入总次数
    assert result['effective_hits'] == 3
    assert result['hits_by_stat'] == {'暴击伤害': {'rolls': 3, 'value_sum': 22.0}}
    assert result['wasted_rolls_by_stat'] == {'生命值提高': 1}


def test_flat_percent_homonym_no_mixing() -> None:
    """规则 2/6：同名异义词条（name_cn 同为「生命值」）按 value 的 % 后缀
    消歧，flat 与百分比不混桶；平坦毕业线求和只累计平坦主+副词条。

    锁：有效口径「大生命」只命中 % 词条；「生命值」平坦线的 current
    = 头部主词条 705 + 平坦副词条 42 = 747（% 词条的 3.4 不混入）。"""
    roster = _ok_roster(_roster_character('刃', [
        _piece('宝命长存的莳者', '头部', ('生命值', '705'), [_sub('生命值', '3.4%', 2)]),
        _piece('宝命长存的莳者', '手部', ('攻击力', '352'), [_sub('生命值', '42', 3)]),
    ]))
    criteria = [{
        'character_name': '刃',
        'effective_substats': ['大生命'],
        'stat_thresholds': {'生命值': 700},
    }]

    envelope = evaluate(roster, criteria)

    result = envelope['data']['results']['刃']
    assert result['effective_hits'] == 2
    assert result['hits_by_stat'] == {'生命值提高': {'rolls': 2, 'value_sum': 3.4}}
    assert result['wasted_rolls_by_stat'] == {'生命值': 3}
    assert result['threshold_report'] == [
        {'stat': '生命值', 'current': 747.0, 'line': 700, 'gap_text': '达标 +47.0'}
    ]
    assert result['verdict'] == '命中 2/5（40%）达标 1 项、差线 0 项；最弱件：手部（浪费 3 条）'


def test_unrecognized_words_reported_as_warnings() -> None:
    """规则 1：口径词与名册词条名都归不上 → warnings 各追加一条、按无效
    处理，不静默当标准名；未识别词条名无标准名可键，不计入浪费分布。"""
    roster = _ok_roster(_roster_character('黑天鹅', [
        _piece('幽锁深牢的系囚', '头部', ('生命值', '705'), [
            _sub('暴击率', '5.5%', 2),
            _sub('神秘词条', '9.9%', 1),
        ]),
    ]))
    criteria = [{'character_name': '黑天鹅', 'effective_substats': ['双暴', '不存在的词条']}]

    envelope = evaluate(roster, criteria)

    result = envelope['data']['results']['黑天鹅']
    assert any('不存在的词条' in w for w in result['warnings'])
    assert any('神秘词条' in w for w in result['warnings'])
    assert result['total_rolls'] == 3  # 未识别词条的次数仍计入总数
    assert result['effective_hits'] == 2
    assert result['wasted_rolls_by_stat'] == {}  # 无标准名可键，不污染分布


def test_value_parse_failure_counts_zero() -> None:
    """规则 2：数值解析失败 → warnings 追加、按 0 计，命中次数照常累计。"""
    roster = _ok_roster(_roster_character('缇宝', [
        _piece('哀歌覆国的诗人', '头部', ('生命值', '705'), [_sub('暴击率', 'abc', 2)]),
    ]))
    criteria = [{'character_name': '缇宝', 'effective_substats': ['暴击']}]

    envelope = evaluate(roster, criteria)

    result = envelope['data']['results']['缇宝']
    assert result['effective_hits'] == 2
    assert result['hits_by_stat'] == {'暴击率': {'rolls': 2, 'value_sum': 0.0}}
    assert any('解析失败' in w for w in result['warnings'])


def test_main_stat_check_slots_and_missing_piece() -> None:
    """规则 5：核对只对躯干/脚部/位面球/连结绳执行（头部期望跳过并告警）；
    缺件部位 actual=null 记穿错；分母 = 传入期望的部位数。

    锁：期望含「暴击」（别名）归一为标准名比对；穿错计数=2。"""
    roster = _ok_roster(_roster_character('丹恒•腾荒', [
        _piece('重循苦旅的司铎', '头部', ('生命值', '705'), []),
        _piece('重循苦旅的司铎', '手部', ('攻击力', '352'), []),
        _piece('死水深潜的先驱', '躯干', ('暴击伤害', '64.8%'), []),
        _piece('死水深潜的先驱', '脚部', ('速度', '128.4'), [_sub('速度', '5.6', 2)]),
    ]))
    criteria = [{
        'character_name': '丹恒•腾荒',
        'effective_substats': ['速度'],
        'main_stat_expectations': {
            '躯干': ['暴击'],
            '脚部': ['速度'],
            '连结绳': ['充能'],
            '头部': ['生命值'],
        },
    }]

    envelope = evaluate(roster, criteria)

    result = envelope['data']['results']['丹恒•腾荒']
    check = result['main_stat_check']
    assert [item['slot'] for item in check] == ['躯干', '脚部', '连结绳']  # 头部被排除
    assert check[0] == {'slot': '躯干', 'actual': '暴击伤害', 'expected': ['暴击率'], 'matches': False}
    assert check[1] == {'slot': '脚部', 'actual': '速度', 'expected': ['速度'], 'matches': True}
    assert check[2] == {'slot': '连结绳', 'actual': None, 'expected': ['能量恢复效率'], 'matches': False}
    assert any('头部' in w and '不参与核对' in w for w in result['warnings'])
    assert result['verdict'].startswith('命中 2/2（100%）主词条穿错 2 件；')


def test_threshold_report_main_plus_sub_sum() -> None:
    """规则 6：current = 同标准名的主词条（若同名）+ 副词条求和（两件
    主词条都计入；词条 line 的 value 只累加一次，times 只进命中次数）；
    gap_text 达标/差线保留 1 位小数。"""
    roster = _ok_roster(_roster_character('黄泉', [
        _piece('野穗伴行的快枪手', '头部', ('生命值', '705'), [_sub('击破特攻', '5.8%', 2)]),
        _piece('毁烬焚骨的大公', '躯干', ('攻击力', '43.2%'), [_sub('攻击力', '7.3%', 2)]),
        _piece('毁烬焚骨的大公', '连结绳', ('攻击力', '43.2%'), []),
    ]))
    criteria = [{
        'character_name': '黄泉',
        'effective_substats': ['击破'],
        'stat_thresholds': {'大攻击': 60, '击破': 140},
    }]

    envelope = evaluate(roster, criteria)

    result = envelope['data']['results']['黄泉']
    assert result['threshold_report'] == [
        {'stat': '攻击力提高', 'current': 93.7, 'line': 60, 'gap_text': '达标 +33.7'},
        {'stat': '击破特攻', 'current': 5.8, 'line': 140, 'gap_text': '差 134.2'},
    ]
    assert '达标 1 项、差线 1 项；' in result['verdict']


def test_wasted_distribution_and_weakest_piece() -> None:
    """规则 4/7：浪费分布按标准名累计强化次数；最弱件 = 单件浪费次数
    最高者，字段形态 {set_name, slot, effective_hits, wasted_rolls}。"""
    roster = _ok_roster(_roster_character('花火', [
        _piece('野穗伴行的快枪手', '头部', ('生命值', '705'), [_sub('暴击率', '3.2%', 1)]),
        _piece('野穗伴行的快枪手', '手部', ('攻击力', '352'), [
            _sub('防御力', '9.7%', 2),
            _sub('防御力', '42', 2),
        ]),
        _piece('死水深潜的先驱', '躯干', ('暴击伤害', '64.8%'), [_sub('速度', '5.6', 1)]),
    ]))
    criteria = [{'character_name': '花火', 'effective_substats': ['暴击']}]

    envelope = evaluate(roster, criteria)

    result = envelope['data']['results']['花火']
    assert result['wasted_rolls_by_stat'] == {'防御力提高': 2, '防御力': 2, '速度': 1}
    assert result['weakest_piece'] == {
        'set_name': '野穗伴行的快枪手',
        'slot': '手部',
        'effective_hits': 0,
        'wasted_rolls': 4,
    }


def test_weakest_piece_tie_breaks_by_lower_hits() -> None:
    """规则 7：浪费次数并列时取命中次数更低者（头部 0 命中 < 手部 2 命中）。

    同时锁：口径词可直接写标准名（「暴击率」同名直通）。"""
    roster = _ok_roster(_roster_character('阮•梅', [
        _piece('骇域漫游的信使', '头部', ('生命值', '705'), [_sub('效果命中', '3.8%', 3)]),
        _piece('骇域漫游的信使', '手部', ('攻击力', '352'), [
            _sub('效果抵抗', '6.9%', 3),
            _sub('暴击率', '2.9%', 2),
        ]),
    ]))
    criteria = [{'character_name': '阮•梅', 'effective_substats': ['暴击率']}]

    envelope = evaluate(roster, criteria)

    weakest = envelope['data']['results']['阮•梅']['weakest_piece']
    assert weakest == {
        'set_name': '骇域漫游的信使',
        'slot': '头部',
        'effective_hits': 0,
        'wasted_rolls': 3,
    }


def test_verdict_empty_relic_data_branch() -> None:
    """规则 8：total_rolls=0 → verdict「无遗器数据」，hit_ratio/weakest_piece
    均为 null（规则 7 无副词条数据置 null）。"""
    roster = _ok_roster(_roster_character('米沙', []))
    criteria = [{'character_name': '米沙', 'effective_substats': ['双暴']}]

    envelope = evaluate(roster, criteria)

    result = envelope['data']['results']['米沙']
    assert result['verdict'] == '无遗器数据'
    assert result['total_rolls'] == 0
    assert result['hit_ratio'] is None
    assert result['weakest_piece'] is None
    assert result['main_stat_check'] == []


def test_character_not_in_roster_goes_to_not_found() -> None:
    """规则 9：名册缺名记入 not_found，不影响其他角色；success message 按
    「共评估 N 名角色，M 名未命中名册」模板。"""
    roster = _ok_roster(_roster_character('卡芙卡', [
        _piece('幽锁深牢的系囚', '头部', ('生命值', '705'), [_sub('暴击率', '5.5%', 2)]),
    ]))
    criteria = [
        {'character_name': '卡芙卡', 'effective_substats': ['暴击']},
        {'character_name': '花火', 'effective_substats': ['暴击']},
    ]

    envelope = evaluate(roster, criteria)

    assert envelope['status'] == 'success'
    assert envelope['message'] == '共评估 1 名角色，1 名未命中名册'
    assert list(envelope['data']['results'].keys()) == ['卡芙卡']
    assert envelope['data']['not_found'] == ['花火']


@pytest.mark.parametrize('case_name, criteria, message_part', [
    ('空列表', [], 'criteria 为空列表'),
    ('非列表', 'criteria', 'criteria 需为列表'),
    ('重复名', [
        {'character_name': '卡芙卡', 'effective_substats': ['暴击']},
        {'character_name': '卡芙卡', 'effective_substats': ['速度']},
    ], 'criteria 存在重复 character_name：卡芙卡'),
    ('元素缺必填字段', [{'character_name': '卡芙卡'}], 'criteria 元素结构非法'),
])
def test_error_rejections_of_criteria(case_name: str, criteria: object, message_part: str) -> None:
    """规则 9/10 同族防御：空列表 / 非列表 / 重复名（message 列出重复名）/
    元素缺必填字段 → 整体 error 信封，不产出部分结果。"""
    roster = _ok_roster({'name': '卡芙卡', 'relics': [], 'ornaments': []})

    envelope = evaluate(roster, criteria)  # type: ignore[arg-type]

    assert envelope['status'] == 'error', f'场景 {case_name} 应返回 error'
    assert message_part in envelope['message']
    assert envelope['data'] is None


@pytest.mark.parametrize('case_name, roster_data', [
    ('非列表', {'name': '卡芙卡'}),
    ('元素非对象', ['not-a-dict']),
    ('缺 ornaments 键', [{'name': '卡芙卡', 'relics': []}]),
    ('relics 非列表', [{'name': '卡芙卡', 'relics': 'oops', 'ornaments': []}]),
])
def test_error_invalid_roster_data_structure(case_name: str, roster_data: object) -> None:
    """规则 10：roster_data 非 list / 元素缺 name/relics/ornaments 键 →
    error 信封（message 提示应传 data 字段内容），不当空名册静默产出。"""
    criteria = [{'character_name': '卡芙卡', 'effective_substats': ['暴击']}]

    envelope = evaluate(roster_data, criteria)  # type: ignore[arg-type]

    assert envelope['status'] == 'error', f'场景 {case_name} 应返回 error'
    assert envelope['message'] == ROSTER_STRUCTURE_ERROR_MESSAGE
    assert envelope['data'] is None


def test_team_summary_sorted_with_null_last() -> None:
    """出参 team_summary：按 hit_ratio 升序，无数据（null）排最后；同值
    保持 criteria 顺序。"""
    def _char_with_ratio(name: str, crit_hits: int, total: int) -> dict:
        subs = [_sub('暴击率', '5.5%', crit_hits), _sub('速度', '5.6', total - crit_hits)]
        return _roster_character(name, [_piece('野穗伴行的快枪手', '头部', ('生命值', '705'), subs)])

    roster = _ok_roster(
        _char_with_ratio('甲', 4, 5),
        _char_with_ratio('乙', 1, 4),
        _roster_character('丙', []),
    )
    criteria = [
        {'character_name': '甲', 'effective_substats': ['暴击']},
        {'character_name': '乙', 'effective_substats': ['暴击']},
        {'character_name': '丙', 'effective_substats': ['暴击']},
    ]

    envelope = evaluate(roster, criteria)

    assert envelope['message'] == '共评估 3 名角色，0 名未命中名册'
    assert envelope['data']['team_summary'] == [
        {'character_name': '乙', 'hit_ratio': 0.25},
        {'character_name': '甲', 'hit_ratio': 0.8},
        {'character_name': '丙', 'hit_ratio': None},
    ]
