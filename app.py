"""SupportOps: local simulator without a model or external services."""
import json
import sqlite3
import uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import agent
import time
from outcomes import summarize
import tickets

ROOT = Path(__file__).resolve().parent
DB = ROOT / "demo.sqlite3"


class ManagedConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def connect():
    db = sqlite3.connect(DB, factory=ManagedConnection)
    db.row_factory = sqlite3.Row
    return db


def initialize():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, status TEXT);
        CREATE TABLE IF NOT EXISTS payments (id TEXT PRIMARY KEY, order_id TEXT, cents INTEGER);
        CREATE TABLE IF NOT EXISTS proposals (id TEXT PRIMARY KEY, payment_id TEXT UNIQUE, status TEXT);
        INSERT OR IGNORE INTO orders VALUES ('ORD-1001', 'Delayed');
        INSERT OR IGNORE INTO payments VALUES ('PAY-01', 'ORD-1001', 4990);
        INSERT OR IGNORE INTO payments VALUES ('PAY-02', 'ORD-1001', 4990);
        INSERT OR IGNORE INTO orders VALUES ('ORD-1002', 'Delivered');
        INSERT OR IGNORE INTO payments VALUES ('PAY-03', 'ORD-1002', 2990);
        UPDATE orders SET status = 'Delayed' WHERE status = 'Retrasado';
        UPDATE orders SET status = 'Delivered' WHERE status = 'Entregado';
        """)
        tickets.seed(db)


def investigate(order_id, ticket):
    trace = []
    with connect() as db:
        row = db.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
        trace.append({'tool': 'get_order', 'result': dict(row) if row else None})
        if not row:
            return {'answer': 'Order not found. Please check the order ID.', 'trace': trace}
        payments = [dict(p) for p in db.execute('SELECT * FROM payments WHERE order_id = ? ORDER BY id', (order_id,))]
        trace.append({'tool': 'get_payments', 'result': payments})
        policy = 'POL-01: A suspected duplicate charge must be reviewed and requires human approval before a refund is simulated.'
        trace.append({'tool': 'search_policies', 'result': policy})
        result = {'ticket': ticket, 'trace': trace, 'answer': f'Order {order_id}: {row["status"]}. Found {len(payments)} payments. [POL-01]'}
        if len(payments) == 2 and payments[0]['cents'] == payments[1]['cents']:
            payment = payments[1]
            proposal_id = str(uuid.uuid4())
            db.execute("INSERT OR IGNORE INTO proposals VALUES (?, ?, 'pending')", (proposal_id, payment['id']))
            proposal = db.execute('SELECT * FROM proposals WHERE payment_id = ?', (payment['id'],)).fetchone()
            result['proposal'] = {**dict(proposal), 'amount': payment['cents'] / 100}
            result['answer'] += ' Possible duplicate: review both payments before approving. The shipping delay requires human follow-up.'
        else:
            result['answer'] += ' There is insufficient evidence of a duplicate charge; human review is recommended.'
        return result


def approve(proposal_id):
    with connect() as db:
        proposal = db.execute('SELECT * FROM proposals WHERE id = ?', (proposal_id,)).fetchone()
        if not proposal:
            raise ValueError('Unknown proposal')
        db.execute("UPDATE proposals SET status = 'approved' WHERE id = ? AND status = 'pending'", (proposal_id,))
        return {'status': 'approved', 'message': 'Simulated refund approved. No real money was transferred.'}


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, value):
        data = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/api/tickets':
            return self.respond(200, tickets.list_tickets(connect))
        if self.path == '/api/database':
            with connect() as db:
                db.execute('BEGIN')
                records = {
                    'tickets': [dict(row) for row in db.execute('SELECT * FROM tickets ORDER BY id')],
                    'decisions': [dict(row) for row in db.execute('SELECT d.*,i.ticket_id FROM decisions d JOIN investigations i ON i.id=d.investigation_id ORDER BY d.created_at DESC')],
                    'orders': [dict(row) for row in db.execute('SELECT id, status FROM orders ORDER BY id')],
                    'payments': [dict(row) for row in db.execute('SELECT id, order_id, cents FROM payments ORDER BY id')],
                    'proposals': [dict(row) for row in db.execute('''
                        SELECT p.id, p.payment_id, p.status, pay.order_id, pay.cents
                        FROM proposals p LEFT JOIN payments pay ON pay.id = p.payment_id
                        ORDER BY p.id''')],
                }
            return self.respond(200, records)
        pages = {'/': 'index.html', '/database': 'database.html'}
        if self.path not in pages:
            return self.respond(404, {'error': 'Unknown route'})
        data = (ROOT / pages[self.path]).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        started = time.monotonic()
        try:
            size = int(self.headers.get('Content-Length', 0))
            if size < 1 or size > 16000:
                raise ValueError('Request is empty or too large')
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError('A JSON object is required')
            if self.path == '/api/investigate':
                order_id, ticket = body.get('order_id'), body.get('ticket')
                ticket_id = body.get('ticket_id')
                if ticket_id:
                    with connect() as db:
                        selected = db.execute('SELECT * FROM tickets WHERE id=?', (ticket_id,)).fetchone()
                    if not selected:
                        raise ValueError('Unknown ticket')
                    order_id, ticket = selected['order_id'], selected['text']
                if not isinstance(order_id, str) or not isinstance(ticket, str) or not ticket.strip():
                    raise ValueError('Order ID and ticket are required')
                mode = body.get('mode', 'simulation')
                if mode not in ('simulation', 'ai', 'lmstudio'):
                    raise ValueError('Unknown mode')
                result = (agent.investigate(order_id.strip(), ticket.strip(), connect,
                          provider='lmstudio' if mode == 'lmstudio' else 'openai',
                          local_model=body.get('local_model')) if mode in ('ai', 'lmstudio')
                          else investigate(order_id.strip(), ticket.strip()))
                if mode == 'simulation':
                    result['metrics'] = {'latency_seconds': round(time.monotonic()-started, 3), 'input_tokens': 0, 'output_tokens': 0, 'api_calls': 0}
                result['case'] = summarize(result)
                if ticket_id:
                    tickets.save(connect, ticket_id, result)
            elif self.path == '/api/decision':
                if body.get('confirmed') is not True:
                    raise ValueError('Explicit human confirmation is required')
                result = tickets.decide(connect, body.get('investigation_id'), body.get('action'))
            elif self.path == '/api/approve':
                if body.get('confirmed') is not True:
                    raise ValueError('Explicit human confirmation is required')
                result = approve(body.get('proposal_id'))
            else:
                return self.respond(404, {'error': 'Unknown route'})
            self.respond(200, result)
        except (ValueError, TypeError) as exc:
            self.respond(400, {'error': str(exc)})
        except RuntimeError as exc:
            self.respond(502, {'error': str(exc)})


if __name__ == '__main__':
    initialize()
    print('SupportOps: http://127.0.0.1:8000 — Press Ctrl+C to stop', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8000), Handler).serve_forever()
