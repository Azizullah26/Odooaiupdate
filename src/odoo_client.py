import xmlrpc.client
import socket
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import re
import calendar

logger = logging.getLogger(__name__)

class TimeoutTransport(xmlrpc.client.Transport):
    """Custom transport with timeout for XML-RPC connections."""
    def __init__(self, timeout=10):
        super().__init__()
        self.timeout = timeout
    
    def make_connection(self, host):
        connection = super().make_connection(host)
        if hasattr(connection, 'sock') and connection.sock:
            connection.sock.settimeout(self.timeout)
        return connection

class OdooClient:
    """Client for connecting to Odoo ERP via XML-RPC API."""
    
    def __init__(self):
        """Initialize Odoo client with connection parameters."""
        self.url = os.getenv("ODOO_URL", 'https://test.elrace.com')
        self.db = os.getenv("ODOO_DATABASE", 'test.elrace.com')
        self.username = os.getenv("ODOO_USERNAME", 'jawad@elrace.com')
        self.password = os.getenv("ODOO_PASSWORD", '272127212721')

        
        # Initialize RPC clients
        self.common: Any = None
        self.models: Any = None
        self.uid: Any = None
        
        self._initialize_connection()
    
    def _initialize_connection(self):
        """Initialize XML-RPC connection to Odoo."""
        try:
            # Clean URL format
            if not self.url.startswith(('http://', 'https://')):
                self.url = f"http://{self.url}"
            
            if not self.url.endswith('/'):
                self.url += '/'
            
            # Initialize RPC endpoints with timeout
            #timeout_transport = TimeoutTransport(timeout=10)
            self.common = xmlrpc.client.ServerProxy(f"{self.url}xmlrpc/2/common") #,transport=timeout_transport
            self.models = xmlrpc.client.ServerProxy(f"{self.url}xmlrpc/2/object") #,transport=timeout_transport
            
            logger.info(f"Initialized Odoo client for URL: {self.url}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Odoo connection: {str(e)}")
            raise
    
    def authenticate(self) -> bool:
        """Authenticate with Odoo and get user ID."""
        try:
            if not self.common:
                self._initialize_connection()
            
            self.uid = self.common.authenticate(self.db, self.username, self.password, {})
            
            if self.uid:
                logger.info(f"Successfully authenticated as user ID: {self.uid}")
                return True
            else:
                logger.error("Authentication failed - invalid credentials")
                return False
                
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return False
    
    def test_connection(self) -> bool:
        """Test connection to Odoo."""
        try:
            logger.info(f"Testing connection to Odoo at: {self.url}")
            logger.info(f"Database: {self.db}, Username: {self.username}")
            
            if not self.uid:
                if not self.authenticate():
                    logger.error("Authentication failed during connection test")
                    return False
            
            # Test by checking Odoo version
            version = self.common.version()
            logger.info(f"Successfully connected to Odoo version: {version}")
            return True
            
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            logger.error(f"URL: {self.url}, DB: {self.db}")
            return False
    
    def work_order_header(self, entities: Dict[str, str]):
        try:
            # 1) Make sure we're authenticated
            if not self.uid and not self.authenticate():
                raise Exception("Odoo authentication failed")

            #print(entities)
            wo_ref_no = entities.get('wo_ref_no','').lower()

            #if project_id is None:
            project_id = self.models.execute_kw(
                self.db, self.uid, self.password,
                'project.project', 'search',
                [[['wo_ref_no', '=', wo_ref_no]]]
            )
            #print("hi")
            if not project_id:
                return {
                    'success': False,
                    'error': f'Work order "{wo_ref_no}" not found'
                }

            # 4) Read header fields from the project
            proj = self.models.execute_kw(
                self.db, self.uid, self.password,
                'project.project', 'read',
                [project_id],
                {'fields': [
                    'id', 'name', 'create_date', 'create_uid',
                    'wo_amount', 'partner_id',
                    'agreement_id', 'city_id', 'wo_type'
                ]}
            )[0]
            #print("hi2")
            project_header = {
                'id':            proj['id'],
                'name':          proj['name'],
                'create_date':   proj['create_date'],
                'create_uid':    proj['create_uid'] and proj['create_uid'][1],
                'wo_amount':     proj.get('wo_amount', 0.0),
                'client_name':  proj['partner_id'] and proj['partner_id'][1],
                'contract': proj['agreement_id'] and proj['agreement_id'][1],
                'city': proj['city_id'] and proj['city_id'][1],
                'wo_type': proj['wo_type']
            }

            return {'success': True, 'project_header': project_header}

        except Exception as e:
            logger.error(f"work_order_header failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }          

    def work_order_finances(self, entities: Dict[str, str]) -> Dict[str, Any]:
        """
        entities: list of values extracted from the user (e.g. ["expense","00185"])
        
        Returns:
          {
            'success': True,
            'data': {
              'header': { … },
              # expense branch:
              'purchase_orders': [...],
              'petty_cash_total': X,
              'timesheet_hours_total': Y,
              # cost branch:
              'cost': Z
            }
          }
        """
        try:
            # 1) Make sure we're authenticated
            if not self.uid and not self.authenticate():
                raise Exception("Odoo authentication failed")

            #print(entities)
            wo_ref_no = entities.get('wo_ref_no','').lower()
            required = entities.get('required','').lower()

            #if project_id is None:
            project_id = self.models.execute_kw(
                self.db, self.uid, self.password,
                'project.project', 'search',
                [[['wo_ref_no', '=', wo_ref_no]]]
            )
            #print("hi")
            if not project_id:
                return {
                    'success': False,
                    'error': f'Work order "{wo_ref_no}" not found'
                }

            # 4) Read header fields from the project
            proj = self.models.execute_kw(
                self.db, self.uid, self.password,
                'project.project', 'read',
                [project_id],
                {'fields': [
                    'id', 'wo_amount',
                    'analytic_account_id',
                    'project_eng_amount',
                    'mechanical_eng_amount',
                    'electrical_eng_amount',
                    'it_eng_amount'
                ]}
            )[0]
            
            # 7) Search for purchase orders linked 
            po_domain = [
                ['project_id', '=', proj['id']],
                ['order_id.state', '=', 'done']
                ]
            po_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'purchase.order.line', 'search', [po_domain]
            )
            #print("hi4")

            purchase_orders = []
            if po_ids:
                po_recs = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'purchase.order.line', 'read',
                    [po_ids],
                    {'fields': [
                        'order_id', 'create_date', 'create_uid',
                        'partner_id', 'price_subtotal',
                        'price_tax', 'price_total', 
                    ]}
                )
                for po in po_recs:
                    purchase_orders.append({
                        'order_id':             po['order_id'],
                        'create_date':    po['create_date'],
                        'create_uid':     po['create_uid'] and po['create_uid'][1],
                        'partner_name':   po['partner_id'] and po['partner_id'][1],
                        'price_subtotal':   po.get('price_subtotal', 0.0),
                        'price_tax':     po.get('price_tax', 0.0),
                        'price_total':   po.get('price_total', 0.0)
                    })

            #print("hi4")

            # 5) Petty Cash (done sheets only)
            exp_domain = [
                ['analytic_account_id', '=', 'analytic_account_id'],
                ['sheet_id.state', '=', 'done']
            ]
            #print("hi4.1")
            exp_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'hr.expense', 'search', [exp_domain]
            )
            #print("hi4.2")
            petty_cash_total = 0.0
            if exp_ids:
                exp_recs = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'hr.expense', 'read', [exp_ids],
                    {'fields': ['amount']}
                )
                petty_cash_total = sum(e.get('amount', 0.0) for e in exp_recs)

            #print("hi5")
            # 6) Timesheet total amount
            ts_domain = [
                ['project_id', '=', proj['id']]
            ]
            #print("hi5.1")
            ts_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'account.analytic.line', 'search', [ts_domain]
            )
            #print(ts_ids)
            ts_amount_total = 0.0
            #print("hi5.2")
            if ts_ids:
                ts_recs = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'account.analytic.line', 'read', [ts_ids],
                    {'fields': ['amount']}
                )
                if isinstance(ts_recs, list):
                    ts_amount_total = sum(e.get('amount', 0.0) for e in ts_recs)
                else:
                    ts_amount_total = float(ts_recs) if ts_recs is not None else 0.0

                ts_amount_total = abs(ts_amount_total)

            #the expense distribution
            dist = {
                'project_eng_amount':     proj.get('project_eng_amount', 0.0),
                'mechanical_eng_amount':  proj.get('mechanical_eng_amount', 0.0),
                'electrical_eng_amount':  proj.get('electrical_eng_amount', 0.0),
                'it_eng_amount':          proj.get('it_eng_amount', 0.0)
            }
            dist['total_eng_amount'] = sum(dist.values())

            if dist['total_eng_amount'] > proj.get('wo_amount'):
                profit = "LOSS"
            else: 
                profit = "GAIN"


            # Return structured data for your “header” + required
            result_data: Dict[str, Any] = {}

            match required:
                case "expense":
                    result_data.update({
                    'purchase_orders': purchase_orders,
                    'petty_cash_total': petty_cash_total,
                    'timesheet_hours_total': ts_amount_total
                    })

                case "cost":
                    result_data['cost'] = proj.get('wo_amount')
                    
                case "profit":
                    result_data.update({
                    'distribution': dist,
                    'profit': profit})

                case "distribution":
                    result_data.update({'distribution': dist})
                
                case _:
                    result_data.update({
                    'purchase_orders': purchase_orders,
                    'petty_cash_total': petty_cash_total,
                    'timesheet_hours_total': ts_amount_total,
                    'cost' : proj.get('wo_amount'),
                    'profit': profit,
                    'distribution': dist
                    })            

            return {
                'success': True,
                'data': result_data
            }

        except Exception as e:
            logger.error(f"work_order_finance failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    #def verify_user_permission(self, user_id: int, intent: str) -> Dict[str, Any]:

        """
        Checks hr.employee for this user_id, and whether `intent`
        is listed in their allowed_access (a comma-separated string).
        Returns { success: bool, error or data }.
        """

        #check what are the tables in the database
        try:
            if not self.uid and not self.authenticate():
                raise Exception("Odoo authentication failed")

            # 1) fetch the registration record and job_id
            reg_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'hr.employee', 'search',
                [[['emp_id', '=', user_id]]]
            )
            if not reg_ids:
                return {'success': False,
                        'error': f'Employee {user_id} not registered.'}

            reg = self.models.execute_kw(
                self.db, self.uid, self.password,
                'hr.employee', 'read',
                [reg_ids],
                {'fields': ['job_id']}
            )[0]

            # 2) search and fetch for the job_title?
            job_id = reg.get(['job_id'])
            job_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'hr.job', 'search',
                [[['job_id', '=', job_id]]]
            )
            if not job_ids:
                return {'success': False,
                        'error': f'Job ID {job_id} is not registered.'}

            job = self.models.execute_kw(
                self.db, self.uid, self.password,
                'hr.job', 'read',
                [job_ids],
                {'fields': ['job_title']}
            )[0]

            #CONTINUE WORKING FROM HERE BASED ON THE INFORMATION IS THE DB AND AUTHORIZATIONS
 
            # 3) parse allowed_access
            allowed = reg.get('allowed_access') or ''
            # assume comma-separated list of intent names
            allowed_list = [a.strip() for a in allowed.split(',') if a.strip()]

            if intent not in allowed_list:
                return {'success': False,
                        'error': f'You are not authorized to perform "{intent}".'}

            # authorized
            return {'success': True, 'data': None}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_work_orders(self, entities: Dict[str, str]) -> Dict[str, Any]:
        """
        Given a list of extracted entities (e.g. ["ACME Corp", "2025-07-01"]),
        return all matching work order names by:
          • Client name → lookup res.partner → project.project.partner_id
          • Project manager (name or numeric ID) → lookup hr.employee → project.project.user_id
          • Start date → project.project.date_start

        Returns:
          { success: True, data: { work_orders: [ "WO123", "WO124", … ] } }
        or
          { success: False, error: "…message…" }
        """
        try:
            # 1) Ensure authenticated
            if not self.uid and not self.authenticate():
                return {'success': False, 'error': 'Authentication failed.'}

            # Prepare to collect found project IDs
            proj_ids = []

            # 2) Scan for a date pattern:
            #    • YYYY or YYYY-MM(-DD)
            #    • “MonthName YYYY” or “Mon YYYY”
            date_val = None
            date_type = None  # 'year', 'month', or 'exact'
            for e in entities:
                e_clean = e.strip()
                # 1) Full ISO date
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", e_clean):
                    date_val, date_type = e_clean, 'exact'
                    break
                # 2) Year or year-month numeric
                if re.fullmatch(r"\d{4}(?:-\d{2})?", e_clean):
                    date_val, date_type = e_clean, 'month' if '-' in e_clean else 'year'
                    break
                # 3) Month name + year
                m = re.fullmatch(r"([A-Za-z]+)\s+(\d{4})", e_clean)
                if m:
                    mon, yr = m.group(1).lower(), int(m.group(2))
                    month_map = {
                        **{calendar.month_name[i].lower(): i for i in range(1,13)},
                        **{calendar.month_abbr[i].lower(): i for i in range(1,13)}
                    }
                    if mon in month_map:
                        date_val = (month_map[mon], yr)
                        date_type = 'named_month'
                        break

            if date_val:
                if date_type == 'exact':
                    domain = [[ 'date_start', '=', date_val ]]
                elif date_type == 'year':
                    start = f"{date_val}-01-01"
                    end   = f"{date_val}-12-31"
                    domain = [
                        ['date_start', '>=', start],
                        ['date_start', '<=', end]
                    ]
                elif date_type == 'month':
                    year, month = map(int, date_val.split('-'))
                    last = calendar.monthrange(year, month)[1]
                    start = f"{year}-{month:02d}-01"
                    end   = f"{year}-{month:02d}-{last:02d}"
                    domain = [
                        ['date_start', '>=', start],
                        ['date_start', '<=', end]
                    ]
                else:  # 'named_month'
                    month, year = date_val
                    last = calendar.monthrange(year, month)[1]
                    start = f"{year}-{month:02d}-01"
                    end   = f"{year}-{month:02d}-{last:02d}"
                    domain = [
                        ['date_start', '>=', start],
                        ['date_start', '<=', end]
                    ]

                proj_ids = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'project.project', 'search',
                    [domain]
                )

            # 3) If no date filter, look for a client name
            if not proj_ids:
                for ent in entities:
                    # try partner lookup
                    partner_ids = self.models.execute_kw(
                        self.db, self.uid, self.password,
                        'res.partner', 'search',
                        [[[ 'name', 'ilike', ent ]]]
                    )
                    if partner_ids:
                        proj_ids = self.models.execute_kw(
                            self.db, self.uid, self.password,
                            'project.project', 'search',
                            [[[ 'partner_id', 'in', partner_ids ]]]
                        )
                        break

            # 4) If still none, look for a project manager
            if not proj_ids:
                for ent in entities:
                    # numeric → treat as employee ID
                    if ent.isdigit():
                        emp_ids = [int(ent)]
                    else:
                        # string → search by name
                        emp_ids = self.models.execute_kw(
                            self.db, self.uid, self.password,
                            'res.users', 'search',
                            [[[ 'name', 'ilike', ent ]]]
                        )
                    if emp_ids:
                        # assume project.project.user_id is the manager field
                        proj_ids = self.models.execute_kw(
                            self.db, self.uid, self.password,
                            'project.project', 'search',
                            [[[ 'user_id', 'in', emp_ids ]]]
                        )
                        break

            # 5) If still no filter matched, return error
            if not proj_ids:
                return {
                    'success': False,
                    'error': 'No valid client, project manager, or start date found in your query.'
                }

            # 6) Read the WO ref and the name of each project
            proj_recs = self.models.execute_kw(
                self.db, self.uid, self.password,
                'project.project', 'read',
                [proj_ids],
                {'fields': ['wo_ref_no', 'name']}
            )

            work_orders = [
                {
                    'wo_ref_no': rec.get('wo_ref_no'),
                    'name':      rec.get('name')
                }
                for rec in proj_recs
            ]

            return {
                'success': True,
                'work_orders': work_orders,               
                'count':       len(work_orders)
            }

        except Exception as e:
            logger.error(f"Failed to get project: {str(e)}")
            return {'success': False, 'error': str(e)}

    def work_order_details(self, entities: Dict[str, str]) -> Dict[str, Any]:
        try:
            # 1️⃣ Authenticate
            if not self.uid and not self.authenticate():
                return {'success': False, 'error': 'Authentication failed.'}

            wo_ref_no = entities.get('wo_ref_no','').lower()
            required = entities.get('required','').lower()

            proj_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'project.project', 'search',
                [[['wo_ref_no', '=', wo_ref_no]]]
            )
            if not proj_ids:
                return {'success': False,
                        'error': f'Work order "{wo_ref_no}" not found.'}

            # 3️⃣ Read the project header & timeline
            proj = self.models.execute_kw(
                self.db, self.uid, self.password,
                'project.project', 'read',
                [proj_ids],
                {'fields': [
                    'id',
                    'name',
                    'wo_amount',
                    'partner_id',
                    'create_date',
                    'create_uid',
                    'date_start',      # project start
                    'date',            # project end
                    'estimated_duration',
                    'user_id',         # project manager
                    'analytic_account_id'
                ]}
            )[0]

            # 4️⃣ Flatten into details dict
            project_id = proj['id']
            details = {
                'start_date':       proj.get('date_start'),
                'end_date':         proj.get('date'),
                'duration':         proj.get('estimated_duration'),
                'project_manager':  proj['user_id'][1] if proj.get('user_id') else None
            }

            # ── Invoices ──────────────────────────────────────────
            inv_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'account.move', 'search',
                # domain: project_id equals our single project_id
                [[['project', '=', project_id]]]
            )
            inv_items = []
            if inv_ids:
                recs = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'account.move', 'read',
                    [inv_ids],
                    {'fields': [
                        'id', 'name', 'invoice_date',
                        'amount_total', 'partner_id',
                        'client', 'payment_state'
                    ]}
                )
                for r in recs:
                    inv_items.append({
                        'id':            r['id'],
                        'number':        r['name'],
                        'invoice_date':          r.get('invoice_date'),
                        'vendor':        (r['partner_id'][1] if r.get('partner_id') else None),
                        'total_amount':  r.get('amount_total', 0.0),
                        'client':        r.get('client'),
                        'payment_state': r.get('payment_state')
                    })

            # ── Purchase Order Lines ───────────────────────────────────
            po_line_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'purchase.order.line', 'search',
                [[['project_id', '=', project_id]]]
            )
            po_items = []
            if po_line_ids:
                po_recs = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'purchase.order.line', 'read',
                    [po_line_ids],
                    {'fields': [
                        'order_id',      # tuple [id, name]
                        'partner_id',
                        'price_total',
                        'state'
                    ]}
                )
                for po in po_recs:
                    po_items.append({
                        'order_id':    po['order_id'],  # keep [id, name]
                        'partner':     (po['partner_id'][1] if po.get('partner_id') else None),
                        'price_total':       po.get('price_total', 0.0),
                        'state':       po.get('state')
                    })
                    
                

            # ── 6️⃣ Branch on required group ───────
            result_data: Dict[str, Any] = {}

            match required:
                case 'details':
                    result_data['details'] = details

                case 'paid':
                    # POs in state 'purchase' or 'done'
                    paid_pos = [po for po in po_items 
                                if po.get('state') in ('purchase', 'done')]
                    # Invoices in payment_state 'paid' or 'partial'
                    paid_invs = [inv for inv in inv_items 
                                if inv.get('payment_state') in ('paid', 'partial')]

                    result_data['purchase_orders'] = paid_pos
                    result_data['invoices']        = paid_invs

                case 'unpaid' | 'unfinished':
                    # POs in state 'to approve' or 'approved'
                    unpaid_pos = [po for po in po_items  
                                if po.get('state') in ('to approve', 'approved')]
                    # Invoices in payment_state 'not_paid' or 'in_payment'
                    unpaid_invs = [inv for inv in inv_items 
                                if inv.get('payment_state') in ('not_paid', 'in_payment')]

                    result_data['purchase_orders'] = unpaid_pos
                    result_data['invoices']        = unpaid_invs

                case _:
                    # default: return everything
                    balance = details['wo_amount'] - sum(po.get('amount_total', 0.0) for po in po_items )
                    result_data.update({
                        'details':          details,
                        'purchase_orders':  po_items ,
                        'invoices':         inv_items,
                        'balance':          balance
                    })

            return {'success': True, 'data': result_data}

        except Exception as e:
            logger.error(f"work_order_details failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def work_order_time(self, entities: Dict[str, str]) -> Dict[str, Any]:
        """
        entities: a list of strings extracted from the user query.
        
        Looks for the keyword "start_date" or "duration" in the entities.
        Also extracts either a numeric project ID or a WO reference from entities.
        
        Returns:
          { success: True, data: { start_date?: str, duration?: Any } }
        or on error:
          { success: False, error: "…" }
        """
        try:
            # 1) Authenticate
            if not self.uid and not self.authenticate():
                return {'success': False, 'error': 'Authentication failed.'}

            # 2️⃣ Extract the work-order ref and required field
            wo_ref_no = entities.get('wo_ref_no', '').strip()
            if not wo_ref_no:
                return {'success': False,
                        'error': 'No work-order reference provided.'}

            required = entities.get('required', '').strip().lower()

            # 3️⃣ Figure out which field(s) they want
            req_start = required in ('start date')
            req_end   = required in ('end date')
            req_dur   = required in ('duration')

            any_specific = req_start or req_end or req_dur
            fetch_start  = req_start or not any_specific
            fetch_end    = req_end   or not any_specific
            fetch_dur    = req_dur   or not any_specific

            # 4️⃣ Find the project by WO ref
            proj_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'project.project', 'search',
                [[[ 'wo_ref_no', '=', wo_ref_no ]]]
            )
            if not proj_ids:
                return {'success': False,
                        'error': f'Work order "{wo_ref_no}" not found.'}

            # 5️⃣ Only read the needed fields
            fields = []
            if fetch_start: fields.append('date_start')
            if fetch_end:   fields.append('date')
            if fetch_dur:   fields.append('estimated_duration')

            proj = self.models.execute_kw(
                self.db, self.uid, self.password,
                'project.project', 'read',
                [proj_ids],
                {'fields': fields}
            )[0]

            # 6️⃣ Build the response
            data: Dict[str, Any] = {}
            if fetch_start:
                data['start_date'] = proj.get('date_start')
            if fetch_end:
                data['end_date']   = proj.get('date')
            if fetch_dur:
                data['duration']   = proj.get('estimated_duration')
                return {
                    'success': True,
                    'data': data
                }

        except Exception as e:
            logger.error(f"time_taken failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

        """
        Based on the user’s entities list, return:
          • status: the project’s state field
          • progress: percent of duration elapsed since create_date

        If the user asked only for "status" → only status.
        If only for "progress" → only progress.
        If neither or both → both.

        Returns:
          { success: True, data: { status?: str, progress?: float } }
        or on error:
          { success: False, error: "…" }
        """
        # 1️⃣ Authenticate
        if not self.uid and not self.authenticate():
            return {'success': False, 'error': 'Authentication failed.'}

        # 2️⃣ Determine which field(s) are required
        want_status   = any(e.lower() == 'status'   for e in entities)
        want_progress = any(e.lower() == 'progress' for e in entities)
        # If neither or both, fetch both
        fetch_status   = want_status   or not (want_status ^ want_progress)
        fetch_progress = want_progress or not (want_status ^ want_progress)

        # 3️⃣ Extract project identifier
        project_id: Optional[int] = None
        wo_ref_no: Optional[str] = None
        for e in entities:
            if re.fullmatch(r'\d+', e):
                project_id = int(e)
                break
        if project_id is None:
            for e in entities:
                if e.strip().lower() not in ('status','progress'):
                    wo_ref_no = e.strip()
                    break
        if project_id is None and not wo_ref_no:
            return {
                'success': False,
                'error': 'No project ID or work-order reference provided.'
            }

        # 4️⃣ Search for the project
        domain: List[Any] = [['active', '=', True]]
        if project_id:
            domain.append(['id', '=', project_id])
        else:
            domain.append(['wo_ref_no', '=', wo_ref_no])
        proj_ids = self.models.execute_kw(
            self.db, self.uid, self.password,
            'project.project', 'search', [domain]
        )
        if not proj_ids:
            ref = project_id or wo_ref_no
            return {'success': False, 'error': f'Project "{ref}" not found.'}

        # 5️⃣ Read only the fields we need
        fields = []
        if fetch_status:
            fields.append('state')
        if fetch_progress:
            fields += ['create_date', 'duration']
        proj = self.models.execute_kw(
            self.db, self.uid, self.password,
            'project.project', 'read', [proj_ids],
            {'fields': fields}
        )[0]

        # 6️⃣ Build the response data
        result: Dict[str, Any] = {}
        if fetch_status:
            result['status'] = proj.get('state')

        if fetch_progress:
            # parse create_date (ISO format), drop timezone if needed
            created = proj.get('create_date')
            duration = proj.get('duration') or 0
            percent = None
            try:
                # Trim fractional seconds and timezone, if present
                dt = datetime.fromisoformat(created.split('+')[0])
                days_elapsed = (datetime.utcnow() - dt).days
                percent = round(min(max(days_elapsed / duration * 100, 0), 100), 2) \
                          if duration > 0 else 0.0
            except Exception:
                percent = 0.0
            result['progress'] = percent

        return {'success': True, 'data': result}

    def work_order_papers(self, entities: Dict[str,str]) -> Dict[str,Any]:
        """
        Implements the work_order_papers intent:
            • required = "attachments"  → count + list ir.attachment on project.project
            • required = "invoices"     → count + list account.move (invoices) for that project
            • required = "pos"          → count + list purchase.order linked to project
        If required is missing or "all", returns all three groups.
        Expects entities to have:
            - 'required': str
            - either 'wo_ref_no' or 'project_id'
        """
        try:
            # 1) Auth
            if not self.uid and not self.authenticate():
                raise Exception("Authentication failed")

            wo_ref = entities.get('wo_ref_no', '').lower()
            req = entities.get('required', '').lower()

            # 2) Resolve project ID
            proj_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'project.project', 'search',
                [[['wo_ref_no', '=', wo_ref]]]
            )
            if not proj_ids:
                return {'success': False,
                        'error': f'Work order "{wo_ref}" not found'}

            proj_id = proj_ids[0]

            # 3) Determine what to fetch
            groups = {
                'attachment': req in ('attachments','attachment'),
                'invoice':    req in ('invoices','invoice'),
                'pos':         req in ('pos','purchase orders','lpo','lpos')
            }
            # if nothing matched, fetch all
            if not any(groups.values()):
                for k in groups:
                    groups[k] = True

            data: Dict[str,Any] = {}

            # ── Attachments ───────────────────────────────────────
            if groups['attachments']:
                attach_ids = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'ir.attachment', 'search',
                    [[
                        ['res_model','=', 'project.project'],
                        ['res_id',   '=', proj_id]
                    ]]
                )
                attach2_ids = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'project.attachment', 'search',
                    [[
                        ['res_model','=', 'project.project'],
                        ['res_id',   '=', proj_id]
                    ]]
                )
                items = []
                if attach_ids:
                    recs = self.models.execute_kw(
                        self.db, self.uid, self.password,
                        'ir.attachment', 'read',
                        [attach_ids],
                        {'fields': ['id','name','mimetype']}
                    )
                    for r in recs:
                        items.append({
                            'id':       r['id'],
                            'name':     r['name'],
                            'mimetype': r.get('mimetype')
                        })

                if attach2_ids:
                    recs = self.models.execute_kw(
                        self.db, self.uid, self.password,
                        'project.attachment', 'read',
                        [attach2_ids],
                        {'fields': ['id','name','mimetype']}
                    )
                    for r in recs:
                        items.append({
                            'id':       r['id'],
                            'name':     r['name'],
                            'mimetype': r.get('mimetype')
                        })
                data['attachments'] = {
                    'count': len(items),
                    'items': items
                }

            # ── Invoices ────────────────────────────────────────── 
            if groups['invoices']:
                inv_ids = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'account.move', 'search',
                    [[
                        ['project', '=', proj_id],
                        ['invoice_type','=','done']
                    ]]
                )

                items = []
                if inv_ids:
                    recs = self.models.execute_kw(
                        self.db, self.uid, self.password,
                        'account.move', 'read',
                        [inv_ids],
                        {'fields': [
                            'id', 'name', 'invoice_date',
                            'amount_total', 'partner_id',
                            'client','payment_state'
                        ]}
                    )
                    for r in recs:
                        items.append({
                            'id':           r['id'],
                            'number':       r['name'],
                            'date':         r.get('invoice_date'),
                            'vendor':       r.get('partner_id')[1] if r.get('partner_id') else None,
                            'total_amount': r.get('amount_total'),
                            'client':       r.get('client'),
                            'payment': r['payment_state']
                        })

                data['invoices'] = {
                    'count': len(items),
                    'items': items
                }


            # ── Purchase Orders ───────────────────────────────────
            if groups['pos']:
                po_domain = [
                    ['project_id', '=', proj_id]
                    ]
                po_ids = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'purchase.order.line', 'search', [po_domain]
                )
                items = []
                if po_ids:
                    po_recs = self.models.execute_kw(
                        self.db, self.uid, self.password,
                        'purchase.order.line', 'read',
                        [po_ids],
                        {'fields': [
                            'order_id', 'create_date', 'create_uid',
                            'partner_id', 'price_subtotal',
                            'price_tax', 'price_total'
                        ]}
                    )
                    for po in po_recs:
                        items.append({
                            'order_id':             po['order_id'],
                            'create_date':    po['create_date'],
                            'create_uid':     po['create_uid'] and po['create_uid'][1],
                            'partner_name':   po['partner_id'] and po['partner_id'][1],
                            'price_subtotal':   po.get('price_subtotal', 0.0),
                            'price_tax':     po.get('price_tax', 0.0),
                            'price_total':   po.get('price_total', 0.0)
                        })
                    
                data['purchase_orders'] = {
                    'count': len(items),
                    'items': items
                }

            return {'success': True, 'data': data}

        except Exception as e:
            logger.error(f"get_papers failed: {e}")
            return {'success': False, 'error': str(e)}

    def work_order_employees(self, entities: Dict[str, str]) -> Dict[str, Any]:
            """
            Returns the requested employee(s) for a work order:
            - civil engineer    → field project_eng_id
            - mechanical engineer → mechanical_eng_id
            - electrical engineer → electrical_eng_id
            - IT engineer         → it_eng_id
            - project manager     → user_id
            Entities must include:
            - 'wo_ref_no': str
            - 'required':  comma-separated roles or generic keywords
            If no specific role is found or 'all'/'employees' in required,
            returns all five.
            """
            # 1️⃣ Auth
            if not self.uid and not self.authenticate():
                return {'success': False, 'error': 'Authentication failed.'}

            # 2️⃣ Parse inputs
            wo_ref   = entities.get('wo_ref_no', '').strip()
            required = entities.get('required', '').lower()
            if not wo_ref:
                return {'success': False, 'error': 'No work-order reference provided.'}

            # 3️⃣ Figure out which roles were requested
            role_map = {
                'civil':       'project_eng_id',
                'mechanical':  'mechanical_eng_id',
                'electrical':  'electrical_eng_id',
                'it':          'it_eng_id',
                'pm':     'user_id'
            }
            requested = []
            for key in role_map:
                if re.search(rf'\b{key}\b', required):
                    requested.append(key)

            # if nothing specific or generic terms, return all roles
            if not requested or re.search(r'\b(all|employees|engineers?)\b', required):
                requested = list(role_map.keys())

            # 4️⃣ Lookup the project
            proj_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'project.project', 'search',
                [[['wo_ref_no', '=', wo_ref]]]
            )
            if not proj_ids:
                return {'success': False,
                        'error': f'Work order "{wo_ref}" not found.'}
            proj_id = proj_ids[0]

            # 5️⃣ Read the employee‐pointer fields
            fields = [role_map[r] for r in requested]
            proj = self.models.execute_kw(
                self.db, self.uid, self.password,
                'project.project', 'read',
                [[proj_id]],
                {'fields': fields}
            )[0]

            # 6️⃣ Collect non‐null employee IDs
            emp_ids = []
            role_to_eid: Dict[str,int] = {}
            for role in requested:
                val = proj.get(role_map[role])
                if isinstance(val, (list, tuple)) and val:
                    eid = val[0]
                    emp_ids.append(eid)
                    role_to_eid[role] = eid

            if not emp_ids:
                return {'success': True, 'data': {'employees': []}}

            
            # 7️⃣ Separate manager vs. engineer IDs
            manager_id = role_to_eid.get('manager')
            eng_ids    = [eid for role, eid in role_to_eid.items() if role != 'manager']

            # 8️⃣ Read engineers from hr.employee
            eng_records = []
            if eng_ids:
                eng_records = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'hr.employee', 'read',
                    [eng_ids],
                    {'fields': ['id', 'name', 'job_id']}
                )

            # Turn engineer records into a dict for lookup
            eng_dict = {rec['id']: rec for rec in eng_records}

            # 9️⃣ Read manager from res.users
            mgr_record = None
            if manager_id:
                try:
                    mgr_record = self.models.execute_kw(
                        self.db, self.uid, self.password,
                        'res.users', 'read',
                        [[manager_id]],
                        {'fields': ['id', 'name']}
                    )[0]
                except Exception:
                    mgr_record = None

            #  🔟 Build the final `employees` list
            employees: List[Dict[str, Any]] = []

            for role in requested:
                if role == 'manager':
                    if mgr_record:
                        employees.append({
                            'role':     'manager',
                            'id':       mgr_record['id'],
                            'name':     mgr_record['name'],
                            'position': 'Project Manager'
                        })
                else:
                    eid = role_to_eid.get(role)
                    rec = eng_dict.get(eid)
                    if rec:
                        job = rec.get('job_id')  # MANY2ONE [id, title]
                        employees.append({
                            'role':     role,
                            'id':       rec['id'],
                            'name':     rec['name'],
                            'position': job[1] if isinstance(job, (list, tuple)) and len(job) > 1 else None
                        }) 

            return {'success': True, 'data': {'employees': employees}}

    def call_method(self, method, **params):
        if hasattr(self, method):
            func = getattr(self, method)
            if callable(func):
                return func(**params)
            else:
                raise AttributeError(f"Attribute {method} is not callable on OdooClient")
        else:
            raise AttributeError(f"Method {method} not found in OdooClient")

