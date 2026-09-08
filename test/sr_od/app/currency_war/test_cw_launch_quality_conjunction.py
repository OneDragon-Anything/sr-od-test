"""达标臂 armed 成型质量合取锁面(B_t 通道承重结构维;ADR-0570)。

出处(docstring 引设计出处,锁的存在性纪律):
- 命题 ADR = ``docs/develop/currency_war/decisions/
  0570-launch-quality-load-bearing-conjunction.md``——armed = 配方完备
  ∧〔承重满额 ∨ 部署计划不可得 fail-open〕;质量维只消费 B_t 通道
  承重结构派生量(承重计数/槽位占用/部署计划存在性,零自由参数);
  原候选「2★ 数/装备覆盖重校」作废(00 §1 禁战力建模 + P62 已证
  form_score 饱和零信息);P63(r=0.403)只作方向锚禁作判据资格。
- 行为核算 = C3 设计《设计-C3成型质量维度.md》§3.2(推迟上界 =
  armed 翻真 ∨ 计划耗尽 ∨ 金尽 → ADR-0554 收益耗尽臂,无死锁)。

本批锁:
1. 合取真值表:配方腿前置闸/承重满额开闸/线外件+计划可得推迟/
   线外件+计划不可得 fail-open/未识别件 fail-closed 承重不认/
   质量评估异常 fail-open(C3 §6 教义);
2. 质量维视图随目标线(comp.all_factions)不随四体系披露视图——
   四体系外阵营线真实 comp 回归锁(ADR-0570 Considered 否决 3 的
   回归防线)+ 四体系线 comp 披露对账锁;
2b. 自家核准集(core∪shared)并入承重判定——反甲白厄空羁绊单卡/
    视图外 shared 件回归锁(落地审 F1 防线,ADR-0570 §判据);
2c. 质量评估异常显影旗(quality_eval_error,残量禁静默,三审07轮
    C1)+ 分键名单一源 grep 守卫(三审07轮 C2);
3. B5 推迟上界:推迟帧换血翻真序列 + 收益耗尽臂判据与质量闸零耦合
   (判据签名结构锁)。
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel import cw_launch_admission
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_state import BenchChar

_LINE_MEMBERS = set()


def _line_members(_comp):
    """线成员谓词桩(判据核注入参;本锁面不消费其语义,恒空集)。"""
    return _LINE_MEMBERS


def _comp(form: dict, factions: list, core: list = (),
          flex: list = ()):
    """最小 Comp 形状(form_progress 读 form_tiers;质量报告读
    factions/all_factions/core_chars)。"""
    return SimpleNamespace(form_tiers=dict(form), factions=list(factions),
                           core_chars=list(core), flex_factions=list(flex),
                           shared_chars=[],
                           all_factions=set(factions) | set(flex))


def _state(names: list, *, bench: list = (), max_units: int = 6):
    """最小 GameState 形状:board 按注册表全羁绊聚合(deployed 聚合
    语义),deployed/bench 定长槽表。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    board: dict[str, int] = {}
    dep: list = [None] * 10
    for i, name in enumerate(names):
        dep[i] = BenchChar(slot=i + 1, char_id=name, star=1,
                           position_pref='back')
        ch = CHARACTERS.get(name)
        for f in ((set(ch.factions) | set(ch.flows)) if ch else set()):
            board[f] = board.get(f, 0) + 1
    b: list = [None] * 9
    for i, name in enumerate(bench):
        b[i] = BenchChar(slot=i + 1, char_id=name, star=1,
                         position_pref='back')
    return SimpleNamespace(board=board, deployed=dep, bench=b,
                           level=max_units, deploy_cap=max_units,
                           max_units=lambda: max_units)


def _decide(state, comp):
    return cw_launch_admission.readiness_launch_decision(
        state, comp, line_members=_line_members)


# 真值表夹具(注册表直调核实,2026-09-07):藿藿/停云/爻光/丹恒·饮月
# = 仙舟系;卡芙卡 = {持续伤害,星核猎手}(仙舟单阵营 comp 视图的线外件)。
_XZ3 = ('藿藿', '停云', '爻光')
_COMP_XZ = _comp({'仙舟': 3}, ['仙舟'], core=['藿藿'])


