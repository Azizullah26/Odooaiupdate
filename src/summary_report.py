#from tarfile import data_filter
#from requests import check_compatibility

class SummaryReport:

    def generate_header(self, project_header: dict) -> str:
        
        lines = [
            "Report Summary",
            "─────────────────────────────────────",
            f"🔹 Project Name: {project_header.get('name','')}",
            f"🔹 Project ID: {project_header.get('id','')}",
            f"🔹 Client: {project_header.get('client_name','')}",
            f"🔹 Contract: {project_header.get('contract','')}",
            f"🔹 Work Order Amount: AED {project_header.get('wo_amount', 0.0):,.2f}",
            f"🔹 City:  {project_header.get('city','')}",
            "",
            f"🔹 Created On: {project_header.get('create_date','')}",
            f"🔹 Created By: {project_header.get('create_uid','')}",
            ""
        ]

        return "\n".join(lines)

    def generate_expense_report(self, data: dict) -> str:
        """
        Given the output of work_order_finances, returns a markdown-style
        expense summary matching the requested format.
        """
        #data = report.get('data', {})
        pos     = data.get('purchase_orders', [])
        petty   = data.get('petty_cash_total', 0.0)
        ts      = data.get('timesheet_hours_total', 0.0)
        cost    = data.get('cost')
        profit  = data.get('profit')
        dist    = data.get('distribution')
        #print(data)

        lines = []
        # 1) COST-ONLY
        if cost is not None and not pos and petty == 0 and ts == 0 and profit is None and not dist:
            lines += [
                f"**Work Order Cost:** AED {cost:,.2f}",
                "─────────────────────────────────────"
            ]
            return "\n".join(lines)

        # 2) PROFIT-ONLY
        if profit is not None and not pos and petty == 0 and ts == 0 and cost is None and not dist:
            lines += [

                f"Total Engineering Amount: AED {dist.get('total_eng_amount',0.0):,.2f}",

                f"**Profit Status:** {profit}",
                "─────────────────────────────────────"
            ]
            return "\n".join(lines)

        # 3) DISTRIBUTION-ONLY
        if dist and not pos and petty == 0 and ts == 0 and cost is None and profit is None:
            lines += [
                "**Expense Distribution:**",
                "─────────────────────────────────────",
                f"• Project Engineering Amount: AED {dist.get('project_eng_amount',0.0):,.2f}",
                f"• Mechanical Engineering Amount: AED {dist.get('mechanical_eng_amount',0.0):,.2f}",
                f"• Electrical Engineering Amount: AED {dist.get('electrical_eng_amount',0.0):,.2f}",
                f"• IT Engineering Amount: AED {dist.get('it_eng_amount',0.0):,.2f}",
                f"• **Total Engineering Amount:** AED {dist.get('total_eng_amount',0.0):,.2f}",
                "─────────────────────────────────────"
            ]
            return "\n".join(lines)

        # 4) EXPENSE (PO + Petty + Timesheet) and/or DEFAULT
        # Associated Purchase Orders
        lines += [
            "Associated Expenses (Purchase Orders):",
            "─────────────────────────────────────",
        ]
        total_po = 0.0
        if not pos:
            lines.append("– None found")
        else:
            for i, po in enumerate(pos, start=1):
                # each po['order_id'] is [id, name]
                po_name = po.get('order_id')
                po_name = po_name[1] if isinstance(po_name, (list, tuple)) and len(po_name) > 1 else po_name
                amt    = po.get('price_total', 0.0)
                tax    = po.get('price_tax',   0.0)
                net    = po.get('price_subtotal', 0.0)
                total_po += amt
                lines += [
                    f"{i}️⃣ **PO #:** {po_name}  ",
                    f"   • **Vendor:** {po.get('partner_name','')}  ",
                    f"   • **Total Amount:** AED {amt:,.2f}  ",
                    f"   • **Tax Amount:** AED {tax:,.2f}  ",
                    f"   • **Net Amount:** AED {net:,.2f}  ",
                    f"   • **Date:** {po.get('create_date','')}  ",
                    f"   • **Created By:** {po.get('create_uid','')}",
                    ""
                ]

        # Summary Totals
        lines += [
            f"**Petty Cash Total:** AED {petty:,.2f}",
            f"**Total Timesheet Amount:** AED {ts:,.2f}",
            "─────────────────────────────────────",
            f"**Total Expenses (POs):** AED {total_po:,.2f}",
            ""
        ]

        # 5) Append COST, PROFIT, DISTRIBUTION if present
        if cost is not None:
            lines.append(f"**Work Order Cost:** AED {cost:,.2f}")
            remaining = cost - total_po - petty
        if profit is not None:
            lines.append(f"**Profit Status:** {profit}")
        if dist:
            lines += [
                "",
                "**Expense Distribution:**",
                f"• Project Engineering Amount: AED {dist.get('project_eng_amount',0.0):,.2f}",
                f"• Mechanical Engineering Amount: AED {dist.get('mechanical_eng_amount',0.0):,.2f}",
                f"• Electrical Engineering Amount: AED {dist.get('electrical_eng_amount',0.0):,.2f}",
                f"• IT Engineering Amount: AED {dist.get('it_eng_amount',0.0):,.2f}",
                f"• **Total Engineering Amount:** AED {dist.get('total_eng_amount',0.0):,.2f}"
            ]

        return "\n".join(lines)

    def generate_details_report(self, data: dict) -> str:
        """
        Given the output of work_order_details, returns a markdown-style
        summary including:
        - Core details (start, end, duration, manager)
        - Purchase Orders (if any)
        - Invoices (if any)
        - Remaining balance (if provided)
        """
        #data = report.get('data', {})
        details = data.get('details', {})
        pos     = data.get('purchase_orders', [])
        invs    = data.get('invoices', [])
        balance = data.get('balance')

        lines = [
            "Work Order Details Report",
            "─────────────────────────────────────",
        ]

        # Core details
        if details:
            lines += [
                f"🔹 **Start Date:** {details.get('start_date','')}",
                f"🔹 **End Date:** {details.get('end_date','')}",
                f"🔹 **Duration:** {details.get('duration','')}",
                f"🔹 **Project Manager:** {details.get('project_manager','')}",
                ""
            ]

        # Purchase Orders
        if pos:
            lines += [
                "📦 Purchase Orders:",
                "─────────────────────────────────────",
            ]
            for i, po in enumerate(pos, start=1):
                # po['order_id'] might be [id, name]
                po_ref = po.get('order_id')
                po_name = (po_ref[1] if isinstance(po_ref, (list, tuple)) and len(po_ref) > 1
                        else po_ref)
                lines += [
                    f"{i}️⃣ **PO #:** {po_name}  ",
                    f"   • **Partner:** {po.get('partner_name','')}  ",
                    f"   • **Total:** AED {po.get('price_total',0.0):,.2f}  ",
                    ""
                ]

        # Invoices
        if invs:
            lines += [
                "🧾 Invoices:",
                "─────────────────────────────────────",
            ]
            for i, inv in enumerate(invs, start=1):
                lines += [
                    f"{i}️⃣ **Invoice #:** {inv.get('number','')}  ",
                    f"   • **Date:** {inv.get('invoice_date','')}  ",
                    f"   • **Vendor:** {inv.get('vendor','')}  ",
                    f"   • **Client:** {inv.get('client','')}  ",
                    f"   • **Payment:** {inv.get('payment_state','')}  ",
                    f"   • **Total:** AED {inv.get('total_amount',0.0):,.2f}  ",
                    ""
                ]

        # Remaining balance
        if balance is not None:
            lines += [
                "─────────────────────────────────────",
                f"✅ **Remaining Balance:** AED {balance:,.2f}",
                "─────────────────────────────────────",
            ]

        return "\n".join(lines)


    def generate_papers_report(self, data: dict) -> str:
        """
        Given the output of get_papers, returns a markdown-style summary of:
        • Attachments
        • Invoices
        • Purchase Orders
        """
        #data = report.get('data', {})
        atts = data.get('attachments', {})
        invs = data.get('invoices', {})
        poss  = data.get('purchase_orders', {})

        lines = []

        # ── Attachments ─────────────────────────────────────────
        lines += [
            "Attachments:",
            "─────────────────────────────────────",
        ]
        att_items = atts.get('items', [])
        if not att_items:
            lines.append("– None found")
        else:
            for i, att in enumerate(att_items, start=1):
                lines += [
                    f"{i}️⃣ **Attachment ID:** {att['id']}  ",
                    f"   • **Name:** {att['name']}  ",
                    f"   • **MIME Type:** {att.get('mimetype','')}  ",
                    ""
                ]

        # ── Invoices ───────────────────────────────────────────
        lines += [
        "🧾 Invoices:",
        "─────────────────────────────────────",
        ]
        inv_items = invs.get('items', [])
        if not inv_items:
            lines.append("– None found")
        else:
            for i, inv in enumerate(inv_items, start=1):
                lines += [
                    f"{i}️ Invoice #: {inv.get('number','')}  ",
                    f"   • Date: {inv.get('date','')}  ",
                    f"   • Vendor: {inv.get('vendor','')}  ",
                    f"   • Client: {inv.get('client','')}  ",
                    f"   • Type: {inv.get('type','')}  ",
                    f"   • Total Amount: AED {inv.get('total_amount',0.0):,.2f}  ",
                    ""
                ]

        # ── Purchase Orders ────────────────────────────────────
        total_po = 0.0
        lines += [
            "Purchase Orders:",
            "─────────────────────────────────────"
        ]
        pos = poss.get('items', [])
        if not pos:
            lines.append("– None found")
        else:
            for i, po in enumerate(pos, start=1):
                # each po['order_id'] is [id, name]
                po_name = po.get('order_id')
                po_name = po_name[1] if isinstance(po_name, (list, tuple)) and len(po_name) > 1 else po_name
                amt    = po.get('price_total', 0.0)
                tax    = po.get('price_tax',   0.0)
                net    = po.get('price_subtotal', 0.0)
                total_po += amt
                lines += [
                    f"{i}️⃣ **PO #:** {po_name}  ",
                    f"   • **Vendor:** {po.get('partner_name','')}  ",
                    f"   • **Total Amount:** AED {amt:,.2f}  ",
                    f"   • **Tax Amount:** AED {tax:,.2f}  ",
                    f"   • **Net Amount:** AED {net:,.2f}  ",
                    f"   • **Date:** {po.get('create_date','')}  ",
                    f"   • **Created By:** {po.get('create_uid','')}",
                    ""
                ]
        
        

        return "\n".join(lines)

    def generate_time_report(self, data: dict) -> str:
        """
        Given the output of work_order_time, returns a markdown‐style
        summary of the project’s start date, end date, and/or duration.
        """
        #data = report.get('data', {})
        lines = [
            "Time Report Summary",
            "─────────────────────────────────────",
        ]

        # Start Date
        if 'start_date' in data:
            lines.append(f"🔹 Start Date: {data['start_date']}")

        # End Date
        if 'end_date' in data:
            lines.append(f"🔹 End Date: {data['end_date']}")

        # Duration
        if 'duration' in data:
            lines.append(f"🔹 Duration: {data['duration']}")

        # If nothing was returned
        if not any(k in data for k in ('start_date', 'end_date', 'duration')):
            lines.append("– No timing information found")

        lines.append("─────────────────────────────────────")
        return "\n".join(lines)

    def generate_work_orders_report(self, data: dict) -> str:
        #data = report.get('data', {})
        orders = data.get('work_orders', [])
        count  = data.get('count', len(orders))

        lines = [
            f"Number of work orders: {count}",
            "Work Orders Summary",
            "─────────────────────────────────────"
        ]

        if not orders:
            lines.append("– No work orders found for your query.")
        else:
            for i, wo in enumerate(orders, start=1):
                lines.append(f"{i}️ {wo['wo_ref_no']} – {wo['name']}")

        lines.append("─────────────────────────────────────")
        return "\n".join(lines)

    def generate_employees_report(self, data: dict) -> str:
        """
        Given the output of work_order_employees, returns a markdown-style
        summary listing each requested employee by role, ID, name, and position.
        """
        employees = data.get('employees', [])

        lines = [
            "Work Order Employees Report",
            "─────────────────────────────────────",
        ]

        if not employees:
            lines.append("– No employees found for this work order.")
        else:
            for i, emp in enumerate(employees, start=1):
                # Capitalize the role
                role = emp.get('role', '').replace('_', ' ').title()
                lines += [
                    f"{i}️⃣ **Role:** {role}  ",
                    f"   • **ID:** {emp.get('id')}  ",
                    f"   • **Name:** {emp.get('name','')}  ",
                    f"   • **Position:** {emp.get('position','')}  ",
                    ""
                ]

        lines.append("─────────────────────────────────────")
        return "\n".join(lines)
