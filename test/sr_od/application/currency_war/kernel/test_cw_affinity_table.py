"""词缀吃怕表 + boss 面测试(design §3.3/§3.4;2026-11-03-unified-line-scoring 批 2)。

判据正本 = docs/develop/sr_od/application/currency_war/changes/
2026-11-03-unified-line-scoring/design.md §3.3(词缀:12 已审线+兜底层)
/§3.4(boss 面:4 线实证+D4 类级兜底+非 boss 强敌)。断言全部引设计
语义,期望值 = cw_line_scales 常数符号直读;数据源出处 = final_comps
各篇 counter 节(原话注释在表内,此处断言行值)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_affinity_table import (
    AFFINITY_TABLE,
    AFFIX_ALIASES_PENDING,
    BOSS_AFFINITY,
    BOSS_NAME_PENDING,
    LINE_ENGINE_KIND,
    STRONG_ENEMY_AFFINITY,
    affix_line_score,
    affix_restart_hit,
    affix_row_of,
    boss_line_score,
    boss_restart_hit,
    fuel_set_of,
    generic_fear_bonus,
    strong_enemy_score,
)
from sr_od.application.currency_war.kernel.cw_line_scales import (
    AFFIX_STRONG_FUEL,
    FEAR_PENALTY,
    RESTART_PENALTY,
)

# ===== 已审 12 线逐行抽查(final_comps counter 节原话对照)=====


def test_seele_row_restart_class() -> None:
    """希儿量子:量子熄火等 5 词缀重开级(final_seele_quantum「重开级:
    量子熄火/丢失幸运/免死金牌/极速制冷/以人为本——量子同频被禁=核心失效」);
    正当防卫「挡不住」二义标待核不登(不在行 = 记 0)。"""
    for affix in ('量子熄火', '丢失幸运', '免死金牌', '极速制冷', '以人为本'):
        assert affix_line_score('希儿量子', (affix,)) == RESTART_PENALTY, affix
    assert '正当防卫' not in affix_row_of('希儿量子')


def test_grail_red_a_fear_row() -> None:
    """命运圣杯红A(圣杯双C):8 词缀怕 −150(final_grail_dual counter 节,
    榜样激励 = 构造机理「克高倍率单核」);满愿俗称待采集不入表。"""
    for affix in ('正当防卫', '复仇心切', '一鼓作气', '永久创伤',
                  '能量逃逸', '榜样激励', '极速制冷', '量子熄火'):
        assert affix_line_score('命运圣杯红A', (affix,)) == FEAR_PENALTY, affix
    assert '满愿' not in affix_row_of('命运圣杯红A')
    assert '满愿' in AFFIX_ALIASES_PENDING


def test_yinlang_feiying_joy_rows() -> None:
    """狼尊欢愉怕 4 词缀(final_yinlang「避开正当防卫/能量逃逸/时间刺客/
    忍无可忍」);绯英欢愉同欢愉族只点名 2 词缀(final_feiying「counter 同
    欢愉族(正当防卫/能量逃逸类)」——「…类」不外推)。"""
    for affix in ('正当防卫', '能量逃逸', '时间刺客', '忍无可忍'):
        assert affix_line_score('狼尊欢愉', (affix,)) == FEAR_PENALTY, affix
    for affix in ('正当防卫', '能量逃逸'):
        assert affix_line_score('绯英欢愉', (affix,)) == FEAR_PENALTY, affix
    assert affix_line_score('绯英欢愉', ('时间刺客',)) == 0


def test_daheita_huangquan_rows() -> None:
    """大黑塔怕 3(final_daheita「坠入陷阱/正当防卫/冰之熄火(攻略共识)」);
    黄泉怕 3(final_huangquan「避免正当防卫/同步行动/免死金牌」)。"""
    for affix in ('坠入陷阱', '正当防卫', '冰之熄火'):
        assert affix_line_score('大黑塔银河学者', (affix,)) == FEAR_PENALTY, affix
    for affix in ('正当防卫', '同步行动', '免死金牌'):
        assert affix_line_score('黄泉减益', (affix,)) == FEAR_PENALTY, affix


def test_dot_restart_and_longdan_opening_fear() -> None:
    """DOT队:净化身心重开级(final_dot_kafka「净化身心环境别玩」);
    龙丹战技点怕 3(final_longtail 龙丹节「开局怕:正当防卫/极速制冷/
    丢失幸运类词条」)。"""
    assert affix_line_score('DOT队', ('净化身心',)) == RESTART_PENALTY
    for affix in ('正当防卫', '极速制冷', '丢失幸运'):
        assert affix_line_score('龙丹战技点', (affix,)) == FEAR_PENALTY, affix


def test_train_eat_and_fear_row() -> None:
    """列车同行(A 反震主体,批 3 拆分重写):吃忍无可忍/同步行动
    +750 受击触发类燃料(final_jizi「吃忍无可忍/同步行动/怪物提速」;
    怪物提速俗称待采集不入);怕正当防卫/能量逃逸/时间刺客/重症难题
    (A 节直接记载+构造机理史料级补回)。"""
    for affix in ('忍无可忍', '同步行动'):
        assert affix_line_score('列车同行', (affix,)) == AFFIX_STRONG_FUEL, affix
    for affix in ('正当防卫', '能量逃逸', '时间刺客', '重症难题'):
        assert affix_line_score('列车同行', (affix,)) == FEAR_PENALTY, affix
    assert '怪物提速' not in affix_row_of('列车同行')
    assert '怪物提速' in AFFIX_ALIASES_PENDING


def test_wandi_row_annotated_unchanged() -> None:
    """万敌行(批 1 直入)批 2 零改动:燃料集投影仍五行值(含灼热轰炸
    双面词条主阶段正值);「反伤类」= 正当防卫族同义注记(表内注释)。"""
    assert fuel_set_of('万敌单C') == frozenset(
        {'正当防卫', '忍无可忍', '应激反应', '灼热轰炸', '一鼓作气'})


def test_baie_and_aya_no_affix_row() -> None:
    """反甲白厄/昼神阿雅词缀面无实证不建行:白厄忌燃血类/回血减行动值
    均无注册名、受击触发类两推断打架标 0 待 sim(design §5);阿雅词缀面
    无记载(counter 仅 boss 面)。两线走兜底层(见泛化组测试)。"""
    assert '反甲白厄' not in AFFINITY_TABLE
    assert '昼神阿雅' not in AFFINITY_TABLE


def test_longtail_lines_no_affix_row() -> None:
    """长尾 8 线无 counter 记载不登吃行(final_comps 长尾篇+各篇 plaza 注),
    怕向由兜底层覆盖。"""
    longtail = {'千冶减益', '银枝群攻', '巡海击破', '双王圣杯',
                '火花星间旅人', '景元仙舟', '追击飞霄', '专家桑博DOT'}
    assert longtail & set(AFFINITY_TABLE) == set()
    # 12 已审线中词缀面空白的昼神阿雅/反甲白厄同走兜底,其余 10 线已登记
    assert set(AFFINITY_TABLE) == {
        '万敌单C', '希儿量子', '命运圣杯红A', '狼尊欢愉', '绯英欢愉',
        '大黑塔银河学者', '黄泉减益', 'DOT队', '龙丹战技点', '列车同行'}


# ===== 兜底层(方向保守:只给怕不给吃;design §3.3)=====


def test_generic_fear_conservative_direction() -> None:
    """未登记线泛化只给怕不给吃:dot 线×净化身心 −150(专家桑博DOT 与
    DOT队 同派——DOT队 实证重开级在表,泛化层只给怕档);大招流×能量
    逃逸(双王圣杯——final_grail 构造机理「能量逃逸(克 Saber 路线)」
    的类级佐证);任何词缀对未登记线**不给吃**(泛化分 ≤ 0 恒成立)。"""
    assert generic_fear_bonus('专家桑博DOT', ('净化身心',)) == FEAR_PENALTY
    assert generic_fear_bonus('双王圣杯', ('能量逃逸',)) == FEAR_PENALTY
    # 只怕不吃:全部 52 词缀对任一未登记线泛化分非正
    from sr_od.application.currency_war.data.affix_effects_data import (
        AFFIX_EFFECTS,
    )
    unregistered = ('千冶减益', '双王圣杯', '巡海击破', '专家桑博DOT',
                    '昼神阿雅', '反甲白厄', '景元仙舟', '追击飞霄')
    for line in unregistered:
        assert generic_fear_bonus(line, tuple(AFFIX_EFFECTS)) <= 0, line


def test_generic_fear_axes() -> None:
    """泛化轴逐面:暴击引擎(双王/银枝/火花星间×丢失幸运);前后台主力
    (前台熄火克前台主力线/后台熄火克后台主力线/前后台熄火克两轴);
    前后台灵活线(common 无覆盖,如 DOT队/银枝群攻)不泛化熄火。"""
    for line in ('双王圣杯', '银枝群攻', '火花星间旅人'):
        assert generic_fear_bonus(line, ('丢失幸运',)) == FEAR_PENALTY, line
    assert generic_fear_bonus('追击飞霄', ('前台熄火',)) == FEAR_PENALTY
    assert generic_fear_bonus('千冶减益', ('后台熄火',)) == FEAR_PENALTY
    assert generic_fear_bonus('千冶减益', ('前台熄火',)) == 0
    assert generic_fear_bonus('DOT队', ('前台熄火', '后台熄火', '前后台熄火')) == 0
    assert generic_fear_bonus('巡海击破', ('前后台熄火',)) == FEAR_PENALTY


def test_generic_fear_skips_contested_affixes() -> None:
    """有向争议词缀不泛化(机制泛化不预判方向):正当防卫(万敌 +900 vs
    姬子 −150 vs 白厄两推断打架)/时间刺客/同步行动等对未登记线 0。"""
    for affix in ('正当防卫', '时间刺客', '同步行动', '免死金牌',
                  '忍无可忍', '极速制冷'):
        assert generic_fear_bonus('双王圣杯', (affix,)) == 0, affix


def test_registered_line_unregistered_affix_zero() -> None:
    """已登记线(含强吃线)未登记词条记 0 不罚(design §3.3「已登记强吃线
    的未登记词条记 0 不罚」):万敌×随从强化(带燃料在局无底线)、
    列车同行×榜样激励 均为 0——泛化层不作用于已登记线。"""
    assert affix_line_score('万敌单C', ('一鼓作气', '随从强化')) \
        == AFFIX_STRONG_FUEL
    assert affix_line_score('列车同行', ('忍无可忍', '榜样激励')) \
        == AFFIX_STRONG_FUEL


def test_engine_kind_full_coverage() -> None:
    """B1 引擎型分类覆盖全 20 线(README B1 三类+final_comps 引擎节补核);
    值域锚(受击/行动/大招/dot/击破/追击)。"""
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    assert set(LINE_ENGINE_KIND) == {c.name for c in COMP_LIBRARY}
    assert set(LINE_ENGINE_KIND.values()) == {'受击', '行动', '大招',
                                              'dot', '击破', '追击'}
    assert LINE_ENGINE_KIND['列车同行'] == '受击'   # 盾反姬子 A 主体
    assert LINE_ENGINE_KIND['万敌单C'] == '受击'


# ===== boss 面(§3.4:4 线实证 + D4 类级兜底)=====


def test_boss_rows_empirical_four_lines() -> None:
    """4 线实证:姬子 3 只怕(死龙/酒杯怪/电视机经俗称归位)/希儿×蕉研组
    怕/阿雅×电视机怕/白厄×史瓦罗重开级(final_baie「重开级,攻略多帖共识」)。"""
    assert boss_line_score('列车同行', ('死龙', '酒杯怪', '电视机')) \
        == FEAR_PENALTY * 3
    assert boss_line_score('希儿量子', ('蕉研组',)) == FEAR_PENALTY
    assert boss_line_score('昼神阿雅', ('电视机',)) == FEAR_PENALTY
    assert boss_line_score('反甲白厄', ('史瓦罗',)) == RESTART_PENALTY
    assert boss_line_score('反甲白厄', ('深穹智械科技',)) == RESTART_PENALTY


def test_boss_sum_normalizes_and_unknown_zero() -> None:
    """boss 分 = Σ三只(均权,简报候选集口径):白厄局三只全克重开级可叠
    (Σ −200000 语义仍数值排他);俗称「电视机」与规范「造梦互动娱乐」
    同值;未登记 boss(对姬子的凛冬经贸联合体)记 0。"""
    assert boss_line_score('希儿量子',
                           ('造梦互动娱乐', '电视机', '灰手生命科技')) \
        == FEAR_PENALTY * 2
    assert boss_line_score('列车同行', ('凛冬经贸联合体',)) == 0
    assert boss_line_score('反甲白厄',
                           ('深穹智械科技', '深穹智械科技', '深穹智械科技')) \
        == RESTART_PENALTY * 3


def test_boss_blank_declaration_grail_lines() -> None:
    """圣杯两线 boss 面空白声明(审查 R1 撤登:README D4 原文唯红绿灯带
    类级括注且适用线均已实证,蕉研组无类级指向——类推克制属推断不登记,
    「无直接记载不登记」纪律;版本重跑攻略 boss 记载补登)。蕉研组对圣杯
    两线 0 分,两线不在 BOSS_AFFINITY。"""
    assert '命运圣杯红A' not in BOSS_AFFINITY
    assert '双王圣杯' not in BOSS_AFFINITY
    assert boss_line_score('命运圣杯红A', ('蕉研组',)) == 0
    assert boss_line_score('双王圣杯', ('造梦互动娱乐',)) == 0


def test_boss_pending_names_not_silently_dropped() -> None:
    """待验证映射表(不静默丢):存护星神(姬子)/贝洛伯格加血机器(万敌)/
    祸源萨姆(白厄重开级候选)三旧名在案;祸源萨姆→虫人兵器未定值不入
    白厄行(boss_line_score 对虫人兵器 0——映射待实机校验)。"""
    assert set(BOSS_NAME_PENDING) == {'存护星神', '贝洛伯格加血机器', '祸源萨姆'}
    assert boss_line_score('反甲白厄', ('虫人兵器',)) == 0


# ===== 非 boss 强敌(§3.4 单列知识条目)=====


def test_strong_enemy_traffic_light_restart() -> None:
    """红绿灯(小怪非 boss,52 词缀表外独立强敌键):白厄/万敌重开级;
    经简报词缀行 OCR 命中(enemy_affixes 透传未注册名);姬子无红绿灯条目
    (final_jizi「红绿灯(白厄子形态)」注记正名 = 克白厄子形态非姬子)。"""
    assert strong_enemy_score('反甲白厄', ('红绿灯',), frozenset()) \
        == RESTART_PENALTY
    assert strong_enemy_score('万敌单C', ('红绿灯',), frozenset()) \
        == RESTART_PENALTY
    assert '红绿灯' not in STRONG_ENEMY_AFFINITY.get('列车同行', {})


def test_strong_enemy_piggy_via_env_hold() -> None:
    """扑满(经济环境产物开局可见):持有扑满环境(经济过热/经济严重过热,
    PIGGY_ENV_NAMES 单一源)→ 姬子 −150(counter 有解降档:瓦尔特延后
    倒计时是机制解,design §3.3);未持环境不触发。"""
    assert strong_enemy_score('列车同行', (), frozenset({'经济过热'})) \
        == FEAR_PENALTY
    assert strong_enemy_score('列车同行', (), frozenset({'经济严重过热'})) \
        == FEAR_PENALTY
    assert strong_enemy_score('列车同行', (), frozenset({'蓝海'})) == 0
    assert strong_enemy_score('列车同行', ('扑满',), frozenset()) == 0, \
        '扑满非词缀行通道(词缀 OCR 读到「扑满」不触发——观察面 = 环境持有)'


# ===== 重开级命中原语(配方锁联动消费;design §6)=====


def test_restart_hit_primitives() -> None:
    """affix/boss 重开级命中判定(配方锁联动 kernel 原语):希儿×量子熄火
    True/白厄×史瓦罗 True/白厄×红绿灯 True/列车同行×死龙 False(怕档)/
    万敌无燃料 True;泛化怕(−150)不触发。"""
    assert affix_restart_hit('希儿量子', ('量子熄火',)) is True
    assert affix_restart_hit('万敌单C', ('风之熄火',)) is True   # 无燃料底线
    assert affix_restart_hit('万敌单C', ('正当防卫',)) is False
    assert boss_restart_hit('反甲白厄', ('深穹智械科技',)) is True
    assert boss_restart_hit('反甲白厄', (), ('红绿灯',)) is True
    assert boss_restart_hit('列车同行', ('灰手生命科技',)) is False
    assert affix_restart_hit('专家桑博DOT', ('净化身心',)) is False, \
        '泛化怕档不构成重开级命中'


def test_boss_table_keys_in_canonical_namespace() -> None:
    """boss 表键全落 BOSS_MECHANICS 规范名空间(俗称经 BOSS_NICKNAMES 归位,
    构建校验 import 即炸——此条为可观测锚);强敌表键不撞 boss 名空间。"""
    from sr_od.application.currency_war.data.cw_enemy_data import (
        BOSS_MECHANICS,
        BOSS_NICKNAMES,
    )
    for row in BOSS_AFFINITY.values():
        assert set(row) <= set(BOSS_MECHANICS)
    for row in STRONG_ENEMY_AFFINITY.values():
        assert not (set(row) & set(BOSS_MECHANICS))
    # BOSS_NICKNAMES 补史瓦罗;祸源萨姆待实机校验不入
    assert BOSS_NICKNAMES['史瓦罗'] == '深穹智械科技'
    assert '祸源萨姆' not in BOSS_NICKNAMES
