"""撤销操作证据留存锁(熔断发生 → 分键在案可读回)。

覆盖面:①W209 卖出熔断(sell_breaker_preserved:谁/为何/保留了什么);
②干旱计数器买入不重置(drought_buy_no_reset:解锁流程审计面)。
record_defect 无 run_id 时 no-op——锁经 monkeypatch defects.record_defect
捕获行,零真实落盘(测试纪律)。
"""
from types import SimpleNamespace

from sr_od.application.currency_war.telemetry import undo_evidence


def _capture(monkeypatch) -> list[dict]:
    rows: list[dict] = []
    monkeypatch.setattr(undo_evidence.defects, 'record_defect',
                        lambda *a, **kw: rows.append(
                            {'args': a, **kw}))
    return rows


class TestSellBreakerEvidence:

    def test_breaker_row_recorded_and_readable(self, monkeypatch):
        """熔断发生 → 分键在案可读回:行含谁(char_id)/为何(拒因)/
        保留了什么(expected),且 L2 留证级。"""
        rows = _capture(monkeypatch)
        sess = SimpleNamespace(cw4_counters={})
        undo_evidence.record_sell_breaker_preserved(
            sess, char_id='藿藿',
            reason='fence:仙舟', channel='deploy_offtarget')
        assert len(rows) == 1
        row = rows[0]
        assert row['args'][0] == 'sell'
        assert row['args'][1] == 'sell_breaker_preserved'
        assert '藿藿' in row['observed']
        assert 'fence:仙舟' in row['observed']
        assert 'deploy_offtarget' in row['expected']
        assert row['severity'] == undo_evidence.defects.SEVERITY_L2_RECORD
        assert row['refs'][0]['key'] == 'sell_breaker|藿藿|fence:仙舟'


class TestDroughtNoResetEvidence:

    def test_buy_no_reset_row_recorded(self, monkeypatch):
        """买入不重置 → 分键在案可读回:成员/体系/当值摘要齐
        (干旱解锁流程审计面)。"""
        rows = _capture(monkeypatch)
        sess = SimpleNamespace(cw4_counters={})
        undo_evidence.record_drought_buy_no_reset(
            sess, member='三月七', system='列车同行', drought=7)
        assert len(rows) == 1
        row = rows[0]
        assert row['args'][0] == 'economy'
        assert row['args'][1] == 'drought_buy_no_reset'
        assert '三月七' in row['observed']
        assert '列车同行' in row['observed']
        assert '=7' in row['observed']
        assert 'pair_drought|列车同行|7|三月七' in row['refs'][0]['key']

    def test_zero_drought_no_row(self, monkeypatch):
        """干旱计数为 0(无审计诉求)⇒ 不落行(零噪声)。"""
        rows = _capture(monkeypatch)
        sess = SimpleNamespace(cw4_counters={})
        undo_evidence.record_drought_buy_no_reset(
            sess, member='三月七', system='列车同行', drought=0)
        assert rows == []
