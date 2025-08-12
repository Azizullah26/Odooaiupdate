from database import DatabaseManager, QueryLog
from odoo_client import OdooClient
from typing import List
#from nlp_processor import NLPProcessor

def test_nlp_processor():
    # Test OpenAI API integration in NLPProcessor
    #nlp = NLPProcessor()

    import requests

    response = requests.post("http://localhost:5005/model/parse", json={"text": "what is the update on the number of employees of the company"})
    print(response.json())


def test_db():
    # Existing DB test
    db = DatabaseManager()
    session = db.get_session()

    # Example: Get the 10 most recent queries
    recent_queries = session.query(QueryLog).order_by(QueryLog.timestamp.desc()).limit(10).all()

    for q in recent_queries:
        print(f"ID: {q.id}, Query: {q.query}, Type: {q.query_type}, Time: {q.timestamp}")

    session.close()


def get_fields():
    # ad-hoc script, or add a debug route in middleware
    odoo = OdooClient()
    fields = odoo.models.execute_kw(
        odoo.db, odoo.uid, odoo.password,
        'project.project', 'fields_get',
        [], {'attributes': ['string','type']}
    )
    print("project.project fields:", list(fields.keys()))

#get_fields()


def get_first_10_analytic_accounts(client: OdooClient) -> List[int]:
    if not client.uid:
        client.authenticate()

    project_ids = client.models.execute_kw(
        client.db, client.uid, client.password,
        'project.project', 'search',
        [[]],
        {'limit': 10}
    )
    if not project_ids:
        return []

    recs = client.models.execute_kw(
        client.db, client.uid, client.password,
        'project.project', 'read',
        [project_ids],
        {'fields': ['analytic_account_id']}
    )
    ids = []
    for r in recs:
        aa = r.get('analytic_account_id')
        ids.append(aa[0] if isinstance(aa, (list, tuple)) and aa else None)
    return ids

# Usage:

#first_10 = get_first_10_analytic_accounts(odoo)
#print(first_10)

def timesheet(client: OdooClient):
    ts_domain = [
        ['project_id', '=', 2842]
    ]
    print("hi5.1")
    ts_ids = client.models.execute_kw(
        client.db, client.uid, client.password,
        'account.analytic.line', 'search', [ts_domain]
    )
    ts_amount_total = 0.0
    print("hi5.2")
    if ts_ids:
        ts_recs = client.models.execute_kw(
            client.db, client.uid, client.password,
            'account.analytic.line', 'read', [ts_ids],
            {'fields': ['amount']}
        )
        ts_amount_total = sum(e.get('amount', 0.0) for e in ts_recs)
        print(ts_amount_total)
    else:
        print("no timesheet hours found")

def test_work_order_papers():
    """
    Ad-hoc test for OdooClient.work_order_papers:
      • attachments-only
      • invoices-only
      • purchase orders-only
      • all
    :contentReference[oaicite:1]{index=1}
    """
    from odoo_client import OdooClient

    client = OdooClient()
    if not client.authenticate():
        print("❌ Authentication to Odoo failed")
        return

    wo_ref = '00185'  # ← replace with a valid WO ref in your test DB
    for req in ('attachments', 'invoices', 'pos'):
        print(f"\n▶︎ work_order_papers(required='{req}')")
        try:
            payload = {'wo_ref_no': wo_ref, 'required': req}
            result = client.work_order_papers(payload)
            print(result)
        except Exception as e:
            print(f"❌ Error for required='{req}': {e}")
            


def test_summary_papers():
    # Ad-hoc test for summary_report.generate_papers_report :contentReference[oaicite:3]{index=3}
    import summary_report
    from odoo_client import OdooClient

    odoo = OdooClient()
    if not odoo.uid and not odoo.authenticate():
        print("❌ Authentication to Odoo failed")
        return

    print("▶︎ Generating papers report…")
    report = odoo.work_order_papers({'wo_ref_no': '00185', 'required': 'all'})
    md = summary_report.generate_papers_report(report)
    print(md)


def test_work_order_time():
    # Ad-hoc test for OdooClient.work_order_papers :contentReference[oaicite:2]{index=2}
    from odoo_client import OdooClient

    odoo = OdooClient()
    if not odoo.uid and not odoo.authenticate():
        print("❌ Authentication to Odoo failed")
        return

    print("▶︎ Running work_order_time…")
    # Use a valid WO reference in your test DB
    params = {'wo_ref_no': '00185', 'required': 'all'}
    result = odoo.work_order_time(params)
    print(result)


def test_summary_time():
    # Ad-hoc test for summary_report.generate_papers_report :contentReference[oaicite:3]{index=3}
    import summary_report
    from odoo_client import OdooClient

    odoo = OdooClient()
    if not odoo.uid and not odoo.authenticate():
        print("❌ Authentication to Odoo failed")
        return

    print("▶︎ Generating time report…")
    report = odoo.work_order_time({'wo_ref_no': '00185', 'required': 'all'})
    md = summary_report.generate_time_report(report)
    print(md)



