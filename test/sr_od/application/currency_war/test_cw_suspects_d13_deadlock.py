"""D13 席满死锁收敛缺陷线检测器锁面(合取判据 + 锚点归属 + 行形状)。

出处 = sim/checks/suspects.py D13 docstring(判据 = 实机局 s77091 复盘
下钻的最小充分组合:连续 ≥2 轮线内件 missing_bench_full ∧ bench 含
同名 1★ 非线内对;拒因读波级 sim.shop_waves[].rejects 全量并,帧级
shop_rejects 只作生产合并行回退)。

锁的四件事:
1. 合取命中:连击 + 死库存对同时成立 → 恰一锚点条目(真实线注册表
   解析线成员);
2. 合取缺一零误报:单轮 / 无对 / 拒因全落线外 / 线内同名对 / 2★ 同名
   对 / 跨位面断连击,各形零条目;
3. 锚点归属:对迟现时锚点后移到首个同时成立轮,连击延伸轮落交叉
   引用行(D9 同款归属);
4. 行形状分派:波级缺失回退帧级;波级在场则帧级末波不参与判定
   (波级优先,末波 last-wins 不漏中波拒买)。
"""

from __future__ import annotations

from sr_od.application.currency_war.sim.checks.suspects import (
    d13_bench_full_deadlock,
)

_LINE = '过渡配方·仙舟+持续伤害'   # 真实线标签:k_members 经 bridge pool 解析
_PAIR = [('阿格莱雅', 1), ('阿格莱雅', 1)]   # 非线内同名 1★ 对(死库存候选)


def _row(rn: int, *, waves: list[dict] | None = None,
         rejects: dict[str, str] | None = None,
         bench: list[tuple[str, int]] | None = None,
         target: str = _LINE) -> dict:
    """构造最小 sim 行(waves = 波级 rejects 列表;rejects = 帧级)。"""
    row: dict = {
        'plane': 1, 'round_num': rn, 'target_comp': target,
        'state': {'bench': [{'char_id': n, 'star': s} for n, s in bench or []]},
        'actions': [], 'sim': {'node': 'shop'},
    }
    if waves is not None:
        row['sim']['shop_waves'] = [{'rejects': w} for w in waves]
    if rejects is not None:
        row['shop_rejects'] = rejects
    return row


def test_d13_flags_convergence_defect_line():
    """合取命中:连续两轮线内件席满拒 + 非线内 1★ 对 → 恰一锚点条目。"""
    rows = [
        _row(6, waves=[{'忘归人': 'missing_bench_full'}], bench=_PAIR),
        _row(7, waves=[{'符玄': 'missing_bench_full'}], bench=_PAIR),
    ]
    entries = d13_bench_full_deadlock(rows)
    assert len(entries) == 1
    e = entries[0]
    assert (e['plane'], e['round_num']) == (1, 7)   # 锚点 = 连击达成轮
    assert e['mode'] == 'D13'
    assert e['evidence']['rejected_line_names'] == ['符玄']
    assert e['evidence']['dead_star1_pairs'] == {'阿格莱雅': 2}
    assert e['evidence']['streak_rounds'] == 2
    assert e['evidence']['bench_used'] == 2   # 阿格莱雅×2(对本身占 2 席)


def test_d13_silent_without_conjunction():
    """合取缺一零误报:六种残缺形态全部零条目。"""
    # a) 单轮席满(连击不足)= 金/席硬闸合法拦截
    rows = [_row(6, waves=[{'忘归人': 'missing_bench_full'}], bench=_PAIR)]
    assert d13_bench_full_deadlock(rows) == []
    # b) 连击成立但 bench 无同名 1★ 非线内对
    rows = [_row(6, waves=[{'忘归人': 'missing_bench_full'}], bench=[]),
            _row(7, waves=[{'符玄': 'missing_bench_full'}], bench=[])]
    assert d13_bench_full_deadlock(rows) == []
    # c) 对在场但席满拒因全落线外名
    off_line = [_row(6, waves=[{'阿格莱雅': 'missing_bench_full'}],
                     bench=_PAIR),
                _row(7, waves=[{'阿格莱雅': 'missing_bench_full'}],
                     bench=_PAIR)]
    assert d13_bench_full_deadlock(off_line) == []
    # d) 线内同名 1★ 对 = 合法合成素材,不构成死对
    line_pair = [('停云', 1), ('停云', 1)]
    rows = [_row(6, waves=[{'忘归人': 'missing_bench_full'}],
                 bench=line_pair),
            _row(7, waves=[{'符玄': 'missing_bench_full'}],
                 bench=line_pair)]
    assert d13_bench_full_deadlock(rows) == []
    # e) 2★ 同名对不算 1★ 对(星级读法)
    star2 = [('阿格莱雅', 2), ('阿格莱雅', 2)]
    rows = [_row(6, waves=[{'忘归人': 'missing_bench_full'}], bench=star2),
            _row(7, waves=[{'符玄': 'missing_bench_full'}], bench=star2)]
    assert d13_bench_full_deadlock(rows) == []
    # f) 跨位面不续连击(round_num 跨面重启,行序轴按位面断开)
    p1_last = _row(9, waves=[{'忘归人': 'missing_bench_full'}], bench=_PAIR)
    p2_first = _row(1, waves=[{'忘归人': 'missing_bench_full'}],
                    bench=_PAIR)
    p2_first['plane'] = 2
    assert d13_bench_full_deadlock([p1_last, p2_first]) == []


def test_d13_anchor_at_first_pair_round_and_cross_refs():
    """对迟现:锚点后移到首个同时成立轮;延伸轮落交叉引用行(D9 同款)。"""
    rows = [
        _row(5, waves=[{'忘归人': 'missing_bench_full'}], bench=[]),
        _row(6, waves=[{'忘归人': 'missing_bench_full'}], bench=[]),
        _row(7, waves=[{'符玄': 'missing_bench_full'}], bench=_PAIR),
        _row(8, waves=[{'符玄': 'missing_bench_full'}], bench=_PAIR),
    ]
    entries = d13_bench_full_deadlock(rows)
    assert [(e['round_num'], e.get('cross_ref', False)) for e in entries] \
        == [(7, False), (8, True)]
    assert entries[0]['evidence']['streak_rounds'] == 3   # 锚点时连击长度
    assert entries[1]['anchor_round'] == 7


def test_d13_wave_level_vs_frame_level_rejects():
    """行形状分派:波级在场优先(末波 last-wins 不漏中波);缺波级回退帧级。"""
    # 波级中波拒因可达 + 帧级末波无席满拒 → 仍命中(s77091 R6 形态)
    rows = [
        _row(6, waves=[{'忘归人': 'missing_bench_full'},
                       {'阿格莱雅': 'non_line'}],
             rejects={'阿格莱雅': 'non_line'}, bench=_PAIR),
        _row(7, waves=[{'符玄': 'missing_bench_full'}],
             rejects={}, bench=_PAIR),
    ]
    assert len(d13_bench_full_deadlock(rows)) == 1
    # 生产合并行形状(无波级键):回退帧级 shop_rejects
    rows = [
        _row(6, rejects={'忘归人': 'missing_bench_full'}, bench=_PAIR),
        _row(7, rejects={'符玄': 'missing_bench_full'}, bench=_PAIR),
    ]
    assert len(d13_bench_full_deadlock(rows)) == 1
