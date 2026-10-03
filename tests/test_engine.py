import copy
import json
import unittest
from pathlib import Path
from engine import analyze,clusters,eligible_runbooks,similarity,timestamp,validate_runbooks
from knowledge import capture,approve
from app import render
TICKETS=json.loads(Path('data/tickets.json').read_text());BOOKS=json.loads(Path('data/runbooks.json').read_text());NOW=timestamp('2026-10-03T00:00:00Z')
class EngineTests(unittest.TestCase):
    def test_demo_counts(self):
        r=analyze(TICKETS,BOOKS,NOW);self.assertEqual(r['open_backlog'],10);self.assertEqual(r['missing_owner'],2)
        self.assertEqual(r['sme_required'],6);self.assertEqual(r['reported_sme_wait_hours'],34)
    def test_severity_before_age(self):
        r=analyze(TICKETS,BOOKS,NOW);self.assertEqual(r['triage'][0]['ticket_id'],'LAB-007')
        self.assertGreater(r['triage'][-1]['age_days'],r['triage'][0]['age_days'])
    def test_missing_owner_within_priority(self):
        r=analyze(TICKETS,BOOKS,NOW);p3=[t for t in r['triage'] if t['priority']=='P3'];self.assertTrue(p3[0]['missing_owner']);self.assertTrue(p3[1]['missing_owner'])
    def test_context_boundaries(self):
        groups=clusters(TICKETS);redis=next(g for g in groups if g[0]['service']=='Redis');self.assertNotIn('LAB-011',[t['ticket_id'] for t in redis])
        ticket=dict(TICKETS[0],platform_version='different');self.assertEqual(eligible_runbooks(ticket,BOOKS,NOW),[])
    def test_drafts_not_suggested(self):self.assertEqual(eligible_runbooks(TICKETS[3],BOOKS,NOW),[])
    def test_expired_not_suggested(self):self.assertEqual(eligible_runbooks(TICKETS[8],BOOKS,NOW),[])
    def test_future_review_not_suggested(self):
        books=copy.deepcopy(BOOKS);books[0]['reviewed_at']='2026-10-04T00:00:00Z';self.assertEqual(eligible_runbooks(TICKETS[0],books,NOW),[])
    def test_review_expiry_boundary(self):self.assertEqual(eligible_runbooks(TICKETS[0],BOOKS,timestamp(BOOKS[0]['review_expires_at'])),[])
    def test_approved_suggestion(self):self.assertEqual(eligible_runbooks(TICKETS[0],BOOKS,NOW)[0]['runbook_id'],'RB-LAB-003')
    def test_recurring_gap(self):
        r=analyze(TICKETS,BOOKS,NOW);k=next(g for g in r['knowledge_gaps'] if g['service']=='Kafka');self.assertEqual(k['uncovered_open_ticket_ids'],['LAB-004','LAB-005'])
    def test_capture_and_review(self):
        d=capture(TICKETS[5],'author');self.assertEqual(d['status'],'draft');self.assertEqual(d['source_ticket_ids'],['LAB-006'])
        a=approve(d,'reviewer','tester',NOW);self.assertEqual(a['status'],'approved');self.assertEqual(d['status'],'draft')
    def test_incomplete_and_self_review_rejected(self):
        d=capture(TICKETS[5],'author');d['rollback_steps']=['TODO: validate']
        with self.assertRaises(ValueError):approve(d,'reviewer','tester',NOW)
        with self.assertRaises(ValueError):approve(capture(TICKETS[5],'author'),'author','tester',NOW)
    def test_review_unlocks_only_matching_context(self):
        draft=capture(TICKETS[5],'author-d')
        before=analyze(TICKETS,BOOKS,NOW)
        pending=analyze(TICKETS,[b for b in BOOKS if b['runbook_id']!=draft['runbook_id']]+[draft],NOW)
        reviewed=approve(draft,'reviewer-e','tester-f',NOW)
        after=analyze(TICKETS,[b for b in BOOKS if b['runbook_id']!=reviewed['runbook_id']]+[reviewed],NOW)
        self.assertEqual(len(before['knowledge_gaps']),3)
        self.assertEqual(len(pending['knowledge_gaps']),3)
        self.assertEqual(len(after['knowledge_gaps']),2)
        self.assertEqual(after['suggestion_coverage'],.4)
    def test_placeholder_test_evidence_rejected(self):
        draft=capture(TICKETS[5],'author-d');draft['validation_evidence']='TODO: attach evidence'
        with self.assertRaises(ValueError):approve(draft,'reviewer-e','tester-f',NOW)
    def test_open_capture_rejected(self):
        with self.assertRaises(ValueError):capture(TICKETS[0],'author')
    def test_historical_resolution(self):
        r=analyze(TICKETS,BOOKS,timestamp('2026-09-27T00:00:00Z'));self.assertIn('LAB-003',[t['ticket_id'] for t in r['triage']]);self.assertNotIn('LAB-007',[t['ticket_id'] for t in r['triage']])
    def test_duplicate_and_bad_data(self):
        with self.assertRaises(ValueError):analyze(TICKETS+[TICKETS[0]],BOOKS,NOW)
        rows=copy.deepcopy(TICKETS);rows[0]['sme_wait_hours']=-1
        with self.assertRaises(ValueError):analyze(rows,BOOKS,NOW)
    def test_empty(self):
        r=analyze([],[],NOW);self.assertEqual(r['open_backlog'],0);self.assertIsNone(r['suggestion_coverage'])
    def test_threshold_validation(self):
        with self.assertRaises(ValueError):analyze(TICKETS,BOOKS,NOW,cluster_threshold=0)
    def test_html_escape(self):
        rows=copy.deepcopy(TICKETS);rows[0]['symptom']='<script>alert(1)</script>'
        self.assertNotIn('<script>alert',render(analyze(rows,BOOKS,NOW)))
    def test_similarity_not_confidence(self):
        self.assertEqual(similarity('connection limit exhausted','connection limit exhausted'),1)
        self.assertEqual(similarity('',''),0)
if __name__=='__main__':unittest.main()
