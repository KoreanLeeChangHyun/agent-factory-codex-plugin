#!/usr/bin/env python3
"""Durable chat execution routing, observation and report delivery."""
from __future__ import annotations
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'runtime'))
from execution.cli import JsonArgumentParser, add_project_argument
from storage.files import emit, error_document
from storage.errors import ContractError
from tasks.conductor import Conductor
from tasks.conductor_backend import ManagedBackend


def build_parser():
    parser=JsonArgumentParser(prog='conductor.py',description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    for name in ('init','receive','reserve','dispatch','observe','decision','answer','switch-provider','retry','inspect','reports','status'):
        p=commands.add_parser(name)
        add_project_argument(p)
        p.add_argument('--chat-id',required=True)
        if name in {'init','receive','decision','answer','switch-provider','retry','inspect'}:
            p.add_argument('--input',type=Path,required=True,help='Exact JSON contract payload; credentials must use existing protected input')
        if name=='observe':
            p.add_argument('--input',type=Path,help='Goal-linked progress evidence bound to managed runId/taskRevision/source; status comes from exec.py')
        if name=='reserve':
            p.add_argument('--session-id',required=True)
        if name in {'dispatch','observe','decision','inspect'}:
            p.add_argument('--run-id',required=True)
        if name=='reports':
            p.add_argument('--consumer',required=True)
            p.add_argument('--ack',type=int,help='Persist last fully applied event sequence; replay uses stable event IDs')
    return parser


def main(argv=None):
    try:
        args=build_parser().parse_args(argv)
        c=Conductor(args.project_root,args.chat_id,runtime_home=args.runtime_home,project_id=args.project_id)
        payload=json.loads(args.input.read_text(encoding='utf-8')) if getattr(args,'input',None) else {}
        if args.command=='init': result=c.initialize(payload['settings'],payload['policy'])
        elif args.command=='receive': result=c.receive(payload)
        elif args.command=='reserve': result=c.reserve(args.session_id)
        elif args.command=='dispatch': result=c.dispatch(args.run_id,ManagedBackend(c))
        elif args.command=='observe': result=ManagedBackend(c).observe(args.run_id,payload)
        elif args.command=='decision': result=c.decision(args.run_id,payload)
        elif args.command=='answer': result=c.answer(payload)
        elif args.command=='switch-provider': result=c.switch_provider(payload['taskId'],payload['taskRevision'],payload['settings'])
        elif args.command=='retry': result=c.retry(payload['taskId'],payload['taskRevision'],reference=payload['reference'],failure_class=payload['failureClass'],max_attempts=payload.get('maxAttempts',1))
        elif args.command=='inspect': result=c.inspect(args.run_id,payload)
        elif args.command=='reports': result=c.reports(args.consumer,args.ack)
        else: result=c.snapshot()
        emit(result)
        return 0
    except ContractError as error:
        emit(error_document(error.code,error.message))
        return 2
    except (OSError,ValueError,KeyError,TypeError) as error:
        emit(error_document('conductor_input_invalid',str(error)))
        return 1


if __name__=='__main__':
    raise SystemExit(main())
