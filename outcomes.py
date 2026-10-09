"""Case labels derived from tool evidence and application state."""
def summarize(result):
    trace = result.get('trace', [])
    errors = [str(item['result']['error']) for item in trace
              if isinstance(item.get('result'), dict) and 'error' in item['result']]
    order = next((item['result'] for item in reversed(trace) if item['tool'] == 'get_order'), None)
    proposal = result.get('proposal')
    delayed = isinstance(order, dict) and order.get('status') == 'Delayed'
    if proposal and proposal['status'] == 'pending':
        status, reason = 'pending_approval', 'Review both payments before approving the simulated refund.'
    elif proposal and proposal['status'] == 'rejected':
        status, reason = 'escalated', 'The refund proposal was rejected and requires human review.'
    elif errors or not order or (isinstance(order, dict) and 'error' in order):
        status, reason = 'escalated', 'Verify the order ID or review the tool errors before continuing.'
    elif delayed:
        status, reason = 'escalated', 'Shipping is delayed and requires human follow-up.'
    elif any(item['tool'] == 'get_payments' for item in trace) and not proposal:
        status, reason = 'escalated', 'The billing concern needs human review; no refund proposal was created.'
    else:
        status, reason = 'resolved', 'The inquiry was answered using available order records.'
    return {'status': status, 'reason': reason, 'shipping_follow_up': delayed, 'errors': errors}