def test_get_work_orders_by_date():
    # Ad-hoc test for get_work_orders with an exact date :contentReference[oaicite:3]{index=3}
    from odoo_client import OdooClient

    client = OdooClient()
    if not client.uid and not client.authenticate():
        print("❌ Authentication to Odoo failed")
        return

    print("\n▶︎ get_work_orders with date filter")
    # Replace '2025-07-01' with a date present in your test DB
    result = client.get_work_orders(['2025-04-20'])
    print(result)


def test_get_work_orders_by_client():
    # Ad-hoc test for get_work_orders filtering by client name :contentReference[oaicite:2]{index=2}
    from odoo_client import OdooClient
    import summary_report

    client = OdooClient()
    if not client.uid and not client.authenticate():
        print("❌ Authentication to Odoo failed")
        return

    print("\n▶︎ get_work_orders with client filter (first 10 only)")
    # Replace with a real partner name in your test DB
    odoo_result = client.get_work_orders(['Rafed Healthcare Supplies LLC'])

    if not odoo_result.get('success'):
        print("❌ Error:", odoo_result.get('error'))
        return

    # Take only the first 10 work order names
    all_orders = odoo_result.get('work_orders', [])
    limited_orders = all_orders[:10]

    # Build a new “limited” report payload
    limited_report = {
        'success': True,
        'data': {'work_orders': limited_orders}
    }

    # Render the markdown summary for just those ten :contentReference[oaicite:3]{index=3}
    summary_md = summary_report.generate_work_orders_report(limited_report)
    print(summary_md)



def test_get_work_orders_by_manager():
    # Ad-hoc test for get_work_orders filtering by project manager :contentReference[oaicite:5]{index=5}
    from odoo_client import OdooClient

    client = OdooClient()
    if not client.uid and not client.authenticate():
        print("❌ Authentication to Odoo failed")
        return

    print("\n▶︎ get_work_orders with manager filter")
    # Replace 'Jane Doe' with an employee name or ID in your test DB
    result = client.get_work_orders(['Mohammed W E Abuyousef'])
    print(result)


def test_work_order_details():
    
    from odoo_client import OdooClient

    client = OdooClient()
    if not client.authenticate():
        print("❌ Authentication to Odoo failed")
        return

    wo_ref = '00185'  # ← replace with a valid WO ref in your test DB
    for req in ('paid', 'unpaid', 'details'):
        try:
            payload = {'wo_ref_no': wo_ref, 'required': req}
            result = client.work_order_details(payload)
            print(result)
        except Exception as e:
            print(f"❌ Error for required='{req}': {e}")
            

def test_employess_report():
    # Ad-hoc test for summary_report.generate_papers_report :contentReference[oaicite:3]{index=3}
    import summary_report
    from odoo_client import OdooClient

    odoo = OdooClient()
    if not odoo.uid and not odoo.authenticate():
        print("❌ Authentication to Odoo failed")
        return

    print("▶︎ Generating papers report…")
    report = odoo.work_order_employees({'wo_ref_no': '00185', 'required': 'all'})
    md = summary_report.generate_employees_report(report)
    print(md)

if __name__ == "__main__":
    #test_get_work_orders_by_date()
    #test_get_work_orders_by_client()
    #test_get_work_orders_by_manager()
    #test_work_order_time()
    #test_work_order_papers()
    #test_summary_papers()
    #test_work_order_details()
    #test_employess_report()
    test_nlp_processor()

def generate_summary_report(self, project_header: Dict[str, Any], result: Dict[str, Any]) -> str:
        """
        If the last query was an expense request, render the full markdown
        report. Otherwise return an empty string.
        """
        #print(result)
        # Grab what we need out of the process_query output
        parsed_query = result.get('parsed_query', {})
        data = result.get('data',)
        #this is the odoo result
        #project_header  = header.get('header', {})
        odoo_result = data.get('result',{})

        # If the Odoo call failed, show its error
        if not result.get('success', False):
            return result.get('error', "")

        header = self.summary_report.generate_header(project_header)

        if parsed_query.get('intent') == 'work_order_finances':
            summary = self.summary_report.generate_expense_report(odoo_result)

        elif parsed_query.get('intent') == 'work_order_details':
            summary = self.summary_report.generate_details_report(odoo_result)

        elif parsed_query.get('intent') == 'work_order_papers':
            summary = self.summary_report.generate_papers_report(odoo_result)

        elif parsed_query.get('intent') == 'work_order_time':
            summary = self.summary_report.generate_time_report(odoo_result)

        elif parsed_query.get('intent') == 'get_work_orders':
            summary = self.summary_report.generate_work_orders_report(odoo_result)

            return summary

        elif parsed_query.get('intent') == 'work_order_employees':
            summary = self.summary_report.generate_employees_report(odoo_result)
            
        return header + "\n" + summary