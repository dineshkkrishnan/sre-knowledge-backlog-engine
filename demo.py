"""Demonstrate knowledge-gap capture and local review, using fictional labels."""
import json
from pathlib import Path
from engine import analyze,timestamp
from knowledge import capture,approve

def main():
    tickets=json.loads(Path('data/tickets.json').read_text());books=json.loads(Path('data/runbooks.json').read_text());now=timestamp('2026-10-03T00:00:00Z')
    before=analyze(tickets,books,now)
    source=next(t for t in tickets if t['ticket_id']=='LAB-006')
    draft=capture(source,'author-d')
    with_draft=analyze(tickets,[b for b in books if b['runbook_id']!=draft['runbook_id']]+[draft],now)
    approved=approve(draft,'reviewer-e','tester-f',now)
    after=analyze(tickets,[b for b in books if b['runbook_id']!=approved['runbook_id']]+[approved],now)
    report=dict(scenario='Synthetic workflow; review/test names are fictional labels, not authenticated humans',source_ticket='LAB-006',draft_status=draft['status'],approved_status=approved['status'],before_gaps=len(before['knowledge_gaps']),gaps_with_unapproved_draft=len(with_draft['knowledge_gaps']),after_gaps=len(after['knowledge_gaps']),before_suggestion_coverage=before['suggestion_coverage'],after_suggestion_coverage=after['suggestion_coverage'],note='This demonstrates retrieval eligibility, not faster resolution or reduced real SME dependency.')
    path=Path('output');path.mkdir(exist_ok=True);(path/'workflow_demo.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
