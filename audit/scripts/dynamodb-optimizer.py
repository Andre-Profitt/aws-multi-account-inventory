#!/usr/bin/env python3
"""
DynamoDB Table Optimizer
Analyzes DynamoDB tables for optimization opportunities
"""

import json
import os
from datetime import datetime
from datetime import timedelta

import boto3


class DynamoDBOptimizer:
    def __init__(self, region: str = 'us-east-1'):
        self.dynamodb = boto3.client('dynamodb', region_name=region)
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)

    def list_tables(self) -> list[str]:
        """List all DynamoDB tables"""
        tables = []
        paginator = self.dynamodb.get_paginator('list_tables')

        for page in paginator.paginate():
            tables.extend(page['TableNames'])

        return tables

    def analyze_table(self, table_name: str) -> dict:
        """Analyze a single DynamoDB table"""
        # Get table description
        table_desc = self.dynamodb.describe_table(TableName=table_name)['Table']

        analysis = {
            'table_name': table_name,
            'status': table_desc['TableStatus'],
            'item_count': table_desc.get('ItemCount', 0),
            'size_bytes': table_desc.get('TableSizeBytes', 0),
            'billing_mode': table_desc.get('BillingModeSummary', {}).get('BillingMode', 'PROVISIONED'),
            'indexes': {
                'global': len(table_desc.get('GlobalSecondaryIndexes', [])),
                'local': len(table_desc.get('LocalSecondaryIndexes', []))
            }
        }

        # Get CloudWatch metrics
        metrics = self._get_table_metrics(table_name)
        analysis['metrics'] = metrics

        # Generate recommendations
        recommendations = self._generate_recommendations(table_desc, metrics)
        analysis['recommendations'] = recommendations

        # Calculate potential savings
        savings = self._calculate_savings(table_desc, metrics)
        analysis['potential_monthly_savings'] = savings

        return analysis

    def _get_table_metrics(self, table_name: str) -> dict:
        """Get CloudWatch metrics for the table"""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=7)

        metrics = {}

        # Define metrics to collect
        metric_configs = [
            ('ConsumedReadCapacityUnits', 'Sum'),
            ('ConsumedWriteCapacityUnits', 'Sum'),
            ('ProvisionedReadCapacityUnits', 'Average'),
            ('ProvisionedWriteCapacityUnits', 'Average'),
            ('UserErrors', 'Sum'),
            ('SystemErrors', 'Sum'),
            ('ThrottledRequests', 'Sum')
        ]

        for metric_name, stat in metric_configs:
            try:
                response = self.cloudwatch.get_metric_statistics(
                    Namespace='AWS/DynamoDB',
                    MetricName=metric_name,
                    Dimensions=[
                        {'Name': 'TableName', 'Value': table_name}
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=3600,  # 1 hour
                    Statistics=[stat]
                )

                if response['Datapoints']:
                    values = [dp[stat] for dp in response['Datapoints']]
                    metrics[metric_name] = {
                        'average': sum(values) / len(values),
                        'max': max(values),
                        'min': min(values),
                        'total': sum(values)
                    }
            except Exception as e:
                print(f"Error getting metric {metric_name}: {e}")

        return metrics

    def _generate_recommendations(self, table_desc: dict, metrics: dict) -> list[str]:
        """Generate optimization recommendations"""
        recommendations = []

        # Check billing mode
        if table_desc.get('BillingModeSummary', {}).get('BillingMode') == 'PROVISIONED':
            # Check utilization
            read_consumed = metrics.get('ConsumedReadCapacityUnits', {}).get('average', 0)
            read_provisioned = metrics.get('ProvisionedReadCapacityUnits', {}).get('average', 1)
            read_utilization = (read_consumed / read_provisioned * 100) if read_provisioned > 0 else 0

            write_consumed = metrics.get('ConsumedWriteCapacityUnits', {}).get('average', 0)
            write_provisioned = metrics.get('ProvisionedWriteCapacityUnits', {}).get('average', 1)
            write_utilization = (write_consumed / write_provisioned * 100) if write_provisioned > 0 else 0

            if read_utilization < 20 and write_utilization < 20:
                recommendations.append("Consider switching to ON_DEMAND billing mode for low utilization")
            elif read_utilization < 50:
                recommendations.append(f"Reduce provisioned read capacity (current utilization: {read_utilization:.1f}%)")
            elif write_utilization < 50:
                recommendations.append(f"Reduce provisioned write capacity (current utilization: {write_utilization:.1f}%)")

        # Check for throttling
        throttled = metrics.get('ThrottledRequests', {}).get('total', 0)
        if throttled > 0:
            recommendations.append(f"Table experienced {throttled} throttled requests - consider increasing capacity")

        # Check indexes
        gsi_count = len(table_desc.get('GlobalSecondaryIndexes', []))
        if gsi_count > 5:
            recommendations.append(f"Table has {gsi_count} GSIs - review if all are necessary")

        # Check table size
        size_gb = table_desc.get('TableSizeBytes', 0) / (1024**3)
        if size_gb > 100:
            recommendations.append(f"Large table ({size_gb:.1f} GB) - consider archiving old data")

        # Check for unused capacity
        if table_desc.get('ItemCount', 0) == 0:
            recommendations.append("Table appears to be empty - consider deletion if unused")

        return recommendations

    def _calculate_savings(self, table_desc: dict, metrics: dict) -> float:
        """Calculate potential monthly savings"""
        savings = 0.0

        if table_desc.get('BillingModeSummary', {}).get('BillingMode') == 'PROVISIONED':
            # Calculate over-provisioned capacity costs
            read_provisioned = table_desc.get('ProvisionedThroughput', {}).get('ReadCapacityUnits', 0)
            write_provisioned = table_desc.get('ProvisionedThroughput', {}).get('WriteCapacityUnits', 0)

            read_consumed = metrics.get('ConsumedReadCapacityUnits', {}).get('average', 0)
            write_consumed = metrics.get('ConsumedWriteCapacityUnits', {}).get('average', 0)

            # DynamoDB pricing (approximate)
            read_price_per_unit = 0.00013  # per RCU per hour
            write_price_per_unit = 0.00065  # per WCU per hour

            # Calculate over-provisioning
            read_over = max(0, read_provisioned - (read_consumed * 1.2))  # 20% buffer
            write_over = max(0, write_provisioned - (write_consumed * 1.2))

            monthly_hours = 730
            savings += read_over * read_price_per_unit * monthly_hours
            savings += write_over * write_price_per_unit * monthly_hours

            # Add GSI costs
            for gsi in table_desc.get('GlobalSecondaryIndexes', []):
                gsi_read = gsi.get('ProvisionedThroughput', {}).get('ReadCapacityUnits', 0)
                gsi_write = gsi.get('ProvisionedThroughput', {}).get('WriteCapacityUnits', 0)

                # Assume 50% utilization for GSIs (conservative)
                savings += gsi_read * 0.5 * read_price_per_unit * monthly_hours
                savings += gsi_write * 0.5 * write_price_per_unit * monthly_hours

        return round(savings, 2)

    def generate_report(self, output_dir: str = 'audit/reports'):
        """Generate comprehensive DynamoDB optimization report"""
        os.makedirs(output_dir, exist_ok=True)

        tables = self.list_tables()
        analyses = []
        total_savings = 0

        print(f"Analyzing {len(tables)} DynamoDB tables...")

        for table_name in tables:
            try:
                analysis = self.analyze_table(table_name)
                analyses.append(analysis)
                total_savings += analysis['potential_monthly_savings']
            except Exception as e:
                print(f"Error analyzing table {table_name}: {e}")

        # Generate report
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_tables': len(tables),
                'total_potential_savings': total_savings,
                'tables_with_recommendations': sum(1 for a in analyses if a['recommendations'])
            },
            'table_analyses': analyses
        }

        # Save JSON report
        json_file = os.path.join(output_dir, f'dynamodb-optimization-{timestamp}.json')
        with open(json_file, 'w') as f:
            json.dump(report, f, indent=2)

        # Generate HTML report
        html_file = os.path.join(output_dir, f'dynamodb-optimization-{timestamp}.html')
        self._generate_html_report(report, html_file)

        print("Reports generated:")
        print(f"  - JSON: {json_file}")
        print(f"  - HTML: {html_file}")

        return json_file

    def _generate_html_report(self, report: dict, output_file: str):
        """Generate HTML report"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>DynamoDB Optimization Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .summary {{ background: #f0f0f0; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #4CAF50; color: white; }}
                .recommendations {{ color: #ff6600; }}
                .savings {{ color: #008000; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>DynamoDB Optimization Report</h1>
            <div class="summary">
                <h2>Summary</h2>
                <p>Generated: {report['generated_at']}</p>
                <p>Total Tables Analyzed: {report['summary']['total_tables']}</p>
                <p>Tables with Recommendations: {report['summary']['tables_with_recommendations']}</p>
                <p class="savings">Total Potential Monthly Savings: ${report['summary']['total_potential_savings']:.2f}</p>
            </div>
            
            <h2>Table Analysis</h2>
            <table>
                <tr>
                    <th>Table Name</th>
                    <th>Size (GB)</th>
                    <th>Items</th>
                    <th>Billing Mode</th>
                    <th>Recommendations</th>
                    <th>Potential Savings</th>
                </tr>
        """

        for analysis in sorted(report['table_analyses'],
                             key=lambda x: x['potential_monthly_savings'],
                             reverse=True):
            size_gb = analysis['size_bytes'] / (1024**3)
            recommendations = '<br>'.join(analysis['recommendations']) if analysis['recommendations'] else 'None'

            html += f"""
                <tr>
                    <td>{analysis['table_name']}</td>
                    <td>{size_gb:.2f}</td>
                    <td>{analysis['item_count']:,}</td>
                    <td>{analysis['billing_mode']}</td>
                    <td class="recommendations">{recommendations}</td>
                    <td class="savings">${analysis['potential_monthly_savings']:.2f}</td>
                </tr>
            """

        html += """
            </table>
        </body>
        </html>
        """

        with open(output_file, 'w') as f:
            f.write(html)

if __name__ == '__main__':
    optimizer = DynamoDBOptimizer()
    optimizer.generate_report()
