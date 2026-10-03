"""Deterministic backlog triage and reviewed-knowledge retrieval for a local lab."""
import math
import re
from collections import Counter
from datetime import datetime,timezone

PRIORITIES={'P0':0,'P1':1,'P2':2,'P3':3,'P4':4}
STOP={'the','a','an','and','to','in','on','for','with','of','is','are','after','before'}
PROCEDURE_FIELDS=['prerequisites','diagnostic_steps','resolution_steps','validation_steps','rollback_steps','stop_conditions']

def timestamp(value):
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None:raise ValueError('Timestamp requires a timezone')
    return dt.astimezone(timezone.utc)

def tokens(text):
    return set(re.findall(r'[a-z0-9]+',text.lower()))-STOP

def similarity(left,right):
    a,b=tokens(left),tokens(right)
    return len(a&b)/len(a|b) if a|b else 0.0

def validate_tickets(rows):
    if not isinstance(rows,list):raise ValueError('Tickets must be a list')
    seen=set()
    for row in rows:
        required=['ticket_id','service','environment','platform_version','symptom','priority','status','created_at','owner','blocked','sme_required','sme_wait_hours']
        if not isinstance(row,dict) or not all(k in row for k in required):raise ValueError('Missing ticket fields')
        for key in ['ticket_id','service','environment','platform_version','symptom']:
            if not isinstance(row[key],str) or not row[key].strip():raise ValueError(f'Invalid {key}')
        if row['ticket_id'] in seen:raise ValueError('Duplicate ticket_id')
        seen.add(row['ticket_id'])
        if row['priority'] not in PRIORITIES or row['status'] not in {'open','resolved'}:raise ValueError('Invalid priority/status')
        if row['owner'] is not None and not isinstance(row['owner'],str):raise ValueError('Invalid owner')
        if type(row['blocked']) is not bool or type(row['sme_required']) is not bool:raise ValueError('Flags must be booleans')
        if type(row['sme_wait_hours']) not in (int,float) or not math.isfinite(row['sme_wait_hours']) or row['sme_wait_hours']<0:raise ValueError('Invalid SME wait')
        created=timestamp(row['created_at'])
        resolved=timestamp(row['resolved_at']) if row.get('resolved_at') else None
        if (row['status']=='resolved') != (resolved is not None):raise ValueError('Resolution timestamp/status mismatch')
        if resolved and resolved<created:raise ValueError('Resolution before creation')
    return rows

def validate_runbooks(rows):
    if not isinstance(rows,list):raise ValueError('Runbooks must be a list')
    seen=set()
    for row in rows:
        if not isinstance(row,dict):raise ValueError('Invalid runbook')
        for key in ['runbook_id','title','service','environment','platform_version','symptom','owner','status']:
            if not isinstance(row.get(key),str) or not row[key].strip():raise ValueError(f'Invalid runbook {key}')
        if row['runbook_id'] in seen:raise ValueError('Duplicate runbook_id')
        seen.add(row['runbook_id'])
        if row['status'] not in {'draft','approved','retired'}:raise ValueError('Invalid runbook status')
        if row['status']=='approved':
            for field in PROCEDURE_FIELDS:
                values=row.get(field)
                if not isinstance(values,list) or not values or not all(isinstance(v,str) and v.strip() and 'TODO' not in v.upper() for v in values):raise ValueError(f'Approved runbook missing {field}')
            for field in ['reviewer','tested_by','validation_evidence']:
                if not isinstance(row.get(field),str) or not row[field].strip():raise ValueError('Approved runbook lacks review/test record')
            if 'TODO' in row['validation_evidence'].upper():raise ValueError('Test evidence cannot be a placeholder')
            if row['reviewer']==row['owner'] or row['tested_by']==row['owner']:raise ValueError('Review/test labels must differ from author')
            if timestamp(row['review_expires_at'])<=timestamp(row['reviewed_at']):raise ValueError('Invalid review interval')
    return rows

def context(row):return tuple(row[k] for k in ['service','environment','platform_version'])