class TestArmedConjunctionTruthTable:
    """锁 1:armed 三支路真值表(ADR-0570 §判据)。"""

    def test_recipe_leg_gates_first(self):
        """配方腿前置:fp<1.0 帧质量维不评估(quality=None),armed 恒假
        ——合取序保持,配方完备语义零改。"""
        st = _state(list(_XZ3[:2]) + ['卡芙卡'], bench=['丹恒·饮月'])
        core = _decide(st, _COMP_XZ)
        assert core['armed'] is False
        assert core['quality'] is None

    def test_load_bearing_full_arms(self):
        """承重满额支:fp=1.0 ∧ 板面零线外件 → armed True(承重=占用)。"""
        core = _decide(_state(list(_XZ3)), _COMP_XZ)
        assert core['armed'] is True
        q = core['quality']
        assert q['load_bearing_full'] is True
        assert q['line_weight'] == q['occupied'] == 3
        assert q['defer_by_quality'] is False

    def test_offline_with_plan_defers(self):
        """推迟支:fp=1.0 ∧ 线外件在场 ∧ 部署计划可得 → armed False
        (defer_by_quality 显影;C3 §3.2 推迟语义的判据位)。"""
        st = _state(list(_XZ3) + ['卡芙卡'], bench=['丹恒·饮月'])
        core = _decide(st, _COMP_XZ)
        assert core['armed'] is False
        q = core['quality']
        assert q['load_bearing_full'] is False
        assert q['deploy_plan_available'] is True
        assert q['defer_by_quality'] is True
        assert q['line_weight'] == 3 and q['occupied'] == 4

    def test_offline_without_plan_fails_open(self):
        """fail-open 支:线外件在场 ∧ 部署计划不可得(bench 空)→ armed
        True——质量目标不可达帧降格配方完备发射(ADR-0570 §判据;
        C3 §6 防死锁:关闸后无动作 = 守卫停摆死型,结构性排除)。"""
        st = _state(list(_XZ3) + ['卡芙卡'])
        core = _decide(st, _COMP_XZ)
        assert core['armed'] is True
        q = core['quality']
        assert q['load_bearing_full'] is False
        assert q['deploy_plan_available'] is False
        assert q['defer_by_quality'] is False

    def test_unknown_identity_counts_offline_fail_closed(self):
        """fail-closed 分界:未识别/未注册名承重不认(按线外计),但
        计划不可得帧仍 fail-open——承重判定与防死锁两语义各自成立。"""
        st = _state(list(_XZ3) + ['未收录角色'])
        core = _decide(st, _COMP_XZ)
        assert core['quality']['line_weight'] == 3   # 未收录件不计承重
        assert core['quality']['occupied'] == 4
        assert core['armed'] is True                 # 计划不可得 fail-open

    def test_quality_evaluation_exception_fails_open(self, monkeypatch):
        """质量评估异常 → armed 维持配方腿结果、quality=None + 显影旗
        quality_eval_error=True(算不出不关闸的防死锁教义 + 残量禁静默:
        异常帧与「配方不完备」常态帧单义区分,三审07轮 C1);正常帧
        旗恒 False(双态不混载)。"""

        def _boom(*a, **kw):
            raise RuntimeError('质量报告不可得(注入异常)')

        monkeypatch.setattr(cw_launch_admission,
                            'launch_board_quality_report', _boom)
        core = _decide(_state(list(_XZ3)), _COMP_XZ)
        assert core['armed'] is True
        assert core['quality'] is None
        assert core['quality_eval_error'] is True
        monkeypatch.undo()
        normal = _decide(_state(list(_XZ3)), _COMP_XZ)
        assert normal['quality'] is not None
        assert normal['quality_eval_error'] is False


class TestConsumerKeySingleSource:
    """锁 2c:质量闸分键名单一源(三审07轮 C2 守卫锁,F8 族 grep 守卫
    扩展)——两消费面写点禁字面量散写,键名改 kernel 常量即全链跟随。"""

    def test_counter_keys_not_inlined_in_consumers(self):
        """engine_p1/cw_loop 源内不得出现 ``launch_quality_defer_frames``
        /``launch_quality_eval_error`` 字面量(单一源 = kernel 常量
        LAUNCH_QUALITY_*_KEY;字面量散写 = 双源,红)。"""
        from one_dragon.utils.file_utils import get_project_root
        root = get_project_root()
        for rel in ('src/sr_od/application/currency_war/sim/engine_p1.py',
                    'src/sr_od/application/currency_war/operations/'
                    'cw_loop.py'):
            src = (root / rel).read_text(encoding='utf-8')
            assert 'launch_quality_defer_frames' not in src, (
                f'{rel} 分键名字面量散写(经 kernel 常量消费)')
            assert 'launch_quality_eval_error' not in src, (
                f'{rel} 分键名字面量散写(经 kernel 常量消费)')


