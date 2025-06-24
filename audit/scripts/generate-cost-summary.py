#!/usr/bin/env python3
"""
Generate a markdown summary from the latest cost analysis report
"""

import json
from pathlib import Path


def find_latest_report(report_dir: str = 'audit/reports') -> str:
    """Find the most recent cost analysis report"""
    report_path = Path(report_dir)
    cost_reports = list(report_path.glob('cost-analysis-*.json'))

    if not cost_reports:
        return None

    # Sort by modification time
    latest_report = max(cost_reports, key=lambda p: p.stat().st_mtime)
    return str(latest_report)

def generate_summary():
    """Generate markdown summary from latest report"""
    report_file = find_latest_report()

    if not report_file:
        print("No cost analysis report found.")
        return

    with open(report_file) as f:
        report = json.load(f)

    # Generate summary
    print(f"**Report Date**: {report['generated_at']}")
    print(f"**Total Monthly Cost**: ${report['summary']['total_monthly_cost']:,.2f}")
    print(f"**Potential Savings**: ${report['summary']['total_potential_savings']:,.2f} ({report['summary']['savings_percentage']:.1f}%)")
    print("")

    # Top services
    print("### Top 5 Services by Cost")
    print("| Service | Monthly Cost |")
    print("|---------|-------------|")
    for service in report['service_costs'][:5]:
        print(f"| {service['service']} | ${service['cost']:,.2f} |")
    print("")

    # Optimization opportunities
    if report['optimization_recommendations']:
        print("### Top Optimization Opportunities")
        total_recs = len(report['optimization_recommendations'])
        print(f"Found {total_recs} optimization recommendations:")
        print("")

        for rec in report['optimization_recommendations'][:5]:
            savings = rec.get('estimated_monthly_savings', 0)
            if savings > 0:
                print(f"- **{rec['type']}** {rec['resource'].split('/')[-1]}: Save ${savings:,.2f}/month")

    # Unused resources summary
    total_unused = 0
    for resource_type, resources in report['unused_resources'].items():
        count = len(resources)
        if count > 0:
            cost = sum(r.get('estimated_monthly_cost', 0) for r in resources)
            total_unused += cost

    if total_unused > 0:
        print("")
        print("### Unused Resources")
        print(f"Total waste from unused resources: **${total_unused:,.2f}/month**")

if __name__ == '__main__':
    generate_summary()
