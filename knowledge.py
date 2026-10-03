"""Capture closure notes as a draft, then apply explicit local review gates."""
import argparse
import copy
import json
from datetime import timedelta
from pathlib import Path
from engine import PROCEDURE_FIELDS,timestamp,validate_runbooks,validate_tickets

def capture(ticket,author):
    validate_tickets([ticket])
    if ticket['status']!='resolved':raise ValueError('Capture requires a resolved ticket')
    if not isinstance(author,str) or not author.strip():raise ValueError('Author required')
    closure=ticket.get('closure',{})
    draft=dict(runbook_id='RB-'+ticket['ticket_id'],title=ticket['symptom'],service=ticket['service'],environment=ticket['environment'],platform_version=ticket['platform_version'],symptom=ticket['symptom'],owner=author,status='draft',source_ticket_ids=[ticket['ticket_id']],validation_evidence=closure.get('validation_evidence','TODO: attach test evidence'))
    for field in PROCEDURE_FIELDS:draft[field]=closure.get(field,['TODO: capture and verify this section'])
    return draft

def approve(draft,reviewer,tested_by,at):
    if draft.get('status')!='draft':raise ValueError('Only drafts can be approved')
    result=copy.deepcopy(draft)
    result.update(status='approved',reviewer=reviewer,tested_by=tested_by,reviewed_at=at.isoformat(),review_expires_at=(at+timedelta(days=30)).isoformat())
    validate_runbooks([result]);return result

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    d=sub.add_parser('draft');d.add_argument('--ticket-id',required=True);d.add_argument('--author',required=True);d.add_argument('--tickets',default='data/tickets.json');d.add_argument('--output',required=True)
    a=sub.add_parser('approve');a.add_argument('--input',required=True);a.add_argument('--reviewer',required=True);a.add_argument('--tested-by',required=True);a.add_argument('--at',required=True);a.add_argument('--output',required=True)
    args=p.parse_args()
    try:
        if args.command=='draft':
            tickets=validate_tickets(json.loads(Path(args.tickets).read_text()));ticket=next((t for t in tickets if t['ticket_id']==args.ticket_id),None)
            if ticket is None:raise ValueError('Unknown ticket')
            result=capture(ticket,args.author)
        else:result=approve(json.loads(Path(args.input).read_text()),args.reviewer,args.tested_by,timestamp(args.at))
        path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2)+'\n');print(path)
    except (ValueError,OSError,TypeError) as exc:p.error(str(exc))
if __name__=='__main__':main()