class TestQualityViewFollowsTargetLine:
    """锁 2:质量维视图 = comp.all_factions(随目标线),非四体系披露
    视图(ADR-0570 Considered 否决 3 的回归防线:注册表实证 20 套
    comp 中 15 套 form_tiers 非空且含四体系外阵营,四体系视图会令这些
    线的达标板面永久关闸)。"""

    def test_non_transition_comp_arms_on_own_view(self):
        """真实四体系外线(千冶减益,form={减益:4,星核猎手:2}):达标
        板面全员 comp 视图承重 → 开闸;披露 B_t(四体系)对同板严格
        更小(黄泉/赛飞儿/千冶·刃/刃/流萤零四体系羁绊,唯彦卿持仙舟)
        ——两视图分叉且判据走 comp 视图。"""
        comp = get_comp('千冶减益')
        assert comp is not None
        names = ['黄泉', '赛飞儿', '千冶·刃', '彦卿', '刃', '流萤']
        core = _decide(_state(names), comp)
        q = core['quality']
        assert q['load_bearing_full'] is True
        assert q['line_weight'] == q['occupied'] == 6
        assert core['armed'] is True
        assert q['b_t_disclosure'] < q['line_weight']

    def test_transition_comp_disclosure_parity(self):
        """四体系线对账锁:仙舟线达标板面 comp 视图承重 = 披露 B_t
        (同族同源,ADR-0570 §判据;披露口径本体零改)。"""
        comp = get_comp('景元仙舟')
        assert comp is not None
        core = _decide(_state(['藿藿', '停云', '爻光', '丹恒·饮月', '景元']),
                       comp)
        q = core['quality']
        assert q['load_bearing_full'] is True
        assert q['line_weight'] == q['b_t_disclosure'] == 5
        assert core['armed'] is True


class TestDeferBoundB5:
    """锁 3:B5 推迟上界(推迟有界、出路在册;C3 §3.2)。"""

    def test_deferred_frame_flips_after_purify(self):
        """armed 翻真序列:线外件被线内件换下(承重满额)→ 推迟帧解除
        ——闸关闭帧的解除路径 = 换血收敛(P61 族 B_t 单调),推迟恒有界。"""
        comp = _comp({'仙舟': 3}, ['仙舟'], core=['藿藿'])
        deferred = _state(list(_XZ3) + ['卡芙卡'], bench=['丹恒·饮月'])
        assert _decide(deferred, comp)['armed'] is False
        purified = _state(['藿藿', '停云', '爻光', '丹恒·饮月'],
                          bench=['卡芙卡'])
        assert _decide(purified, comp)['armed'] is True

    def test_exhaustion_arm_independent_of_quality_gate(self):
        """金尽上界出路零耦合:收益耗尽臂判据(ADR-0554;T-167 修订版)
        签名不含 armed/质量位(结构锁)∧ RunDeploy 稳态在推迟形态语境下
        仍合格——质量闸不延伸进金尽出路辖域。签名含 actions_union =
        F2 窗口动作批并集(非质量维,判据放宽的输入)。"""
        from sr_od.application.currency_war.operations.cw_loop import (
            prep_exhaustion_launch_eligible,
        )
        params = set(inspect.signature(
            prep_exhaustion_launch_eligible).parameters)
        assert params == {'action_sig', 'last_prep_success', 'actions_union'}, (
            f'收益耗尽臂判据签名漂移(不得引入 armed/质量位):{params}')
        # 推迟形态语境(armed=False 的板面)下,RunDeploy 稳态照旧判合格:
        _decide(_state(list(_XZ3) + ['卡芙卡'], bench=['丹恒·饮月']),
                _COMP_XZ)
        assert prep_exhaustion_launch_eligible(
            ('RunDeploy',), True, frozenset({'RunDeploy'})) is True
        assert prep_exhaustion_launch_eligible(
            (), True, frozenset()) is False   # 空批非 RunDeploy 末批(守卫语义不变)


class TestSanctionedRosterView:
    """锁 2b:自家核准集并入承重判定(落地审 F1 回归防线;ADR-0570
    §判据「核准集 core∪shared ∪ 视图」)。

    注册表实证(2026-09-07):白厄 factions∪flows = 空集(独立羁绊绑死
    单卡)、不死途={巡海游侠,追击} ∉ 千冶减益视图、布洛妮娅={燃血} ∉
    希儿量子视图、刃={星核猎手,燃血} ∉ 黄泉减益视图——纯视图判定会把
    comp 自家核准板面件误判线外,该线承重满额支路恒不可达(同 ADR
    Considered 否决 3 的自设判据形状,四体系视图同罪先例)。
    """

    def test_empty_bond_core_counts_load_bearing(self):
        """反甲白厄(唯一空羁绊核心线):自家核心白厄在板 → 核准计入
        承重,不因注册表空羁绊判线外。"""
        comp = get_comp('反甲白厄')
        assert comp is not None
        from sr_od.application.currency_war.kernel import (
            cw_launch_admission as _cla,
        )
        q = _cla.launch_board_quality_report(_state(['白厄']), comp)
        assert q['line_weight'] == q['occupied'] == 1
        assert q['load_bearing_full'] is True

    def test_view_external_shared_member_fixed(self):
        """千冶减益达标板 + 视图外 shared『不死途』(巡海游侠/追击):
        核准集并入后承重满额开闸——纯视图判定下该帧 line_weight=6<7
        恒推迟(本锁红证锚,口径见交付报告)。"""
        comp = get_comp('千冶减益')
        assert comp is not None
        names = ['黄泉', '赛飞儿', '千冶·刃', '彦卿', '刃', '流萤', '不死途']
        core = _decide(_state(names), comp)
        q = core['quality']
        assert q['line_weight'] == q['occupied'] == 7
        assert q['load_bearing_full'] is True
        assert core['armed'] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
