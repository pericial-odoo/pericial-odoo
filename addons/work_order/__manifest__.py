# 
{
    "name": "Work Order",
    "version": "12.0.1.0.0",
    "category": "Work Order",
    "summary": "Work Order management",
    "author": "Odooapps Spain S.L.",
    "depends": ["base", "sale_management", "product", "stock", "hr", "analytic", "web_m2x_options", "purchase"],
    "data": [
        "report/work_order_reports.xml",
        "data/work_order_data.xml",
        "security/work_order_security.xml",
        "views/res_partner_views.xml",
        "views/work_order_views.xml",
        "views/sale_views.xml",
        "views/work_order_team_views.xml",
        "views/work_order_category_views.xml",
        "views/work_order_dashboard_view.xml",
        "views/hr_employee_views.xml",
        "views/account_analytic_line_views.xml",
        "views/work_order_tag_views.xml",
        "views/res_config_settings_views.xml",
        "views/product_views.xml",
        "views/work_order_templates.xml",
        "data/ir_sequence_data.xml",
        "security/ir.model.access.csv",
        "report/work_order_templates_work_order.xml",
        "wizard/work_order_make_invoice_views.xml",
    ],
    "installable": True,
    "application": True,
}