def eligible_runbooks(ticket,runbooks,as_of,threshold=.45):
    matches=[]
    for rb in runbooks:
        if rb['status']!='approved' or context(rb)!=context(ticket):continue
        if not timestamp(rb['reviewed_at'])<=as_of<timestamp(rb['review_expires_at']):continue
        match=similarity(ticket['symptom'],rb['symptom'])
        if match>=threshold:
            matches.append(dict(runbook_id=rb['runbook_id'],title=rb['title'],score=round(match,3),source=f"data/runbooks.json#{rb['runbook_id']}",prerequisites=rb['prerequisites'],stop_conditions=rb['stop_conditions']))
    return sorted(matches,key=lambda r:(-r['score'],r['runbook_id']))[:3]

def clusters(tickets,threshold=.6):
    """Greedy representative matching; prevents transitive similarity chaining."""
    groups=[]
    for ticket in sorted(tickets,key=lambda t:t['ticket_id']):
        group=next((g for g in groups if context(g[0])==context(ticket) and similarity(g[0]['symptom'],ticket['symptom'])>=threshold),None)
        if group is None:groups.append([ticket])
        else:group.append(ticket)
    return [g for g in groups if len(g)>=2]

def analyze(tickets,runbooks,as_of,cluster_threshold=.6,search_threshold=.45):
    validate_tickets(tickets);validate_runbooks(runbooks)
    if as_of.tzinfo is None:raise ValueError('as_of requires timezone')
    for value in [cluster_threshold,search_threshold]:
        if not math.isfinite(value) or not 0<value<=1:raise ValueError('Similarity thresholds must be in (0,1]')
    as_of=as_of.astimezone(timezone.utc)
    history=[t for t in tickets if timestamp(t['created_at'])<=as_of]
    opened=[t for t in history if not t.get('resolved_at') or timestamp(t['resolved_at'])>as_of]
    triage=[]
    for t in opened:
        age=(as_of-timestamp(t['created_at'])).days;unowned=not bool(t['owner'] and t['owner'].strip())
        suggestions=eligible_runbooks(t,runbooks,as_of,search_threshold)
        reasons=[f"{t['priority']} severity",f'{age} whole days old']
        if unowned:reasons.append('missing owner')
        if t['blocked']:reasons.append('blocked: coordinate next step')
        triage.append(dict(ticket_id=t['ticket_id'],service=t['service'],environment=t['environment'],priority=t['priority'],age_days=age,owner=t['owner'],missing_owner=unowned,blocked=t['blocked'],sme_required=t['sme_required'],symptom=t['symptom'],reasons=reasons,suggestions=suggestions))
    # Severity always outranks age. Ownership gaps are first within a severity.
    triage.sort(key=lambda t:(PRIORITIES[t['priority']],not t['missing_owner'],-t['age_days'],t['ticket_id']))
    recurring=[];gaps=[]
    for group in clusters(history,cluster_threshold):
        representative=group[0];group_ids={t['ticket_id'] for t in group};active=[t for t in opened if t['ticket_id'] in group_ids]
        uncovered=[t['ticket_id'] for t in active if not eligible_runbooks(t,runbooks,as_of,search_threshold)]
        item=dict(service=representative['service'],environment=representative['environment'],platform_version=representative['platform_version'],symptom=representative['symptom'],ticket_ids=sorted(group_ids),occurrences=len(group),open_count=len(active),uncovered_open_ticket_ids=uncovered)
        recurring.append(item)
        if uncovered:gaps.append(dict(item,next_step='Capture a reviewed procedure from a resolved example or schedule SME investigation'))
    services=[]
    for service in sorted({t['service'] for t in opened}):
        group=[t for t in opened if t['service']==service];rows=[t for t in triage if t['service']==service]
        services.append(dict(service=service,open=len(group),sme_required=sum(t['sme_required'] for t in group),reported_sme_wait_hours=sum(t['sme_wait_hours'] for t in group),suggestion_coverage=sum(bool(t['suggestions']) for t in rows)/len(rows)))
    return dict(as_of=as_of.isoformat(),open_backlog=len(opened),missing_owner=sum(t['missing_owner'] for t in triage),blocked=sum(t['blocked'] for t in opened),sme_required=sum(t['sme_required'] for t in opened),reported_sme_wait_hours=sum(t['sme_wait_hours'] for t in opened),suggestion_coverage=sum(bool(t['suggestions']) for t in triage)/len(triage) if triage else None,triage=triage,recurring_patterns=recurring,knowledge_gaps=gaps,services=services)
