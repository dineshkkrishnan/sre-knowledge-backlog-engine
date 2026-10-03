"""Generate a local backlog/knowledge dashboard. No network calls."""
import argparse
import html
import json
from pathlib import Path
from engine import analyze,timestamp

def esc(value):return html.escape(str(value),quote=True)

def table(headers,rows):
    return '<table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table>'

def render(report):
    cards=[('Open backlog',report['open_backlog']),('Missing owners',report['missing_owner']),('Blocked',report['blocked']),('SME required',report['sme_required']),('Reported SME wait hours',report['reported_sme_wait_hours']),('Runbook suggestion coverage',f"{report['suggestion_coverage']:.0%}" if report['suggestion_coverage'] is not None else 'N/A')]
    options='<option value="">All services</option>'+''.join(f'<option>{esc(s["service"])}</option>' for s in report['services'])
    rows=''
    for t in report['triage']:
        suggestions='; '.join(r['runbook_id']+' · similarity '+str(r['score'])+' · '+r['source'] for r in t['suggestions']) or 'Knowledge gap — no eligible match'
        cells=[t['ticket_id'],t['service'],t['priority'],t['age_days'],t['owner'] or 'UNASSIGNED','; '.join(t['reasons']),suggestions]
        rows+=f'<tr data-service="{esc(t["service"])}">'+''.join('<td>'+esc(v)+'</td>' for v in cells)+'</tr>'
    triage='<table><thead><tr>'+''.join('<th>'+h+'</th>' for h in ['Ticket','Service','Priority','Age/days','Owner','Reason','Approved runbook suggestions'])+'</tr></thead><tbody id="triageRows">'+rows+'</tbody></table>'
    recurring=table(['Service / environment','Pattern','Occurrences','Open','Source tickets'],[(g['service']+' / '+g['environment'],g['symptom'],g['occurrences'],g['open_count'],', '.join(g['ticket_ids'])) for g in report['recurring_patterns']])
    gaps=table(['Service','Knowledge gap','Uncovered open tickets','Next step'],[(g['service'],g['symptom'],', '.join(g['uncovered_open_ticket_ids']),g['next_step']) for g in report['knowledge_gaps']])
    services=table(['Service','Open','SME required','Reported SME wait/hours','Suggestion coverage'],[(s['service'],s['open'],s['sme_required'],s['reported_sme_wait_hours'],f"{s['suggestion_coverage']:.0%}") for s in report['services']])
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SRE Knowledge &amp; Backlog</title><style>body{margin:0;background:#f3f6fa;color:#152a42;font:15px system-ui}main{max-width:1250px;margin:auto;padding:28px}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}article,section{background:white;border:1px solid #dbe4ed;border-radius:12px;padding:20px}strong{display:block;font-size:30px;margin-top:8px}section{margin-top:20px;overflow:auto}h2{font-size:21px}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px;vertical-align:top;border-bottom:1px solid #e5eaf0}th{background:#f4f7fb}p{color:#53667c}select{padding:8px;font:inherit}button{font:inherit;padding:8px}@media(max-width:650px){main{padding:12px}.cards{grid-template-columns:repeat(2,1fr)}}[hidden]{display:none}</style><main><h1>SRE Knowledge &amp; Backlog</h1>''' + f'<p>Synthetic operational lab · Snapshot {esc(report["as_of"])} · No live integrations</p><div class="cards">'+''.join(f'<article>{esc(label)}<strong>{esc(value)}</strong></article>' for label,value in cards)+f'</div><section><h2>Backlog triage</h2><p>Severity first, then ownership gaps, then age. Blocked work needs coordination, not an invented urgency score.</p><label for="serviceFilter">Filter triage by service: </label><select id="serviceFilter">{options}</select>{triage}</section><section><h2>Recurring patterns</h2><p>Lexical candidates grouped within the same service, environment and platform version. These are not confirmed common causes.</p>{recurring}</section><section><h2>Knowledge-gap queue</h2>{gaps}</section><section><h2>SME dependency and knowledge coverage</h2>{services}</section><p>Suggestion coverage measures retrieval matches, not successful resolutions or reduced dependency. Review runbook prerequisites and stop conditions in the source JSON.</p><script>document.getElementById("serviceFilter").addEventListener("change",function(){{for(const row of document.querySelectorAll("#triageRows tr")){{row.hidden=this.value!==""&&row.dataset.service!==this.value;}}}});</script></main></html>'

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tickets',default='data/tickets.json');parser.add_argument('--runbooks',default='data/runbooks.json');parser.add_argument('--as-of',default='2026-10-03T00:00:00Z');parser.add_argument('--output',default='output');parser.add_argument('--cluster-threshold',type=float,default=.6);parser.add_argument('--search-threshold',type=float,default=.45)
    args=parser.parse_args()
    try:
        report=analyze(json.loads(Path(args.tickets).read_text()),json.loads(Path(args.runbooks).read_text()),timestamp(args.as_of),args.cluster_threshold,args.search_threshold)
        path=Path(args.output);path.mkdir(parents=True,exist_ok=True);(path/'report.json').write_text(json.dumps(report,indent=2)+'\n');(path/'dashboard.html').write_text(render(report));print(f'Dashboard: {path / "dashboard.html"}');print(f'Open: {report["open_backlog"]}; knowledge gaps: {len(report["knowledge_gaps"])}')
    except (ValueError,OSError,TypeError) as exc:parser.error(str(exc))
if __name__=='__main__':main()
