# Flask middleware - variables defined externally
app.before_request(csp_report_handler)  # type: ignore
app.before_request(csp_middleware)  # type: ignore





