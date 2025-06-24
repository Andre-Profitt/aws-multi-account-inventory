#!/usr/bin/env python3
"""
AWS Cost Analysis Script
Analyzes costs across services and provides optimization recommendations
"""

import json
import os
from datetime import datetime
from datetime import timedelta

import boto3
import pandas as pd


class AWSCostAnalyzer:
    def __init__(self, region: str = 'us-east-1'):
        self.ce_client = boto3.client('ce', region_name=region)
        self.org_client = boto3.client('organizations', region_name=region)

    def get_cost_and_usage(
        self,
        start_date: str,
        end_date: str,
        granularity: str = 'DAILY',
        metrics: list[str] = ['UnblendedCost'],
        group_by: list[dict] = None
    ) -> dict:
        """Get cost and usage data from AWS Cost Explorer"""

        if group_by is None:
            group_by = [
                {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                {'Type': 'DIMENSION', 'Key': 'LINKED_ACCOUNT'}
            ]

        response = self.ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date,
                'End': end_date
            },
            Granularity=granularity,
            Metrics=metrics,
            GroupBy=group_by
        )

        return response

    def analyze_service_costs(self, days: int = 30) -> pd.DataFrame:
        """Analyze costs by service over the specified period"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        cost_data = self.get_cost_and_usage(
            start_date=str(start_date),
            end_date=str(end_date),
            granularity='MONTHLY',
            group_by=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
        )

        # Process data into DataFrame
        rows = []
        for result in cost_data['ResultsByTime']:
            for group in result['Groups']:
                service = group['Keys'][0]
                cost = float(group['Metrics']['UnblendedCost']['Amount'])
                rows.append({
                    'service': service,
                    'cost': cost,
                    'period': result['TimePeriod']['Start']
                })

        df = pd.DataFrame(rows)
        return df.sort_values('cost', ascending=False)

    def get_resource_recommendations(self) -> list[dict]:
        """Get cost optimization recommendations from Compute Optimizer"""
        compute_optimizer = boto3.client('compute-optimizer')
        recommendations = []

        # Get Lambda recommendations
        try:
            lambda_recs = compute_optimizer.get_lambda_function_recommendations()
            for rec in lambda_recs.get('lambdaFunctionRecommendations', []):
                recommendations.append({
                    'type': 'Lambda',
                    'resource': rec['functionArn'],
                    'finding': rec['finding'],
                    'current_memory': rec['currentMemorySize'],
                    'recommended_memory': rec['memorySizeRecommendationOptions'][0]['memorySize'] if rec['memorySizeRecommendationOptions'] else None,
                    'estimated_monthly_savings': rec.get('estimatedMonthlySavings', {}).get('value', 0)
                })
        except Exception as e:
            print(f"Error getting Lambda recommendations: {e}")

        # Get EC2 recommendations
        try:
            ec2_recs = compute_optimizer.get_ec2_instance_recommendations()
            for rec in ec2_recs.get('instanceRecommendations', []):
                recommendations.append({
                    'type': 'EC2',
                    'resource': rec['instanceArn'],
                    'finding': rec['finding'],
                    'current_type': rec['currentInstanceType'],
                    'recommended_type': rec['recommendationOptions'][0]['instanceType'] if rec['recommendationOptions'] else None,
                    'estimated_monthly_savings': rec['recommendationOptions'][0].get('estimatedMonthlySavings', {}).get('value', 0) if rec['recommendationOptions'] else 0
                })
        except Exception as e:
            print(f"Error getting EC2 recommendations: {e}")

        return recommendations

    def identify_unused_resources(self) -> dict[str, list]:
        """Identify potentially unused resources"""
        unused_resources = {
            'ebs_volumes': [],
            'elastic_ips': [],
            'load_balancers': [],
            'rds_instances': []
        }

        ec2 = boto3.client('ec2')
        elb = boto3.client('elbv2')
        rds = boto3.client('rds')

        # Unattached EBS volumes
        try:
            volumes = ec2.describe_volumes(
                Filters=[{'Name': 'status', 'Values': ['available']}]
            )
            for volume in volumes['Volumes']:
                unused_resources['ebs_volumes'].append({
                    'id': volume['VolumeId'],
                    'size': volume['Size'],
                    'type': volume['VolumeType'],
                    'estimated_monthly_cost': volume['Size'] * 0.10  # Rough estimate
                })
        except Exception as e:
            print(f"Error checking EBS volumes: {e}")

        # Unassociated Elastic IPs
        try:
            eips = ec2.describe_addresses()
            for eip in eips['Addresses']:
                if 'InstanceId' not in eip and 'NetworkInterfaceId' not in eip:
                    unused_resources['elastic_ips'].append({
                        'id': eip.get('AllocationId', eip.get('PublicIp')),
                        'ip': eip['PublicIp'],
                        'estimated_monthly_cost': 3.60  # $0.005 per hour
                    })
        except Exception as e:
            print(f"Error checking Elastic IPs: {e}")

        # Load Balancers with no targets
        try:
            lbs = elb.describe_load_balancers()
            for lb in lbs['LoadBalancers']:
                target_groups = elb.describe_target_health(
                    TargetGroupArn=lb['LoadBalancerArn']
                )
                if not target_groups['TargetHealthDescriptions']:
                    unused_resources['load_balancers'].append({
                        'name': lb['LoadBalancerName'],
                        'type': lb['Type'],
                        'estimated_monthly_cost': 16.20 if lb['Type'] == 'application' else 21.60
                    })
        except Exception as e:
            print(f"Error checking Load Balancers: {e}")

        return unused_resources

    def generate_cost_report(self, output_dir: str = 'audit/reports'):
        """Generate comprehensive cost analysis report"""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Gather all data
        service_costs = self.analyze_service_costs()
        recommendations = self.get_resource_recommendations()
        unused_resources = self.identify_unused_resources()

        # Calculate total potential savings
        total_savings = sum(rec.get('estimated_monthly_savings', 0) for rec in recommendations)

        for resource_type, resources in unused_resources.items():
            total_savings += sum(res.get('estimated_monthly_cost', 0) for res in resources)

        # Generate report
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_monthly_cost': float(service_costs['cost'].sum()),
                'total_potential_savings': total_savings,
                'savings_percentage': (total_savings / float(service_costs['cost'].sum()) * 100) if service_costs['cost'].sum() > 0 else 0
            },
            'service_costs': service_costs.to_dict('records'),
            'optimization_recommendations': recommendations,
            'unused_resources': unused_resources
        }

        # Save JSON report
        json_file = os.path.join(output_dir, f'cost-analysis-{timestamp}.json')
        with open(json_file, 'w') as f:
            json.dump(report, f, indent=2)

        # Generate markdown summary
        self._generate_markdown_summary(report, output_dir, timestamp)

        return json_file

    def _generate_markdown_summary(self, report: dict, output_dir: str, timestamp: str):
        """Generate a markdown summary of the cost report"""
        md_file = os.path.join(output_dir, f'cost-summary-{timestamp}.md')

        with open(md_file, 'w') as f:
            f.write("# AWS Cost Analysis Report\n\n")
            f.write(f"Generated: {report['generated_at']}\n\n")

            f.write("## Executive Summary\n\n")
            f.write(f"- **Total Monthly Cost**: ${report['summary']['total_monthly_cost']:,.2f}\n")
            f.write(f"- **Potential Monthly Savings**: ${report['summary']['total_potential_savings']:,.2f}\n")
            f.write(f"- **Savings Percentage**: {report['summary']['savings_percentage']:.1f}%\n\n")

            f.write("## Top Services by Cost\n\n")
            f.write("| Service | Monthly Cost |\n")
            f.write("|---------|-------------|\n")
            for service in report['service_costs'][:10]:
                f.write(f"| {service['service']} | ${service['cost']:,.2f} |\n")
            f.write("\n")

            f.write("## Optimization Recommendations\n\n")
            if report['optimization_recommendations']:
                f.write("| Resource Type | Resource | Current | Recommended | Potential Savings |\n")
                f.write("|---------------|----------|---------|-------------|------------------|\n")
                for rec in report['optimization_recommendations'][:20]:
                    resource_name = rec['resource'].split('/')[-1]
                    current = rec.get('current_memory', rec.get('current_type', 'N/A'))
                    recommended = rec.get('recommended_memory', rec.get('recommended_type', 'N/A'))
                    savings = rec.get('estimated_monthly_savings', 0)
                    f.write(f"| {rec['type']} | {resource_name} | {current} | {recommended} | ${savings:,.2f} |\n")
            else:
                f.write("No optimization recommendations available.\n")
            f.write("\n")

            f.write("## Unused Resources\n\n")
            for resource_type, resources in report['unused_resources'].items():
                if resources:
                    f.write(f"### {resource_type.replace('_', ' ').title()}\n\n")
                    total_cost = sum(res.get('estimated_monthly_cost', 0) for res in resources)
                    f.write(f"Found {len(resources)} unused resources costing approximately ${total_cost:,.2f}/month\n\n")

            f.write("\n## Action Items\n\n")
            f.write("1. Review and implement Compute Optimizer recommendations\n")
            f.write("2. Delete or deallocate unused resources\n")
            f.write("3. Consider Reserved Instances or Savings Plans for stable workloads\n")
            f.write("4. Implement tagging strategy for better cost allocation\n")
            f.write("5. Set up cost anomaly detection alerts\n")

if __name__ == '__main__':
    analyzer = AWSCostAnalyzer()
    report_file = analyzer.generate_cost_report()
    print(f"Cost analysis report generated: {report_file}")
