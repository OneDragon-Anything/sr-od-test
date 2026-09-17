"""TRANSITION_PACK 单一源锁(2026-09 策略内容回流普查:kernel 双副本退役批)。

背景:过渡包数据曾存在 kernel/cw_transition 与 knowledge/cw_line_facts 双副本,
kernel 旧副本滞留旧错误标签(花火='列车')。收敛后单一源 = knowledge,
kernel 判据函数与配方/围栏消费点全部改从 knowledge 取数。

花火框架 = ('量子', 'carry'):注册表 cw_chars 花火 = 盛会之星阵营 +
战技点/量子同频流派,**无列车阵营**(comp 审计修复项4,2026-08-31)。
本锁走消费侧真实路径(kernel.cw_recipe 读 knowledge 单一源):若 kernel
副本复活且消费点改接旧源,列车 core 会重新混入无列车同行阵营的花火
——一个永远凑不了 form_tiers 的死件,本锁红。
"""
from sr_od.application.currency_war.knowledge.cw_line_facts import TRANSITION_PACK
from sr_od.application.currency_war.kernel.cw_recipe import recipe_comp


def test_sparkle_framework_is_quantum_via_single_source():
    """花火框架 = 量子线(knowledge 单一源 + 配方消费侧同向)。

    断言值按注册表事实机械重推:花火流派含量子同频 → 量子配方
    (form_tiers 量子同频:3)可贡献成型档,入 core;无列车同行 →
    列车配方(form_tiers 列车同行:4)永远凑不了档,不入 core。
    """
    assert TRANSITION_PACK['花火'] == ('量子', 'carry')
    assert '花火' in recipe_comp('量子').core_chars
    assert '花火' not in recipe_comp('列车').core_chars
