"""CW 羁绊聚合生成器·对拍闭环与 fail-closed 退出语义锁面。

出处 = skills/sr-od-dev-currency-war/scripts/gen_traits.py 模块头「对拍非零
退出语义」「翻译与成员对拍(查表契约 = 派生形态)」两节(口径单一源)。
对拍三判据:骨架(聚合 trait_name/trait_type vs config 逐键 + 无 layers 覆盖
报警)/全覆盖(条数与 id 集合 = config 过滤 type 0/1/2 后全集)/成员(members
vs 注册表自报派生集合全等)。测试注入构造输入直调对拍函数——.debug 面数据
(gitignored 区)零依赖;main 级用例把生成器落盘常量重定向 tmp_path、断言的
退出路径发生在 wiki 拉取之前,故零网络零子进程零真实落盘。

锁五件事:
1. 骨架对拍闭环:一致构造零 diff;name/type 漂移、无 layers、聚合缺条逐行归位;
2. 全覆盖对拍闭环:config 有聚合缺 / 聚合有 config 无各一行;
3. 成员对拍闭环:官方多出/自报多出差异行含 role_ids 键形;例外清单同名
   全键放行才改写 members,部分裁决 = 未裁决保持差异可见;
4. 翻译 fail-closed:翻不出的 id 进 unknown 不静默丢弃;is_hide 过滤
   (可组队员口径)与同名多档合并(成员是角色非档位);
5. fail-closed 编排闭环:帖 role_ids 含注册表翻不出 id 时 main 以
   SystemExit code=1 非零退出(函数收集 unknown → 编排拦截的完整链路)。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_gen_traits_module():
    """从仓库根定位 skills 脚本并加载(sr-od-test 独立仓,无包路径可达)。"""
    for anc in Path(__file__).resolve().parents:
        p = (anc / 'skills' / 'sr-od-dev-currency-war' / 'scripts'
             / 'gen_traits.py')
        if p.is_file():
            spec = importlib.util.spec_from_file_location(
                '_gen_traits_under_test', p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise AssertionError('自 __file__ 向上找不到 gen_traits.py(仓库根?)')


_gt = _load_gen_traits_module()


def _skel(tid: str, name: str, ttype: int = 1) -> dict:
    """config 骨架条目形状(build_skeleton 产物键子集)。"""
    return {'trait_id': tid, 'trait_name': name, 'trait_type': ttype,
            'trait_icon': f'icon:{tid}'}


def _prod(tid: str, name: str, ttype: int = 1, layers: tuple = (2, 4),
          member_ids: tuple = (), members: tuple = ()) -> dict:
    """聚合产物条目形状(aggregate_posts + translate_members 消费面字段)。"""
    return {'trait_id': tid, 'trait_name': name, 'trait_type': ttype,
            'trait_icon': f'icon:{tid}',
            'layers': [{'layer': lay, 'quality': 4, 'trait_desc': f'效果{lay}'}
                       for lay in layers],
            'member_ids': list(member_ids), 'members': list(members),
            'simple_desc': ''}


class TestSkeletonCrosscheck:
    """骨架对拍闭环(判据 = 逐键相等 + 无 layers 覆盖报警)。"""

    def test_consistent_and_broken_matrix(self):
        """一致构造零 diff;四类破坏各产一行:name/type 漂移、基座有而聚合无
        layers(帖子覆盖报警)、基座有而聚合缺条。"""
        skeleton = {'100001': _skel('100001', '持续伤害'),
                    '100002': _skel('100002', '击破'),
                    '100003': _skel('100003', '治疗')}
        ok = {'100001': _prod('100001', '持续伤害'),
              '100002': _prod('100002', '击破'),
              '100003': _prod('100003', '治疗')}
        assert _gt.crosscheck_skeleton(ok, skeleton) == []

        bad = {'100001': {**_prod('100001', '持续伤害'), 'trait_name': '漂移名'},
               '100002': {**_prod('100002', '击破'), 'trait_type': 9,
                          'layers': []}}
        diffs = _gt.crosscheck_skeleton(bad, skeleton)
        assert len(diffs) == 4, diffs
        assert any('trait_name' in d and '100001' in d for d in diffs)
        assert any('trait_type' in d and '100002' in d for d in diffs)
        assert any('100002' in d and 'layers' in d for d in diffs)
        assert any('100003' in d and '基座有而聚合无' in d for d in diffs)


class TestFullCoverageCrosscheck:
    """全覆盖对拍闭环(判据 = 条数与 id 集合 = config 过滤后全集)。"""

    def test_consistent_and_broken_matrix(self):
        """一致零 diff;双向破坏各归其位:config 有聚合缺 / 聚合有 config 无。"""
        cfg = {'trait_info_list': [
            {'trait_id': '100001', 'trait_name': '持续伤害', 'trait_type': 1,
             'trait_icon': 'u'},
            {'trait_id': '400001', 'trait_name': '主角光环', 'trait_type': 3,
             'trait_icon': 'u'},  # type 3 不进本数据域,对拍右源不含
        ]}
        assert _gt.crosscheck_full_coverage(
            {'100001': _prod('100001', '持续伤害')}, cfg) == []

        diffs = _gt.crosscheck_full_coverage(
            {'100002': _prod('100002', '多出条')}, cfg)
        assert len(diffs) == 2, diffs
        assert any('100001' in d and 'config 有而聚合缺' in d for d in diffs)
        assert any('100002' in d and '聚合有而 config 无' in d for d in diffs)


class TestMembersCrosscheck:
    """成员对拍闭环(判据 = members vs 注册表自报派生集合全等)。"""

    @staticmethod
    def _products_one(name: str, member_ids: tuple, members: tuple) -> dict:
        return {'100001': _prod('100001', name, member_ids=member_ids,
                                members=members)}

    def test_consistent_and_two_difference_directions(self):
        """一致零 hard;官方多出(译出名的 role_ids 全集入行)/自报多出
        (该名全部档位 id 入行)两类差异行键形归位。"""
        source_map = {'r1': '甲', 'r2': '乙', 'r3': '丙'}
        hidden_ids: set[str] = set()
        bond_index = {'持续伤害': {'甲'}}
        name_sources = {'甲': ['r1'], '乙': ['r2'], '丙': ['r3']}

        ok = self._products_one('持续伤害', ('r1',), ('甲',))
        info, hard = _gt.crosscheck_members(
            ok, source_map, hidden_ids, bond_index, name_sources)
        assert hard == []
        assert info == []

        official_extra = self._products_one(
            '持续伤害', ('r1', 'r2'), ('甲', '乙'))
        info, hard = _gt.crosscheck_members(
            official_extra, source_map, hidden_ids, bond_index, name_sources)
        assert info == [] and len(hard) == 1, hard
        assert "官方成员 乙" in hard[0] and "['r2']" in hard[0]

        selfreport_extra = self._products_one('持续伤害', ('r1',), ('甲',))
        bond_two = {'持续伤害': {'甲', '丙'}}
        info, hard = _gt.crosscheck_members(
            selfreport_extra, source_map, hidden_ids, bond_two, name_sources)
        assert info == [] and len(hard) == 1, hard
        assert "自报成员 丙" in hard[0] and "['r3']" in hard[0]

    def test_exception_release_requires_full_key_set(self):
        """例外清单放行语义:同名全部档位 id 皆在清单才放行(改写 members +
        理由进 info_rows);部分裁决 = 未裁决,差异保持 hard 可见。"""
        source_map = {'r1': '甲', 'r2': '乙', 'r4': '乙'}
        bond_index = {'持续伤害': {'甲'}}
        name_sources = {'甲': ['r1'], '乙': ['r2', 'r4']}

        products = self._products_one('持续伤害', ('r1', 'r2', 'r4'),
                                      ('甲', '乙'))
        partial = {('100001', 'r2'): '召唤物不算成员(测试裁决)'}
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(_gt, 'MEMBER_EXCEPTIONS', partial)
            info, hard = _gt.crosscheck_members(
                products, source_map, set(), bond_index, name_sources)
        assert info == [] and len(hard) == 1, (info, hard)
        assert "['r2', 'r4']" in hard[0]
        assert products['100001']['members'] == ['甲', '乙']  # 未放行不改写

        products2 = self._products_one('持续伤害', ('r1', 'r2', 'r4'),
                                       ('甲', '乙'))
        full = {('100001', 'r2'): '召唤物不算成员(测试裁决)',
                ('100001', 'r4'): '召唤物不算成员(测试裁决)'}
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(_gt, 'MEMBER_EXCEPTIONS', full)
            info, hard = _gt.crosscheck_members(
                products2, source_map, set(), bond_index, name_sources)
        assert hard == []
        assert len(info) == 1 and '例外放行' in info[0]
        assert products2['100001']['members'] == ['甲']  # 放行即从 members 排除


class TestTranslateMembersFailClosed:
    """翻译段口径:fail-closed 收集 + is_hide 过滤 + 同名多档合并。"""

    def test_unknown_collected_and_filters_applied(self):
        """翻不出的 id 进 unknown(tid → [id])不静默丢弃;is_hide 条目不入
        members(可组队员口径)且记入 hidden_filtered;同名多档 id 合并为
        单一角色名(合并事件进报告句)。"""
        products = {'100001': _prod('100001', '持续伤害',
                                    member_ids=('r1', 'r2', 'h1', 'h2', 'zz'))}
        source_map = {'r1': '甲', 'r2': '甲', 'h1': '腾荒', 'h2': '腾荒'}
        hidden_filtered, unknown, note = _gt.translate_members(
            products, source_map, {'h1', 'h2'})
        assert unknown == {'100001': ['zz']}
        assert products['100001']['members'] == ['甲']  # 多档合并 + 隐藏过滤后
        assert sorted(hidden_filtered) == [
            ('100001', 'h1', '腾荒'), ('100001', 'h2', '腾荒')]
        assert '甲' in note  # r1/r2 两档同名的合并事件可见


class TestCountModeGuard:
    """count_mode 覆盖表双向引文校验与落字段(判据表单一源 = 生成器常量)。"""

    def test_override_guards_and_apply(self):
        """三向守卫各自非零退出:覆盖表条目不在骨架 / 覆盖表条目 desc 缺三星
        句式锚 / 非覆盖表条目 desc 出现锚(新 STAR3 候选待人裁);正向
        apply_count_mode 默认 TOTAL、覆盖表条目落 STAR3。"""
        skeleton = {'100001': _skel('100001', '千星商会', 2),
                    '100002': _skel('100002', '持续伤害')}
        anchor = '每上场1位3星【千星商会】角色,将激活1级羁绊效果'
        _gt.check_count_mode(skeleton, {'100001': {anchor}})  # 一致不抛

        with pytest.raises(SystemExit, match='不在骨架'):
            _gt.check_count_mode({'100002': skeleton['100002']}, {})
        with pytest.raises(SystemExit, match='引文校验失败'):
            _gt.check_count_mode(skeleton, {'100001': {'无锚文本'}})
        with pytest.raises(SystemExit, match='新 STAR3 候选'):
            _gt.check_count_mode(
                skeleton,
                {'100001': {anchor},
                 '100002': {'每上场1位3星【持续伤害】角色,将激活1级效果'}})

        products = {'100001': _prod('100001', '千星商会', 2),
                    '100002': _prod('100002', '持续伤害')}
        _gt.apply_count_mode(products)
        assert products['100001']['count_mode'] == 'STAR3'
        assert products['100002']['count_mode'] == 'TOTAL'


class TestMainFailClosedExit:
    """fail-closed 编排闭环:main 级非零退出(main 内部编排 = 生产路径)。"""

    def test_main_exits_nonzero_on_untranslatable_role_id(self, tmp_path,
                                                          monkeypatch,
                                                          capsys):
        """帖 role_ids 含注册表翻不出 id → main 以 SystemExit code=1 退出,
        stdout 报告披露 FAIL-CLOSED 与该 id(禁静默丢弃);落盘常量已重定向
        tmp_path,真实目录零写入。"""
        first_source = sorted(_gt.CHARACTERS, key=lambda c: c.source)[0].source
        cfg = {
            'rpg_game_big_version': '4.7',
            'trait_info_list': [
                {'trait_id': '100001', 'trait_name': '测试羁绊',
                 'trait_type': 1, 'trait_icon': 'u'},
                {'trait_id': '100602', 'trait_name': '千星商会',
                 'trait_type': 2, 'trait_icon': 'u'},
            ],
            'role_property_list': [],
            'role_list': [{'id': first_source,
                           'trait_details': [{'id': '100602',
                                              'desc': '每上场1位3星【千星商会】角色,'
                                                      '将激活1级羁绊效果'}]}],
        }
        post = {'created_at': 1, 'tourn_detail': {'role_stages': [{'traits': [
            {'trait_id': '100001', 'trait_name': '测试羁绊', 'trait_type': 1,
             'layers': [{'layer': 2, 'quality': 4, 'trait_desc': '效果'}],
             'role_ids': [first_source, '999999999'], 'simple_desc': ''},
            {'trait_id': '100602', 'trait_name': '千星商会', 'trait_type': 2,
             'layers': [{'layer': 1, 'quality': 4, 'trait_desc': '三星效果'}],
             'role_ids': [first_source], 'simple_desc': ''},
        ]}]}}
        cfg_path = tmp_path / 'config_v4.7.json'
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False),
                            encoding='utf-8')
        lineups_path = tmp_path / 'lineups_Hot.jsonl'
        lineups_path.write_text(json.dumps(post, ensure_ascii=False) + '\n',
                                encoding='utf-8')

        monkeypatch.setattr(_gt, 'PLAZA_DIR', tmp_path / 'plaza')
        monkeypatch.setattr(_gt, 'REPORT_SAMPLE_DIR', tmp_path / 'reports')
        monkeypatch.setattr(sys, 'argv', [
            'gen_traits.py', '--config', str(cfg_path),
            '--lineups', str(lineups_path)])
        with pytest.raises(SystemExit) as excinfo:
            _gt.main()
        assert excinfo.value.code == 1
        out = capsys.readouterr().out
        assert 'FAIL-CLOSED' in out and '999999999' in out
