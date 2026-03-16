# Improve UX Monitoring Task Pack

This task pack breaks the monitoring UX cleanup into small, dependency-ordered steps.

The target end state is:

- `cd /Users/jjae/Documents/guthib/cc-deep-research/dashboard`
- `npm run dev`
- open `http://localhost:3000`
- start research from the web UI
- watch live progress and final report in the browser

Design constraints for this pack:

- extract shared research execution into reusable application code
- keep `cc-deep-research research` as a thin in-process caller of that shared service
- let the FastAPI backend call the same service for browser-started runs
- avoid making the CLI depend on a running server for normal local usage

## Task Order

1. [001_shared_research_run_contract.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/001_shared_research_run_contract.md)
2. [002_config_override_normalization.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/002_config_override_normalization.md)
3. [003_report_output_materialization.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/003_report_output_materialization.md)
4. [004_research_run_service.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/004_research_run_service.md)
5. [005_cli_research_command_delegation.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/005_cli_research_command_delegation.md)
6. [006_dashboard_backend_runtime_state.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/006_dashboard_backend_runtime_state.md)
7. [007_start_research_run_api.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/007_start_research_run_api.md)
8. [008_research_run_status_api.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/008_research_run_status_api.md)
9. [009_session_report_api.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/009_session_report_api.md)
10. [010_dashboard_client_run_api_integration.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/010_dashboard_client_run_api_integration.md)
11. [011_home_page_research_form.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/011_home_page_research_form.md)
12. [012_submit_and_redirect_flow.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/012_submit_and_redirect_flow.md)
13. [013_session_run_status_summary.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/013_session_run_status_summary.md)
14. [014_session_report_view.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/014_session_report_view.md)
15. [015_dashboard_dev_launcher_script.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/015_dashboard_dev_launcher_script.md)
16. [016_dashboard_dev_script_wiring.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/016_dashboard_dev_script_wiring.md)
17. [017_browser_first_monitoring_docs.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/017_browser_first_monitoring_docs.md)
18. [018_monitoring_ux_validation.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/tasks/improve-ux-monitoring/018_monitoring_ux_validation.md)

