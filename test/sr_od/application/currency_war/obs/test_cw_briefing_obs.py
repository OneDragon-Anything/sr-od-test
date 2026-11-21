"""简报 boss 读数归一(``clean_boss_names_by_lcs`` 两段转换)回归
(文件镜像 src cw_briefing_obs.py)。

锁的设计约定:**规范注册名走①段精确命中原样透传,不进 LCS 相似段**。
回归背景:图鉴 20 公司集外的新赛季公司(深渊育种科技)未注册时,
读数落入②段 LCS 相似匹配,因共享词素(深×科技)被误归一为
深穹智械科技——错名直写状态容器并进线分 boss 分量。注册后须精确
透传(注册面 = ``cw_enemy_data.BOSS_MECHANICS``)。
"""
from __future__ import annotations

from sr_od.application.currency_war.obs.cw_briefing_obs import (
    clean_boss_names_by_lcs,
)


def test_registered_new_season_company_passthrough_exact() -> None:
    """已注册规范名(含新赛季补注册公司)①段精确透传,禁 LCS 误归一。"""
    assert clean_boss_names_by_lcs(
        ['深渊育种科技', '铁盾安保集团', '钢铁意志集团']) == \
        ['深渊育种科技', '铁盾安保集团', '钢铁意志集团']
