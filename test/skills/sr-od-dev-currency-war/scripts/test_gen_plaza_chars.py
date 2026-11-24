"""gen_plaza_chars 生成器·技能块派生 / 片段往返 / 文档渲染 / 对拍闭环锁面。

出处 = skills/sr-od-dev-currency-war/scripts/gen_plaza_chars.py 模块头「产出 1/4」
与 derive_skills / _ch_line / skill_block / check_fragment_vs_config docstring
(口径单一源)。合成 role/config 直调生成器函数——.debug 面数据零依赖,落盘常量
重定向 tmp_path,零网络零真实落盘。

锁四件事:
1. derive_skills:双技能(Back/Front,3 段与 4 段)产出 CharacterSkill 元组(官方顺序);
   守卫矩阵——段间原文不一致 / 未知 front_back_type / 无星级段 / 原文空 各报错;
   derive_all 同名多档 skills 不一致报错(合并取首档的前提);
2. 片段生成端真实路径:_ch_line 文本 exec 往返(桩 _ch/_sk 构造 CharacterSkill)与
   派生字段全等,含 is_hide 行内注条目——生成器写坏片段格式即红;
3. 人读文档:羁绊行经 render_rich 映射属性名(不丢「提供2%<属性>和<属性>」)、
   字面 \\n 压平为一行;技能标题带【前台】/【后台】;gen_docs 接线 prop_map;
4. 对拍闭环:gen_registry_fragment → check_fragment_vs_config 归零;篡改片段技能原文
   → SystemExit(1)。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from sr_od.application.currency_war.data.cw_chars import CharacterSkill


def _load_gen_module():
    """从仓库根定位 skills 脚本并加载(sr-od-test 独立仓,无包路径可达)。"""
    for anc in Path(__file__).resolve().parents:
        p = anc / 'skills' / 'sr-od-dev-currency-war' / 'scripts' / 'gen_plaza_chars.py'
        if p.is_file():
            spec = importlib.util.spec_from_file_location('_gen_plaza_chars_under_test', p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise AssertionError('自 __file__ 向上找不到 gen_plaza_chars.py(仓库根?)')


_g = _load_gen_module()


def _skill(name: str, fb: str, tags: tuple, descs: list[str]) -> dict:
    """官方 skills[] 条目形状(front_back_type 官方原值 Front/Back)。"""
    return {'name': name, 'front_back_type': fb, 'icon': 'u', 'category_tags': list(tags),
            'skill_stars': [{'star': i + 1, 'desc': d, 'skill_types': []}
                            for i, d in enumerate(descs)]}


def _role(rid: str = '100402', name: str = '测试员', skills: list | None = None,
          fbt: str = 'Common', **extra) -> dict:
    # 默认双技能同标签(多技能标签不一致是生成器另一守卫面,与技能块无关)
    return {'id': rid, 'name': name, 'rarity': '1', 'front_back_type': fbt, 'icon': 'u',
            'trait_details': [], 'skills': skills if skills is not None else
            [_skill('甲', 'Back', ('输出', '辅助'), ['后台文'] * 3),
             _skill('甲', 'Front', ('输出', '辅助'), ['前台文'] * 4)], **extra}


class TestDeriveSkills:
    """技能块派生与守卫矩阵。"""

    def test_two_sided_skills_official_order_and_guards(self):
        """双技能按官方顺序产出,各星级段只取一份;四类破坏各自报错停手。"""
        sk = _g.derive_skills(_role())
        assert [(s.name, s.front_back, s.category_tags, s.desc) for s in sk] == [
            ('甲', 'back', ('输出', '辅助'), '后台文'), ('甲', 'front', ('输出', '辅助'), '前台文')]

        with pytest.raises(RuntimeError, match='不一致'):
            _g.derive_skills(_role(skills=[_skill('a', 'Front', (), ['甲', '乙', '甲'])]))
        with pytest.raises(RuntimeError, match='front_back_type'):
            _g.derive_skills(_role(skills=[_skill('a', 'Common', (), ['甲'])]))
        with pytest.raises(RuntimeError, match='无星级段'):
            _g.derive_skills(_role(skills=[_skill('a', 'Front', (), [])]))
        with pytest.raises(RuntimeError, match='原文为空'):
            _g.derive_skills(_role(skills=[_skill('a', 'Front', (), ['  '])]))

    def test_multi_tier_skills_must_match(self):
        """同名多档 skills 不一致 → derive_all 报错(合并查询取首档的前提被破坏)。"""
        a = _role('100402', '测试员')
        b = _role('100403', '测试员', skills=[_skill('甲', 'Back', ('输出',), ['别的文'])])
        with pytest.raises(RuntimeError, match='同名多档'):
            _g.derive_all([a, b], {})
        assert len(_g.derive_all([a, {**b, 'skills': a['skills']}], {})) == 2


def _exec_fragment(text: str, path: Path) -> list[dict]:
    """片段往返解析:桩 _ch/_sk 构造与 check_fragment_vs_config 同形记录。"""
    records: list[dict] = []

    def _ch(name, cost, position, category_tags, factions=(), schools=(),
            independent='', source='', is_expert=False, is_hide=False, skills=()):
        records.append({'name': name, 'cost': cost, 'position': position,
                        'category_tags': category_tags, 'factions': factions, 'schools': schools,
                        'independent': independent, 'source': source, 'is_expert': is_expert,
                        'is_hide': is_hide, 'skills': tuple(skills)})

    def _sk(name, front_back, category_tags, desc):
        return CharacterSkill(name=name, front_back=front_back,
                              category_tags=tuple(category_tags), desc=desc)

    exec(compile(text, str(path), 'exec'), {'_ch': _ch, '_sk': _sk})
    return records


def test_fragment_roundtrip(tmp_path, monkeypatch):
    """片段生成端真实路径:_ch_line 文本 exec 往返与派生字段全等(含 is_hide 行内注条目)。"""
    monkeypatch.setattr(_g, 'PLAZA_DIR', tmp_path)
    roles = [_role('100402', '测试员'), _role('141402', '随从', is_hide=True)]
    fields = _g.derive_all(roles, {})
    path = _g.gen_registry_fragment(fields, '9.9', 0)
    text = path.read_text(encoding='utf-8')
    assert text.count('\n    _sk(') == 4 and '各星级段原文相同只存一份' in text
    records = _exec_fragment(text, path)
    assert [r['name'] for r in records] == ['测试员', '随从']
    assert records[1]['is_hide'] is True
    for rec, f in zip(records, fields, strict=True):
        assert rec['skills'] == f['skills']
        assert (rec['name'], rec['cost'], rec['position'], rec['category_tags'], rec['source']) == (
            f['name'], f['cost'], f['position'], f['category_tags'], f['source'])


def test_gen_docs_renders_property_names_and_skill_side(tmp_path, monkeypatch):
    """人读文档:羁绊行映射属性名并压平字面 \\n;技能标题带【后台】;gen_docs 接线 prop_map。"""
    monkeypatch.setattr(_g, 'DOC_DIR', tmp_path)
    prop_map = {'ExtraLuckChance': '幸运一击率', 'ExtraLuckDamage': '幸运一击伤害'}
    role = _role('150302', '真珠', skills=[_skill('甲', 'Back', ('治疗', '辅助'), ['后台文'] * 3)],
                 trait_details=[{'name': '千星商会', 'desc': (
                     '每上场1位<color=#f29e38ff>3星</color>角色。\\n提供2%'
                     '<property type=ExtraLuckChance display=all>和'
                     '<property type=ExtraLuckDamage display=all>。')}])
    assert _g.gen_docs([role], '4.7', prop_map) == 1
    doc = (tmp_path / '真珠.md').read_text(encoding='utf-8')
    assert '- 羁绊【千星商会】:每上场1位3星角色。 提供2%幸运一击率和幸运一击伤害。' in doc
    assert '#### 技能 甲【后台】(治疗、辅助)' in doc
    assert '\\n' not in doc and '<property' not in doc


def test_check_fragment_vs_config_closed_loop(tmp_path, monkeypatch):
    """对拍闭环:片段 vs 合成 config 归零;篡改片段技能原文 → SystemExit(1)。"""
    monkeypatch.setattr(_g, 'PLAZA_DIR', tmp_path)
    cfg = {'rpg_game_big_version': '4.7', 'trait_info_list': [], 'role_property_list': [],
           'role_list': [_role()]}
    cfg_path = tmp_path / 'config_v4.7.json'
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding='utf-8')
    fields = _g.derive_all(cfg['role_list'], _g.trait_map(cfg))
    frag = _g.gen_registry_fragment(fields, '4.7', 0)
    _g.check_fragment_vs_config(cfg_path)  # 一致不抛

    frag.write_text(frag.read_text(encoding='utf-8').replace('后台文', '被改'), encoding='utf-8')
    with pytest.raises(SystemExit) as excinfo:
        _g.check_fragment_vs_config(cfg_path)
    assert excinfo.value.code == 1
