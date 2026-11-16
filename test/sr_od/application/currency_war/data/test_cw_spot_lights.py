"""货币战争主角光环数据层结构守卫(镜像 src = data/cw_spot_lights.py)。

出处 = cw_spot_lights.py 模块 docstring(id 稳定主键/suitable_roles 生成期
翻译口径)。锁生成产物的结构不变量:id 唯一与索引一致/适配名单注册表
sanity——条目数与具体名单随游戏版本变动(版本更新重跑生成器重写数据),
一律不锁。
"""

from __future__ import annotations

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.data.cw_spot_lights import (
    SPOT_LIGHTS,
    spot_light_by_id,
)


def test_id_unique_and_index_consistency() -> None:
    """id 唯一与索引一致锁(cw_spot_lights.py:plaza id 为稳定主键):
    SPOT_LIGHTS 内 id 不重复,spot_light_by_id 键集 = 各条目 id 集合且回指
    同对象(平行索引双份抄写时此锁红);空表(生成器断流)同红。"""
    assert len(SPOT_LIGHTS) > 0
    ids = [x.id for x in SPOT_LIGHTS]
    assert len(ids) == len(set(ids))
    by_id = spot_light_by_id()
    assert set(by_id) == set(ids)
    assert all(by_id[x.id] is x for x in SPOT_LIGHTS)


def test_suitable_roles_registry_sanity() -> None:
    """适配名单 sanity 锁(cw_spot_lights.py 文件头 suitable_roles 口径注释):
    名单为生成期经角色注册表翻译的名字形态,出现的名字必须 ⊆ 注册表规范名
    (查无名 = 脱离注册表的平行名单回流);零 is_hide 成员(腾荒类隐藏随从
    不可上阵不可持有光环,官方 suitable_role_list 语义下不该出现)。
    名单允许为空(全局/非角色绑定型光环,官方原样)——非空性不锁。"""
    registry_names = {c.name for c in CHARACTERS}
    hidden_names = {c.name for c in CHARACTERS if c.is_hide}
    for x in SPOT_LIGHTS:
        assert set(x.suitable_roles) <= registry_names, x.id
        assert not (set(x.suitable_roles) & hidden_names), x.id
