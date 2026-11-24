"""cw_chars 角色注册表·技能块不变量。

出处 = cw_chars.py ``CharacterSkill`` / ``Character.skills`` 字段注释 + 生成器
gen_plaza_chars.py ``derive_skills`` / ``derive_all`` 守卫(口径单一源)。

锁两件事:
1. 官方镜像全量——每条纯角色带非空 skills,技能 front_back ∈ {front, back}、原文非空
   (生成器守卫保证;注册表被手改/重灌漂移即红);
2. 同名多档各档 skills 全等——``cw_char_lookup`` 合并条目取首档 skills 的前提
   (生成器同名多档守卫的落库结果)。
"""

from sr_od.application.currency_war.data.cw_chars import CHARACTERS


def test_every_character_has_valid_skills_and_multi_tier_consistent() -> None:
    """全部纯角色技能块合法;同名多档(如星神★阿哈 4/5/7)各档 skills 全等。"""
    for c in CHARACTERS:
        assert c.skills, f'{c.name}({c.source}) 无技能块'
        for s in c.skills:
            assert s.name and s.desc, (c.name, s)
            assert s.front_back in ('front', 'back'), (c.name, s.front_back)

    by_name: dict[str, list] = {}
    for c in CHARACTERS:
        by_name.setdefault(c.name, []).append(c)
    for name, group in by_name.items():
        if len(group) > 1:
            assert len({c.skills for c in group}) == 1, f'{name}: 同名多档 skills 不一致'
