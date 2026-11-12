"""CW 批统计 ④ 终局阵容完成率的 p1_pair 代理键锁面 + 凑齐判定轮末
快照现算锁面。

出处 = skills/sr-od-dev-currency-war/scripts/cw_batch_stats.py ``game_metrics``
④ 分支(模块 docstring「P1 配方对代理键」节,口径单一源);语义依据 =
ADR-0357(P1 配方锁局 locked_comp 恒空)+ kernel/cw_intention.p1_pair
字段契约(配方锁活跃 ⟺ p1_pair 非空,P2+ 恒空)。凑齐判定口径单一源 =
kernel/cw_launch_admission.readiness_form_ok_from_snapshot(轮末快照
现算,镜像回退;动机 = 2026-09-15 批 4/300 镜像时点低估实证)。

锁的语义(现状):skill 脚本对真实对局档案的 p1_pair 代理——P1 配方
锁局的档案行 locked_comp 结构性为空,④ 靠同行 p1_pair 非空识别「配方
锁活跃」,以同行 form_ok 判定完成并标 proxy(观测面专用;引擎
ADR-0357 语义零改)。锁四件事:
1. 配方锁活跃帧:④ = form_ok 判定(1/0)且 comp_proxy=True;
2. 未锁线帧(p1_pair 空)与锁线帧(locked_comp 非空)既有口径零漂移,
   proxy 恒 False;
3. 档案行(locked_comp/p1_pair 结构性 None)= 无数据不入分母,代理
   分支不可达;
4. ``_sim_rows`` 装配链把 decisions 行 v3_intention.p1_pair 带进 row,
   端到端 ④ 经代理可判(装配漏字段会让代理结构性不可达)。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_stats_module():
    """从仓库根定位 skills 脚本并加载(sr-od-test 独立仓,无包路径可达)。"""
    for anc in Path(__file__).resolve().parents:
        p = (anc / 'skills' / 'sr-od-dev-currency-war' / 'scripts'
             / 'cw_batch_stats.py')
        if p.is_file():
            spec = importlib.util.spec_from_file_location(
                '_cw_batch_stats_under_test', p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise AssertionError('自 __file__ 向上找不到 cw_batch_stats.py(仓库根?)')


_gs = _load_stats_module()


def _game(rows: list[dict]) -> dict:
    """game_metrics 消费的最小局壳(末行即末帧,plane/round 无关判定)。"""
    return {'rows': rows, 'plane_reached': None, 'killed': None}


def _row(round_num: int = 9, *, locked_comp: str | None = '',
         p1_pair: tuple | None = (), form_ok: bool | None = None) -> dict:
    """统一行形状(sim 装配产物;locked_comp/p1_pair=None 形态 = 档案行)。"""
    return {'plane': 1, 'round': round_num, 'node_type': None,
            'gold': 66, 'hp': 30, 'form': None, 'form_ok': form_ok,
            'level': 6, 'locked_comp': locked_comp, 'p1_pair': p1_pair}


class TestCompDoneP1Proxy:
    """④ 判定分支矩阵(口径 = cw_batch_stats 模块 docstring ④ 节)。"""

    def test_game_metrics_comp_done_branch_matrix(self):
        """④ 判定分支矩阵三段并一。
        [代理活跃] 配方锁活跃(locked_comp 空 ∧ p1_pair 非空):
        ④ = 同行 form_ok,标 proxy;
        [零漂移] 未锁线(p1_pair 空):用户规格逐字 = 0,非代理(空窗
        ≠ 锁定);锁线帧(locked_comp 非空):既有 form_ok 分支,代理
        不辖(ADR-0357 语义零改的观测面半边:①资格锁/P2+ 判定不换道);
        [档案行] 结构性 None = 无数据;代理不可达(不把无数据虚构读成
        行为),不入分母。"""
        # [代理活跃]
        ok = _gs.game_metrics(_game(
            [_row(p1_pair=('仙舟', '列车同行'), form_ok=True)]))
        ng = _gs.game_metrics(_game([_row(p1_pair=('仙舟',), form_ok=False)]))
        assert ok['comp_done'] == 1
        assert ok['comp_proxy'] is True
        assert ng['comp_done'] == 0
        assert ng['comp_proxy'] is True
        # [零漂移]
        unl = _gs.game_metrics(_game(
            [_row(locked_comp='', p1_pair=(), form_ok=True)]))
        assert unl['comp_done'] == 0
        assert unl['comp_proxy'] is False
        lk0 = _gs.game_metrics(_game(
            [_row(locked_comp='不息之途', p1_pair=(), form_ok=False)]))
        lk1 = _gs.game_metrics(_game(
            [_row(locked_comp='不息之途', p1_pair=(), form_ok=True)]))
        assert lk0['comp_done'] == 0
        assert lk0['comp_proxy'] is False
        assert lk1['comp_done'] == 1
        assert lk1['comp_proxy'] is False
        # [档案行]
        ar = _gs.game_metrics(_game(
            [_row(locked_comp=None, p1_pair=None, form_ok=True)]))
        assert ar['comp_done'] is None
        assert ar['comp_proxy'] is False

    def test_sim_rows_end_to_end_carries_p1_pair(self, tmp_path: Path):
        # 装配链:decisions 行 v3_intention.p1_pair → row → ④ 代理可判
        dec = {'run_id': 'r1', 'plane': 1, 'round_num': 9, 'gold': 66,
               'hp': 30, 'form_ok': True,
               'v3_intention': {'phase': 'unlocked', 'locked_comp': '',
                                'p1_pair': ['仙舟', '列车同行']}}
        (tmp_path / 'decisions.jsonl').write_text(
            json.dumps(dec, ensure_ascii=False) + '\n', encoding='utf-8')
        games = _gs._sim_rows(tmp_path)
        m = _gs.game_metrics(games['r1'])
        assert m['comp_done'] == 1
        assert m['comp_proxy'] is True

    def test_game_metrics_prefers_round_end_snapshot_over_stale_mirror(self):
        """凑齐判定口径 = 行内 state 轮末快照现算优先,镜像回退(口径
        单一源 = 模块 docstring ②节;kernel 判据单一源 =
        cw_launch_admission.readiness_form_ok)。动机 =
        2026-09-15 批 4/300 低估实证:决策行 form_ok 是策略器镜像写端
        商店帧时点读数,轮内升级补位达标局恒 False——轮末快照现算
        翻正;反向快照已物化但未达标压制镜像 True。载体 =
        locked_comp 终局线帧(p1_pair 配方锁伪阵容路径已随配方决策层
        退役恒走「判据不可判 → 回退镜像」,快照现算面只在锁定线帧
        可达——skill 脚本 _readiness_from_snapshot docstring 已声明)。
        锁三件事:
        1. 轮末快照可算时覆盖镜像(②同源走 _row_form_ok)——满档 ∧
           点名件(定义件)在板 → 翻正;满档但点名件缺板 → 压制(点名件
           统一表达式进完备契约,required-deployed-retirement 后语义);
        2. p1_pair 帧(配方锁)现行恒回退镜像读数(伪阵容载体已退役);
        3. 快照缺输入回退镜像。"""
        line = '希儿量子'
        snap = _materialized_snapshot(line)
        # 翻正分支:镜像 False(stale),轮末板面已物化(满档+定义件在板) → 判真
        row_ok = _row(locked_comp=line, form_ok=False)
        row_ok['state_board_factions'] = snap['board_factions']
        row_ok['state_deployed'] = snap['deployed']
        m_ok = _gs.game_metrics(_game([row_ok]))
        assert m_ok['exit_form_ok'] is True
        assert m_ok['comp_done'] == 1
        assert m_ok['comp_proxy'] is False
        # 压制分支:镜像 True(stale),轮末板面物化但点名件缺板
        # (满档 ∧ 定义件不在板 → fp < 1.0)→ 判假
        row_ng = _row(locked_comp=line, form_ok=True)
        row_ng['state_board_factions'] = snap['board_factions']
        row_ng['state_deployed'] = []
        m_ng = _gs.game_metrics(_game([row_ng]))
        assert m_ng['exit_form_ok'] is False
        assert m_ng['comp_done'] == 0
        # p1_pair 帧(配方锁):伪阵容载体已退役 → 判据不可判 →
        # 回退镜像读数(现行语义锁,防「快照现算面复活」静默漂移)。
        row_p1 = _row(p1_pair=('仙舟', '列车同行'), form_ok=True)
        row_p1['state_board_factions'] = {'仙舟': 3, '列车同行': 2}
        row_p1['state_deployed'] = []
        m_p1 = _gs.game_metrics(_game([row_p1]))
        assert m_p1['exit_form_ok'] is True
        assert m_p1['comp_proxy'] is True

    def test_game_metrics_falls_back_to_mirror_without_snapshot(self):
        """回退分支显式锁:行缺轮末快照两键(旧批/档案形状)→ 判定 =
        form_ok 镜像读数,与既有口径逐位等价(禁静默改历史读数)。"""
        pair = ('仙舟', '列车同行')
        m = _gs.game_metrics(_game(
            [_row(p1_pair=pair, form_ok=True)]))
        assert m['exit_form_ok'] is True
        assert m['comp_done'] == 1


def _materialized_snapshot(line: str) -> dict:
    """按注册表档位现造「已物化」轮末快照(档位/点名件消费 kernel
    单一源,测试不手写 tier 值——registry 演进测试自动跟随;点名件 =
    定义件/core 统一表达式,与 form_progress 同式——
    required-deployed-retirement 后语义)。"""
    from sr_od.application.currency_war.kernel.cw_comps import (
        carry_anchor,
        get_comp,
    )
    comp = get_comp(line)
    assert comp is not None, f'终局线名未注册: {line}'
    board = {f: t for f, t in comp.core_faction_reqs.items() if t > 0}
    anchor = carry_anchor(comp)
    named = (anchor,) if anchor else tuple(comp.core_chars)
    deployed = [{'char_id': n} for n in named]
    return {'board_factions': board, 'deployed': deployed}
