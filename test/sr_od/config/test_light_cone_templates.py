"""light_cone_templates 光锥卡面库单测。

锁的内容（命名约定即注册表；读仓内真实模板资产）：
- 卡面库与常量表一致：目录名集合 == 非空 id 光锥集合（空 id 光锥
  国际服未同步不入库，白名单随 test_sr_light_cones 同步收紧）；
- 遍历条目自洽：template_id == 光锥 id，raw 可加载。
"""

from sr_od.config.light_cone_templates import iter_light_cone_templates
from sr_od.mys.sr_light_cones import LIGHT_CONES


def test_iter_light_cone_templates_matches_constants(test_context, monkeypatch) -> None:
    monkeypatch.setattr(test_context, 'light_cone_templates', None, raising=False)
    entries = iter_light_cone_templates(test_context)
    expected = {c.id: c for c in LIGHT_CONES if c.id}
    assert {e.template_id for e in entries} == set(expected)
    for e in entries:
        assert e.light_cone.id == e.template_id
        assert e.info.raw is not None
