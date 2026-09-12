"""T-130 投资环境迭代 3.4 送卡型结构 · 预注册单帧锁(G1/G2/G8 半边)。

锁面出处(持久索引):
- docs/develop/sr_od/application/currency_war/changes/2026-09-12-invest-env/
  landing.md §3.4(批辖域 = G1 分档表直调锁 + G2 失格门构造锁 + G8 互斥断言半边);
- docs/develop/sr_od/application/currency_war/changes/2026-09-12-invest-env/
  details/env-value-models.md §2.1(送卡型:§2.1.1 语义盘点/§2.1.2 估值形态与
  档位阶梯/§2.1.3 结构与落码面/§2.1.4 正交性/§2.1.5 G 组锁表)。

机器单一源 = ``ENV_GIFTS``(kernel/cw_investments.py,白名单制 11 条 + 构建期
校验 _validate_env_gifts)+ ``gift_hit_tier``/``candidate_char_universe``
(kernel/cw_comps.py,COMP_LIBRARY 派生 helper 区)。档位 floor 常数
(GIFT_FLOOR_CORE/SHARED/ADVISOR_CORE)= 定序实现常数(ADR-0524 同族先例),
值只承载档间定序与对既有域带的位次,禁读基数。

批内不碰 cw_events.py(landing §3.4 文件面边界):消费支(cw_events env 分支
送卡档 max(),decide_event 行为帧)归 3.5 = G3-G7;G2 的 decide_event 行为
半边(分 0/env-gift-off-universe 归因/argmax 落其余候选)随 G3-G7 同批落锁,
本批只锁失格门构造(构造 GiftGrant → 档位机器判 'off' + 消费契约谓词)。
G8 的 ∩ ENV_POOL_REWRITE 半边随 3.6 建表收全(= Q6)。

fixture 直调核验(仿 test_cw_env_universe.py U 组先例;模块导入即验,
COMP_LIBRARY/环境/角色注册表漂移先红于此——漂移 = 修库后重核全集咬合面,
不是改断言保绿):
- ENV_GIFTS 恰 11 条 + 效果原文对账 id(INVESTMENT_ENVS.source = plaza:<id>);
- 分档表逐位(详设 §2.1.2 命中表的宿主套名单 + 全集外名单 + §2.1.1 faction 事实);
- floor 常数锚点不等式(注册表派生:契约裸分上界 58/阵营 floor 下界 70/
  env 裸分上界 72/结构可比簇上界 52/头彩 55)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_investments as inv
from sr_od.application.currency_war.kernel.cw_comps import (
    COMP_LIBRARY,
    candidate_char_universe,
    gift_hit_tier,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    ENV_ECONOMY,
    ENV_FACTION_MATCH_FLOOR,
    ENV_GIFTS,
    ENV_PICK_VALUE,
    GIFT_FLOOR_ADVISOR_CORE,
    GIFT_FLOOR_CORE,
    GIFT_FLOOR_SHARED,
    INVESTMENT_ENVS,
    GiftGrant,
)

# ===== fixture 前提直调核验(锁语义依赖的注册表事实;漂移先红于此)=====

# 效果原文对账 id(details/env-value-models.md §2.1.1 表;cw_invest_data.PLAZA_PORTALS)
_GIFT_IDS: dict[str, str] = {
    '量子同频契约': 'plaza:125',
    '公司契约': 'plaza:126',
    '持续伤害契约': 'plaza:127',
    '战技点契约': 'plaza:128',
    '星核猎手契约': 'plaza:129',
    '欢愉契约': 'plaza:1201',
    '命运圣杯契约': 'plaza:1202',
    '特邀专家:停云': 'plaza:141',
    '特邀专家:加拉赫': 'plaza:142',
    '特邀专家:银狼': 'plaza:143',
    '特邀专家:桑博': 'plaza:148',
}
assert set(ENV_GIFTS) == frozenset(_GIFT_IDS), (
    f'送卡白名单漂移(详设 §2.1.1 恰 11 条),实得 {sorted(ENV_GIFTS)}')
for _n, _src in _GIFT_IDS.items():
    assert INVESTMENT_ENVS[_n].source == _src, f'{_n} 效果原文对账 id 漂移'

# §2.1.4-1 faction 事实(阵营全集门先行评估的前置:契约 faction 非空走门 1,
# 顾问 3 条 faction 空恒放行,加拉赫=击破例外表唯一条走阵营门/floor 路)
_GIFT_FACTIONS: dict[str, str] = {
    '量子同频契约': '量子同频', '公司契约': '公司', '持续伤害契约': '持续伤害',
    '战技点契约': '战技点', '星核猎手契约': '星核猎手', '欢愉契约': '欢愉',
    '命运圣杯契约': '命运圣杯',
    '特邀专家:停云': '', '特邀专家:加拉赫': '击破', '特邀专家:银狼': '',
    '特邀专家:桑博': '',
}
for _n, _f in _GIFT_FACTIONS.items():
    assert INVESTMENT_ENVS[_n].faction == _f, f'{_n} faction 漂移,实得 {INVESTMENT_ENVS[_n].faction!r}'


def _hosts(char: str) -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    """角色三名单宿主套名单(core, shared, transition);注册表直读核验用。"""
    return (
        frozenset(c.name for c in COMP_LIBRARY if char in c.core_chars),
        frozenset(c.name for c in COMP_LIBRARY if char in c.shared_chars),
        frozenset(c.name for c in COMP_LIBRARY if char in c.transition_chars),
    )


# 详设 §2.1.2 分档表(2026-09-12 对抗批逐位复算口径;本批开工直调复核一致):
# core 命中宿主套逐名钉死(套名漂移先红,重核咬合面)
_CORE_HOSTS: dict[str, frozenset[str]] = {
    '卡芙卡': frozenset({'DOT队', '专家桑博DOT', '千冶减益'}),
    '花火': frozenset({'列车同行', '希儿量子', '龙丹战技点', '火花星间旅人'}),
    '符玄': frozenset({'DOT队', '千冶减益', '绯英欢愉', '希儿量子', '双王圣杯',
                       '景元仙舟'}),
    '银狼LV.999': frozenset({'火花星间旅人', '狼尊欢愉'}),
    '远坂凛': frozenset({'命运圣杯红A', '龙丹战技点'}),
    '吉尔伽美什': frozenset({'双王圣杯'}),
    '丹恒·饮月': frozenset({'龙丹战技点'}),
    '希儿': frozenset({'希儿量子'}),
    '桑博': frozenset({'专家桑博DOT'}),
    '黑天鹅': frozenset({'DOT队'}),
    '火花': frozenset({'狼尊欢愉'}),
    'Archer': frozenset({'命运圣杯红A'}),
    '开拓者·欢愉': frozenset({'绯英欢愉', '火花星间旅人', '狼尊欢愉'}),
    '翡翠': frozenset({'大黑塔银河学者', '银枝群攻'}),
}
# shared 命中(且非 core):椒丘 shared×1(千冶减益)/流萤 shared×1(巡海击破)/
# 银狼 shared×2(昼神阿雅/火花星间旅人)
_SHARED_HOSTS: dict[str, frozenset[str]] = {
    '椒丘': frozenset({'千冶减益'}),
    '流萤': frozenset({'巡海击破'}),
    '银狼': frozenset({'昼神阿雅', '火花星间旅人'}),
}
# 全集外(三名单皆不在;详设 §2.1.2 档表行 4)
_OFF_UNIVERSE_CHARS = ('砂金', '托帕&账账', '停云', '加拉赫')
# evicted 传导例(§2.1.4-5)依赖的 transition 宿主事实
assert _hosts('椒丘')[2] == frozenset({'千冶减益', '黄泉减益', '银枝群攻', '万敌单C'}), (
    '椒丘 transition 宿主漂移,§2.1.4-5 evicted 传导例须重核')
assert _hosts('卡芙卡')[2] == frozenset({'专家桑博DOT'}), (
    '卡芙卡 transition 宿主漂移,§2.1.4-5 evicted 传导例须重核')

for _ch, _hosts_expect in _CORE_HOSTS.items():
    assert _hosts(_ch)[0] == _hosts_expect, f'{_ch} core 宿主漂移,重核分档表咬合面'
for _ch, _hosts_expect in _SHARED_HOSTS.items():
    _core_h, _shared_h, _trans_h = _hosts(_ch)
    assert _shared_h == _hosts_expect and not _core_h, (
        f'{_ch} shared 宿主漂移(或已升 core),重核分档表咬合面')
for _ch in _OFF_UNIVERSE_CHARS:
    _core_h, _shared_h, _trans_h = _hosts(_ch)
    assert not _core_h and not _shared_h and not _trans_h, (
        f'{_ch} 应三名单皆不在(全集外),实得 core={_core_h} shared={_shared_h} '
        f'trans={_trans_h}——注册表演化,重核分档表')


# ===== G1 分档表直调锁(详设 §2.1.5 行 1)=====


def test_g1_grant_structure() -> None:
    """G1 前半:11 条发放结构 = 详设 §2.1.1 盘点表逐位(效果原文直读口径)。

    即时/条件两分 + advisor 旗标;条件描述摘要为注释字段(内容不进判据,
    只核「具名角色集」——随机战技点角色不可具名,不入 chars_conditional)。
    """
    expect: dict[str, GiftGrant] = {
        '量子同频契约': GiftGrant(chars_conditional=(
            ('符玄', ''), ('希儿', ''),
        )),
        '公司契约': GiftGrant(
            chars_immediate=('翡翠', '砂金'),
            chars_conditional=(('托帕&账账', ''),),
        ),
        '持续伤害契约': GiftGrant(
            chars_immediate=('椒丘', '卡芙卡'),
            chars_conditional=(('黑天鹅', ''),),
        ),
        '战技点契约': GiftGrant(
            chars_immediate=('丹恒·饮月', '花火'),
            chars_conditional=(('火花', ''),),
        ),
        '星核猎手契约': GiftGrant(
            chars_immediate=('卡芙卡',),
            chars_conditional=(('流萤', ''),),
        ),
        '欢愉契约': GiftGrant(
            chars_immediate=('银狼LV.999',),
            chars_conditional=(('火花', ''), ('开拓者·欢愉', '')),
        ),
        '命运圣杯契约': GiftGrant(
            chars_immediate=('远坂凛', '吉尔伽美什'),
            chars_conditional=(('Archer', ''),),
        ),
        '特邀专家:停云': GiftGrant(chars_immediate=('停云',), advisor=True),
        '特邀专家:加拉赫': GiftGrant(chars_immediate=('加拉赫',), advisor=True),
        '特邀专家:银狼': GiftGrant(chars_conditional=(('银狼', ''),), advisor=True),
        '特邀专家:桑博': GiftGrant(chars_immediate=('桑博',), advisor=True),
    }
    for _n, _want in expect.items():
        got = ENV_GIFTS[_n]
        assert got.chars_immediate == _want.chars_immediate, f'{_n} 即时发放漂移'
        assert [c for c, _ in got.chars_conditional] == [c for c, _ in _want.chars_conditional], (
            f'{_n} 条件发放具名角色漂移')
        assert all(note for _, note in got.chars_conditional), (
            f'{_n} 条件描述摘要缺失(注释字段须留实采对账文案)')
        assert got.advisor == _want.advisor, f'{_n} advisor 旗标漂移'


def test_g1_tier_table() -> None:
    """G1 后半:11 条逐条档位 = 详设 §2.1.2 落点表(直调 ENV_GIFTS × gift_hit_tier)。

    - 5 契约即时 core → 66;量子同频即时空、条件 core 降一档 → shared(60);
    - 公司契约 = core 机器对账行(env 级被阵营全集门先行击杀,faction=公司 ∉
      全集;不发档位断言,门放行后发卡档接续 = §2.1.4-1);
    - 特邀专家:桑博 core(advisor 换族 → 54);停云/加拉赫 off(advisor 不提档
      维持裸分,floor 表行 4,失格门不咬 advisor——顾问是购买选项无浪费);
    - 特邀专家:银狼条件 shared 降一档 → transition(无 floor 维持裸分 30)。
    注册表漂移先红(fixture 断言),重核后改表不是改断言。
    """
    expect: dict[str, str] = {
        '命运圣杯契约': 'core',
        '战技点契约': 'core',
        '星核猎手契约': 'core',
        '持续伤害契约': 'core',
        '欢愉契约': 'core',
        '量子同频契约': 'shared',
        '公司契约': 'core',
        '特邀专家:桑博': 'core',
        '特邀专家:停云': 'off',
        '特邀专家:加拉赫': 'off',
        '特邀专家:银狼': 'transition',
    }
    for _n, _tier in expect.items():
        got = gift_hit_tier(ENV_GIFTS[_n])
        assert got == _tier, f'{_n} 档位漂移:期望 {_tier} 实得 {got}(注册表演化,重核落点表)'


def test_g1_floor_anchors() -> None:
    """floor 常数锚点不等式(详设 §2.1.2 表;注册表派生,非拍值复述)。

    值域链:送卡档 54-66 < 阵营 floor 70-78 < 经济域带(111-119,3.5 接线)
    ——「静态结构证据 < 动态对齐 < 真金流」次序的环境轴锚;值禁读基数
    (ADR-0524 定序/基数分账),只承载档间定序与位次。
    """
    assert (GIFT_FLOOR_CORE, GIFT_FLOOR_SHARED, GIFT_FLOOR_ADVISOR_CORE) == (66, 60, 54)
    contract_pvs = [ENV_PICK_VALUE[n] for n, e in INVESTMENT_ENVS.items()
                    if e.category == '契约']
    max_contract_pv = max(contract_pvs)
    min_faction_floor = min(ENV_FACTION_MATCH_FLOOR.values())
    max_env_pv = max(ENV_PICK_VALUE.values())
    assert max_contract_pv == 58 and min_faction_floor == 70.0 and max_env_pv == 72, (
        '锚点参照值漂移(契约裸分上界/阵营 floor 下界/env 裸分上界),重推锚点链')
    assert max_contract_pv < GIFT_FLOOR_CORE, 'core 档须压过契约裸分上界'
    assert min_faction_floor > GIFT_FLOOR_CORE, 'core 档须弱于最低阵营 floor'
    assert max_env_pv >= GIFT_FLOOR_CORE, 'core 档不得凭结构档推翻知识评估最强项'
    assert 58 < GIFT_FLOOR_SHARED < GIFT_FLOOR_CORE
    assert GIFT_FLOOR_ADVISOR_CORE < GIFT_FLOOR_SHARED, '付费期权 < 白得(同档位类)'
    assert ENV_PICK_VALUE['过剩经费'] < GIFT_FLOOR_ADVISOR_CORE, '结构可比簇上界(52)'
    assert ENV_PICK_VALUE['头彩'] > GIFT_FLOOR_ADVISOR_CORE, '让位头彩知识评估分(55)'


# ===== G1 补:evicted 传导(详设 §2.1.4-5 直调例;机器级,G7 在 3.5 锁消费行为)=====


def test_g1b_evicted_narrows_tier() -> None:
    """evicted 收窄 → 档随之下调或失格,零额外代码(§2.1.4-5)。

    持续伤害契约排除三 DOT 套:卡芙卡三名单皆不在 = off、椒丘落 transition
    (黄泉减益/银枝群攻/万敌单C)→ 即时最优档 = transition,无 floor → 裸分
    维持(48);宿主套再被排除 → 椒丘亦 off → 整条失格档。
    """
    ev1 = frozenset({'DOT队', '专家桑博DOT', '千冶减益'})
    assert '卡芙卡' not in candidate_char_universe(ev1), '排除三 DOT 套后卡芙卡应退出全集'
    assert gift_hit_tier(ENV_GIFTS['持续伤害契约'], ev1) == 'transition', (
        '椒丘 transition 宿主健在,契约即时最优档应落 transition(失格门不咬)')
    ev2 = ev1 | {'黄泉减益', '银枝群攻', '万敌单C'}
    assert gift_hit_tier(ENV_GIFTS['持续伤害契约'], ev2) == 'off', (
        '椒丘宿主套再被排除,整条应失格档')


# ===== G2 失格门构造锁(详设 §2.1.5 行 2;decide_event 行为半边归 3.5 G3-G7)=====


def test_g2_disqualify_gate_construction() -> None:
    """G2:白得契约全员集外构造 → 档位机器判 'off' → 消费契约失格谓词命中。

    构造 GiftGrant(chars_immediate=('砂金',))(advisor 缺省 False,即契约形态)
    注入档位机器:砂金三名单皆不在 → 'off'。消费契约(gift_hit_tier docstring,
    3.5 cw_events env 分支按此实现):tier=='off' ∧ 非 advisor ∧ 即时集非空
    → 失格 0(归因 env-gift-off-universe,全集门同款);对照 = advisor off
    (停云)与条件降档落底(银狼型)同档不触发失格(无浪费,维持裸分)。
    当前注册表 11 条无一触发失格(§2.1.2;门 = COMP_LIBRARY 演化时结构性咬合)。
    """
    grant = GiftGrant(chars_immediate=('砂金',))
    assert gift_hit_tier(grant) == 'off', '全员集外白得契约应判 off'

    def _disqualify(grant: GiftGrant) -> bool:
        """消费契约失格谓词(3.5 落地前的机器级预演;单一源 = 谓词三支)。"""
        return gift_hit_tier(grant) == 'off' and not grant.advisor and bool(grant.chars_immediate)

    assert _disqualify(grant), '白得契约全员集外 → 失格'
    assert not _disqualify(ENV_GIFTS['特邀专家:停云']), 'advisor off = 不买即可,不失格'
    assert not _disqualify(ENV_GIFTS['特邀专家:银狼']), '条件降档落底 = 无 floor 维持,不失格'
    for _n in ENV_GIFTS:
        assert not _disqualify(ENV_GIFTS[_n]), f'{_n} 当前注册表不应触发失格门(§2.1.2 无一触发)'


def test_g2_conditional_downgrade_chain() -> None:
    """G2 补:条件降档链逐位(规则 3;core→shared→transition→off)。

    构造条件集单角色档位递减:core 命中降 shared、shared 命中降 transition、
    全集外(降 off)维持 off;即时集非空时降档不发生(规则 1 即时优先)。
    """
    assert gift_hit_tier(GiftGrant(chars_conditional=(('卡芙卡', 'x'),))) == 'shared'
    assert gift_hit_tier(GiftGrant(chars_conditional=(('椒丘', 'x'),))) == 'transition'
    assert gift_hit_tier(GiftGrant(chars_conditional=(('砂金', 'x'),))) == 'off'
    assert gift_hit_tier(GiftGrant(chars_immediate=('卡芙卡', '砂金'))) == 'core', (
        '即时集非空取最优档,降档不发生(规则 1)')


# ===== G8 结构互斥(详设 §2.1.5 行 8 半边;∩ ENV_POOL_REWRITE 半边 = 3.6 Q6)=====


def test_g8_cross_registry_mutex_half() -> None:
    """G8 半边:ENV_GIFTS ∩ ENV_ECONOMY = ∅(构建期断言的可读红面)。

    单一环境只落一个估值结构,防双通道叠加(详设 §2.1.3);∩ ENV_POOL_REWRITE
    半边由 3.6 品质改写建表时收全(Q6)。import 即炸闸 = _validate_env_gifts()
    模块级调用(构建闸给可读红 = 本锁与下列 validator-firing 用例)。
    """
    assert not (set(ENV_GIFTS) & set(ENV_ECONOMY)), '送卡与经济通道注册表必须互斥'


def test_g8_validator_fires(monkeypatch: pytest.MonkeyPatch) -> None:
    """G8 半边:构建校验四闸逐闸可炸(孤儿键/角色名漂移/空发放集/∩ENV_ECONOMY)。

    构建闸炸 import(模块级 _validate_env_gifts 调用),本锁逐闸给可读红:
    monkeypatch 注入坏条目后直调 validator,断言 ValueError 带对账语义。
    """
    # ① 孤儿键(ENV_PICK_VALUE/ENV_ECONOMY 先例同款)
    monkeypatch.setitem(inv.ENV_GIFTS, '不存在的环境', GiftGrant(chars_immediate=('砂金',)))
    with pytest.raises(ValueError, match='孤儿键'):
        inv._validate_env_gifts()
    monkeypatch.undo()
    # ② 角色名漂移(即时发放路径)
    monkeypatch.setitem(inv.ENV_GIFTS, '持续伤害契约',
                        GiftGrant(chars_immediate=('椒丘', '不存在的角色')))
    with pytest.raises(ValueError, match='角色名漂移'):
        inv._validate_env_gifts()
    monkeypatch.undo()
    # ②' 角色名漂移(条件发放路径)
    monkeypatch.setitem(inv.ENV_GIFTS, '量子同频契约',
                        GiftGrant(chars_conditional=(('不存在角色', 'x'),)))
    with pytest.raises(ValueError, match='角色名漂移'):
        inv._validate_env_gifts()
    monkeypatch.undo()
    # ③ 空发放集(档位机器恒判 off,会把登记笔误放大成失格门误杀)
    monkeypatch.setitem(inv.ENV_GIFTS, '持续伤害契约', GiftGrant())
    with pytest.raises(ValueError, match='空发放集'):
        inv._validate_env_gifts()
    monkeypatch.undo()
    # ④ ∩ ENV_ECONOMY(双通道叠加拒绝;Q6 收全 ∩ ENV_POOL_REWRITE 半边)
    monkeypatch.setitem(inv.ENV_GIFTS, '增发货币',
                        GiftGrant(chars_immediate=('砂金',)))
    with pytest.raises(ValueError, match='ENV_ECONOMY'):
        inv._validate_env_gifts()
